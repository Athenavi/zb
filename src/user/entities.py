from sqlalchemy.exc import SQLAlchemyError

from src.database import SessionLocal
from src.models import Article, User


def auth_by_uid(article_id, user_id):
    try:
        session = SessionLocal()
        article = session.query(Article).filter_by(article_id=article_id, user_id=user_id, Status='Deleted').first()
        return article is not None
    except SQLAlchemyError as e:
        print(f"An error occurred: {e}")
        return False
    finally:
        session.close()


def check_user_conflict(zone, value):
    try:
        session = SessionLocal()
        if zone == 'username':
            user = session.query(User).filter_by(username=value).first()
        elif zone == 'email':
            user = session.query(User).filter_by(email=value).first()
        else:
            return False
        return user is not None
    except SQLAlchemyError as e:
        print(f"Error getting user list: {e}")
        return False
    finally:
        session.close()


def db_save_avatar(user_id, avatar_uuid):
    session = None
    try:
        session = SessionLocal()
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            user.profile_picture = avatar_uuid
            session.commit()
    except SQLAlchemyError as e:
        print(f"Error saving avatar: {e} by user {user_id} avatar uuid: {avatar_uuid}")
        if session:
            session.rollback()
    finally:
        if session:
            session.close()


def db_save_bio(user_id, bio):
    session = None
    try:
        session = SessionLocal()
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            user.bio = bio
            session.commit()
    except SQLAlchemyError as e:
        print(f"Error saving bio: {e} by user {user_id} bio: {bio}")
        if session:
            session.rollback()
    finally:
        if session:
            session.close()


def change_username(user_id, new_username):
    # 修改用户名将可能导致资料被意外删除,建议先导出您的资料再进行下一步操作
    # 导出资料: 点击右上角头像 -> 点击设置 -> 点击导出资料
    session = None
    try:
        session = SessionLocal()
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            user.username = new_username
            session.commit()
    except SQLAlchemyError as e:
        print(f"Error changing username: {e} by user {user_id} new username: {new_username}")
        if session:
            session.rollback()
    finally:
        if session:
            session.close()


def bind_email(user_id, param):
    if check_user_conflict('email', param):
        return False
    session = None
    try:
        session = SessionLocal()
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            user.email = param
            session.commit()
    except SQLAlchemyError as e:
        print(f"Error binding email: {e} by user {user_id} email: {param}")
        if session:
            session.rollback()
    finally:
        if session:
            session.close()


def get_avatar(domain, user_identifier=None, identifier_type='id'):
    avatar_url = None
    if not user_identifier:
        return avatar_url

    session = None
    try:
        session = SessionLocal()
        if identifier_type == 'id':
            user = session.query(User).filter_by(id=user_identifier).first()
        elif identifier_type == 'username':
            user = session.query(User).filter_by(username=user_identifier).first()
        else:
            raise ValueError("identifier_type must be 'id' or 'username'")
        if user and user.profile_picture:
            avatar_url = f"{domain}static/avatar/{user.profile_picture}.webp"
    except SQLAlchemyError as e:
        print(f"Error fetching avatar: {e}")
    finally:
        if session:
            session.close()
    return avatar_url
