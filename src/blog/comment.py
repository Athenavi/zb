from flask import render_template, current_app, abort
from flask import request, jsonify

from src.database import get_db
from src.models import Comment, Article


def create_comment(user_id, article_id):
    data = request.get_json()
    print(data)
    user_agent_str = str(request.user_agent)
    with get_db() as db:
        try:
            new_comment = Comment(
                user_id=int(user_id),
                article_id=int(article_id),
                content=data['content'],
                ip=request.remote_addr,
                user_agent=user_agent_str,
                parent_id=int(data['parent_id']) if 'parent_id' in data else None,
            )
            db.add(new_comment)
            return jsonify({"message": "评论成功"}), 201
        except Exception as e:
            print(f'Error: {e}')
            db.rollback()
            return jsonify({"message": "评论失败"}), 500


from sqlalchemy.orm import joinedload


def comment_page_get(user_id, article_id):
    with get_db() as db:
        article = Article.query.filter_by(article_id=article_id).first()
        if not article:
            abort(404, "Article not found")
        try:
            # 获取评论树（不序列化）
            comments = Comment.query.filter_by(article_id=article_id) \
                .options(joinedload(Comment.author)) \
                .order_by(Comment.parent_id, Comment.created_at.asc()) \
                .all()

            # print(comments_tree)
            return render_template('Comment.html',
                                   article=article,
                                   comments_tree=comments)

        except Exception as e:
            current_app.logger.error(f"加载评论失败: {str(e)}")
            return render_template('Comment.html',
                                   article=article,
                                   comments_tree=[],
                                   error="加载评论失败")
