import base64
import concurrent.futures
import datetime
import hashlib
import io
import json
import logging
import os
import random
import re
import time
import urllib.parse
import uuid
import xml.etree.ElementTree as ElementTree
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import markdown
import qrcode
import requests
from PIL import Image
from flask import Flask, render_template, redirect, request, url_for, Response, jsonify, send_file, \
    make_response, send_from_directory, abort
from flask_caching import Cache
from jinja2 import select_autoescape
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

from src.AboutLogin import zy_login, zy_register, zy_mail_login
from src.AboutPW import zy_change_password, zy_confirm_password
from src.BlogDeal import get_article_names, get_article_content, clear_html_format, \
    get_blog_author, get_file_date, \
    zy_edit_article, get_unique_tags, get_articles_by_tag, \
    get_tags_by_article, set_article_info, write_tags_to_database, auth_by_id, \
    article_change_pw, get_file_summary, get_comments, auth_files, get_more_info, article_save_change, auth_aid
from src.database import get_db_connection
from src.links import create_special_url, redirect_to_long_url
from src.notification import get_sys_notice, read_notification
from src.user import error, get_owner_articles, zy_general_conf, get_following_count, \
    get_follower_count, get_can_followed, get_all_themes
from src.utils import admin_upload_file, get_client_ip, \
    generate_jwt, secret_key, authenticate_jwt, \
    authenticate_refresh_token, handle_article_upload, is_allowed_file, zb_safe_check, \
    generate_thumbs, generate_video_thumb, \
    get_username, admin_required, jwt_required, finger_required, theme_safe_check, mask_ip, user_id_required, \
    user_agent_info, handle_article_delete, handle_cover_resize

global_encoding = 'utf-8'

app = Flask(__name__, template_folder='../templates', static_folder="../static")
app.config['CACHE_TYPE'] = 'simple'
cache = Cache(app)
app.secret_key = secret_key
app.config['SESSION_COOKIE_NAME'] = 'zb_session'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=4)
app.config['USER_BASE_PATH'] = 'media'
app.config['TEMP_FOLDER'] = 'temp/upload'
app.config['AVATAR_PATH'] = 'avatar'
# 定义随机头像服务器
app.config['AVATAR_SERVER'] = "https://api.7trees.cn/avatar"
# 定义允许上传的文件类型/文件大小
app.config['ALLOWED_EXTENSIONS'] = {'.jpg', '.png', '.webp', '.jfif', '.pjpeg', '.jpeg', '.pjp', '.mp4', '.xmind'}
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

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

domain, sitename, beian, sys_version, api_host, app_id, app_key, DEFAULT_KEY = zy_general_conf()
print("please check information")
print("++++++++++==========================++++++++++")
print(
    f'\n domain: {domain} \n title: {sitename} \n beian: {beian} \n Version: {sys_version} \n 三方登录api: {api_host} \n')
print("++++++++++==========================++++++++++")


@app.context_processor
def inject_variables():
    return dict(
        beian=beian,
        title=sitename,
        username=get_username(),
        domain=domain
    )


@app.route('/login', methods=['POST', 'GET'])
def login():
    callback_route = request.args.get('callback', 'index_html')
    if request.cookies.get('jwt'):
        user_id = authenticate_jwt(request.cookies.get('jwt'))
        if user_id:
            return redirect(url_for(callback_route))
    if request.method == 'POST':
        return zy_login(callback_route)

    return render_template('LoginRegister.html', title="登录")


@app.route('/logout')
def logout():
    response = make_response(redirect(url_for('login')))
    response.set_cookie('jwt', '', expires=0)  # 清除 Cookie
    response.set_cookie('refresh_token', '', expires=0)  # 清除刷新令牌
    return response


@app.route('/register', methods=['POST', 'GET'])
def register():
    callback_route = request.args.get('callback', 'index_html')
    if request.cookies.get('jwt'):
        user_id = authenticate_jwt(request.cookies.get('jwt'))
        if user_id:
            return redirect(url_for(callback_route))
    ip = get_client_ip(request)
    return zy_register(ip)


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
    matched_content = []

    if request.method == 'POST':
        keyword = request.form.get('keyword')  # 获取搜索关键字
        app.logger.info(f'{user_id} search keyword: {keyword}')
        cache_dir = os.path.join('temp', 'search')
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, keyword + '.xml')

        # 检查缓存是否失效
        if os.path.isfile(cache_path) and (
                time.time() - os.path.getmtime(cache_path) < app.config['MAX_CACHE_TIMESTAMP']):
            # 读取缓存并继续处理
            with open(cache_path, 'r', encoding=global_encoding) as cache_file:
                match_data = cache_file.read()
        else:
            files = os.listdir('articles')
            markdown_files = [file for file in files if file.endswith('.md')]
            root = ElementTree.Element('root')

            for file in markdown_files:
                article_name = file[:-3]  # 移除文件扩展名 (.md)
                encoded_article_name = urllib.parse.quote(article_name)
                article_url = domain + 'blog/' + encoded_article_name
                date = get_file_date(encoded_article_name)
                describe = get_article_content(article_name, 50)
                describe = clear_html_format(describe)

                if keyword.lower() in article_name.lower() or keyword.lower() in describe.lower():
                    item = ElementTree.SubElement(root, 'item')
                    ElementTree.SubElement(item, 'title').text = article_name
                    ElementTree.SubElement(item, 'link').text = article_url
                    ElementTree.SubElement(item, 'pubDate').text = date
                    ElementTree.SubElement(item, 'description').text = describe

            # 创建XML树并写入缓存
            tree = ElementTree.ElementTree(root)
            match_data = ElementTree.tostring(tree.getroot(), encoding="unicode", method='xml')

            with open(cache_path, 'w', encoding=global_encoding) as cache_file:
                cache_file.write(match_data)

        # 解析XML数据
        parsed_data = ElementTree.fromstring(match_data)
        for item in parsed_data.findall('item'):
            content = {
                'title': item.find('title').text,
                'link': item.find('link').text,
                'pubDate': item.find('pubDate').text,
                'description': item.find('description').text
            }
            matched_content.append(content)

    return render_template('search.html', results=matched_content)


@cache.memoize(120)
def read_hidden_articles():
    hidden_articles = []
    try:
        with get_db_connection() as db:
            with db.cursor() as cursor:
                query = "SELECT `Title` FROM `articles` WHERE `Hidden` = 1"
                cursor.execute(query)
                results = cursor.fetchall()
                for result in results:
                    hidden_articles.append(result[0])
    except Exception as e:
        print(f"An error occurred: {e}")
        # 更详细的日志记录或错误处理机制

    return hidden_articles


@cache.memoize(180)
@app.route('/blog/api/<article_name>', methods=['GET', 'POST'])
@app.route('/api/<article_name>', methods=['GET', 'POST'])
def sys_out_file(article_name):
    hidden_articles = read_hidden_articles()

    if article_name[:-3] in hidden_articles:
        # 隐藏的文章
        return error(message="页面不见了", status_code=404)

    articles_dir = os.path.join(base_dir, 'articles')
    return send_from_directory(articles_dir, article_name)


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


@app.route('/setting/profiles', methods=['GET', 'POST'])
@finger_required
def setting_profiles(user_id):
    user_info = cache.get(f"{user_id}_userInfo") or get_profiles(user_id=user_id)

    if user_info is None:
        # 处理未找到用户信息的情况
        return "用户信息未找到", 404

    cache.set(f'{user_id}_userInfo', user_info, timeout=3600)

    # 确保索引存在
    avatar_url = user_info[5] if len(user_info) > 5 and user_info[5] else app.config['AVATAR_SERVER']
    bio = user_info[6] if len(user_info) > 6 and user_info[6] else "这人很懒，什么也没留下"
    user_name = user_info[1] if len(user_info) > 1 else "匿名用户"

    return render_template(
        'setting.html',
        avatar_url=avatar_url,
        userStatus=bool(user_id),
        username=user_name,
        Bio=bio
    )


@cache.cached(timeout=1800, key_prefix='article_info')
def get_article_info(articles):
    articles_info = []
    for a_title in articles:
        try:
            article_info = ''
            db = get_db_connection()

            try:
                article_info += get_file_date(a_title)
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


@cache.memoize(30)
def get_a_list(chanel=1, page=1):
    if chanel == 1:
        articles, has_next_page, has_previous_page = get_article_names(page=1, per_page=99999)
        return articles
    if chanel == 2:
        articles, has_next_page, has_previous_page = get_article_names(page=page, per_page=12)
        return articles, has_next_page, has_previous_page
    if chanel == 3:
        # rss页面
        articles, has_next_page, has_previous_page = get_article_names(page=1, per_page=30)
        return articles


