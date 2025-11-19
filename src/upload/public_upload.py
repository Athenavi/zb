import hashlib
import os
import uuid

import magic
from flask import jsonify, request
from werkzeug.utils import secure_filename

from src.database import get_db
from src.models import Media, FileHash
from src.utils.shortener.links import create_special_url


class FileProcessor:
    """文件处理器，统一处理文件上传逻辑"""

    def __init__(self, user_id, allowed_mimes=None, allowed_size=10 * 1024 * 1024):
        self.user_id = user_id
        self.allowed_mimes = allowed_mimes or {'image/jpeg', 'image/png'}
        self.allowed_size = allowed_size

    def validate_file(self, file_data, filename):
        """验证文件基本属性"""
        if not filename:
            return False, "文件名为空"

        mime_type = magic.from_buffer(file_data, mime=True)
        if mime_type not in self.allowed_mimes:
            return False, f"不支持的文件类型: {mime_type}"

        file_size = len(file_data)
        if file_size > self.allowed_size:
            return False, f"文件大小超过限制: {self.allowed_size / 1024 / 1024}MB"

        return True, {"mime_type": mime_type, "file_size": file_size}

    def calculate_hash(self, file_data):
        """计算文件哈希"""
        return hashlib.sha256(file_data).hexdigest()

    def save_file(self, file_hash, file_data, original_filename):
        """保存文件到存储系统"""
        hash_prefix = file_hash[:2]
        hash_subdir = os.path.join('hashed_files', hash_prefix)
        os.makedirs(hash_subdir, exist_ok=True)

        storage_path = os.path.join(hash_subdir, file_hash)
        with open(storage_path, 'wb') as f:
            f.write(file_data)

        return storage_path

    def create_file_hash_record(self, db, file_hash, filename, file_size, mime_type, storage_path, reference_count=1):
        """创建文件哈希记录"""
        existing = FileHash.query.filter_by(hash=file_hash, mime_type=mime_type).first()
        if existing:
            existing.reference_count += reference_count
            return existing

        new_file_hash = FileHash(
            hash=file_hash,
            filename=filename,
            file_size=file_size,
            mime_type=mime_type,
            storage_path=storage_path,
            reference_count=reference_count
        )
        db.add(new_file_hash)
        return new_file_hash

    def create_media_record(self, db, file_hash, filename, check_existing=False):
        """创建媒体记录"""
        if check_existing:
            existing = Media.query.filter_by(user_id=self.user_id, hash=file_hash).first()
            if existing:
                return existing

        new_media = Media(
            user_id=self.user_id,
            hash=file_hash,
            original_filename=secure_filename(filename)
        )
        db.add(new_media)
        return new_media


def upload_cover_back(user_id, base_path, domain):
    """上传封面图片"""
    if 'cover_image' not in request.files:
        return jsonify({"code": 400, "msg": "未上传文件"}), 400

    file = request.files['cover_image']
    if not file or file.filename == '':
        return jsonify({"code": 400, "msg": "文件名为空"}), 400

    # 保存临时文件
    temp_filename = str(uuid.uuid4()) + '.png'
    temp_file_path = os.path.join(base_path, temp_filename)
    os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
    file.save(temp_file_path)

    try:
        # 处理文件
        with open(temp_file_path, 'rb') as f:
            file_data = f.read()

        processor = FileProcessor(user_id, allowed_size=8 * 1024 * 1024)
        result = _process_single_file(processor, file_data, file.filename)

        if result['success']:
            s_url = create_special_url(
                domain + "thumbnail?data=" + result['hash'],
                user_id=user_id
            )
            cover_url = "/s/" + s_url
            return jsonify({"code": 200, "msg": "上传成功", "data": cover_url}), 200
        else:
            return jsonify({"code": 500, "msg": "文件处理失败", "error": result['error']}), 500

    except Exception as e:
        return jsonify({"code": 500, "msg": "上传失败", "error": str(e)}), 500
    finally:
        # 清理临时文件
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


