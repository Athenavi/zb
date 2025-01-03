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
import xml.etree.ElementTree as ElementTree
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import markdown
import qrcode
import requests
from flask import Flask, render_template, redirect, request, url_for, Response, jsonify, send_file, \
    make_response, send_from_directory
from flask_caching import Cache
from jinja2 import select_autoescape
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

from src.AboutLogin import zy_login, zy_register, zy_mail_login
from src.AboutPW import zy_change_password, zy_confirm_password
from src.BlogDeal import get_article_names, get_article_content, clear_html_format, \
    get_blog_author, read_hidden_articles, auth_articles, get_file_date, \
    zy_edit_article, get_subscriber_ids, get_unique_tags, get_articles_by_tag, \
    get_tags_by_article, set_article_info, write_tags_to_database, set_article_visibility, auth_by_id, \
    article_change_pw, get_file_summary, get_comments, auth_files
from src.database import get_database_connection, get_db_connection
from src.links import create_special_url, redirect_to_long_url
from src.notification import get_sys_notice, read_notification, send_change_mail
from src.user import error, get_owner_articles, zy_general_conf, get_profiles, get_following_count, \
    get_follower_count, get_can_followed, get_user_id, get_all_themes
from src.utils import admin_upload_file, get_client_ip, \
    zy_noti_conf, generate_jwt, secret_key, authenticate_jwt, \
    authenticate_refresh_token, handle_file_upload, is_allowed_file, is_valid_domain_with_slash, \
    get_all_img, get_all_video, get_all_xmind, get_list_intersection, generate_thumbs, generate_video_thumb, \
    get_username, admin_required, jwt_required, finger_required, theme_safe_check, mask_ip, parse_update_file, \
    user_id_required, user_agent_info

global_encoding = 'utf-8'

app = Flask(__name__, template_folder='../templates', static_folder="../static")
app.config['CACHE_TYPE'] = 'simple'
cache = Cache(app)
app.secret_key = secret_key
app.config['SESSION_COOKIE_NAME'] = 'zb_session'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=4)
app.config['USER_BASE_PATH'] = 'media'
app.config['TEMP_FOLDER'] = 'temp/upload'
# 定义随机头像服务器
app.config['AVATAR_SERVER'] = "https://api.7trees.cn/avatar"
# 定义允许上传的文件类型/文件大小
app.config['ALLOWED_EXTENSIONS'] = {'.jpg', '.png', '.webp', '.jfif', '.pjpeg', '.jpeg', '.pjp', '.mp4', '.xmind'}
app.config['UPLOAD_LIMIT'] = 60 * 1024 * 1024
# 定义文件最大可编辑的行数
app.config['MAX_LINE'] = 360
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

domain, title, beian, sys_version, api_host, app_id, app_key = zy_general_conf()
print("please check information")
print("++++++++++==========================++++++++++")
print(
    f'\n domain: {domain} \n title: {title} \n beian: {beian} \n Version: {sys_version} \n 三方登录api: {api_host} \n')
print("++++++++++==========================++++++++++")


@app.context_processor
def inject_variables():
    return dict(
        beian=beian,
        title=title,
        username=get_username,
        domain=domain
    )


@app.route('/login', methods=['POST', 'GET'])
def login():
    callback_route = request.args.get('callback', 'home')
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
    callback_route = request.args.get('callback', 'home')
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
            with open(cache_path, 'r') as cache_file:
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

            with open(cache_path, 'w') as cache_file:
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


@cache.memoize(180)
@app.route('/blog/api/<article_name>', methods=['GET', 'POST'])
@app.route('/api/<article_name>', methods=['GET', 'POST'])
def sys_out_file(article_name):
    if article_name.startswith("tempPrev_"):
        parts = article_name[:-3].rsplit('_', 1)
        if len(parts) == 2:
            author, file_name = parts
        author = get_username()
        prev = f"""
        ```xmind preview
        ../blog/f/{author}/{file_name}
        ```

        """
        return prev

    # 隐藏文章判别
    hidden_articles = read_hidden_articles()

    if article_name[:-3] in hidden_articles:
        # 隐藏的文章
        return error(message="页面不见了", status_code=404)

    articles_dir = os.path.join(base_dir, 'articles')
    return send_from_directory(articles_dir, article_name)


@cache.memoize(600)
def get_avatar():
    avatar = app.config['AVATAR_SERVER']
    return avatar


@app.route('/profile', methods=['GET', 'POST'])
@jwt_required
def profile(user_id):
    user_name = get_username()
    avatar_url = get_avatar()
    user_bio = get_user_bio(user_id) or "这人很懒，什么也没留下"
    owner_articles = get_owner_articles(owner_id=None, user_name=user_name) or []
    user_follow = get_following_count(user_id=user_id) or 0
    follower = get_follower_count(user_id=user_id) or 0
    return render_template('Profile.html', url_for=url_for, avatar_url=avatar_url,
                           userStatus=bool(user_id), username=user_name, userBio=user_bio,
                           following=user_follow, follower=follower,
                           target_id=user_id, user_id=user_id,
                           Articles=owner_articles)


