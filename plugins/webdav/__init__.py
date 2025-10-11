import logging
import os
import urllib.parse
from decimal import Decimal

from flask import Blueprint, request, Response, jsonify, send_file

from blueprints.media import get_user_storage_used
from setting import app_config
from src.database import get_db
from src.models import Media, FileHash, User
from src.utils.security.jwt_handler import JWTHandler

logger = logging.getLogger(__name__)


def register_plugin(app):
    bp = Blueprint('webdav_plugin', __name__)

    # 安全的时间戳 - 确保在 Windows FileTime 有效范围内
    SAFE_TIMESTAMP = 1325376000  # 2012-01-01 00:00:00 UTC
    SAFE_DATE_STRING = "Sun, 01 Jan 2012 00:00:00 GMT"

    class WebDAVHandler:
        """简化的 WebDAV 处理器"""

        def __init__(self, app):
            self.base_dir = app_config.base_dir or os.getcwd()
            print(f"WebDAV base dir: {self.base_dir}")

            # 初始化时不获取磁盘使用情况
            self.total_size = None
            self.used_size = None
            self.free_size = None

        def _get_disk_usage(self, request):
            """获取磁盘的总大小、已使用大小和可用大小"""
            user_info = self._authenticate_user(request)
            if user_info:
                disk_used = Decimal(user_info['disk_used'])
                disk_limit = Decimal(user_info['disk_limit'])
                disk_available = disk_limit - disk_used
                return disk_limit, disk_used, disk_available
            else:
                logger.error("无法获取用户信息")
                return None

        def handle_request(self, path, method, user_info):
            """处理 WebDAV 请求"""
            try:
                # 解析路径
                path_parts = [p for p in path.strip('/').split('/') if p]

                if len(path_parts) == 0:
                    # 根目录 - 返回目录列表
                    return self._handle_propfind_root(user_info, request)
                elif len(path_parts) == 1:
                    # 用户目录
                    if path_parts[0] != user_info['username']:
                        return self._not_found()
                    return self._handle_propfind_root(user_info, request)
                else:
                    # 文件请求
                    if path_parts[0] != user_info['username']:
                        return self._not_found()
                    filename = '/'.join(path_parts[1:])
                    return self._handle_file_request(filename, method, user_info)

            except Exception as e:
                logger.error(f"WebDAV request error: {e}", exc_info=True)
                return self._error_response(500, str(e))

        def _handle_propfind_root(self, user_info, request):
            """处理根目录的 PROPFIND 请求"""
            if self.total_size is None:
                self.total_size, self.used_size, self.free_size = self._get_disk_usage(request)

            with get_db() as db:
                media_files = db.query(Media).filter(
                    Media.user_id == user_info['id']
                ).all()

                # 生成目录列表 XML
                xml_parts = []
                xml_parts.append('<?xml version="1.0" encoding="utf-8"?>')
                xml_parts.append('<D:multistatus xmlns:D="DAV:">')

                # 添加当前目录
                xml_parts.append(f'<D:response>')
                xml_parts.append(f'<D:href>/dav/{user_info["username"]}/</D:href>')
                xml_parts.append(f'<D:propstat>')
                xml_parts.append(f'<D:prop>')
                xml_parts.append(f'<D:resourcetype><D:collection/></D:resourcetype>')
                xml_parts.append(f'<D:displayname>{user_info["username"]}\'s Media</D:displayname>')
                xml_parts.append(f'<D:creationdate>2012-01-01T00:00:00Z</D:creationdate>')
                xml_parts.append(f'<D:getlastmodified>{SAFE_DATE_STRING}</D:getlastmodified>')
                xml_parts.append(f'<D:getcontentlength>{self.total_size}</D:getcontentlength>')
                xml_parts.append(f'<D:quota-used-bytes>{self.used_size}</D:quota-used-bytes>')
                xml_parts.append(f'<D:quota-available-bytes>{self.free_size}</D:quota-available-bytes>')
                xml_parts.append(f'</D:prop>')
                xml_parts.append(f'<D:status>HTTP/1.1 200 OK</D:status>')
                xml_parts.append(f'</D:propstat>')
                xml_parts.append(f'</D:response>')

                # 添加文件
                for media in media_files:
                    file_hash = db.query(FileHash).filter(
                        FileHash.hash == media.hash
                    ).first()

                    if file_hash:
                        safe_filename = urllib.parse.quote(media.original_filename)
                        xml_parts.append(f'<D:response>')
                        xml_parts.append(f'<D:href>/dav/{user_info["username"]}/{safe_filename}</D:href>')
                        xml_parts.append(f'<D:propstat>')
                        xml_parts.append(f'<D:prop>')
                        xml_parts.append(f'<D:resourcetype/>')
                        xml_parts.append(f'<D:displayname>{media.original_filename}</D:displayname>')
                        xml_parts.append(f'<D:creationdate>2012-01-01T00:00:00Z</D:creationdate>')
                        xml_parts.append(f'<D:getlastmodified>{SAFE_DATE_STRING}</D:getlastmodified>')
                        xml_parts.append(f'<D:getcontentlength>{file_hash.file_size}</D:getcontentlength>')
                        xml_parts.append(
                            f'<D:getcontenttype>{file_hash.mime_type or "application/octet-stream"}</D:getcontenttype>')
                        xml_parts.append(f'<D:getetag>"{file_hash.hash}"</D:getetag>')
                        xml_parts.append(f'</D:prop>')
                        xml_parts.append(f'<D:status>HTTP/1.1 200 OK</D:status>')
                        xml_parts.append(f'</D:propstat>')
                        xml_parts.append(f'</D:response>')

                xml_parts.append('</D:multistatus>')
                xml_response = '\n'.join(xml_parts)

                return Response(
                    response=xml_response,
                    status=207,
                    content_type='application/xml; charset="utf-8"',
                    headers={
                        'DAV': '1, 2',
                        'Allow': 'OPTIONS, PROPFIND, GET, HEAD',
                    }
                )

        def _handle_file_request(self, filename, method, user_info):
            """处理文件请求"""
            try:
                original_filename = urllib.parse.unquote(filename)
            except:
                original_filename = filename

            with get_db() as db:
                media = db.query(Media).filter(
                    Media.user_id == user_info['id'],
                    Media.original_filename == original_filename
                ).first()

                if not media:
                    return self._not_found()

                file_hash = db.query(FileHash).filter(
                    FileHash.hash == media.hash
                ).first()

                if not file_hash:
                    return self._not_found()

                if method == 'GET':
                    return self._serve_file(file_hash, original_filename)
                elif method == 'HEAD':
                    return self._file_headers(file_hash, original_filename)
                elif method == 'PROPFIND':
                    return self._handle_propfind_file(file_hash, media, user_info, request)
                else:
                    return self._method_not_allowed()

        def _serve_file(self, file_hash, filename):
            """提供文件下载"""
            storage_path = file_hash.storage_path
            if not os.path.isabs(storage_path):
                file_path = os.path.join(self.base_dir, storage_path)
            else:
                file_path = storage_path

            file_path = os.path.normpath(file_path)

            if not os.path.exists(file_path):
                return self._not_found()

            try:
                # 使用 Flask 的 send_file 替代手动文件操作
                return send_file(
                    file_path,
                    as_attachment=False,
                    download_name=filename,
                    mimetype=file_hash.mime_type or 'application/octet-stream',
                    last_modified=SAFE_TIMESTAMP,
                    etag=file_hash.hash
                )
            except Exception as e:
                logger.error(f"Error serving file {file_path}: {e}")
                return self._error_response(500, "File serving error")

        @staticmethod
        def _file_headers(file_hash, filename):
            """返回文件头部信息"""
            return Response(
                status=200,
                headers={
                    'Content-Type': file_hash.mime_type or 'application/octet-stream',
                    'Content-Length': str(file_hash.file_size),
                    'Last-Modified': SAFE_DATE_STRING,
                    'ETag': f'"{file_hash.hash}"',
                    'Accept-Ranges': 'bytes',
                }
            )

        def _handle_propfind_file(self, file_hash, media, user_info, request):
            """处理文件的 PROPFIND 请求"""
            if self.total_size is None:
                self.total_size, self.used_size, self.free_size = self._get_disk_usage(request)

            safe_filename = urllib.parse.quote(media.original_filename)

            xml_parts = []
            xml_parts.append('<?xml version="1.0" encoding="utf-8"?>')
            xml_parts.append('<D:multistatus xmlns:D="DAV:">')
            xml_parts.append(f'<D:response>')
            xml_parts.append(f'<D:href>/dav/{user_info["username"]}/{safe_filename}</D:href>')
            xml_parts.append(f'<D:propstat>')
            xml_parts.append(f'<D:prop>')
            xml_parts.append(f'<D:resourcetype/>')
            xml_parts.append(f'<D:displayname>{media.original_filename}</D:displayname>')
            xml_parts.append(f'<D:creationdate>2012-01-01T00:00:00Z</D:creationdate>')
            xml_parts.append(f'<D:getlastmodified>{SAFE_DATE_STRING}</D:getlastmodified>')
            xml_parts.append(f'<D:getcontentlength>{file_hash.file_size}</D:getcontentlength>')
            xml_parts.append(
                f'<D:getcontenttype>{file_hash.mime_type or "application/octet-stream"}</D:getcontenttype>')
            xml_parts.append(f'<D:getetag>"{file_hash.hash}"</D:getetag>')
            xml_parts.append(f'</D:prop>')
            xml_parts.append(f'<D:status>HTTP/1.1 200 OK</D:status>')
            xml_parts.append(f'</D:propstat>')
            xml_parts.append(f'</D:response>')
            xml_parts.append('</D:multistatus>')

            xml_response = '\n'.join(xml_parts)

            return Response(
                response=xml_response,
                status=207,
                content_type='application/xml; charset="utf-8"',
                headers={
                    'DAV': '1, 2',
                }
            )

        @staticmethod
        def _authenticate_user(request):
            """用户认证"""
            # 检查 Basic Auth
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Basic '):
                try:
                    import base64
                    auth_decoded = base64.b64decode(auth_header[6:]).decode('utf-8')
                    username, refresh_token = auth_decoded.split(':', 1)

                    with get_db() as db:
                        user_id = JWTHandler.authenticate_refresh_token(refresh_token)
                        user = db.query(User).filter(User.id == user_id).first()

                        if user and user.username == username:
                            return {
                                'id': user.id,
                                'username': user.username,
                                'vip_level': user.vip_level,
                                'created_at': user.created_at,
                                'disk_used': get_user_storage_used(user.id),
                                'disk_limit': app_config.USER_FREE_STORAGE_LIMIT,
                            }
                except Exception as e:
                    logger.error(f"Basic Auth error: {e}")

            return None

        @staticmethod
        def _not_found():
            return Response(
                response="Not Found",
                status=404,
                content_type='text/plain'
            )

        @staticmethod
        def _method_not_allowed():
            return Response(
                response="Method Not Allowed",
                status=405,
                content_type='text/plain'
            )

        @staticmethod
        def _error_response(status, message):
            return Response(
                response=message,
                status=status,
                content_type='text/plain'
            )

    # 创建处理器实例
    handler = WebDAVHandler(app)

    # WebDAV 路由
    @bp.route('/dav/', defaults={'path': ''},
              methods=['OPTIONS', 'GET', 'HEAD', 'PROPFIND'])
    @bp.route('/dav/<path:path>',
              methods=['OPTIONS', 'GET', 'HEAD', 'PROPFIND'])
    def webdav_handler(path=''):
        # 用户认证
        user_info = handler._authenticate_user(request)
        if not user_info:
            return Response(
                response="Authentication required",
                status=401,
                headers={'WWW-Authenticate': 'Basic realm="WebDAV"'},
                content_type='text/plain'
            )

        # 处理 OPTIONS 请求
        if request.method == 'OPTIONS':
            return Response(
                status=200,
                headers={
                    'DAV': '1, 2',
                    'Allow': 'OPTIONS, GET, HEAD, PROPFIND',
                    'MS-Author-Via': 'DAV',
                }
            )

        # 处理其他 WebDAV 请求
        return handler.handle_request(path, request.method, user_info)

    # WebDAV 发现页面
    @bp.route('/dav/')
    def webdav_root():
        return """
        <html>
            <head>
                <title>WebDAV Media Server</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; }
                    h1 { color: #333; }
                    .info { background: #f5f5f5; padding: 15px; border-radius: 5px; }
                </style>
            </head>
            <body>
                <h1>WebDAV Media Server</h1>
                <div class="info">
                    <p>Your media files are available via WebDAV protocol.</p>
                    <p><strong>Authentication methods:</strong></p>
                    <ul>
                        <li>Browser: Automatic Cookie-based authentication</li>
                        <li>WebDAV Clients: HTTP Basic Auth (username + refresh_token)</li>
                    </ul>
                    <p><strong>Supported methods:</strong> OPTIONS, GET, HEAD, PROPFIND</p>
                    <p><a href="/dav/">Browse your files via WebDAV</a></p>
                </div>
            </body>
        </html>
        """

    # 健康检查端点
    @bp.route('/dav/health')
    def webdav_health():
        return jsonify({
            "status": "healthy",
            "service": "webdav",
            "timestamp": SAFE_TIMESTAMP
        })

    plugin = type('Plugin', (), {
        'name': 'WebDAV Media Server',
        'version': '2.0.0',
        'description': '轻量级 WebDAV 媒体服务器，支持只读访问用户媒体库',
        'author': 'System',
        'blueprint': bp,
        'enabled': True,
        'handler': handler
    })()

    return plugin
