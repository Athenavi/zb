from src.database import get_db_connection


def get_article_titles(per_page=30, page=1):
    # 连接到MySQL数据库
    conn = get_db_connection()
    cursor = conn.cursor()

    # 计算查询的起始和结束索引
    start_index = (page - 1) * per_page

    # 执行查询，获取仅公开且未隐藏的文章标题
    query = """
            SELECT title
            FROM articles
            WHERE status = 'Published'
              AND hidden = 0
            ORDER BY updated_at DESC
            LIMIT %s OFFSET %s \
            """
    cursor.execute(query, (per_page, start_index))
    articles = [row[0] for row in cursor.fetchall()]

    # 关闭数据库连接
    cursor.close()
    conn.close()

    # 计算是否有下一页和上一页
    # 这里我们再次查询总的公开且未隐藏的文章数量，以确定是否有下一页和上一页
    count_query = """
                  SELECT COUNT(*)
                  FROM articles
                  WHERE status = 'Published'
                    AND hidden = 0 \
                  """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(count_query)
    total_articles = cursor.fetchone()[0]

    has_next_page = (start_index + per_page) < total_articles
    has_previous_page = start_index > 0

    # 关闭数据库连接
    cursor.close()
    conn.close()

    return articles, has_next_page, has_previous_page


import html


def get_content(identifier, is_title=True, limit=10):
    try:
        db = get_db_connection()
        cursor = db.cursor()

        if is_title:
            query = """
                    SELECT ac.content, ac.updated_at
                    FROM articles a
                             JOIN article_content ac ON a.article_id = ac.aid
                    WHERE a.title = %s
                      and a.status = 'Published'
                      and a.hidden = 0
                    """
            cursor.execute(query, (identifier,))
        else:
            query = """
                    SELECT ac.content, ac.updated_at
                    FROM articles a
                             JOIN article_content ac ON a.article_id = ac.aid
                    WHERE ac.aid = %s
                      and a.status = 'Published'
                      and a.hidden = 0
                    """
            cursor.execute(query, (identifier,))

        result = cursor.fetchone()
        cursor.close()
        db.close()

        if not result:
            print(f"No article found with {'title' if is_title else 'article_id'}:", identifier)
            return None, None

        content, date = result
        unescaped_content = html.unescape(content)

        # 按行分割Markdown内容
        lines = unescaped_content.splitlines()

        # 处理空内容的情况
        if not lines:
            return "这是一篇空白文章", date

        # 截取指定行数并保留行结构
        truncated_lines = lines[:limit]
        truncated_content = "\n".join(truncated_lines)

        # 添加省略号指示截断（如果实际行数超过限制）
        if len(lines) > limit:
            truncated_content += "\n..."

        return truncated_content, date

    except Exception as e:
        print(f"Error fetching content: {str(e)}")
        return None, None


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
