from src.blog.article.core.content import get_i18n_title
from src.database import get_db_connection
from src.utils.security.safe import is_valid_iso_language_code


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


def get_articles_by_uid(user_id=None):
    db = get_db_connection()
    articles = []

    try:
        with db.cursor() as cursor:
            if user_id:
                query = """
                        SELECT a.article_id, a.Title
                        FROM articles AS a
                        WHERE a.user_id = %s
                          and a.`Status` != 'Deleted'
                        order by a.article_id DESC; \
                        """
                cursor.execute(query, (user_id,))
                articles.extend((result[0], result[1]) for result in cursor.fetchall())
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        db.close()
        return articles


def get_aid_by_title(title):
    """根据标题获取文章ID（带缓存）"""
    try:
        with get_db_connection() as db:
            with db.cursor() as cursor:
                query = """
                        SELECT `article_id`
                        FROM `articles`
                        WHERE `title` = %s
                          AND `Hidden` = 0
                          AND `Status` = 'Published' \
                        """
                cursor.execute(query, (title,))
                result = cursor.fetchone()
                return result[0] if result else None
    except Exception as e:
        # app.logger.error(f"Failed to get ID for title '{title}': {str(e)}",exc_info=True)
        return None


def blog_update(aid, content):
    try:
        # 更新文章内容
        with get_db_connection() as db:
            with db.cursor() as cursor:
                cursor.execute("UPDATE `article_content` SET `Content` = %s WHERE `aid` = %s", (content, aid))
                db.commit()
                return True
    except Exception as e:
        # app.logger.error(f"Error updating article content for article id {aid}: {e}")
        return False


def get_blog_name(aid, i18n_code=None):
    i180_title = None
    try:
        if i18n_code:
            if not is_valid_iso_language_code(i18n_code):
                return None
            i180_title = get_i18n_title(iso=i18n_code, aid=aid)
        return i180_title
    except Exception:
        return i180_title
