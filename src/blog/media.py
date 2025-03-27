import io
import os
import random

import cv2
from PIL import Image


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







def handle_cover_resize(img, width, height):
    img = img.resize((width, height), Image.LANCZOS)
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='WEBP')
    img_byte_arr.seek(0)
    return img_byte_arr.getvalue()

