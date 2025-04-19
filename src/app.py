import base64
import datetime
import hashlib
import io
import json
import logging
import os
import random
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import markdown
import qrcode
import requests
from PIL import Image
from flask import Flask, render_template, redirect, request, url_for, jsonify, send_file, \
    make_response, send_from_directory
from flask_caching import Cache
from jinja2 import select_autoescape, TemplateNotFound
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

from src.blog.article.core.content import get_article_last_modified, get_file_summary, \
    delete_article, save_article_changes, edit_article_content
from src.blog.article.core.crud import get_articles_by_owner, read_hidden_articles, delete_db_article, fetch_articles, \
    get_articles_recycle
from src.blog.article.metadata.handlers import get_article_metadata, upsert_article_metadata
from src.blog.article.security.password import update_article_password
from src.blog.comment import get_comments, create_comment, delete_comment
from src.blog.tag import update_article_tags
from src.blueprints.auth import auth_bp
from src.blueprints.dashboard import dashboard_bp
from src.blueprints.media import create_media_blueprint
from src.blueprints.theme import create_theme_blueprint
from src.blueprints.website import create_website_blueprint
from src.config.general import get_general_config
from src.config.mail import zy_mail_conf
from src.config.theme import db_get_theme
from src.database import get_db_connection
from src.error import error
from src.media.permissions import verify_file_permissions
from src.media.processing import handle_cover_resize
from src.notification import get_sys_notice, read_notification
from src.other.report import report_add
from src.other.search import search_handler
from src.upload.admin_upload import admin_upload_file
from src.upload.public_upload import handle_user_upload, save_bulk_article_db
from src.user.authz.core import secret_key, get_username, authenticate_refresh_token, generate_jwt
from src.user.authz.decorators import jwt_required, admin_required, origin_required
from src.user.authz.login import tp_mail_login
from src.user.authz.password import update_password, validate_password
from src.user.entities import query_blog_author, authorize_by_aid, get_user_sub_info, check_user_conflict, \
    db_save_avatar, db_save_bio, db_change_username, db_bind_email, authorize_by_aid_deleted
from src.user.profile.social import get_following_count, get_can_followed, get_follower_count
from src.utils.http.etag import generate_etag
from src.utils.security.ip_utils import get_client_ip, anonymize_ip_address
from src.utils.security.safe import run_security_checks, random_string
from src.utils.user_agent.parser import user_agent_info

global_encoding = 'utf-8'

app = Flask(__name__, template_folder='../templates', static_folder="../static")
app.config['CACHE_TYPE'] = 'simple'
cache = Cache(app)
app.secret_key = secret_key

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

domain, sitename, beian, sys_version, api_host, app_id, app_key, DEFAULT_KEY = get_general_config()
print("please check information")
print("++++++++++==========================++++++++++")
print(
    f'\n domain: {domain} \n title: {sitename} \n beian: {beian} \n Version: {sys_version} \n 三方登录api: {api_host} \n')
print("++++++++++==========================++++++++++")

app.register_blueprint(auth_bp)
app.register_blueprint(create_website_blueprint(cache, domain, sitename))
app.register_blueprint(create_theme_blueprint(cache, domain, sys_version, base_dir))
app.register_blueprint(create_media_blueprint(cache, domain, base_dir))
app.register_blueprint(dashboard_bp)
app.config['SESSION_COOKIE_NAME'] = 'zb_session'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=48)
app.config['TEMP_FOLDER'] = 'temp/upload'
# 定义随机头像服务器
app.config['AVATAR_SERVER'] = "https://api.7trees.cn/avatar"
# 定义允许上传的文件类型/文件大小
app.config['ALLOWED_MIMES'] = [
    # 常见图片格式
    'image/jpeg',
    'image/png',
    'image/gif',
    'image/bmp',
    'image/tiff',
    'image/webp',

    # 常见视频格式
    'video/mp4',
    'video/avi',
    'video/mpeg',
    'video/quicktime',
    'video/x-msvideo',
    'video/mp2t',
    'video/x-flv',
    'video/webm',
    'video/x-m4v',
    'video/3gpp'
]
app.config['UPLOAD_LIMIT'] = 60 * 1024 * 1024
# 定义文件最大可编辑的行数
app.config['MAX_LINE'] = 1000
# 定义rss和站点地图的缓存时间（单位:s）
app.config['MAX_CACHE_TIMESTAMP'] = 7200
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1)  # 添加 ProxyFix 中间件

# 移除默认的日志处理程序
app.logger.handlers = []

# 配置 Jinja2 环境
app.jinja_env.autoescape = select_autoescape(['html', 'xml'])
app.jinja_env.add_extension('jinja2.ext.loopcontrols')

# 新增日志处理程序
log_formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
file_handler = logging.FileHandler('temp/app.log', encoding=global_encoding)
file_handler.setFormatter(log_formatter)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)


@app.context_processor
def inject_variables():
    return dict(
        beian=beian,
        title=sitename,
        username=get_username(),
        domain=domain
    )


@app.before_request
def check_jwt_expiration():
    # 检查 JWT 是否即将过期
    token = request.cookies.get('jwt')
    if token:
        payload = jwt.decode(token, app.secret_key, algorithms=['HS256'], options={"verify_exp": False})
        if 'exp' in payload and datetime.fromtimestamp(payload['exp'], tz=timezone.utc) < datetime.now(
                tz=timezone.utc) + timedelta(minutes=60):
            # 如果 JWT 将在 60 分钟内过期，允许校验刷新令牌
            refresh_token = request.cookies.get('refresh_token')
            user_id = authenticate_refresh_token(refresh_token)
            if user_id:
                new_token = generate_jwt(user_id, payload['username'])
                response = make_response()
                response.set_cookie('jwt', new_token, httponly=True)  # 刷新 JWT
                return response


@app.route('/search', methods=['GET', 'POST'])
@jwt_required
def search(user_id):
    return search_handler(user_id, domain, global_encoding, app.config['MAX_CACHE_TIMESTAMP'])


@cache.memoize(180)
@app.route('/blog/api/<article_name>.md', methods=['GET', 'POST'])
@app.route('/api/<article_name>.md', methods=['GET', 'POST'])
@origin_required
def sys_out_file(article_name):
    hidden_articles = read_hidden_articles()
    if article_name in hidden_articles:
        # 隐藏的文章
        return error(message="页面不见了", status_code=404)

    articles_dir = os.path.join(base_dir, 'articles')
    return send_from_directory(articles_dir, article_name + '.md')


def get_user_bio(user_id):
    user_info = cache.get(f"{user_id}_userInfo") or get_profiles(user_id=user_id)

    if user_info is None:
        # 处理未找到用户信息的情况
        return "用户信息未找到", 404
    cache.set(f'{user_id}_userInfo', user_info)
    bio = user_info[6] if len(user_info) > 6 and user_info[6] else "这人很懒，什么也没留下"
    return bio


def get_profiles(user_id):
    if not user_id:
        return []

    cached_profiles = cache.get(f"userProfiles_{user_id}")
    if cached_profiles:
        return cached_profiles

    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            query = "SELECT * FROM users WHERE `id` = %s;"
            params = (user_id,)
            cursor.execute(query, params)
            info = cursor.fetchone()

            if info:
                info_list = list(info)
                if len(info_list) > 2:
                    del info_list[2]
                    cache.set(f"userProfiles_{user_id}", info_list, timeout=300)
                return info_list
            else:
                return []

    except Exception as e:
        logging.error(f"An error occurred: {e}")
    finally:
        db.close()


