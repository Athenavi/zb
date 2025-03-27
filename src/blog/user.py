from src.database import get_db_connection


def query_blog_author(title):
    db = get_db_connection()

    try:
        with db.cursor() as cursor:
            query = "SELECT Author FROM articles WHERE Title = %s"
            cursor.execute(query, (title,))
            result = cursor.fetchone()

            if result:
                query = "SELECT id FROM users WHERE username = %s"
                cursor.execute(query, (result[0],))
                author_uid = cursor.fetchone()
                return result[0], author_uid[0]
            else:
                return None, None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None, None
    finally:
        try:
            cursor.close()
        except NameError:
            pass
        db.close()


def authorize_by_aid(article_id, user_name):
    try:
        with get_db_connection() as db:
            with db.cursor() as cursor:
                query = "SELECT 1 FROM articles WHERE ArticleID = %s AND `Status` != 'Deleted' AND Author = %s"
                cursor.execute(query, (article_id, user_name))
                return cursor.fetchone() is not None
    except Exception as e:
        print(f"An error occurred: {e}")
        return False


def get_user_id(user_name):
    db = get_db_connection()
    user_id = 0
    try:
        with db.cursor() as cursor:
            query = "SELECT `id` FROM `users` WHERE `username` = %s;"
            cursor.execute(query, (user_name,))
            user_id = cursor.fetchone()[0]
            if user_id:
                return user_id
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        db.close()

    return user_id
