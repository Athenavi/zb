import base64
import configparser
import csv
import datetime
import io
import json
import logging
import os
import random
import re
import shutil
import time
import urllib
import xml.etree.ElementTree as ET
from configparser import ConfigParser
import portalocker
import requests
from PIL import Image, ImageDraw, ImageFont
from flask import Flask, render_template, redirect, session, request, url_for, Response, jsonify, send_file, \
    make_response, send_from_directory
from flask_caching import Cache
from jinja2 import Environment, select_autoescape, FileSystemLoader
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import safe_join

from src.AboutLogin import zy_login, zy_register, get_email, profile, zy_mail_login
from src.AboutPW import zy_change_password, zy_confirm_password
from src.BlogDeal import get_article_names, get_article_content, clear_html_format, \
    get_file_date, get_blog_author, generate_random_text, read_hidden_articles, zy_send_message, auth_articles, \
    zy_show_article, zy_edit_article, get_all_article_names
from src.database import get_database_connection
from src.user import zyadmin, zy_delete_file, zy_new_article, error, get_owner_articles
from src.utils import zy_upload_file, get_user_status, get_username, get_client_ip, read_file, \
    zy_save_edit
from src.links import create_special_url

global_encoding = 'utf-8'
template_dir = 'templates'  # 模板文件的目录
loader = FileSystemLoader(template_dir)
env = Environment(loader=loader, autoescape=select_autoescape(['html', 'xml']))
env.add_extension('jinja2.ext.loopcontrols')

app = Flask(__name__, static_folder="../static")
app.config['CACHE_TYPE'] = 'simple'
cache = Cache(app)
app.jinja_env = env
app.secret_key = 'your_secret_key'
app.permanent_session_lifetime = datetime.timedelta(hours=3)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1)  # 添加 ProxyFix 中间件

# 移除默认的日志处理程序
app.logger.handlers = []

# 新增日志处理程序
log_formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
file_handler = logging.FileHandler('temp/app.log', encoding=global_encoding)
file_handler.setFormatter(log_formatter)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)

config = ConfigParser()
try:
    config.read('config.ini', encoding='utf-8')
except UnicodeDecodeError:
    config.read('config.ini', encoding='gbk')
# 应用分享配置参数
from datetime import datetime, timedelta


@app.context_processor
def inject_variables():
    return dict(
        userStatus=get_user_status(),
        username=get_username(),
    )


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


try:
    domain = config.get('general', 'domain').strip("'")
    title = config.get('general', 'title').strip("'")
    display = config.get('general', 'theme').strip("'")
except (configparser.NoSectionError, configparser.NoOptionError):
    domain = '127.0.0.1'
    title = '您的配置文件出现问题！！！'
    display = 'default'

theme_display = configparser.ConfigParser()
CopyRight = 'Powered by zyBLOG'

# 读取template.ini文件
if display != 'default':
    # 读取 template.ini 文件
    theme_display.read(f'templates/theme/{display}/template.ini', encoding=global_encoding)
    # 获取配置文件中的属性值
    CopyRight = ' Theme Author:' + theme_display.get('default', 'author').strip("'")


@app.route('/toggle_theme', methods=['POST'])  # 处理切换主题的请求
def toggle_theme():
    if session['theme'] == 'day-theme':
        session['theme'] = 'night-theme'  # 如果当前主题为白天，则切换为夜晚（night-theme）
    else:
        session['theme'] = 'day-theme'  # 如果当前主题为夜晚，则切换为白天（day-theme）

    return 'success'  # 返回切换成功的消息


@app.route('/search', methods=['GET', 'POST'])
def search():
    if 'username' not in session:
        return render_template('zylogin.html', error='登陆后可以使用此功能')
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
            root = ET.Element('root')

            for file in markdown_files:
                article_name = file[:-3]  # 移除文件扩展名 (.md)
                encoded_article_name = urllib.parse.quote(article_name)  # 对文件名进行编码处理
                article_url = domain + 'blog/' + encoded_article_name
                date = get_file_date(encoded_article_name)
                describe = get_article_content(article_name, 50)  # 建议的值50以内
                describe = clear_html_format(describe)

                if keyword.lower() in article_name.lower() or keyword.lower() in describe.lower():
                    # 创建item元素并包含内容
                    item = ET.SubElement(root, 'item')
                    ET.SubElement(item, 'title').text = article_name
                    ET.SubElement(item, 'link').text = article_url
                    ET.SubElement(item, 'pubDate').text = date
                    ET.SubElement(item, 'description').text = describe

            # 创建XML树
            tree = ET.ElementTree(root)

            # 将XML数据转换为字符串
            match_data = ET.tostring(tree.getroot(), encoding=global_encoding, method='xml').decode()

            # 写入缓存
            with open(cache_path, 'w') as cache_file:
                cache_file.write(match_data)

        # 解析XML数据
        parsed_data = ET.fromstring(match_data)
        for item in parsed_data.findall('item'):
            content = {
                'title': item.find('title').text,
                'link': item.find('link').text,
                'pubDate': item.find('pubDate').text,
                'description': item.find('description').text
            }
            matched_content.append(content)

    return render_template('search.html', results=matched_content)


