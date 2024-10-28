import os
import random
import string
import urllib
import zipfile
from configparser import ConfigParser
from datetime import datetime, timedelta

import jwt
import requests
from flask import request, make_response
from werkzeug.utils import secure_filename

from src.user import error

secret_key = 'your_secret_key'

JWT_EXPIRATION_DELTA = 10800  # JWT过期时间设置为3小时
REFRESH_TOKEN_EXPIRATION_DELTA = 604800  # 刷新令牌过期时间设置为7天


def generate_jwt(user_id, user_name):
    expiration_time = datetime.utcnow() + timedelta(seconds=JWT_EXPIRATION_DELTA)
    payload = {
        'user_id': user_id,
        'username': user_name,
        'exp': expiration_time
    }

    return jwt.encode(payload, secret_key, algorithm='HS256')


def generate_refresh_token(user_id, user_name):
    # 生成刷新令牌
    expiration_time = datetime.utcnow() + timedelta(seconds=REFRESH_TOKEN_EXPIRATION_DELTA)
    payload = {
        'user_id': user_id,
        'username': user_name,
        'exp': expiration_time
    }
    return jwt.encode(payload, secret_key, algorithm='HS256')


def authenticate_token(token):
    """
    通用的令牌认证函数。
    验证JWT或刷新令牌，并返回用户ID。
    """
    try:
        payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        return payload['user_id']
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def authenticate_jwt(token):
    # 认证JWT令牌
    return authenticate_token(token)


def authenticate_refresh_token(token):
    # 认证刷新令牌
    return authenticate_token(token)


def generate_short_url():
    characters = string.ascii_letters + string.digits
    short_url = ''.join(random.choice(characters) for _ in range(6))
    return short_url


ALLOWED_EXTENSIONS = {
    'txt': 5 * 1024 * 1024,  # 5MB
    'jpg': 10 * 1024 * 1024,  # 10MB
    'png': 10 * 1024 * 1024,  # 10MB
    'md': 5 * 1024 * 1024,  # 5MB
    'zip': 10 * 1024 * 1024,  # 10MB

}


def allowed_file(filename):
    # 检查文件扩展名是否在允许的列表中
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def zy_upload_file():
    if request.method == 'POST':
        # 检查是否有文件被上传
        if 'file' not in request.files:
            return error('No file uploaded', 400)

        file = request.files['file']

        # 检查用户是否选择了文件
        if file.filename == '':
            return error('No file selected', 400)

        # 检查文件类型和大小是否在允许范围内
        if not allowed_file(file.filename) or file.content_length > 10 * 1024 * 1024:
            return error('Invalid file', 400)

        type = request.form.get('type')

        # 根据类型选择保存目录
        if type == 'articles':
            save_directory = 'articles/'
        elif type == 'notice':
            save_directory = 'notice/'
        elif type == 'theme':
            save_directory = 'templates/theme/'
        else:
            return error('Invalid type', 400)

        # 检查保存目录是否存在，不存在则创建它
        if not os.path.exists(save_directory):
            os.makedirs(save_directory)

        # 保存文件到服务器上的指定目录，覆盖同名文件
        file_path = os.path.join(save_directory, secure_filename(file.filename))
        file.save(file_path)

        # 判断文件是否为 .zip 文件
        if file.filename[-4:] == '.zip':
            # 预览 .zip 文件的内容
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                # 获取压缩包中的文件列表
                zip_ref.extractall(save_directory)
        else:
            # 跳过非 .zip 文件的处理
            pass

        return 'File uploaded successfully'

    return make_response('success')


def get_client_ip(request, session):
    # 尝试从 session 中读取 IP 地址
    public_ip = session.get('public_ip')
    if public_ip:
        return public_ip

    # 按顺序尝试获取真实 IP 地址
    headers = ["X-Real-IP", "X-Forwarded-For"]
    for header in headers:
        ip = request.headers.get(header)
        if ip:
            session['public_ip'] = ip
            return ip

    # 获取公共 IP 地址
    if 'public_ip' not in session:
        try:
            response = requests.get('http://ip-api.com/json')
            data = response.json()
            if data.get('status') == 'success':
                public_ip = data.get('query')
            else:
                public_ip = ''
        except requests.RequestException:
            public_ip = ''

        # 将 IP 存入 session 中
        session['public_ip'] = public_ip

    return public_ip


# 登录页面

def read_file(file_path, num_chars):
    decoded_path = urllib.parse.unquote(file_path)  # 对文件路径进行解码处理
    encoding = 'utf-8'
    with open(decoded_path, 'r', encoding=encoding) as file:
        content = file.read(num_chars)
    return content


# 获取系统默认编码
def zy_save_edit(article_name, content):
    if article_name and content:
        save_directory = 'articles/'

        # 将文章名转换为字节字符串
        article_name_bytes = article_name.encode('utf-8')

        # 将字节字符串和目录拼接为文件路径
        file_path = os.path.join(save_directory, article_name_bytes.decode('utf-8') + ".md")

        # 检查保存目录是否存在，如果不存在则创建它
        if not os.path.exists(save_directory):
            os.makedirs(save_directory)

        # 将文件保存到指定的目录上，覆盖任何已存在的文件
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)

        return 'success'

    return 'failed'


def zy_noti_conf():
    noti_config = ConfigParser()
    try:
        noti_config.read('config.ini', encoding='utf-8')
    except UnicodeDecodeError:
        noti_config.read('config.ini', encoding='gbk')
    noti_host = noti_config.get('notification', 'host', fallback='error').strip("'")
    noti_port = noti_config.get('notification', 'port', fallback='error').strip("'")

    return noti_host, noti_port


def zy_mail_conf():
    mail_config = ConfigParser()
    try:
        mail_config.read('config.ini', encoding='utf-8')
    except UnicodeDecodeError:
        mail_config.read('config.ini', encoding='gbk')
    mail_host = mail_config.get('mail', 'host', fallback='error').strip("'")
    mail_port = mail_config.get('mail', 'port', fallback='error').strip("'")
    mail_user = mail_config.get('mail', 'user', fallback='error').strip("'")
    mail_password = mail_config.get('mail', 'password', fallback='error').strip("'")

    return mail_host, mail_port, mail_user, mail_password