@cache.cached(timeout=1800, key_prefix='article_info')
def get_article_info(articles):
    articles_info = []
    for a_title in articles:
        try:
            article_info = ''
            db = get_db_connection()

            try:
                article_info += get_article_last_modified(a_title)
                article_info += ';'
                with db.cursor() as cursor:
                    query = "SELECT * FROM articles WHERE Title = %s"
                    cursor.execute(query, (a_title,))
                    result = cursor.fetchone()
                    if result:
                        article_info += result[2]
                        article_info += ";"
                        article_info += str(result[5])
                        article_info += ";"
                        article_info += str(result[6])
                    else:
                        article_info += '官方;0;0'
            except Exception as e:
                print(f"An error occurred: {e}")
            finally:
                try:
                    cursor.close()
                except NameError:
                    pass
                db.close()

            articles_info.append(article_info)
        except FileNotFoundError:
            articles_info.append('点赞：0 评论：0')
    return articles_info


@cache.cached(timeout=1800, key_prefix='summary')
def get_summary(articles):
    articles_summary = []
    for a_title in articles:
        try:
            summary = get_file_summary(a_title)
            articles_summary.append(summary)
        except FileNotFoundError:
            articles_summary.append('获取摘要失败')
    return articles_summary


@app.route('/confirm-password', methods=['GET', 'POST'])
@jwt_required
def confirm_password(user_id):
    return validate_password(user_id)


@app.route('/change-password', methods=['GET', 'POST'])
@jwt_required
def change_password(user_id):
    ip = get_client_ip(request)
    return update_password(user_id, ip)


@app.route('/Admin_upload', methods=['POST'])
@admin_required
def upload_file1(user_id):
    app.logger.info(f'{user_id} : Try Upload file')
    return admin_upload_file(app.config['UPLOAD_LIMIT'])


@app.route('/login/<provider>')
def cc_login(provider):
    if run_security_checks(api_host):
        pass
    else:
        return error(message="彩虹聚合登录API接口配置错误,您的程序无法使用第三方登录", status_code='503'), 503
    if provider not in ['qq', 'wx', 'alipay', 'sina', 'baidu', 'huawei', 'xiaomi', 'dingtalk', 'douyin']:
        return jsonify({'message': 'Invalid login provider'})

    redirect_uri = domain + "callback/" + provider

    api_safe_check = [api_host, app_id, app_key]
    if 'error' in api_safe_check:
        return error(message=api_safe_check, status_code='503'), 503
    login_url = f'{api_host}connect.php?act=login&appid={app_id}&appkey={app_key}&type={provider}&redirect_uri={redirect_uri}'
    response = requests.get(login_url)
    data = response.json()
    code = data.get('code')
    msg = data.get('msg')
    if code == 0:
        cc_url = data.get('url')
    else:
        return error(message=msg, status_code='503')

    return redirect(cc_url, 302)


@app.route('/callback/<provider>')
def callback(provider):
    if provider not in ['qq', 'wx', 'alipay', 'sina', 'baidu', 'huawei', 'xiaomi', 'dingtalk']:
        return jsonify({'message': 'Invalid login provider'})

    authorization_code = request.args.get('code')

    callback_url = f'{api_host}connect.php?act=callback&appid={app_id}&appkey={app_key}&type={provider}&code={authorization_code}'

    response = requests.get(callback_url)
    data = response.json()
    code = data.get('code')
    msg = data.get('msg')
    if code == 0:
        social_uid = data.get('social_uid')
        ip = get_client_ip(request)
        user_email = social_uid + f"@{provider}.com"
        return tp_mail_login(user_email, ip)

    return render_template('LoginRegister.html', error=msg)


@app.route('/favicon.ico', methods=['GET'])
def favicon():
    return send_file('../static/favicon.ico', mimetype='image/png', max_age=3600)


@cache.cached(timeout=3 * 3600, key_prefix='article_img')
@app.route('/blog/<article_name>/images/<image_name>', methods=['GET'])
def article_img(article_name, image_name):
    author_uid, author = query_blog_author(article_name)
    if author is None:
        author = 'test'
    articles_img_dir = os.path.join(base_dir, 'media', str(author))
    return send_from_directory(articles_img_dir, image_name)


@app.route('/preview', methods=['GET'])
@jwt_required
def sys_out_prev_page(user_id):
    user = request.args.get('user')
    file_name = request.args.get('file_name')
    prev_file_path = os.path.join(base_dir, 'media', str(user), file_name)
    if not os.path.exists(prev_file_path):
        return error(message=f'{file_name}不存在', status_code=404)
    else:
        app.logger.info(f'{user_id} preview: {file_name}')
        return render_template('zyDetail.html', article_content=1,
                               articleName=f"prev_{file_name}", domain=domain,
                               url_for=url_for, article_Surl='-')


@app.route('/api/mail')
@jwt_required
def api_mail(user_id):
    from src.notification import send_email
    smtp_server, stmp_port, sender_email, password = zy_mail_conf()
    receiver_email = sender_email
    subject = '安全通知邮件'  # 邮件主题
    body = '这是一封测试邮件。'  # 邮件正文
    send_email(sender_email, password, receiver_email, smtp_server, int(stmp_port), subject=subject,
               body=body)
    app.logger.info(f'{user_id} sendMail')
    return 'success'


@app.route('/api/follow', methods=['GET', 'POST'])
@jwt_required
def follow_user(user_id):
    follow_id = request.args.get('fid')

    if not user_id or not follow_id:
        return jsonify({'follow_code': 'failed', 'message': '用户ID或关注ID不能为空'})

    # 首次尝试从缓存中读取用户的关注列表
    user_followed = cache.get(f'{user_id}_followed')

    # 如果缓存为空，则从数据库中获取所有关注并缓存
    if user_followed is None:
        db = get_db_connection()
        try:
            with db.cursor() as cursor:
                cursor.execute("SELECT `subscribed_user_id` FROM `user_subscriptions` WHERE `subscriber_id` = %s",
                               (int(user_id),))
                user_followed = [row[0] for row in cursor.fetchall()]  # 获取所有关注ID
                cache.set(f'{user_id}_followed', user_followed)  # 更新缓存
        except Exception as e:
            print(f"Exception occurred when loading from DB: {e}")
            return jsonify({'follow_code': 'failed', 'message': "error"})
        finally:
            db.close()

    # 检查是否已经关注过
    if follow_id in user_followed:
        return jsonify({'follow_code': 'success', 'message': '已关注'})

    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            # 进行关注操作
            insert_query = ("INSERT INTO `user_subscriptions` (`subscriber_id`, `subscribed_user_id`) VALUES "
                            "(%s, %s)")
            cursor.execute(insert_query, (int(user_id), int(follow_id)))
            db.commit()

            user_followed.append(follow_id)  # 更新列表
            cache.set(f'{user_id}_followed', user_followed)  # 更新缓存
            return jsonify({'follow_code': 'success'})

    except Exception as e:
        print(f"Exception occurred: {e}")
        return jsonify({'follow_code': 'failed', 'message': "error"})

    finally:
        db.close()


