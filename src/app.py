import secrets
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, render_template, make_response, redirect
from flask import request, jsonify, send_file
from flask_caching import Cache
from flask_siwadoc import SiwaDoc
from jinja2 import select_autoescape
from werkzeug.exceptions import NotFound
from werkzeug.middleware.proxy_fix import ProxyFix

from src.blog.article.core.content import get_content, get_i18n_content_by_aid
from src.blog.article.core.crud import get_aid_by_title
from src.blog.article.core.views import blog_tmp_url, blog_detail_back, \
    blog_detail_aid_back, blog_detail_i18n, edit_article_back, new_article_back
from src.blog.article.metadata.handlers import persist_views
from src.blog.article.security.password import get_apw_form, check_apw_form
from src.blog.comment import create_comment, comment_page_get
from src.blog.homepage import index_page_back, tag_page_back, featured_page_back
from src.blueprints.auth import auth_bp
from src.blueprints.dashboard import dashboard_bp
from src.blueprints.media import create_media_blueprint
from src.blueprints.my import my_bp
from src.blueprints.relation import relation_bp
from src.blueprints.role import role_bp
from src.blueprints.theme import create_theme_blueprint
from src.blueprints.website import create_website_blueprint
from src.config.theme import db_get_theme
from src.error import error
from src.notification import read_all_notifications, get_notifications, read_current_notification
from src.other.diy import diy_space_put
from src.other.filters import json_filter, string_split, article_author, md2html, relative_time_filter
from src.other.report import report_back
from src.other.search import search_handler
from src.plugin import plugin_bp, init_plugin_manager
from src.setting import AppConfig
from src.upload.admin_upload import admin_upload_file
from src.upload.public_upload import handle_user_upload, handle_editor_upload, handle_file_upload_v2, upload_cover_back
from src.upload.views import upload_bulk_back
from src.user.authz.decorators import jwt_required, admin_required, origin_required
from src.user.authz.password import confirm_password_back, change_password_back
from src.user.authz.qrlogin import qr_login, check_qr_login_back, phone_scan_back
from src.user.entities import username_exists, get_avatar
from src.user.profile.social import get_user_info
from src.user.views import setting_profiles_back, change_profiles_back, \
    diy_space_back, confirm_email_back
from src.utils.http.generate_response import send_chunk_md
from src.utils.security.jwt_handler import JWTHandler
from src.utils.security.safe import is_valid_iso_language_code

app = Flask(__name__, template_folder=f'{AppConfig.base_dir}/templates', static_folder=f'{AppConfig.base_dir}/static')
app.config.from_object(AppConfig)
from src.models import db, User, Article, UserSubscription

db.init_app(app)

# 初始化 Cache
cache = Cache(app)
# 管理员密钥管理
ADMIN_KEY = secrets.token_urlsafe(32)
print(f"此密钥仅在单次运行中生效: {ADMIN_KEY}")
# 打印运行信息
print(f"running at: {AppConfig.base_dir}")
print("sys information")
print("++++++++++==========================++++++++++")
print(
    f'\n domain: {AppConfig.domain} \n title: {AppConfig.sitename} \n beian: {AppConfig.beian} \n Version: {AppConfig.sys_version} \n 三方登录api: {AppConfig.api_host} \n')
print("++++++++++==========================++++++++++")

# 初始化 SiwaDoc
siwa = SiwaDoc(
    app,
    title=f'{AppConfig.sitename} API 文档',
    version=AppConfig.sys_version,
    description=f'系统版本: {AppConfig.sys_version} | 备案号: {AppConfig.beian}'
)

# 注册蓝图
app.register_blueprint(auth_bp)
app.register_blueprint(create_website_blueprint(cache, AppConfig.domain, AppConfig.sitename))
app.register_blueprint(create_theme_blueprint(cache, AppConfig.domain, AppConfig.sys_version, AppConfig.base_dir))
app.register_blueprint(create_media_blueprint(cache, AppConfig.domain, AppConfig.base_dir))
app.register_blueprint(dashboard_bp)
app.register_blueprint(my_bp)
app.register_blueprint(relation_bp)
app.register_blueprint(role_bp)
app.register_blueprint(plugin_bp)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1)  # 添加 ProxyFix 中间件

