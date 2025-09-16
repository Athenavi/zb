from src.database import get_db_connection


def get_user_info(user_id):
    if not user_id:
        return []
    info_list = []
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            query = "SELECT * FROM users WHERE id = %s;"
            params = (user_id,)
            cursor.execute(query, params)
            info = cursor.fetchone()

            if info:
                info_list = list(info)
                if len(info_list) > 2:
                    del info_list[2]
    except Exception as e:
        # app.logger.error(f"An error occurred: {e}")
        print(f"An error occurred: {e}")
    finally:
        db.close()
        return info_list


def get_user_name_by_id(user_id):
    author_name = '未知作者'
    try:
        with get_db_connection() as db:
            with db.cursor() as cursor:
                cursor.execute("SELECT username FROM users WHERE id = %s", (user_id,))
                result = cursor.fetchone()
                if result:
                    author_name = result[0]
    except (ValueError, TypeError) as e:
        pass
        # app.logger.error(f"Error getting author name for user_id {user_id}: {e}")
    finally:
        return author_name