def get_user_bio(user_id):
    UserInfo = cache.get(f"{user_id}_userInfo") or get_profiles(user_id=user_id, user_name=None)

    if UserInfo is None:
        # 处理未找到用户信息的情况
        return "用户信息未找到", 404
    cache.set(f'{user_id}_userInfo', UserInfo)
    Bio = UserInfo[5] if len(UserInfo) > 5 and UserInfo[5] else "这人很懒，什么也没留下"

    return Bio


@app.route('/setting/profiles', methods=['GET', 'POST'])
@finger_required
def setting_profiles(user_id):
    UserInfo = cache.get(f"{user_id}_userInfo") or get_profiles(user_id=user_id, user_name=None)

    if UserInfo is None:
        # 处理未找到用户信息的情况
        return "用户信息未找到", 404

    cache.set(f'{user_id}_userInfo', UserInfo, timeout=3600)

    # 确保索引存在
    avatar_url = UserInfo[5] if len(UserInfo) > 5 and UserInfo[5] else app.config['AVATAR_SERVER']
    Bio = UserInfo[5] if len(UserInfo) > 5 and UserInfo[5] else "这人很懒，什么也没留下"
    user_name = UserInfo[1] if len(UserInfo) > 1 else "匿名用户"

    return render_template(
        'setting.html',
        avatar_url=avatar_url,
        userStatus=bool(user_id),
        username=user_name,
        Bio=Bio
    )


# 主页
@app.route('/', methods=['GET', 'POST'])
def home():
    if not is_valid_domain_with_slash(domain):
        return error(message="域名配置出错,您的程序将无法正常运行", status_code=503)

    if request.method == 'GET':
        page = request.args.get('page', default=1, type=int)
        tag = request.args.get('tag', default='None')
        display = get_current_theme()

        if page <= 0:
            page = 1

        home_cache = f'page_content:{display}:{page}:{tag}'

        # 尝试从缓存中获取页面内容
        content = cache.get(home_cache)
        if content:
            resp = make_response(content)
            resp.headers['Cache-Control'] = 'public, max-age=600'
            app.logger.info(f'缓存命中，页面: {page}, 标签: {tag}')
            return resp
        else:
            app.logger.info(f'缓存未命中，准备生成新内容，页面: {page}, 标签: {tag}')

        # 获取文章内容
        articles, has_next_page, has_previous_page = get_a_list(chanel=2, page=page)

        if not articles:
            app.logger.warning('没有找到任何文章！')
            return error(message="没有找到任何文章", status_code=404)

        # 模版配置
        template_display = get_current_theme()
        template_path = f'templates/theme/{template_display}/index.html'
        if os.path.exists(template_path):
            template = app.jinja_env.get_template(f'theme/{template_display}/index.html')
        else:
            template = app.jinja_env.get_template('zyIndex.html')

        notice = ''
        try:
            notice = get_sys_notice(0)
        except Exception as e:
            app.logger.error(f'读取通知文件出错: {e}')

        tags = []
        try:
            tags = get_unique_tags()
        except Exception as e:
            app.logger.error(f'获取标签出错: {e}')

        if tag != 'None':
            tag_articles = get_articles_by_tag(tag)
            if tag_articles:
                articles = get_list_intersection(articles, tag_articles)
            else:
                app.logger.warning(f'没有找到标签: {tag} 下的文章！')

        # 检查获取的文章是否为空
        info_list = get_article_info(articles)
        summary_list = get_summary(articles)
        compressed_list = list(zip(articles, summary_list, info_list))

        if not info_list:
            app.logger.warning('获取文章信息失败，返回错误提示')
            return error(message="没有找到任何文章", status_code=404)

        friends_links = get_friends_link(type=1)

        # 渲染模板并存储渲染后的页面内容到缓存中
        rendered_content = template.render(
            articles_time_list=compressed_list,
            url_for=url_for,
            notice=notice,
            has_next_page=has_next_page,
            has_previous_page=has_previous_page,
            current_page=page,
            tags=tags,
            tag=tag,
            friends_links=friends_links
        )

        # 确保渲染的内容是字符串
        if isinstance(rendered_content, str):
            cache.set(home_cache, rendered_content, timeout=360)  # 设置为360秒
        else:
            app.logger.error('渲染内容不是字符串，无法缓存。')

        resp = make_response(rendered_content)

        if 'key' in request.cookies:
            visitor = request.cookies.get('key')
            app.logger.info('访客已存在，使用现有用户名: %s', visitor)
        else:
            visitor = 'qks' + format(random.randint(10000, 99999))
            app.logger.warning('新访客，生成随机用户名: %s', visitor)
            resp.set_cookie('key', 'zyBLOG_' + sys_version + visitor, 7200)

        return resp

    else:
        return error("此方法无效", 500)


@cache.cached(timeout=1800, key_prefix='article_info')
def get_article_info(articles):
    articles_info = []
    for a_title in articles:
        try:
            articleInfo = ''
            db = get_database_connection()

            try:
                articleInfo += get_file_date(a_title)
                articleInfo += ';'
                with db.cursor() as cursor:
                    query = "SELECT * FROM articles WHERE Title = %s"
                    cursor.execute(query, (a_title,))
                    result = cursor.fetchone()
                    if result:
                        articleInfo += result[2]
                        articleInfo += ";"
                        articleInfo += str(result[5])
                        articleInfo += ";"
                        articleInfo += str(result[6])
                    else:
                        articleInfo += '官方;0;0'
            except Exception as e:
                print(f"An error occurred: {e}")
            finally:
                try:
                    cursor.close()
                except NameError:
                    pass
                db.close()

            articles_info.append(articleInfo)
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


