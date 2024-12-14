import json
import os
import random
import re
import shutil
import string
import zipfile
from configparser import ConfigParser
from datetime import datetime, timedelta

import cv2
import jwt
import requests
from PIL import Image
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
    # 按顺序尝试获取真实 IP 地址
    headers = ["X-Real-IP", "X-Forwarded-For"]
    for header in headers:
        ip = request.headers.get(header)
        if ip:
            session['public_ip'] = ip
            return ip
    return None


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
    imgs, has_next_page, has_previous_page = get_media_list(username, category='img', page=page, per_page=per_page)
    return imgs, has_next_page, has_previous_page


def get_all_video(username, page=1, per_page=10):
    videos, has_next_page, has_previous_page = get_media_list(username, category='video', page=page, per_page=per_page)
    return videos, has_next_page, has_previous_page


def get_all_xmind(username, page=1, per_page=10):
    videos, has_next_page, has_previous_page = get_media_list(username, category='xmind', page=page, per_page=per_page)
    return videos, has_next_page, has_previous_page


def generate_random_text():
    # 生成随机的验证码文本
    characters = list('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
    captcha_text = ''.join(random.choices(characters, k=4))
    return captcha_text


def generate_thumbs(img_dir, img_thumbs):
    # 打开原始图像
    original_image = Image.open(img_dir)

    # 计算要裁剪的区域
    width, height = original_image.size
    if width > height:
        left = (width - height) / 2
        top = 0
        right = left + height
        bottom = height
    else:
        left = 0
        top = (height - width) / 2
        right = width
        bottom = top + width

    # 裁剪图像
    image = original_image.crop((left, top, right, bottom))

    # 设置缩略图的尺寸
    size = (160, 160)

    # 生成缩略图并确保为160x160
    thumb_image = image.resize(size, Image.LANCZOS)

    # Convert to RGB if the image has an alpha channel
    if thumb_image.mode == 'RGBA':
        thumb_image = thumb_image.convert('RGB')

    # 保存缩略图
    thumb_image.save(img_thumbs, format='JPEG')


def generate_video_thumb(video_path, thumb_path, time=1):
    # 用OpenCV打开视频文件
    cap = cv2.VideoCapture(video_path)

    # 设置要提取的帧的时间（以毫秒为单位）
    cap.set(cv2.CAP_PROP_POS_MSEC, time * 1000)

    # 读取该帧
    success, frame = cap.read()

    if not success:
        print("无法读取视频帧")
        return

    # 转换颜色通道，从BGR到RGB
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # 将NumPy数组转换为PIL图像
    image = Image.fromarray(frame_rgb)

    # 计算要裁剪的区域
    width, height = image.size
    if width > height:
        left = (width - height) / 2
        top = 0
        right = left + height
        bottom = height
    else:
        left = 0
        top = (height - width) / 2
        right = width
        bottom = top + width

    # 裁剪图像
    image = image.crop((left, top, right, bottom))

    # 设置缩略图的尺寸
    size = (160, 160)

    # 生成缩略图并确保为160x160
    thumb_image = image.resize(size, Image.LANCZOS)

    # 保存缩略图
    thumb_image.save(thumb_path)

    # 释放视频捕捉对象
    cap.release()
