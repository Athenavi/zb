import configparser
import datetime
import io
import json
import logging
import os
import random
import re
import shutil
import time
import urllib.parse
import xml.etree.ElementTree as ElementTree
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

import jwt
import requests
from flask import Flask, render_template, redirect, session, request, url_for, Response, jsonify, send_file, \
    make_response, send_from_directory
from flask_caching import Cache
from jinja2 import select_autoescape
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

from src.AboutLogin import zy_login, zy_register, zy_mail_login
from src.AboutPW import zy_change_password, zy_confirm_password
from src.BlogDeal import get_article_names, get_article_content, clear_html_format, \
    get_file_date, get_blog_author, read_hidden_articles, auth_articles, \
    zy_show_article, zy_edit_article, get_all_article_names
from src.database import get_database_connection
from src.links import create_special_url
from src.user import zyadmin, zy_delete_article, error, get_owner_articles, zy_general_conf
from src.utils import zy_upload_file, get_client_ip, read_file, \
    zy_save_edit, zy_noti_conf, generate_jwt, secret_key, authenticate_jwt, \
    authenticate_refresh_token

global_encoding = 'utf-8'

app = Flask(__name__, template_folder='../templates', static_folder="../static")
app.config['CACHE_TYPE'] = 'simple'
cache = Cache(app)
app.secret_key = secret_key
app.config['SESSION_COOKIE_NAME'] = 'zb_session'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=3)
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
        username=get_username,
        domain=domain
    )


@app.route('/login', methods=['POST', 'GET'])
def login():
    callback = request.args.get('callback', 'home')
    if request.cookies.get('jwt'):
        # 如果存在 jwt，解析并获取用户状态
        user_id = authenticate_jwt(request.cookies.get('jwt'))
        if user_id:
            return redirect(url_for(callback))
    if request.method == 'POST':
        return zy_login()

    return render_template('Login.html', title="登录")


@app.route('/logout')
def logout():
    response = make_response(redirect(url_for('login')))
    response.set_cookie('jwt', '', expires=0)  # 清除 Cookie
    response.set_cookie('refresh_token', '', expires=0)  # 清除刷新令牌
    return response


@app.route('/register', methods=['POST', 'GET'])
def register():
    ip = get_client_ip(request, session)
    return zy_register(ip)


def jwt_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get('jwt')
        user_id = authenticate_jwt(token)
        if user_id is None:
            return error(message="Unauthorized", status_code=401)
        return f(user_id, *args, **kwargs)

    return decorated_function


@app.before_request
def check_jwt_expiration():
    # 检查 JWT 是否即将过期
    token = request.cookies.get('jwt')
    if token:
        payload = jwt.decode(token, app.secret_key, algorithms=['HS256'], options={"verify_exp": False})
        if 'exp' in payload and datetime.utcfromtimestamp(payload['exp']) < datetime.utcnow() + timedelta(minutes=5):
            # 如果 JWT 将在 5 分钟内过期，允许校验刷新令牌
            refresh_token = request.cookies.get('refresh_token')
            user_id = authenticate_refresh_token(refresh_token)
            if user_id:
                new_token = generate_jwt(user_id, payload['username'])
                response = make_response()
                response.set_cookie('jwt', new_token, httponly=True)  # 刷新 JWT
                return response


def get_username():
    token = request.cookies.get('jwt')
    if token:
        payload = jwt.decode(token, app.secret_key, algorithms=['HS256'], options={"verify_exp": False})
        return payload['username']


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get('jwt')
        user_id = authenticate_jwt(token)
        if user_id != 1:
            return error(message="Unauthorized", status_code=403)
        return f(user_id, *args, **kwargs)

    return decorated_function


@app.route('/search', methods=['GET', 'POST'])
@jwt_required
def search(user_id):
    matched_content = []

    if request.method == 'POST':
        keyword = request.form.get('keyword')  # 获取搜索关键字
        cache_dir = os.path.join('temp', 'search')
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, keyword + '.xml')

        # 检查缓存是否存在且在一个小时之内
        if os.path.isfile(cache_path) and (time.time() - os.path.getmtime(cache_path) < 3600):
            # 读取缓存并继续处理
            with open(cache_path, 'r') as cache_file:
                match_data = cache_file.read()
        else:
            files = os.listdir('articles')
            markdown_files = [file for file in files if file.endswith('.md')]

            # 创建XML根元素
            root = ElementTree.Element('root')

            for file in markdown_files:
                article_name = file[:-3]  # 移除文件扩展名 (.md)
                encoded_article_name = urllib.parse.quote(article_name)  # 对文件名进行编码处理
                article_url = domain + 'blog/' + encoded_article_name
                date = get_file_date(encoded_article_name)
                describe = get_article_content(article_name, 50)  # 建议的值50以内
                describe = clear_html_format(describe)

                if keyword.lower() in article_name.lower() or keyword.lower() in describe.lower():
                    # 创建item元素并包含内容
                    item = ElementTree.SubElement(root, 'item')
                    ElementTree.SubElement(item, 'title').text = article_name
                    ElementTree.SubElement(item, 'link').text = article_url
                    ElementTree.SubElement(item, 'pubDate').text = date
                    ElementTree.SubElement(item, 'description').text = describe

            # 创建XML树
            tree = ElementTree.ElementTree(root)

            # 将XML数据转换为字符串
            match_data = ElementTree.tostring(tree.getroot(), encoding=global_encoding, method='xml').decode()

            # 写入缓存
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