# 初始化插件管理器
init_plugin_manager(app)

# 移除默认的日志处理程序
app.logger.handlers = []

# 配置 Jinja2 环境
app.jinja_env.autoescape = select_autoescape(['html', 'xml'])
app.jinja_env.add_extension('jinja2.ext.loopcontrols')

# 新增日志处理程序
app.logger.info("app.py logging已启动，并使用全局日志配置。")

domain = AppConfig.domain
global_encoding = AppConfig.global_encoding
base_dir = AppConfig.base_dir

# 注册过滤器
app.add_template_filter(json_filter, 'fromjson')
app.add_template_filter(string_split, 'string.split')
app.add_template_filter(article_author, 'Author')
app.add_template_filter(md2html, 'md2html')
app.add_template_filter(relative_time_filter, 'relative_time')


@app.context_processor
def inject_variables():
    return dict(
        beian=AppConfig.beian,
        title=AppConfig.sitename,
        username=JWTHandler.get_current_username(),
        domain=domain
    )


@app.route('/search', methods=['GET', 'POST'])
@jwt_required
def search(user_id):
    return search_handler(user_id, domain, global_encoding, app.config['MAX_CACHE_TIMESTAMP'])


import threading

# 启动持久化线程
persist_thread = threading.Thread(target=persist_views, daemon=True)
persist_thread.start()


@cache.memoize(7200)
def get_aid(title):
    return get_aid_by_title(title)


@app.route('/confirm-password', methods=['GET', 'POST'])
@jwt_required
def confirm_password(user_id):
    return confirm_password_back(user_id, cache)


@app.route('/change-password', methods=['GET', 'POST'])
@jwt_required
def change_password(user_id):
    return change_password_back(user_id, cache)


@app.route('/api/theme/upload', methods=['POST'])
@siwa.doc(
    summary='上传主题文件',
    description='上传主题文件',
    tags=['主题']
)
@admin_required
def api_theme_upload(user_id):
    app.logger.info(f'{user_id} : Try Upload file')
    return admin_upload_file(app.config['UPLOAD_LIMIT'])


@app.route('/favicon.ico', methods=['GET'])
def favicon():
    return send_file('../static/favicon.ico', mimetype='image/png', max_age=3600)


@cache.memoize(1800)
@origin_required
@app.route('/api/blog/<int:aid>', methods=['GET'])
def api_blog_content(aid):
    content, _ = get_content(identifier=aid, is_title=False, limit=9999)
    return send_chunk_md(content, aid)


@cache.memoize(1800)
@origin_required
@app.route('/api/blog/<int:aid>/i18n/<string:iso>', methods=['GET'])
def api_blog_i18n_content(iso, aid):
    if not is_valid_iso_language_code(iso):
        return jsonify({"error": "Invalid language code"}), 400
    content = get_i18n_content_by_aid(iso=iso, aid=aid)
    return send_chunk_md(content, aid, iso)


@app.route('/p/<slug_name>', methods=['GET', 'POST'])
def blog_detail(slug_name):
    return blog_detail_back(blog_slug=slug_name)


@app.route('/<int:aid>.html/<string:iso>/<string:slug_name>', methods=['GET', 'POST'])
def blog_detail_i18n_route(aid, iso, slug_name):
    return blog_detail_i18n(aid=aid, blog_slug=slug_name, i18n_code=iso)


@app.route('/<int:aid>.html', methods=['GET', 'POST'])
def blog_detail_aid(aid):
    return blog_detail_aid_back(aid=aid)


@app.route('/api/article/unlock', methods=['GET', 'POST'])
@siwa.doc(
    summary='文章解锁',
    description='文章解锁',
    tags=['文章']
)
def api_article_unlock():
    return blog_tmp_url(domain=domain, cache_instance=cache)


@app.route('/tmpView', methods=['GET', 'POST'])
def temp_view():
    url = request.args.get('url')
    if url is None:
        return jsonify({"message": "Missing URL parameter"}), 400

    aid = cache.get(f"temp-url_{url}")
    print(aid)

    if aid is None:
        return jsonify({"message": "Temporary URL expired or invalid"}), 404
    else:
        return blog_detail_aid_back(aid=aid, safeMode=False)


