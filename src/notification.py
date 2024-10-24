from datetime import timedelta

import flask_socketio
from flask import Flask, session

from src.utils import zy_noti_conf, get_user_status, get_username

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
        notification_message = f"当前用户没有更多通知"
    socketio.emit('new_notification', {'message': notification_message})
    return notification_message


@noti.route('/test')
def test():
    data = session.get('data', 'Not set')
    return f'Session data: {data}'
