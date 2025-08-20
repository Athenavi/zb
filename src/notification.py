import smtplib
from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# import flask_socketio
from flask import Flask, jsonify
from flask_caching import Cache

from src.config.mail import get_mail_conf
from src.database import get_db_connection
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
    try:
        with get_db_connection() as db:
            with db.cursor() as cursor:
                # 批量更新所有未读通知
                cursor.execute("""UPDATE notifications
                                  SET is_read = 1
                                  WHERE user_id = %s
                                    AND is_read = 0""",
                               (user_id,))
                db.commit()
    except Exception as e:
        print(f"批量更新已读状态失败: {e}")

    response = jsonify({"success": success, "updated_count": cursor.rowcount if success else 0})
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


def get_notifications(user_id):
    messages = []
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            cursor.execute("""SELECT *
                              FROM notifications
                              WHERE user_id = %s;""",
                           (user_id,))
            messages = cursor.fetchall()
    except Exception as e:
        print(f"获取消息时发生错误: {e}")
    finally:
        db.close()
        return jsonify(messages)


def read_current_notification(user_id, notification_id):
    is_notice_read = False
    try:
        with get_db_connection() as db:
            with db.cursor() as cursor:
                # 直接更新所读通知
                cursor.execute("""UPDATE notifications
                                  SET is_read = 1
                                  WHERE id = %s
                                    AND user_id = %s;""",
                               (notification_id, user_id))
                db.commit()
    except Exception as e:
        print(f"获取通知时发生错误: {e}")

    response = jsonify({"is_notice_read": is_notice_read})
    response.headers.add("Access-Control-Allow-Origin", "*")
    return jsonify({"success": True}), 200