def analyze_ip_location(ip_address):
    # 使用IP地址作为缓存的键
    if ip_address in session:
        return session[ip_address]

    try:
        ip_api_url = f'http://whois.pconline.com.cn/ipJson.jsp?ip={ip_address}&json=true'
        response = requests.get(ip_api_url, timeout=3)  # 设置超时时间为3秒
        data = response.json()

        city_name = data.get('city', '未知')
        city_code = data.get('cityCode', '未知')

        # 如果API没有返回城市名称或代码，则赋值为“未知”
        if not city_name:
            city_name = '未知'
        if not city_code:
            city_code = '未知'

    except (requests.exceptions.Timeout, requests.exceptions.ProxyError):
        # 处理超时和代理错误，将城市名称和代码设为“未知”
        city_name = '接口异常'
        city_code = '接口异常'

    # 将结果缓存，避免重复查询
    session[ip_address] = (city_name, city_code)

    return city_name, city_code


def check_exist(cache_file):
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
            cache_timestamp = datetime.fromtimestamp(os.path.getmtime(cache_file))
            if datetime.now() - cache_timestamp <= timedelta(hours=1):
                return jsonify(cache_data)


@app.route('/api/weather/<city_code>', methods=['GET', 'POST'])
def get_weather(city_code):
    cache_dir = 'temp'
    os.makedirs(cache_dir, exist_ok=True)

    cache_file = os.path.join(cache_dir, f'{city_code}.json')

    # Check if cache file exists and is within one hour
    check_exist(cache_file)

    # Acquire a lock before generating cache file
    lock_file = f'{cache_file}.lock'
    try:
        with portalocker.Lock(lock_file, timeout=1):
            # Check again if cache file is created by another request
            check_exist(cache_file)
            apiUrl = f'http://t.weather.itboy.net/api/weather/city/{city_code}'
            try:
                response = requests.get(apiUrl)
                processedData = response.json()

                with open(cache_file, 'w') as f:
                    json.dump(processedData, f)

                return jsonify(processedData)
            except Exception as e:
                error_message = {'error': str(e)}
                return jsonify(error_message), 500
    except portalocker.exceptions.LockException:
        # Another request is already creating the cache file
        pass

    # If cache file creation failed, return error
    error_message = {'error': 'Failed to create cache file'}
    return jsonify(error_message), 500


@app.route('/api/get_city_code', methods=['GET', 'POST'])
def get_city_code():
    city_name = request.args.get('city_name')
    city_name = clear_html_format(city_name)
    return zy_get_city_code(city_name)


@app.route('/blog/<any>/api/<articleName>', methods=['GET', 'POST'])
@app.route('/blog/api/<articleName>', methods=['GET', 'POST'])
@app.route('/api/<articleName>', methods=['GET', 'POST'])
def sys_out_file(articleName):
    # 隐藏文章判别
    hidden_articles = read_hidden_articles()
    if articleName[:-3] in hidden_articles:
        # 隐藏的文章
        return zy_pw_blog(articleName[:-3])
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        articles_dir = os.path.join(base_dir, 'articles')
        return send_from_directory(articles_dir, articleName)
    except Exception as e:
        return "An internal error occurred", 500


@app.route('/profile', methods=['GET', 'POST'])
def space():
    avatar_url = profile('guest@7trees.cn')
    template = env.get_template('zyprofile.html')
    session.setdefault('theme', 'day-theme')
    notice = read_file('notice/1.txt', 50)
    userStatus = get_user_status()
    username = get_username()
    ownerArticles = None

    if userStatus and username is not None:
        ownerName = request.args.get('id')
        if ownerName is None or ownerName == '':
            ownerName = username
        ownerArticles = get_owner_articles(ownerName)
        avatar_url = get_email(ownerName)
        avatar_url = profile(avatar_url)
        if 'faceimg' in session:
            avatar_url = session['faceimg']
    if ownerArticles is None:
        ownerArticles = []  # 设置为空列表

    return template.render(url_for=url_for, theme=session['theme'],
                           notice=notice, avatar_url=avatar_url,
                           userStatus=userStatus, username=username,
                           Articles=ownerArticles)


