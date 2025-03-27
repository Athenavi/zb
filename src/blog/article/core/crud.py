from src.database import get_db_connection


def get_articles_by_owner(owner_id=None, user_name=None):
    db = get_db_connection()
    articles = []

    try:
        with db.cursor() as cursor:
            if user_name:
                query = "SELECT ArticleID, Title FROM articles WHERE `Author` = %s and `Status` != 'Deleted';"
                cursor.execute(query, (user_name,))
                articles.extend((result[0], result[1]) for result in cursor.fetchall())

            if owner_id:
                query = """
                SELECT a.ArticleID, a.Title
                FROM articles AS a 
                JOIN users AS u ON a.Author = u.username
                WHERE u.id = %s and a.`Status` != 'Deleted';
                """
                cursor.execute(query, (owner_id,))
                articles.extend((result[0], result[1]) for result in cursor.fetchall())
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        db.close()

    return articles
