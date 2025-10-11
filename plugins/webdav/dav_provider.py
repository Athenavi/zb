import base64
import datetime
import logging
import os
import urllib.parse
import time

from werkzeug.http import generate_etag
from wsgidav.dav_provider import DAVProvider, DAVCollection, DAVNonCollection

from src.database import get_db
from src.models import Media, FileHash, User
from src.utils.security.jwt_handler import JWTHandler

logger = logging.getLogger(__name__)


class MediaDAVProvider(DAVProvider):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.base_dir = app.config.get('base_dir', '.')

    def get_resource_inst(self, path, environ):
        """根据路径返回资源实例"""
        # 首先进行认证检查
        if not self.is_authenticated(environ, None):
            return None

        # 获取用户信息
        user_info = environ.get('webdav.user_info')
        if not user_info:
            return None

        # 解析路径，格式为 /dav/username/filename
        path_parts = [p for p in path.strip('/').split('/') if p]

        # 如果路径只有用户名部分，返回用户根目录
        if len(path_parts) == 0:
            return UserMediaRootCollection(path, environ, user_info, self.app)
        elif len(path_parts) == 1:
            # 检查路径中的用户名是否与认证用户匹配
            if path_parts[0] != user_info['username']:
                return None  # 用户只能访问自己的目录
            return UserMediaRootCollection(path, environ, user_info, self.app)
        # 如果路径包含用户名和文件名，返回具体文件
        elif len(path_parts) >= 2:
            # 检查路径中的用户名是否与认证用户匹配
            if path_parts[0] != user_info['username']:
                return None
            filename = '/'.join(path_parts[1:])  # 处理子目录情况
            return self._get_media_file(user_info, filename, path, environ)

        return None

    def is_authenticated(self, environ, realm):
        """
        重写认证检查方法
        返回 True 表示已认证，False 表示需要认证
        """
        user_info = self._get_authenticated_user(environ)
        if user_info:
            # 将用户信息存入 environ 供后续使用
            environ['wsgidav.auth.user_name'] = user_info['username']
            environ['webdav.user_info'] = user_info
            return True

        # 认证失败，返回 False 会触发 401
        environ['wsgidav.auth.user_name'] = 'anonymous'
        return False

    @staticmethod
    def get_domain_controller():
        """返回 None 表示我们使用自定义的认证系统"""
        return None

    def _get_authenticated_user(self, environ):
        """
        综合认证方法，支持：
        1. HTTP Basic 认证（用户名 + refresh_token）
        """
        user_info = None
        # 1. 首先尝试 HTTP Basic 认证（WebDAV客户端）
        user_info = self._get_user_from_basic_auth(environ)
        if user_info:
            return user_info

        return None

    @staticmethod
    def _get_user_from_basic_auth(environ):
        """从 HTTP Basic 认证中提取用户信息"""
        auth_header = environ.get('HTTP_AUTHORIZATION', '')

        if not auth_header.startswith('Basic '):
            return None

        # 解码 Basic Auth 凭据
        try:
            auth_decoded = base64.b64decode(auth_header[6:]).decode('utf-8')
            username, password = auth_decoded.split(':', 1)
        except Exception as e:
            logger.error(f"Basic Auth decode error: {e}")
            return None

        # 验证 密码 并获取用户
        try:
            if username and password:
                with get_db() as db:
                    refresh_token = password
                    if refresh_token is not None:
                        user_id = JWTHandler.authenticate_refresh_token(refresh_token)
                        user = db.query(User).filter(User.id == user_id).first()
                        if user and user.username == username:
                            logger.info(f"Basic Auth successful for user: {user.username}")
                            # 在会话关闭前提取所需属性
                            return {
                                'id': user.id,
                                'username': user.username,
                                'vip_level': user.vip_level,
                                'created_at': user.created_at
                            }

        except Exception as e:
            logger.error(f"Refresh token validation error: {e}")

        return None

    def _get_media_file(self, user_info, filename, path, environ):
        """获取用户的媒体文件"""
        # 解码 URL 编码的文件名
        try:
            original_filename = urllib.parse.unquote(filename)
        except:
            original_filename = filename

        with get_db() as db:
            media = db.query(Media).filter(
                Media.user_id == user_info['id'],
                Media.original_filename == original_filename
            ).first()

            if media:
                file_hash = db.query(FileHash).filter(
                    FileHash.hash == media.hash
                ).first()

                if file_hash:
                    # 在数据库会话关闭前提取所有需要的属性
                    media_info = {
                        'id': media.id,
                        'original_filename': media.original_filename,
                        'hash': media.hash,
                        'created_at': media.created_at,
                        'updated_at': media.updated_at
                    }

                    file_hash_info = {
                        'hash': file_hash.hash,
                        'file_size': file_hash.file_size,
                        'mime_type': file_hash.mime_type,
                        'storage_path': file_hash.storage_path
                    }

                    return MediaFile(path, environ, media_info, file_hash_info, self.base_dir, user_info)
        return None


