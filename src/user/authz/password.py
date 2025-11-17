import bcrypt
from flask import request

from src.models import User, Notification, db


def update_password(user_id, new_password, confirm_password, ip):
    user = db.session.query(User).filter_by(id=user_id).first()

    if user:
        # 验证新密码和确认密码是否一致，并且长度是否符合要求
        if new_password == confirm_password and len(new_password) >= 6:
            # 哈希新密码
            hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())

            # 更新密码
            user.password = hashed_password.decode('utf-8')

            # 创建通知
            notice = Notification(
                user_id=user_id,
                type='safe',
                message=f"{ip} changed password"
            )

            # 添加通知到会话
            db.session.add(notice)
            return True

    return False


def validate_password(user_id):
    password = request.form.get('password')
    # 查询用户
    user = db.session.query(User).filter_by(id=user_id).first()

    if user and bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
        return True
    else:
        return False