@app.route('/api/comment/<article_id>', methods=['POST'])
@siwa.doc(
    summary='添加评论',
    tags=['评论']
)
@jwt_required
def api_comment(user_id, article_id):
    return create_comment(user_id, article_id)


@app.route("/api/comment/<article_id>", methods=['GET'])
@jwt_required
def comment(user_id, article_id):
    return comment_page_get(user_id, article_id)


@app.route('/api/report', methods=['POST'])
@siwa.doc(
    summary='举报内容',
    description='举报内容',
    tags=['举报']
)
@jwt_required
def api_report(user_id):
    return report_back(user_id)


@cache.memoize(120)
@app.route('/api/user/avatar', methods=['GET'])
@siwa.doc(
    description='获取用户头像',
    tags=['用户']
)
def api_user_avatar(user_identifier=None, identifier_type='id'):
    user_id = request.args.get('id')
    if user_id is not None:
        user_identifier = int(user_id)
        identifier_type = 'id'
    avatar_url = get_avatar(domain, user_identifier=user_identifier, identifier_type=identifier_type)
    if avatar_url:
        return avatar_url
    else:
        avatar_url = app.config['AVATAR_SERVER']  # 默认头像服务器地址
        return avatar_url


@app.route('/profile')
@jwt_required
def profile(user_id):
    """当前用户的个人资料页面"""
    return redirect(f'/space/{user_id}')


@app.route('/space/<int:target_user_id>')
@jwt_required
def user_space(user_id, target_user_id):
    try:
        """用户空间页面 - 显示用户资料和文章"""
        target_user = User.query.get_or_404(target_user_id)

        # 判断是否为当前用户自己的空间
        is_own_profile = user_id == target_user_id

        # 获取用户统计数据
        stats = {
            'articles_count': Article.query.filter_by(user_id=target_user_id, status='Published').count(),
            'followers_count': UserSubscription.query.filter_by(subscribed_user_id=target_user_id).count(),
            'following_count': UserSubscription.query.filter_by(subscriber_id=target_user_id).count(),
            'total_views': db.session.query(db.func.sum(Article.views)).filter_by(user_id=target_user_id,
                                                                                  status='Published').scalar() or 0,
            'total_likes': db.session.query(db.func.sum(Article.likes)).filter_by(user_id=target_user_id,
                                                                                  status='Published').scalar() or 0
        }

        # 获取用户最新发布的文章
        recent_articles = Article.query.filter_by(
            user_id=target_user_id,
            status='Published'
        ).order_by(Article.updated_at.desc()).limit(6).all()

        # 检查当前用户是否已关注目标用户
        is_following = False
        if user_id != target_user_id:
            is_following = UserSubscription.query.filter_by(
                subscriber_id=user_id,
                subscribed_user_id=target_user_id
            ).first() is not None

        return render_template('profile.html',
                               target_user=target_user,
                               is_own_profile=is_own_profile,
                               is_following=is_following,
                               stats=stats,
                               recent_articles=recent_articles)
    except Exception as e:
        print(e)


@app.route('/api/tags/suggest', methods=['GET'])
def suggest_tags():
    prefix = request.args.get('prefix', '')
    # 从数据库获取匹配的标签
    tags = [2025, 2026, 2027]
    return jsonify(tags)


@app.route('/new', methods=['GET', 'POST'])
@app.route('/article/new', methods=['GET', 'POST'])
@jwt_required
def new_article(user_id):
    return new_article_back(user_id)


@app.route('/', methods=['GET'])
@app.route('/index.html', methods=['GET'])
@cache.cached(timeout=180, query_string=True)
def index_html():
    return index_page_back()


@app.route('/tag/<tag_name>', methods=['GET'])
@cache.cached(timeout=300, query_string=True)
def tag_page(tag_name):
    return tag_page_back(tag_name, global_encoding)


@app.route('/featured', methods=['GET'])
@cache.cached(timeout=300, query_string=True)
def featured_page():
    return featured_page_back()


def validate_api_key(api_key):
    if api_key == ADMIN_KEY:
        return True
    else:
        return False


@app.route('/upload/bulk', methods=['GET', 'POST'])
@jwt_required
def upload_bulk(user_id):
    if request.method == 'POST':
        api_key = request.form.get('API_KEY')
        if not validate_api_key(api_key):
            return jsonify([{"filename": "无法上传", "status": "failed", "message": "API_KEY 错误"}]), 403
    return upload_bulk_back(user_id, cache, app.config['UPLOAD_LIMIT'])


