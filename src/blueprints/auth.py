import re
from datetime import datetime, timedelta, timezone

import bcrypt
from flask import Blueprint
from flask import render_template, jsonify, flash
from flask_bcrypt import check_password_hash

from src.models import User
from src.utils.security.jwt_handler import JWTHandler, JWT_EXPIRATION_DELTA, REFRESH_TOKEN_EXPIRATION_DELTA

auth_bp = Blueprint('auth', __name__, template_folder='templates')
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, BooleanField, SelectField
from wtforms.validators import DataRequired, Length, EqualTo, Regexp, Optional, Email

from flask import url_for
from urllib.parse import urlparse, urljoin

from functools import wraps
from flask import request, make_response, redirect, current_app


def babel_language_switch(view_func):
    """装饰器：用于URL参数语言切换"""

    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        response = make_response(view_func(*args, **kwargs))

        # 如果通过URL参数切换语言，则设置cookie
        lang_from_request = request.args.get('lang')
        if lang_from_request in ['zh_CN', 'en']:
            response.set_cookie('lang', lang_from_request, max_age=30 * 24 * 60 * 60)

        return response

    return wrapped_view


def email_validator(form, field):
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, field.data):
        raise ValueError('请输入有效的邮箱地址')


class RegisterForm(FlaskForm):
    # 基础信息
    username = StringField('用户名', validators=[
        DataRequired(message='用户名不能为空'),
        Length(min=3, max=20, message='用户名长度必须在3-20个字符之间'),
        Regexp(r'^[a-zA-Z0-9_]+', message='用户名只能包含字母、数字和下划线')
    ])

    email = StringField('邮箱', validators=[
        DataRequired(message='邮箱不能为空'),
        Length(max=255, message='邮箱地址过长')
    ])

    password = PasswordField('密码', validators=[
        DataRequired(message='密码不能为空'),
        Length(min=8, message='密码至少需要8个字符'),
        Regexp(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]+',
               message='密码必须包含大小写字母、数字和特殊字符')
    ])

    confirm_password = PasswordField('确认密码', validators=[
        DataRequired(message='请确认密码'),
        EqualTo('password', message='两次输入的密码不一致')
    ])

    # 个人信息
    bio = TextAreaField('个人简介', validators=[
        Optional(),
        Length(max=500, message='个人简介不能超过500字符')
    ])

    display_name = StringField('显示名称', validators=[
        Optional(),
        Length(max=50, message='显示名称不能超过50字符')
    ])

    location = StringField('所在地', validators=[
        Optional(),
        Length(max=100, message='所在地信息过长')
    ])

    website = StringField('个人网站', validators=[
        Optional(),
        Length(max=255, message='网站地址过长'),
        Regexp(r'^https?://.+', message='请输入有效的网址（以http://或https://开头）')
    ])

    # 偏好设置
    locale = SelectField('语言偏好', choices=[
        ('zh_CN', '简体中文'),
        ('en_US', 'English'),
        ('ja_JP', '日本語')
    ], default='zh_CN')

    profile_private = BooleanField('私密资料', default=False)

    # 订阅设置
    newsletter = BooleanField('订阅新闻通讯', default=True)
    marketing_emails = BooleanField('接收营销邮件', default=False)

    # 条款同意
    terms = BooleanField('同意条款', validators=[
        DataRequired(message='必须同意服务条款才能注册')
    ])


@auth_bp.route('/register', methods=['GET', 'POST'])
@babel_language_switch
def register():
    from src.models import db, EmailSubscription  # 移动导入语句
    form = RegisterForm()

    if form.validate_on_submit():
        # 检查用户名和邮箱是否已存在
        if User.query.filter_by(username=form.username.data).first():
            flash('用户名已存在', 'error')
            return render_template('auth/register.html', form=form)

        if User.query.filter_by(email=form.email.data).first():
            flash('电子邮件已注册', 'error')
            return render_template('auth/register.html', form=form)

        try:
            # 创建新用户
            hashed_password = bcrypt.hashpw(
                form.password.data.encode('utf-8'),
                bcrypt.gensalt()
            ).decode('utf-8')

            new_user = User(
                username=form.username.data,
                email=form.email.data,
                password=hashed_password,
                bio=form.bio.data,
                locale=form.locale.data,
                profile_private=form.profile_private.data,
                register_ip=request.remote_addr
            )

            db.session.add(new_user)
            db.session.flush()  # 获取用户ID

            # 创建邮箱订阅设置
            if form.newsletter.data or form.marketing_emails.data:
                email_sub = EmailSubscription(
                    user_id=new_user.id,
                    subscribed=True,
                    created_at=datetime.now(timezone.utc)
                )
                db.session.add(email_sub)

            db.session.commit()

            if request.is_json:
                return jsonify({
                    'success': True,
                    'message': '注册成功',
                    'user': new_user.to_dict()
                })
            else:
                flash('注册成功！请登录。', 'success')
                return redirect(url_for('auth.login'))

        except Exception as e:
            print(e)
            db.session.rollback()
            if request.is_json:
                return jsonify({
                    'success': False,
                    'message': '注册失败，请重试'
                }), 500
            else:
                flash('注册失败，请重试。', 'error')
                return render_template('auth/register.html', form=form)

    # 处理验证错误
    if form.errors:
        for field, errors in form.errors.items():
            for error in errors:
                flash(error, 'error')

    return render_template('auth/register.html', form=form)