@app.route('/api/unfollow', methods=['GET', 'POST'])
@jwt_required
def unfollow_user(user_id):
    unfollow_id = request.args.get('fid')
    if not user_id or not unfollow_id:
        return jsonify({'unfollow_code': 'failed', 'message': '操作无效'})

    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            # 进行取关操作
            delete_query = "DELETE FROM `user_subscriptions` WHERE `subscriber_id` = %s AND `subscribed_user_id` = %s"
            cursor.execute(delete_query, (user_id, unfollow_id))
            db.commit()
            cache.set(f'{user_id}_followed', None)
            return jsonify({'unfollow_code': 'success', 'message': '成功取关'})

    except Exception as e:
        print(f"Exception occurred during unfollow: {e}, user_id: {user_id}, unfollow_id: {unfollow_id}")
        return jsonify({'unfollow_code': 'failed', 'message': "error"})
    finally:
        db.close()


@app.route('/like', methods=['GET', 'POST'])
@jwt_required
def like(user_id):
    aid = request.args.get('aid')
    if request.method == 'POST':
        if not aid:
            return jsonify({'like_code': 'failed', 'message': "error"})
        if user_id == 0:
            return jsonify({'like_code': 'failed', 'message': "请登录后操作"})
        user_liked = cache.get(f'{user_id}_liked')
        if user_liked is None:
            user_liked = []
        if aid in user_liked:
            return jsonify({'like_code': 'failed', 'message': "你已经点赞过了!!"})
        db = get_db_connection()
        try:
            with db.cursor() as cursor:
                rd_like = random.randint(3, 8)
                rd_view = random.randint(22, 33)
                query = "UPDATE `articles` SET `Likes` = `Likes` + %s WHERE `articles`.`article_id` = %s;"
                cursor.execute(query, (rd_like, int(aid),))
                query2 = "UPDATE `articles` SET `Views` = `Views` + %s WHERE `articles`.`article_id` = %s;"
                cursor.execute(query2, (rd_view, int(aid),))
                db.commit()
                user_liked.append(aid)
                cache.set(f'{user_id}_liked', user_liked)
                return jsonify({'like_code': 'success'})

        except Exception as e:
            return jsonify({'like_code': 'failed', 'message': str(e)})
        finally:
            db.close()
    else:
        return jsonify({'like_code': 'failed'})


def sanitize_user_agent(user_agent):
    if user_agent is None:
        return None
    sanitized_agent = re.sub(r'[.;,()/\s]', '', user_agent)
    return sanitized_agent


def gen_qr_token(input_string, current_time):
    ct = current_time
    rd_num = random.randint(617, 1013)
    input_string = sys_version + ct + input_string + str(rd_num)
    print(input_string)
    sha256_hash = hashlib.sha256()
    sha256_hash.update(input_string.encode(global_encoding))
    return sha256_hash.hexdigest()


@app.route("/qrlogin")
def qrlogin():
    ct = str(int(time.time()))
    user_agent = sanitize_user_agent(request.headers.get('User-Agent'))
    token = gen_qr_token(user_agent, ct)
    token_expire = str(int(time.time() + 180))
    qr_data = f"{domain}api/phone/scan?login_token={token}"

    # 生成二维码
    qr_img = qrcode.make(qr_data)
    buffered = io.BytesIO()
    qr_img.save(buffered, format="PNG")
    qr_code_base64 = base64.b64encode(buffered.getvalue()).decode(global_encoding)

    # 存储二维码状态（可以根据需要扩展）
    token_json = {'status': 'pending', 'created_at': ct, 'expire_at': token_expire}
    cache.set(f"QR-token_{token}", token_json, timeout=200)

    return jsonify({
        'qr_code': f"data:image/png;base64,{qr_code_base64}",
        'token': token,
        'expire': token_expire
    })


@app.route("/checkQRLogin")
def check_qr_login():
    token = request.args.get('token')
    cache_qr_token = cache.get(f"QR-token_{token}")
    if cache_qr_token:
        expire_at = cache_qr_token['expire_at']
        if int(expire_at) > int(time.time()):
            return success_scan()
        else:
            return jsonify({'status': 'pending'})
    else:
        return jsonify({'status': 'invalid_token'})


def success_scan():
    # 扫码成功调用此接口
    token = request.args.get('token')
    cache_qr_allowed = cache.get(f"QR-allow_{token}")
    if token and cache_qr_allowed:
        token_expire = cache_qr_allowed['expire_at']
        if int(token_expire) > int(time.time()):
            return jsonify(cache_qr_allowed)
    else:
        token_json = {'status': 'failed'}
        return jsonify(token_json)


@app.route("/api/phone/scan")
@jwt_required
def phone_scan(user_id):
    # 用户扫码调用此接口
    token = request.args.get('login_token')
    phone_token = request.cookies.get('jwt')
    refresh_token = request.cookies.get('refresh_token')
    if token:
        cache_qr_token = cache.get(f"QR-token_{token}")
        if cache_qr_token:
            ct = str(int(time.time()))
            token_expire = str(int(time.time() + 30))
            page_json = {'status': 'success', 'created_at': ct, 'expire_at': token_expire}
            cache.set(f"QR-token_{token}", page_json, timeout=60)
            allow_json = {'status': 'success', 'created_at': ct, 'expire_at': token_expire, 'token': phone_token,
                          'refresh_token': refresh_token}
            cache.set(f"QR-allow_{token}", allow_json, timeout=60)
            return render_template('inform.html', status_code=200, message='授权成功，请在30秒内完成登录')
    else:
        token_json = {'status': 'failed'}
        return jsonify(token_json)


@app.route('/api/notice', methods=['GET'])
@jwt_required
def user_notification(user_id):
    user_notices = get_sys_notice(user_id)
    return jsonify(user_notices)


@app.route('/api/notice/read')
def read_user_notification():
    read_content = read_notification()
    return jsonify(read_content), 200


def api_view_content(article, auth_key):
    html_content = '<p>没有找到内容</p>'
    if auth_key != DEFAULT_KEY:
        return html_content
    articles_dir = os.path.join(base_dir, 'articles', article + ".md")
    try:
        with open(articles_dir, 'r', encoding=global_encoding) as file:
            content = file.read()
            html_content = markdown.markdown(content)
            return html_content
    finally:
        return html_content


@cache.cached(timeout=600, key_prefix='article_passwd')
def article_passwd(aid):
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            query = "SELECT `pass` FROM article_pass WHERE aid = %s"
            cursor.execute(query, (int(aid),))
            result = cursor.fetchone()
            if result:
                return result[0]

    except ValueError as e:
        pass
    except Exception as e:
        pass

    finally:
        db.close()

    return None


@app.route('/api/article/unlock', methods=['GET', 'POST'])
@jwt_required
def api_article_unlock(user_id):
    try:
        aid = int(request.args.get('aid'))
    except (TypeError, ValueError):
        return jsonify({"message": "Invalid Article ID"}), 400

    entered_password = request.args.get('passwd')
    temp_url = ''
    uuid = random_string(16)

    response_data = {
        'aid': aid,
        'temp_url': temp_url,
    }

    # 验证密码长度
    if len(entered_password) != 4:
        return jsonify({"message": "Invalid Password"}), 400

    passwd = article_passwd(aid) or None

    if passwd is None:
        return jsonify({"message": "Authentication failed"}), 401

    if entered_password == passwd:
        cache.set(f"temp-url_{uuid}", aid, timeout=900)
        temp_url = f'{domain}tmpView?url={uuid}'
        response_data['temp_url'] = temp_url
        return jsonify(response_data), 200
    else:
        referrer = request.referrer
        app.logger.error(f"{referrer} Failed access attempt {uuid} :  {user_id}")
        return jsonify({"message": "Authentication failed"}), 401


