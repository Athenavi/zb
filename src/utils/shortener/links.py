import random
import string

from src.models import db, Url


def generate_short_url():
    characters = string.ascii_letters + string.digits
    short_url = ''.join(random.choice(characters) for _ in range(6))
    return short_url


def create_special_url(long_url, user_id):
    try:
        # 查询是否存在该长链接和用户ID对应的短链接
        existing_url = db.session.query(Url).filter_by(long_url=long_url, user_id=user_id).first()

        if existing_url:
            short_url = existing_url.short_url
        else:
            # 生成新的短链接
            short_url = generate_short_url()
            new_url = Url(long_url=long_url, short_url=short_url, user_id=user_id)
            db.session.add(new_url)
            db.session.commit()

        return short_url
    except Exception as e:
        return f"Not Found {e}"
    finally:
        db.session.close()


def redirect_to_long_url(short_url):
    try:
        # 查询短链接对应的长链接
        url_entry = db.session.query(Url).filter_by(short_url=short_url).first()

        if url_entry:
            long_url = url_entry.long_url
            return long_url
        else:
            return None
    finally:
        db.session.close()


def delete_link(short_url):
    try:
        # 查询并删除短链接对应的记录
        url_entry = db.session.query(Url).filter_by(short_url=short_url).first()
        if url_entry:
            db.session.delete(url_entry)
            db.session.commit()
            return True
        else:
            return False
    except Exception as e:
        return f"Not Found {e}"
    finally:
        db.session.close()