class UserMediaRootCollection(DAVCollection):
    """用户媒体库根目录"""

    def __init__(self, path, environ, user_info, app):
        super().__init__(path, environ)
        self.user_info = user_info
        self.app = app

    def get_member_list(self):
        """返回目录中的成员列表"""
        with get_db() as db:
            media_files = db.query(Media).filter(
                Media.user_id == self.user_info['id']
            ).all()

            members = []
            for media in media_files:
                file_hash = db.query(FileHash).filter(
                    FileHash.hash == media.hash
                ).first()

                if file_hash:
                    # 在数据库会话关闭前提取所有需要的属性
                    media_info = {
                        'id': media.id,
                        'original_filename': media.original_filename,
                        'hash': media.hash,
                        'created_at': media.created_at,
                        'updated_at': media.updated_at
                    }

                    file_hash_info = {
                        'hash': file_hash.hash,
                        'file_size': file_hash.file_size,
                        'mime_type': file_hash.mime_type,
                        'storage_path': file_hash.storage_path
                    }

                    # 安全地处理文件名编码
                    safe_filename = self._safe_filename(media.original_filename)
                    safe_path = f"{self.path.rstrip('/')}/{safe_filename}"

                    members.append(MediaFile(
                        safe_path,
                        self.environ,
                        media_info,
                        file_hash_info,
                        self.app.config.get('base_dir', '.'),
                        self.user_info
                    ))
            return members

    def get_member_names(self):
        """返回目录中的文件名列表"""
        with get_db() as db:
            media_files = db.query(Media).filter(
                Media.user_id == self.user_info['id']
            ).all()
            return [self._safe_filename(m.original_filename) for m in media_files]

    def get_member(self, name):
        """获取特定成员"""
        # 需要处理编码后的文件名与原始文件名的映射
        with get_db() as db:
            # 查找所有媒体文件，然后匹配编码后的文件名
            media_files = db.query(Media).filter(
                Media.user_id == self.user_info['id']
            ).all()

            for media in media_files:
                safe_name = self._safe_filename(media.original_filename)
                if safe_name == name:
                    file_hash = db.query(FileHash).filter(
                        FileHash.hash == media.hash
                    ).first()

                    if file_hash:
                        # 在数据库会话关闭前提取所有需要的属性
                        media_info = {
                            'id': media.id,
                            'original_filename': media.original_filename,
                            'hash': media.hash,
                            'created_at': media.created_at,
                            'updated_at': media.updated_at
                        }

                        file_hash_info = {
                            'hash': file_hash.hash,
                            'file_size': file_hash.file_size,
                            'mime_type': file_hash.mime_type,
                            'storage_path': file_hash.storage_path
                        }

                        safe_path = f"{self.path.rstrip('/')}/{safe_name}"
                        return MediaFile(
                            safe_path,
                            self.environ,
                            media_info,
                            file_hash_info,
                            self.app.config.get('base_dir', '.'),
                            self.user_info
                        )
        return None

    @staticmethod
    def _safe_filename(filename):
        """处理文件名编码问题"""
        try:
            # 尝试使用 UTF-8 编码
            return filename.encode('utf-8').decode('latin-1')
        except (UnicodeEncodeError, UnicodeDecodeError):
            # 如果失败，使用 URL 编码
            import urllib.parse
            return urllib.parse.quote(filename)

    def get_display_name(self):
        """返回集合的显示名称"""
        return f"{self.user_info['username']}'s Media Library"

    def get_creation_date(self):
        """返回集合的创建日期"""
        created_at = self.user_info.get('created_at', datetime.datetime.now())
        # 转换为时间戳（秒数）
        if isinstance(created_at, datetime.datetime):
            return created_at.timestamp()
        return time.time()

    def get_last_modified(self):
        """返回集合的最后修改时间"""
        with get_db() as db:
            latest_media = db.query(Media).filter(
                Media.user_id == self.user_info['id']
            ).order_by(Media.updated_at.desc()).first()

            if latest_media and latest_media.updated_at:
                # 转换为时间戳（秒数）
                if isinstance(latest_media.updated_at, datetime.datetime):
                    return latest_media.updated_at.timestamp()
                return latest_media.updated_at
        return time.time()

    def create_collection(self, name):
        """创建新集合（目录）"""
        # 在这个实现中，我们不支持创建子目录
        raise NotImplementedError("Creating collections is not supported")

    def create_empty_resource(self, name):
        """创建空资源"""
        # 在这个实现中，我们不支持通过 WebDAV 创建新文件
        raise NotImplementedError("Creating empty resources is not supported")

    def get_etag(self):
        """返回集合的 ETag"""
        # 基于集合内容生成 ETag
        with get_db() as db:
            count = db.query(Media).filter(Media.user_id == self.user_info['id']).count()
            latest = db.query(Media).filter(
                Media.user_id == self.user_info['id']
            ).order_by(Media.updated_at.desc()).first()

            latest_time = latest.updated_at if latest and latest.updated_at else datetime.datetime.min
            # 将 datetime 转换为时间戳
            if isinstance(latest_time, datetime.datetime):
                latest_timestamp = latest_time.timestamp()
            else:
                latest_timestamp = datetime.datetime.now().timestamp()

            etag_data = f"{count}-{latest_timestamp}"
            return generate_etag(etag_data.encode())

    def support_etag(self):
        return True

    def support_ranges(self):
        return True

    @staticmethod
    def is_readonly():
        return True  # 根目录只读

    def get_content_length(self):
        return None  # 集合没有内容长度

    def get_content_type(self):
        return "httpd/unix-directory"

    def _format_http_date(self, timestamp):
        """将时间戳格式化为兼容Windows的HTTP日期格式"""
        dt = datetime.datetime.utcfromtimestamp(timestamp)
        return dt.strftime('%a, %d %b %Y %H:%M:%S GMT')

    def get_properties(self, properties=None, **kwargs):
        """返回资源属性"""
        props = {}
        if properties is None:
            # 返回所有属性
            props.update({
                "displayname": self.get_display_name(),
                "creationdate": self._format_http_date(self.get_creation_date()),
                "getlastmodified": self._format_http_date(self.get_last_modified()),
                "getcontentlength": self.get_content_length(),
                "getcontenttype": self.get_content_type(),
                "getetag": self.get_etag(),
            })
        else:
            # 只返回请求的属性
            for prop in properties:
                if prop == "displayname":
                    props[prop] = self.get_display_name()
                elif prop == "creationdate":
                    props[prop] = self._format_http_date(self.get_creation_date())
                elif prop == "getlastmodified":
                    props[prop] = self._format_http_date(self.get_last_modified())
                elif prop == "getcontentlength":
                    props[prop] = self.get_content_length()
                elif prop == "getcontenttype":
                    props[prop] = self.get_content_type()
                elif prop == "getetag":
                    props[prop] = self.get_etag()
        return props

    def get_property_names(self, is_allprop=None, **kwargs):
        """返回支持的属性名称"""
        return [
            "displayname",
            "creationdate",
            "getlastmodified",
            "getcontentlength",
            "getcontenttype",
            "getetag",
        ]


