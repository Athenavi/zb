from sqlalchemy.sql.functions import current_timestamp

from . import db


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True)
    created_at = db.Column(db.TIMESTAMP, server_default=current_timestamp())
    updated_at = db.Column(db.TIMESTAMP, server_default=current_timestamp(), onupdate=current_timestamp())
    profile_picture = db.Column(db.String(255))
    bio = db.Column(db.Text)
    register_ip = db.Column(db.String(45), nullable=False)
    is_2fa_enabled = db.Column(db.Boolean, default=False)
    totp_secret = db.Column(db.String(32))
    backup_codes = db.Column(db.Text)
    profile_private = db.Column(db.Boolean, default=False)

    # 关系定义
    media = db.relationship('Media', back_populates='user', lazy=True)
    comments = db.relationship('Comment', back_populates='author', lazy='dynamic')
    articles = db.relationship('Article', back_populates='author', lazy='dynamic')
    notifications = db.relationship('Notification', back_populates='user', lazy='dynamic')
    custom_fields = db.relationship('CustomField', back_populates='user', lazy='dynamic')
    email_subscription = db.relationship('EmailSubscription', back_populates='user', uselist=False)
    reports = db.relationship('Report', back_populates='reporter', lazy='dynamic')
    urls = db.relationship('Url', back_populates='user', lazy='dynamic')

    # 订阅关系
    subscriptions = db.relationship('UserSubscription', foreign_keys='UserSubscription.subscriber_id',
                                    back_populates='subscriber', lazy='dynamic')
    subscribers = db.relationship('UserSubscription', foreign_keys='UserSubscription.subscribed_user_id',
                                  back_populates='subscribed_user', lazy='dynamic')
    category_subscriptions = db.relationship('CategorySubscription', back_populates='subscriber', lazy='dynamic')

    # 角色关系
    roles = db.relationship('Role', secondary='user_roles', back_populates='users')

    oauth_connections = db.relationship('OAuthConnection', back_populates='user', lazy='dynamic')

    def __repr__(self):
        return f'<User {self.username}>'

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'profile_picture': self.profile_picture,
            'bio': self.bio
        }



class OAuthConnection(db.Model):
    __tablename__ = 'oauth_connections'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    provider = db.Column(db.String(50), nullable=False)
    provider_user_id = db.Column(db.String(255), nullable=False)
    access_token = db.Column(db.String(512))
    refresh_token = db.Column(db.String(512))
    expires_at = db.Column(db.DateTime)

    user = db.relationship('User', back_populates='oauth_connections')

    __table_args__ = (
        db.UniqueConstraint('provider', 'provider_user_id'),
        db.Index('idx_oauth_user', 'user_id', 'provider')
    )


class CustomField(db.Model):
    __tablename__ = 'custom_fields'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    field_name = db.Column(db.String(100), nullable=False)
    field_value = db.Column(db.Text, nullable=False)

    # 关系定义
    user = db.relationship('User', back_populates='custom_fields')

    __table_args__ = (
        db.Index('idx_user_id', 'user_id'),
    )


class EmailSubscription(db.Model):
    __tablename__ = 'email_subscriptions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    subscribed = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())

    # 关系定义
    user = db.relationship('User', back_populates='email_subscription')

    __table_args__ = (
        db.Index('idx_user_id', 'user_id'),
    )