def check_exist(cache_file):
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
            cache_timestamp = datetime.fromtimestamp(os.path.getmtime(cache_file))
            if datetime.now() - cache_timestamp <= timedelta(hours=1):
                return jsonify(cache_data)


@app.route('/blog/api/<article_name>', methods=['GET', 'POST'])
@app.route('/api/<article_name>', methods=['GET', 'POST'])
def sys_out_file(article_name):
    if article_name.startswith("tempPrev_"):
        return temp_preview(article_name[:-3])

    # 隐藏文章判别
    hidden_articles = read_hidden_articles()

    if article_name[:-3] in hidden_articles:
        # 隐藏的文章
        return error(message="页面不见了", status_code=404)

    articles_dir = os.path.join(base_dir, 'articles')
    return send_from_directory(articles_dir, article_name)


def temp_preview(file_name):
    parts = file_name.rsplit('_', 1)
    if len(parts) == 2:
        author, file_name = parts
        print(author, file_name)
    author = get_username()
    prev = f"""
```xmind preview
../blog/f/{author}/{file_name}
```

"""
    return prev


def get_avatar():
    username = get_username()
    if username:
        avatar = os.path.join(base_dir, 'media', username, 'avatar.png')
        if os.path.exists(avatar):
            avatar_url = domain + 'zyImg/' + username + '/avatar.png'
        else:
            avatar_url = None
    else:
        avatar_url = domain + 'static/favicon.ico'
    return avatar_url


@app.route('/profile', methods=['GET', 'POST'])
@jwt_required
def profile(user_id):
    avatar_url = get_avatar() or domain + 'static/favicon.ico'
    owner_id = request.args.get('id')
    username = get_username()
    if owner_id is None or owner_id == '':
        owner_articles = get_owner_articles(owner_id=None, user_name=username) or []
    else:
        owner_articles = get_owner_articles(owner_id=owner_id, user_name=None) or []

    notiHost, notiPort = zy_noti_conf()

    # 确保 render_template 返回正确对象
    return render_template('Profile.html', url_for=url_for, avatar_url=avatar_url,
                           userStatus=bool(user_id), username=username,
                           Articles=owner_articles, notiHost=notiHost)


@app.route('/setting/profiles', methods=['GET', 'POST'])
@jwt_required
def setting_profiles(user_id):
    avatar_url = get_avatar() or domain + 'static/favicon.ico'
    username = get_username()
    return render_template('setting.html', url_for=url_for, avatar_url=avatar_url,
                           userStatus=bool(user_id), username=username)


def get_unique_tags():
    db = get_database_connection()
    cursor = db.cursor()
    unique_tags = []

    try:
        query = "SELECT Tags FROM articles"
        cursor.execute(query)

        results = cursor.fetchall()
        for result in results:
            tags_str = result[0]
            if tags_str:
                tags_list = tags_str.split(';')
                unique_tags.extend(tags for tags in tags_list if tags)

        unique_tags = list(set(unique_tags))

    except Exception as e:
        logging.error(f"Error logging in: {e}")
        return "未知错误"

    finally:
        cursor.close()
        db.close()

    return unique_tags


def get_articles_by_tag(tag_name):
    db = get_database_connection()
    cursor = db.cursor()
    tag_articles = []

    try:
        query = "SELECT Title FROM articles WHERE Tags LIKE %s"
        cursor.execute(query, ('%' + tag_name + '%',))

        results = cursor.fetchall()
        for result in results:
            tag_articles.append(result[0])

    except Exception as e:
        logging.error(f"Error logging in: {e}")
        return "未知错误"

    finally:
        cursor.close()
        db.close()

    return tag_articles


def get_tags_by_article(article_title):
    db = get_database_connection()
    cursor = db.cursor()
    unique_tags = []

    try:
        query = "SELECT Tags FROM articles WHERE Title = %s"
        cursor.execute(query, (article_title,))

        result = cursor.fetchone()
        if result:
            tags_str = result[0]
            if tags_str:
                tags_list = tags_str.split(';')
                unique_tags = list(set(tags_list))

    except Exception as e:
        logging.error(f"Error logging in: {e}")
        return error("未知错误", 500), 500
    finally:
        cursor.close()
        db.close()

    return unique_tags


def get_list_intersection(list1, list2):
    intersection = list(set(list1) & set(list2))
    return intersection


def is_valid_domain_with_slash(url):
    pattern = r"^(https?://)?([a-zA-Z0-9-]+\.)*[a-zA-Z]{2,}(\/)$"

    if re.match(pattern, url):
        return True
    else:
        return False


