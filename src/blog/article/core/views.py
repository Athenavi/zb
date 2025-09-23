import re

from flask import request, render_template, url_for, jsonify, current_app, flash, redirect

from src.blog.article.security.password import get_article_password
from src.database import get_db
from src.error import error
from src.models import Article, ArticleContent, ArticleI18n, User
from src.user.entities import auth_by_uid
from src.utils.security.safe import random_string, is_valid_iso_language_code, valid_language_codes


def blog_detail_back(blog_slug, safeMode=True):
    with get_db() as db:
        # 尝试作为文章slug查找
        article = db.query(Article).filter(
            Article.slug == blog_slug,
            Article.status == 'Published',
        ).first()

        print(f'0. {article}')

        if article:
            if safeMode:
                # 仅在安全模式下检查是否隐藏
                if article.hidden:
                    return render_template('inform.html', aid=article.article_id)

            # 获取文章内容
            content = db.query(ArticleContent).filter_by(aid=article.article_id).first()

            # 获取多语言版本
            i18n_versions = db.query(ArticleI18n).filter_by(article_id=article.article_id).all()

            # 获取作者信息
            author = db.query(User).get(article.user_id)
            print(f'1. author: {author}')
            print(f'2. content: {content}')
            print(f'3. i18n: {i18n_versions}')

            return render_template('blog_detail.html',
                                   article=article,
                                   content=content,
                                   author=author,
                                   i18n_versions=i18n_versions
                                   )
        return None


def blog_detail_i18n(aid, blog_slug, i18n_code):
    if request.method == 'GET':
        return render_template('zyDetail.html', articleName=blog_slug, url_for=url_for,
                               i18n_code=i18n_code, aid=aid)
    return error(message='Invalid request', status_code=400)


def blog_detail_i18n_list(aid, i18n_code):
    if not is_valid_iso_language_code(i18n_code):
        return error(message='Invalid request', status_code=400)
    article = Article.query.filter_by(article_id=aid).first()
    if not article:
        return error(message='Article not found', status_code=404)
    if article.status != 'Published':
        return error(message='Article not published', status_code=403)
    articleI18n = ArticleI18n.query.filter_by(article_id=aid, language_code=i18n_code).all()
    if not articleI18n:
        return error(message=f'Article not found for language {i18n_code}', status_code=404)

    # 生成包含链接的HTML代码
    html_links = "<ul>"
    for i in articleI18n:
        link = f"/{aid}.html/{i18n_code}/{i.slug}"
        html_links += f"<li><a href='{link}'>{i.language_code}: {i.title}-{i.slug}</a></li>"
    html_links += "</ul>"

    return render_template('inform.html',
                           status_code=f"This article contains {len(articleI18n)} international translations.（{i18n_code}）",
                           message=html_links)


def contribute_back(aid):
    with get_db() as db:
        if request.method == 'GET':
            # 获取现有翻译信息用于展示
            existing_translations = db.query(ArticleI18n.language_code).filter(
                ArticleI18n.article_id == aid
            ).all()
            existing_languages = [t.language_code for t in existing_translations]

            return render_template('contribute.html',
                                   aid=aid,
                                   existing_languages=existing_languages,
                                   valid_language_codes=sorted(valid_language_codes))

        if request.method == 'POST':
            # 确保请求是JSON格式
            if not request.is_json:
                return jsonify({'success': False, 'message': 'Request must be JSON'}), 400

            data = request.get_json()

            # 处理表单提交
            contribute_type = data.get('contribute_type')
            contribute_content = data.get('contribute_content')
            contribute_language = data.get('contribute_language')
            contribute_title = data.get('contribute_title')
            contribute_slug = data.get('contribute_slug')

            # 验证必填字段
            if not all([contribute_type, contribute_content, contribute_language,
                        contribute_title, contribute_slug]):
                return jsonify({'success': False, 'message': 'All fields are required'}), 400

            # 处理slug
            contribute_slug = re.sub(r'[^\w\s]', '', contribute_slug)  # 移除非字母数字和下划线的字符
            contribute_slug = re.sub(r'\s+', '_', contribute_slug)

            # 验证语言代码
            if not is_valid_iso_language_code(contribute_language):
                return jsonify({'success': False, 'message': 'Invalid language code'}), 400

            # 验证文章是否存在
            article = db.query(Article).filter(
                Article.article_id == aid,
                Article.status == 'Published'
            ).first()
            if not article:
                return jsonify({'success': False, 'message': 'Article not found'}), 404

            # 检查是否已存在相同语言版本的翻译
            existing_i18n = ArticleI18n.query.filter_by(
                article_id=aid,
                language_code=contribute_language
            ).first()

            try:
                if existing_i18n:
                    # 更新现有翻译
                    existing_i18n.title = contribute_title
                    existing_i18n.slug = contribute_slug
                    existing_i18n.content = contribute_content
                    return jsonify({
                        'success': True,
                        'message': 'Translation updated successfully',
                        'i18n_id': existing_i18n.i18n_id
                    })
                else:
                    # 创建新翻译
                    new_i18n = ArticleI18n(
                        article_id=aid,
                        language_code=contribute_language,
                        title=contribute_title,
                        slug=contribute_slug,
                        content=contribute_content,
                        excerpt=contribute_content[:200]  # 简单截取作为摘要
                    )
                    db.add(new_i18n)
                    return jsonify({
                        'success': True,
                        'message': 'Translation submitted successfully',
                        'i18n_id': new_i18n.i18n_id
                    })
            except Exception as e:
                db.rollback()
                return jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500

        return jsonify({'success': False, 'message': 'Invalid request method'}), 400


