import logging
import random
from datetime import timedelta

import bcrypt
import bleach  # 导入 bleach 库用于 XSS 防范
from flask import request, session, redirect, url_for, render_template, app, make_response

from src.database import get_database_connection


def zy_login():
    if request.method == 'POST':
        input_value = bleach.clean(request.form['username'])  # 用户输入的用户名或邮箱
        password = bleach.clean(request.form['password'])

        if input_value == 'guest@7trees.cn':
            return render_template('Login.html', error="宾客账户仅能使用用户名登录")

        db = get_database_connection()
        cursor = db.cursor()

        try:
            query = "SELECT * FROM users WHERE (username = %s OR email = %s) AND username <> 'guest@7trees.cn'"
            cursor.execute(query, (input_value, input_value))
            result = cursor.fetchone()

            if result is not None and bcrypt.checkpw(password.encode('utf-8'), result[2].encode('utf-8')):
                session.permanent = True
                app.permanent_session_lifetime = timedelta(minutes=120)
                session['logged_in'] = True
                session['username'] = result[1]

                return redirect(url_for('home'))
            else:
                return render_template('Login.html', error="Invalid username or password")

        except Exception as e:
            logging.error(f"Error logging in: {e}")
            return "登录失败"

        finally:
            cursor.close()
            db.close()

    return render_template('Login.html', title="登录")


def zy_register(ip):
    if request.method == 'POST':
        username = bleach.clean(request.form['username'])  # 使用 bleach 进行 XSS 防范
        password = bleach.clean(request.form['password'])
        invite_code = bleach.clean(request.form['invite_code'])

        db = get_database_connection()
        cursor = db.cursor()

        try:
            # 判断用户名是否已存在
            query_username = "SELECT * FROM users WHERE username = %s"
            cursor.execute(query_username, (username,))
            existing_user = cursor.fetchone()

            if existing_user:
                return render_template('zyregister.html', title="注册新用户",
                                       msg='该用户名已被注册，请选择其他用户名!')

                # 执行用户注册的逻辑
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            insert_query = "INSERT INTO users (username, password,register_ip) VALUES (%s, %s,%s)"
            cursor.execute(insert_query, (username, hashed_password, ip))
            db.commit()
            session.pop('logged_in', None)
            session.pop('username', None)
            session.pop('password_confirmed', None)
            return render_template('success.html')

        except Exception as e:
            logging.error(f"Error registering user: {e}")
            return render_template('zyregister.html', title="注册新用户", msg='注册失败!')
        finally:
            cursor.close()
            db.close()

    return render_template('zyregister.html', title="注册新用户")


def get_email(username):
    email = 'guest@7trees.cn'
    if username is not None and isinstance(username, str):
        username = bleach.clean(username)
    db = get_database_connection()
    cursor = db.cursor()

    try:
        query = "SELECT email FROM users WHERE username = %s"
        cursor.execute(query, (username,))
        result = cursor.fetchone()  # 获取查询结果

        if result:
            email = result[0]  # 从结果中提取email值

    finally:
        cursor.close()
        db.close()

    return email


def zy_mail_login(user_email, ip):
    username = 'qks' + format(random.randint(1000, 9999))
    password = '123456'
    db = get_database_connection()
    cursor = db.cursor()

    try:
        # 判断用户是否已存在
        query = "SELECT * FROM users WHERE (username = %s OR email = %s) AND username <> 'guest@7trees.cn'"
        cursor.execute(query, (user_email, user_email))
        result = cursor.fetchone()

        if result is not None:
            session.permanent = True
            app.permanent_session_lifetime = timedelta(minutes=120)
            session['logged_in'] = True
            session['username'] = result[1]

            resp = make_response(render_template('success.html', message="授权通过!你可以关闭此页面"))

            # 设置 cookie
            resp.set_cookie('login_statu', '1', 30)
            return resp

        else:
            # 执行用户注册的逻辑
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            insert_query = "INSERT INTO users (username, password, email,register_ip) VALUES (%s, %s, %s,%s)"
            cursor.execute(insert_query, (username, hashed_password, user_email, ip))
            db.commit()
            message = '已经为您自动注册账号\n' + '账号' + username + '默认密码：123456 请尽快修改'
            resp = make_response(render_template('success.html', message=message))
            session['logged_in'] = True
            session['username'] = username
            # 设置 cookie
            resp.set_cookie('login_statu', '1', 30)
            return resp

    except Exception as e:
        logging.error(f"Error registering user: {e}")
        return "注册失败,如遇到其他问题，请尽快反馈"

    finally:
        cursor.close()
        db.close()
