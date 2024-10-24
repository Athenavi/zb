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
from pathlib import Path

import requests
from flask import Flask, render_template, redirect, session, request, url_for, Response, jsonify, send_file, \
    make_response, send_from_directory
from flask_caching import Cache
from jinja2 import select_autoescape
from werkzeug.middleware.proxy_fix import ProxyFix

from src.AboutLogin import zy_login, zy_register, zy_mail_login
from src.AboutPW import zy_change_password, zy_confirm_password
from src.BlogDeal import get_article_names, get_article_content, clear_html_format, \
    get_file_date, get_blog_author, read_hidden_articles, auth_articles, \
    zy_show_article, zy_edit_article, get_all_article_names
from src.database import get_database_connection
from src.links import create_special_url
from src.user import zyadmin, zy_delete_file, zy_new_article, error, get_owner_articles, zy_general_conf
from src.utils import zy_upload_file, get_user_status, get_username, get_client_ip, read_file, \
    zy_save_edit, zy_noti_conf

global_encoding = 'utf-8'

app = Flask(__name__, template_folder='../templates', static_folder="../static")
app.config['CACHE_TYPE'] = 'simple'
cache = Cache(app)
app.secret_key = 'your_secret_key'
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

domain, title, beian, version, api_host, app_id, app_key = zy_general_conf()
print("please check information")
print("++++++++++==========================++++++++++")
print(f'\n domain: {domain} \n title: {title} \n beian: {beian} \n Version: {version} \n 三方登录api: {api_host} \n')
print("++++++++++==========================++++++++++")
print('''
                                                                                                                               
                                                                
                                                                
                           ||         ||                        
                           ||         ||                        
                           ||         ||                        
                           ||         ||                        
         ||||||   ||   ||  |||||      ||      ||||     ||||||   
         ||||||   ||   |   ||||||     ||     ||||||   |||||||   
            ||    ||  ||   ||  |||    ||     ||   ||  ||  ||    
           |||     || ||   ||   ||    ||     ||   ||  ||  ||    
          |||      || |    ||   ||    ||     ||   ||  |||||     
          ||       ||||    ||  ||     ||     ||  |||  ||        
         |||||||    |||    ||||||     ||     ||||||   ||||||    
         |||||||    ||     |||||      ||       |||    ||   ||   
                  ||||                                |||||||   
                  |||                                  |||||    
                                                                
                                                                
                                                                
''')
print("++++++++++==========================++++++++++")


@app.context_processor
def inject_variables():
    return dict(
        userStatus=get_user_status(),
        username=get_username(),
        beian=beian,
    )


base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@app.route('/login', methods=['POST', 'GET'])
def login():
    if 'logged_in' in session:
        return redirect(url_for('home'))
    else:
        return zy_login()


# 注册页面
@app.route('/register', methods=['GET', 'POST'])
def register():
    ip = get_client_ip(request, session)
    return zy_register(ip)


# 登出页面
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/search', methods=['GET', 'POST'])
def search():
    if 'logged_in' not in session:
        return render_template('Login.html', error='登陆后可以使用此功能')
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
def space():
    avatar_url = get_avatar() or domain + 'static/favicon.ico'
    userStatus = get_user_status()
    username = get_username()
    owner_articles = None

    if userStatus and username is not None:
        owner_name = request.args.get('id')
        if owner_name is None or owner_name == '':
            owner_name = username
        owner_articles = get_owner_articles(owner_name)

    if owner_articles is None:
        owner_articles = []  # 设置为空列表

    if 'default' in owner_articles:
        owner_articles.remove('default')

    notiHost, notiPort = zy_noti_conf()

    return render_template('Profile.html', url_for=url_for, avatar_url=avatar_url,
                           userStatus=userStatus, username=username,
                           Articles=owner_articles, notiHost=notiHost)


@app.route('/setting/profiles', methods=['GET', 'POST'])
def setting_profiles():
    avatar_url = get_avatar() or domain + 'static/favicon.ico'
    userStatus = get_user_status()
    username = get_username()

    return render_template('setting.html', url_for=url_for, avatar_url=avatar_url,
                           userStatus=userStatus, username=username)


@app.route('/settingRegion', methods=['POST'])
def setting_region():
    username = get_username()
    if username is not None:
        return 1
    return 1


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
        return error("未知错误", 500)
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
            resp.headers['Cache-Control'] = 'public, max-age=240'  # 缓存为4分钟
            return resp

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

        # 获取用户名
        username = session.get('username')
        app.logger.info(f'当前访问的用户: {username}, IP: {ip}')

        # 渲染模板并存储渲染后的页面内容到缓存中
        rendered_content = template.render(
            title=title, articles_time_list=articles_time_list, url_for=url_for,
            notice=notice, has_next_page=has_next_page, has_previous_page=has_previous_page,
            current_page=page, tags=tags, tag=tag
        )
        # 缓存渲染后的页面内容，并设置服务端缓存过期时间
        cache.set(cache_key, rendered_content, timeout=60)
        resp = make_response(rendered_content)

        if username is None:
            username = 'qks' + format(random.randint(10000, 99999))
            app.logger.warning('未找到用户名，生成随机用户名: %s', username)
            session['username'] = username

        resp.set_cookie('key', 'zyBLOG' + username, 7200)
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


