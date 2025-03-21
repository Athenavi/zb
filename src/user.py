import os
from configparser import ConfigParser

from flask import render_template

from src.database import get_db_connection

config = ConfigParser()
try:
    config.read('config.ini', encoding='utf-8')
except UnicodeDecodeError:
    config.read('config.ini', encoding='gbk')


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
    default_key = config.get('security', 'default_key').strip("'")

    return domain, title, beian, version, api_host, app_id, app_key, default_key


def zy_safe_conf():
    sys_config = ConfigParser()
    sys_config.read('config.ini', encoding='utf-8')
    secret_key = config.get('security', 'secret_key').strip("'")
    jwt_expiration_delta = config.get('security', 'JWT_EXPIRATION_DELTA').strip("'")
    refresh_token_expiration_delta = config.get('security', 'REFRESH_TOKEN_EXPIRATION_DELTA').strip("'")
    return secret_key, int(jwt_expiration_delta), int(refresh_token_expiration_delta)


def error(message, status_code):
    return render_template('inform.html', error=message, status_code=status_code), status_code


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
        db = get_db_connection()
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
    db = get_db_connection()
    articles = []

    try:
        with db.cursor() as cursor:
            if user_name:
                query = "SELECT ArticleID, Title FROM articles WHERE `Author` = %s and `Status` != 'Deleted';"
                cursor.execute(query, (user_name,))
                articles.extend((result[0], result[1]) for result in cursor.fetchall())

            if owner_id:
                query = """
                SELECT a.ArticleID, a.Title
                FROM articles AS a 
                JOIN users AS u ON a.Author = u.username
                WHERE u.id = %s and a.`Status` != 'Deleted';
                """
                cursor.execute(query, (owner_id,))
                articles.extend((result[0], result[1]) for result in cursor.fetchall())
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        db.close()

    return articles


def get_following_count(user_id, subscribe_type='User'):
    db = get_db_connection()
    count = 0
    try:
        with db.cursor() as cursor:
            if subscribe_type == 'User':
                query = "SELECT COUNT(*) FROM subscriptions WHERE `subscriber_id` = %s AND `subscribe_type` = 'User';"
                cursor.execute(query, (int(user_id),))
            else:
                query = ("SELECT COUNT(*) FROM subscriptions WHERE `subscriber_id` = %s AND `subscribe_type` = "
                         "'Category';")
                cursor.execute(query, (int(user_id),))

            # 读取查询结果
            count = cursor.fetchone()[0]
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        db.close()

    return count


def get_follower_count(user_id, subscribe_type='User'):
    db = get_db_connection()
    count = 0
    try:
        with db.cursor() as cursor:
            if subscribe_type == 'User':
                query = "SELECT COUNT(*) FROM subscriptions WHERE `subscribe_to_id` = %s AND `subscribe_type` = 'User';"
                cursor.execute(query, (int(user_id),))
            else:
                query = ("SELECT COUNT(*) FROM subscriptions WHERE `subscribe_to_id` = %s AND `subscribe_type` = "
                         "'Category';")
                cursor.execute(query, (int(user_id),))

            count = cursor.fetchone()[0]
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        db.close()

    return count


def get_can_followed(user_id, target_id):
    db = get_db_connection()
    can_follow = 1
    try:
        with db.cursor() as cursor:
            query = "SELECT COUNT(*) FROM `subscriptions` WHERE `subscriber_id` = %s AND `subscribe_to_id` = %s;"
            cursor.execute(query, (int(user_id), int(target_id)))
            count = cursor.fetchone()[0]
            if count:
                can_follow = 0
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        db.close()

    return can_follow


def get_user_id(user_name):
    db = get_db_connection()
    user_id = 0
    try:
        with db.cursor() as cursor:
            query = "SELECT `id` FROM `users` WHERE `username` = %s;"
            cursor.execute(query, (user_name,))
            user_id = cursor.fetchone()[0]
            if user_id:
                return user_id
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        db.close()

    return user_id
