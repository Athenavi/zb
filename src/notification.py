from datetime import timedelta
import flask_socketio
from flask import Flask, request, jsonify, session
from flask_caching import Cache
from src.database import get_database_connection
from src.utils import zy_noti_conf, get_user_status, get_username

noti = Flask(__name__, template_folder='../templates')
socketio = flask_socketio.SocketIO(noti, cors_allowed_origins='*')
noti.secret_key = 'your_secret_key'
noti.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=3)
noti.config['SESSION_COOKIE_NAME'] = 'zb_session'

cache = Cache(config={'CACHE_TYPE': 'simple'})
cache.init_app(noti)


def run_socketio():
    notiHost, notiPort = zy_noti_conf()
    print(f"推送服务：{notiHost},端口：{notiPort}")
    socketio.run(noti, port=notiPort)


@noti.route('/')
def send_notification():
    username = get_username()
    print(f"发送通知的用户名: {username}")

    if not username:
        return emit_notification("用户名未找到")

    # 从缓存中获取通知消息
    cached_message = cache.get(username)
    if cached_message is not None:
        print(f'从缓存获取通知: {cached_message}')
        return emit_notification(cached_message)

    # 查询用户状态并获取通知
    if get_user_status():
        notification_message = get_sys_notice(username)
        cache.set(username, notification_message, timeout=300)  # 设置缓存有效期为5分钟
    else:
        notification_message = "当前用户状态不佳，无法获取通知"

    return emit_notification(notification_message)


def emit_notification(notification_message):
    socketio.emit('new_notification', {'message': notification_message})
    return notification_message


def get_sys_notice(username):
    notice = "当前用户没有更多通知"
    try:
        with get_database_connection() as db:
            with db.cursor() as cursor:
                # 查询用户ID及其未读通知
                cursor.execute("""
                    SELECT n.id,n.user_id,n.type,n.message,n.is_read,n.created_at,n.updated_at
                    FROM users AS u 
                    JOIN notifications AS n ON u.id = n.user_id 
                    WHERE u.username = %s AND n.is_read = 0
                """, (username,))

                existing_records = cursor.fetchall()
                print(f'获取的通知记录: {existing_records}')

                if existing_records:
                    notice = '<br />'.join(
                        [f"""{record[2]}: {record[3]} <button class="notice_read" id={record[0]}>close</button>""" for
                         record in existing_records]
                    )
    except Exception as e:
        print(f"获取通知时发生错误: {e}")
    return notice


@noti.route('/read')
def read_notification():
    username = get_username()
    nid = request.args.get('nid')

    if not username or not nid:
        return jsonify({"is_notice_read": False})

    is_notice_read = False
    try:
        with get_database_connection() as db:
            with db.cursor() as cursor:
                # 直接更新所读通知
                cursor.execute("""
                    UPDATE notifications 
                    SET is_read = 1 
                    WHERE id = %s AND user_id = (SELECT id FROM users WHERE username = %s)
                """, (nid, username))

                db.commit()
                if cursor.rowcount > 0:
                    is_notice_read = True
                    # 更新缓存
                    updated_notice = get_sys_notice(username)
                    cache.set(username, updated_notice, timeout=300)

    except Exception as e:
        print(f"获取通知时发生错误: {e}")

    response = jsonify({"is_notice_read": is_notice_read})
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email(sender_email, password, receiver_email, smtp_server, stmp_port, subject, body):
    # 创建邮件对象
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject

    # 添加邮件正文
    msg.attach(MIMEText(body, 'plain'))

    try:
        # 连接到SMTP服务器，使用SMTP_SSL
        with smtplib.SMTP_SSL(smtp_server, stmp_port) as server:  # 465 是SSL的常用端口
            server.login(sender_email, password)  # 登录
            server.sendmail(sender_email, receiver_email, msg.as_string())  # 发送邮件
        print("邮件发送成功!")
    except Exception as e:
        print(f"邮件发送失败: {e}")
