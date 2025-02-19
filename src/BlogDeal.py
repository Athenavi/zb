import codecs
import datetime
import html
import os
import re
import urllib.parse
from contextlib import closing

import markdown
from pymysql import DatabaseError

from src.database import get_db_connection
from src.user import error


def get_article_names(per_page, page=1):
    articles = []
    files = os.listdir('articles')
    markdown_files = [file for file in files if file.endswith('.md')]

    # 根据修改日期对markdown_files进行逆序排序
    markdown_files = sorted(markdown_files, key=lambda f: datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(
        'articles', f))), reverse=True)

    start_index = (page - 1) * per_page
    end_index = start_index + per_page

    for file in markdown_files[start_index:end_index]:
        article_name = file[:-3]  # 去除文件扩展名(.md)
        articles.append(article_name)

    # 检查每篇文章是否在hidden.txt中，并在必要时将其移除
    # hidden_articles = read_hidden_articles()
    # articles = [article for article in articles if article not in hidden_articles]

    # 移除文章名称列表中以下划线开头的文章
    articles = [article for article in articles if not article.startswith('_')]

    has_next_page = end_index < len(markdown_files)
    has_previous_page = start_index > 0

    return articles, has_next_page, has_previous_page


def get_article_content(article, limit):
    global code_lang
    try:
        with codecs.open(f'articles/{article}.md', 'r', encoding='utf-8') as f:
            content = f.read()

        lines = content.split('\n')
        lines_limit = min(limit, len(lines))
        line_counter = 0
        html_content = ''
        read_nav = []
        in_code_block = False
        in_math_block = False
        code_block_content = ''
        math_content = ''

        for line in lines:
            if line_counter >= lines_limit:
                break

            if line.startswith('```'):
                if in_code_block:
                    in_code_block = False
                    # code_lang = line.split('```')[1].strip()
                    escaped_code_block_content = html.escape(code_block_content.strip())
                    html_content += f'<div class="highlight"><pre><code class="language-{code_lang}">{escaped_code_block_content}</code></pre></div>'
                    code_block_content = ''
                else:
                    in_code_block = True
                    code_lang = line.split('```')[1].strip()
            elif in_code_block:
                code_block_content += line + '\n'
            elif line.startswith('$$'):
                if not in_math_block:
                    in_math_block = True
                else:
                    in_math_block = False
                    html_content += f'<div class="math">{math_content.strip()}</div>'
                    math_content = ''
            elif in_math_block:
                math_content += line.strip() + ' '
            else:
                if re.search(r'^\s*<.*?>', line):
                    # Skip HTML tags and their content in non-code block lines
                    continue

                if line.startswith('#'):
                    header_level = len(line.split()[0]) + 2
                    header_title = line.strip('#').strip()
                    anchor = header_title.lower().replace(" ", "-")
                    read_nav.append(
                        f'<a href="#{anchor}">{header_title}</a><br>'
                    )
                    line = f'<h{header_level} id="{anchor}">{header_title}</h{header_level}>'

                html_content += zy_show_article(line)

            line_counter += 1

        return html_content, '\n'.join(read_nav)

    except FileNotFoundError:
        # Return a 404 error page if the file does not exist
        return error('No file', 404)


def zy_show_article(content):
    try:
        markdown_text = content
        article_content = markdown.markdown(markdown_text)
        return article_content
    except Exception as e:
        # 发生任何异常时返回一个错误页面，可以根据需要自定义错误消息
        return error(f'Error in displaying the article :{e}', 404)


def clear_html_format(text):
    clean_text = re.sub('<.*?>', '', str(text))
    return clean_text


def get_blog_author(title):
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


def auth_articles(article_name, user_name):
    try:
        with get_db_connection() as db:
            with db.cursor() as cursor:
                query = "SELECT 1 FROM articles WHERE Title = %s AND `Status` != 'Deleted' AND Author = %s"
                cursor.execute(query, (article_name, user_name))
                return cursor.fetchone() is not None
    except Exception as e:
        print(f"An error occurred: {e}")
        return False


def auth_by_id(aid, user_name):
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            query = "SELECT 1 FROM articles WHERE ArticleID = %s AND Author = %s"
            cursor.execute(query, (aid, user_name))
            return cursor.fetchone() is not None
    except Exception as e:
        print(f"An error occurred: {e}")
        return False
    finally:
        db.close()


def zy_edit_article(article, max_line):
    limit = max_line
    try:
        with codecs.open(f'articles/{article}.md', 'r', encoding='utf-8-sig', errors='replace') as f:
            lines = []
            for line in f:
                try:
                    lines.append(line)
                except UnicodeDecodeError:
                    # 在遇到解码错误时跳过当前行
                    pass

                if len(lines) >= limit:
                    break

        return ''.join(lines)
    except FileNotFoundError:
        # 文件不存在时返回 404 错误页面
        return error('No file', 404)


