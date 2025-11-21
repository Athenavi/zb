from functools import wraps

from flask import abort, make_response
from flask import request, redirect, url_for
from flask_login import login_user

from src.models import User
from src.setting import app_config
from src.utils.security.jwt_handler import JWTHandler


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get('jwt')
        user_id = JWTHandler.authenticate_jwt(token)
        if user_id != 1:
            return redirect(url_for('profile'))
        return f(user_id, *args, **kwargs)

    return decorated_function


def jwt_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get('jwt')
        user_id = JWTHandler.authenticate_jwt(token)
        callback_endpoint = request.endpoint
        refresh_token = request.cookies.get('refresh_token')

        if user_id is None:
            if refresh_token is not None:
                user_id = JWTHandler.authenticate_refresh_token(refresh_token)

            if user_id is None:
                return redirect("/login?callback=" + callback_endpoint)

            # 仅在刷新令牌验证成功后设置用户会话
            user = User.get(user_id)
            login_user(user)

            resp = f(user_id, *args, **kwargs)
            response = make_response(resp)
            return JWTHandler.update_jwt_cookies(response, user_id) or response

        # 普通JWT验证成功，直接传递user_id
        return f(user_id, *args, **kwargs)

    return decorated_function


def get_current_user_id():
    token = request.cookies.get('jwt')
    user_id = JWTHandler.authenticate_jwt(token)
    refresh_token = request.cookies.get('refresh_token')
    if user_id is None:
        if refresh_token is not None:
            user_id = JWTHandler.authenticate_refresh_token(refresh_token)
    return user_id


domain = app_config.domain

# 定义白名单
allowed_origins = [domain]


def origin_required(f):
    def decorated_function(*args, **kwargs):
        origin = request.headers.get('Origin')
        if origin and origin not in allowed_origins:
            abort(403, description="请求被拒绝, 请使用白名单内的域名")
        return f(*args, **kwargs)

    decorated_function.__name__ = f.__name__
    return decorated_function
