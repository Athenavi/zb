import json
import os
import random
import re
import shutil
import string
import zipfile
from configparser import ConfigParser
from datetime import datetime, timedelta

import jwt
import requests
from flask import request, make_response, jsonify
from werkzeug.utils import secure_filename

from src.user import error

secret_key = 'your_secret_key'

JWT_EXPIRATION_DELTA = 21600  # JWT过期时间设置为6小时
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

        file_type = request.form.get('type')

        # 根据类型选择保存目录
        if file_type == 'articles':
            save_directory = 'articles/'
        elif file_type == 'notice':
            save_directory = 'notice/'
        elif file_type == 'theme':
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


def handle_file_upload(file, upload_folder):
    # 验证文件格式和大小
    if not file.filename.endswith('.md') or file.content_length > 10 * 1024 * 1024:
        return 'Invalid file format or file too large.', 400

    os.makedirs(upload_folder, exist_ok=True)
    file_path = os.path.join(upload_folder, file.filename)

    # 避免文件名冲突
    if os.path.isfile(os.path.join('articles', file.filename)):
        return 'Upload failed, the file already exists.', 400

    # 保存文件
    file.save(file_path)
    shutil.copy(file_path, 'articles')
    return None


def is_allowed_file(filename, allowed_types):
    # 检查文件是否是允许的类型
    return any(filename.lower().endswith(ext) for ext in allowed_types)


def check_exist(cache_file):
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
            cache_timestamp = datetime.fromtimestamp(os.path.getmtime(cache_file))
            if datetime.now() - cache_timestamp <= timedelta(hours=1):
                return jsonify(cache_data)


def is_valid_domain_with_slash(url):
    pattern = r"^(https?://)?([a-zA-Z0-9-]+\.)*[a-zA-Z]{2,}(\/)$"

    if re.match(pattern, url):
        return True
    else:
        return False


def get_list_intersection(list1, list2):
    intersection = list(set(list1) & set(list2))
    return intersection


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


def generate_random_text():
    # 生成随机的验证码文本
    characters = list('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
    captcha_text = ''.join(random.choices(characters, k=4))
    return captcha_text