@app.route('/tmpView', methods=['GET', 'POST'])
def temp_view():
    url = request.args.get('url')
    if url is None:
        return jsonify({"message": "Missing URL parameter"}), 400

    aid = cache.get(f"temp-url_{url}")

    if aid:
        content = '<p>无法加载文章内容</p>'
        db = get_db_connection()

        try:
            with db.cursor() as cursor:
                query = "SELECT `Title` FROM articles WHERE article_id = %s"
                cursor.execute(query, (int(aid),))
                result = cursor.fetchone()
                if result:
                    a_title = result[0]

                    content = api_view_content(a_title, DEFAULT_KEY)
        except ValueError as e:
            app.logger.error(f"Value error: {e}")
            return jsonify({"message": "Invalid article_id"}), 400
        except Exception as e:
            app.logger.error(f"Unexpected error: {e}")
            return jsonify({"message": "Internal server error"}), 500

        finally:
            cursor.close()
            db.close()
            referrer = request.referrer
            app.logger.info(f"Request from {referrer} with url {url}")
            return content
    else:
        return jsonify({"message": "Temporary URL expired or invalid"}), 404


@app.route('/api/article/PW', methods=['POST'])
@jwt_required
def api_article_password(user_id):
    try:
        aid = int(request.args.get('aid'))
    except (TypeError, ValueError):
        return jsonify({"message": "无效的文章ID"}), 400

    if aid == cache.get(f"PWLock_{user_id}"):
        return jsonify({"message": "操作过于频繁"}), 400

    new_password = request.args.get('new-passwd')

    if len(new_password) != 4:
        return jsonify({"message": "无效的密码"}), 400

    auth = authorize_by_aid(aid, user_id)

    if auth:
        cache.set(f"PWLock_{user_id}", aid, timeout=30)
        result = update_article_password(aid, new_password)
        return jsonify({'aid': aid, 'changed': result}), 200
    else:
        return jsonify({"message": "身份验证失败"}), 401


@app.route('/api/comment', methods=['POST'])
@jwt_required
def api_comment(user_id):
    try:
        aid = int(request.json.get('aid'))
        pid = int(request.json.get('pid')) or 0
    except (TypeError, ValueError):
        return jsonify({"message": "Invalid Article ID"}), 400

    if aid == cache.get(f"CommentLock_{user_id}"):
        return jsonify({"message": "操作过于频繁"}), 400

    new_comment = request.json.get('new-comment')
    if not new_comment:
        return jsonify({"message": "评论内容不能为空"}), 400

    user_ip = get_client_ip(request) or ''
    masked_ip = ''
    if user_ip:
        masked_ip = anonymize_ip_address(user_ip)

    user_agent = request.headers.get('User-Agent') or ''
    user_agent = user_agent_info(user_agent)

    cache.set(f"CommentLock_{user_id}", aid, timeout=30)
    result = create_comment(aid, user_id, pid, new_comment, masked_ip, user_agent)

    if result:
        return jsonify({'aid': aid, 'changed': True}), 201
    else:
        return jsonify({"message": "评论失败"}), 500


@app.route("/Comment")
@jwt_required
def comment(user_id):
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader('templates'))
    env.filters['fromjson'] = json_filter
    aid = request.args.get('aid')
    if not aid:
        pass
    page = request.args.get('page', default=1, type=int)

    if page <= 0:
        page = 1

    comments, has_next_page, has_previous_page = get_comments(aid, page=page, per_page=30)
    template = env.get_template('Comment.html')
    rendered = template.render(aid=aid, user_id=user_id, comments=comments,
                               has_next_page=has_next_page, has_previous_page=has_previous_page, current_page=page)
    return rendered


@app.route('/api/delete/<filename>', methods=['DELETE'])
@jwt_required
def api_delete_file(user_id, filename):
    user_name = get_username()
    arg_type = request.args.get('type')
    if arg_type == 'article':
        db = get_db_connection()
        try:
            with db.cursor() as cursor:
                cursor.execute("DELETE FROM `articles` WHERE `Title` = %s AND `user_id` = %s", (filename, user_id))
                db.commit()
                article_path = os.path.join(base_dir, 'articles', f"{filename}.md")
                if os.path.exists(article_path):
                    os.remove(article_path)
                return jsonify({'Deleted': True}), 200
        except Exception as e:
            db.rollback()
            app.logger.error(f"Error deleting article {filename}: {str(e)}")
            return jsonify({'Deleted': False}), 500
        finally:
            db.close()

    file_path = os.path.join('media', user_name, filename)
    if verify_file_permissions(file_path, user_name):
        os.remove(file_path) if os.path.exists(file_path) else None
        return jsonify({'filename': filename, 'Deleted': True}), 201
    else:
        app.logger.info(f'Delete error for {filename} by user {user_id}')
        return jsonify({'filename': filename, 'Deleted': False}), 503


@app.route('/api/report', methods=['POST'])
@jwt_required
def api_report(user_id):
    try:
        report_id = int(request.json.get('report-id'))
        report_type = request.json.get('report-type') or ''
        report_reason = request.json.get('report-reason') or ''
        reason = report_type + report_reason
    except (TypeError, ValueError):
        return jsonify({"message": "Invalid Report ID"}), 400

    if report_id == cache.get(f"reportLock{report_id}_{user_id}"):
        return jsonify({"message": "操作过于频繁"}), 400

    result = report_add(user_id, "Comment", report_id, reason)

    if result:
        cache.set(f"reportLock{report_id}_{user_id}", report_id, timeout=3600)
        return jsonify({'report-id': report_id, 'info': '举报已记录'}), 201
    else:
        return jsonify({"message": "举报失败"}), 500


@app.route('/api/comment', methods=['delete'])
@jwt_required
def api_delete_comment(user_id):
    try:
        comment_id = int(request.json.get('comment_id'))
    except (TypeError, ValueError):
        return jsonify({"message": "Invalid Comment ID"}), 400

    if comment_id == cache.get(f"deleteCommentLock_{user_id}"):
        return jsonify({"message": "操作过于频繁"}), 400

    result = delete_comment(user_id, comment_id)

    if result:
        cache.set(f"deleteCommentLock_{user_id}", comment_id, timeout=30)
        return jsonify({"message": "删除成功"}), 201
    else:
        return jsonify({"message": "操作失败"}), 500


@app.template_filter('fromjson')
def json_filter(value):
    """将 JSON 字符串解析为 Python 对象"""
    if not isinstance(value, str):
        print(f"Unexpected type for value: {type(value)}. Expected a string.")
        return None

    try:
        result = json.loads(value)
        return result
    except (ValueError, TypeError) as e:
        print(f"Error parsing JSON: {e}, Value: {value}")
        return None


@app.route('/static/music/music.json', methods=['GET'])
@jwt_required
def music_json(user_id):
    referrer = request.referrer
    if referrer and "@" in referrer:
        username_from_referrer = referrer.split('@')[-1]
        user_dir = os.path.join('media', username_from_referrer)
        # 确保 user_dir 是字符串类型
        user_dir = base_dir + '\\' + str(user_dir)
        return send_from_directory(user_dir, 'music.json')
    if not user_id:
        return send_from_directory(app.static_folder, 'music/music.json')
    else:
        user_name = get_username()
        user_dir = os.path.join('media', user_name)
        # 确保 user_dir 是字符串类型
        user_dir = base_dir + '\\' + str(user_dir)
        return send_from_directory(user_dir, 'music.json')