@app.route('/settingRegion', methods=['POST'])
def setting_region():
    username = get_username()
    if username is not None:
        return 1
    return 1


@cache.cached(timeout=None, key_prefix='cities')
def get_table_data():
    db = get_database_connection()

    cursor = db.cursor()
    # 执行 MySQL 查询获取你想要缓存的表数据
    query = "SELECT * FROM cities"
    cursor.execute(query)

    # 构建数据字典列表
    data = []
    columns = [desc[0] for desc in cursor.description]
    for row in cursor.fetchall():
        data.append(dict(zip(columns, row)))

    cursor.close()
    db.close()

    return data


def zy_get_city_code(city_name):
    table_data = get_table_data()

    # 在缓存的数据中查询城市代码
    result = next((item for item in table_data if item['city_name'] == city_name), None)

    # 检查查询结果
    if result:
        return jsonify({'city_code': result['city_code']})
    else:
        return jsonify({'error': '城市不存在'})


def get_unique_tags(csv_filename):
    tags = []
    with open(csv_filename, 'r', encoding=global_encoding) as file:
        reader = csv.reader(file)
        next(reader)  # Skip the header line
        for row in reader:
            tags.extend(row[1:])  # Append tags from the row (excluding the article name)

    unique_tags = list(set(tags))  # Remove duplicates
    return unique_tags


def get_articles_by_tag(csv_filename, tag_name):
    tag_articles = []
    with open(csv_filename, 'r', encoding=global_encoding) as file:
        reader = csv.reader(file)
        next(reader)  # Skip the header line
        for row in reader:
            if tag_name in row[1:]:
                tag_articles.append(row[0])  # Append the article name

    return tag_articles


def get_tags_by_article(csv_filename, article_name):
    tags = []
    with open(csv_filename, 'r', encoding=global_encoding) as file:
        reader = csv.reader(file)
        next(reader)  # Skip the header line
        for row in reader:
            if row[0] == article_name:
                tags.extend(row[1:])  # Append tags from the row (excluding the article name)
                break  # Break the loop if the article is found

    unique_tags = list(set(tags))  # Remove duplicates
    unique_tags = [tag for tag in unique_tags if tag]  # Remove empty tags
    return unique_tags


def get_list_intersection(list1, list2):
    intersection = list(set(list1) & set(list2))
    return intersection


# 主页

@app.route('/', methods=['GET', 'POST'])
def home():
    # 获取客户端IP地址
    ip = get_client_ip(request, session)
    city_name, city_code = analyze_ip_location(ip)

    if request.method == 'GET':
        page = request.args.get('page', default=1, type=int)
        tag = request.args.get('tag')

        if page <= 0:
            page = 1

        if 'theme' not in session:
            session['theme'] = 'day-theme'  # 设置默认主题
        theme = session.get('theme')
        cache_key = f'page_content:{page}:{theme}:{tag}'  # 根据页面值、主题以及标签生成缓存键

        # 尝试从缓存中获取页面内容
        content = cache.get(cache_key)
        if content:
            # 设置浏览器缓存
            resp = make_response(content)
            resp.headers['Cache-Control'] = 'public, max-age=600'  # 缓存为10分钟
            return resp

        # 重新获取页面内容
        articles, has_next_page, has_previous_page = get_article_names(page=page)

        # 模版配置
        template = env.get_template('zyhome.html')
        display = session.get('display', 'default')
        template_path = f'templates/theme/{display}/index.html'
        if os.path.exists(template_path):
            template = env.get_template(f'theme/{display}/index.html')

        notice = ''
        try:
            notice = read_file('notice/1.txt', 50)
        except Exception as e:
            app.logger.error(f'读取通知文件出错: {e}')

        tags = []
        try:
            tags = get_unique_tags('articles/tags.csv')
        except Exception as e:
            app.logger.error(f'获取标签出错: {e}')

        if tag:
            tag_articles = get_articles_by_tag('articles/tags.csv', tag)
            articles = get_list_intersection(articles, tag_articles)

        # 获取用户名
        username = session.get('username')
        app.logger.info(f'当前访问的用户: {username}, IP: {ip}, IP归属地: {city_name}, 城市代码: {city_code}')

        # 渲染模板并存储渲染后的页面内容到缓存中
        rendered_content = template.render(
            title=title, articles=articles, url_for=url_for, theme=theme,
            notice=notice, has_next_page=has_next_page, has_previous_page=has_previous_page,
            current_page=page, tags=tags, CopyRight='Your CopyRight'
        )
        # 缓存渲染后的页面内容，并设置服务端缓存过期时间
        cache.set(cache_key, rendered_content, timeout=300)
        resp = make_response(rendered_content)

        if username is None:
            username = 'qks' + format(random.randint(10000, 99999))
            app.logger.warning('未找到用户名，生成随机用户名: %s', username)
            session['username'] = username

        resp.set_cookie('key', 'zyBLOG' + username, 7200)
        return resp

    else:
        return render_template('zyhome.html')