def blog_detail_aid_back(aid, safeMode=True):
    with get_db() as db:
        try:
            article = db.query(Article).filter(
                Article.article_id == aid,
                Article.status == 'Published'
            ).first()

            print(article)

            if article:
                if safeMode:
                    # 仅在安全模式下检查是否隐藏
                    if article.hidden:
                        return render_template('inform.html', aid=article.article_id)
                # 获取文章内容
                content = db.query(ArticleContent).filter_by(aid=article.article_id).first()
                print(content)

                # 获取多语言版本
                i18n_versions = db.query(ArticleI18n).filter_by(article_id=article.article_id).all()

                # 获取作者信息
                author = db.query(User).get(article.user_id)
                print(f'1. author: {author}')
                print(f'2. content: {content}')
                print(f'3. i18n: {i18n_versions}')

                return render_template('blog_detail.html',
                                       article=article,
                                       content=content,
                                       author=author,
                                       i18n_versions=i18n_versions,
                                       )
            return None
        except Exception as e:
            print(f"Template error: {str(e)}")
            return str(e), 500


def blog_tmp_url(domain, cache_instance):
    try:
        aid = int(request.args.get('aid'))
    except (TypeError, ValueError):
        return jsonify({"message": "Invalid Article ID"}), 400

    entered_password = request.args.get('passwd')
    temp_url = ''
    view_uuid = random_string(16)

    response_data = {
        'aid': aid,
        'temp_url': temp_url,
    }

    # 验证密码长度
    if len(entered_password) < 4 or len(entered_password) > 128:
        return jsonify({"message": "Invalid Password"}), 400

    passwd = get_article_password(aid)
    if passwd is None:
        return jsonify({"message": "Authentication failed"}), 401

    if entered_password == passwd:
        cache_instance.set(f"temp-url_{view_uuid}", aid, timeout=900)
        temp_url = f'{domain}tmpView?url={view_uuid}'
        response_data['temp_url'] = temp_url
        return jsonify(response_data), 200
    else:
        referrer = request.referrer
        current_app.logger.error(f"{referrer} Failed access attempt {view_uuid}")
        return jsonify({"message": "Authentication failed"}), 401


def edit_article_back(user_id, article_id):
    auth = auth_by_uid(article_id, user_id)
    if not auth:
        return jsonify({"message": "Authentication failed"}), 401
    with get_db() as db:
        article = Article.query.get_or_404(article_id)
        content_obj = ArticleContent.query.filter_by(aid=article_id).first()
        content = content_obj.content if content_obj else ""

        if request.method == 'POST':
            # 更新文章信息
            article.title = request.form.get('title')
            article.slug = request.form.get('slug')
            article.excerpt = request.form.get('excerpt')
            article.tags = request.form.get('tags')
            article.hidden = 1 if request.form.get('hidden') else 0
            article.status = request.form.get('status')
            article.article_type = request.form.get('article_type')
            article.cover_image = request.form.get('cover_image')

            article.slug = re.sub(r'[^\w\s]', '', article.slug)  # 移除非字母数字和下划线的字符
            article.slug = re.sub(r'\s+', '_', article.slug)

            # 更新内容
            if content_obj:
                content_obj.content = request.form.get('content')
            else:
                content_obj = ArticleContent(
                    aid=article_id,
                    content=request.form.get('content'),
                    language_code='zh-CN'
                )
                db.add(content_obj)

                # flash('update success!', 'success')
            return redirect(url_for('edit_article', article_id=article_id))

        return render_template('article_edit.html',
                               article=article,
                               content=content,
                               status_options=['Draft', 'Published', 'Deleted'])


def new_article_back(user_id):
    article = None
    content = ""
    if request.method == 'POST':
        # 处理表单提交
        title = request.form.get('title')
        slug = request.form.get('slug')
        excerpt = request.form.get('excerpt')
        content = request.form.get('content')
        tags = request.form.get('tags')
        is_featured = True if request.form.get('is_featured') else False
        status = request.form.get('status', 'Draft')
        article_type = request.form.get('article_type')
        cover_image = request.form.get('cover_image')
        # 创建新文章
        new_article = Article(
            title=title,
            slug=slug,
            excerpt=excerpt,
            tags=tags,
            is_featured=is_featured,
            status=status,
            article_type=article_type,
            cover_image=cover_image,
            user_id=user_id
        )
        with get_db() as db:
            db.add(new_article)
            db.commit()
            article_content = ArticleContent(
                aid=new_article.article_id,
                content=content,
                language_code='zh-CN'
            )
            db.add(article_content)
            flash('文章创建成功!', 'success')
            return redirect(url_for('markdown_editor', aid=new_article.article_id))

    return render_template('article_edit.html',
                           article=article,
                           content=content,
                           status_options=['Draft', 'Published'])
