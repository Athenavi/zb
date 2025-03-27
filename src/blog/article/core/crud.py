from flask import jsonify

from src.database import get_db_connection


def fetch_articles(query, params):
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            cursor.execute(query, params)
            article_info = cursor.fetchall()
            cursor.execute("SELECT COUNT(*) FROM `articles` WHERE `Hidden`=0 AND `Status`='Published'")
            total_articles = cursor.fetchone()[0]

    except Exception as e:
        print(f"Error getting articles: {e}")
        raise

    finally:
        if db is not None:
            db.close()
        return article_info, total_articles


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


def read_hidden_articles():
    hidden_articles = []
    try:
        with get_db_connection() as db:
            with db.cursor() as cursor:
                query = "SELECT `Title` FROM `articles` WHERE `Hidden` = 1"
                cursor.execute(query)
                results = cursor.fetchall()
                for result in results:
                    hidden_articles.append(result[0])
    except Exception as e:
        print(f"An error occurred: {e}")
        # 更详细的日志记录或错误处理机制

    return hidden_articles


def delete_db_article(user_id, aid):
    try:
        with get_db_connection() as db:
            with db.cursor() as cursor:
                cursor.execute("UPDATE `articles` SET `Status`=%s WHERE `ArticleID`=%s", ('Deleted', aid))
                db.commit()
        return jsonify({'show_edit_code': "deleted"}), 201
    except Exception as e:
        return jsonify({'show_edit_code': 'error', 'message': f'删除文章失败{e}'}), 500