@app.route('/blog/discord/README.md', methods=['GET', 'POST'])
def discord_R():
    return """
    社区讨论条约

尊重他人意见：在社区讨论中，大家都有权利发表自己的观点，但请避免恶意攻击或侮辱他人。请尊重他人的意见和观点，保持开放、友善的讨论环境。

文明交流：在讨论过程中，请尽量使用文明、礼貌的语言，避免使用粗鲁或攻击性言辞。保持冷静，理性讨论，不要轻易引发争议。

尊重知识产权：在引用他人观点或资料时，请注明出处，并尊重他人的知识产权。禁止抄袭和侵犯他人版权。

禁止谩骂和人身攻击：严禁在讨论中使用谩骂、人身攻击等不当言论，保持理性、平和的态度，避免情绪化的讨论。

尊重社区规则：遵守社区规定，不发表违反法律法规和社区规定的言论，保持社区秩序和正常运转。

尊重他人隐私：在讨论中，不要公开或泄露他人的个人信息，尊重他人的隐私权。

以上是社区讨论的基本条约，希望大家共同遵守，保持社区和谐与发展。

<button id="show_comments" onclick="showComments()">开启评论区</button>
* 参与讨论表示同意上述观点
"""


@cache.memoize(30)
def get_a_list():
    return get_all_article_names()


@app.route('/blog/<article>', methods=['GET', 'POST'])
@app.route('/blog/<article>.html', methods=['GET', 'POST'])
def blog_detail(article):
    try:
        # 根据文章名称获取相应的内容并处理
        article_name = article
        article_names = get_a_list()
        # print(article_names)
        hidden_articles = read_hidden_articles()

        if article_name in hidden_articles:
            # 隐藏的文章
            return zy_pw_blog(article_name)

        if article_name not in article_names:
            return render_template('error.html', status_code='404'), 404

        article_tags = get_tags_by_article('articles/tags.csv', article_name)
        article_url = domain + 'blog/' + article_name
        article_Surl = api_shortlink(article_url)
        # print(article_Surl)
        author = get_blog_author(article_name)
        blogDate = get_file_date(article_name)
        theme = session.get('theme', 'day-theme')  # 获取当前主题

        response = make_response(render_template('zyDetail.html', title=title, article_content=1,
                                                 articleName=article_name, theme=theme,
                                                 author=author, blogDate=blogDate,
                                                 url_for=url_for, article_Surl=article_Surl, article_tags=article_tags))

        # 设置服务器端缓存时间
        response.cache_control.max_age = 180
        response.expires = datetime.utcnow() + timedelta(seconds=300)

        # 设置浏览器端缓存时间
        response.headers['Cache-Control'] = 'public, max-age=300'

        return response

    except FileNotFoundError:
        return render_template('error.html', status_code='404'), 404


