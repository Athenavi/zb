import logging
import os
from configparser import ConfigParser

from flask import session, render_template, redirect, url_for

from src.database import get_database_connection

config = ConfigParser()
try:
    config.read('config.ini', encoding='utf-8')
except UnicodeDecodeError:
    config.read('config.ini', encoding='gbk')

door_key = config.get('admin', 'key').strip("'")


def error(message, status_code):
    return render_template('error.html', error=message, status_code=status_code), status_code


def read_hidden_articles():
    db = get_database_connection()
    hidden_articles = []

    try:
        with db.cursor() as cursor:
            query = "SELECT Title FROM articles WHERE Hidden = 1"
            cursor.execute(query)
            results = cursor.fetchall()

            for result in results:
                hidden_articles.append(result[0])
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        try:
            cursor.close()
        except NameError:
            pass
        db.close()

    return hidden_articles


def zyadmin(key, method):
    if key == door_key:
        return back(method)
    else:
        return redirect(url_for('space'))


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
                    return redirect(url_for('space'))
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
        # files = show_files('articles/')
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


def get_owner_articles(Author):
    db = get_database_connection()
    articles = []

    try:
        with db.cursor() as cursor:
            query = "SELECT Title FROM articles WHERE Author = %s"
            cursor.execute(query, (Author,))
            results = cursor.fetchall()

            for result in results:
                articles.append(result[0])
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        try:
            cursor.close()
        except NameError:
            pass
        db.close()

    return articles
