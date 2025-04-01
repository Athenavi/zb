from functools import wraps

from flask import request, redirect, url_for

from src.user.authz.core import authenticate_jwt


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get('jwt')
        user_id = authenticate_jwt(token)
        if user_id != 1:
            return redirect(url_for('profile'))
        return f(user_id, *args, **kwargs)

    return decorated_function


def jwt_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get('jwt')
        user_id = authenticate_jwt(token)
        if user_id is None:
            callback_route = request.endpoint
            return redirect(url_for('auth.login', callback=callback_route))
        return f(user_id, *args, **kwargs)

    return decorated_function