# 主页
@app.route('/', methods=['GET', 'POST'])
def home():
    if is_valid_domain_with_slash(domain):
        pass
    else:
        return render_template('error.html', status_code='域名配置出错,您的程序将无法正常运行'), 404

    # 获取客户端IP地址
    ip = get_client_ip(request, session)

    if request.method == 'GET':
        page = request.args.get('page', default=1, type=int)
        tag = request.args.get('tag', default='None')

        if page <= 0:
            page = 1

        cache_key = f'page_content:{page}:{tag}'  # 根据页面值、主题以及标签生成缓存键

        # 尝试从缓存中获取页面内容
        content = cache.get(cache_key)
        if content:
            # 设置浏览器缓存
            resp = make_response(content)
            resp.headers['Cache-Control'] = 'public, max-age=600'  # 缓存为10分钟
            app.logger.info(f'缓存命中，页面: {page}, 标签: {tag}')
            return resp
        else:
            app.logger.info(f'缓存未命中，准备生成新内容，页面: {page}, 标签: {tag}')

        # 重新获取页面内容
        articles, has_next_page, has_previous_page = get_article_names(page=page)

        # 模版配置
        template_display = session.get('display', 'default')
        template_path = f'templates/theme/{template_display}/index.html'
        if os.path.exists(template_path):
            template = app.jinja_env.get_template(f'theme/{template_display}/index.html')
        else:
            template = app.jinja_env.get_template('zyIndex.html')

        notice = ''
        try:
            notice = read_file('notice/1.txt', 3000)
        except Exception as e:
            app.logger.error(f'读取通知文件出错: {e}')

        tags = []
        try:
            tags = get_unique_tags()
        except Exception as e:
            app.logger.error(f'获取标签出错: {e}')

        if tag != 'None':
            tag_articles = get_articles_by_tag(tag)
            articles = get_list_intersection(articles, tag_articles)

        infoList = get_article_info(articles)
        articles_time_list = zip(articles, infoList)

        app.logger.info(f'当前访问的用户, IP: {ip}')

        # 渲染模板并存储渲染后的页面内容到缓存中
        rendered_content = template.render(
            title=title, articles_time_list=articles_time_list, url_for=url_for,
            notice=notice, has_next_page=has_next_page, has_previous_page=has_previous_page,
            current_page=page, tags=tags, tag=tag
        )

        # 缓存渲染后的页面内容，并设置服务端缓存过期时间
        cache.set(cache_key, rendered_content, timeout=600)  # 服务端缓存10分钟
        resp = make_response(rendered_content)

        if 'key' in request.cookies:
            visiter = request.cookies.get('key')  # 使用现有的访客名称
            app.logger.info('访客已存在，使用现有用户名: %s', visiter)
        else:
            visiter = 'qks' + format(random.randint(10000, 99999))
            app.logger.warning('新访客，生成随机用户名: %s', visiter)
            resp.set_cookie('key', 'zyBLOG_' + sys_version + visiter, 7200)  # 设置 cookie

        return resp

    else:
        return render_template('zyIndex.html')


@cache.cached(timeout=1800, key_prefix='article_info')
def get_article_info(articles):
    print(articles)
    articles_info = []
    for a_title in articles:
        try:
            # 获取文件的修改时间
            articleInfo = ''
            db = get_database_connection()

            try:
                with db.cursor() as cursor:
                    query = "SELECT * FROM articles WHERE Title = %s"
                    cursor.execute(query, (a_title,))
                    result = cursor.fetchone()
                    print(result)
                    if result:
                        articleInfo += result[2]
                        articleInfo += " 点赞: "
                        articleInfo += str(result[5])
                        articleInfo += " 评论: "
                        articleInfo += str(result[6])
                    else:
                        articleInfo += get_file_date(a_title)
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


@cache.memoize(30)
def get_a_list():
    return get_all_article_names()


@app.route('/blog/<article>.html', methods=['GET', 'POST'])
def blog_detail_seo(article):
    return redirect(f'/blog/{article}')


@app.route('/blog/<article>', methods=['GET', 'POST'])
def blog_detail(article):
    try:
        # 根据文章名称获取相应的内容并处理
        article_name = article
        article_names = get_a_list()
        hidden_articles = read_hidden_articles()

        if article_name in hidden_articles:
            # 隐藏的文章
            return error(message="页面不见了", status_code=404)

        if article_name not in article_names:
            return render_template('error.html', status_code='404'), 404

        article_tags = get_tags_by_article(article_name)
        article_url = domain + 'blog/' + article_name
        article_surl = api_shortlink(article_url)
        # print(article_Surl)
        author = get_blog_author(article_name)
        update_date = get_file_date(article_name)
        response = make_response(render_template('zyDetail.html', title=title, article_content=1,
                                                 articleName=article_name,
                                                 author=author, blogDate=update_date, domain=domain,
                                                 url_for=url_for, article_Surl=article_surl, article_tags=article_tags))

        # 设置服务器端缓存时间
        response.cache_control.max_age = 180
        response.expires = datetime.now() + timedelta(seconds=180)

        # 设置浏览器端缓存时间
        response.headers['Cache-Control'] = f'public, max-age=180'

        return response

    except FileNotFoundError:
        return render_template('error.html', status_code='404'), 404


@cache.cached(timeout=300)
@app.route('/sitemap.xml')
@app.route('/sitemap')
def generate_sitemap():
    cache_dir = 'temp'
    os.makedirs(cache_dir, exist_ok=True)

    cache_file = os.path.join(cache_dir, 'sitemap.xml')

    if os.path.exists(cache_file):
        cache_timestamp = os.path.getmtime(cache_file)
        if datetime.now().timestamp() - cache_timestamp <= 3600:
            with open(cache_file, 'r') as f:
                cached_xml_data = f.read()
            response = Response(cached_xml_data, mimetype='text/xml')
            return response

    files = os.listdir('articles')
    markdown_files = [file for file in files if file.endswith('.md') and not file.startswith('_')]

    # 创建XML文件头
    xml_data = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_data += '<?xml-stylesheet type="text/xsl" href="./static/sitemap.xsl"?>\n'
    xml_data += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

    for file in markdown_files:
        article_name = file[:-3]  # 移除文件扩展名 (.md)
        article_url = domain + 'blog/' + article_name
        date = get_file_date(article_name)
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


