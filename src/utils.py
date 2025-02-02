import configparser
import json
import os
import random
import re
import shutil
import string
import zipfile
from configparser import ConfigParser
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

import cv2
import jwt
from PIL import Image
from flask import request, jsonify, redirect, url_for, render_template
from packaging.version import Version
from user_agents import parse
from werkzeug.utils import secure_filename

from src.user import error, zy_general_conf

secret_key = 'your_secret_key'

JWT_EXPIRATION_DELTA = 21600  # JWT过期时间设置为6小时
REFRESH_TOKEN_EXPIRATION_DELTA = 604800  # 刷新令牌过期时间设置为7天


def generate_jwt(user_id, user_name):
    expiration_time = datetime.now(tz=timezone.utc) + timedelta(seconds=JWT_EXPIRATION_DELTA)
    payload = {
        'user_id': user_id,
        'username': user_name,
        'exp': expiration_time.timestamp()  # 使用 timestamp() 获取 UNIX 时间戳
    }

    return jwt.encode(payload, secret_key, algorithm='HS256')


def generate_refresh_token(user_id, user_name):
    # 生成刷新令牌
    expiration_time = datetime.now(tz=timezone.utc) + timedelta(seconds=REFRESH_TOKEN_EXPIRATION_DELTA)
    payload = {
        'user_id': user_id,
        'username': user_name,
        'exp': expiration_time.timestamp()  # 使用 timestamp() 获取 UNIX 时间戳
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


def get_username():
    token = request.cookies.get('jwt')
    if token:
        payload = jwt.decode(token, secret_key, algorithms=['HS256'], options={"verify_exp": False})
        return payload['username']


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get('jwt')
        user_id = authenticate_jwt(token)
        if user_id != 1:
            return error(message="Unauthorized", status_code=403)
        return f(user_id, *args, **kwargs)

    return decorated_function


def jwt_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get('jwt')
        user_id = authenticate_jwt(token)
        if user_id is None:
            callback_route = request.endpoint
            return redirect(url_for('login', callback=callback_route))
        return f(user_id, *args, **kwargs)

    return decorated_function


def user_id_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get('jwt')
        user_id = authenticate_jwt(token)
        if user_id is None:
            user_id = 0
        return f(user_id, *args, **kwargs)

    return decorated_function


def finger_required(f):
    @wraps(f)
    def finger_func(*args, **kwargs):
        token = request.cookies.get('jwt')
        user_id = authenticate_jwt(token)

        # 身份验证失败
        if user_id is None:
            callback_route = request.endpoint
            return redirect(url_for('login', callback=callback_route))

        chrome_fingerprint = request.cookies.get('finger')

        # 如果指纹不存在，呈现指纹认证模板
        if not chrome_fingerprint:
            return render_template('Authentication.html', form='finger')

        # 调用原始视图函数，并返回其响应
        return f(user_id, *args, **kwargs)

    return finger_func


def generate_short_url():
    characters = string.ascii_letters + string.digits
    short_url = ''.join(random.choice(characters) for _ in range(6))
    return short_url


def allowed_file(filename):
    allowed_extensions = {
        'txt': 5 * 1024 * 1024,  # 5MB
        'jpg': 10 * 1024 * 1024,  # 10MB
        'png': 10 * 1024 * 1024,  # 10MB
        'md': 5 * 1024 * 1024,  # 5MB
        'zip': 10 * 1024 * 1024,  # 10MB

    }
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def admin_upload_file(size_limit):
    # 检查是否有文件被上传
    if 'file' not in request.files:
        return error('No file uploaded', 400)

    file = request.files['file']

    # 检查用户是否选择了文件
    if file.filename == '':
        return error('No file selected', 400)

    # 检查文件类型和大小是否在允许范围内
    if not allowed_file(file.filename) or file.content_length > size_limit:
        return error('Invalid file', 400)

    file_type = request.form.get('type')

    # 根据类型选择保存目录
    if file_type == 'articles':
        save_directory = 'articles/'
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
    if file.filename[-4:] == '.zip' and file_type == 'theme':
        # 预览 .zip 文件的内容
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            # 获取压缩包中的文件列表
            zip_ref.extractall(save_directory)
    else:
        # 跳过非 .zip 文件的处理
        pass

    return 'File uploaded successfully'


def get_client_ip(req):
    if 'X-Forwarded-For' in req.headers:
        ip = req.headers['X-Forwarded-For'].split(',')[0].strip()
    elif 'X-Real-IP' in req.headers:
        ip = req.headers['X-Real-IP'].strip()
    else:
        ip = req.remote_addr

    return ip


def mask_ip(ip):
    # 将 IP 地址分割成四个部分
    parts = ip.split('.')
    if len(parts) == 4:
        # 隐藏最后两个部分
        masked_ip = f"{parts[0]}.{parts[1]}.xxx.xxx"
        return masked_ip
    return ip


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


def handle_article_upload(file, upload_folder, allowed_size):
    # 验证文件格式和大小
    if not file.filename.endswith('.md') or file.content_length > allowed_size:
        return 'Invalid file format or file too large.', 400

    # 使用 pathlib 创建上传文件夹
    upload_path = Path(upload_folder)
    upload_path.mkdir(parents=True, exist_ok=True)

    # 构建文件路径
    file_path = upload_path / file.filename

    # 避免文件名冲突
    if file_path.is_file():
        return 'Upload failed, the file already exists.', 400

    # 保存文件
    file.save(str(file_path))  # 确保转换为字符串
    shutil.copy(str(file_path), str(Path('articles') / file.filename))
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


domain, title, beian, sys_version, api_host, app_id, app_key = zy_general_conf()


def theme_safe_check(theme_id, channel=1):
    theme_path = f'templates/theme/{theme_id}'
    if not os.path.exists(theme_path):
        return False
    has_index_html = os.path.exists(os.path.join(theme_path, 'index.html'))
    has_template_ini = os.path.exists(os.path.join(theme_path, 'template.ini'))

    if has_index_html and has_template_ini:
        theme_detail = configparser.ConfigParser()
        # 读取 template.ini 文件
        theme_detail.read(f'templates/theme/{theme_id}/template.ini', encoding='utf-8')
        # 获取配置文件中的属性值
        tid = theme_detail.get('default', 'id').strip("'")
        author = theme_detail.get('default', 'author').strip("'")
        theme_title = theme_detail.get('default', 'title').strip("'")
        theme_description = theme_detail.get('default', 'description').strip("'")
        author_website = theme_detail.get('default', 'authorWebsite').strip("'")
        theme_version = theme_detail.get('default', 'version').strip("'")
        theme_version_code = theme_detail.get('default', 'versionCode').strip("'")
        update_url = theme_detail.get('default', 'updateUrl').strip("'")
        screenshot = theme_detail.get('default', 'screenshot').strip("'")

        theme_properties = {
            'id': tid,
            'author': author,
            'title': theme_title,
            'description': theme_description,
            'authorWebsite': author_website,
            'version': theme_version,
            'versionCode': theme_version_code,
            'updateUrl': update_url,
            'screenshot': screenshot,
        }

        if channel == 1:
            return jsonify(theme_properties)
        else:
            # print(Version(theme_version) > Version(sys_version))
            if Version(theme_version) < Version(sys_version):
                return False
            else:
                return True
    else:
        return False


def parse_update_file(filename):
    updates = []
    with open(filename, 'r', encoding='utf-8') as file:
        content = file.read()

    # 使用正则表达式提取版本信息
    pattern = re.compile(r"版本 (.+?)\s+发布日期:(.+?)\s+-*\n((?:-.*(?:\n|$))*)", re.MULTILINE)
    matches = pattern.findall(content)

    for match in matches:
        version_info = {
            'version': match[0].strip(),
            'date': match[1].strip(),
            'updates': [update.strip() for update in match[2].strip().splitlines() if update.strip()]
        }
        updates.append(version_info)
    return updates


def user_agent_info(user_agent):
    # 解析 User-Agent 字符串
    user_agent_parsed = parse(user_agent)

    # 初始化值得转换后的 User-Agent 描述
    converted_ua = "Unknown Device"

    # 根据解析结果构造转换后的描述
    if user_agent_parsed.is_pc:
        converted_ua = f"PC / {user_agent_parsed.browser.family} / {user_agent_parsed.os.family}"
    elif user_agent_parsed.is_mobile:
        converted_ua = f"Mobile / {user_agent_parsed.device.family} / {user_agent_parsed.os.family}"
    elif user_agent_parsed.is_tablet:
        converted_ua = f"Tablet / {user_agent_parsed.device.family} / {user_agent_parsed.os.family}"

    return converted_ua


def handle_article_delete(article_name, temp_folder):
    # 确保 temp_folder 是 Path 对象
    temp_folder = Path(temp_folder)

    # 构建文件路径
    draft_file_path = temp_folder / f"{article_name}.md"
    published_file_path = Path('articles') / f"{article_name}.md"

    # 删除草稿文件
    if draft_file_path.is_file():
        os.remove(draft_file_path)

    # 删除已发布文件
    if published_file_path.exists():
        os.remove(published_file_path)

    return True