@app.route('/static/music/music.json', methods=['PUT'])
@jwt_required
def music_json_change(user_id):
    if not user_id:
        return jsonify({'error': 'User ID is required'}), 503

    json_data = request.get_json()
    if json_data is None:
        return jsonify({'error': 'Invalid JSON data'}), 400

    # 检查JSON数据格式是否正确
    if not isinstance(json_data, list):
        return jsonify({'error': 'JSON data should be a list of music tracks'}), 400

    for track in json_data:
        # 检查每个track是否包含必要的键
        required_keys = {'name', 'audio_url', 'singer', 'album', 'cover', 'time'}
        if not required_keys.issubset(track.keys()):
            return jsonify({
                'error': '需要包含的属性name, audio_url, singer, album, cover, time'}), 400

    user_name = get_username()
    user_dir = os.path.join('media', user_name)

    # 确保 user_dir 存在
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)

    # 构建保存路径
    save_path = os.path.join(str(user_dir), 'music.json')

    # 保存JSON数据
    file: io.TextIOWrapper
    with io.open(save_path, 'w', encoding=global_encoding) as file:
        json.dump(json_data, file, ensure_ascii=False, indent=4)

    return jsonify({'message': 'success'}), 200


@cache.memoize(30)
def get_avatar(user_identifier, identifier_type='id'):
    avatar = app.config['AVATAR_SERVER']  # 默认头像服务器地址
    if not user_identifier:
        return avatar  # 如果没有用户标识符，返回默认头像
    query_map = {
        'id': "select profile_picture from users where id = %s",
        'username': "select profile_picture from users where username = %s"
    }

    if identifier_type not in query_map:
        raise ValueError("identifier_type must be 'id' or 'username'")

    db = None
    try:
        db = get_db_connection()
        with db.cursor() as cursor:
            cursor.execute(query_map[identifier_type], (user_identifier,))
            result = cursor.fetchone()
            if result and result[0]:
                avatar = f"{domain}api/avatar/{result[0]}.webp"
    except Exception as e:
        app.logger.error(f"Error getting avatar for {user_identifier} with type {identifier_type}: {e}")
    finally:
        if db is not None:
            db.close()
    return avatar


@app.route('/api/avatar/<avatar_uuid>.webp', methods=['GET'])
def api_avatar_image(avatar_uuid):
    return send_file(f'{base_dir}/avatar/{avatar_uuid}.webp', mimetype='image/webp')


def ueditor_plus_edit(user_id, aid, user_name):
    all_info = get_article_metadata(aid)
    edit_html = api_view_content(all_info[1], auth_key=DEFAULT_KEY)
    return render_template('ueditor-plus.html',
                           user_id=user_id, user_name=user_name,
                           edit_html=edit_html, all_info=all_info)


def get_outer_url(user_id):
    f_hash = handle_user_upload(user_id=user_id, allowed_size=app.config['UPLOAD_LIMIT'],
                                allowed_mimes=app.config['ALLOWED_MIMES'], check_existing=True)
    return domain + 'shared/' + '?data=' + f_hash


@app.route('/api/ueditor', methods=['GET', 'POST'])
@jwt_required
def ueditor_plus_server(user_id):
    # /ueditor-plus/_demo_server/handle.php
    aid = request.args.get('aid')
    argparse_username = request.args.get('user_name')
    user_name = get_username()
    if not aid or user_name != argparse_username:
        return jsonify({'state': 'ERROR', 'message': '参数不完整'}), 400
    action = request.args.get('action', default=None)
    upload_folder = 'media' + '/' + user_name
    if os.path.exists(upload_folder) is False:
        return jsonify({'state': 'ERROR', 'message': '请先前往媒体管理页面上传文件'}), 400
    if action == 'showPost':
        return jsonify(request.form)
    elif action in ['image', 'video', 'voice', 'file', 'scrawl']:
        file = request.files.get('file')
        if file:
            filename = secure_filename(file.filename)
            outer_url = get_outer_url(user_id)
            return jsonify({
                'state': 'SUCCESS',
                'url': outer_url,
                'title': filename,
                'original': filename,
            })
        else:
            return jsonify({'state': 'ERROR', 'message': f'No {action} uploaded'})

    elif action == 'listImage':
        list_images = [{'url': '/' + os.path.join(upload_folder, f),
                        'mtime': int(os.path.getmtime(os.path.join(upload_folder, f)))} for f in
                       os.listdir(upload_folder) if f.endswith(('.png', '.jpg', '.jpeg', '.gif'))]
        result = {
            "state": "SUCCESS",
            "list": list_images,
            "start": int(request.args.get('start', 0)),
            "total": len(list_images)
        }
        return jsonify(result)

    elif action == 'listFile':
        list_files = [{'url': '/' + os.path.join(upload_folder, f),
                       'mtime': int(os.path.getmtime(os.path.join(upload_folder, f)))} for f in
                      os.listdir(upload_folder)]
        result = {
            "state": "SUCCESS",
            "list": list_files,
            "start": int(request.args.get('start', 0)),
            "total": len(list_files)
        }
        return jsonify(result)

    elif action == 'catch':
        list_catch = []
        source = request.form.getlist('source[]')
        if not source:
            return jsonify({'state': 'ERROR', 'message': 'No source URL provided'})
        for img_url in source:
            try:
                filename = secure_filename(os.path.basename(img_url))
                response = requests.get(img_url)
                response.raise_for_status()
                outer_url = get_outer_url(user_id)
                list_catch.append({
                    'state': 'SUCCESS',
                    'url': outer_url,
                    'size': os.path.getsize(os.path.join(upload_folder, filename)),
                    'title': filename,
                    'original': filename,
                    'source': img_url,
                })
            except Exception as e:
                list_catch.append({
                    'state': 'ERROR',
                    'message': str(e),
                    'source': img_url,
                })
        return jsonify({'state': 'SUCCESS', 'list': list_catch})

    # 当 action 为 None 或其他未定义操作时，返回 ueditor_config
    ueditor_config = cache.get(f"ueditor_config")
    if ueditor_config is None:
        config_path = os.path.join(base_dir, 'static', 'ueditorPlus', 'config.json')
        try:
            with open(config_path, 'r', encoding=global_encoding) as f:
                ueditor_config = json.load(f)

            cache.set(f"ueditor_config", ueditor_config, timeout=3600)
        except FileNotFoundError:
            return jsonify({'state': 'ERROR', 'message': 'Config file not found'})
        except json.JSONDecodeError:
            return jsonify({'state': 'ERROR', 'message': 'Invalid JSON format in config file'})
    return jsonify(ueditor_config)


def zy_save_edit(aid, content, a_name):
    if content is None:
        raise ValueError("Content cannot be None")
    if a_name is None or a_name.strip() == "":
        raise ValueError("Article name cannot be None or empty")

    save_directory = 'articles/'

    # 计算内容的哈希值
    current_content_hash = hashlib.md5(content.encode(global_encoding)).hexdigest()

    # 从缓存中获取之前的哈希值
    previous_content_hash = cache.get(f"{aid}_lasted_hash")

    # 检查内容是否与上一次提交相同
    if current_content_hash == previous_content_hash:
        return {'show_edit_code': 'success'}

    # 更新缓存中的哈希值
    cache.set(f"{aid}_lasted_hash", current_content_hash, timeout=28800)

    # 将文章名转换为安全的文件名
    filename = secure_filename(a_name) + ".md"

    # 将字节字符串和目录拼接为文件路径
    file_path = os.path.join(save_directory, filename)

    # 检查保存目录是否存在，如果不存在则创建它
    if not os.path.exists(save_directory):
        os.makedirs(save_directory)

    # 将文件保存到指定的目录上，覆盖任何已存在的文件
    with open(file_path, 'w', encoding=global_encoding) as file:
        file.write(content)

    return {'show_edit_code': 'success'}