@app.route('/blog/<article>.html', methods=['GET', 'POST'])
def blog_detail_seo(article):
    return redirect(f'/blog/{article}')


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


@app.route('/sitemap.xml')
@app.route('/sitemap')
def generate_sitemap():
    cache_dir = 'temp'
    os.makedirs(cache_dir, exist_ok=True)

    cache_file = os.path.join(cache_dir, 'sitemap.xml')

    if os.path.exists(cache_file):
        cache_timestamp = os.path.getmtime(cache_file)
        if datetime.now().timestamp() - cache_timestamp <= app.config['MAX_CACHE_TIMESTAMP']:
            with open(cache_file, 'r') as f:
                cached_xml_data = f.read()
            response = Response(cached_xml_data, mimetype='text/xml')
            return response

    markdown_files = get_a_list(chanel=1)

    # 创建XML文件头
    xml_data = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_data += '<?xml-stylesheet type="text/xsl" href="./static/sitemap.xsl"?>\n'
    xml_data += '<urlset xmlns="https://www.sitemaps.org/schemas/sitemap/0.9/">\n'

    for file in markdown_files:
        article_url = domain + 'blog/' + file
        date = get_file_date(file)
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

    # 写入缓存文件
    with open(cache_file, 'w') as f:
        f.write(xml_data)

    response = Response(xml_data, mimetype='text/xml')
    return response


@app.route('/feed')
@app.route('/rss')
def generate_rss():
    cache_dir = 'temp'
    os.makedirs(cache_dir, exist_ok=True)

    cache_file = os.path.join(cache_dir, 'feed.xml')

    if os.path.exists(cache_file):
        cache_timestamp = os.path.getmtime(cache_file)
        if datetime.now().timestamp() - cache_timestamp <= app.config['MAX_CACHE_TIMESTAMP']:
            with open(cache_file, 'r', encoding=global_encoding, errors='ignore') as f:
                cached_xml_data = f.read()
            response = Response(cached_xml_data, mimetype='application/rss+xml')
            return response

    markdown_files = get_a_list(chanel=3, page=1)

    # 创建XML文件头及其他信息...
    xml_data = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_data += '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
    xml_data += '<channel>\n'
    xml_data += '<title>' + title + 'RSS Feed </title>\n'
    xml_data += '<link>' + domain + '</link>\n'
    xml_data += '<description>' + title + 'RSS Feed</description>\n'
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

    # 写入缓存文件
    with open(cache_file, 'w', encoding=global_encoding, errors='ignore') as f:
        f.write(xml_data)

    response = Response(xml_data, mimetype='application/rss+xml')
    return response


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


def forbid_submit(user_id):
    if cache.get(f'forbid_{user_id}'):
        return True
    else:
        return False


@app.route('/newArticle', methods=['GET', 'POST'])
@jwt_required
def new_article(user_id):
    user_name = get_username()
    if not user_name:
        error(message='请先登录', status_code=401)
    if request.method == 'GET':
        if forbid_submit(user_id):
            return error('您完成了一次服务（无论成功与否），此服务短期内将变得不可达，请您10分钟之后再来', 503)
        return render_template('postNewArticle.html')

    elif request.method == 'POST':
        if forbid_submit(user_id):
            return error('距离您上次上传时间过短，请十分钟后重试', 503)

        file = request.files['file']

        logging.info(f"User {user_id} attempting to upload: {file.filename}")
        error_message = handle_file_upload(file, app.config['TEMP_FOLDER'])
        if error_message:
            logging.error(f"File upload error: {error_message[0]}")
            return error(*error_message)

        file_name = os.path.splitext(file.filename)[0]
        if set_article_info(file_name, user_name):
            message = '上传成功。但请您检查错误以及编辑。'
            logging.info(f"Article info successfully saved for {file_name} by user:{user_id}.")
            cache.set(f'forbid_{user_id}', True, timeout=600)
        else:
            message = '上传成功，但文章信息未能更新，请重试。'
            cache.set(f'forbid_{user_id}', True, timeout=600)
            logging.error("Failed to update article information in the database.")

        return render_template('postNewArticle.html', message=message)


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


@app.route('/edit/<article>', methods=['GET', 'POST', 'PUT'])
def markdown_editor(article):
    if article == 'default':
        return error(404, status_code=404)
    user_name = get_username()
    auth = False

    if user_name is not None:
        auth = auth_articles(article, user_name)

    if auth:
        aid, tags = get_tags_by_article(article)
        if request.method == 'GET':
            edit_html = zy_edit_article(article, max_line=app.config['MAX_LINE'])
            article_url = domain + 'blog/' + article
            article_surl = api_shortlink(article_url)
            # 渲染编辑页面并将转换后的HTML传递到模板中
            return render_template('editor.html', edit_html=edit_html, aid=aid, articleName=article,
                                   tags=tags, article_surl=article_surl)
        elif request.method == 'POST':
            content = request.json['content']
            return zy_save_edit(aid, content, article)
        elif request.method == 'PUT':
            tags_input = request.get_json().get('tags')
            return zy_save_tags(aid, tags_input)
        else:
            # 渲染编辑页面
            return render_template('editor.html')

    else:
        return error(message='您没有权限', status_code=503)


