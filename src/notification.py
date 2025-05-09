import smtplib
from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import flask_socketio
from flask import Flask, request, jsonify
from flask_caching import Cache

from src.config.mail import zy_mail_conf
from src.user.authz.core import secret_key, authenticate_jwt
from src.database import get_db_connection

noti = Flask(__name__, template_folder='../templates')
socketio = flask_socketio.SocketIO(noti, cors_allowed_origins='*')
noti.secret_key = secret_key
noti.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=3)
noti.config['SESSION_COOKIE_NAME'] = 'zb_session'

cache = Cache(config={'CACHE_TYPE': 'simple'})
cache.init_app(noti)


def get_user_id():
    token = request.cookies.get('jwt')
    print(token)
    if token:
        user_info = authenticate_jwt(token)
        return user_info
    else:
        return None


def emit_notification(notification_message):
    socketio.emit('new_notification', {'message': notification_message})
    return notification_message


def get_sys_notice(user_id):
    notices = [{
        "id": 0,
        "title": "系统",
        "message": "暂无新信息"
    }]
    if not user_id:
        return notices

    try:
        with get_db_connection() as db:
            with db.cursor() as cursor:
                # 查询用户ID及其未读通知
                cursor.execute("""SELECT *
                                  FROM notifications
                                  WHERE user_id = %s
                                    and is_read = 0;""", (user_id,))
                existing_records = cursor.fetchall()
                print(f'获取的通知记录: {existing_records}')

                if existing_records:
                    notices = [
                        {
                            "id": record[0],
                            "title": record[2],
                            "message": record[3]
                        }
                        for record in existing_records
                    ]

    except Exception as e:
        print(f"获取通知时发生错误: {e}")
        notices = {"error": "获取通知时发生错误，详情已记录"}  # 出现异常时，返回错误消息

    return notices


def send_email(sender_email, password, receiver_email, smtp_server, smtp_port, subject, body):
    # 创建邮件对象
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject

    # 添加邮件正文
    msg.attach(MIMEText(body, 'plain'))

    try:
        # 连接到SMTP服务器，使用SMTP_SSL
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender_email, password)  # 登录
            server.sendmail(sender_email, receiver_email, msg.as_string())  # 发送邮件
        print("邮件发送成功!")
    except Exception as e:
        print(f"邮件发送失败: {e}")


def send_change_mail(content, kind):
    try:
        if content and kind:
            subject = "数据变化通知"
            body = f"来自{kind}新的内容: {content}"
            smtp_server, stmp_port, sender_email, password = zy_mail_conf()
            receiver_email = sender_email
            send_email(sender_email, password, receiver_email, smtp_server, smtp_port=int(stmp_port),
                       subject=subject,
                       body=body)
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        pass