@cache.cached(timeout=300)
@app.route('/feed')
@app.route('/rss')
def generate_rss():
    cache_dir = 'temp'
    os.makedirs(cache_dir, exist_ok=True)

    cache_file = os.path.join(cache_dir, 'feed.xml')

    if os.path.exists(cache_file):
        cache_timestamp = os.path.getmtime(cache_file)
        if datetime.now().timestamp() - cache_timestamp <= 3600:
            with open(cache_file, 'r', encoding=global_encoding, errors='ignore') as f:
                cached_xml_data = f.read()
            response = Response(cached_xml_data, mimetype='application/rss+xml')
            return response

    hidden_articles = read_hidden_articles()
    hidden_articles = [ha + ".md" for ha in hidden_articles]
    files = os.listdir('articles')
    markdown_files = [file for file in files if file.endswith('.md') and not file.startswith('_')]
    # markdown_files = markdown_files[:10]

    # 创建XML文件头及其他信息...
    xml_data = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_data += '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
    xml_data += '<channel>\n'
    xml_data += '<title>' + title + 'RSS Feed </title>\n'
    xml_data += '<link>' + domain + '</link>\n'
    xml_data += '<description>Your RSS Feed Description</description>\n'
    xml_data += '<language>en-us</language>\n'
    xml_data += '<lastBuildDate>' + datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z") + '</lastBuildDate>\n'
    xml_data += '<atom:link href="' + domain + 'rss" rel="self" type="application/rss+xml" />\n'

    for file in markdown_files:
        article_name = file[:-3]  # 移除文件扩展名 (.md)
        encoded_article_name = urllib.parse.quote(article_name)  # 对文件名进行编码处理
        article_url = domain + 'blog/' + encoded_article_name
        date = get_file_date(encoded_article_name)
        if file in hidden_articles:
            describe = "本文章属于加密文章"
            content = "本文章属于加密文章\n" + f'<a href="{article_url}" target="_blank" rel="noopener">带密码访问</a>'
        else:
            content, *_ = get_article_content(article_name, 10)
            describe = encoded_article_name

        article_surl = api_shortlink(article_url)
        # 创建item标签并包含内容
        xml_data += '<item>\n'
        xml_data += f'\t<title>{article_name}</title>\n'
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
    ip = get_client_ip(request, session)
    return zy_change_password(user_id, ip)


@app.route('/admin/<key>', methods=['GET', 'POST'])
@admin_required
def admin(user_id, key):
    method = 'GET'
    if request.method == 'POST':
        method = 'POST'
    return zyadmin(key, method)


@app.route('/admin/changeTheme', methods=['POST'])
@admin_required
def change_display(user_id):
    theme_id = request.args.get('NT')
    if theme_id:
        db = get_database_connection()
        cursor = db.cursor()
        try:
            theme_path = f'templates/theme/{theme_id}'
            if theme_id == 'default':
                print(f"recover theme to {theme_id}")
                session['display'] = theme_id
                return 'success'

            if os.path.exists(theme_path):
                has_index_html = os.path.exists(os.path.join(theme_path, 'index.html'))
                has_screenshot_png = os.path.exists(os.path.join(theme_path, 'screenshot.png'))
                has_template_ini = os.path.exists(os.path.join(theme_path, 'template.ini'))

                if has_index_html and has_screenshot_png and has_template_ini:
                    print(f"update theme to {theme_path}")
                    session['display'] = theme_id
                    query = "INSERT INTO `events` (`id`, `title`, `description`, `event_date`, `created_at`) VALUES (NULL, 'theme change', %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);"
                    cursor.execute(query, (theme_id,))
                    db.commit()
                    return 'success'

                else:
                    return 'failed'
            else:
                return error("非管理员用户禁止访问！！！", 403)
        except Exception as e:
            logging.error(f"Error logging in: {e}")
            return error("未知错误", 500), 500
        finally:
            cursor.close()
            db.close()


last_newArticle_time = {}  # 全局变量，用于记录用户最后递交时间
app.config['UPLOAD_FOLDER'] = 'temp/upload'


def can_user_submit(username):
    current_time = time.time()
    last_time = last_newArticle_time.get(username)
    return last_time is None or current_time - last_time >= 600


def handle_file_upload(file):
    # 验证文件格式和大小
    if not file.filename.endswith('.md') or file.content_length > 10 * 1024 * 1024:
        return 'Invalid file format or file too large.', 400

    upload_folder = app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    file_path = os.path.join(upload_folder, file.filename)

    # 避免文件名冲突
    if os.path.isfile(os.path.join('articles', file.filename)):
        return 'Upload failed, the file already exists.', 400

    # 保存文件
    file.save(file_path)
    shutil.copy(file_path, 'articles')
    return None


@app.route('/newArticle', methods=['GET', 'POST'])
@jwt_required
def new_article(user_id):
    username = get_username()
    if not username:
        error(message='请先登录', status_code=401)
    if request.method == 'GET':
        if not can_user_submit(user_id):
            return error('您完成了一次服务（无论成功与否），此服务短期内将变得不可达，请您10分钟之后再来', 503)
        return render_template('postNewArticle.html')

    elif request.method == 'POST':
        if not can_user_submit(user_id):
            return error('距离您上次上传时间过短，请十分钟后重试', 503)

        last_newArticle_time[user_id] = time.time()
        file = request.files['file']

        logging.info(f"User {user_id} attempting to upload: {file.filename}")
        error_message = handle_file_upload(file)
        if error_message:
            logging.error(f"File upload error: {error_message[0]}")
            return error(*error_message)

        file_name = os.path.splitext(file.filename)[0]
        if set_article_info(file_name, username):
            message = '上传成功。但请您检查错误以及编辑。'
            logging.info(f"Article info successfully saved for {file_name} by user:{user_id}.")
        else:
            message = '上传成功，但文章信息未能更新，请重试。'
            logging.error("Failed to update article information in the database.")

        return render_template('postNewArticle.html', message=message)