"""
last_comment_time = {}  # 全局变量，用于记录用户最后评论时间

@app.route('/post_comment', methods=['POST'])
def post_comment():
    article_name = request.form.get('article_name')
    username = request.form.get('username')
    comment = request.form.get('comment')

    # 在处理评论前检查用户评论时间
    if username in last_comment_time:
        last_time = last_comment_time[username]
        current_time = time.time()
        if current_time - last_time < 10:
            response = {
                'result': 'error',
                'message': '请稍后再发表评论'
            }
            return json.dumps(response)

    # 更新用户最后评论时间
    last_comment_time[username] = time.time()

    # 处理评论逻辑
    result = zy_post_comment(article_name, username, comment)

    # 构建响应JSON对象
    response = {
        'result': result,
        'username': username,
        'comment': comment
    }

    return json.dumps(response)
"""


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
        article_Surl = api_shortlink(article_url)
        # 创建url标签并包含链接
        xml_data += '<url>\n'
        xml_data += f'\t<loc>{article_Surl}</loc>\n'
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

    # Check if cache file exists and is within one hour
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
    markdown_files = markdown_files[:10]

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

        article_Surl = api_shortlink(article_url)
        # 创建item标签并包含内容
        xml_data += '<item>\n'
        xml_data += f'\t<title>{article_name}</title>\n'
        xml_data += f'\t<link>{article_Surl}</link>\n'
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
def admin(key):
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
                query = "SELECT ifAdmin FROM users WHERE username = %s"
                cursor.execute(query, (username,))
                ifAdmin = cursor.fetchone()[0]
                if ifAdmin:
                    theme_path = f'templates/theme/{theme_id}'

                    if os.path.exists(theme_path):
                        has_index_html = os.path.exists(os.path.join(theme_path, 'index.html'))
                        has_screenshot_png = os.path.exists(os.path.join(theme_path, 'screenshot.png'))
                        has_template_ini = os.path.exists(os.path.join(theme_path, 'template.ini'))

                        if has_index_html and has_screenshot_png and has_template_ini:
                            currentTheme = config.get('general', 'theme').strip("'")

                            if theme_id == currentTheme:
                                return 'success'
                            else:
                                # Modify the value of 'theme' in config_example.ini
                                config.set('general', 'theme', f"'{theme_id}'")
                                with open('config_example.ini', 'w') as config_file:
                                    config.write(config_file)

                                currentTheme = config.get('general', 'theme').strip("'")

                                if theme_id == currentTheme:
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
                    with open('articles/hidden.txt', 'a', encoding=global_encoding) as f:
                        f.write('\n' + file_name + '\n')
                    authorMapper.read('author/mapper.ini', encoding=global_encoding)
                    author_value = session.get('username')
                    # 更新 [author] 节中的键值对
                    authorMapper.set('author', file_name, f"'{author_value}'")

                    # 将更改保存到文件
                    with open('author/mapper.ini', 'w', encoding=global_encoding) as configfile:
                        authorMapper.write(configfile)

                    message = '上传成功。但目前处于隐藏状态，以便于你检查错误以及编辑'

                return render_template('postNewArticle.html', message=message)

            else:
                return redirect('/newArticle')


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
            query = "SELECT ifAdmin FROM users WHERE username = %s"
            cursor.execute(query, (username,))
            ifAdmin = cursor.fetchone()[0]
            if ifAdmin:
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


@app.route('/robots.txt')
def static_from_root():
    content = "User-agent: *\nDisallow: /admin"
    modified_content = content + '\nSitemap: ' + domain + 'sitemap.xml'  # Add your additional rule here

    response = Response(modified_content, mimetype='text/plain')
    return response


@app.route('/<path:undefined_path>')
def undefined_route():
    return render_template('error.html', status_code='404'), 404


# ...

@app.route('/generate_captcha')
def generate_captcha():
    image_base64 = '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'
    captcha_text = '8er2'
    if 'logged_in' not in session:
        return {'image': image_base64, 'captcha_text': captcha_text}
    # 生成验证码文本
    captcha_text = generate_random_text()

    # 创建一个新的图像对象
    image = Image.new('RGB', (135, 80), color=(255, 255, 255))

    # 创建字体对象并设置字体大小
    font = ImageFont.truetype('static/font/babyground.ttf', size=40)

    # 在图像上绘制验证码文本
    d = ImageDraw.Draw(image)
    d.text((35, 20), captcha_text, font=font, fill=(0, 0, 0))

    # 将图像转换为 RGBA 模式
    image = image.convert('RGBA')
    data = image.getdata()

    # 修改图像像素，将白色像素变为透明
    theme = session.get('theme', 'day-theme')
    if theme == 'night-theme':
        new_data = data
    else:
        new_data = [(255, 255, 255, 0) if item[:3] == (255, 255, 255) else item for item in data]

    # 更新图像数据
    image.putdata(new_data)

    # 保存图像到内存中
    image_bytes = io.BytesIO()
    image.save(image_bytes, format='PNG')
    image_bytes.seek(0)

    # 将图像转换为 base64 编码字符串
    image_base64 = base64.b64encode(image_bytes.getvalue()).decode('ascii')

    # 将验证码文本存储在 session 中，用于校对
    session['captcha_text'] = captcha_text
    # print(captcha_text)
    # 返回图像的 base64 编码给用户
    return {'image': image_base64, 'captcha_text': captcha_text}