@app.route('/diy/space', methods=['GET'])
@jwt_required
def diy_space(user_id):
    return diy_space_back(user_id, avatar_url=api_user_avatar(user_id), profiles=api_user_profile(user_id),
                          user_bio=api_user_bio(user_id))


@app.route('/edit/blog/<int:aid>', methods=['GET', 'POST', 'PUT'])
@jwt_required
def markdown_editor(user_id, aid):
    return edit_article_back(user_id, aid)


@app.route('/setting/profiles', methods=['GET'])
@jwt_required
def setting_profiles(user_id):
    user_info = api_user_profile(user_id=user_id)
    return setting_profiles_back(user_id, user_info, cache, app.config['AVATAR_SERVER'])


@app.route('/setting/profiles', methods=['PUT'])
@jwt_required
def change_profiles(user_id):
    return change_profiles_back(user_id, cache, domain)


# 验证并执行换绑的路由
@app.route('/api/change-email/confirm/<token>', methods=['GET'])
@jwt_required
def confirm_email_change(user_id, token):
    return confirm_email_back(user_id, cache, token)


@cache.cached(timeout=2 * 60, key_prefix='current_theme')
@app.route('/api/theme', methods=['GET'])
@siwa.doc(
    summary='获取当前主题',
    tags=['主题'],
)
def get_current_theme():
    return db_get_theme()


@app.route("/@<user_name>")
def user_diy_space(user_name):
    @cache.cached(timeout=300, key_prefix=f'current_{user_name}')
    def _user_diy_space():
        user_id = username_exists(user_name)
        user_path = Path(base_dir) / 'media' / user_id / 'index.html'
        print(user_path)
        if user_path.exists():
            with user_path.open('r', encoding=global_encoding) as f:
                return f.read()
        else:
            return "用户主页未找到", 404

    return _user_diy_space()


@app.route("/diy/space", methods=['PUT'])
@jwt_required
def diy_space_upload(user_id):
    print("111")
    return diy_space_put(base_dir=base_dir, user_id=user_id, encoding=global_encoding)


@app.route('/api/user/bio/<int:user_id>', methods=['GET'])
@siwa.doc(
    description="获取用户的个人简介",
    tags=["用户"]
)
def api_user_bio(user_id):
    user_info = api_user_profile(user_id=user_id)
    bio = user_info[6] if len(user_info) > 6 and user_info[6] else ""
    return bio


@app.route('/api/user/profile/<int:user_id>', methods=['GET'])
@cache.memoize(timeout=300)
@siwa.doc(
    summary="获取用户的个人信息",
    description="获取用户的个人信息，包括用户名、邮箱、个人简介、头像等。",
    tags=["用户"]
)
def api_user_profile(user_id):
    return get_user_info(user_id)


@cache.cached(timeout=600, key_prefix='username_check')
def api_username_check(username):
    return username_exists(username)


@app.route('/api/messages/read', methods=['POST'])
@siwa.doc(
    summary="标记消息为已读",
    description="标记消息为已读。",
    tags=["消息"]
)
@jwt_required
def read_notification(user_id):
    nid = request.args.get('nid')
    return read_current_notification(user_id, nid)


@app.route('/api/messages', methods=['GET'])
@siwa.doc(
    summary="获取消息列表",
    description="获取消息列表。",
    tags=["消息"]
)
@jwt_required
def fetch_message(user_id):
    return get_notifications(user_id)


@app.route('/api/messages/read_all', methods=['POST'])
@siwa.doc(
    summary="标记所有消息为已读",
    description="标记所有消息为已读。",
    tags=["消息"]
)
@jwt_required
def mark_all_as_read(user_id):
    return read_all_notifications(user_id)


@app.route('/api/media/upload', methods=['POST'])
@siwa.doc(
    summary="上传文件",
    description="上传文件，返回外链 URL。",
    tags=["文件"]
)
@jwt_required
def upload_user_path(user_id):
    return handle_user_upload(user_id=user_id, allowed_size=app.config['UPLOAD_LIMIT'],
                              allowed_mimes=app.config['ALLOWED_MIMES'], check_existing=False)