def set_article_info(title, username):
    db = get_database_connection()
    try:
        with db.cursor() as cursor:
            # 获取当前年份
            current_year = datetime.now().year  # 直接使用 datetime 类

            # 插入或更新文章信息，tags 写入当前年份
            query = """
            INSERT INTO articles (Title, Author, tags) 
            VALUES (%s, %s, %s) 
            ON DUPLICATE KEY UPDATE Author = %s, tags = %s;
            """

            logging.debug(
                f"Executing SQL: {query} with parameters: {(title, username, current_year, username, current_year)}")
            cursor.execute(query, (title, username, current_year, username, current_year))

            # 记录事件信息
            event_log = "INSERT INTO events (title, description, event_date, created_at) VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);"
            event_title = 'article update'
            event_description = f'{username} updated {title}'
            cursor.execute(event_log, (event_title, event_description))

            # 提交事务
            db.commit()
            return True  # 表示操作成功

    except Exception as e:
        logging.error(f"An error occurred during database operation: {e}")
        # 事务回滚
        db.rollback()
        return False  # 表示操作失败

    finally:
        db.close()


@app.route('/Admin_upload', methods=['GET', 'POST'])
@admin_required
def upload_file1(user_id):
    return zy_upload_file()


@app.route('/delete/<filename>', methods=['POST'])
@jwt_required
def delete_file(user_id, filename):
    username = get_username()
    if username:
        auth = auth_articles(title=filename, username=username)
        if auth:
            return zy_delete_article(filename)
    else:
        return error(message='您没有权限', status_code=503)


@cache.cached(timeout=4800)
@app.route('/robots.txt')
def static_from_root():
    content = "User-agent: *\nDisallow: /admin"
    modified_content = content + '\nSitemap: ' + domain + 'sitemap.xml'  # Add your additional rule here

    response = Response(modified_content, mimetype='text/plain')
    return response


@app.route('/edit/<article>', methods=['GET', 'POST', 'PUT'])
def markdown_editor(article):
    if article == 'default':
        return error(404, status_code=404)
    username = get_username()
    auth = False  # 设置默认值

    if username is not None:
        # Auth 认证
        auth = auth_articles(article, username)

    if auth:
        if request.method == 'GET':
            edit_html = zy_edit_article(article)
            show_edit = zy_show_article(article)

            tags = get_tags_by_article(article)

            # 渲染编辑页面并将转换后的HTML传递到模板中
            return render_template('editor.html', edit_html=edit_html, show_edit=show_edit, articleName=article,
                                   tags=tags)
        elif request.method == 'POST':
            content = request.json['content']
            save_edit_code = zy_save_edit(article, content)
            return jsonify({'show_edit_code': save_edit_code})
        elif request.method == 'PUT':
            tags_input = request.get_json().get('tags')
            tags_list = []
            # 将中文逗号转换为英文逗号
            tags_input = tags_input.replace("，", ",")

            # 用正则表达式截断标签信息中超过五个标签的部分
            comma_count = tags_input.count(",")
            if comma_count > 4:
                tags_input = re.split(",", tags_input, maxsplit=4)[0]

            # 限制每个标签最大字符数为10，并添加到标签列表

            for tag in tags_input.split(","):
                tag = tag.strip()
                if len(tag) <= 10:
                    tags_list.append(tag)

            # 写入更新后的标签到数据库
            write_tags_to_database(tags_list, article)
            return jsonify({'show_edit': "success"})

        else:
            # 渲染编辑页面
            return render_template('editor.html')

    else:
        return error(message='您没有权限', status_code=503)


def write_tags_to_database(tags_list, title):
    tags_str = ';'.join(tags_list)

    db = get_database_connection()
    cursor = db.cursor()

    try:
        # 检查文章是否存在
        query = "SELECT * FROM articles WHERE Title = %s"
        cursor.execute(query, (title,))
        result = cursor.fetchone()

        if result:
            # 如果文章存在，则更新标签
            update_query = "UPDATE articles SET Tags = %s WHERE Title = %s"
            cursor.execute(update_query, (tags_str, title))
            db.commit()
        else:
            # 如果文章不存在，则创建新文章记录
            insert_query = "INSERT INTO articles (Title, Tags) VALUES (%s, %s)"
            cursor.execute(insert_query, (title, tags_str))
            db.commit()

    except Exception as e:
        logging.error(f"Error writing tags to database: {e}")

    finally:
        cursor.close()
        db.close()


@app.route('/save/edit', methods=['POST'])
def edit_save():
    content = request.json.get('content', '')
    article = request.json.get('article')

    if article is None:
        return jsonify({'message': '404'}), 404

    username = get_username()

    if username is None:
        return jsonify({'message': '您没有权限'}), 503

    # Auth 认证
    auth = auth_articles(article, username)

    if not auth:
        return jsonify({'message': '404'}), 404

    save_edit_code = zy_save_edit(article, content)
    if save_edit_code == 'success':
        return jsonify({'show_edit_code': 'success'})
    else:
        return jsonify({'show_edit_code': 'failed'})


