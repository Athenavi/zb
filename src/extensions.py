# extensions.py
from flask_babel import Babel
from flask_caching import Cache
from flask_cors import CORS
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_restful import Api
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

# --------------------------
# 扩展实例化
# --------------------------
db = SQLAlchemy(engine_options={"pool_pre_ping": True})  # 带连接池优化的 SQLAlchemy
cache = Cache()
login_manager = LoginManager()
csrf = CSRFProtect()
mail = Mail()
api = Api()
cors = CORS()
migrate = Migrate()
# talisman = Talisman()
# limiter = Limiter()
babel = Babel()


# --------------------------
# 扩展初始化函数
# --------------------------
def init_extensions(app):
    """集中初始化所有扩展"""
    db.init_app(app)
    cache.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    api.init_app(app)
    cors.init_app(app)
    migrate.init_app(app, db)  # 需要关联数据库实例
    # talisman.init_app(app)
    # limiter.init_app(app)
    babel.init_app(app)

    # 登录管理器额外配置
    login_manager.login_view = 'auth.login'  # 设置登录路由