class MediaFile(DAVNonCollection):
    def __init__(self, path, environ, media_info, file_hash_info, base_dir, user_info):
        super().__init__(path, environ)
        self.media_info = media_info
        self.file_hash_info = file_hash_info
        self.base_dir = base_dir
        self.user_info = user_info
        # 添加调试信息
        logger.debug(f"MediaFile created: {media_info.get('original_filename', 'unknown')}")
        logger.debug(f"Storage path: {file_hash_info.get('storage_path', 'unknown')}")
        logger.debug(f"Base dir: {base_dir}")

    def get_content_length(self):
        return self.file_hash_info['file_size']

    def get_content_type(self):
        return self.file_hash_info['mime_type'] or "application/octet-stream"

    def begin_write(self, content_type=None):
        raise PermissionError("Read-only resource")

    def end_write(self, with_errors):
        raise PermissionError("Read-only resource")

    def write_content(self, content, content_length=None):
        raise PermissionError("Read-only resource")

    def delete(self):
        raise PermissionError("Read-only resource")

    def copy_move_single(self, dest_path, is_move):
        raise PermissionError("Read-only resource")

    def support_etag(self):
        return True

    def support_ranges(self):
        return True

    def get_etag(self):
        return self.file_hash_info['hash']

    def get_display_name(self):
        return self.media_info['original_filename']

    def get_creation_date(self):
        """返回文件的创建日期"""
        created_at = self.media_info.get('created_at', datetime.datetime.now())
        # 转换为时间戳（秒数）
        if isinstance(created_at, datetime.datetime):
            return created_at.timestamp()
        return time.time()

    def get_last_modified(self):
        """返回文件的最后修改时间"""
        updated_at = self.media_info.get('updated_at', datetime.datetime.now())
        # 转换为时间戳（秒数）
        if isinstance(updated_at, datetime.datetime):
            return updated_at.timestamp()
        return time.time()

    def _format_http_date(self, timestamp):
        """将时间戳格式化为兼容Windows的HTTP日期格式"""
        if isinstance(timestamp, (int, float)):
            dt = datetime.datetime.utcfromtimestamp(timestamp)
        else:
            dt = timestamp
        return dt.strftime('%a, %d %b %Y %H:%M:%S GMT')

    def get_content_headers(self):
        """返回内容相关的 HTTP 头"""
        # 获取时间戳并转换为 datetime 对象用于格式化
        last_modified_timestamp = self.get_last_modified()

        return {
            'Content-Type': self.get_content_type(),
            'Content-Length': str(self.get_content_length()),
            'Last-Modified': self._format_http_date(last_modified_timestamp),
            'ETag': self.get_etag(),
            'Accept-Ranges': 'bytes',
        }

    @staticmethod
    def is_readonly():
        return True

    def get_properties(self, properties=None, **kwargs):
        """返回资源属性"""
        props = {}
        logger.debug(f"properties parameter: {properties}")
        if properties is None:
            logger.debug(f"displayname: {self.get_display_name()}")
            logger.debug(f"creationdate: {self._format_http_date(self.get_creation_date())}")
            logger.debug(f"getlastmodified: {self._format_http_date(self.get_last_modified())}")
            logger.debug(f"getcontentlength: {self.get_content_length()}")
            logger.debug(f"getcontenttype: {self.get_content_type()}")
            logger.debug(f"getetag: {self.get_etag()}")
            props.update({
                "displayname": self.get_display_name(),
                "creationdate": self._format_http_date(self.get_creation_date()),
                "getlastmodified": self._format_http_date(self.get_last_modified()),
                "getcontentlength": self.get_content_length(),
                "getcontenttype": self.get_content_type(),
                "getetag": self.get_etag(),
            })
        else:
            for prop in properties:
                logger.debug(f"Requested property: {prop}")
                if prop == "displayname":
                    logger.debug(f"displayname: {self.get_display_name()}")
                    props[prop] = self.get_display_name()
                elif prop == "creationdate":
                    logger.debug(f"creationdate: {self._format_http_date(self.get_creation_date())}")
                    props[prop] = self._format_http_date(self.get_creation_date())
                elif prop == "getlastmodified":
                    logger.debug(f"getlastmodified: {self._format_http_date(self.get_last_modified())}")
                    props[prop] = self._format_http_date(self.get_last_modified())
                elif prop == "getcontentlength":
                    logger.debug(f"getcontentlength: {self.get_content_length()}")
                    props[prop] = self.get_content_length()
                elif prop == "getcontenttype":
                    logger.debug(f"getcontenttype: {self.get_content_type()}")
                    props[prop] = self.get_content_type()
                elif prop == "getetag":
                    logger.debug(f"getetag: {self.get_etag()}")
                    props[prop] = self.get_etag()
        return props

    def get_property_names(self, is_allprop=None, **kwargs):
        """返回支持的属性名称"""
        return [
            "displayname",
            "creationdate",
            "getlastmodified",
            "getcontentlength",
            "getcontenttype",
            "getetag",
        ]

    def get_used_bytes(self):
        return self.get_content_length()

    def get_available_bytes(self):
        vip_level = self.user_info.get('vip_level', 0)
        if vip_level >= 3:
            return 100 * 1024 * 1024 * 1024
        elif vip_level >= 2:
            return 50 * 1024 * 1024 * 1024
        elif vip_level >= 1:
            return 20 * 1024 * 1024 * 1024
        else:
            return 10 * 1024 * 1024 * 1024

    def get_content(self):
        """返回文件内容流"""
        logger.debug(f"get_content: {self.path}")
        storage_path = self.file_hash_info['storage_path']
        logger.debug(f"storage_path: {storage_path}")
        # 构建完整路径
        if not os.path.isabs(storage_path):
            file_path = os.path.join(self.base_dir, storage_path)
        else:
            file_path = storage_path

        # 规范化路径
        file_path = os.path.normpath(file_path)

        logger.info(f"Opening file: {file_path}")

        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")

        if not os.access(file_path, os.R_OK):
            logger.error(f"File not readable: {file_path}")
            raise PermissionError(f"File not readable: {file_path}")

        try:
            # 使用二进制模式打开文件，确保正确读取
            file_obj = open(file_path, 'rb')
            # 验证文件大小
            file_size = os.path.getsize(file_path)
            if file_size != self.file_hash_info['file_size']:
                logger.warning(f"File size mismatch: expected {self.file_hash_info['file_size']}, got {file_size}")

            return file_obj
        except Exception as e:
            logger.error(f"Error opening file {file_path}: {e}")
            raise