def get_subscriber_ids(uid):
    db = get_db_connection()
    cursor = db.cursor()

    try:
        # 查询用户的订阅信息和对应的用户名，合并两个查询
        query = """
                SELECT u.id, u.username
                FROM subscriptions s
                         JOIN users u ON s.subscribe_to_id = u.id
                WHERE s.subscriber_id = %s
                  AND s.subscribe_type = 'User'; \
                """
        cursor.execute(query, (uid,))
        subscribers = cursor.fetchall()

        # 如果没有找到订阅者，返回空列表
        if not subscribers:
            return []

        # 创建（ID, 用户名）元组列表
        subscriber_ids_list = [(sub[0], sub[1]) for sub in subscribers]
        print(subscriber_ids_list)
        return subscriber_ids_list

    except Exception as e:
        return f"未知错误{e}", False, False

    finally:
        cursor.close()
        db.close()


def get_unique_tags():
    db = get_db_connection()
    cursor = db.cursor()
    unique_tags = []

    try:
        query = "SELECT Tags FROM articles"
        cursor.execute(query)
        results = cursor.fetchall()
        for result in results:
            tags_str = result[0]
            if tags_str:
                tags_list = tags_str.split(';')
                unique_tags.extend(tag for tag in tags_list if tag)
        unique_tags = list(set(unique_tags))

    except Exception as e:
        return f"未知错误: {e}"

    finally:
        cursor.close()
        db.close()

    return unique_tags


def get_articles_by_tag(tag_name):
    db = get_db_connection()
    cursor = db.cursor()
    tag_articles = []

    try:
        query = "SELECT Title FROM articles WHERE hidden = 0 AND `Status` = 'Published' AND`Tags` LIKE %s"
        cursor.execute(query, ('%' + tag_name + '%',))
        results = cursor.fetchall()
        for result in results:
            tag_articles.append(result[0])

    except Exception as e:
        return f"未知错误{e}"

    finally:
        cursor.close()
        db.close()

    return tag_articles


def get_tags_by_article(article_name):
    db = get_db_connection()
    cursor = db.cursor()
    unique_tags = []
    aid = 0

    try:
        query = "SELECT ArticleID, Tags FROM articles WHERE Title = %s"
        cursor.execute(query, (article_name,))

        result = cursor.fetchone()
        if result:
            aid = result[0] or 0
            tags_str = result[1]
            if tags_str:
                tags_list = tags_str.split(';')
                unique_tags = list(set(tags_list))

    except DatabaseError as db_err:  # 处理特定的数据库错误
        # 记录数据库错误
        print(f"数据库错误: {db_err}")
        return aid, []
    except Exception as e:  # 捕获其他异常
        # 记录其他错误
        print(f"发生了一个错误: {e}")
        return aid, []
    finally:
        cursor.close()
        db.close()
        return aid, unique_tags


def set_article_info(a_title, username):
    try:
        with closing(get_db_connection()) as db:
            with db.cursor() as cursor:
                current_year = datetime.datetime.now().year

                # 插入或更新文章信息
                cursor.execute("""
                               INSERT INTO articles (Title, Author, tags)
                               VALUES (%s, %s, %s)
                               ON DUPLICATE KEY UPDATE Author = VALUES(Author),
                                                       tags   = VALUES(tags);
                               """, (a_title, username, current_year))

                # 记录事件信息
                cursor.execute("""
                               INSERT INTO events (title, description, event_date, created_at)
                               VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                               """, ('article update', f'{username} updated {a_title}'))

                # 提交事务
                db.commit()
                return True

    except Exception as e:
        print(f"数据库操作期间发生错误: {e}")
        db.rollback()
        return False


def write_tags_to_database(aid, tags_list):
    tags_str = ';'.join(tags_list)

    db = get_db_connection()
    cursor = db.cursor()

    try:
        # 检查文章是否存在
        query = "SELECT * FROM articles WHERE ArticleID = %s"
        cursor.execute(query, (int(aid),))
        result = cursor.fetchone()

        if result:
            # 如果文章存在，则更新标签
            update_query = "UPDATE articles SET Tags = %s WHERE ArticleID = %s"
            cursor.execute(update_query, (tags_str, int(aid)))
            db.commit()

    except Exception as e:
        print(f"An error occurred during database operation: {e}")
        pass

    finally:
        cursor.close()
        db.close()