def zy_save_tags(aid, tags_input):
    # 将中文逗号转换为英文逗号
    tags_input = tags_input.replace("，", ",")

    # 用正则表达式限制标签数量和每个标签的长度
    tags_list = [
        tag.strip() for tag in re.split(",", tags_input, maxsplit=4) if len(tag.strip()) <= 10
    ]

    # 计算标签的哈希值
    current_tag_hash = hashlib.md5(tags_input.encode('utf-8')).hexdigest()
    previous_content_hash = cache.get(f"{aid}:tag_hash")

    # 检查内容是否与上一次提交相同
    if current_tag_hash == previous_content_hash:
        return jsonify({'show_edit': 'success'})

    # 更新缓存中的标签哈希值
    cache.set(f"{aid}:tag_hash", current_tag_hash, timeout=28800)

    # 写入更新后的标签到数据库
    write_tags_to_database(tags_list, aid)
    return jsonify({'show_edit': "success"})


def zy_save_edit(aid, content, a_name):
    save_directory = 'articles/'

    # 计算内容的哈希值
    current_content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()

    # 从缓存中获取之前的哈希值
    previous_content_hash = cache.get(f"{aid}_lasted_hash")

    # 检查内容是否与上一次提交相同
    if current_content_hash == previous_content_hash:
        return jsonify({'show_edit_code': 'success'})

    # 更新缓存中的哈希值
    cache.set(f"{aid}_lasted_hash", current_content_hash, timeout=28800)

    # 将文章名转换为字节字符串
    article_name_bytes = a_name.encode('utf-8')

    # 将字节字符串和目录拼接为文件路径
    file_path = os.path.join(save_directory, article_name_bytes.decode('utf-8') + ".md")

    # 检查保存目录是否存在，如果不存在则创建它
    if not os.path.exists(save_directory):
        os.makedirs(save_directory)

    # 将文件保存到指定的目录上，覆盖任何已存在的文件
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(content)

    return jsonify({'show_edit_code': 'success'})


last_request_time = {}


@app.route('/hidden/article', methods=['POST'])
def hidden_article():
    article = request.json.get('article')

    if article is None:
        return jsonify({'message': '404'}), 404

    user_name = get_username()
    if user_name is None:
        return jsonify({'deal': 'noAuth'})

    if not auth_articles(article, user_name):
        return jsonify({'deal': 'noAuth'})

    # 防抖机制：限制时间内对相同文章的请求
    current_time = time.time()
    cooldown_time = 6
    hidden_status_key = f"{article}_hiddenStatus"

    if hidden_status_key in last_request_time:
        last_time = last_request_time[hidden_status_key]
        if current_time - last_time < cooldown_time:
            return jsonify({'deal': 'Please wait before trying again'})

    # 更新最后请求时间
    last_request_time[hidden_status_key] = current_time

    cached_status = cache.get(hidden_status_key)

    if cached_status:
        current_hidden_status = set_article_visibility(article, hide=True)
        cache.set(hidden_status_key, current_hidden_status)
        return jsonify({'deal': 'hide'})
    else:
        current_hidden_status = set_article_visibility(article, hide=False)
        cache.set(hidden_status_key, current_hidden_status)
        return jsonify({'deal': 'unhide'})


@app.route('/media', methods=['GET', 'POST'])
@jwt_required
def media(user_id):
    media_type = request.args.get('type', default='img')
    page = request.args.get('page', default=1, type=int)
    user_name = get_username()
    if request.method == 'GET':
        preference = request.cookies.get('preference')
        template_choose = 'Media.html'
        if preference == 'V2':
            template_choose = 'Media_V2.html'
        if not media_type or media_type == 'img':
            imgs, has_next_page, has_previous_page = get_all_img(user_name, page=page, per_page=20)

            return render_template(template_choose, imgs=imgs, title='Media', url_for=url_for,
                                   has_next_page=has_next_page,
                                   has_previous_page=has_previous_page, current_page=page, userid=user_name,
                                   domain=domain)
        if media_type == 'video':
            videos, has_next_page, has_previous_page = get_all_video(user_name, page=page)

            return render_template(template_choose, videos=videos, title='Media', url_for=url_for,
                                   has_next_page=has_next_page,
                                   has_previous_page=has_previous_page, current_page=page, userid=user_name,
                                   domain=domain)

        if media_type == 'xmind':
            xminds, has_next_page, has_previous_page = get_all_xmind(user_name, page=page)

            return render_template(template_choose, xminds=xminds, title='Media', url_for=url_for,
                                   has_next_page=has_next_page,
                                   has_previous_page=has_previous_page, current_page=page, userid=user_name,
                                   domain=domain)
    elif request.method == 'POST':
        img_name = request.json.get('img_name')
        if not img_name:
            return error(message='缺少图像名称', status_code=400)

        image = get_image_path(user_name, img_name)
        if not image:
            return error(message='未找到图像', status_code=404)

        return image


