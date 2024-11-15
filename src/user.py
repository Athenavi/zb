import logging
import os
from configparser import ConfigParser

from flask import session, render_template

from src.database import get_database_connection

config = ConfigParser()
try:
    config.read('config.ini', encoding='utf-8')
except UnicodeDecodeError:
    config.read('config.ini', encoding='gbk')

door_key = config.get('admin', 'key').strip("'")


def zy_general_conf():
    sys_config = ConfigParser()
    sys_config.read('config.ini', encoding='utf-8')
    domain = config.get('general', 'domain', fallback='error').strip("'")
    title = config.get('general', 'title', fallback='error').strip("'")
    beian = config.get('general', 'beian', fallback='error').strip("'")
    version = config.get('general', 'version', fallback='error').strip("'")
    api_host = config.get('general', 'api_host', fallback='error').strip("'")
    app_id = config.get('general', 'app_id', fallback='error').strip("'")
    app_key = config.get('general', 'app_key', fallback='error').strip("'")

    return domain, title, beian, version, api_host, app_id, app_key


def error(message, status_code):
    return render_template('inform.html', error=message, status_code=status_code), status_code


def zyadmin(key, method):
    if key == door_key:
        db = get_database_connection()
        cursor = db.cursor()
        try:
            query = "SHOW TABLE STATUS WHERE Name IN ('articles', 'users', 'comments','media','events')"
            cursor.execute(query)
            dash_info = cursor.fetchall()
            return admin_dashboard(method, dash_info), 200
        except Exception as e:
            logging.error(f"Error logging in: {e}")
            return error("未知错误", 500)
        finally:
            cursor.close()
            db.close()


def admin_dashboard(method, dash_info):
    if method != 'GET':
        return None
    else:
        # print(dashInfo)
        display_list = get_all_themes()
        current_display = session.get('display', 'default')
        return render_template('dashboard.html', displayList=display_list,
                               currentDisplay=current_display, dashInfo=dash_info)


def get_all_themes():
    display_list = ['default']
    themes_path = 'templates/theme'
    if os.path.exists(themes_path):
        subfolders = [f.path for f in os.scandir(themes_path) if f.is_dir()]
        for subfolder in subfolders:
            has_index_html = os.path.exists(os.path.join(subfolder, 'index.html'))
            has_template_ini = os.path.exists(os.path.join(subfolder, 'template.ini'))
            if has_index_html and has_template_ini:
                display_list.append(os.path.basename(subfolder))
    # print(display_list)
    return display_list


def show_files(path):
    # 指定目录的路径
    directory = path
    files = os.listdir(directory)
    return files


def zy_delete_article(filename):
    # 指定目录的路径
    directory = 'articles/'
    db = None
    cursor = None
    try:
        db = get_database_connection()
        with db.cursor() as cursor:
            query = "UPDATE `articles` SET `Status` = 'Deleted' WHERE `articles`.`Title` = %s;"
            cursor.execute(query, (filename,))  # 确保 filename 与数据库中存储的格式一致
            db.commit()
            filename = filename + '.md'
            # 构建文件的完整路径
            file_path = os.path.join(directory, filename)
            # 删除文件
            os.remove(file_path)
            return 'success'
    except Exception as e:
        return 'failed: ' + str(e)
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


def get_owner_articles(owner_id=None, user_name=None):
    db = get_database_connection()
    articles = []

    try:
        with db.cursor() as cursor:
            if user_name:
                query = "SELECT Title FROM articles WHERE `Author` = %s and `Status` != 'Deleted';"
                cursor.execute(query, (user_name,))
                articles.extend(result[0] for result in cursor.fetchall())

            if owner_id:
                query = """
                SELECT a.Title FROM articles AS a JOIN users AS u ON a.Author = u.username WHERE u.id = %s and a.`Status` != 'Deleted';
                """
                cursor.execute(query, (owner_id,))
                articles.extend(result[0] for result in cursor.fetchall())
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        db.close()

    return articles


def get_userInfo(user_id=None, user_name=None):
    db = get_database_connection()
    info_list = []

    try:
        with db.cursor() as cursor:
            # 确定需要查询的条件
            if user_name:
                query = "SELECT * FROM users WHERE `username` = %s;"
                params = (user_name,)
            elif user_id:
                query = "SELECT * FROM users WHERE `id` = %s;"
                params = (user_id,)
            else:
                return info_list  # 没有提供有效的查询条件

            cursor.execute(query, params)
            info = cursor.fetchone()

            if info:
                print(info)
                info_list = list(info)  # 转换为列表

                # 移除第三个元素（如果存在）
                if len(info_list) > 2:
                    del info_list[2]

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        db.close()

    return info_list