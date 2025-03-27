import os
from configparser import ConfigParser

from flask import render_template

config = ConfigParser()
try:
    config.read('config.ini', encoding='utf-8')
except UnicodeDecodeError:
    config.read('config.ini', encoding='gbk')


def get_general_config():
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


def show_files(path):
    # 指定目录的路径
    directory = path
    files = os.listdir(directory)
    return files