@app.route('/media/<username>/<img_name>')
@app.route('/zyImg/<username>/<img_name>')
def get_image_path(username, img_name):
    preview = request.args.get('preview')
    if preview:
        return api_img(username, img_name)
    try:
        img_dir = Path(base_dir) / 'media' / username / img_name
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

    if not user_name:
        return jsonify({'message': 'failed, user not authenticated'}), 403

    try:
        allowed_types = app.config['ALLOWED_EXTENSIONS']
        user_dir = os.path.join(app.config['USER_BASE_PATH'], user_name)  # 用户文件存储目录
        os.makedirs(user_dir, exist_ok=True)  # 如果目录不存在则创建

        file_records = []  # 用于存储文件记录的列表
        with get_database_connection() as db:  # 使用上下文管理器获取数据库连接
            with db.cursor() as cursor:  # 使用上下文管理器获取数据库游标
                userid = user_id
                # 处理每个上传的文件
                for f in request.files.getlist('file'):
                    if not is_allowed_file(f.filename, allowed_types):  # 检查文件类型
                        continue

                    if f.content_length > app.config['UPLOAD_LIMIT']:
                        return jsonify({'message': f'File size exceeds the limit of {app.config['UPLOAD_LIMIT']}'}), 413

                        # 确保文件名安全并确保是字符串类型
                    newfile_name = secure_filename(str(f.filename))
                    user_dir = str(user_dir)

                    # 生成新文件路径并保存文件
                    newfile_path = os.path.join(user_dir, newfile_name)
                    f.save(newfile_path)  # 保存文件

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
                        file_records.append((userid, newfile_path, file_type, datetime.now(), datetime.now()))  # 添加文件记录
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


@app.route('/zyVideo/<username>/<video_name>')
def start_video(username, video_name):
    try:
        # 使用 pathlib.Path 处理路径
        video_dir = Path(base_dir) / 'media' / username
        video_path = video_dir / video_name

        # 检查文件是否存在
        if not video_path.exists():
            return f"Video {video_name} not found for user {username}.", 404

        # 使用 send_file 发送视频文件
        return send_file(video_path, mimetype='video/mp4', as_attachment=False, conditional=True)
    except Exception as e:
        print(f"Error in getting video path: {e}")
        return "Internal Server Error", 500


@app.route('/jump', methods=['GET', 'POST'])
def jump():
    url = request.args.get('url', default=domain)
    return render_template('inform.html', url=url, domain=domain)


@app.route('/login/<provider>')
def cc_login(provider):
    if is_valid_domain_with_slash(api_host):
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
            'author': title,
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
    user_name = title
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
    db = get_database_connection()
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
        return error(message='{file_name}不存在', status_code=404)
    else:
        app.logger.info(f'{user_id} preview: {file_name}')
        return render_template('zyDetail.html', article_content=1,
                               articleName=f"tempPrev_{file_name}", domain=domain,
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


@app.route('/following', methods=['GET', 'POST'])
@jwt_required
def following(user_id):
    ip = get_client_ip(request)

    if request.method == 'GET':

        userFllowed_key = f'subscriber_ids_uid:{user_id}'

        # 尝试从缓存中获取页面内容
        content = cache.get(userFllowed_key)
        if content:
            # 设置浏览器缓存
            resp = make_response(content)
            resp.headers['Cache-Control'] = 'public, max-age=600'  # 缓存为10分钟
            app.logger.info(f'缓存命中，following 页面: {user_id}')
            return resp
        else:
            app.logger.info(f'缓存未命中，准备生成新内容，页面: {user_id}')

        # 重新获取页面内容
        subscriber_ids_list = get_subscriber_ids(uid=user_id)

        # 模版配置
        template_display = get_current_theme()
        template_path = f'templates/theme/{template_display}/index.html'
        if os.path.exists(template_path):
            template = app.jinja_env.get_template(f'theme/{template_display}/index.html')
        else:
            template = app.jinja_env.get_template('zyIndex.html')

        app.logger.info(f'subscriber_ids 访问的用户 {user_id}, IP: {ip}')

        # 渲染模板并存储渲染后的页面内容到缓存中
        rendered_content = template.render(
            subscriber_ids_list=subscriber_ids_list, url_for=url_for,
            notice='', tags=[], page_mark='订阅'
        )

        # 缓存渲染后的页面内容，并设置服务端缓存过期时间
        cache.set(userFllowed_key, rendered_content, timeout=600)  # 服务端缓存10分钟
        resp = make_response(rendered_content)
        return resp

    if request.method == 'POST':
        return error(message='Not Found', status_code=404)


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
        db = get_database_connection()
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

    db = get_database_connection()
    try:
        with db.cursor() as cursor:
            # 进行关注操作
            insert_query = "INSERT INTO `subscriptions` (`subscriber_id`, `subscribe_to_id`, `subscribe_type`) VALUES (%s, %s, 'User')"
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

    db = get_database_connection()
    try:
        with db.cursor() as cursor:
            # 进行取关操作
            delete_query = "DELETE FROM `subscriptions` WHERE `subscriber_id` = %s AND `subscribe_to_id` = %s AND `subscribe_type` = 'User';"
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
        db = get_database_connection()
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
    sha256_hash.update(input_string.encode('utf-8'))
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
    qr_code_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

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
    cache_QR_token = cache.get(f"QR-token_{token}")
    if cache_QR_token:
        expire_at = cache_QR_token['expire_at']
        if int(expire_at) > int(time.time()):
            return success_scan()
        else:
            return jsonify({'status': 'pending'})
    else:
        return jsonify({'status': 'invalid_token'})


def success_scan():
    # 扫码成功调用此接口
    token = request.args.get('token')
    cache_QR_allowed = cache.get(f"QR-allow_{token}")
    if token and cache_QR_allowed:
        token_expire = cache_QR_allowed['expire_at']
        if int(token_expire) > int(time.time()):
            return jsonify(cache_QR_allowed)
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
        cache_QR_token = cache.get(f"QR-token_{token}")
        if cache_QR_token:
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
    cachedFinger = cache.get(f'fingerprint_{user_id}') or []
    return jsonify(cachedFinger), 200


@app.route('/finger', methods=['GET', 'POST'])
@jwt_required
def finger(user_id):
    if request.method == 'POST':
        data = request.json
        chrome_fingerprint = data.get('fingerprint')
        if user_id and chrome_fingerprint:
            cachedFinger = cache.get(f'fingerprint_{user_id}') or []
            if chrome_fingerprint not in cachedFinger:
                cachedFinger.append(chrome_fingerprint)
                cache.set(f'fingerprint_{user_id}', cachedFinger)
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
    cachedFinger = cache.get(f'fingerprint_{user_id}')
    UserInfo = cache.get(f'{user_id}_userInfo')
    user_followed = cache.get(f'{user_id}_followed')
    user_liked = cache.get(f'{user_id}_liked')
    result = {
        'key': key,
        'ip': cached_ip,
        'cachedFinger': cachedFinger,
        'UserInfo': UserInfo,
        'user_followed': user_followed,
        'user_liked': user_liked,
    }
    return jsonify(result)


@app.route('/@<user_name>', methods=['GET', 'POST'])
@user_id_required
def user_center(user_id, user_name):
    if not re.match(r'^[a-zA-Z0-9]+$', user_name):
        return error("Invalid username", 400)

    user_dir = Path(base_dir) / 'media' / user_name
    if not os.path.exists(user_dir):
        return error("Invalid username", 400)

    target_id = get_user_id(user_name)
    userBio = get_user_bio(user_id=target_id)
    canFollowed = 1
    if user_id != 0 and target_id != 0:
        canFollowed = get_can_followed(user_id, target_id)
    owner_articles = get_owner_articles(owner_id=None, user_name=user_name) or []
    noti_host, noti_port = zy_noti_conf()
    return render_template('Profile.html', url_for=url_for, avatar_url=get_avatar(),
                           userStatus=bool(user_name), username=user_name, userBio=userBio,
                           target_id=target_id, user_id=user_id,
                           Articles=owner_articles, canFollowed=canFollowed, notiHost=noti_host, notiPort=noti_port)


def diy_space(page):
    template_path = os.path.join(base_dir, 'media', page, 'index.html')
    print(template_path)
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding=global_encoding) as file:
            html_content = file.read()
            resp = make_response(html_content)
            visit_id = sys_version + format(random.randint(10000, 99999))
            resp.set_cookie('visitID', 'zyBLOG' + visit_id, 7200)
        return resp
    return error(message="Not Found", status_code=404)


