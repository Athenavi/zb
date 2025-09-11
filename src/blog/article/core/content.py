from src.database import get_db_connection


def get_article_slugs():
    # 连接到MySQL数据库
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
        with get_db_connection() as db:
            with db.cursor() as cursor:
                query = 'SELECT content FROM article_i18n WHERE article_id = %s AND language_code = %s'
                cursor.execute(query, (aid, iso))
                result = cursor.fetchone()
                if result:
                    return result[0]
                else:
                    return None
    except Exception as e:
        print(f"Error fetching i18n content: {str(e)}")
        return None


def get_i18n_title(aid, iso):
    try:
        with get_db_connection() as db:
            with db.cursor() as cursor:
                query = 'SELECT title FROM article_i18n WHERE article_id = %s and language_code = %s'
                cursor.execute(query, (aid, iso))
                return cursor.fetchone()[0]
    except Exception as e:
        print(f"Error fetching i18n info: {str(e)}")
        return None
