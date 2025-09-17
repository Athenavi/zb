from src.database import get_db
from src.models import db, ArticleI18n, Article


def get_article_slugs():
    with get_db() as session:
        # 使用ORM查询
        results = session.query(Article.article_id, Article.slug).filter(
            Article.status == 'Published',
            Article.hidden == False
        ).all()
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