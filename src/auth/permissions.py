from src.database import get_db_connection


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