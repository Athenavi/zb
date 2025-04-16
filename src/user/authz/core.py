from datetime import datetime, timedelta, timezone

from flask import request
from jwt import ExpiredSignatureError, InvalidTokenError, encode, decode

from src.config.general import zy_safe_conf

secret_key, JWT_EXPIRATION_DELTA, REFRESH_TOKEN_EXPIRATION_DELTA = zy_safe_conf()


def generate_jwt(user_id, user_name):
    expiration_time = datetime.now(tz=timezone.utc) + timedelta(seconds=JWT_EXPIRATION_DELTA)
    payload = {
        'user_id': user_id,
        'username': user_name,
        'exp': expiration_time.timestamp()  # 使用 timestamp() 获取 UNIX 时间戳
    }

    return encode(payload, secret_key, algorithm='HS256')


def generate_refresh_token(user_id, user_name):
    # 生成刷新令牌
    expiration_time = datetime.now(tz=timezone.utc) + timedelta(seconds=REFRESH_TOKEN_EXPIRATION_DELTA)
    payload = {
        'user_id': user_id,
        'username': user_name,
        'exp': expiration_time.timestamp()  # 使用 timestamp() 获取 UNIX 时间戳
    }
    return encode(payload, secret_key, algorithm='HS256')


def authenticate_token(token):
    """
    通用的令牌认证函数。
    验证JWT或刷新令牌，并返回用户ID。
    """
    try:
        payload = decode(token, secret_key, algorithms=['HS256'])
        return payload['user_id']
    except ExpiredSignatureError:
        return None
    except InvalidTokenError:
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
        payload = decode(token, secret_key, algorithms=['HS256'], options={"verify_exp": False})
        return payload['username']

