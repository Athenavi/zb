# extensions.py

import flask_monitoringdashboard as dashboard
from flask_babel import Babel
from flask_caching import Cache
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_principal import Principal
from flask_restful import Api
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

# --------------------------
# 扩展实例化
# --------------------------
db = SQLAlchemy(
    engine_options={
        # 基础连接池设置
        "pool_size": 5,  # 常驻连接数
        "max_overflow": 10,  # 最大临时连接数
        "pool_recycle": 300,  # 5分钟回收连接(需小于数据库的wait_timeout)
        "pool_timeout": 15,  # 获取连接超时时间(秒)

        # 连接健康检查
        "pool_pre_ping": True,  # 执行前检查连接活性

        # 服务端连接保持
        "connect_args": {
            "options": "-c statement_timeout=30s"  # PostgreSQL查询超时
            # MySQL需在连接参数添加：connect_timeout=15
        }
    }
)
cache = Cache()
login_manager = LoginManager()
jwt = JWTManager()
csrf = CSRFProtect()
mail = Mail()
api = Api()
cors = CORS()
migrate = Migrate()
# talisman = Talisman()
# limiter = Limiter()
babel = Babel()
principal = Principal()

# 初始化 SocketIO
# 明确指定使用 gevent 异步模式，避免与 eventlet 冲突
socketio = SocketIO(cors_allowed_origins="*", async_mode='gevent')

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
    principal.init_app(app)
    # 登录管理器额外配置
    login_manager.login_view = 'auth.login'
    login_manager.login_message = '请先登录'

    # 初始化SocketIO
    # 让 Flask-SocketIO 自动选择最佳异步模式
    socketio.init_app(app)

    # JWT配置
    jwt.init_app(app)

    # 初始化直播服务
    from src.services.live import LiveStreamService
    live_service = LiveStreamService(app)
    # 将 live_service 添加到 app 对象上，避免导入问题
    app.live_service = live_service
    
    # 配置监控面板
    try:
        dashboard.config.init_from(file='dashboard_config.cfg')
        # 绑定应用
        dashboard.bind(app)
        if hasattr(dashboard, 'blueprint'):
            csrf.exempt(dashboard.blueprint)
    except Exception as e:
        app.logger.error(f"Failed to initialize Flask-MonitoringDashboard: {str(e)}")
        # 即使监控面板初始化失败，也不影响主应用运行