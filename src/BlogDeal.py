import random
import urllib
import markdown
from configparser import ConfigParser
from src.database import get_database_connection
import os
from urllib.parse import quote_plus
from src.user import error
import datetime
import re


def get_article_names(page=1, per_page=10):
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
    hidden_articles = read_hidden_articles()
    articles = [article for article in articles if article not in hidden_articles]

    # 移除文章名称列表中以下划线开头的文章
    articles = [article for article in articles if not article.startswith('_')]

    has_next_page = end_index < len(markdown_files)
    has_previous_page = start_index > 0

    return articles, has_next_page, has_previous_page


def get_all_article_names():
    articles = []
    files = os.listdir('articles')
    markdown_files = [file for file in files if file.endswith('.md')]

    # 根据修改日期对markdown_files进行逆序排序
    markdown_files = sorted(markdown_files, key=lambda f: datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(
        'articles', f))), reverse=True)

    for file in markdown_files:
        article_name = file[:-3]
        articles.append(article_name)

    # 检查每篇文章是否在hidden.txt中，并在必要时将其移除
    hidden_articles = read_hidden_articles()
    articles = [article for article in articles if article not in hidden_articles]

    # 移除文章名称列表中以下划线开头的文章
    articles = [article for article in articles if not article.startswith('_')]

    return articles


def read_hidden_articles():
    db = get_database_connection()
    hidden_articles = []

    try:
        with db.cursor() as cursor:
            query = "SELECT Title FROM articles WHERE Hidden = 1"
            cursor.execute(query)
            results = cursor.fetchall()

            for result in results:
                hidden_articles.append(result[0])
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        try:
            cursor.close()
        except NameError:
            pass
        db.close()

    return hidden_articles


import codecs
import html


def get_article_content(article, limit):
    global code_lang
    try:
        with codecs.open(f'articles/{article}.md', 'r', encoding='utf-8') as f:
            content = f.read()

        lines = content.split('\n')
        lines_limit = min(limit, len(lines))
        line_counter = 0
        html_content = ''
        readNav = []
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
                    readNav.append(
                        f'<a href="#{anchor}">{header_title}</a><br>'
                    )
                    line = f'<h{header_level} id="{anchor}">{header_title}</h{header_level}>'

                html_content += zy_show_article(line)

            line_counter += 1

        return html_content, '\n'.join(readNav)

    except FileNotFoundError:
        # Return a 404 error page if the file does not exist
        return error('No file', 404)


def clear_html_format(text):
    clean_text = re.sub('<.*?>', '', str(text))
    return clean_text


def generate_random_text():
    # 生成随机的验证码文本
    characters = list('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
    captcha_text = ''.join(random.choices(characters, k=4))
    return captcha_text


def get_blog_author(title):
    db = get_database_connection()

    try:
        with db.cursor() as cursor:
            query = "SELECT Author FROM articles WHERE Title = %s"
            cursor.execute(query, (title,))
            result = cursor.fetchone()

            if result:
                return result['Author']
            else:
                return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None
    finally:
        try:
            cursor.close()
        except NameError:
            pass
        db.close()


def get_file_date(file_path):
    try:
        decoded_name = urllib.parse.unquote(file_path)  # 对文件名进行解码处理
        file_path = os.path.join('articles', decoded_name + '.md')
        # 获取文件的创建时间
        create_time = os.path.getctime(file_path)
        # 获取文件的修改时间
        modify_time = os.path.getmtime(file_path)
        # 获取文件的访问时间
        access_time = os.path.getatime(file_path)

        formatted_modify_time = datetime.datetime.fromtimestamp(modify_time).strftime("%Y-%m-%d %H:%M:%S")

        return formatted_modify_time

    except FileNotFoundError:
        # 处理文件不存在的情况
        return None


def zy_send_message(message):
    config = ConfigParser()
    config.read('config.ini', encoding='utf-8')
    return 1


def auth_articles(title, username):
    db = get_database_connection()

    try:
        with db.cursor() as cursor:
            query = "SELECT Author FROM articles WHERE Title = %s"
            cursor.execute(query, (title,))
            result = cursor.fetchone()

            if result and result[0] == username:
                return True
            else:
                return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False
    finally:
        try:
            cursor.close()
        except NameError:
            pass
        db.close()


def zy_show_article(content):
    try:
        markdown_text = content
        article_content = markdown.markdown(markdown_text)
        return article_content
    except:
        # 发生任何异常时返回一个错误页面，可以根据需要自定义错误消息
        return error('Error in displaying the article', 404)


def zy_edit_article(article):
    limit = 215  # 读取的最大行数
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
