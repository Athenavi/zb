import bcrypt
from flask import session, flash, redirect, url_for, render_template, request

from src.database import get_database_connection


def zy_change_password(user_id, ip):
    if 'password_confirmed' not in session or not session['password_confirmed']:
        return redirect(url_for('confirm_password'))

    if request.method == 'POST':
        username = request.form.get('username')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        # 验证用户名是否与会话中的用户名一致
        if session.get('username') != username:
            return render_template('zyPW.html', error="请核对你的用户名", form='change')

        # 查询当前密码
        db = get_database_connection()
        cursor = db.cursor()
        query = "SELECT password FROM users WHERE `id` = %s"
        cursor.execute(query, (user_id,))
        result = cursor.fetchone()

        if result:
            hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())

            if new_password == confirm_password and len(new_password) >= 6:
                # 更新密码
                update_query = "UPDATE users SET password = %s WHERE `id` = %s"
                cursor.execute(update_query, (hashed_password.decode('utf-8'), user_id))
                db.commit()

                notice_query = "INSERT INTO `notifications` (`id`, `user_id`, `type`, `message`, `is_read`, `created_at`, `updated_at`) VALUES (NULL, %s, 'safe', %s, '0', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);"
                cursor.execute(notice_query, (user_id,f"{ip} changed password"))
                db.commit()

                cursor.close()
                db.close()

                flash('密码修改成功！')
                session.clear()
                return render_template('inform.html', status_code='200', message='密码修改成功！')
    return render_template('zyPW.html', form='change')


def zy_confirm_password(user_id):
    if 'password_confirmed' in session and session['password_confirmed']:
        return redirect(url_for('change_password'))

    if request.method == 'POST':
        password = request.form.get('password')

        # 验证密码是否正确
        db = get_database_connection()
        cursor = db.cursor()

        query = "SELECT password FROM users WHERE `id` = %s"
        cursor.execute(query, (user_id,))
        result = cursor.fetchone()

        if result and bcrypt.checkpw(password.encode('utf-8'), result[0].encode('utf-8')):
            session['password_confirmed'] = True
            cursor.close()
            db.close()
            return redirect(url_for('change_password'))
        else:
            cursor.close()
            db.close()
            return render_template('zyPW.html', error="密码错误", form='confirm')

    return render_template('zyPW.html', form='confirm')