@app.route('/hidden/article', methods=['POST'])
def hidden_article():
    article = request.json.get('article')
    if article is None:
        return jsonify({'message': '404'}), 404

    username = get_username()

    if username is None:
        return jsonify({'deal': 'noAuth'})

    auth = auth_articles(article, username)

    if not auth:
        return jsonify({'deal': 'noAuth'})

    if is_hidden(article):
        # 取消隐藏文章
        unhidden_article(article)
        return jsonify({'deal': 'unhide'})
    else:
        # 隐藏文章
        hide_article(article)
        return jsonify({'deal': 'hide'})


def hide_article(article):
    db = get_database_connection()
    try:
        with db.cursor() as cursor:
            query = "SELECT * FROM articles WHERE Title = %s"
            cursor.execute(query, (article,))
            result = cursor.fetchone()

            if result is None:
                query = "INSERT INTO articles (Title, Author, Hidden) VALUES (%s, 'test', 1)"
                cursor.execute(query, (article,))
            elif result[3] == 0:
                query = "UPDATE articles SET Hidden = 1 WHERE Title = %s"
                cursor.execute(query, (article,))

            db.commit()
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        try:
            cursor.close()
        except NameError:
            pass
        db.close()


def unhidden_article(article):
    db = get_database_connection()
    try:
        with db.cursor() as cursor:
            query = "SELECT * FROM articles WHERE Title = %s"
            cursor.execute(query, (article,))
            result = cursor.fetchone()

            if result is not None and result[3] == 1:
                query = "UPDATE articles SET Hidden = 0 WHERE Title = %s"
                cursor.execute(query, (article,))
            elif result is None:
                query = "INSERT INTO articles (Title, Author, Hidden) VALUES (%s, 'test', 0)"
                cursor.execute(query, (article,))

            db.commit()
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        try:
            cursor.close()
        except NameError:
            pass
        db.close()


def is_hidden(article):
    db = get_database_connection()
    try:
        with db.cursor() as cursor:
            query = "SELECT Hidden FROM articles WHERE Title = %s"
            cursor.execute(query, (article,))
            result = cursor.fetchone()

            if result is not None and result[0] == 1:
                return True
            else:
                return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False
    finally:
        try:
            cursor.close()
        except NameError:
            pass
        db.close()