@app.route('/guestbook', methods=['GET', 'POST'])
@finger_required
def guestbook(user_id):
    username = get_username()
    avatar_url = get_avatar()
    message_list = get_guestbook() or []
    user_finger = request.cookies.get('finger')
    if request.method == 'POST':
        data = request.get_json()
        nickname = data.get('nickname') or username
        message = data.get('message')
        content = f'"{nickname}":"{message}"'

        cached_user_guestbook = cache.get(f"guestbook_{user_finger}")
        if cached_user_guestbook:
            return jsonify({'status': 'failed', 'message_list': message_list}), 503
        upload_guestbook(content)
        cache.set(f"guestbook", None)
        cache.set(f"guestbook_{user_finger}", True, timeout=180)
        return jsonify({'status': 'success', 'message_list': message_list}), 201

    return render_template('guestbook.html', avatar_url=avatar_url, username=username, message_list=message_list)


def get_guestbook():
    cached_guestbook = cache.get(f"guestbook")
    if cached_guestbook:
        return cached_guestbook
    try:
        db = get_database_connection()

        try:
            with db.cursor() as cursor:
                query = "SELECT * FROM `events` WHERE Title = 'guestbook'"
                cursor.execute(query)
                result = cursor.fetchall()
                if result:
                    cache.set(f"guestbook", result)
        except Exception as e:
            print(f"An error occurred during the database operation: {e}")

        finally:
            db.close()
            return result

    except Exception as e:  # 捕获所有异常，而不是仅 FileNotFoundError
        print(f"An error occurred while getting the database connection: {e}")
        return None


def upload_guestbook(content):
    try:
        db = get_database_connection()
        try:
            with db.cursor() as cursor:
                query = "INSERT INTO `events` (`title`, `description`, `event_date`,`created_at`) VALUES ('guestbook',%s,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP);"
                cursor.execute(query, (content,))
                db.commit()
        except Exception as e:
            print(f"An error occurred during the database operation: {e}")

        finally:
            db.close()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                executor.submit(send_change_mail(content, kind='guestbook'))
    except Exception as e:
        print(f"An error occurred while getting the database connection: {e}")


@app.route('/api/notice', methods=['GET'])
@jwt_required
def user_notification(user_id):
    user_notices = get_sys_notice(user_id)
    return jsonify(user_notices)


@app.route('/api/notice/read')
def read_user_notification():
    readContent = read_notification()
    return jsonify(readContent), 200


