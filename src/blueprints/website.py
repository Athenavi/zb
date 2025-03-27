import re
import urllib
from datetime import datetime

from flask import Blueprint, Response, request, render_template, redirect, make_response, url_for

from src.blog.article.core.content import get_article_content, get_article_last_modified, get_a_list
from src.blog.article.core.crud import read_hidden_articles
from src.blog.tag import query_article_tags
from src.database import get_db_connection
from src.error import error
from src.user.entities import query_blog_author
from src.utils.shortener.links import create_special_url, redirect_to_long_url

website_bp = Blueprint('website', __name__, template_folder='templates')


# 通过参数传递 Cache 实例
def create_website_blueprint(cache_instance, domain, sitename):
    @website_bp.route('/robots.txt')
    @cache_instance.cached(7200)
    def static_from_root():
        content = "User-agent: *\nDisallow: /admin"
        modified_content = content + '\nSitemap: ' + domain + 'sitemap.xml'

        response = Response(modified_content, mimetype='text/plain')
        return response

    @website_bp.route('/sitemap.xml')
    @website_bp.route('/sitemap')
    @cache_instance.memoize(7200)
    def generate_sitemap():
        db = None
        try:
            db = get_db_connection()
            with db.cursor() as cursor:
                query = """SELECT Title
                           FROM `articles`
                           WHERE `Hidden` = 0
                             AND `Status` = 'Published'
                           ORDER BY `ArticleID` DESC LIMIT 40"""
                cursor.execute(query)
                results = cursor.fetchall()
                article_titles = [item[0] for item in results]

                xml_data = '<?xml version="1.0" encoding="UTF-8"?>\n'
                xml_data += '<urlset xmlns="https://www.sitemaps.org/schemas/sitemap/0.9">\n'

                for title in article_titles:
                    article_url = domain + 'blog/' + title
                    article_surl = api_shortlink(article_url)
                    date = get_article_last_modified(title)

                    xml_data += '<url>\n'
                    xml_data += f'\t<loc>{article_surl}</loc>\n'
                    xml_data += f'\t<lastmod>{date}</lastmod>\n'
                    xml_data += '\t<changefreq>Monthly</changefreq>\n'
                    xml_data += '\t<priority>0.8</priority>\n'
                    xml_data += '</url>\n'

                xml_data += '</urlset>\n'

                response = Response(xml_data, mimetype='text/xml')
                return response
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            if db is not None:
                db.close()

    @website_bp.route('/feed')
    @website_bp.route('/rss')
    @cache_instance.memoize(7200)
    def generate_rss():
        markdown_files = get_a_list(chanel=3, page=1)

        xml_data = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml_data += '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        xml_data += '<channel>\n'
        xml_data += f'<title>{domain} RSS Feed </title>\n'
        xml_data += f'<link>{domain}rss</link>\n'
        xml_data += f'<description>{sitename} RSS Feed</description>\n'
        xml_data += '<language>en-us</language>\n'
        xml_data += f'<lastBuildDate>{datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")}</lastBuildDate>\n'
        xml_data += f'<atom:link href="{domain}rss" rel="self" type="application/rss+xml" />\n'

        for file in markdown_files:
            encoded_article_name = urllib.parse.quote(file)
            article_url = domain + 'blog/' + encoded_article_name
            article_surl = api_shortlink(article_url)
            date = get_article_last_modified(encoded_article_name)
            content, *_ = get_article_content(file, 10)
            describe = encoded_article_name

            xml_data += '<item>\n'
            xml_data += f'\t<title>{file}</title>\n'
            xml_data += f'\t<link>{article_surl}</link>\n'
            xml_data += f'\t<guid>{article_url}</guid>\n'
            xml_data += f'\t<pubDate>{date}</pubDate>\n'
            xml_data += f'\t<description>{describe}</description>\n'
            xml_data += f'\t<content:encoded><![CDATA[{content}]]></content:encoded>'
            xml_data += '</item>\n'

        xml_data += '</channel>\n'
        xml_data += '</rss>\n'

        response = Response(xml_data, mimetype='application/rss+xml')
        return response

    @website_bp.route('/jump', methods=['GET', 'POST'])
    def jump():
        url = request.args.get('url', default=domain)
        return render_template('inform.html', url=url, domain=domain)

    @website_bp.route('/api/shortlink')
    def api_shortlink(long_url):
        if not long_url.startswith('https://') and not long_url.startswith('http://'):
            return 'error'
        user_name = sitename
        short_url = create_special_url(long_url, user_name)
        article_surl = domain + 's/' + short_url
        return article_surl

    @cache_instance.cached(timeout=24 * 3600, key_prefix='short_link')
    @website_bp.route('/s/<short_url>', methods=['GET', 'POST'])
    def redirect_to_long_url_route(short_url):
        if len(short_url) != 6:
            return 'error'
        user_agent = request.headers.get('User-Agent')
        long_url = redirect_to_long_url(short_url)
        if long_url:
            return redirect(long_url, code=302)
        else:
            return "短网址无效"

    @cache_instance.cached(timeout=3 * 3600, key_prefix='aid')
    @website_bp.route('/<article_id>.html', methods=['GET', 'POST'])
    def id_find_article(article_id):
        if not re.match(r'^\d{1,4}$', article_id):
            return error(message='无效的文章', status_code=404)
        db = get_db_connection()
        cursor = db.cursor()
        try:
            query = "SELECT long_url FROM urls WHERE id = %s"
            cursor.execute(query, (article_id,))
            result = cursor.fetchone()

            if result:
                long_url = result[0]
                last_slash_index = long_url.rfind("/")
                article = long_url[last_slash_index + 1:]
                return blog_detail(article)
            else:

                return error(message='没有找到文章', status_code=404)
        except Exception as e:
            db.rollback()
            return error(message='服务器内部错误', status_code=500)
        finally:
            cursor.close()
            db.close()

    @website_bp.route('/blog/<article>', methods=['GET', 'POST'])
    @cache_instance.memoize(180)
    def blog_detail(article):
        try:
            article_names = get_a_list(chanel=1)
            hidden_articles = read_hidden_articles()
            if article not in article_names:
                pass

            aid, article_tags = query_article_tags(article)
            if article in hidden_articles:
                return render_template('inform.html', aid=aid)

            author, author_uid = query_blog_author(article)
            update_date = get_article_last_modified(article)

            response = make_response(render_template('zyDetail.html',
                                                     article_content=1,
                                                     aid=aid,
                                                     articleName=article,
                                                     author=author,
                                                     authorUID=str(author_uid),
                                                     blogDate=update_date,
                                                     domain=domain,
                                                     url_for=url_for,
                                                     # article_Surl=article_surl,
                                                     article_tags=article_tags))

            # 只设置缓存的 max_age
            response.cache_control.max_age = 180

            return response

        except FileNotFoundError:
            return error(message="页面不见了", status_code=404)

    @website_bp.route('/travel', methods=['GET'])
    def travel():
        return '此接口暂时弃用'

    @website_bp.route('/guestbook', methods=['GET', 'POST'])
    def guestbook():
        return '当前功能暂未开放！'

    @website_bp.route('/changelog')
    def changelog():
        return redirect('https://github.com/Athenavi/zb/blob/main/articles/changelog.md')

    return website_bp