@app.route('/api/edit/<int:aid>', methods=['POST', 'PUT'])
@jwt_required
def api_edit(user_id, aid):
    a_name = request.form.get('title') or None
    auth = authorize_by_aid(aid, user_id)
    if auth is False:
        return jsonify({'show_edit_code': 'failed'}), 403
    try:
        content = request.form.get('content') or ''
        status = request.form.get('status') or 'Draft'
        excerpt = request.form.get('excerpt')[:145] or ''
        hidden_status = request.form.get('hiddenStatus') or 0
        cover_image = request.files.get('coverImage') or None
        cover_image_path = 'cover'
        if status == 'Deleted':
            if delete_article(a_name, app.config['TEMP_FOLDER']):
                return delete_db_article(user_id, aid)
        if cover_image:
            # 保存封面图片
            cover_image_path = os.path.join('cover', f"{aid}.png")
            os.makedirs(os.path.dirname(cover_image_path), exist_ok=True)
            with open(cover_image_path, 'wb') as f:
                cover_image.save(f)
        if save_article_changes(aid, int(hidden_status), status, cover_image_path, excerpt) and zy_save_edit(aid,
                                                                                                             content,
                                                                                                             a_name):
            return jsonify({'show_edit_code': 'success'}), 200
    except Exception as e:
        app.logger.error(f"保存文章 article id: {aid} 时出错: {e} by user {user_id} ")
        return jsonify({'show_edit_code': 'failed'}), 500


@app.route('/api/edit/tag/<int:aid>', methods=['PUT'])
@jwt_required
def api_update_article_tags(user_id, aid):
    tags_input = request.get_json().get('tags')
    if not isinstance(tags_input, str):
        return jsonify({'show_edit': 'error', 'message': '标签输入不是字符串'})
    tags_input = tags_input.replace("，", ",")
    tags_list = [
        tag.strip() for tag in re.split(",", tags_input, maxsplit=4) if len(tag.strip()) <= 10
    ]
    current_tag_hash = hashlib.md5(tags_input.encode(global_encoding)).hexdigest()
    previous_content_hash = cache.get(f"{aid}:tag_hash")
    # 检查内容是否与上一次提交相同
    if current_tag_hash == previous_content_hash:
        return jsonify({'show_edit': 'success'})
    # 更新缓存中的标签哈希值
    cache.set(f"{aid}:tag_hash", current_tag_hash, timeout=28800)
    # 写入更新后的标签到数据库
    auth = authorize_by_aid(aid, user_id)
    if auth is False:
        return jsonify({'show_edit': 'failed'}), 403
    update_article_tags(aid, tags_list)
    return jsonify({'show_edit': "success"})


@app.route('/api/cover/<cover_img>', methods=['GET'])
@app.route('/edit/cover/<cover_img>', methods=['GET'])
def api_cover(cover_img):
    require_format = request.args.get('format') or False
    if not require_format:
        cache.set(f"cover_{cover_img}", None)
        return send_file(f'../cover/{cover_img}', mimetype='image/png')
    cached_cover = cache.get(f"cover_{cover_img}")
    if cached_cover:
        return send_file(io.BytesIO(cached_cover), mimetype='image/webp', max_age=600)
    cover_path = f'cover/{cover_img}'
    if os.path.isfile(cover_path):
        with Image.open(cover_path) as img:
            cover_data = handle_cover_resize(img, 480, 270)
        cache.set(f"cover_{cover_img}", cover_data, timeout=28800)
        return send_file(io.BytesIO(cover_data), mimetype='image/webp', max_age=600)
    else:
        print("File not found, returning default image")
        return send_file('../static/image/dark.jpg', mimetype='image/png')


@app.route('/upload_file', methods=['POST'])
@jwt_required
def upload_user_path(user_id):
    return handle_user_upload(user_id=user_id, allowed_size=app.config['UPLOAD_LIMIT'],
                              allowed_mimes=app.config['ALLOWED_MIMES'], check_existing=False)


@app.route('/', methods=['GET'])
@app.route('/index.html', methods=['GET'])
@cache.cached(timeout=180, query_string=True)
def index_html():
    page = request.args.get('page', 1, type=int)
    page = max(page, 1)
    page_size = 45
    offset = (page - 1) * page_size

    query = """
        SELECT article_id, Title, user_id, Views, Likes, Comments, 
               cover_image, article_type, excerpt, is_featured, tags
        FROM `articles`
        WHERE `Hidden` = 0 AND `Status` = 'Published'
        ORDER BY `article_id` DESC
        LIMIT %s OFFSET %s
    """

    try:
        article_info, total_articles = fetch_articles(query, (page_size, offset))
        total_pages = (total_articles + page_size - 1) // page_size
    except Exception as e:
        return error(str(e), 500)
    html_content, etag = proces_page_data(total_articles, article_info, page, total_pages)
    # 设置响应头
    response = make_response(html_content)
    response.set_etag(etag)
    response.headers['Cache-Control'] = 'public, max-age=180'
    return response.make_conditional(request.environ)


def proces_page_data(total_articles, article_info, page, total_pages):
    current_theme = get_current_theme()
    template_rel_path = f'theme/{current_theme}/index.html' if current_theme != 'default' else 'index.html'

    try:
        loader = app.jinja_loader
        loader.get_source(app.jinja_env, template_rel_path)
    except TemplateNotFound:
        cache.set('display_theme', 'default')
        template_rel_path = 'index.html'
    html_content = render_template(template_rel_path, article_info=article_info, page=page, total_pages=total_pages)
    etag = generate_etag(total_articles, article_info, page, current_theme)
    return html_content, etag


@app.route('/tag/<tag_name>', methods=['GET'])
@cache.cached(timeout=300, query_string=True)
def tag_page(tag_name):
    if len(tag_name.encode(global_encoding)) > 10:
        return error("Tag 名称不能超过 10 字节。", status_code=400)

    page = request.args.get('page', 1, type=int)
    page = max(page, 1)
    page_size = 45
    offset = (page - 1) * page_size

    query = """
            SELECT article_id,
                   Title,
                   user_id,
                   Views,
                   Likes,
                   Comments,
                   cover_image,
                   article_type,
                   excerpt,
                   is_featured,
                   tags
            FROM `articles`
            WHERE `Hidden` = 0
              AND `Status` = 'Published'
              AND `tags` LIKE %s
            ORDER BY `article_id` DESC
                LIMIT %s
            OFFSET %s \
            """

    try:
        article_info, total_articles = fetch_articles(query, ('%' + tag_name + '%', page_size, offset))
        total_pages = (total_articles + page_size - 1) // page_size

    except Exception:
        return error("获取文章时发生错误。", status_code=500)

    html_content, etag = proces_page_data(total_articles, article_info, page, total_pages)

    # 设置响应头
    response = make_response(html_content)
    response.set_etag(etag)
    response.headers['Cache-Control'] = 'public, max-age=180'
    return response


