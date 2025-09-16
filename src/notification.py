import smtplib
from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# import flask_socketio
from flask import Flask, jsonify
from flask_caching import Cache

from src.config.mail import get_mail_conf
from src.database import SessionLocal
from src.models import Notification
from src.utils.security.jwt_handler import secret_key

noti = Flask(__name__, template_folder='../templates')
# socketio = flask_socketio.SocketIO(noti, cors_allowed_origins='*')
noti.secret_key = secret_key
noti.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=3)
noti.config['SESSION_COOKIE_NAME'] = 'zb_session'

cache = Cache(config={'CACHE_TYPE': 'simple'})
cache.init_app(noti)


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
            smtp_server, stmp_port, sender_email, password = get_mail_conf()
            receiver_email = sender_email
            send_email(sender_email, password, receiver_email, smtp_server, smtp_port=int(stmp_port),
                       subject=subject,
                       body=body)
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        pass


def read_all_notifications(user_id):
    success = False
    session = SessionLocal()
    try:
        # 批量更新所有未读通知
        updated_count = session.query(Notification).filter(Notification.user_id == user_id,
                                                           Notification.is_read == False).update(
            {Notification.is_read: True})
        session.commit()
        success = True
    except Exception as e:
        print(f"批量更新已读状态失败: {e}")
        session.rollback()
    finally:
        session.close()

    response = jsonify({"success": success, "updated_count": updated_count if success else 0})
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


def get_notifications(user_id):
    messages = []
    session = SessionLocal()
    try:
        # 获取用户的所有通知
        notifications = session.query(Notification).filter(Notification.user_id == user_id).all()
        messages = [{"id": n.id, "user_id": n.user_id, "message": n.message, "is_read": n.is_read} for n in
                    notifications]
    except Exception as e:
        print(f"获取消息时发生错误: {e}")
    finally:
        session.close()

    response = jsonify(messages)
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


def read_current_notification(user_id, notification_id):
    success = False
    session = SessionLocal()
    try:
        # 更新特定通知的已读状态
        updated_count = session.query(Notification).filter(Notification.id == notification_id,
                                                           Notification.user_id == user_id).update(
            {Notification.is_read: True})
        session.commit()
        success = True
    except Exception as e:
        print(f"更新通知已读状态失败: {e}")
        session.rollback()
    finally:
        session.close()

    response = jsonify({"success": success})
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response, 200
