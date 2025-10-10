import base64
import datetime
from pathlib import Path

from werkzeug.http import generate_etag
from wsgidav.dav_provider import DAVProvider, DAVCollection, DAVNonCollection

from src.database import get_db
from src.models import Media, FileHash, User
from src.utils.security.jwt_handler import JWTHandler


class MediaDAVProvider(DAVProvider):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.base_dir = app.config.get('base_dir', '.')

    def get_resource_inst(self, path, environ):
        """根据路径返回资源实例"""
        # 从请求中获取用户认证（支持多种方式）
        user_info = self._get_authenticated_user(environ)
        if not user_info:
            # 认证失败，返回 None 会触发 401
            environ['wsgidav.auth.user_name'] = 'anonymous'
            return None

        # 将用户信息存入 environ 供后续使用
        environ['wsgidav.auth.user_name'] = user_info['username']
        environ['webdav.user_info'] = user_info

        # 解析路径，格式为 /dav/username/filename
        path_parts = [p for p in path.strip('/').split('/') if p]

        # 如果路径只有用户名部分，返回用户根目录
        if len(path_parts) == 1:
            return UserMediaRootCollection(path, environ, user_info, self.app)
        # 如果路径包含用户名和文件名，返回具体文件
        elif len(path_parts) >= 2:
            # 检查路径中的用户名是否与认证用户匹配
            if path_parts[0] != user_info['username']:
                return None  # 用户只能访问自己的目录
            filename = path_parts[-1]
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
        2. Cookie JWT 认证（浏览器访问）
        """
        user_info = None

        # 1. 首先尝试 HTTP Basic 认证（WebDAV客户端）
        user_info = self._get_user_from_basic_auth(environ)
        if user_info:
            return user_info

        # 2. 尝试 Cookie JWT 认证（浏览器访问）
        user_info = self._get_user_from_cookie(environ)
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
            username, refresh_token = auth_decoded.split(':', 1)
        except Exception as e:
            print(f"Basic Auth decode error: {e}")
            return None

        # 验证 refresh_token 并获取用户
        try:
            payload = JWTHandler.decode_token(refresh_token)
            user_id = payload.get('user_id')
            if not user_id:
                return None

            with get_db() as db:
                user = db.query(User).filter(User.id == user_id).first()
                # 验证用户名是否匹配
                if user and user.username == username:
                    print(f"Basic Auth successful for user: {username}")
                    # 在会话关闭前提取所需属性
                    return {
                        'id': user.id,
                        'username': user.username,
                        'vip_level': user.vip_level,
                        'created_at': user.created_at
                    }
                else:
                    print(f"Basic Auth failed: username mismatch")

        except Exception as e:
            print(f"Refresh token validation error: {e}")

        return None

    @staticmethod
    def _get_user_from_cookie(environ):
        """从 Cookie 中提取用户信息（浏览器访问）"""
        from flask import request as flask_request

        # 使用 Flask 的请求对象来获取 cookie
        jwt_token = flask_request.cookies.get('jwt')
        if not jwt_token:
            return None

        try:
            payload = JWTHandler.decode_token(jwt_token)
            user_id = payload.get('user_id')
            if user_id:
                with get_db() as db:
                    user = db.query(User).filter(User.id == user_id).first()
                    if user:
                        print(f"Cookie Auth successful for user: {user.username}")
                        # 在会话关闭前提取所需属性
                        return {
                            'id': user.id,
                            'username': user.username,
                            'vip_level': user.vip_level,
                            'created_at': user.created_at
                        }
        except Exception as e:
            print(f"Cookie JWT validation error: {e}")

        return None

    def _get_media_file(self, user_info, filename, path, environ):
        """获取用户的媒体文件"""
        with get_db() as db:
            media = db.query(Media).filter(
                Media.user_id == user_info['id'],
                Media.original_filename == filename
            ).first()

            if media:
                file_hash = db.query(FileHash).filter(
                    FileHash.hash == media.hash
                ).first()

                if file_hash:
                    return MediaFile(path, environ, media, file_hash, self.base_dir, user_info)
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
                    members.append(MediaFile(
                        f"{self.path}/{media.original_filename}",
                        self.environ,
                        media,
                        file_hash,
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
            return [m.original_filename for m in media_files]

    def get_member(self, name):
        """获取特定成员"""
        with get_db() as db:
            media = db.query(Media).filter(
                Media.user_id == self.user_info['id'],
                Media.original_filename == name
            ).first()

            if media:
                file_hash = db.query(FileHash).filter(
                    FileHash.hash == media.hash
                ).first()

                if file_hash:
                    return MediaFile(
                        f"{self.path}/{name}",
                        self.environ,
                        media,
                        file_hash,
                        self.app.config.get('base_dir', '.'),
                        self.user_info
                    )
        return None

    def get_display_name(self):
        """返回集合的显示名称"""
        return f"{self.user_info['username']}'s Media Library"

    def get_creation_date(self):
        """返回集合的创建日期"""
        return self.user_info.get('created_at', datetime.datetime.now())

    def get_last_modified(self):
        """返回集合的最后修改时间"""
        # 返回最新文件的修改时间
        with get_db() as db:
            latest_media = db.query(Media).filter(
                Media.user_id == self.user_info['id']
            ).order_by(Media.updated_at.desc()).first()

            if latest_media and latest_media.updated_at:
                return latest_media.updated_at
        return datetime.datetime.now()

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
            etag_data = f"{count}-{latest_time.timestamp()}"
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


class MediaFile(DAVNonCollection):
    def __init__(self, path, environ, media, file_hash, base_dir, user_info):
        super().__init__(path, environ)
        self.media = media
        self.file_hash = file_hash
        self.base_dir = base_dir
        self.user_info = user_info

    def get_content_length(self):
        return self.file_hash.file_size

    def get_content_type(self):
        return self.file_hash.mime_type or "application/octet-stream"

    def get_content(self):
        """返回文件内容流"""
        file_path = Path(self.base_dir) / self.file_hash.storage_path
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        return open(file_path, 'rb')

    def begin_write(self, content_type=None):
        """开始写入文件"""
        raise PermissionError("Read-only resource")

    def end_write(self, with_errors):
        """完成文件写入"""
        raise PermissionError("Read-only resource")

    def write_content(self, content, content_length=None):
        """写入文件内容"""
        raise PermissionError("Read-only resource")

    def delete(self):
        """删除文件"""
        raise PermissionError("Read-only resource")

    def copy_move_single(self, dest_path, is_move):
        """复制或移动文件"""
        raise PermissionError("Read-only resource")

    def support_etag(self):
        return True

    def support_ranges(self):
        return True

    def get_etag(self):
        return self.file_hash.hash

    def get_display_name(self):
        return self.media.original_filename

    def get_creation_date(self):
        return self.media.created_at if hasattr(self.media, 'created_at') else datetime.datetime.now()

    def get_last_modified(self):
        return self.media.updated_at if hasattr(self.media, 'updated_at') else datetime.datetime.now()

    @staticmethod
    def is_readonly():
        return True  # 文件只读

    def get_properties(self, **kwargs):
        """返回资源属性"""
        return {
            "displayname": self.get_display_name(),
            "creationdate": self.get_creation_date(),
            "getlastmodified": self.get_last_modified(),
            "getcontentlength": self.get_content_length(),
            "getcontenttype": self.get_content_type(),
            "getetag": self.get_etag(),
        }

    def get_property_names(self, **kwargs):
        """返回支持的属性名称"""
        return [
            "displayname",
            "creationdate",
            "getlastmodified",
            "getcontentlength",
            "getcontenttype",
            "getetag",
        ]

    @staticmethod
    def support_locks():
        """是否支持锁"""
        return False

    def get_used_bytes(self):
        """返回已用字节数"""
        return self.get_content_length()

    def get_available_bytes(self):
        """返回可用字节数"""
        # 根据用户 VIP 等级返回不同的可用空间
        vip_level = self.user_info.get('vip_level', 0)
        if vip_level >= 3:
            return 100 * 1024 * 1024 * 1024  # 100GB for VIP3
        elif vip_level >= 2:
            return 50 * 1024 * 1024 * 1024  # 50GB for VIP2
        elif vip_level >= 1:
            return 20 * 1024 * 1024 * 1024  # 20GB for VIP1
        else:
            return 10 * 1024 * 1024 * 1024  # 10GB for regular users