def handle_user_upload(user_id, allowed_size=10 * 1024 * 1024, allowed_mimes=None, check_existing=False):
    """处理用户文件上传"""
    if not request.files.getlist('file'):
        return jsonify({'message': 'no files uploaded'}), 400

    try:
        return _process_multiple_files(user_id, allowed_size, allowed_mimes, check_existing)
    except Exception as e:
        print(f"Upload Error: {str(e)}")
        return jsonify({'message': 'failed', 'error': str(e)}), 500


def _process_single_file(processor, file_data, filename):
    """处理单个文件的核心逻辑"""
    with get_db() as db:
        try:
            # 验证文件
            is_valid, validation_result = processor.validate_file(file_data, filename)
            if not is_valid:
                return {'success': False, 'error': validation_result}

            # 计算哈希
            file_hash = processor.calculate_hash(file_data)
            mime_type = validation_result['mime_type']
            file_size = validation_result['file_size']

            # 检查文件是否已存在
            existing_file_hash = FileHash.query.filter_by(
                hash=file_hash, mime_type=mime_type
            ).first()

            if not existing_file_hash:
                # 保存新文件
                storage_path = processor.save_file(file_hash, file_data, filename)
                processor.create_file_hash_record(db, file_hash, filename, file_size, mime_type, storage_path)

            # 创建媒体记录
            processor.create_media_record(db, file_hash, filename)
            db.commit()

            return {'success': True, 'hash': file_hash}

        except Exception as e:
            db.rollback()
            return {'success': False, 'error': str(e)}


def _process_multiple_files(user_id, allowed_size, allowed_mimes, check_existing):
    """处理多个文件上传"""
    processor = FileProcessor(user_id, allowed_mimes, allowed_size)
    uploaded_files = []
    reused_count = 0
    errors = []

    # 收集文件信息
    file_info_list = []
    for f in request.files.getlist('file'):
        try:
            file_data = f.read()
            file_info = {
                'file_obj': f,
                'filename': f.filename,
                'file_data': file_data,
                'file_hash': processor.calculate_hash(file_data)
            }

            # 验证文件
            is_valid, validation_result = processor.validate_file(file_data, f.filename)
            if not is_valid:
                errors.append(f'File {f.filename}: {validation_result}')
                continue

            file_info.update(validation_result)
            file_info_list.append(file_info)

        except Exception as e:
            errors.append(f'Error processing file {f.filename}: {str(e)}')

    # 按哈希分组处理
    hash_groups = {}
    for file_info in file_info_list:
        hash_groups.setdefault(file_info['file_hash'], []).append(file_info)

    # 处理每个哈希组
    with get_db() as db:
        for file_hash, file_group in hash_groups.items():
            try:
                first_file = file_group[0]

                # 检查文件是否已存在
                existing_file_hash = FileHash.query.filter_by(
                    hash=file_hash, mime_type=first_file['mime_type']
                ).first()

                if existing_file_hash:
                    # 更新引用计数
                    existing_file_hash.reference_count += len(file_group)
                    reused_count += len(file_group)
                    storage_path = existing_file_hash.storage_path
                else:
                    # 保存新文件
                    storage_path = processor.save_file(file_hash, first_file['file_data'], first_file['filename'])
                    processor.create_file_hash_record(
                        db, file_hash, first_file['filename'],
                        first_file['file_size'], first_file['mime_type'],
                        storage_path, len(file_group)
                    )

                # 为每个文件创建媒体记录
                for file_info in file_group:
                    media_record = processor.create_media_record(
                        db, file_hash, file_info['filename'], check_existing
                    )
                    if media_record:
                        uploaded_files.append(file_info['filename'])

                db.commit()

            except Exception as e:
                db.rollback()
                errors.append(f'Error processing files with hash {file_hash}: {str(e)}')

    # 构建响应
    response_data = {
        'message': 'success' if not errors else 'partial success',
        'uploaded': uploaded_files,
        'reused': reused_count
    }

    if errors:
        response_data['errors'] = errors

    status_code = 200 if not errors else 207
    return jsonify(response_data), status_code
