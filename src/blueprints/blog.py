from flask import Blueprint, request, jsonify, current_app

from src.blog.article.core.views import blog_detail_i18n, blog_detail_i18n_list, contribute_back, blog_detail_aid_back, \
    new_article_back, edit_article_back
from src.blog.homepage import index_page_back, tag_page_back, featured_page_back
from src.blueprints.api import api_user_profile
from src.error import error
from src.extensions import cache
from src.user.authz.decorators import jwt_required, domain
from src.user.views import change_profiles_back, setting_profiles_back

blog_bp = Blueprint('blog', __name__)


@blog_bp.route('/<int:aid>.html/<string:iso>/<string:slug_name>', methods=['GET', 'POST'])
def blog_detail_i18n_route(aid, iso, slug_name):
    return blog_detail_i18n(aid=aid, blog_slug=slug_name, i18n_code=iso)


@blog_bp.route('/contribute', methods=['GET', 'POST'])
def contribute():
    aid = request.args.get('aid')  # 文章ID
    if aid is None:
        # 根据请求类型返回不同的错误响应
        if request.method == 'POST':
            return jsonify({'success': False, 'message': 'Invalid request: missing article ID'}), 400
        return error(message='Invalid request: missing article ID', status_code=400)
    return contribute_back(aid)


@blog_bp.route('/<int:aid>.html/<string:iso>', methods=['GET'])
def blog_detail_i18n_list_route(aid, iso):
    return blog_detail_i18n_list(aid=aid, i18n_code=iso)


@blog_bp.route('/<int:aid>.html', methods=['GET', 'POST'])
def blog_detail_aid(aid):
    return blog_detail_aid_back(aid=aid)


@blog_bp.route('/tmpView', methods=['GET', 'POST'])
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


@blog_bp.route('/new', methods=['GET', 'POST'])
@jwt_required
def new_article(user_id):
    return new_article_back(user_id)


@blog_bp.route('/', methods=['GET'])
@blog_bp.route('/index.html', methods=['GET'])
@cache.cached(timeout=180, query_string=True)
def index_html():
    return index_page_back()


@blog_bp.route('/tag/<tag_name>', methods=['GET'])
@cache.cached(timeout=300, query_string=True)
def tag_page(tag_name):
    return tag_page_back(tag_name, current_app.config['global_encoding'])


@blog_bp.route('/featured', methods=['GET'])
@cache.cached(timeout=300, query_string=True)
def featured_page():
    return featured_page_back()


@blog_bp.route('/edit/blog/<int:aid>', methods=['GET', 'POST', 'PUT'])
@jwt_required
def markdown_editor(user_id, aid):
    return edit_article_back(user_id, aid)


@blog_bp.route('/setting/profiles', methods=['GET'])
@jwt_required
def setting_profiles(user_id):
    user_info = api_user_profile(user_id=user_id)
    return setting_profiles_back(user_id, user_info, cache, current_app.config['AVATAR_SERVER'])


@blog_bp.route('/setting/profiles', methods=['PUT'])
@jwt_required
def change_profiles(user_id):
    return change_profiles_back(user_id, cache, domain)