@app.route('/changelog')
def changelog():
    updates = parse_update_file('update.txt')
    return render_template('changelog.html', updates=updates)


@app.route('/img/<username>/thumbs/<img>', methods=['GET', 'POST'])
def api_img(username, img):
    if request.method == 'GET':
        img_dir = Path(base_dir) / 'media' / username / img
        img_thumbs = Path(base_dir) / 'media' / username / 'thumbs' / img
        if os.path.isfile(img_dir) and os.path.isfile(img_thumbs):
            return send_file(img_thumbs, mimetype='image/jpeg')
        if os.path.isfile(img_dir) and not os.path.isfile(img_thumbs):
            # 使用线程池异步执行 gen_thumbs 函数
            with concurrent.futures.ThreadPoolExecutor() as executor:
                thumbs_path = os.path.join(base_dir, 'media', username, 'thumbs')
                if not os.path.exists(thumbs_path):
                    os.makedirs(thumbs_path)
                executor.submit(generate_thumbs(img_dir, img_thumbs))
            return send_file('../static/favicon.ico', mimetype='image/png')


@app.route('/video/<username>/thumbs/<video>.png', methods=['GET', 'POST'])
def api_video(username, video):
    if request.method == 'GET':
        video_dir = Path(base_dir) / 'media' / username / video
        video_thumbs = Path(base_dir) / 'media' / username / 'thumbs' / f"V-thumbs_{video}.png"
        if os.path.isfile(video_dir) and os.path.isfile(video_thumbs):
            return send_file(video_thumbs, mimetype='image/jpeg')
        if os.path.isfile(video_dir) and not os.path.isfile(video_thumbs):
            with concurrent.futures.ThreadPoolExecutor() as executor:
                thumbs_path = os.path.join(base_dir, 'media', username, 'thumbs')
                if not os.path.exists(thumbs_path):
                    os.makedirs(thumbs_path)
                executor.submit(generate_video_thumb(video_dir, video_thumbs))
            return send_file('../static/favicon.ico', mimetype='image/png')


@app.route('/xmind/<username>/thumbs/<xmind>.png', methods=['GET', 'POST'])
def api_xmind(username, xmind):
    if request.method == 'GET':
        video_dir = Path(base_dir) / 'media' / username / xmind
        if os.path.isfile(video_dir):
            return send_file('../static/image/xmind.png', mimetype='image/jpeg')


@app.route('/api/wx/home', methods=['GET'])
def api_wx_home():
    page = request.args.get('page', default=1, type=int)
    tag = request.args.get('tag', default='None')

    if page <= 0:
        page = 1

    articles, has_next_page, has_previous_page = get_a_list(chanel=2, page=page)
    notice = ''
    try:
        notice = get_sys_notice(0)
    except Exception as e:
        app.logger.error(f'读取通知文件出错: {e}')

    tags = []
    try:
        tags = get_unique_tags()
    except Exception as e:
        app.logger.error(f'获取标签出错: {e}')

    if tag != 'None':
        tag_articles = get_articles_by_tag(tag)
        if tag_articles:
            articles = get_list_intersection(articles, tag_articles)
        else:
            app.logger.warning(f'没有找到标签: {tag} 下的文章！')

    # 获取文章信息和摘要
    info_list = get_article_info(articles)
    summary_list = get_summary(articles)
    compressed_list = list(zip(articles, summary_list, info_list))

    friends_links = get_friends_link(type=1)

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


@app.route('/api/wx/blog_detail/<article>', methods=['GET'])
def api_wx_blog_detail(article):
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
        content = api_wx_content(article)

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


def api_wx_content(article):
    articles_dir = os.path.join(base_dir, 'articles', article + ".md")
    html_content = '<p>没有找到内容</p>'
    try:
        with open(articles_dir, 'r', encoding='utf-8') as file:
            content = file.read()
            html_content = markdown.markdown(content)
            return html_content
    finally:
        return html_content


