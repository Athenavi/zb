from src.database import get_db_connection


def get_media_db(user_id, category, page=1, per_page=20):
    media_type = category or 'image'
    try:
        with get_db_connection() as db:
            with db.cursor() as cursor:
                offset = (page - 1) * per_page
                # 查询文件路径和ID，并按id降序排列
                query = f"SELECT `id`, `file_path` FROM media WHERE user_id = %s AND file_type = %s ORDER BY id DESC LIMIT %s OFFSET %s"
                cursor.execute(query, (user_id, media_type, per_page, offset))
                files = cursor.fetchall()
                print(files)
                count_query = f"SELECT COUNT(*) FROM media WHERE user_id = %s AND file_type = %s"
                cursor.execute(count_query, (user_id, media_type))
                total_files = cursor.fetchone()[0]
                total_pages = (total_files + per_page - 1) // per_page

                return files, total_pages
    except Exception as e:
        print(f"An error occurred: {e}")
        return [], 0


def verify_file_permissions(file_path, user_id):
    db = get_db_connection()
    auth = False
    print(file_path)
    try:
        with db.cursor() as cursor:
            query = "SELECT * FROM `media` WHERE `user_id` = %s and file_path = %s"
            cursor.execute(query, (user_id, file_path,))
            result = cursor.fetchone()
            if result:
                auth = True

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        try:
            cursor.close()
        except NameError:
            pass
        db.close()
        return auth
