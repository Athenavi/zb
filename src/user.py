import logging
import os
from configparser import ConfigParser

from flask import session, render_template

from src.database import get_database_connection

config = ConfigParser()
try:
    config.read('config_example.ini', encoding='utf-8')
except UnicodeDecodeError:
    config.read('config_example.ini', encoding='gbk')

door_key = config.get('admin', 'key').strip("'")


def error(message, status_code):
    return render_template('error.html', error=message, status_code=status_code), status_code


def read_hidden_articles():
    hidden_articles = []
    with open('articles/hidden.txt', 'r') as hidden_file:
        hidden_articles = hidden_file.read().splitlines()
    return hidden_articles


def zyadmin(key, method):
    if key == door_key:
        return back(method)
    else:
        return error("页面不存在", 404)


def back(method):
    if session.get('logged_in'):
        username = session.get('username')
        if username:
            db = get_database_connection()
            cursor = db.cursor()
            try:
                query = "SELECT ifAdmin FROM users WHERE username = %s"
                cursor.execute(query, (username,))
                ifAdmin = cursor.fetchone()[0]
                if ifAdmin:
                    return admin_dashboard(method), 200
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


def admin_dashboard(method):
    if method != 'GET':
        return None
    else:
        if 'theme' not in session:
            session['theme'] = 'night-theme'
        files = show_files('articles/')
        hiddenList = read_hidden_articles()
        display_list = get_all_themes()
        currentDisPlay = config.get('general', 'theme').strip("'")
        print(hiddenList)
        return render_template('admin.html', theme=session['theme'], hiddenList=hiddenList, displayList=display_list,
                               currentDisplay=currentDisPlay)


def get_all_themes():
    display_list = []
    themes_path = 'templates/theme'
    if os.path.exists(themes_path):
        subfolders = [f.path for f in os.scandir(themes_path) if f.is_dir()]
        for subfolder in subfolders:
            has_index_html = os.path.exists(os.path.join(subfolder, 'index.html'))
            has_screenshot_png = os.path.exists(os.path.join(subfolder, 'screenshot.png'))
            has_template_ini = os.path.exists(os.path.join(subfolder, 'template.ini'))
            if has_index_html and has_screenshot_png and has_template_ini:
                display_list.append(os.path.basename(subfolder))
    return display_list


def zy_new_article():
    if session.get('logged_in'):
        username = session.get('username')
        if username:
            try:
                return render_template('postNewArticle.html', theme=session['theme'])
            except Exception as e:
                logging.error(f"Error logging in: {e}")
                return error("未知错误", 500)
        else:
            return error("请先登录", 401)
    else:
        return error("请先登录", 401)


def show_files(path):
    # 指定目录的路径
    directory = path
    files = os.listdir(directory)
    return files


def zy_delete_file(filename):
    # 指定目录的路径
    directory = 'articles/'

    mapper = 'author/mapper.ini'
    lines = []
    with open(mapper, 'r', encoding='utf-8') as file:
        for line in file:
            if not line.strip().startswith(filename + '='):
                lines.append(line)

    with open(mapper, 'w', encoding='utf-8') as file:
        file.writelines(lines)

    filename = filename + '.md'
    # 构建文件的完整路径
    file_path = os.path.join(directory, filename)

    try:
        # 删除文件
        os.remove(file_path)

        return 'success'

    except OSError as error:
        # 处理出错的情况
        return 'failed: ' + str(error)


def get_owner_articles(owner_name):
    articles = []

    # 读取mapper.ini文件内容
    with open('author/mapper.ini', 'r', encoding='utf-8') as file:
        lines = file.readlines()

    # 根据name获取拥有者的文章列表
    for line in lines:
        line = line.strip()
        if line and '=' in line:  # 修改这行代码
            article_info = line.split('=')
            if len(article_info) == 2:
                article_name = article_info[0].strip()
                article_owner = article_info[1].strip().strip('\'')
                if article_owner == owner_name:
                    articles.append(article_name)

    return articles
