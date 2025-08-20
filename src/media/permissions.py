from src.database import get_db_connection


def get_media_db(user_id, page=1, per_page=20):
    try:
        with get_db_connection() as db:
            with db.cursor() as cursor:
                offset = (page - 1) * per_page
                query = f"SELECT `id`, `original_filename`,`hash` FROM media WHERE user_id = %s ORDER BY id DESC LIMIT %s OFFSET %s"
                cursor.execute(query, (user_id, per_page, offset))
                files = cursor.fetchall()
                count_query = f"SELECT COUNT(*) FROM media WHERE user_id = %s"
                cursor.execute(count_query, (user_id,))
                total_files = cursor.fetchone()[0]
                total_pages = (total_files + per_page - 1) // per_page

                return files, total_pages
    except Exception as e:
        print(f"An error occurred: {e}")
        return [], 0