@app.route('/verify_captcha', methods=['POST'])
def verify_captcha():
    # 获取前端传来的验证码值
    user_input = request.form.get('captcha')
    user_input = clear_html_format(user_input)

    # 获取存储在session中的验证码文本
    captcha_text = session['captcha_text']

    if user_input.lower() == captcha_text.lower():
        # 验证码匹配成功，执行相应逻辑
        return '验证码匹配成功'
    else:
        # 验证码匹配失败，执行相应逻辑
        return '验证码不匹配'


@app.route('/send_message', methods=['POST'])
def send_message(message):
    zy_send_message(message)
    return '1'


@app.route('/edit/<article>', methods=['GET', 'POST', 'PUT'])
def markdown_editor(article):
    if 'theme' not in session:
        session['theme'] = 'day-theme'
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

            tags = get_tags_by_article("articles/tags.csv", article)

            # 渲染编辑页面并将转换后的HTML传递到模板中
            return render_template('editor.html', edit_html=edit_html, show_edit=show_edit, articleName=article,
                                   theme=session['theme'], tags=tags)
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
                tags_input = re.split(",{1}", tags_input, maxsplit=4)[0]

            # 限制每个标签最大字符数为10，并添加到标签列表

            for tag in tags_input.split(","):
                tag = tag.strip()
                if len(tag) <= 10:
                    tags_list.append(tag)

            # 读取标签文件，查找文章名是否存在
            exists = False
            with open('articles/tags.csv', 'r', encoding=global_encoding) as file:
                reader = csv.reader(file)
                rows = list(reader)
                for row in rows:
                    if row[0] == article:
                        row[1:] = tags_list  # 替换现有标签
                        exists = True
                        break

                # 文章名不存在，创建新行
                if not exists:
                    rows.append([article] + tags_list)

            # 写入更新后的标签文件
            with open('articles/tags.csv', 'w', encoding=global_encoding, newline='') as file:
                writer = csv.writer(file)
                writer.writerows(rows)
            return jsonify({'show_edit': "success"})

        else:
            # 渲染编辑页面
            return render_template('editor.html')

    else:
        return error(message='您没有权限', status_code=503)


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
def hideen_article():
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
        unhide_article(article)
        return jsonify({'deal': 'unhide'})
    else:
        # 隐藏文章
        hide_article(article)
        return jsonify({'deal': 'hide'})


def hide_article(article):
    with open('articles/hidden.txt', 'a', encoding=global_encoding) as hidden_file:
        # 将文章名写入hidden.txt的新的一行中
        hidden_file.write('\n' + article + '\n')


def unhide_article(article):
    with open('articles/hidden.txt', 'r', encoding=global_encoding) as hidden_file:
        hidden_articles = hidden_file.read().splitlines()

    with open('articles/hidden.txt', 'w', encoding=global_encoding) as hidden_file:
        # 从hidden中移除完全匹配文章名的一行
        for hidden_article in hidden_articles:
            if hidden_article != article:
                hidden_file.write(hidden_article + '\n')


def is_hidden(article):
    with open('articles/hidden.txt', 'r', encoding=global_encoding) as hidden_file:
        hidden_articles = hidden_file.read().splitlines()
        return article in hidden_articles


@app.route('/travel', methods=['GET'])
def travel():
    response = requests.get(domain + 'sitemap.xml')  # 发起对/sitemap接口的请求
    if response.status_code == 200:
        tree = ET.fromstring(response.content)  # 使用xml.etree.ElementTree解析响应内容

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


def zy_pw_blog(article_name):
    session.setdefault('theme', 'day-theme')
    if request.method == 'GET':
        # 在此处添加密码验证的逻辑
        codePass = zy_pw_check(article_name, request.args.get('password'))
        if codePass == 'success':
            try:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                articles_dir = os.path.join(base_dir, 'articles')
                return send_from_directory(articles_dir, article_name + '.md')
            except Exception as e:
                return "An internal error occurred", 500

    return render_template('zyDetail.html', articleName=article_name,
                           theme=session['theme'],
                           url_for=url_for)


def zy_pw_check(article, code):
    try:
        invitecodes = get_invitecode_data()  # 获取invitecode表数据

        for result in invitecodes:
            if result['uuid'] == article and result['code'] == code:
                app.logger.info('完成了一次数据表更新')
                return 'success'

        return 'failed'
    except:
        return 'failed'