def set_article_visibility(article, hide=True):
    if not isinstance(article, str):
        raise ValueError("Article must be a string")
    db = get_db_connection()
    cursor = db.cursor()
    try:
        with cursor:
            # 查询文章的当前状态
            query = "SELECT Hidden FROM articles WHERE Title = %s"
            cursor.execute(query, (article,))
            result = cursor.fetchone()

            if result is None:
                # 如果文章不存在，则插入新记录
                hidden_status = 1 if hide else 0
                tags_value = str(datetime.datetime.now().year)
                query = "INSERT INTO articles (Title, Author, Hidden, Tags) VALUES (%s, 'test', %s, %s)"
                cursor.execute(query, (article, hidden_status, tags_value))
                db.commit()
                return hidden_status
            else:
                current_hidden_status = result[0]
                if (hide and current_hidden_status == 0) or (not hide and current_hidden_status == 1):
                    # 如果需要改变隐藏状态，则更新记录
                    query = "UPDATE articles SET Hidden = %s WHERE Title = %s"
                    cursor.execute(query, (1 if hide else 0, article))
                    db.commit()
                return current_hidden_status
    except Exception as e:
        print(f"An error occurred: {e}")
        return None
    finally:
        cursor.close()
        db.close()


def get_file_date(file_path):
    try:
        decoded_name = urllib.parse.unquote(file_path)  # 对文件名进行解码处理
        file_path = os.path.join('articles', decoded_name + '.md')
        # 获取文件的创建时间
        # create_time = os.path.getctime(file_path)
        # 获取文件的修改时间
        modify_time = os.path.getmtime(file_path)
        # 获取文件的访问时间
        # access_time = os.path.getatime(file_path)

        formatted_modify_time = datetime.datetime.fromtimestamp(modify_time).strftime("%Y-%m-%d %H:%M")

        return formatted_modify_time

    except FileNotFoundError:
        # 处理文件不存在的情况
        return None


def article_change_pw(aid, passwd):
    db = get_db_connection()
    aid = int(aid)
    try:
        with db.cursor() as cursor:
            query = "SELECT * FROM article_pass WHERE aid = %s;"
            cursor.execute(query, (aid,))
            result = cursor.fetchone()
            if result:
                query = "UPDATE `article_pass` SET `pass` = %s WHERE `article_pass`.`aid` = %s;"
                cursor.execute(query, (passwd, aid,))
            else:
                query = "INSERT INTO `article_pass` (`aid`, `pass`) VALUES (%s, %s);"
                cursor.execute(query, (aid, passwd,))
    except Exception as e:
        print(f"An error occurred: {e}")
        return False
    finally:
        db.commit()
        try:
            cursor.close()
        except NameError:
            pass
        db.close()
        return True


def get_file_summary(a_title):
    articles_dir = os.path.join('articles', a_title + ".md")
    try:
        with open(articles_dir, 'r', encoding='utf-8') as file:
            content = file.read()
    except FileNotFoundError:
        return "未找到文件"
    html_content = markdown.markdown(content)
    text_content = clear_html_format(html_content)
    summary = (text_content[:75] + "...") if len(text_content) > 75 else text_content
    return summary


def get_comments(aid, page=1, per_page=30):
    comments = []
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            offset = (page - 1) * per_page
            query = "SELECT * FROM `comments` WHERE `article_id` = %s LIMIT %s OFFSET %s"
            cursor.execute(query, (int(aid), per_page, offset))
            comments = cursor.fetchall()

            # 查询评论的总数以判断是否有下一页和上一页
            count_query = "SELECT COUNT(*) FROM `comments` WHERE `article_id` = %s"
            cursor.execute(count_query, (int(aid),))
            total_comments = cursor.fetchone()[0]

            has_next_page = (page * per_page) < total_comments
            has_previous_page = page > 1
    except Exception as e:
        print(f'Error: {e}')
    finally:
        db.close()

    return comments, has_next_page, has_previous_page


def auth_files(file_path, user_id):
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


def get_more_info(aid):
    result = (None,) * 13
    db = get_db_connection()
    cursor = db.cursor()
    try:
        query = "SELECT * FROM articles WHERE ArticleID = %s"
        cursor.execute(query, (int(aid),))
        fetched_result = cursor.fetchone()
        if fetched_result:
            result = fetched_result
    except DatabaseError as db_err:
        print(f"数据库错误: {db_err}")
    except Exception as e:
        print(f"发生了一个错误: {e}")
    finally:
        cursor.close()
        db.close()
    return result


def article_save_change(aid, hidden, status, cover_image_path, excerpt):
    db = None
    try:
        db = get_db_connection()
        with db.cursor() as cursor:
            # 根据cover_image_path是否为None构建不同的查询
            if cover_image_path is None:
                query = "UPDATE `articles` SET `Hidden` = %s, `Status` = %s, `excerpt` = %s WHERE `ArticleID` = %s"
                cursor.execute(query, (int(hidden), status, excerpt, aid))
            else:
                query = "UPDATE `articles` SET hidden = %s, `Status` = %s, `CoverImage` = %s, `excerpt` = %s WHERE `ArticleID` = %s"
                cursor.execute(query, (int(hidden), status, cover_image_path, excerpt, aid))
            db.commit()
            return {'show_edit_code': 'success'}
    except Exception as e:
        print(f"An error occurred: {e}")
        return {'show_edit_code': 'failure', 'error': str(e)}
    finally:
        if db is not None:
            db.close()