@app.route('/featured', methods=['GET'])
@cache.cached(timeout=300, query_string=True)
def featured_page():
    page = request.args.get('page', 1, type=int)
    page = max(page, 1)
    page_size = 45
    offset = (page - 1) * page_size

    query = """
            SELECT article_id,
                   Title,
                   user_id,
                   Views,
                   Likes,
                   Comments,
                   cover_image,
                   article_type,
                   excerpt,
                   is_featured,
                   tags
            FROM `articles`
            WHERE `Hidden` = 0
              AND `Status` = 'Published'
              AND `is_featured` >= 127
            ORDER BY `article_id` DESC
                LIMIT %s
            OFFSET %s \
            """

    try:
        article_info, total_articles = fetch_articles(query, (page_size, offset))
        total_pages = (total_articles + page_size - 1) // page_size

    except Exception:
        return error("获取文章时发生错误。", status_code=500)
    html_content, etag = proces_page_data(total_articles, article_info, page, total_pages)
    response = make_response(html_content)
    response.set_etag(etag)
    response.headers['Cache-Control'] = 'public, max-age=180'
    return response


def validate_api_key(api_key):
    if api_key == DEFAULT_KEY:
        return True
    else:
        return False


@app.route('/upload/bulk', methods=['GET', 'POST'])
@jwt_required
def upload_bulk(user_id):
    upload_locked = cache.get(f"upload_locked_{user_id}") or False
    if request.method == 'POST':
        if upload_locked:
            return jsonify([{"filename": "无法上传", "status": "failed", "message": "上传已被锁定，请稍后再试"}]), 209

        try:
            api_key = request.form.get('API_KEY')
            if not validate_api_key(api_key):
                return jsonify([{"filename": "无法上传", "status": "failed", "message": "API_KEY 错误"}]), 403

            files = request.files.getlist('files')

            # Check if the number of files exceeds the limit
            if len(files) > 50:
                return jsonify([{"filename": "无法上传", "status": "failed", "message": "最多只能上传50个文件"}]), 400

            upload_result = []
            for file in files:
                cache.set(f"upload_locked_{user_id}", True, timeout=30)
                current_file_result = {"filename": file.filename, "status": "", "message": ""}
                # 直接使用原始文件名
                original_name = file.filename

                if not original_name.endswith('.md') or original_name.startswith('_') or file.content_length > \
                        app.config['UPLOAD_LIMIT']:
                    current_file_result["status"] = "failed"
                    current_file_result["message"] = "文件类型或名称不受支持或文件大小超过限制"
                    upload_result.append(current_file_result)
                    continue

                # 确保文件路径支持中文字符
                file_path = os.path.join("articles", original_name)

                # 自动重命名文件
                if os.path.exists(file_path):
                    current_file_result["status"] = "failed"
                    current_file_result["message"] = "存在同名文件！！！"
                    upload_result.append(current_file_result)
                    continue

                # 保存文件
                file.save(file_path)
                if save_bulk_article_db(original_name, user_id):
                    current_file_result["status"] = "success"
                    current_file_result["message"] = "上传成功"
                else:
                    current_file_result["status"] = "failed"
                    current_file_result["message"] = "数据库保存失败"
                upload_result.append(current_file_result)

            return jsonify({'upload_result': upload_result})

        except Exception as e:
            app.logger.error(f"Error in file upload: {e}")
            return jsonify({'message': 'failed', 'error': str(e)}), 500
    tip_message = f"请不要上传超过 {app.config['UPLOAD_LIMIT'] / (1024 * 1024)}MB 的文件"
    return render_template('upload.html', upload_locked=upload_locked, message=tip_message)


@app.route('/newArticle', methods=['GET', 'POST'])
@app.route('/new', methods=['GET', 'POST'])
@jwt_required
def create_article(user_id):
    upload_locked = cache.get(f"upload_locked_{user_id}") or False
    if request.method == 'POST':
        if upload_locked:
            return jsonify(
                {'message': '上传被锁定，请稍后再试。', 'upload_locked': upload_locked, 'Lock_countdown': -1}), 423

        file = request.files.get('file')
        if not file:
            return jsonify({'message': '未提供文件。', 'upload_locked': upload_locked, 'Lock_countdown': 15}), 400

        from src.upload.public_upload import upload_article
        error_message = upload_article(file, app.config['TEMP_FOLDER'], app.config['UPLOAD_LIMIT'])
        if error_message:
            logging.error(f"File upload error: {error_message[0]}")
            return jsonify({'message': error_message[0], 'upload_locked': upload_locked, 'Lock_countdown': 300}), 400

        file_name = os.path.splitext(file.filename)[0]

        if upsert_article_metadata(file_name, user_id):
            message = f'上传成功。但请您前往编辑页面进行编辑:<a href="/edit/{file_name}" target="_blank">编辑</a>'
            logging.info(f"Article info successfully saved for {file_name} by user:{user_id}.")
            cache.set(f'upload_locked_{user_id}', True, timeout=300)
            return jsonify({'message': message, 'upload_locked': True, 'Lock_countdown': 300}), 200
        else:
            message = f'上传中出现了问题，你可以检查是否可以编辑该文件。:<a href="/edit/{file_name}" target="_blank">编辑</a>'
            cache.set(f'upload_locked_{user_id}', True, timeout=120)
            logging.error("Failed to update article information in the database.")
            return jsonify({'message': message, 'upload_locked': True, 'Lock_countdown': 120}), 200
    tip_message = f"请不要上传超过 {app.config['UPLOAD_LIMIT'] / (1024 * 1024)}MB 的文件"
    return render_template('upload.html', message=tip_message, upload_locked=upload_locked)


@app.route('/profile', methods=['GET', 'POST'])
@jwt_required
def profile(user_id):
    avatar_url = get_avatar(user_id)
    user_bio = get_user_bio(user_id) or "这人很懒，什么也没留下"
    owner_articles = get_articles_by_owner(owner_id=user_id) or []
    user_follow = get_following_count(user_id=user_id) or 0
    follower = get_follower_count(user_id=user_id) or 0
    return render_template('Profile.html', url_for=url_for, avatar_url=avatar_url,
                           userBio=user_bio,
                           following=user_follow, follower=follower,
                           target_id=user_id, user_id=user_id,
                           Articles=owner_articles, recycle_bin=False)


@app.route('/profile/~recycle', methods=['GET', 'POST'])
@jwt_required
def recycle_bin(user_id):
    avatar_url = get_avatar(user_id)
    user_bio = get_user_bio(user_id) or "这人很懒，什么也没留下"
    recycle_articles = get_articles_recycle(user_id=user_id) or []
    user_follow = get_following_count(user_id=user_id) or 0
    follower = get_follower_count(user_id=user_id) or 0
    return render_template('Profile.html', url_for=url_for, avatar_url=avatar_url,
                           userBio=user_bio,
                           following=user_follow, follower=follower,
                           target_id=user_id, user_id=user_id,
                           Articles=recycle_articles, recycle_bin=True)


@app.route('/delete/blog/<int:aid>', methods=['DELETE'])
@jwt_required
def delete_blog(user_id, aid):
    auth = authorize_by_aid_deleted(aid, user_id)
    if auth is False:
        jsonify({"message": f"操作失败"}), 503
    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                query = "DELETE FROM `articles` WHERE `articles`.`article_id` = %s;"
                cursor.execute(query, (aid,))
                connection.commit()
        return jsonify({"message": "操作成功"}), 200
    except Exception as e:
        return jsonify({"message": f"操作失败{e}"}), 500


