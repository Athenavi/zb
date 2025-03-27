from flask import Blueprint, request, redirect, url_for, render_template, make_response

from src.user.authz.core import authenticate_jwt
from src.user.authz.login import user_login, create_user
from src.utils.security.ip_utils import get_client_ip

auth_bp = Blueprint('auth', __name__, template_folder='templates')


# 登录路由
@auth_bp.route('/login', methods=['POST', 'GET'])
def login():
    callback_route = request.args.get('callback', 'index_html')
    if request.cookies.get('jwt'):
        user_id = authenticate_jwt(request.cookies.get('jwt'))
        if user_id:
            return redirect(url_for(callback_route))
    if request.method == 'POST':
        return user_login(callback_route)
    return render_template('LoginRegister.html', title="登录")


# 登出路由
@auth_bp.route('/logout')
def logout():
    response = make_response(redirect(url_for('auth.login')))
    response.set_cookie('jwt', '', expires=0)
    response.set_cookie('refresh_token', '', expires=0)
    return response


# 注册路由
@auth_bp.route('/register', methods=['POST', 'GET'])
def register():
    callback_route = request.args.get('callback', 'index_html')
    if request.cookies.get('jwt'):
        user_id = authenticate_jwt(request.cookies.get('jwt'))
        if user_id:
            return redirect(url_for(callback_route))
    ip = get_client_ip(request)
    return create_user(ip)