def is_safe_url(target):
    """检查URL是否安全（同源）"""
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
        ref_url.netloc == test_url.netloc


def resolve_callback(callback, default='profile'):
    """
    解析callback参数，可能是endpoint名称或URL路径
    """
    if not callback:
        return url_for(default)

    # 如果callback已经是URL路径且安全，直接使用
    if callback.startswith('/') and is_safe_url(callback):
        return callback

    # 如果callback是endpoint名称，尝试解析为URL
    try:
        # 分割可能的端点参数
        if '?' in callback:
            endpoint_part, query_part = callback.split('?', 1)
        else:
            endpoint_part, query_part = callback, ''

        # 尝试解析端点
        url_path = url_for(endpoint_part)

        # 添加查询参数
        if query_part:
            url_path = f"{url_path}?{query_part}"

        return url_path
    except Exception as e:
        # 如果端点解析失败，回退到默认
        current_app.logger.warning(f"Failed to resolve callback '{callback}': {str(e)}")
        return url_for(default)


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    remember_me = BooleanField('Remember Me')


@auth_bp.route('/login', methods=['GET', 'POST'])
@babel_language_switch
def login():
    form = LoginForm()
    try:
        # 获取并正确解析callback参数
        raw_callback = request.args.get('callback') or '/profile'
        callback_url = resolve_callback(raw_callback, 'profile')

        if request.method == 'GET':
            user_agent = request.headers.get('User-Agent', '')
            if is_mobile_device(user_agent):
                # 对于移动端，传递原始callback参数
                mobile_callback = raw_callback or 'profile'
                return redirect(f'/api/mobile/login?callback={mobile_callback}')

        # 设置双语标题
        title = "登录 - 认证系统"
        title_en = "Login - Authentication System"

        if request.method == 'POST':
            if request.is_json:
                data = request.get_json()
                email = data.get('email')
                password = data.get('password')
            else:
                email = form.email.data
                password = form.password.data

            user = User.query.filter_by(email=email).first()

            if user and check_password_hash(user.password, password):
                token = JWTHandler.generate_token(user_id=user.id, username=user.username)
                refresh_token = JWTHandler.generate_refresh_token(user_id=user.id)

                if request.is_json:
                    return jsonify({
                        'success': True,
                        'message': '登录成功',
                        'user': user.to_dict(),
                        'access_token': token,
                        'refresh_token': refresh_token
                    })
                else:
                    expires = datetime.now(timezone.utc) + timedelta(seconds=JWT_EXPIRATION_DELTA)
                    refresh_expires = datetime.now(timezone.utc) + timedelta(seconds=REFRESH_TOKEN_EXPIRATION_DELTA)

                    response = make_response(redirect(callback_url))
                    response.set_cookie('jwt', token, httponly=True, expires=expires)
                    response.set_cookie('refresh_token', refresh_token, httponly=True, expires=refresh_expires)
                    flash('登录成功', 'success')
                    return response
            else:
                if request.is_json:
                    return jsonify({
                        'success': False,
                        'message': '无效的电子邮件或密码'
                    }), 401
                else:
                    flash('无效的电子邮件或密码', 'error')
                    # 传递原始callback用于表单
                    return render_template('auth/login.html', form=form, email=email, callback=raw_callback)

        # 检查是否已登录
        if jwt_cookie := request.cookies.get('jwt'):
            try:
                JWTHandler.authenticate_token(jwt_cookie)
                return redirect(callback_url)
            except Exception:
                flash('您的登录已过期，请重新登录', 'error')

        # 传递原始callback用于表单
        return render_template('auth/login.html', form=form, callback=raw_callback)
    except Exception as e:
        flash('登录过程中发生错误，请稍后再试', 'error')
        current_app.logger.error(f"Login error: {str(e)}")
        return render_template('auth/login.html', form=form)


@auth_bp.route('/api/i18n/set_language', methods=['POST'])
def set_language():
    """处理语言切换请求"""
    from flask import jsonify, make_response
    data = request.get_json()
    if not data or 'language' not in data:
        return jsonify({'success': False, 'message': 'Invalid request'}), 400

    lang = data['language']
    if lang not in ['en', 'zh_CN']:
        return jsonify({'success': False, 'message': 'Unsupported language'}), 400

    response = make_response(jsonify({'success': True, 'message': 'Language updated'}))
    response.set_cookie('lang', lang, max_age=31536000)  # 1年有效期
    return response


# 移动设备检测函数
def is_mobile_device(user_agent):
    """检查User-Agent判断是否为移动设备"""
    mobile_keywords = [
        'mobile', 'android', 'iphone', 'ipad', 'ipod',
        'blackberry', 'windows phone', 'opera mini', 'iemobile'
    ]
    user_agent = user_agent.lower()
    return any(keyword in user_agent for keyword in mobile_keywords)


@auth_bp.route('/logout')
def logout():
    response = make_response(redirect('/login'))
    response.set_cookie('jwt', '', expires=0)
    response.set_cookie('refresh_token', '', expires=0)
    return response
