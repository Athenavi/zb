from src.database import get_db_connection
from src.models import db, ArticleI18n


def get_article_slugs():
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
            SELECT article_id, slug
            FROM articles
            WHERE status = 'Published'
              AND hidden is false
            """
    cursor.execute(query)
    results = cursor.fetchall()

    # 关闭数据库连接
    cursor.close()
    conn.close()

    # 组合成字典返回
    article_dict = {row[0]: row[1] for row in results}
    return article_dict


def get_i18n_content_by_aid(iso, aid):
    try:
        content = db.query(ArticleI18n.content).filter(
            ArticleI18n.article_id == aid, ArticleI18n.language_code == iso).first()
        if content:
            return content[0]
        else:
            return None
    except Exception as e:
        print(f"Error fetching i18n content: {str(e)}")
        return None


def get_i18n_title(aid, iso):
    try:
        title = db.query(ArticleI18n.title).filter(
            ArticleI18n.article_id == aid, ArticleI18n.language_code == iso).first()
        if title:
            return title[0]
        else:
            return None
    except Exception as e:
        print(f"Error fetching i18n info: {str(e)}")
        return None
