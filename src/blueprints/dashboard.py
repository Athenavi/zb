from flask import Blueprint, request, render_template, redirect, url_for
from flask import jsonify

from src.config.general import get_general_config
from src.config.theme import get_all_themes
from src.database import get_db_connection
from src.error import error
from src.user.authz.decorators import admin_required

dashboard_bp = Blueprint('dashboard', __name__, template_folder='templates')


@dashboard_bp.route('/dashboard', methods=['GET'])
@dashboard_bp.route('/dashboard/overview', methods=['GET'])
@admin_required
def m_overview(user_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SHOW TABLE STATUS WHERE Name IN ('articles', 'users', 'comments','media','events');")
        dash_info = cursor.fetchall()
        cursor.execute('SELECT * FROM events')
        events = cursor.fetchall()
        cursor.close()
        connection.close()
        return render_template('dashboard/M-overview.html', dashInfo=dash_info, events=events)
    except Exception as e:
        return jsonify({"message": f"获取Overview时出错: {str(e)}"}), 500


@dashboard_bp.route('/dashboard/overview', methods=['DELETE'])
@admin_required
def m_overview_delete(user_id):
    event_id = request.args.get('id', type=int)
    if event_id is None:
        return jsonify({"message": "操作失败"}), 400

    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                query = "DELETE FROM `events` WHERE `id` = %s;"
                cursor.execute(query, (event_id,))
                connection.commit()

        return jsonify({"message": "操作成功"}), 200

    except Exception as e:
        return jsonify({"message": "操作失败", "error": str(e)}), 500
    finally:
        referrer = request.referrer
        print(referrer)


@dashboard_bp.route('/dashboard/urls', methods=['DELETE'])
@admin_required
def m_urls_delete(user_id):
    url_id = int(request.args.get('id'))
    if not id:
        return jsonify({"message": "操作失败"}), 400

    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                query = "DELETE FROM `urls` WHERE `id` = %s;"
                cursor.execute(query, (url_id,))
                connection.commit()

        return jsonify({"message": "操作成功"}), 200

    except Exception as e:
        return jsonify({"message": "操作失败", "error": str(e)}), 500
    finally:
        referrer = request.referrer
        print(f"{referrer}: {user_id}")


@dashboard_bp.route('/dashboard/permissions', methods=['GET', 'POST'])
@admin_required
def manage_permissions(user_id):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # 处理权限操作
    if request.method == 'POST':
        # 添加新权限
        if 'add_permission' in request.form:
            code = request.form['code']
            description = request.form['description']
            cursor.execute('INSERT INTO permissions (code, description) VALUES (%s, %s)', (code, description))

        # 添加新角色
        elif 'add_role' in request.form:
            name = request.form['name']
            description = request.form['description']
            cursor.execute('INSERT INTO roles (name, description) VALUES (%s, %s)', (name, description))

        # 分配权限给角色
        elif 'assign_permission' in request.form:
            role_id = request.form['role_id']
            permission_id = request.form['permission_id']
            cursor.execute('INSERT IGNORE INTO role_permissions (role_id, permission_id) VALUES (%s, %s)',
                           (role_id, permission_id))

        # 分配角色给用户
        elif 'assign_role' in request.form:
            user_id = request.form['user_id']
            role_id = request.form['role_id']
            cursor.execute('INSERT IGNORE INTO user_roles (user_id, role_id) VALUES (%s, %s)',
                           (user_id, role_id))

        db.commit()

    # 获取所有数据
    cursor.execute('SELECT * FROM permissions')
    permissions = cursor.fetchall()

    cursor.execute('SELECT * FROM roles')
    roles = cursor.fetchall()

    cursor.execute(
        'SELECT u.id, u.username, GROUP_CONCAT(r.name) as roles FROM users u LEFT JOIN user_roles ur ON u.id = ur.user_id LEFT JOIN roles r ON ur.role_id = r.id GROUP BY u.id')
    users = cursor.fetchall()

    cursor.execute(
        'SELECT r.id as role_id, r.name as role_name, GROUP_CONCAT(p.code) as permissions FROM roles r LEFT JOIN role_permissions rp ON r.id = rp.role_id LEFT JOIN permissions p ON rp.permission_id = p.id GROUP BY r.id')
    role_permissions = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template('permissions.html',
                           permissions=permissions,
                           roles=roles,
                           users=users,
                           role_permissions=role_permissions)


@dashboard_bp.route('/dashboard/articles', methods=['GET'])
@admin_required
def m_articles(user_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute('SELECT * FROM articles')
        articles = cursor.fetchall()
        cursor.close()
        connection.close()
        return render_template('dashboard/M-articles.html', articles=articles)
    except Exception as e:
        # 记录错误日志
        print(f"Error fetching articles by user {user_id}: {str(e)}")
        # 返回错误信息或重定向到错误页面
        return error(message=f"获取文章时出错: {str(e)}", status_code=500), 500


@dashboard_bp.route('/dashboard/users', methods=['GET'])
@admin_required
def m_users(user_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users')  # 从数据库获取用户列表
        users = cursor.fetchall()
        cursor.close()
        connection.close()
        return render_template('dashboard/M-users.html', users=users)
    except Exception as e:
        # 记录错误日志
        print(f"Error fetching users by user {user_id}: {str(e)}")
        # 返回错误信息或重定向到错误页面
        return error(message=f"获取用户时出错: {str(e)}", status_code=500), 500


@dashboard_bp.route('/dashboard/comments', methods=['GET'])
@admin_required
def m_comments(user_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute('SELECT * FROM comments')
        comments = cursor.fetchall()
        cursor.close()
        connection.close()
        return render_template('dashboard/M-comments.html', comments=comments)
    except Exception as e:
        # 记录错误日志
        print(f"Error fetching comments by user {user_id}: {str(e)}")
        # 返回错误信息或重定向到错误页面
        return error(message=f"获取文章时出错: {str(e)}", status_code=500), 500


@dashboard_bp.route('/dashboard/media', methods=['GET'])
@admin_required
def m_media(user_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute('SELECT * FROM media')  # 从数据库获取媒体列表
        media_items = cursor.fetchall()
        cursor.close()
        connection.close()
        return render_template('dashboard/M-media.html', media_items=media_items)
    except Exception as e:
        # 记录错误日志
        print(f"An error occurred while user-{user_id} was retrieving media : {str(e)}")
        # 返回错误信息或重定向到错误页面
        return error(message=f"获取媒体时出错: {str(e)}", status_code=500), 500


@dashboard_bp.route('/dashboard/notifications', methods=['GET'])
@admin_required
def m_notifications(user_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute('SELECT * FROM notifications')  # 从数据库获取通知列表
        notifications = cursor.fetchall()
        cursor.close()
        connection.close()
        return render_template('dashboard/M-notifications.html', notifications=notifications)
    except Exception as e:
        # 记录错误日志
        print(f"An error occurred while user-{user_id} was getting notifications : {str(e)}")
        # 返回错误信息或重定向到错误页面
        return error(message=f"获取文章时出错: {str(e)}", status_code=500), 500


@dashboard_bp.route('/dashboard/reports', methods=['GET'])
@admin_required
def m_reports(user_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute('SELECT * FROM reports')  # 从数据库获取举报列表
        reports = cursor.fetchall()
        cursor.close()
        connection.close()
        return render_template('dashboard/M-reports.html', reports=reports)
    except Exception as e:
        # 记录错误日志
        print(f"An error occurred while user-{user_id} was getting reports : {str(e)}")
        # 返回错误信息或重定向到错误页面
        return error(message=f"获取举报信息时出错: {str(e)}", status_code=500), 500


@dashboard_bp.route('/dashboard/urls', methods=['GET'])
@admin_required
def m_urls(user_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute('SELECT * FROM urls')  # 从数据库获取短链接列表
        urls = cursor.fetchall()
        cursor.close()
        connection.close()
        return render_template('dashboard/M-urls.html', urls=urls)
    except Exception as e:
        # 记录错误日志
        print(f"An error occurred while user-{user_id} was getting urls : {str(e)}")
        # 返回错误信息或重定向到错误页面
        return error(message=f"获取短链接时出错: {str(e)}", status_code=500), 500


@dashboard_bp.route('/dashboard/display', methods=['GET'])
@admin_required
def m_display(user_id):
    return render_template('dashboard/M-display.html', displayList=get_all_themes(), user_id=user_id)


@dashboard_bp.route('/dashboard/articles', methods=['DELETE'])
@admin_required
def m_articles_delete(user_id):
    aid = request.args.get('aid')
    if not aid:
        return jsonify({"message": "操作失败"}), 400

    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                query = "DELETE FROM `articles` WHERE `articles`.`article_id` = %s;"
                cursor.execute(query, (int(aid),))
                connection.commit()

        return jsonify({"message": "操作成功"}), 200

    except Exception as e:
        return jsonify({"message": "操作失败", "error": str(e)}), 500
    finally:
        referrer = request.referrer
        print(f"{referrer} delete {aid} by: {user_id}")


@dashboard_bp.route('/dashboard/articles', methods=['PUT'])
@admin_required
def m_articles_edit(user_id):
    data = request.get_json()
    article_id = data.get('ArticleID')
    article_title = data.get('Title')
    article_status = data.get('Status')
    if not article_id or not article_title:
        return jsonify({"message": "操作失败"}), 400

    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                query = "UPDATE `articles` SET `Title` = %s,`Status`= %s WHERE `article_id` = %s;"
                cursor.execute(query, (article_title, article_status, int(article_id)))
                connection.commit()

        return jsonify({"message": "操作成功"}), 200

    except Exception as e:
        return jsonify({"message": "操作失败", "error": str(e)}), 500
    finally:
        referrer = request.referrer
        print(f"{referrer} : modify article {article_id} by  {user_id}")


@dashboard_bp.route('/dashboard/users', methods=['DELETE'])
@admin_required
def m_users_delete(user_id):
    uid = int(request.args.get('uid'))
    if not uid or uid == 1:
        return jsonify({"message": "操作失败"}), 400

    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                query = "DELETE FROM `users` WHERE `id` = %s;"
                cursor.execute(query, (uid,))
                connection.commit()

        return jsonify({"message": "操作成功"}), 200

    except Exception as e:
        return jsonify({"message": "操作失败", "error": str(e)}), 500
    finally:
        referrer = request.referrer
        print(f"{referrer}: delete user {uid} by: {user_id}")


@dashboard_bp.route('/dashboard/users', methods=['PUT'])
@admin_required
def m_users_edit(user_id):
    data = request.get_json()
    u_id = data.get('UId')
    user_name = data.get('UName')
    user_role = data.get('URole')
    if not u_id or not user_name:
        return jsonify({"message": "操作失败"}), 400

    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                query = "UPDATE `users` SET `username` = %s WHERE `id` = %s;"
                cursor.execute(query, (user_name, int(u_id)))
                connection.commit()

        return jsonify({"message": "操作成功"}), 200

    except Exception as e:
        return jsonify({"message": "操作失败", "error": str(e)}), 500
    finally:
        referrer = request.referrer
        print(f"{referrer} edit {u_id} to {user_role} by: {user_id}")


@dashboard_bp.route('/dashboard/comments', methods=['DELETE'])
@admin_required
def m_comments_delete(user_id):
    cid = int(request.args.get('cid'))
    if not cid:
        return jsonify({"message": "操作失败"}), 400

    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                query = "DELETE FROM `comments` WHERE `id` = %s;"
                cursor.execute(query, (cid,))
                connection.commit()

        return jsonify({"message": "操作成功"}), 200

    except Exception as e:
        return jsonify({"message": "操作失败", "error": str(e)}), 500
    finally:
        referrer = request.referrer
        print(f"{referrer}: delete comment {cid} by: {user_id}")


@dashboard_bp.route('/dashboard/media', methods=['DELETE'])
@admin_required
def m_media_delete(user_id):
    file_id = int(request.args.get('file-id'))
    if not file_id:
        return jsonify({"message": "操作失败"}), 400

    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                query = "DELETE FROM `media` WHERE `id` = %s;"
                cursor.execute(query, (file_id,))
                connection.commit()

        return jsonify({"message": "操作成功"}), 200

    except Exception as e:
        return jsonify({"message": "操作失败", "error": str(e)}), 500
    finally:
        referrer = request.referrer
        print(f"{referrer}: delete file {file_id} by: {user_id}")


@dashboard_bp.route('/dashboard/notifications', methods=['DELETE'])
@admin_required
def m_notifications_delete(user_id):
    nid = int(request.args.get('nid'))
    if not nid:
        return jsonify({"message": "操作失败"}), 400

    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                query = "DELETE FROM `notifications` WHERE `id` = %s;"
                cursor.execute(query, (nid,))
                connection.commit()

        return jsonify({"message": "操作成功"}), 200

    except Exception as e:
        return jsonify({"message": "操作失败", "error": str(e)}), 500
    finally:
        referrer = request.referrer
        print(f"{referrer} delete notification {nid} by: {user_id}")


@dashboard_bp.route('/dashboard/reports', methods=['DELETE'])
@admin_required
def m_reports_delete(user_id):
    rid = int(request.args.get('rid'))
    if not rid:
        return jsonify({"message": "操作失败"}), 400

    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                query = "DELETE FROM `reports` WHERE `id` = %s;"
                cursor.execute(query, (rid,))
                connection.commit()

        return jsonify({"message": "操作成功"}), 200

    except Exception as e:
        return jsonify({"message": "操作失败", "error": str(e)}), 500
    finally:
        referrer = request.referrer
        print(f"{referrer}: delete report {rid} by: {user_id}")
