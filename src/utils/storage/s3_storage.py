import os
from typing import Optional
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError


class S3Storage:
    """
    S3兼容存储实现类
    支持AWS S3、MinIO、阿里云OSS、腾讯云COS等S3兼容服务
    """
    
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """初始化应用配置"""
        self.app = app
        
        # S3配置
        self.s3_enabled = app.config.get('S3_ENABLED', False)
        if not self.s3_enabled:
            return
            
        self.s3_endpoint = app.config.get('S3_ENDPOINT_URL')
        self.s3_access_key = app.config.get('S3_ACCESS_KEY')
        self.s3_secret_key = app.config.get('S3_SECRET_KEY')
        self.s3_bucket_name = app.config.get('S3_BUCKET_NAME', 'media-bucket')
        self.s3_region = app.config.get('S3_REGION', 'us-east-1')
        self.s3_use_ssl = app.config.get('S3_USE_SSL', True)
        self.s3_signature_version = app.config.get('S3_SIGNATURE_VERSION', 's3v4')
        
        # 创建S3客户端
        self.s3_client = self._create_s3_client()
    
    def _create_s3_client(self):
        """创建S3客户端"""
        if not self.s3_enabled:
            return None
            
        # 检查必要的配置
        if not all([self.s3_access_key, self.s3_secret_key, self.s3_bucket_name]):
            raise ValueError("S3配置不完整：缺少访问密钥、密钥或存储桶名称")
        
        # 配置S3客户端参数
        client_config = {
            'aws_access_key_id': self.s3_access_key,
            'aws_secret_access_key': self.s3_secret_key,
            'region_name': self.s3_region,
        }
        
        # 如果有自定义端点（如MinIO），添加endpoint_url
        if self.s3_endpoint:
            client_config['endpoint_url'] = self.s3_endpoint
            client_config['use_ssl'] = self.s3_use_ssl
            client_config['verify'] = False  # 对于自签名证书
        
        # 创建S3客户端
        s3_client = boto3.client('s3', **client_config)
        
        # 验证连接
        try:
            s3_client.head_bucket(Bucket=self.s3_bucket_name)
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                # 存储桶不存在，尝试创建
                try:
                    if self.s3_region == 'us-east-1':
                        # us-east-1区域创建存储桶不需要LocationConstraint
                        s3_client.create_bucket(Bucket=self.s3_bucket_name)
                    else:
                        s3_client.create_bucket(
                            Bucket=self.s3_bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': self.s3_region}
                        )
                    print(f"S3存储桶 {self.s3_bucket_name} 创建成功")
                except ClientError as create_error:
                    print(f"无法创建S3存储桶: {create_error}")
                    raise
            else:
                print(f"无法访问S3存储桶: {e}")
                raise
        
        return s3_client
    
    def save_file(self, file_hash: str, file_data: bytes, original_filename: str) -> str:
        """
        保存文件到S3存储
        返回存储路径（格式：s3://bucket/key）
        """
        if not self.s3_enabled:
            # 如果S3未启用，使用本地存储
            return self._save_local_file(file_hash, file_data, original_filename)
        
        try:
            # 构建S3对象键（路径）
            # 使用哈希的前两个字符作为目录，提高性能
            hash_prefix = file_hash[:2]
            key = f"hashed_files/{hash_prefix}/{file_hash}"
            
            # 上传文件到S3
            self.s3_client.put_object(
                Bucket=self.s3_bucket_name,
                Key=key,
                Body=file_data,
                Metadata={
                    'original_filename': original_filename,
                    'file_hash': file_hash
                }
            )
            
            # 返回S3路径格式
            storage_path = f"s3://{self.s3_bucket_name}/{key}"
            return storage_path
            
        except Exception as e:
            print(f"S3文件上传失败: {str(e)}")
            raise
    
    def load_file(self, storage_path: str) -> Optional[bytes]:
        """
        从S3存储加载文件
        """
        if not self.s3_enabled:
            # 如果S3未启用，从本地加载
            return self._load_local_file(storage_path)
        
        try:
            if storage_path.startswith('s3://'):
                # 解析S3路径
                parsed = urlparse(storage_path)
                bucket = parsed.netloc
                key = parsed.path.lstrip('/')
                
                # 从S3下载文件
                response = self.s3_client.get_object(Bucket=bucket, Key=key)
                file_data = response['Body'].read()
                return file_data
            else:
                # 可能是本地路径，尝试从本地加载
                return self._load_local_file(storage_path)
                
        except ClientError as e:
            print(f"从S3加载文件失败: {str(e)}")
            return None
        except Exception as e:
            print(f"从S3加载文件失败: {str(e)}")
            return None
    
    def delete_file(self, storage_path: str) -> bool:
        """
        从S3存储删除文件
        """
        if not self.s3_enabled:
            # 如果S3未启用，删除本地文件
            return self._delete_local_file(storage_path)
        
        try:
            if storage_path.startswith('s3://'):
                # 解析S3路径
                parsed = urlparse(storage_path)
                bucket = parsed.netloc
                key = parsed.path.lstrip('/')
                
                # 从S3删除文件
                self.s3_client.delete_object(Bucket=bucket, Key=key)
                return True
            else:
                # 可能是本地路径，尝试删除本地文件
                return self._delete_local_file(storage_path)
                
        except ClientError as e:
            print(f"从S3删除文件失败: {str(e)}")
            return False
        except Exception as e:
            print(f"从S3删除文件失败: {str(e)}")
            return False
    
    def file_exists(self, storage_path: str) -> bool:
        """
        检查S3中文件是否存在
        """
        if not self.s3_enabled:
            # 如果S3未启用，检查本地文件
            return self._local_file_exists(storage_path)
        
        try:
            if storage_path.startswith('s3://'):
                # 解析S3路径
                parsed = urlparse(storage_path)
                bucket = parsed.netloc
                key = parsed.path.lstrip('/')
                
                # 检查S3中文件是否存在
                self.s3_client.head_object(Bucket=bucket, Key=key)
                return True
            else:
                # 可能是本地路径，检查本地文件
                return self._local_file_exists(storage_path)
                
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                print(f"检查S3文件存在性失败: {str(e)}")
                return False
        except Exception as e:
            print(f"检查S3文件存在性失败: {str(e)}")
            return False
    
    def get_file_url(self, storage_path: str, expires: int = 3600) -> Optional[str]:
        """
        生成S3文件的预签名URL（用于临时访问）
        """
        if not self.s3_enabled:
            return None  # 本地存储无法生成预签名URL
        
        try:
            if storage_path.startswith('s3://'):
                # 解析S3路径
                parsed = urlparse(storage_path)
                bucket = parsed.netloc
                key = parsed.path.lstrip('/')
                
                # 生成预签名URL
                url = self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket, 'Key': key},
                    ExpiresIn=expires
                )
                return url
            else:
                return None
                
        except Exception as e:
            print(f"生成S3预签名URL失败: {str(e)}")
            return None
    
    def _save_local_file(self, file_hash: str, file_data: bytes, original_filename: str) -> str:
        """保存文件到本地存储（兼容模式）"""
        hash_prefix = file_hash[:2]
        hash_subdir = os.path.join('hashed_files', hash_prefix)
        os.makedirs(hash_subdir, exist_ok=True)

        storage_path = os.path.join(hash_subdir, file_hash)
        with open(storage_path, 'wb') as f:
            f.write(file_data)

        return storage_path
    
    def _load_local_file(self, storage_path: str) -> Optional[bytes]:
        """从本地存储加载文件"""
        if os.path.exists(storage_path):
            with open(storage_path, 'rb') as f:
                return f.read()
        return None
    
    def _delete_local_file(self, storage_path: str) -> bool:
        """删除本地存储文件"""
        if os.path.exists(storage_path):
            try:
                os.remove(storage_path)
                return True
            except Exception as e:
                print(f"删除本地文件失败: {str(e)}")
                return False
        return False
    
    def _local_file_exists(self, storage_path: str) -> bool:
        """检查本地文件是否存在"""
        return os.path.exists(storage_path)


# 全局S3存储实例
s3_storage = S3Storage()