@app.route('/blog/<article>', methods=['GET', 'POST'])
@cache.memoize(180)
def blog_detail(article):
    try:
        article_names = get_a_list(chanel=1)
        hidden_articles = read_hidden_articles()
        if article not in article_names:
            pass

        aid, article_tags = get_tags_by_article(article)
        if article in hidden_articles:
            return render_template('inform.html', aid=aid)

        # article_url = domain + 'blog/' + article
        # article_surl = api_shortlink(article_url)
        author, author_uid = get_blog_author(article)
        update_date = get_file_date(article)

        response = make_response(render_template('zyDetail.html',
                                                 article_content=1,
                                                 aid=aid,
                                                 articleName=article,
                                                 author=author,
                                                 authorUID=str(author_uid),
                                                 blogDate=update_date,
                                                 domain=domain,
                                                 url_for=url_for,
                                                 # article_Surl=article_surl,
                                                 article_tags=article_tags))

        # 只设置缓存的 max_age
        response.cache_control.max_age = 180

        return response

    except FileNotFoundError:
        return error(message="页面不见了", status_code=404)


@app.route('/confirm-password', methods=['GET', 'POST'])
@jwt_required
def confirm_password(user_id):
    return zy_confirm_password(user_id)


@app.route('/change-password', methods=['GET', 'POST'])
@jwt_required
def change_password(user_id):
    ip = get_client_ip(request)
    return zy_change_password(user_id, ip)


@app.route('/admin/changeTheme', methods=['POST'])
@admin_required
def change_display(user_id):
    if cache.get("Theme_Lock"):
        return "failed"
    theme_id = request.args.get('NT')

    if not theme_id:
        return error("非管理员用户禁止访问！！！", 403)

    current_theme = get_current_theme()

    if theme_id == current_theme:
        return "failed001"

    # 使用上下文管理器处理数据库连接
    try:
        if theme_id == 'default':
            cache.set('display_theme', theme_id)
            cache.set(f"Theme_Lock", theme_id, timeout=15)  # 设置超时
            return 'success'

        if not theme_safe_check(theme_id, channel=2):
            return "failed"

        # 更新缓存并插入数据库记录
        cache.set('display_theme', theme_id)
        cache.set(f"Theme_Lock", theme_id, timeout=15)  # 设置超时

        app.logger.info(f'{user_id} : change theme to {theme_id}')
        return "success"

    except Exception as e:
        logging.error(f"Error during theme change: {e}")
        return error("未知错误", 500), 500


@app.route('/Admin_upload', methods=['POST'])
@admin_required
def upload_file1(user_id):
    app.logger.info(f'{user_id} : Try Upload file')
    return admin_upload_file(app.config['UPLOAD_LIMIT'])


@cache.cached(timeout=14400)
@app.route('/robots.txt')
def static_from_root():
    content = "User-agent: *\nDisallow: /admin"
    modified_content = content + '\nSitemap: ' + domain + 'sitemap.xml'

    response = Response(modified_content, mimetype='text/plain')
    return response


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


@app.route('/media/<user_name>/<img_name>')
@app.route('/zyImg/<user_name>/<img_name>')
def get_image_path(user_name, img_name):
    preview = request.args.get('preview')
    if preview:
        return api_img(user_name, img_name)
    try:
        img_dir = Path(base_dir) / 'media' / user_name / img_name
        with open(img_dir, 'rb') as f:
            img_data = f.read()
        # 使用 BytesIO 包装图像数据
        return send_file(io.BytesIO(img_data), mimetype='image/png')
    except Exception as e:
        print(f"Error in getting image path: {e}")
        return None


@app.route('/upload_file', methods=['POST'])
@jwt_required
def upload_user_path(user_id):
    user_name = get_username()
    handle_user_upload(user_name=user_name, user_id=user_id)


@app.route('/jump', methods=['GET', 'POST'])
def jump():
    url = request.args.get('url', default=domain)
    return render_template('inform.html', url=url, domain=domain)


@app.route('/login/<provider>')
def cc_login(provider):
    if zb_safe_check(api_host):
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
        return zy_mail_login(user_email, ip)

    return render_template('LoginRegister.html', error=msg)


@cache.cached(timeout=300, key_prefix='display_detail')
@app.route('/theme/<theme_id>')
def get_theme_detail(theme_id):
    if theme_id == 'default':
        theme_properties = {
            'id': theme_id,
            'author': sitename,
            'title': "恢复系统默认",
            'authorWebsite': domain,
            'version': sys_version,
            'versionCode': "None",
            'updateUrl': "None",
            'screenshot': "None",
        }
        return jsonify(theme_properties)
    return theme_safe_check(theme_id, channel=1)


@app.route('/theme/<theme_id>/<img_name>')
def get_screenshot(theme_id, img_name):
    if theme_id == 'default':
        return send_file('../static/favicon.ico', mimetype='image/png')
    try:
        img_dir = os.path.join(base_dir, 'templates', 'theme', theme_id, img_name)
        with open(img_dir, 'rb') as f:
            img_data = f.read()

        img_io = io.BytesIO(img_data)
        img_io.seek(0)

        return send_file(img_io, mimetype='image/png')
    except Exception as e:
        print(f"Error in getting image path: {e}")
        return jsonify(error='Failed to get image path')


@app.route('/favicon.ico', methods=['GET', 'POST'])
def favicon():
    return send_file('../static/favicon.ico', mimetype='image/png')


@cache.cached(timeout=24 * 3600, key_prefix='short_link')
@app.route('/s/<short_url>', methods=['GET', 'POST'])
def redirect_to_long_url_route(short_url):
    if len(short_url) != 6:
        return 'error'
    user_agent = request.headers.get('User-Agent')
    long_url = redirect_to_long_url(short_url)
    if long_url:
        app.logger.info(f"{user_agent}->{short_url}")
        return redirect(long_url, code=302)
    else:
        # 如果没有找到对应的长网址，则返回错误页面或其他处理逻辑
        logging.error(f"Invalid short URL: {short_url}")
        return "短网址无效"


@app.route('/api/shortlink')
def api_shortlink(long_url):
    if not long_url.startswith('https://') and not long_url.startswith('http://'):
        return 'error'
    user_name = sitename
    short_url = create_special_url(long_url, user_name)
    article_surl = domain + 's/' + short_url
    return article_surl


@cache.cached(timeout=3 * 3600, key_prefix='aid')
@app.route('/<article_id>.html', methods=['GET', 'POST'])
def id_find_article(article_id):
    if not re.match(r'^\d{1,4}$', article_id):
        logging.error(f"Invalid article ID: {article_id}")
        return error(message='无效的文章', status_code=404)

    user_agent = request.headers.get('User-Agent')
    db = get_db_connection()
    cursor = db.cursor()
    try:
        query = "SELECT long_url FROM urls WHERE id = %s"
        cursor.execute(query, (article_id,))
        result = cursor.fetchone()

        if result:
            long_url = result[0]
            last_slash_index = long_url.rfind("/")
            article = long_url[last_slash_index + 1:]
            return blog_detail(article)
        else:
            # If no URL is found
            logging.error(f"URL not found for: {article_id}")
            return error(message='没有找到文章', status_code=404)
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        db.rollback()
        return error(message='服务器内部错误', status_code=500)
    finally:
        ip_address = get_client_ip(request)
        app.logger.info(f'IP:{ip_address}, UA:{user_agent}')
        cursor.close()
        db.close()


@cache.cached(timeout=3 * 3600, key_prefix='article_img')
@app.route('/blog/<article_name>/images/<image_name>', methods=['GET'])
def article_img(article_name, image_name):
    author, author_uid = get_blog_author(article_name)
    if author is None:
        author = 'test'
    articles_img_dir = os.path.join(base_dir, 'media', str(author))
    return send_from_directory(articles_img_dir, image_name)


@app.route('/blog/f/<author>/<file_name>', methods=['GET'])
def sys_out_user_file(author, file_name):
    xmind_file_path = Path(base_dir) / 'media' / str(author) / file_name  # 使用 pathlib.Path 处理路径
    # 返回 用户 文件
    try:
        return send_file(xmind_file_path, as_attachment=True)
    except Exception as e:
        logging.error("An error occurred: %s", str(e))
        return "An error occurred while trying to access the file."


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
    from src.utils import zy_mail_conf
    from src.notification import send_email
    smtp_server, stmp_port, sender_email, password = zy_mail_conf()
    receiver_email = sender_email
    subject = '安全通知邮件'  # 邮件主题
    body = '这是一封测试邮件。'  # 邮件正文
    send_email(sender_email, password, receiver_email, smtp_server, int(stmp_port), subject=subject,
               body=body)
    app.logger.info(f'{user_id} sendMail')
    return 'success'


@app.route('/api/ip')
def ip_api():
    key = request.cookies.get('key')

    if key:
        cached_ip = cache.get(key)
        if cached_ip:
            query_params = request.args.to_dict()
            print(f"{key} cache ip : {cached_ip} with {query_params}")
            return jsonify({'ip': cached_ip})

    ip = get_client_ip(request)
    cache.set(key, ip, timeout=600)
    return jsonify({'ip': ip})


