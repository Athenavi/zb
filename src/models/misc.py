from . import db


class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    event_date = db.Column(db.TIMESTAMP, nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'event_date': self.event_date.isoformat() if self.event_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Report(db.Model):
    __tablename__ = 'reports'
    __abstract__ = False
    __table_args__ = (
        db.Index('idx_reports_reported_by', 'reported_by'),
    )

    id = db.Column(db.Integer, primary_key=True)
    reported_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content_type = db.Column(db.Integer, nullable=False)
    content_id = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())

    # 关系定义
    reporter = db.relationship('User', back_populates='reports')

    def to_dict(self):
        return {
            'id': self.id,
            'reported_by': self.reported_by,
            'content_type': self.content_type,
            'content_id': self.content_id,
            'reason': self.reason,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Url(db.Model):
    __tablename__ = 'urls'
    id = db.Column(db.Integer, primary_key=True)
    long_url = db.Column(db.String(255), nullable=False)
    short_url = db.Column(db.String(10), nullable=False, unique=True)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # 关系定义
    user = db.relationship('User', back_populates='urls')

    __table_args__ = (
        db.Index('idx_user_id_url', 'user_id'),
        db.UniqueConstraint('user_id', 'long_url', name='uq_user_long_url')
    )

    def to_dict(self):
        return {
            'id': self.id,
            'long_url': self.long_url,
            'short_url': self.short_url,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'user_id': self.user_id
        }


class SearchHistory(db.Model):
    __tablename__ = 'search_history'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, nullable=False)
    keyword = db.Column(db.String(255), nullable=False)
    results_count = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'keyword': self.keyword,
            'results_count': self.results_count,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