@app.route('/api/wx/guestbook', methods=['GET', 'POST'])
def api_wx_guestbook():
    avatar_url = get_avatar()
    message_list = get_guestbook() or []
    response_data = {
        'avatar_url': avatar_url,
        'username': "陌生人",
        'message_list': message_list
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
        db = get_database_connection()

        try:
            with db.cursor() as cursor:
                query = "SELECT `Title` FROM articles WHERE ArticleID = %s"
                cursor.execute(query, (int(aid),))
                result = cursor.fetchone()
                if result:
                    a_title = result[0]

                    content = api_wx_content(a_title)

        except Exception:
            return jsonify({f"message": "Database error"}, 500)

        finally:
            cursor.close()
            db.close()

        return content
    else:
        return jsonify({"message": "Temporary URL expired or invalid"}), 404


@cache.cached(timeout=600, key_prefix='article_passwd')
def article_passwd(aid):
    db = get_database_connection()
    try:
        with db.cursor() as cursor:
            query = "SELECT `pass` FROM article_pass WHERE aid = %s"
            cursor.execute(query, (int(aid),))
            result = cursor.fetchone()
            if result:
                a_pass = result[0]
                return a_pass
    except Exception:
        return None

    finally:
        cursor.close()
        db.close()


@cache.cached(timeout=600, key_prefix='gen_md5')
def gen_md5(text):
    # 创建MD5哈希对象
    md5_hash = hashlib.md5()
    # 更新哈希对象
    md5_hash.update(text.encode('utf-8'))
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

    auth = auth_by_id(aid, username=get_username())

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

    userIP = get_client_ip(request) or ''
    maskedIP = ''
    if userIP:
        maskedIP = mask_ip(userIP)

    userAgent = request.headers.get('User-Agent') or ''
    userAgent = user_agent_info(userAgent)

    cache.set(f"CommentLock_{user_id}", aid, timeout=30)
    result = comment_add(aid, user_id, pid, new_comment, maskedIP, userAgent)

    if result:
        return jsonify({'aid': aid, 'changed': True}), 201
    else:
        return jsonify({"message": "评论失败"}), 500


def comment_add(aid, user_id, pid, comment_content, ip, ua):
    c_json = {'content': comment_content, 'pid': pid, 'ip': ip, 'ua': ua}
    comment_json = json.dumps(c_json)
    db = get_database_connection()
    try:
        with db.cursor() as cursor:
            query = "INSERT INTO `comments` (`article_id`, `user_id`, `content`) VALUES (%s, %s, %s);"
            cursor.execute(query, (int(aid), int(user_id), comment_json))
            db.commit()
            return True
    except Exception as e:
        print(f'Error: {e}')
        return False
    finally:
        db.close()


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
    rendered = template.render(aid=aid, user_id=user_id, username=get_username(), comments=comments,
                               has_next_page=has_next_page, has_previous_page=has_previous_page, current_page=page)
    return rendered


@app.route('/api/delete/<filename>', methods=['GET', 'delete'])
@jwt_required
def api_delete(user_id, filename):
    user_name = get_username()
    file_path = os.path.join('media', user_name, filename)
    auth = auth_files(file_path, user_id)
    if auth:
        if os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({'filename': filename, 'Deleted': True}), 201
    else:
        app.logger.info(f'{user_id} Delete: {filename} :error')
        return jsonify({'filename': filename, 'Deleted': False}), 503


@app.route('/links')
def get_friends_link(type=0):
    avatar_url = get_avatar()
    friends_links = {
        '本站地址': domain,
        'GitHub': "https://github.com/Athenavi",
        '博客园': "https://cnblogs.com/Athenavi/",
    }
    if type == 1:
        return friends_links
    return render_template('guestbook.html', avatar_url=avatar_url, link_list=friends_links)


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
    db = get_database_connection()
    try:
        with db.cursor() as cursor:
            query = "INSERT INTO `reports` (`reported_by`, `content_type`, `content_id`,`reason`) VALUES (%s, %s, %s,%s);"
            cursor.execute(query, (int(user_id), reported_type, reported_id, reason))
            db.commit()
            return True
    except Exception as e:
        print(f'Error: {e}')
        return False
    finally:
        db.close()


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
    db = get_database_connection()
    try:
        with db.cursor() as cursor:
            query = "DELETE FROM `comments` WHERE `id` = %s AND `user_id` = %s;"
            cursor.execute(query, (int(comment_id), int(user_id)))
            db.commit()
            return True
    except Exception as e:
        print(f'Error: {e}')
        return False
    finally:
        db.close()


@app.route('/travel', methods=['GET'])
def travel():
    return '此接口暂时弃用'


@app.route('/dashboard/articles', methods=['GET'])
@admin_required
def m_articles(user_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute('SELECT * FROM articles')  # 从数据库获取文章列表
    articles = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template('M-articles.html', articles=articles)


@app.route('/dashboard', methods=['GET'])
@app.route('/dashboard/overview', methods=['GET'])
@admin_required
def m_overview(user_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SHOW TABLE STATUS WHERE Name IN ('articles', 'users', 'comments','media','events');")
    dash_info = cursor.fetchall()
    cursor.execute('SELECT * FROM events')
    events = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template('M-overview.html', dashInfo=dash_info, events=events)


@app.route('/dashboard/users', methods=['GET'])
@admin_required
def m_users(user_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute('SELECT * FROM users')  # 从数据库获取用户列表
    users = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template('M-users.html', users=users)


@app.route('/dashboard/comments', methods=['GET'])
@admin_required
def m_comments(user_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute('SELECT * FROM comments')
    comments = cursor.fetchall()
    cursor.close()
    connection.close()

    return render_template('M-comments.html', comments=comments)


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
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute('SELECT * FROM media')  # 从数据库获取媒体列表
    media_items = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template('M-media.html', media_items=media_items, domain=domain)


@app.route('/dashboard/notifications', methods=['GET'])
@admin_required
def m_notifications(user_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute('SELECT * FROM notifications')  # 从数据库获取通知列表
    notifications = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template('M-notifcations.html', notifications=notifications)


@app.route('/dashboard/reports', methods=['GET'])
@admin_required
def m_reports(user_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute('SELECT * FROM reports')  # 从数据库获取举报列表
    reports = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template('M-reports.html', reports=reports)


@app.route('/dashboard/urls', methods=['GET'])
@admin_required
def m_urls(user_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute('SELECT * FROM urls')  # 从数据库获取短链接列表
    urls = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template('M-urls.html', urls=urls)


@app.route('/dashboard/display', methods=['GET'])
@admin_required
def m_display(user_id):
    return render_template('M-display.html', displayList=get_all_themes())


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