@app.route('/travel', methods=['GET'])
def travel():
    response = requests.get(domain + 'sitemap.xml')  # 发起对/sitemap接口的请求
    if response.status_code == 200:
        tree = ElementTree.fromstring(response.content)  # 使用xml.etree.ElementTree解析响应内容

        urls = []  # 用于记录提取的URL列表
        for url_element in tree.findall('{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
            loc_element = url_element.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
            if loc_element is not None:
                urls.append(loc_element.text)  # 将标签中的内容添加到列表中

        if urls:
            random.shuffle(urls)  # 随机打乱URL列表的顺序
            random_url = urls[0]  # 选择打乱后的第一个URL
            return render_template('zyJump.html', url=random_url, domian=domain)
        # 如果没有找到任何<loc>标签，则返回适当的错误信息或默认页面
        return "No URLs found in the response."
    else:
        # 处理无法获取响应内容的情况，例如返回错误页面或错误消息
        return "Failed to fetch sitemap content."


@app.route('/media', methods=['GET', 'POST'])
def media_space():
    type = request.args.get('type', default='img')
    page = request.args.get('page', default=1, type=int)
    username = request.args.get('username', default=get_username())
    if username is not None:
        if request.method == 'GET':
            if not type or type == 'img':
                imgs, has_next_page, has_previous_page = get_all_img(username, page=page)

                return render_template('Media.html', imgs=imgs, title='Media', url_for=url_for,
                                       theme=session.get('theme'), has_next_page=has_next_page,
                                       has_previous_page=has_previous_page, current_page=page, userid=username,
                                       domain=domain)
            if type == 'video':
                videos, has_next_page, has_previous_page = get_all_video(username, page=page)

                return render_template('Media.html', videos=videos, title='Media', url_for=url_for,
                                       theme=session.get('theme'), has_next_page=has_next_page,
                                       has_previous_page=has_previous_page, current_page=page, userid=username,
                                       domain=domain)

            if type == 'xmind':
                xminds, has_next_page, has_previous_page = get_all_xmind(username, page=page)

                return render_template('Media.html', xminds=xminds, title='Media', url_for=url_for,
                                       theme=session.get('theme'), has_next_page=has_next_page,
                                       has_previous_page=has_previous_page, current_page=page, userid=username,
                                       domain=domain)
        elif request.method == 'POST':
            img_name = request.json.get('img_name')
            if not img_name:
                return error(message='缺少图像名称', status_code=400)

            image = get_image_path(username, img_name)
            if not image:
                return error(message='未找到图像', status_code=404)

            return image

    return error(message='您没有权限', status_code=503)


def get_media_list(username, category, page=1, per_page=10):
    file_suffix = ()
    if category == 'img':
        file_suffix = ('.png', '.jpg', '.webp')
    elif category == 'video':
        file_suffix = ('.mp4', '.avi', '.mkv', '.webm', '.flv')
    elif category == 'xmind':
        file_suffix = '.xmind'
    file_dir = os.path.join('media', username)
    if not os.path.exists(file_dir):
        os.makedirs(file_dir)

    files = [file for file in os.listdir(file_dir) if file.endswith(tuple(file_suffix))]
    files = sorted(files, key=lambda x: os.path.getctime(os.path.join(file_dir, x)), reverse=True)
    total_img_count = len(files)
    total_pages = (total_img_count + per_page - 1) // per_page

    start_index = (page - 1) * per_page
    end_index = start_index + per_page
    files = files[start_index:end_index]

    has_next_page = page < total_pages
    has_previous_page = page > 1

    return files, has_next_page, has_previous_page


def get_all_img(username, page=1, per_page=10):
    imgs, has_next_page, has_previous_page = get_media_list(username, category='img')
    return imgs, has_next_page, has_previous_page


def get_all_video(username, page=1, per_page=10):
    videos, has_next_page, has_previous_page = get_media_list(username, category='video')
    return videos, has_next_page, has_previous_page


def get_all_xmind(username, page=1, per_page=10):
    videos, has_next_page, has_previous_page = get_media_list(username, category='xmind')
    return videos, has_next_page, has_previous_page


@app.route('/zyImg/<username>/<img_name>')
def get_image_path(username, img_name):
    try:
        img_dir = Path(base_dir) / 'media' / username / img_name

        # 从缓存中获取图像数据
        img_data = cache.get(str(img_dir))

        # 如果缓存中没有图像数据，则从文件中读取并进行缓存
        if img_data is None:
            with open(img_dir, 'rb') as f:
                img_data = f.read()
            cache.set(img_dir, img_data)

        # 使用 BytesIO 包装图像数据
        return send_file(io.BytesIO(img_data), mimetype='image/png')
    except Exception as e:
        print(f"Error in getting image path: {e}")
        return None


app.config['UPLOADED_PATH'] = 'media'


@app.route('/upload_file', methods=['POST'])
@jwt_required
def upload_user_path(user_id):
    username = get_username()

    if not username:
        return jsonify({'message': 'failed, user not authenticated'}), 403

    try:
        # 定义允许上传的文件类型
        allowed_types = {'.jpg', '.png', '.webp', '.jfif', '.pjpeg', '.jpeg', '.pjp', '.mp4', '.xmind'}
        user_dir = os.path.join(app.config['UPLOADED_PATH'], username)  # 用户文件存储目录
        os.makedirs(user_dir, exist_ok=True)  # 如果目录不存在则创建

        file_records = []  # 用于存储文件记录的列表
        with get_database_connection() as db:  # 使用上下文管理器获取数据库连接
            with db.cursor() as cursor:  # 使用上下文管理器获取数据库游标
                userid = user_id
                # 处理每个上传的文件
                for f in request.files.getlist('file'):
                    if not is_allowed_file(f.filename, allowed_types):  # 检查文件类型
                        continue

                    if f.content_length > 60 * 1024 * 1024:  # 检查文件大小
                        return jsonify({'message': 'File size exceeds the limit of 60MB'}), 413

                    newfile_name = secure_filename(f.filename)  # 确保文件名是安全的
                    newfile_path = os.path.join(user_dir, newfile_name)  # 生成新文件路径
                    f.save(newfile_path)  # 保存文件

                    # 确定文件类型
                    file_type = ('image' if f.filename.lower().endswith(
                        ('.jpg', '.jpeg', '.png', '.webp', '.jfif', '.pjpeg', '.pjp'))
                                 else 'video' if f.filename.lower().endswith('.mp4')
                    else 'document')

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
                        app.logger.info(f'User: {username}, Uploaded file: {newfile_name}')  # 记录上传日志

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


def is_allowed_file(filename, allowed_types):
    # 检查文件是否是允许的类型
    return any(filename.lower().endswith(ext) for ext in allowed_types)


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
    return render_template('zyJump.html', url=url, domain=domain)


@app.route('/login/<provider>')
def cc_login(provider):
    if is_valid_domain_with_slash(api_host):
        pass
    else:
        return render_template('error.html', status_code='彩虹聚合登录API接口配置错误,您的程序无法使用第三方登录'), 404
    if provider not in ['qq', 'wx', 'alipay', 'sina', 'baidu', 'huawei', 'xiaomi', 'dingtalk']:
        return jsonify({'message': 'Invalid login provider'})

    redirect_uri = domain + "callback/" + provider

    api_safe_check = [api_host, app_id, app_key]
    if 'error' in api_safe_check:
        return render_template('error.html', error='请检查你的第三方登录配置文件')
    login_url = f'{api_host}connect.php?act=login&appid={app_id}&appkey={app_key}&type={provider}&redirect_uri={redirect_uri}'
    response = requests.get(login_url)
    data = response.json()
    code = data.get('code')
    msg = data.get('msg')
    if code == 0:
        cc_url = data.get('url')
    else:
        return render_template('error.html', error=msg)

    return redirect(cc_url, 302)


@app.route('/callback/<provider>')
def callback(provider):
    user_email = ''
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
        ip = data.get('ip')
        session['public_ip'] = ip
        if provider == 'qq':
            user_email = social_uid + "@qq.com"
        if provider == 'wx':
            user_email = social_uid + "@wx.com"
        elif provider != 'qq' and 'wx':
            user_email = social_uid + "@qks.com"
        # face_img = get_user_info(provider, social_uid)
        return zy_mail_login(user_email, ip)

    return render_template('Login.html', error=msg)


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
    if os.path.exists(f'templates/theme/{theme_id}'):
        theme_detail = configparser.ConfigParser()
        # 读取 template.ini 文件
        theme_detail.read(f'templates/theme/{theme_id}/template.ini', encoding=global_encoding)
        # 获取配置文件中的属性值
        tid = theme_detail.get('default', 'id').strip("'")
        author = theme_detail.get('default', 'author').strip("'")
        theme_title = theme_detail.get('default', 'title').strip("'")
        author_website = theme_detail.get('default', 'authorWebsite').strip("'")
        theme_version = theme_detail.get('default', 'version').strip("'")
        theme_version_code = theme_detail.get('default', 'versionCode').strip("'")
        update_url = theme_detail.get('default', 'updateUrl').strip("'")
        screenshot = theme_detail.get('default', 'screenshot').strip("'")

        theme_properties = {
            'id': tid,
            'author': author,
            'title': theme_title,
            'authorWebsite': author_website,
            'version': theme_version,
            'versionCode': theme_version_code,
            'updateUrl': update_url,
            'screenshot': screenshot,
        }

        return jsonify(theme_properties)


@app.route('/theme/<theme_id>/<img_name>')
def get_screenshot(theme_id, img_name):
    if theme_id == 'default':
        return send_file('../static/favicon.ico', mimetype='image/png')
    try:
        img_dir = os.path.join(base_dir, 'templates', 'theme', theme_id, img_name)

        # 从缓存中获取图像数据
        img_data = cache.get(img_dir)

        # 如果缓存中没有图像数据，则从文件中读取并进行缓存
        if img_data is None:
            with open(img_dir, 'rb') as f:
                img_data = f.read()
            cache.set(img_dir, img_data)

        img_io = io.BytesIO(img_data)
        img_io.seek(0)

        return send_file(img_io, mimetype='image/png')
    except Exception as e:
        print(f"Error in getting image path: {e}")
        return jsonify(error='Failed to get image path')


@app.route('/favicon.ico', methods=['GET', 'POST'])
def favicon():
    return send_file('../static/favicon.ico', mimetype='image/png')


@app.route('/@<page>', methods=['GET', 'POST'])
def diy_space(page):
    template_path = os.path.join(base_dir, 'media', page, 'index.html')
    print(template_path)
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding=global_encoding) as file:
            html_content = file.read()
            resp = make_response(html_content)
            visit_id = sys_version + format(random.randint(10000, 99999))  # 可以设置一个默认值或者抛出异常，具体根据需求进行处理
            resp.set_cookie('visitID', 'zyBLOG' + visit_id, 7200)
        return resp
    return render_template('error.html')