@app.route('/blog', methods=['GET', 'POST'])
def blog_page():
    return redirect(url_for('login'))


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

    # Check if cache file exists and is within one hour
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
def confirm_password():
    return zy_confirm_password()


@app.route('/change-password', methods=['GET', 'POST'])
def change_password():
    ip = get_client_ip(request, session)
    return zy_change_password(ip)


@app.route('/admin/<key>', methods=['GET', 'POST'])
def admin(key=''):
    method = 'GET'
    if request.method == 'POST':
        method = 'POST'
    return zyadmin(key, method)


@app.route('/admin/changeTheme', methods=['POST'])
def change_display():
    theme_id = request.args.get('NT')
    if session.get('logged_in') and theme_id:
        username = session.get('username')
        if username:
            db = get_database_connection()
            cursor = db.cursor()
            try:
                query = "SELECT `role` FROM users WHERE username = %s"
                cursor.execute(query, (username,))
                ifAdmin = cursor.fetchone()[0]
                if ifAdmin == 'Admin':
                    theme_path = f'templates/theme/{theme_id}'

                    if os.path.exists(theme_path):
                        has_index_html = os.path.exists(os.path.join(theme_path, 'index.html'))
                        has_screenshot_png = os.path.exists(os.path.join(theme_path, 'screenshot.png'))
                        has_template_ini = os.path.exists(os.path.join(theme_path, 'template.ini'))

                        if has_index_html and has_screenshot_png and has_template_ini:
                            print("update")

                            if theme_id == 1:
                                return 'success'
                            else:
                                return 'failed'
                        else:
                            return 'failed'
                    return 'failed'
                else:
                    return error("非管理员用户禁止访问！！！", 403)
            except Exception as e:
                logging.error(f"Error logging in: {e}")
                return error("未知错误", 500)
            finally:
                cursor.close()
                db.close()
        else:
            return error("请先登录", 401)
    else:
        return error("请先登录", 401)


last_newArticle_time = {}  # 全局变量，用于记录用户最后递交时间
app.config['UPLOAD_FOLDER'] = 'temp/upload'
authorMapper = configparser.ConfigParser()


@app.route('/newArticle', methods=['GET', 'POST'])
def new_article():
    if request.method == 'GET':
        username = session.get('username')
        if username in last_newArticle_time:
            last_time = last_newArticle_time[username]
            current_time = time.time()
            if current_time - last_time < 600:
                return error('您完成了一次服务（无论成功与否），此服务短期内将变得不可达，请你10分钟之后再来', 503)
        return zy_new_article()

    elif request.method == 'POST':
        username = session.get('username')
        if username in last_newArticle_time:
            last_time = last_newArticle_time[username]
            current_time = time.time()
            if current_time - last_time < 600:
                return error('距离你上次上传时间过短，请十分钟后重试', 503)

        # 更新用户最后递交时间
        last_newArticle_time[username] = time.time()
        file = request.files['file']
        if not file.filename.endswith('.md'):
            return error('Invalid file format. Only Markdown files are allowed.', 400)

        if file.content_length > 10 * 1024 * 1024:
            return error('Invalid file', 400)
        else:
            if file:
                # 保存上传的文件到指定路径
                upload_folder = os.path.join('temp/upload')
                os.makedirs(upload_folder, exist_ok=True)
                file_path = os.path.join(upload_folder, file.filename)
                file.save(file_path)

                # 检查文件是否存在于articles文件夹下
                if os.path.isfile(os.path.join('articles', file.filename)):
                    # 如果文件已经存在，提示上传失败
                    message = '上传失败，文件已存在。'
                else:
                    # 如果文件不存在，将文件复制到articles文件夹下，并提示上传成功
                    shutil.copy(os.path.join(app.config['UPLOAD_FOLDER'], file.filename), 'articles')
                    file_name = os.path.splitext(file.filename)[0]  # 获取文件名（不包含后缀）

                    author_value = session.get('username')
                    # 更新 [author]
                    set_article_author(file_name, author_value)

                    message = '上传成功。但请你检查错误以及编辑'

                return render_template('postNewArticle.html', message=message)

            else:
                return redirect('/newArticle')


def set_article_author(title, username):
    db = get_database_connection()

    try:
        with db.cursor() as cursor:
            query = "SELECT * FROM articles WHERE Title = %s"
            cursor.execute(query, (title,))
            result = cursor.fetchone()

            if result:
                # Update the author
                update_query = "UPDATE articles SET Author = %s WHERE Title = %s"
                cursor.execute(update_query, (username, title))
            else:
                # Create a new record
                insert_query = "INSERT INTO articles (Title, Author) VALUES (%s, %s)"
                cursor.execute(insert_query, (title, username))
            db.commit()
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        try:
            cursor.close()
        except NameError:
            pass
        db.close()