@app.route('/restore/blog/<int:aid>', methods=['POST'])
@jwt_required
def restore_blog(user_id, aid):
    auth = authorize_by_aid_deleted(aid, user_id)
    if auth is False:
        return jsonify({"message": f"操作失败"}), 503
    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                query = "UPDATE `articles` SET `status` = 'Draft' WHERE `articles`.`article_id` = %s;"
                cursor.execute(query, (aid,))
                connection.commit()
        return jsonify({"message": "操作成功"}), 200
    except Exception as e:
        return jsonify({"message": f"操作失败{e}"}), 500


@app.route('/fans/follow')
@jwt_required
def fans_follow(user_id):
    query = "SELECT `subscribed_user_id` FROM `user_subscriptions` WHERE `subscriber_id` = %s;"
    user_sub_info = get_user_sub_info(query, user_id)
    return render_template('fans.html', sub_info=user_sub_info, avatar_url=get_avatar(user_id),
                           userBio=get_user_bio(user_id), page_title="我的关注")


@app.route('/fans/fans')
@jwt_required
def fans_fans(user_id):
    query = "SELECT `subscriber_id` FROM `user_subscriptions` WHERE `subscribed_user_id` = %s"
    user_sub_info = get_user_sub_info(query, user_id)
    return render_template('fans.html', sub_info=user_sub_info, avatar_url=get_avatar(user_id),
                           userBio=get_user_bio(user_id), page_title="粉丝")


@app.route('/space/<target_id>', methods=['GET', 'POST'])
@jwt_required
def user_space(user_id, target_id):
    user_bio = get_user_bio(user_id=target_id)
    can_followed = 1
    if user_id != 0 and target_id != 0:
        can_followed = get_can_followed(user_id, target_id)
    owner_articles = get_articles_by_owner(owner_id=target_id) or []
    target_username = get_profiles(user_id=target_id)[1] or "佚名"
    print(target_username)
    return render_template('Profile.html', url_for=url_for, avatar_url=get_avatar(target_id, 'id'),
                           username=target_username,
                           userBio=user_bio, follower=get_follower_count(user_id=target_id, subscribe_type='User'),
                           following=get_following_count(user_id=target_id, subscribe_type='User'),
                           target_id=target_id, user_id=user_id,
                           Articles=owner_articles, canFollowed=can_followed)


@app.route('/api/user/avatar', methods=['GET'])
def api_user_avatar():
    user_id = int(request.args.get('id')) or 0
    return get_avatar(user_id, 'id')


@app.route('/edit/blog/<int:aid>', methods=['GET', 'POST', 'PUT'])
@jwt_required
def markdown_editor(user_id, aid):
    user_name = get_username()
    auth = False

    if user_name is not None:
        auth = authorize_by_aid(aid, user_id)

    if auth:
        if request.args.get('editor') == 'ueditor':
            return ueditor_plus_edit(user_id, aid, user_name)
        all_info = get_article_metadata(aid)
        if request.method == 'GET':
            edit_html = edit_article_content(all_info[1], max_line=app.config['MAX_LINE'])
            # article_url = domain + 'blog/' + all_info[1]
            # article_surl = api_shortlink(article_url)
            # 渲染编辑页面并将转换后的HTML传递到模板中
            return render_template('editor.html', edit_html=edit_html, aid=aid, articleName=all_info[1],
                                   tags=all_info[12], user_id=user_id, article_surl=None, user_name=user_name,
                                   coverImage=f"{domain}api/cover/{aid}.png",
                                   all_info=all_info)
        elif request.method == 'POST':
            content = request.json['content']
            return zy_save_edit(aid, content, all_info[1])
        else:
            return render_template('editor.html')

    else:
        return error(message='您没有权限', status_code=503)


@app.route('/setting/profiles', methods=['GET'])
@jwt_required
def setting_profiles(user_id):
    user_info = cache.get(f"{user_id}_userInfo") or get_profiles(user_id=user_id)
    print(user_info)

    if user_info is None:
        # 处理未找到用户信息的情况
        return "用户信息未找到", 404

    cache.set(f'{user_id}_userInfo', user_info, timeout=3600)

    # 确保索引存在
    avatar_url = user_info[5] if len(user_info) > 5 and user_info[5] else app.config['AVATAR_SERVER']
    bio = user_info[6] if len(user_info) > 6 and user_info[6] else "这人很懒，什么也没留下"
    user_name = user_info[1] if len(user_info) > 1 else "匿名用户"
    user_email = user_info[2] if len(user_info) > 2 else "未绑定邮箱"

    return render_template(
        'setting.html',
        avatar_url=avatar_url,
        userStatus=bool(user_id),
        username=user_name,
        Bio=bio,
        userEmail=user_email,
    )


@app.route('/setting/profiles', methods=['PUT'])
@jwt_required
def change_profiles(user_id):
    change_type = request.args.get('change_type')
    if not change_type:
        return jsonify({'error': 'Change type is required'}), 400
    if change_type not in ['avatar', 'username', 'email', 'password']:
        return jsonify({'error': 'Invalid change type'}), 400

    if change_type == 'avatar':
        if 'avatar' not in request.files:
            return jsonify({'error': 'Avatar is required'}), 400
        avatar_file = request.files['avatar']
        if avatar_file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        # 生成UUID
        avatar_uuid = uuid.uuid4()
        save_path = Path('avatar') / f'{avatar_uuid}.webp'

        # 确保目录存在
        save_path.parent.mkdir(parents=True, exist_ok=True)

        # 使用with语句保存文件
        with save_path.open('wb') as avatar_path:
            avatar_file.save(avatar_path)
            db_save_avatar(user_id, str(avatar_uuid))

        return jsonify({'message': 'Avatar updated successfully', 'avatar_id': str(avatar_uuid)}), 200
    if change_type == 'bio':
        bio = request.json.get('bio')
        db_save_bio(user_id, bio)
        return jsonify({'message': 'Bio updated successfully'}), 200
    if change_type == 'username':
        username = request.json.get('username')
        if not username:
            return jsonify({'error': 'Username is required'}), 400
        if not re.match(r'^[a-zA-Z0-9_]{4,16}$', username):
            return jsonify({'error': 'Username should be 4-16 characters, letters, numbers or underscores'}), 400
        if check_user_conflict(zone='username', value=username):
            return jsonify({'error': 'Username already exists'}), 400
        db_change_username(user_id, new_username=username)
        return jsonify({'message': 'Username updated successfully'}), 200
    if change_type == 'email':
        email = request.json.get('email')
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return jsonify({'error': 'Invalid email format'}), 400
        if check_user_conflict(zone='email', value=email):
            return jsonify({'error': 'Email already exists'}), 400
        db_bind_email(user_id, (None, email))
        return jsonify({'message': 'Email updated successfully'}), 200


@cache.cached(timeout=2 * 60, key_prefix='current_theme')
@app.route('/api/theme', methods=['GET'])
def get_current_theme():
    return db_get_theme()


@app.errorhandler(404)
def page_not_found(error_message):
    app.logger.error(error_message)
    return error(error_message, status_code=404)


@app.errorhandler(500)
def internal_server_error(error_message):
    app.logger.error(error_message)
    return error(error_message, status_code=500)


@app.route('/<path:undefined_path>')
def undefined_route(undefined_path):
    app.logger.error(undefined_path)
    return error("Not Found", status_code=404)


@app.errorhandler(Exception)
def handle_unexpected_error(error_message):
    app.logger.error(error_message)
    return error(error_message, status_code=500)


if __name__ == "__main__":
    app.run()