@cache.cached(timeout=300, key_prefix='short_link')
@app.route('/s/<short_url>', methods=['GET', 'POST'])
def redirect_to_long_url_route(short_url):
    if len(short_url) != 6:
        return 'error'
    user_agent = request.headers.get('User-Agent')
    db = get_database_connection()
    cursor = db.cursor()

    # 根据短网址查询数据库获取对应的长网址
    query = "SELECT long_url FROM urls WHERE short_url = %s"
    cursor.execute(query, (short_url,))
    result = cursor.fetchone()

    if result:
        # 如果找到对应的长网址，则进行重定向
        long_url = result[0]
        # 获取请求者的 IP 地址
        ip_address = get_client_ip(request, session)
        app.logger.info('当前访问的用户:IP:{},UA:{}'.format(ip_address, user_agent))
        db.commit()

        # 关闭数据库连接
        cursor.close()
        db.close()

        return redirect(long_url, code=302)
    else:
        # 如果没有找到对应的长网址，则返回错误页面或其他处理逻辑
        logging.error(f"Invalid short URL: {short_url}")
        return "短网址无效"


@app.route('/api/shortlink')
def api_shortlink(long_url):
    if not long_url.startswith('https://') and not long_url.startswith('http://'):
        return 'error'
    username = '7trees'
    short_url = create_special_url(long_url, username)  # 传递用户名参数
    article_surl = domain + 's/' + short_url
    return article_surl


@cache.cached(timeout=1200)
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
            # print(article)
            return blog_detail(article)
        else:
            # If no URL is found
            logging.error(f"URL not found for: {article_id}")
            return error(message='没有找到文章', status_code=404)
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        db.rollback()
        return error(message='服务器内部错误', status_code=500), 500
    finally:
        ip_address = get_client_ip(request, session)
        app.logger.info(f'IP:{ip_address}, UA:{user_agent}')
        cursor.close()
        db.close()


@cache.cached(timeout=1200)
@app.route('/blog/<article_name>/images/<image_name>', methods=['GET'])
def sys_out_article_img(article_name, image_name):
    author = get_blog_author(article_name)

    if author is None:
        author = 'test'

    articles_img_dir = os.path.join(base_dir, 'media', str(author))  # 确保author是字符串
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
        return render_template('error.html', message=f'{file_name}不存在', status_code=404)
    else:
        return render_template('zyDetail.html', title=title, article_content=1,
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
    send_email(sender_email, password, receiver_email, smtp_server, stmp_port=int(stmp_port), subject=subject,
               body=body)
    return 'success'


@app.route('/test')
def test():
    alert = "hello world"
    return alert


@app.errorhandler(404)
def page_not_found(error_message):
    app.logger.error(error_message)
    return "Page not found", 404


@app.errorhandler(500)
def internal_server_error(error_message):
    app.logger.error(error_message)
    return error(message=error_message, status_code=500), 500


@app.route('/<path:undefined_path>')
def undefined_route(undefined_path):
    app.logger.error(undefined_path)
    return render_template('error.html', status_code='404'), 404


@app.errorhandler(Exception)
def handle_unexpected_error(error_message):
    app.logger.error(error_message)
    return error(message=error_message, status_code=500), 500