@app.route('/Admin_upload', methods=['GET', 'POST'])
def upload_file1():
    if 'username' not in session:
        return redirect(url_for('login'))
    username = session['username']
    ip = session['public_ip']
    app.logger.info('当前访问的用户:{}, IP:{}'.format(username, ip))
    if username:
        db = get_database_connection()
        cursor = db.cursor()
        try:
            query = "SELECT `role` FROM users WHERE username = %s"
            cursor.execute(query, (username,))
            ifAdmin = cursor.fetchone()[0]
            if ifAdmin == 'Admin':
                return zy_upload_file()
        finally:
            cursor.close()
            db.close()
    return False


@app.route('/delete/<filename>', methods=['POST'])
def delete_file(filename):
    userStatus = get_user_status()
    username = get_username()
    auth = False  # 设置默认值

    if userStatus and username is not None:
        article = filename
        # Auth 认证
        auth = auth_articles(article, username)

    if auth:

        return zy_delete_file(filename)

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
    # notice = read_file('notice/1.txt', 50)
    userStatus = get_user_status()
    username = get_username()
    auth = False  # 设置默认值

    if userStatus and username is not None:
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

    userStatus = get_user_status()
    username = get_username()

    if userStatus is None or username is None:
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

    userStatus = get_user_status()
    username = get_username()

    if userStatus is None or username is None:
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
    userStatus = get_user_status()
    username = get_username()

    if userStatus and username is not None:
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
def upload_user_path():
    userStatus = get_user_status()
    username = get_username()

    if userStatus and username is not None:
        if request.method == 'POST':
            try:
                for f in request.files.getlist('file'):
                    if f.filename.lower().endswith(
                            ('.jpg', '.png', '.webp', '.jfif', '.pjpeg', '.jpeg', '.pjp', '.mp4', '.xmind')):
                        if f.content_length > 60 * 1024 * 1024:
                            return 'File size exceeds the limit of 60MB'
                        else:
                            f.save(os.path.join(app.config['UPLOADED_PATH'], f'{username}', f.filename))

                return 'success'

            except Exception as e:
                print(f"Error in getting image path: {e}")
                return 'failed'
    else:
        return 'failed'


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

    api_safeCheck = [api_host, app_id, app_key]
    if 'error' in api_safeCheck:
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

    # Replace with your app's credentials

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
    if os.path.exists(f'templates/theme/{theme_id}'):
        theme_detail = configparser.ConfigParser()
        # 读取 template.ini 文件
        theme_detail.read(f'templates/theme/{theme_id}/template.ini', encoding=global_encoding)
        # 获取配置文件中的属性值
        tid = theme_detail.get('default', 'id').strip("'")
        author = theme_detail.get('default', 'author').strip("'")
        theme_title = theme_detail.get('default', 'title').strip("'")
        author_website = theme_detail.get('default', 'authorWebsite').strip("'")
        version = theme_detail.get('default', 'version').strip("'")
        version_code = theme_detail.get('default', 'versionCode').strip("'")
        update_url = theme_detail.get('default', 'updateUrl').strip("'")
        screenshot = theme_detail.get('default', 'screenshot').strip("'")

        theme_properties = {
            'id': tid,
            'author': author,
            'title': theme_title,
            'authorWebsite': author_website,
            'version': version,
            'versionCode': version_code,
            'updateUrl': update_url,
            'screenshot': screenshot,
        }

        return jsonify(theme_properties)


@app.route('/theme/<theme_id>/<img_name>')
def get_screenshot(theme_id, img_name):
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
            visitID = version + format(random.randint(10000, 99999))  # 可以设置一个默认值或者抛出异常，具体根据需求进行处理
            resp.set_cookie('visitID', 'zyBLOG' + visitID, 7200)
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
        return error(message='服务器内部错误', status_code=500)
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
def sys_out_prev_page():
    user = request.args.get('user')
    file_name = request.args.get('file_name')
    prev_file_path = os.path.join(base_dir, 'media', str(user), file_name)
    if not os.path.exists(prev_file_path):
        return render_template('error.html', message=f'{file_name}不存在', status_code=404)
    else:
        return render_template('zyDetail.html', title=title, article_content=1,
                               articleName=f"tempPrev_{file_name}", domain=domain,
                               url_for=url_for, article_Surl='-')


@app.route('/api/wx', methods=['GET'])
def wx_api():
    page = request.args.get('page')
    if page:
        return "helloworld"
    else:
        return "404 Not found"


@app.route('/test')
def test():
    session['data'] = 'Some Data from App 1'
    return 'session shared running'


@app.errorhandler(404)
def page_not_found(error_message):
    app.logger.error(error_message)
    return "Page not found", 404


@app.errorhandler(500)
def internal_server_error(error_message):
    app.logger.error(error_message)
    return "Internal server error", 500


@app.route('/<path:undefined_path>')
def undefined_route(undefined_path):
    app.logger.error(undefined_path)
    return render_template('error.html', status_code='404'), 404


@app.errorhandler(Exception)
def handle_unexpected_error(error_message):
    app.logger.error(error_message)
    return "An unexpected error occurred", 500