@app.route('/api/upload/files', methods=['POST'])
@siwa.doc(
    summary="编辑时上传文件",
    description="上传文件，返回外链 URL。",
    tags=["文件"]
)
@jwt_required
def handle_file_upload(user_id):
    return handle_editor_upload(domain=domain, user_id=user_id, allowed_size=app.config['UPLOAD_LIMIT'],
                                allowed_mimes=app.config['ALLOWED_MIMES'])


@app.route('/api/upload/files/v2', methods=['POST'])
@jwt_required
def handle_file_upload_v2_test(user_id):
    return handle_file_upload_v2(user_id=user_id, domain=domain, base_path=base_dir)


@app.route('/api/upload/cover', methods=['POST'])
@jwt_required
def upload_cover(user_id):
    cover_path = Path(base_dir) / 'static' / 'cover'
    # print(cover_path)
    return upload_cover_back(user_id=user_id, base_path=cover_path)


@app.route('/api/article/password-form/<int:aid>', methods=['GET'])
@jwt_required
def get_password_form(user_id, aid):
    return get_apw_form(aid)


# 密码更改 API
@app.route('/api/article/password/<int:aid>', methods=['POST'])
@jwt_required
def api_update_article_password(user_id, aid):
    return check_apw_form(aid)


@app.route('/health')
def health_check():
    """健康检查端点"""
    return jsonify({
        "status": "healthy",
        "message": "Application is running",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200


@app.route('/api/routes')
def list_all_routes():
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            "endpoint": rule.endpoint,
            "path": rule.rule,
            "methods": sorted(rule.methods)
        })
    return jsonify({"routes": routes})


@app.route('/api/qr/generate', methods=['GET'])
def generate_qr():
    """Generate QR code for login"""
    try:
        token_json, qr_code_base64, token_expire, token = qr_login(
            sys_version="1.0", global_encoding=global_encoding, domain=domain
        )

        # Store token in cache
        cache.set(f"QR-token_{token}", token_json, timeout=180)

        return jsonify({
            'success': True,
            'qr_code': f"data:image/png;base64,{qr_code_base64}",
            'token': token,
            'expires_at': token_expire,
            'status': 'pending'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Failed to generate QR code'
        }), 500


@app.route('/api/phone/scan', methods=['GET'])
@jwt_required
def phone_scan(user_id):
    return phone_scan_back(user_id, cache)


@app.route('/api/qr/status', methods=['GET', 'POST'])
def check_qr_status():
    """Check QR code login status"""
    return check_qr_login_back(cache)


@app.route('/api/mobile/login', methods=['GET', 'POST'])
def mobile_login():
    """Mobile login page for QR scanning"""
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        email = data.get('email')
        password = data.get('password')

        from flask_bcrypt import check_password_hash
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            # Generate JWT tokens
            jwt_token = JWTHandler.generate_token(user.id, user.username)
            refresh_token = JWTHandler.generate_refresh_token(user.id)
            # Set cookies for mobile QR scanning
            response = make_response(jsonify({
                'success': True,
                'message': 'Login successful',
                'user': user.to_dict()
            }) if request.is_json else redirect('/api/mobile/scanner'))

            response.set_cookie('jwt', jwt_token, httponly=True, secure=False, max_age=3600)
            response.set_cookie('refresh_token', refresh_token, httponly=True, secure=False, max_age=604800)

            return response
        else:
            if request.is_json:
                return jsonify({
                    'success': False,
                    'message': 'Invalid email or password'
                }), 401
            else:
                return render_template('mobile/login.html', error='Invalid email or password')

    return render_template('mobile/login.html')


@app.errorhandler(500)
@app.errorhandler(Exception)
def handle_error(e):
    if isinstance(e, NotFound):
        return error(message="页面未找到", status_code=404)
    elif isinstance(e, Exception):
        return error(message="服务器错误", status_code=500)
    else:
        return error(message="未知错误", status_code=500)


@app.route('/<path:undefined_path>')
def undefined_route(undefined_path):
    error_message = f"Undefined path: {undefined_path}"
    app.logger.error(error_message)
    return error(message=error_message, status_code=500)


if __name__ == "__main__":
    app.run()