@cache.cached(timeout=600, key_prefix='invitecode')
def get_invitecode_data():
    db = get_database_connection()

    cursor = db.cursor()
    # 执行 MySQL 查询获取你想要缓存的表数据
    query = "SELECT * FROM invitecode"
    cursor.execute(query)

    # 构建数据字典列表
    data = []
    columns = [desc[0] for desc in cursor.description]
    for row in cursor.fetchall():
        data.append(dict(zip(columns, row)))
    current_time = datetime.now()
    app.logger.info('当前数据表更新时间：{}'.format(current_time))
    cursor.close()
    db.close()

    return data


@app.route('/change-article-pw/<filename>', methods=['POST'])
def change_article_pw(filename):
    userStatus = get_user_status()
    username = get_username()
    auth = False  # 设置默认值

    if userStatus and username is not None:
        article = filename
        # Auth 认证
        auth = auth_articles(article, username)

    if auth:
        newCode = request.get_json()['NewPass']
        article = request.get_json()["Article"]
        if newCode == '': newCode = '0000'
        return zy_change_article_pw(article, newCode)

    else:
        return error(message='您没有权限', status_code=503)


def zy_change_article_pw(filename, new_pw='1234'):
    # Connect to the database
    db = get_database_connection()

    try:
        with db.cursor() as cursor:
            # Check if the uuid exists in the table
            query = "SELECT * FROM invitecode WHERE uuid = %s"
            cursor.execute(query, (filename,))
            result = cursor.fetchone()

            if result is not None:
                # Update the code value
                query = "UPDATE invitecode SET code = %s WHERE uuid = %s"
                cursor.execute(query, (new_pw, filename))
            else:
                # Insert a new row
                # Check if the length of newCode is not greater than 4
                if len(new_pw) > 4:
                    return "failed"

                query = "INSERT INTO invitecode (uuid, code, is_used) VALUES (%s, %s, 0)"
                cursor.execute(query, (filename, new_pw))

            # Commit the changes to the database
            db.commit()

            # Return success message
            return "success"

    except Exception:
        # Return failure message if any error occurs
        return "failed"

    finally:
        # Close the connection and cursor
        cursor.close()
        db.close()


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

                return render_template('zymedia.html', imgs=imgs, title='Media', url_for=url_for,
                                       theme=session.get('theme'), has_next_page=has_next_page,
                                       has_previous_page=has_previous_page, current_page=page, userid=username,
                                       domain=domain)
            if type == 'video':
                videos, has_next_page, has_previous_page = get_all_video(username, page=page)

                return render_template('zymedia.html', videos=videos, title='Media', url_for=url_for,
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


@app.route('/zyImg/<username>/<img_name>')
def get_image_path(username, img_name):
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        img_dir = os.path.join(base_dir, 'media', username, img_name)  # 修改为实际的图片目录相对路径

        # 从缓存中获取图像数据
        img_data = cache.get(img_dir)

        # 如果缓存中没有图像数据，则从文件中读取并进行缓存
        if img_data is None:
            with open(img_dir, 'rb') as f:
                img_data = f.read()
            cache.set(img_dir, img_data)

        return send_file(img_dir, mimetype='image/png')
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
                            ('.jpg', '.png', '.webp', '.jfif', '.pjpeg', '.jpeg', '.pjp', '.mp4')):
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
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        video_dir = os.path.join(base_dir, 'media', username)
        video_path = os.path.join(video_dir, video_name)

        return send_file(video_path, mimetype='video/mp4', as_attachment=False, conditional=True)
    except Exception as e:
        print(f"Error in getting video path: {e}")
        return None


@app.route('/jump', methods=['GET', 'POST'])
def jump():
    url = request.args.get('url', default=domain)
    return render_template('zyJump.html', url=url, domain=domain)


@app.route('/static/<path:filename>')
def serve_static(filename):
    parts = filename.split('/')
    directory = safe_join('/'.join(parts[:-1]))
    file = parts[-1]
    return send_from_directory(directory, file)


# 彩虹聚合登录
api_host = config.get('general', 'api_host').strip("'")
app_id = config.get('general', 'app_id').strip("'")
app_key = config.get('general', 'app_key').strip("'")


@app.route('/login/<provider>')
def cc_login(provider):
    if provider not in ['qq', 'wx', 'alipay', 'sina', 'baidu', 'huawei', 'xiaomi', 'dingtalk']:
        return jsonify({'message': 'Invalid login provider'})

    redirect_uri = domain + "callback/" + provider

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
    global user_email
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
        face_img = get_user_info(provider, social_uid)
        return zy_mail_login(user_email, ip)

    return render_template('zylogin.html', error=msg)


