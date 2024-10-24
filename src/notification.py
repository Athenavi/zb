from datetime import timedelta

import flask_socketio
from flask import Flask, session

from src.utils import zy_noti_conf, get_user_status, get_username, get_sys_notice

noti = Flask(__name__, template_folder='../templates')
socketio = flask_socketio.SocketIO(noti, cors_allowed_origins='*')
noti.secret_key = 'your_secret_key'  # 确保和app.py中定义一致
noti.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=3)
noti.config['SESSION_COOKIE_NAME'] = 'zb_session'  # 确保和app.py中定义一致


def run_socketio():
    notiHost, notiPort = zy_noti_conf()
    print(f"推送服务：{notiHost},端口：{notiPort}")
    socketio.run(noti, port=notiPort)


@noti.route('/')
def send_notification():
    notification_message = "当前暂无消息"
    userStatus = get_user_status()
    username = get_username()
    if userStatus and username:
        print(userStatus)
        print(username)
        notification_message = get_sys_notice()
    socketio.emit('new_notification', {'message': notification_message})
    return notification_message


@noti.route('/test')
def test():
    data = session.get('data', 'Not set')
    return f'Session data: {data}'


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
