import io

from flask import Blueprint, request, Response
from wsgidav.wsgidav_app import WsgiDAVApp

from .dav_provider import MediaDAVProvider


def register_plugin(app):
    bp = Blueprint('webdav_plugin', __name__)

    # WebDAV 配置 - 完全禁用 WsgiDAV 内置认证
    config = {
        "provider_mapping": {
            "/dav": MediaDAVProvider(app)
        },
        "verbose": 1,
        "logging": {
            "enable_loggers": [],
        },
        "property_manager": True,
        "lock_storage": False,
        # 关键：完全禁用 WsgiDAV 内置认证
        "http_authenticator": {
            "accept_basic": True,    # 允许 Basic 认证
            "accept_digest": False,  # 禁用 Digest 认证
            "default_to_digest": False,
            # 禁用域控制器
            "domain_controller": None,
        },
        "hotfixes": {
            "emulate_win32_lastmod": False,
        },
        # 添加简单域控制器配置，避免错误
        "simple_dc": {
            "user_mapping": {
                "*": True  # 允许所有用户，因为我们有自己的认证
            }
        }
    }

    # 创建 WebDAV 应用
    dav_app = WsgiDAVApp(config)

    # 将 WebDAV 挂载到 Flask 路由
    @bp.route('/dav/<path:path>',
              methods=['GET', 'PUT', 'DELETE', 'PROPFIND', 'PROPPATCH', 'MKCOL', 'COPY', 'MOVE', 'LOCK', 'UNLOCK'])
    def webdav_handler(path=''):
        # 构建正确的 PATH_INFO
        environ = request.environ.copy()
        if path:
            environ['PATH_INFO'] = f'/dav/{path}'
        else:
            environ['PATH_INFO'] = '/dav/'

        # 处理 WebDAV 请求
        response_headers = []
        response_status = [200]
        response_body = io.BytesIO()

        def start_response(status, headers, exc_info=None):
            """正确的 start_response 实现"""
            response_status[0] = status
            response_headers.extend(headers)
            return response_body.write

        # 执行 WebDAV 应用
        try:
            result = dav_app(environ, start_response)

            # 收集响应内容
            for data in result:
                if data:
                    response_body.write(data)
            if hasattr(result, 'close'):
                result.close()

            # 构建 Flask 响应
            response = Response(
                response=response_body.getvalue(),
                status=response_status[0],
                headers=dict(response_headers)
            )

            # 如果认证失败，添加 Basic Auth 质询头
            if response_status[0] == 401:
                response.headers['WWW-Authenticate'] = 'Basic realm="WebDAV Media Server"'

            return response

        except Exception as e:
            app.logger.error(f"WebDAV error: {str(e)}")
            return Response(
                response=f"WebDAV Error: {str(e)}",
                status=500,
                content_type='text/plain'
            )

    # 添加 WebDAV 发现端点
    @bp.route('/dav/')
    def webdav_root():
        """WebDAV 根目录发现"""
        return """
        <html>
            <head><title>WebDAV Media Server</title></head>
            <body>
                <h1>WebDAV Media Server</h1>
                <p>Your media files are available via WebDAV protocol.</p>
                <p>Authentication methods:</p>
                <ul>
                    <li>Browser: Automatic Cookie-based authentication</li>
                    <li>WebDAV Clients: HTTP Basic Auth (username + refresh_token)</li>
                </ul>
            </body>
        </html>
        """

    plugin = type('Plugin', (), {
        'name': 'WebDAV Media Mount',
        'version': '1.0.0',
        'description': 'WebDAV 协议支持用户媒体库，支持浏览器Cookie和WebDAV客户端Basic认证',
        'author': 'System',
        'blueprint': bp,
        'enabled': True
    })()

    return plugin