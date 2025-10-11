import io
import time
import datetime
import re

from flask import Blueprint, request, Response
from wsgidav.wsgidav_app import WsgiDAVApp

from .dav_provider import MediaDAVProvider


def register_plugin(app):
    bp = Blueprint('webdav_plugin', __name__)

    # WebDAV 配置 - 修复时间处理问题
    config = {
        "provider_mapping": {
            "/dav": MediaDAVProvider(app)
        },
        "verbose": 3,
        "logging": {
            "enable_loggers": [],
        },
        "property_manager": True,
        "lock_storage": False,
        # 使用自定义认证
        "http_authenticator": {
            "accept_basic": True,
            "accept_digest": False,
            "default_to_digest": False,
        },
        "hotfixes": {
            "emulate_win32_lastmod": False,  # 禁用win32模拟，使用标准格式
            "win_accept_anonymous_creator": True,
            "win_accept_anonymous_owner": True,
        },
        # 启用简单目录列表
        "simple_dc": {
            "user_mapping": {
                "*": True  # 允许所有用户，因为我们有自己的认证
            }
        }
    }

    # 创建 WebDAV 应用
    dav_app = WsgiDAVApp(config)

    # 修复日期格式的中间件
    class DateFixMiddleware:
        def __init__(self, app):
            self.app = app
            # RFC 1123 日期格式正则表达式
            self.rfc1123_pattern = re.compile(
                r'^\w{3}, \d{2} \w{3} \d{4} \d{2}:\d{2}:\d{2} GMT$'
            )

        def _is_rfc1123_format(self, date_str):
            """检查是否为 RFC 1123 格式"""
            return bool(self.rfc1123_pattern.match(date_str))

        def _is_iso_format(self, date_str):
            """检查是否为 ISO 8601 格式"""
            return 'T' in date_str and ('Z' in date_str or '+' in date_str)

        def _fix_date_header(self, value):
            """修复日期头格式"""
            if value is None:
                return datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')

            # 如果已经是 RFC 1123 格式，直接返回
            if isinstance(value, str) and self._is_rfc1123_format(value):
                return value

            try:
                # 处理时间戳
                if isinstance(value, (int, float)):
                    dt = datetime.datetime.utcfromtimestamp(value)
                    return dt.strftime('%a, %d %b %Y %H:%M:%S GMT')

                # 处理 datetime 对象
                if isinstance(value, datetime.datetime):
                    return value.strftime('%a, %d %b %Y %H:%M:%S GMT')

                # 处理 ISO 8601 格式字符串
                if isinstance(value, str) and self._is_iso_format(value):
                    # 清理 ISO 字符串
                    iso_str = value.replace('Z', '+00:00')
                    dt = datetime.datetime.fromisoformat(iso_str)
                    return dt.strftime('%a, %d %b %Y %H:%M:%S GMT')

                # 处理其他字符串格式，尝试解析
                if isinstance(value, str):
                    try:
                        # 尝试常见日期格式
                        formats = [
                            '%a, %d %b %Y %H:%M:%S %Z',
                            '%Y-%m-%d %H:%M:%S',
                            '%Y-%m-%dT%H:%M:%S',
                            '%Y-%m-%dT%H:%M:%SZ',
                            '%Y-%m-%dT%H:%M:%S.%fZ'
                        ]
                        for fmt in formats:
                            try:
                                dt = datetime.datetime.strptime(value, fmt)
                                return dt.strftime('%a, %d %b %Y %H:%M:%S GMT')
                            except ValueError:
                                continue
                    except:
                        pass

                # 如果无法解析，使用当前时间
                app.logger.warning(f"无法解析日期格式: {value}, 使用当前时间")
                return datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')

            except Exception as e:
                app.logger.warning(f"日期格式修复失败: {e}, 值: {value}")
                return datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')

        def __call__(self, environ, start_response):
            def custom_start_response(status, headers, exc_info=None):
                # 修复日期头
                new_headers = []
                for name, value in headers:
                    if name.lower() in ('last-modified', 'date', 'creationdate'):
                        fixed_value = self._fix_date_header(value)
                        new_headers.append((name, fixed_value))
                    else:
                        new_headers.append((name, value))
                return start_response(status, new_headers, exc_info)

            return self.app(environ, custom_start_response)

    # 包装DAV应用
    dav_app = DateFixMiddleware(dav_app)

    # 将 WebDAV 挂载到 Flask 路由
    @bp.route('/dav/', defaults={'path': ''},
              methods=['GET', 'PUT', 'DELETE', 'PROPFIND', 'PROPPATCH', 'MKCOL', 'COPY', 'MOVE', 'LOCK', 'UNLOCK'])
    @bp.route('/dav/<path:path>',
              methods=['GET', 'PUT', 'DELETE', 'PROPFIND', 'PROPPATCH', 'MKCOL', 'COPY', 'MOVE', 'LOCK', 'UNLOCK'])
    def webdav_handler(path=''):
        try:
            # 构建正确的 PATH_INFO
            environ = request.environ.copy()

            # 确保路径格式正确
            dav_path = f'/dav/{path}' if path else '/dav/'
            environ['PATH_INFO'] = dav_path

            # 记录请求信息用于调试
            app.logger.debug(f"WebDAV Request: {request.method} {dav_path}")

            # 处理 WebDAV 请求
            response_headers = []
            response_status = [200]
            response_body = io.BytesIO()

            # 创建日期修复器实例用于 start_response
            date_fixer = DateFixMiddleware(None)

            def start_response(status, headers, exc_info=None):
                response_status[0] = status
                # 修复日期头
                fixed_headers = []
                for name, value in headers:
                    if name.lower() in ('last-modified', 'date', 'creationdate'):
                        fixed_value = date_fixer._fix_date_header(value)
                        fixed_headers.append((name, fixed_value))
                    else:
                        fixed_headers.append((name, value))
                response_headers.extend(fixed_headers)
                return response_body.write

            # 执行 WebDAV 应用
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

            return response

        except Exception as e:
            app.logger.error(f"WebDAV error: {str(e)}", exc_info=True)
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
                <p><a href="/dav/">Browse your files</a></p>
            </body>
        </html>
        """

    plugin = type('Plugin', (), {
        'name': 'WebDAV Media Mount',
        'version': '1.0.0',
        'description': 'WebDAV 协议支持用户媒体库，支持WebDAV客户端Basic认证',
        'author': 'System',
        'blueprint': bp,
        'enabled': True
    })()

    return plugin
