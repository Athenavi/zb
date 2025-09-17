from flask import render_template, current_app, abort
from flask import request, jsonify

from src.models import Comment, db, Article


def create_comment(user_id, article_id):
    data = request.get_json()
    print(data)
    user_agent_str = str(request.user_agent)

    try:
        new_comment = Comment(
            user_id=int(user_id),
            article_id=int(article_id),
            content=data['content'],
            ip=request.remote_addr,
            user_agent=user_agent_str
        )
        db.session.add(new_comment)
        db.session.commit()
        return jsonify({"message": "评论成功"}), 201
    except Exception as e:
        print(f'Error: {e}')
        db.session.rollback()
        return jsonify({"message": "评论失败"}), 500


def comment_page_get(user_id, article_id):
    article = Article.query.filter_by(article_id=article_id).first()
    if not article:
        abort(404, "Article not found")

    try:
        # 获取评论树（不序列化）
        comments = Comment.query.filter_by(article_id=article_id) \
            .options(db.joinedload(Comment.author)) \
            .order_by(Comment.parent_id, Comment.created_at.asc()) \
            .all()

        # 构建评论树结构
        comments_map = {c.id: {"comment": c, "replies": []} for c in comments}
        comments_tree = []

        for comment in comments:
            if comment.parent_id is None:
                comments_tree.append(comments_map[comment.id])
            else:
                parent = comments_map.get(comment.parent_id)
                if parent:
                    parent["replies"].append(comments_map[comment.id])
        # print(comments_tree)
        return render_template('Comment.html',
                               article=article,
                               comments_tree=comments_tree)

    except Exception as e:
        current_app.logger.error(f"加载评论失败: {str(e)}")
        return render_template('Comment.html',
                               article=article,
                               comments_tree=[],
                               error="加载评论失败")