@app.route('/api/follow', methods=['GET', 'POST'])
@user_id_required
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
                cursor.execute("SELECT `subscribe_to_id` FROM `subscriptions` WHERE `subscriber_id` = %s",
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
            insert_query = ("INSERT INTO `subscriptions` (`subscriber_id`, `subscribe_to_id`, `subscribe_type`) VALUES "
                            "(%s, %s, 'User')")
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
@user_id_required
def unfollow_user(user_id):
    unfollow_id = request.args.get('fid')
    if not user_id or not unfollow_id:
        return jsonify({'unfollow_code': 'failed', 'message': '操作无效'})

    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            # 进行取关操作
            delete_query = ("DELETE FROM `subscriptions` WHERE `subscriber_id` = %s AND `subscribe_to_id` = %s AND "
                            "`subscribe_type` = 'User';")
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
@user_id_required
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
                query = "UPDATE `articles` SET `Likes` = `Likes` + %s WHERE `articles`.`ArticleID` = %s;"
                cursor.execute(query, (rd_like, int(aid),))
                query2 = "UPDATE `articles` SET `Views` = `Views` + %s WHERE `articles`.`ArticleID` = %s;"
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


def get_current_theme():
    current_theme = cache.get('display_theme')
    if current_theme is None:
        current_theme = 'default'
    return current_theme


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
def phone_scan():
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
            return jsonify(page_json)
    else:
        token_json = {'status': 'failed'}
        return jsonify(token_json)


# 获取在线设备
@app.route('/api/devices', methods=['GET'])
@finger_required
def get_devices(user_id):
    cached_finger = cache.get(f'fingerprint_{user_id}') or []
    return jsonify(cached_finger), 200


@app.route('/finger', methods=['GET', 'POST'])
@jwt_required
def finger(user_id):
    if request.method == 'POST':
        data = request.json
        chrome_fingerprint = data.get('fingerprint')
        if user_id and chrome_fingerprint:
            cached_finger = cache.get(f'fingerprint_{user_id}') or []
            if chrome_fingerprint not in cached_finger:
                cached_finger.append(chrome_fingerprint)
                cache.set(f'fingerprint_{user_id}', cached_finger)
                return jsonify({"msg": "Fingerprint saved successfully"}), 200
            return jsonify({"msg": "Fingerprint Auth"}), 200
        return jsonify({"msg": "Failed to save fingerprint"}), 400
    if request.method == 'GET':
        return render_template("Authentication.html", form='finger')


@app.route('/api/user/export', methods=['GET', 'POST'])
@jwt_required
def export(user_id):
    key = request.cookies.get('key')
    cached_ip = cache.get(key)
    cached_finger = cache.get(f'fingerprint_{user_id}')
    user_info = cache.get(f'{user_id}_userInfo')
    user_followed = cache.get(f'{user_id}_followed')
    user_liked = cache.get(f'{user_id}_liked')
    result = {
        'key': key,
        'ip': cached_ip,
        'cachedFinger': cached_finger,
        'UserInfo': user_info,
        'user_followed': user_followed,
        'user_liked': user_liked,
    }
    return jsonify(result)


@app.route('/api/notice', methods=['GET'])
@jwt_required
def user_notification(user_id):
    user_notices = get_sys_notice(user_id)
    return jsonify(user_notices)


@app.route('/api/notice/read')
def read_user_notification():
    read_content = read_notification()
    return jsonify(read_content), 200


@app.route('/changelog')
def changelog():
    return redirect('https://github.com/Athenavi/zb/blob/main/articles/changelog.md')


@app.route('/xmind/<user_name>/thumbs/<xmind>.png', methods=['GET', 'POST'])
def api_xmind(user_name, xmind):
    if request.method == 'GET':
        video_dir = Path(base_dir) / 'media' / user_name / xmind
        if os.path.isfile(video_dir):
            return send_file('../static/image/xmind.png', mimetype='image/jpeg')


@app.route('/api/wx/blog_detail/<article>', methods=['GET'])
def api_wx_blog_detail(article):
    visited_key = request.args.get('KEY')

    def generate_response_data(message="文章不存在"):
        return jsonify({
            'article_name': message,
            'author': message,
            'author_uid': message,
            'update_date': message,
            'domain': domain,
            'article_surl': message,
            'article_tags': message,
            'content': message,
        })

    try:
        article_names = get_a_list(chanel=1)
        hidden_articles = read_hidden_articles()

        if article in hidden_articles or article not in article_names:
            return generate_response_data()

        aid, article_tags = get_tags_by_article(article)
        article_url = f"{domain}blog/{article}"
        article_surl = api_shortlink(article_url)
        author, author_uid = get_blog_author(article)
        update_date = get_file_date(article)
        content = api_wx_content(article, auth_key=visited_key)

        response_data = {
            'article_name': article,
            'author': author,
            'author_uid': str(author_uid),
            'update_date': update_date,
            'domain': domain,
            'article_surl': article_surl,
            'article_tags': article_tags,
            'content': content,
        }

        return jsonify(response_data)

    except FileNotFoundError:
        return generate_response_data()


def api_wx_content(article, auth_key):
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


# wxapi主页
def get_home_data(page, tag):
    page = max(page, 1)  # 确保 page 至少为 1

    articles, has_next_page, has_previous_page = get_a_list(chanel=2, page=page)

    if not articles:
        app.logger.warning('没有找到任何文章！')
        return None, None, None, None, None, None  # 添加 None 用于 tags

    notice = get_sys_notice(0) if (notice := get_sys_notice(0)) else ''

    tags = []
    try:
        tags = get_unique_tags()
    except Exception as e:
        app.logger.error(f'获取标签出错: {e}')

    if tag != 'None':
        tag_articles = get_articles_by_tag(tag)
        if tag_articles:
            articles = tag_articles
        else:
            app.logger.warning(f'没有找到标签: {tag} 下的文章！')

    info_list = get_article_info(articles)
    if not info_list:
        app.logger.warning('没有找到任何文章！')
        return None, None, None, None, None, None

    summary_list = get_summary(articles)
    compressed_list = list(zip(articles, summary_list, info_list))
    friends_links = get_friends_link()

    return compressed_list, notice, has_next_page, has_previous_page, friends_links, tags


@app.route('/api/wx', methods=['GET'])
def api_wx():
    page = request.args.get('page', default=1, type=int)
    tag = request.args.get('tag', default='None')

    (compressed_list, notice, has_next_page, has_previous_page, friends_links, tags) = get_home_data(page, tag)

    response_data = {
        'articles': compressed_list,
        'notice': notice,
        'has_next_page': has_next_page,
        'has_previous_page': has_previous_page,
        'current_page': page,
        'tags': tags,
        'tag': tag,
        'friends_links': friends_links
    }
    return jsonify(response_data)


@app.route('/api/article/unlock', methods=['GET', 'POST'])
@finger_required
def api_article_unlock(user_id):
    try:
        aid = int(request.args.get('aid'))
    except (TypeError, ValueError):
        return jsonify({"message": "Invalid Article ID"}), 400

    entered_password = request.args.get('passwd')
    temp_url = ''
    user_finger = request.cookies.get('finger')

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
        finger_md5 = gen_md5(user_finger)
        cache.set(f"temp-url_{user_finger}", aid, timeout=900)
        temp_url = f'{domain}tmpView?url={finger_md5}'
        response_data['temp_url'] = temp_url
        return jsonify(response_data), 200
    else:
        referrer = request.referrer
        app.logger.error(f"{referrer} Failed access attempt {user_finger} :  {user_id}")
        return jsonify({"message": "Authentication failed"}), 401


@app.route('/tmpView', methods=['GET', 'POST'])
def temp_view():
    url = request.args.get('url')
    if url is None:
        return jsonify({"message": "Missing URL parameter"}), 400

    user_finger = request.cookies.get('finger')
    aid = cache.get(f"temp-url_{user_finger}")

    if aid:
        content = '<p>无法加载文章内容</p>'
        db = get_db_connection()

        try:
            with db.cursor() as cursor:
                query = "SELECT `Title` FROM articles WHERE ArticleID = %s"
                cursor.execute(query, (int(aid),))
                result = cursor.fetchone()
                if result:
                    a_title = result[0]

                    content = api_wx_content(a_title, DEFAULT_KEY)
        except ValueError as e:
            app.logger.error(f"Value error: {e}")
            return jsonify({"message": "Invalid ArticleID"}), 400
        except Exception as e:
            app.logger.error(f"Unexpected error: {e}")
            return jsonify({"message": "Internal server error"}), 500

        finally:
            cursor.close()
            db.close()
            referrer = request.referrer
            app.logger.info(f"Request from {referrer} with finger {user_finger}")
            return content
    else:
        return jsonify({"message": "Temporary URL expired or invalid"}), 404


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
        app.logger.error(f"Value Error: {e}")
    except Exception as e:
        app.logger.error(f"Unexpected Error: {e}")

    finally:
        db.close()

    return None


@cache.cached(timeout=600, key_prefix='gen_md5')
def gen_md5(text):
    # 创建MD5哈希对象
    md5_hash = hashlib.md5()
    # 更新哈希对象
    md5_hash.update(text.encode(global_encoding))
    # 获取十六进制表示的哈希值
    return md5_hash.hexdigest()


@app.route('/api/article/PW', methods=['POST'])
@finger_required
def api_article_pw(user_id):
    try:
        aid = int(request.args.get('aid'))
    except (TypeError, ValueError):
        return jsonify({"message": "无效的文章ID"}), 400

    if aid == cache.get(f"PWLock_{user_id}"):
        return jsonify({"message": "操作过于频繁"}), 400

    new_password = request.args.get('new-passwd')

    if len(new_password) != 4:
        return jsonify({"message": "无效的密码"}), 400

    auth = auth_by_id(aid, user_name=get_username())

    if auth:
        cache.set(f"PWLock_{user_id}", aid, timeout=30)
        result = article_change_pw(aid, new_password)
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
        masked_ip = mask_ip(user_ip)

    user_agent = request.headers.get('User-Agent') or ''
    user_agent = user_agent_info(user_agent)

    cache.set(f"CommentLock_{user_id}", aid, timeout=30)
    result = comment_add(aid, user_id, pid, new_comment, masked_ip, user_agent)

    if result:
        return jsonify({'aid': aid, 'changed': True}), 201
    else:
        return jsonify({"message": "评论失败"}), 500


def comment_add(aid, user_id, pid, comment_content, ip, ua):
    c_json = {'content': comment_content, 'pid': pid, 'ip': ip, 'ua': ua}
    comment_json = json.dumps(c_json)
    db = get_db_connection()
    comment_added = False
    try:
        with db.cursor() as cursor:
            query = "INSERT INTO `comments` (`article_id`, `user_id`, `content`) VALUES (%s, %s, %s);"
            cursor.execute(query, (int(aid), int(user_id), comment_json))
            db.commit()
            comment_added = True
    except Exception as e:
        print(f'Error: {e}')
    finally:
        db.close()
        return comment_added


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
                cursor.execute("DELETE FROM `articles` WHERE `Title` = %s AND `Author` = %s", (filename, user_name))
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
    if auth_files(file_path, user_name):
        os.remove(file_path) if os.path.exists(file_path) else None
        return jsonify({'filename': filename, 'Deleted': True}), 201
    else:
        app.logger.info(f'Delete error for {filename} by user {user_id}')
        return jsonify({'filename': filename, 'Deleted': False}), 503


@app.route('/links')
def get_friends_link():
    friends_links = {
        '本站地址': domain,
        'GitHub': "https://github.com/Athenavi",
        '博客园': "https://cnblogs.com/Athenavi/",
    }
    return friends_links


@app.route('/api/report', methods=['POST'])
@user_id_required
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
        return jsonify({"message": "评论失败"}), 500


def report_add(user_id, reported_type, reported_id, reason):
    reported = False
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            query = ("INSERT INTO `reports` (`reported_by`, `content_type`, `content_id`,`reason`) VALUES (%s, %s, %s,"
                     "%s);")
            cursor.execute(query, (int(user_id), reported_type, reported_id, reason))
            db.commit()
            reported = True
    except Exception as e:
        print(f'Error: {e}')
    finally:
        db.close()
        return reported


@app.route('/api/comment', methods=['delete'])
@user_id_required
def api_comment_delete(user_id):
    try:
        comment_id = int(request.json.get('comment_id'))
    except (TypeError, ValueError):
        return jsonify({"message": "Invalid Comment ID"}), 400

    if comment_id == cache.get(f"deleteCommentLock_{user_id}"):
        return jsonify({"message": "操作过于频繁"}), 400

    result = comment_del(user_id, comment_id)

    if result:
        cache.set(f"deleteCommentLock_{user_id}", comment_id, timeout=30)
        return jsonify({"message": "删除成功"}), 201
    else:
        return jsonify({"message": "操作失败"}), 500


def comment_del(user_id, comment_id):
    db = get_db_connection()
    comment_deleted = False
    try:
        with db.cursor() as cursor:
            query = "DELETE FROM `comments` WHERE `id` = %s AND `user_id` = %s;"
            cursor.execute(query, (int(comment_id), int(user_id)))
            db.commit()
            comment_deleted = True
    except Exception as e:
        print(f'Error: {e}')
    finally:
        db.close()
        return comment_deleted


@app.route('/travel', methods=['GET'])
def travel():
    return '此接口暂时弃用'


@app.route('/dashboard/articles', methods=['GET'])
@admin_required
def m_articles(user_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute('SELECT * FROM articles')
        articles = cursor.fetchall()
        cursor.close()
        connection.close()
        return render_template('M-articles.html', articles=articles)
    except Exception as e:
        # 记录错误日志
        app.logger.error(f"Error fetching articles by user {user_id}: {str(e)}")
        # 返回错误信息或重定向到错误页面
        return error(message=f"获取文章时出错: {str(e)}", status_code=500), 500


@app.route('/dashboard', methods=['GET'])
@app.route('/dashboard/overview', methods=['GET'])
@admin_required
def m_overview(user_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SHOW TABLE STATUS WHERE Name IN ('articles', 'users', 'comments','media','events');")
        dash_info = cursor.fetchall()
        cursor.execute('SELECT * FROM events')
        events = cursor.fetchall()
        cursor.close()
        connection.close()
        return render_template('M-overview.html', dashInfo=dash_info, events=events)
    except Exception as e:
        # 记录错误日志
        app.logger.error(f"Error fetching overview by user {user_id}: {str(e)}")
        # 返回错误信息或重定向到错误页面
        return error(message=f"获取Overview时出错: {str(e)}", status_code=500), 500


@app.route('/dashboard/users', methods=['GET'])
@admin_required
def m_users(user_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users')  # 从数据库获取用户列表
        users = cursor.fetchall()
        cursor.close()
        connection.close()
        return render_template('M-users.html', users=users)
    except Exception as e:
        # 记录错误日志
        app.logger.error(f"Error fetching users by user {user_id}: {str(e)}")
        # 返回错误信息或重定向到错误页面
        return error(message=f"获取用户时出错: {str(e)}", status_code=500), 500


@app.route('/dashboard/comments', methods=['GET'])
@admin_required
def m_comments(user_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute('SELECT * FROM comments')
        comments = cursor.fetchall()
        cursor.close()
        connection.close()
        return render_template('M-comments.html', comments=comments)
    except Exception as e:
        # 记录错误日志
        app.logger.error(f"Error fetching comments by user {user_id}: {str(e)}")
        # 返回错误信息或重定向到错误页面
        return error(message=f"获取文章时出错: {str(e)}", status_code=500), 500


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


@app.route('/dashboard/media', methods=['GET'])
@admin_required
def m_media(user_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute('SELECT * FROM media')  # 从数据库获取媒体列表
        media_items = cursor.fetchall()
        cursor.close()
        connection.close()
        return render_template('M-media.html', media_items=media_items, domain=domain)
    except Exception as e:
        # 记录错误日志
        app.logger.error(f"An error occurred while user-{user_id} was retrieving media : {str(e)}")
        # 返回错误信息或重定向到错误页面
        return error(message=f"获取媒体时出错: {str(e)}", status_code=500), 500


@app.route('/dashboard/notifications', methods=['GET'])
@admin_required
def m_notifications(user_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute('SELECT * FROM notifications')  # 从数据库获取通知列表
        notifications = cursor.fetchall()
        cursor.close()
        connection.close()
        return render_template('M-notifications.html', notifications=notifications)
    except Exception as e:
        # 记录错误日志
        app.logger.error(f"An error occurred while user-{user_id} was getting notifications : {str(e)}")
        # 返回错误信息或重定向到错误页面
        return error(message=f"获取文章时出错: {str(e)}", status_code=500), 500


@app.route('/dashboard/reports', methods=['GET'])
@admin_required
def m_reports(user_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute('SELECT * FROM reports')  # 从数据库获取举报列表
        reports = cursor.fetchall()
        cursor.close()
        connection.close()
        return render_template('M-reports.html', reports=reports)
    except Exception as e:
        # 记录错误日志
        app.logger.error(f"An error occurred while user-{user_id} was getting reports : {str(e)}")
        # 返回错误信息或重定向到错误页面
        return error(message=f"获取举报信息时出错: {str(e)}", status_code=500), 500


@app.route('/dashboard/urls', methods=['GET'])
@admin_required
def m_urls(user_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute('SELECT * FROM urls')  # 从数据库获取短链接列表
        urls = cursor.fetchall()
        cursor.close()
        connection.close()
        return render_template('M-urls.html', urls=urls)
    except Exception as e:
        # 记录错误日志
        app.logger.error(f"An error occurred while user-{user_id} was getting urls : {str(e)}")
        # 返回错误信息或重定向到错误页面
        return error(message=f"获取短链接时出错: {str(e)}", status_code=500), 500


@app.route('/dashboard/display', methods=['GET'])
@admin_required
def m_display(user_id):
    return render_template('M-display.html', displayList=get_all_themes(), user_id=user_id)


@app.route('/dashboard/articles', methods=['DELETE'])
@admin_required
def m_articles_delete(user_id):
    aid = request.args.get('aid')
    if not aid:
        return jsonify({"message": "操作失败"}), 400

    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                query = "DELETE FROM `articles` WHERE `articles`.`ArticleID` = %s;"
                cursor.execute(query, (int(aid),))
                connection.commit()

        return jsonify({"message": "操作成功"}), 200

    except Exception as e:
        return jsonify({"message": "操作失败", "error": str(e)}), 500
    finally:
        referrer = request.referrer
        app.logger.error(f"{referrer} delete {aid} by: {user_id}")


@app.route('/dashboard/articles', methods=['PUT'])
@admin_required
def m_articles_edit(user_id):
    data = request.get_json()
    article_id = data.get('ArticleID')
    article_title = data.get('Title')
    article_status = data.get('Status')
    if not article_id or not article_title:
        return jsonify({"message": "操作失败"}), 400

    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                query = "UPDATE `articles` SET `Title` = %s,`Status`= %s WHERE `ArticleID` = %s;"
                cursor.execute(query, (article_title, article_status, int(article_id)))
                connection.commit()

        return jsonify({"message": "操作成功"}), 200

    except Exception as e:
        return jsonify({"message": "操作失败", "error": str(e)}), 500
    finally:
        referrer = request.referrer
        app.logger.info(f"{referrer} : modify article {article_id} by  {user_id}")


@app.route('/dashboard/users', methods=['DELETE'])
@admin_required
def m_users_delete(user_id):
    uid = int(request.args.get('uid'))
    if not uid or uid == 1:
        return jsonify({"message": "操作失败"}), 400

    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                query = "DELETE FROM `users` WHERE `id` = %s;"
                cursor.execute(query, (uid,))
                connection.commit()

        return jsonify({"message": "操作成功"}), 200

    except Exception as e:
        return jsonify({"message": "操作失败", "error": str(e)}), 500
    finally:
        referrer = request.referrer
        app.logger.info(f"{referrer}: delete user {uid} by: {user_id}")


@app.route('/dashboard/users', methods=['PUT'])
@admin_required
def m_users_edit(user_id):
    data = request.get_json()
    u_id = data.get('UId')
    user_name = data.get('UName')
    user_role = data.get('URole')
    if not u_id or not user_name:
        return jsonify({"message": "操作失败"}), 400

    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                query = "UPDATE `users` SET `username` = %s,`role`= %s WHERE `id` = %s;"
                cursor.execute(query, (user_name, user_role, int(u_id)))
                connection.commit()

        return jsonify({"message": "操作成功"}), 200

    except Exception as e:
        return jsonify({"message": "操作失败", "error": str(e)}), 500
    finally:
        referrer = request.referrer
        app.logger.info(f"{referrer} edit {u_id} to {user_role} by: {user_id}")


@app.route('/dashboard/comments', methods=['DELETE'])
@admin_required
def m_comments_delete(user_id):
    cid = int(request.args.get('cid'))
    if not cid:
        return jsonify({"message": "操作失败"}), 400

    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                query = "DELETE FROM `comments` WHERE `id` = %s;"
                cursor.execute(query, (cid,))
                connection.commit()

        return jsonify({"message": "操作成功"}), 200

    except Exception as e:
        return jsonify({"message": "操作失败", "error": str(e)}), 500
    finally:
        referrer = request.referrer
        app.logger.info(f"{referrer}: delete comment {cid} by: {user_id}")


@app.route('/dashboard/media', methods=['DELETE'])
@admin_required
def m_media_delete(user_id):
    file_id = int(request.args.get('file-id'))
    if not file_id:
        return jsonify({"message": "操作失败"}), 400

    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                query = "DELETE FROM `media` WHERE `id` = %s;"
                cursor.execute(query, (file_id,))
                connection.commit()

        return jsonify({"message": "操作成功"}), 200

    except Exception as e:
        return jsonify({"message": "操作失败", "error": str(e)}), 500
    finally:
        referrer = request.referrer
        app.logger.info(f"{referrer}: delete file {file_id} by: {user_id}")


@app.route('/dashboard/notifications', methods=['DELETE'])
@admin_required
def m_notifications_delete(user_id):
    nid = int(request.args.get('nid'))
    if not nid:
        return jsonify({"message": "操作失败"}), 400

    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                query = "DELETE FROM `notifications` WHERE `id` = %s;"
                cursor.execute(query, (nid,))
                connection.commit()

        return jsonify({"message": "操作成功"}), 200

    except Exception as e:
        return jsonify({"message": "操作失败", "error": str(e)}), 500
    finally:
        referrer = request.referrer
        app.logger.info(f"{referrer} delete notification {nid} by: {user_id}")


@app.route('/dashboard/reports', methods=['DELETE'])
@admin_required
def m_reports_delete(user_id):
    rid = int(request.args.get('rid'))
    if not rid:
        return jsonify({"message": "操作失败"}), 400

    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                query = "DELETE FROM `reports` WHERE `id` = %s;"
                cursor.execute(query, (rid,))
                connection.commit()

        return jsonify({"message": "操作成功"}), 200

    except Exception as e:
        return jsonify({"message": "操作失败", "error": str(e)}), 500
    finally:
        referrer = request.referrer
        app.logger.info(f"{referrer}: delete report {rid} by: {user_id}")


@app.route('/dashboard/overview', methods=['DELETE'])
@admin_required
def m_overview_delete(user_id):
    event_id = int(request.args.get('id'))
    if not id:
        return jsonify({"message": "操作失败"}), 400

    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                query = "DELETE FROM `events` WHERE `id` = %s;"
                cursor.execute(query, (event_id,))
                connection.commit()

        return jsonify({"message": "操作成功"}), 200

    except Exception as e:
        return jsonify({"message": "操作失败", "error": str(e)}), 500
    finally:
        referrer = request.referrer
        app.logger.info(f"{referrer}: delete event {event_id} by: {user_id}")


@app.route('/dashboard/urls', methods=['DELETE'])
@admin_required
def m_urls_delete(user_id):
    url_id = int(request.args.get('id'))
    if not id:
        return jsonify({"message": "操作失败"}), 400

    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                query = "DELETE FROM `urls` WHERE `id` = %s;"
                cursor.execute(query, (url_id,))
                connection.commit()

        return jsonify({"message": "操作成功"}), 200

    except Exception as e:
        return jsonify({"message": "操作失败", "error": str(e)}), 500
    finally:
        referrer = request.referrer
        app.logger.info(f"{referrer}: {user_id}")


@app.route('/static/music/music.json', methods=['GET'])
@user_id_required
def music_json(user_id):
    referrer = request.referrer
    if referrer and "@" in referrer:
        username_from_referrer = referrer.split('@')[-1]
        user_dir = os.path.join(app.config['USER_BASE_PATH'], username_from_referrer)
        # 确保 user_dir 是字符串类型
        user_dir = base_dir + '\\' + str(user_dir)
        return send_from_directory(user_dir, 'music.json')
    if not user_id:
        return send_from_directory(app.static_folder, 'music/music.json')
    else:
        user_name = get_username()
        user_dir = os.path.join(app.config['USER_BASE_PATH'], user_name)
        # 确保 user_dir 是字符串类型
        user_dir = base_dir + '\\' + str(user_dir)
        return send_from_directory(user_dir, 'music.json')


@app.route('/static/music/music.json', methods=['PUT'])
@user_id_required
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
    user_dir = os.path.join(app.config['USER_BASE_PATH'], user_name)

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


@app.route('/setting/profiles', methods=['PUT'])
@user_id_required
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
        save_path = Path(app.config['AVATAR_PATH']) / f'{avatar_uuid}.webp'

        # 确保目录存在
        save_path.parent.mkdir(parents=True, exist_ok=True)

        # 使用with语句保存文件
        with save_path.open('wb') as avatar_path:
            avatar_file.save(avatar_path)
            db_save_avatar(user_id, str(avatar_uuid))

        return jsonify({'message': 'Avatar updated successfully', 'avatar_id': str(avatar_uuid)}), 200


def db_save_avatar(user_id, avatar_uuid):
    db = None
    try:
        db = get_db_connection()
        with db.cursor() as cursor:
            query = "UPDATE users SET profile_picture = %s WHERE id = %s"
            cursor.execute(query, (avatar_uuid, user_id))
            db.commit()
    except Exception as e:
        app.logger.error(f"Error saving avatar: {e} by user {user_id} avatar uuid: {avatar_uuid}")
    finally:
        if db is not None:
            db.close()


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
def get_avatar_image(avatar_uuid):
    return send_file(f'{base_dir}/{app.config['AVATAR_PATH']}/{avatar_uuid}.webp', mimetype='image/webp')


def ueditor_plus_edit(user_id, aid, user_name):
    all_info = get_more_info(aid)
    edit_html = api_wx_content(all_info[1], auth_key=DEFAULT_KEY)
    article_url = domain + 'blog/' + all_info[1]
    article_surl = api_shortlink(article_url)
    # 渲染编辑页面并将转换后的HTML传递到模板中
    return render_template('ueditor-plus.html',
                           user_id=user_id, article_surl=article_surl, user_name=user_name,
                           edit_html=edit_html, all_info=all_info)


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
    upload_folder = app.config['USER_BASE_PATH'] + '/' + user_name
    if os.path.exists(upload_folder) is False:
        return jsonify({'state': 'ERROR', 'message': '请先前往媒体管理页面上传文件'}), 400
    if action == 'showPost':
        return jsonify(request.form)
    elif action in ['image', 'video', 'voice', 'file', 'scrawl']:
        file = request.files.get('file')
        if file:
            filename = secure_filename(file.filename)
            outer_url = get_outer_url(user_name, user_id, filename)
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
                outer_url = get_outer_url(user_name, user_id, filename)
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


@app.route('/api/edit/<int:aid>', methods=['POST', 'PUT'])
@jwt_required
def markdown_editor2(user_id, aid):
    a_name = request.form.get('title') or None
    user_name = get_username()
    if not user_name or not a_name:
        return jsonify({'show_edit_code': 'failed'}), 500
    auth = auth_aid(aid, user_name)
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
            if handle_article_delete(a_name, app.config['TEMP_FOLDER']):
                return api_delete(user_id, aid)
        if cover_image:
            # 保存封面图片
            cover_image_path = os.path.join('cover', f"{aid}.png")
            os.makedirs(os.path.dirname(cover_image_path), exist_ok=True)
            with open(cover_image_path, 'wb') as f:
                cover_image.save(f)
        if article_save_change(aid, int(hidden_status), status, cover_image_path, excerpt) and zy_save_edit(aid,
                                                                                                            content,
                                                                                                            a_name):
            return jsonify({'show_edit_code': 'success'}), 200
    except Exception as e:
        app.logger.error(f"保存文章 article id: {aid} 时出错: {e} by user {user_id} ")
        return jsonify({'show_edit_code': 'failed'}), 500


@app.route('/api/edit/tag/<int:aid>', methods=['PUT'])
@jwt_required
def api_edit_tag(user_id, aid):
    tags_input = request.get_json().get('tags')
    if not isinstance(tags_input, str):
        return jsonify({'show_edit': 'error', 'message': '标签输入不是字符串'})

    # 将中文逗号转换为英文逗号
    tags_input = tags_input.replace("，", ",")

    # 用正则表达式限制标签数量和每个标签的长度
    tags_list = [
        tag.strip() for tag in re.split(",", tags_input, maxsplit=4) if len(tag.strip()) <= 10
    ]

    # 计算标签的哈希值
    current_tag_hash = hashlib.md5(tags_input.encode(global_encoding)).hexdigest()
    previous_content_hash = cache.get(f"{aid}:tag_hash")

    # 检查内容是否与上一次提交相同
    if current_tag_hash == previous_content_hash:
        return jsonify({'show_edit': 'success'})

    # 更新缓存中的标签哈希值
    cache.set(f"{aid}:tag_hash", current_tag_hash, timeout=28800)

    # 写入更新后的标签到数据库
    write_tags_to_database(aid, tags_list)
    return jsonify({'show_edit': "success"})


@app.route('/api/edit/hidden/<int:aid>', methods=['PUT'])
@jwt_required
def api_edit_hidden(user_id, aid):
    hidden_status = request.get_json().get('hiddenStatus')
    try:
        with get_db_connection() as db:
            with db.cursor() as cursor:
                cursor.execute("UPDATE `articles` SET `Hidden`=%s WHERE `ArticleID`=%s", (hidden_status, aid))
                db.commit()
            return jsonify({'show_edit': "success"}), 201
    except Exception as e:
        app.logger.error(f"Error updating hidden status: {e} by user {user_id} ")
        return jsonify({'show_edit': 'error', 'message': '更新隐藏状态失败'}), 500


def api_delete(user_id, aid):
    try:
        with get_db_connection() as db:
            with db.cursor() as cursor:
                cursor.execute("UPDATE `articles` SET `Status`=%s WHERE `ArticleID`=%s", ('Deleted', aid))
                db.commit()
        return jsonify({'show_edit_code': "deleted"}), 201
    except Exception as e:
        app.logger.error(f"Error deleting article: {e} by user {user_id} ")
        return jsonify({'show_edit_code': 'error', 'message': '删除文章失败'}), 500


@app.route('/api/cover/<cover_img>', methods=['GET'])
@app.route('/edit/cover/<cover_img>', methods=['GET'])
def api_cover(cover_img):
    require_format = request.args.get('format') or False
    if not require_format:
        cache.set(f"cover_{cover_img}", None)
        return send_file(f'../cover/{cover_img}', mimetype='image/png')
    cached_cover = cache.get(f"cover_{cover_img}")
    if cached_cover:
        return send_file(io.BytesIO(cached_cover), mimetype='image/webp')
    cover_path = f'cover/{cover_img}'
    if os.path.isfile(cover_path):
        with Image.open(cover_path) as img:
            cover_data = handle_cover_resize(img, 480, 270)
        cache.set(f"cover_{cover_img}", cover_data, timeout=28800)
        return send_file(io.BytesIO(cover_data), mimetype='image/webp')
    else:
        print("File not found, returning default image")
        return send_file('../static/image/dark.jpg', mimetype='image/png')


def handle_user_upload(user_name, user_id):
    if not user_name:
        return jsonify({'message': 'failed, user not authenticated'}), 403
    try:
        allowed_types = app.config['ALLOWED_EXTENSIONS']
        user_dir = os.path.join(app.config['USER_BASE_PATH'], user_name)  # 用户文件存储目录
        os.makedirs(user_dir, exist_ok=True)  # 如果目录不存在则创建
        file_records = []  # 用于存储文件记录的列表
        with get_db_connection() as db:  # 使用上下文管理器获取数据库连接
            with db.cursor() as cursor:  # 使用上下文管理器获取数据库游标
                # 处理每个上传的文件
                for f in request.files.getlist('file'):
                    if not is_allowed_file(f.filename, allowed_types):  # 检查文件类型
                        continue

                    if f.content_length > app.config['UPLOAD_LIMIT']:
                        return jsonify({'message': f'File size exceeds the limit of {app.config["UPLOAD_LIMIT"]}'}), 413

                    # 确保文件名安全并确保是字符串类型
                    newfile_name = secure_filename(str(f.filename))
                    user_dir = str(user_dir)

                    # 生成新文件路径并保存文件
                    newfile_path = os.path.join(user_dir, newfile_name)
                    old_thumb_path = os.path.join(user_dir, 'thumbs', newfile_name)

                    if isinstance(f, io.BytesIO):
                        # 如果是 BytesIO 对象，直接写入文件
                        with open(newfile_path, 'wb') as file:
                            file.write(f.getvalue())
                    else:
                        f.save(newfile_path)

                    if os.path.isfile(old_thumb_path):
                        os.remove(old_thumb_path)

                    # 确定文件类型
                    file_type = (
                        'image' if f.filename.lower().endswith(
                            ('.jpg', '.jpeg', '.png', '.webp', '.jfif', '.pjpeg', '.pjp')
                        ) else 'video' if f.filename.lower().endswith('.mp4')
                        else 'document'
                    )

                    # 查询是否存在相同的文件路径
                    cursor.execute("SELECT `id` FROM `media` WHERE `file_path`=%s", (newfile_path,))
                    existing_record = cursor.fetchone()

                    if existing_record:
                        # 更新已存在文件的 updated_at
                        cursor.execute(
                            "UPDATE `media` SET `updated_at`=%s WHERE `id`=%s",
                            (datetime.now(), existing_record[0])
                        )
                    else:
                        # 文件路径不存在，添加新的记录
                        file_records.append(
                            (user_id, newfile_path, file_type, datetime.now(), datetime.now()))  # 添加文件记录
                        app.logger.info(f'User: {user_name}, Uploaded file: {newfile_name}')  # 记录上传日志

                # 如果有文件记录，则插入数据库
                if file_records:
                    insert_query = ("INSERT INTO `media` (`user_id`, `file_path`, `file_type`, `created_at`, "
                                    "`updated_at`) VALUES (%s, %s, %s, %s, %s)")
                    cursor.executemany(insert_query, file_records)  # 批量插入文件记录

            db.commit()  # 提交数据库事务

        return jsonify({'message': 'success'}), 200  # 返回成功响应

    except Exception as e:
        app.logger.error(f"Error in file upload: {e}")  # 记录错误日志
        return jsonify({'message': 'failed', 'error': str(e)}), 500


def get_outer_url(user_name, user_id, filename):
    if handle_user_upload(user_name, user_id):
        return domain + 'media/' + user_name + '/' + filename


def fetch_articles(query, params):
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            cursor.execute(query, params)
            article_info = cursor.fetchall()
            cursor.execute("SELECT COUNT(*) FROM `articles` WHERE `Hidden`=0 AND `Status`='Published'")
            total_articles = cursor.fetchone()[0]

    except Exception as e:
        app.logger.error(f"Error getting articles: {e}")
        raise

    finally:
        if db is not None:
            db.close()
        return article_info, total_articles


@app.route('/', methods=['GET'])
@app.route('/index.html', methods=['GET'])
def index_html():
    page = request.args.get('page', 1, type=int)
    page_size = 45
    offset = (page - 1) * page_size

    query = """
            SELECT ArticleID,
                   Title,
                   Author,
                   Views,
                   Likes,
                   Comments,
                   CoverImage,
                   ArticleType,
                   excerpt,
                   is_featured,
                   tags
            FROM `articles`
            WHERE `Hidden` = 0
              AND `Status` = 'Published'
            ORDER BY `ArticleID` DESC
                LIMIT %s
            OFFSET %s \
            """

    try:
        article_info, total_articles = fetch_articles(query, (page_size, offset))
        total_pages = (total_articles + page_size - 1) // page_size

    except Exception:
        return error("An error occurred while fetching articles.", status_code=500)

    return render_template('index.html', article_info=article_info, page=page, total_pages=total_pages)


@app.route('/tag/<tag_name>', methods=['GET'])
def tag_page(tag_name):
    if len(tag_name.encode(global_encoding)) > 10:
        return error("Tag 名称不能超过 10 字节。", status_code=400)

    page = request.args.get('page', 1, type=int)
    page_size = 45
    offset = (page - 1) * page_size

    query = """
            SELECT ArticleID,
                   Title,
                   Author,
                   Views,
                   Likes,
                   Comments,
                   CoverImage,
                   ArticleType,
                   excerpt,
                   is_featured,
                   tags
            FROM `articles`
            WHERE `Hidden` = 0
              AND `Status` = 'Published'
              AND `tags` LIKE %s
            ORDER BY `ArticleID` DESC
                LIMIT %s
            OFFSET %s \
            """

    try:
        article_info, total_articles = fetch_articles(query, ('%' + tag_name + '%', page_size, offset))
        total_pages = (total_articles + page_size - 1) // page_size

    except Exception:
        return error("获取文章时发生错误。", status_code=500)

    return render_template('index.html', article_info=article_info, page=page, total_pages=total_pages,
                           tag_name=tag_name)


@app.route('/featured', methods=['GET'])
def featured_page():
    page = request.args.get('page', 1, type=int)
    page_size = 45
    offset = (page - 1) * page_size

    query = """
            SELECT ArticleID,
                   Title,
                   Author,
                   Views,
                   Likes,
                   Comments,
                   CoverImage,
                   ArticleType,
                   excerpt,
                   is_featured,
                   tags
            FROM `articles`
            WHERE `Hidden` = 0
              AND `Status` = 'Published'
              AND `is_featured` = 1
            ORDER BY `ArticleID` DESC
                LIMIT %s
            OFFSET %s \
            """

    try:
        article_info, total_articles = fetch_articles(query, (page_size, offset))
        total_pages = (total_articles + page_size - 1) // page_size

    except Exception:
        return error("获取文章时发生错误。", status_code=500)

    return render_template('index.html', article_info=article_info, page=page, total_pages=total_pages,
                           tag_name='featured')


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

            user_name = get_username()
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
                if save_bulk_article_db(original_name, author=user_name):
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


def save_bulk_article_db(filename, author):
    title = filename.split('.')[0]
    tags = datetime.now().year
    try:
        with get_db_connection() as db:
            with db.cursor() as cursor:
                cursor.execute("INSERT INTO articles (Title, Author, Status, tags) VALUES (%s, %s, %s, %s)",
                               (title, author, 'Draft', tags))
            db.commit()
            return True
    except Exception as e:
        app.logger.error(f"Error in saving to database: {e}")
        return False


@app.route('/newArticle', methods=['GET', 'POST'])
@app.route('/new', methods=['GET', 'POST'])
@jwt_required
def new_article(user_id):
    upload_locked = cache.get(f"upload_locked_{user_id}") or False
    if request.method == 'POST':
        if upload_locked:
            return jsonify(
                {'message': '上传被锁定，请稍后再试。', 'upload_locked': upload_locked, 'Lock_countdown': -1}), 423

        file = request.files.get('file')
        if not file:
            return jsonify({'message': '未提供文件。', 'upload_locked': upload_locked, 'Lock_countdown': 15}), 400

        error_message = handle_article_upload(file, app.config['TEMP_FOLDER'], app.config['UPLOAD_LIMIT'])
        if error_message:
            logging.error(f"File upload error: {error_message[0]}")
            return jsonify({'message': error_message[0], 'upload_locked': upload_locked, 'Lock_countdown': 300}), 400

        file_name = os.path.splitext(file.filename)[0]

        if set_article_info(file_name, username=get_username()):
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
    owner_articles = get_owner_articles(owner_id=user_id, user_name=None) or []
    user_follow = get_following_count(user_id=user_id) or 0
    follower = get_follower_count(user_id=user_id) or 0
    return render_template('Profile.html', url_for=url_for, avatar_url=avatar_url,
                           userBio=user_bio,
                           following=user_follow, follower=follower,
                           target_id=user_id, user_id=user_id,
                           Articles=owner_articles)


@cache.memoize(app.config['MAX_CACHE_TIMESTAMP'])
@app.route('/sitemap.xml')
@app.route('/sitemap')
def generate_sitemap():
    db = None
    try:
        db = get_db_connection()
        with db.cursor() as cursor:
            query = """SELECT Title
                       FROM `articles`
                       WHERE `Hidden` = 0
                         AND `Status` = 'Published'
                       ORDER BY `ArticleID` DESC LIMIT 40"""
            cursor.execute(query)
            results = cursor.fetchall()
            article_titles = [item[0] for item in results]
            xml_data = '<?xml version="1.0" encoding="UTF-8"?>\n'
            xml_data += '<urlset xmlns="https://www.sitemaps.org/schemas/sitemap/0.9/">\n'

            # 遍历文章标题列表
            for title in article_titles:
                article_url = domain + 'blog/' + title
                date = get_file_date(title)
                article_surl = api_shortlink(article_url)
                # 创建url标签并包含链接
                xml_data += '<url>\n'
                xml_data += f'\t<loc>{article_surl}</loc>\n'
                xml_data += f'\t<lastmod>{date}</lastmod>\n'  # 添加适当的标签
                xml_data += '\t<changefreq>Monthly</changefreq>\n'  # 添加适当的标签
                xml_data += '\t<priority>0.8</priority>\n'  # 添加适当的标签
                xml_data += '</url>\n'

            # 关闭urlset标签
            xml_data += '</urlset>\n'
            response = Response(xml_data, mimetype='text/xml')
            return response
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if db is not None:
            db.close()


@cache.memoize(app.config['MAX_CACHE_TIMESTAMP'])
@app.route('/feed')
@app.route('/rss')
def generate_rss():
    markdown_files = get_a_list(chanel=3, page=1)
    # 创建XML文件头及其他信息...
    xml_data = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_data += '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
    xml_data += '<channel>\n'
    xml_data += '<title>' + sitename + 'RSS Feed </title>\n'
    xml_data += '<link>' + domain + '</link>\n'
    xml_data += '<description>' + sitename + 'RSS Feed</description>\n'
    xml_data += '<language>en-us</language>\n'
    xml_data += '<lastBuildDate>' + datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z") + '</lastBuildDate>\n'
    xml_data += '<atom:link href="' + domain + 'rss" rel="self" type="application/rss+xml" />\n'

    for file in markdown_files:
        encoded_article_name = urllib.parse.quote(file)  # 对文件名进行编码处理
        article_url = domain + 'blog/' + encoded_article_name
        date = get_file_date(encoded_article_name)
        content, *_ = get_article_content(file, 10)
        describe = encoded_article_name

        article_surl = api_shortlink(article_url)
        # 创建item标签并包含内容
        xml_data += '<item>\n'
        xml_data += f'\t<title>{file}</title>\n'
        xml_data += f'\t<link>{article_surl}</link>\n'
        xml_data += f'\t<guid>{article_url}</guid>\n'
        xml_data += f'\t<pubDate>{date}</pubDate>\n'
        xml_data += f'\t<description>{describe}</description>\n'
        xml_data += f'\t<content:encoded><![CDATA[{content}]]></content:encoded>'
        xml_data += '</item>\n'

    # 关闭channel和rss标签
    xml_data += '</channel>\n'
    xml_data += '</rss>\n'
    response = Response(xml_data, mimetype='application/rss+xml')
    return response


def get_user_sub_info(query, user_id):
    db = None
    user_sub_info = []
    try:
        db = get_db_connection()
        with db.cursor() as cursor:
            cursor.execute(query, (int(user_id),))
            user_sub = cursor.fetchall()
            subscribe_ids = [sub[0] for sub in user_sub]
            if subscribe_ids:
                placeholders = ', '.join(['%s'] * len(subscribe_ids))
                query = f"SELECT `id`, `username` FROM `users` WHERE `id` IN ({placeholders});"
                cursor.execute(query, tuple(subscribe_ids))
                user_sub_info = cursor.fetchall()
    except Exception as e:
        app.logger.error(f"An error occurred: {e}")
    finally:
        if db is not None:
            db.close()
    return user_sub_info


@app.route('/fans/follow')
@jwt_required
def fans_follow(user_id):
    query = "SELECT `subscribe_to_id` FROM `subscriptions` WHERE `subscriber_id` = %s and `subscribe_type` = 'User';"
    user_sub_info = get_user_sub_info(query, user_id)
    return render_template('fans.html', sub_info=user_sub_info, avatar_url=get_avatar(user_id),
                           userBio=get_user_bio(user_id), page_title="我的关注")


@app.route('/fans/fans')
@jwt_required
def fans_fans(user_id):
    query = "SELECT `subscriber_id` FROM `subscriptions` WHERE `subscribe_to_id` = %s and `subscribe_type` = 'User';"
    user_sub_info = get_user_sub_info(query, user_id)
    return render_template('fans.html', sub_info=user_sub_info, avatar_url=get_avatar(user_id),
                           userBio=get_user_bio(user_id), page_title="粉丝")


@app.route('/space/<target_id>', methods=['GET', 'POST'])
@user_id_required
def user_space(user_id, target_id):
    user_bio = get_user_bio(user_id=target_id)
    can_followed = 1
    if user_id != 0 and target_id != 0:
        can_followed = get_can_followed(user_id, target_id)
    owner_articles = get_owner_articles(owner_id=target_id, user_name=None) or []
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


@cache.memoize(180)
@app.route('/api/prev_<file_name>', methods=['GET', 'POST'])
def temp_prev(file_name):
    author = get_username()
    prev = f"""
    ```xmind preview
    {domain}/blog/f/{author}/{file_name[:-3]}
    ```

     """
    return prev


@app.route('/edit/blog/<int:aid>', methods=['GET', 'POST', 'PUT'])
@jwt_required
def markdown_editor(user_id, aid):
    user_name = get_username()
    auth = False

    if user_name is not None:
        auth = auth_aid(aid, user_name)

    if auth:
        if request.args.get('editor') == 'ueditor':
            return ueditor_plus_edit(user_id, aid, user_name)
        all_info = get_more_info(aid)
        if request.method == 'GET':
            edit_html = zy_edit_article(all_info[1], max_line=app.config['MAX_LINE'])
            article_url = domain + 'blog/' + all_info[1]
            article_surl = api_shortlink(article_url)
            # 渲染编辑页面并将转换后的HTML传递到模板中
            return render_template('editor.html', edit_html=edit_html, aid=aid, articleName=all_info[1],
                                   tags=all_info[12], user_id=user_id, article_surl=article_surl, user_name=user_name,
                                   all_info=all_info)
        elif request.method == 'POST':
            content = request.json['content']
            return zy_save_edit(aid, content, all_info[1])
        else:
            return render_template('editor.html')

    else:
        return error(message='您没有权限', status_code=503)


@app.route('/media', methods=['GET'])
@jwt_required
def media(user_id):
    media_type = request.args.get('type', default='img')
    page = request.args.get('page', default=1, type=int)
    if not media_type or media_type == 'img':
        imgs, total_pages = get_media_db(user_id, category='image', page=page, per_page=20)
        has_next_page = bool(total_pages - page)
        has_previous_page = bool(total_pages - 1)
        return render_template('Media_V2.html', imgs=imgs, title='Media', url_for=url_for,
                               has_next_page=has_next_page,
                               has_previous_page=has_previous_page, current_page=page,
                               domain=domain)
    if media_type == 'video':
        videos, total_pages = get_media_db(user_id, category='video', page=1, per_page=20)
        has_next_page = bool(total_pages - page)
        has_previous_page = bool(total_pages - 1)
        return render_template('Media_V2.html', videos=videos, title='Media', url_for=url_for,
                               has_next_page=has_next_page,
                               has_previous_page=has_previous_page, current_page=page,
                               domain=domain)
    if media_type == 'other':
        docs, total_pages = get_media_db(user_id, category='document', page=1, per_page=20)
        has_next_page = bool(total_pages - page)
        has_previous_page = bool(total_pages - 1)
        return render_template('Media_V2.html', docs=docs, url_for=url_for,
                               has_next_page=has_next_page,
                               has_previous_page=has_previous_page, current_page=page,
                               domain=domain)


@cache.memoize(120)
def get_media_db(user_id, category, page=1, per_page=20):
    media_type = category or 'image'
    try:
        with get_db_connection() as db:
            with db.cursor() as cursor:
                offset = (page - 1) * per_page
                # 查询文件路径和ID，并按id降序排列
                query = f"SELECT `id`, `file_path` FROM media WHERE user_id = %s AND file_type = %s ORDER BY id DESC LIMIT %s OFFSET %s"
                cursor.execute(query, (user_id, media_type, per_page, offset))
                files = cursor.fetchall()
                print(files)
                count_query = f"SELECT COUNT(*) FROM media WHERE user_id = %s AND file_type = %s"
                cursor.execute(count_query, (user_id, media_type))
                total_files = cursor.fetchone()[0]
                total_pages = (total_files + per_page - 1) // per_page

                return files, total_pages
    except Exception as e:
        print(f"An error occurred: {e}")
        return [], 0


@app.route('/thumb/media/<user_name>/<img>', methods=['GET'])
def api_img(user_name, img):
    img_dir = Path(base_dir) / 'media' / user_name / img
    img_thumbs = Path(base_dir) / 'media' / user_name / 'thumbs' / img
    if not img_dir.is_file():
        abort(404)
    if img_thumbs.is_file():
        return send_file(img_thumbs, mimetype='image/jpeg')
    thumbs_dir = img_thumbs.parent
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.submit(generate_thumbs, img_dir, img_thumbs)
    except Exception as e:
        app.logger.error(f"Error submitting thumb generation task: {e}")
    placeholder_path = Path(base_dir) / 'static' / 'favicon.ico'
    if placeholder_path.is_file():
        return send_file(placeholder_path, mimetype='image/png')
    else:
        return "Thumbnail is being generated, please refresh later.", 202


@app.route('/V-thumb/media/<user_name>/<video>.png', methods=['GET'])
def api_video(user_name, video):
    video_dir = Path(base_dir) / 'media' / user_name / video
    video_thumbs = Path(base_dir) / 'media' / user_name / 'thumbs' / f"V-thumbs_{video}.png"
    if not video_dir.is_file():
        abort(404)
    if video_thumbs.is_file():
        return send_file(video_thumbs, mimetype='image/jpeg')
    thumbs_dir = video_thumbs.parent
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.submit(generate_video_thumb, video_dir, video_thumbs)
    except Exception as e:
        app.logger.error(f"Error submitting video thumbnail generation task: {e}")
    placeholder_path = Path(base_dir) / 'static' / 'favicon.ico'
    if placeholder_path.is_file():
        return send_file(placeholder_path, mimetype='image/png')
    else:
        return "Video thumbnail is being generated, please refresh later.", 202


@app.route('/video/media/<user_name>/<video_name>')
def start_video(user_name, video_name):
    try:
        video_dir = Path(base_dir) / 'media' / user_name
        video_path = video_dir / video_name
        if not video_path.exists():
            return f"Video {video_name} not found for user {user_name}.", 404
        return send_file(video_path, mimetype='video/mp4', as_attachment=False, conditional=True)
    except Exception as e:
        print(f"Error in getting video path: {e}")
        return "Internal Server Error", 500


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