def get_user_info(provider, social_uid):
    apiURl = f'{api_host}connect.php?act=query&appid={app_id}&appkey={app_key}&type={provider}&social_uid={social_uid}'
    response = requests.get(apiURl)
    data = response.json()
    code = data.get('code')
    faceimg = None
    if code == 0:
        faceimg = data.get('faceimg')
        session['faceimg'] = faceimg
    return faceimg


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
        authorWebsite = theme_detail.get('default', 'authorWebsite').strip("'")
        version = theme_detail.get('default', 'version').strip("'")
        versionCode = theme_detail.get('default', 'versionCode').strip("'")
        updateUrl = theme_detail.get('default', 'updateUrl').strip("'")
        screenshot = theme_detail.get('default', 'screenshot').strip("'")

        theme_properties = {
            'id': tid,
            'author': author,
            'title': theme_title,
            'authorWebsite': authorWebsite,
            'version': version,
            'versionCode': versionCode,
            'updateUrl': updateUrl,
            'screenshot': screenshot,
        }

        return jsonify(theme_properties)


@app.route('/theme/<theme_id>/<img_name>')
def get_screenshot(theme_id, img_name):
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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


"""
@app.route('/<page>', methods=['GET', 'POST'])
def diy_space(page):
    if ContractedAuthor(page) is True:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_path = os.path.join(base_dir, 'media', page, 'index.html')
        print(template_path)
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding=global_encoding) as file:
                html_content = file.read()
                resp = make_response(html_content)
                username = 'qks' + format(random.randint(1000, 9999))  # 可以设置一个默认值或者抛出异常，具体根据需求进行处理
                resp.set_cookie('key', 'zyBLOG' + username, 7200)
            return resp
    return render_template('error.html')
"""


def Gen_TempAuthPW():
    tempAuthPW = generate_random_text()  # 生成随机文本的函数，需要提供实现
    session['upload_pw'] = tempAuthPW
    session['upload_pw_time'] = datetime.now().timestamp()
    print(tempAuthPW)
    app.logger.info('更新上传密码:{}'.format(tempAuthPW))


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

        # 记录响应次数和第一次响应时间到opentimes表
        insert_query = "INSERT INTO opentimes (short_url, response_count, first_response_time) VALUES (%s, %s, %s) " \
                       "ON DUPLICATE KEY UPDATE response_count = response_count + 1"
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(insert_query, (short_url, 1, current_time))
        db.commit()

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
    article_Surl = domain + 's/' + short_url
    return article_Surl


@cache.cached(timeout=1200)
def get_link_info(username):
    db = get_database_connection()
    cursor = db.cursor()

    # 查询用户是否为管理员
    query_admin = "SELECT ifAdmin FROM users WHERE username = %s"
    cursor.execute(query_admin, (username,))
    admin_result = cursor.fetchone()

    # 如果用户是管理员，则查询所有链接信息
    if admin_result and admin_result[0] == 1:
        query = "SELECT created_at, short_url, long_url FROM urls"
        cursor.execute(query)
    else:
        # 否则，查询特定用户的链接信息
        query = "SELECT created_at, short_url, long_url FROM urls WHERE username = %s"
        cursor.execute(query, (username,))

    result = cursor.fetchall()

    cursor.close()
    db.close()

    return jsonify(result)


@cache.cached(timeout=1200)
@app.route('/<article_id>.html', methods=['GET', 'POST'])
def id_find_article(article_id):
    if re.match(r'^\d{1,4}$', article_id):
        user_agent = request.headers.get('User-Agent')
        db = get_database_connection()
        cursor = db.cursor()

        # 根据短网址查询数据库获取对应的长网址
        query = "SELECT long_url FROM urls WHERE id = %s"
        cursor.execute(query, (article_id,))
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
        logging.error(f"Invalid short URL: {article_id}")
        return error(message='无效的文章', status_code=404)


@cache.cached(timeout=1200)
@app.route('/blog/<article_name>/images/<image_name>', methods=['GET', 'POST'])
def sys_out_article_img(article_name, image_name):
    author = get_blog_author(article_name)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    articles_img_dir = os.path.join(base_dir, 'media', author)
    return send_from_directory(articles_img_dir, image_name)


@app.errorhandler(404)
def page_not_found(e):
    return "Page not found", 404


# 添加一个函数来处理未定义路由的错误
@app.errorhandler(500)
def internal_server_error(e):
    return "Internal server error", 500
