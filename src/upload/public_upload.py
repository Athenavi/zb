import hashlib
import os
import uuid

import magic
from flask import jsonify, request
from werkzeug.utils import secure_filename

from src.database import get_db
from src.models import Media, FileHash


def handle_user_upload(user_id, allowed_size, allowed_mimes, check_existing=False):
    if not request.files.getlist('file'):
        return jsonify({'message': 'no files uploaded'}), 400
    try:
        return file_handler(user_id=user_id, allowed_size=allowed_size, allowed_mimes=allowed_mimes,
                            check_existing=check_existing)
    except Exception as e:
        print(f"Upload Error: {str(e)}")
        return jsonify({'message': 'failed', 'error': str(e)}), 500


def upload_cover_back(user_id, base_path):
    if 'cover_image' not in request.files:
        return jsonify({"code": 400, "msg": "未上传文件"}), 400

    file = request.files['cover_image']

    if file.filename == '':
        return jsonify({"code": 400, "msg": "文件名为空"}), 400

    if file:
        allowed_mimes = {'image/jpeg', 'image/png'}
        if file.mimetype not in allowed_mimes:
            return jsonify({"error": f"Unsupported file type: {file.mimetype}"}), 415
        # 使用 UUID 生成唯一的文件名
        filename = str(uuid.uuid4()) + '.png'
        file_path = os.path.join(base_path, filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        file.save(file_path)
        handle_user_upload(user_id, allowed_size=file.size, allowed_mimes=allowed_mimes, check_existing=True)
        file_url = f"/static/cover/{filename}"
        return jsonify({"code": 200, "msg": "上传成功", "data": file_url}), 200
    else:
        return jsonify({"code": 400, "msg": "文件类型不支持"}), 400


def file_handler(user_id, check_existing=False, allowed_size=1024 * 1024 * 10,
                 allowed_mimes={'image/jpeg', 'image/png'}):
    with get_db() as db:
        for f in request.files.getlist('file'):
            # 校验基础属性
            if f.content_length > allowed_size:
                return jsonify({'message': f'File size exceeds limit: {allowed_size / 1024 / 1024}MB'}), 413
            file_data = f.read()
            file_hash = hashlib.sha256(file_data).hexdigest()
            f.seek(0)  # 重置文件指针

            reused_count = 0
            uploaded_files = []
            if check_existing:
                # 检查用户是否已上传过相同文件
                existing_media = Media.query.filter_by(
                    user_id=user_id,
                    hash=file_hash
                ).first()

                if existing_media:
                    # 根据需求决定是否跳过已存在文件
                    # 这里只是示例，可以根据需要调整
                    pass

            # 校验MIME类型
            mime_type = magic.from_buffer(file_data, mime=True)
            if mime_type not in allowed_mimes:
                print(f'Rejected: User {user_id}, Invalid MIME {mime_type}')
                continue

            # 检查文件哈希是否已存在
            existing_file_hash = FileHash.query.filter_by(
                hash=file_hash,
                mime_type=mime_type
            ).first()

            if existing_file_hash:
                # 复用已有文件
                storage_path = existing_file_hash.storage_path
                print(f'Reuse existing file: {storage_path}')
                # 增加引用计数
                existing_file_hash.reference_count += 1
                db.add(existing_file_hash)
                reused_count += 1
            else:
                # 生成存储路径（哈希分片目录）
                hash_prefix = file_hash[:2]
                hash_subdir = os.path.join('hashed_files', hash_prefix)
                os.makedirs(hash_subdir, exist_ok=True)

                # 保存文件
                filename = f.filename
                storage_path = os.path.join(hash_subdir, file_hash)
                with open(storage_path, 'wb') as dest:
                    dest.write(file_data)

                # 创建新的 FileHash 记录
                new_file_hash = FileHash(
                    hash=file_hash,
                    filename=filename,
                    file_size=len(file_data),
                    mime_type=mime_type,
                    storage_path=storage_path,
                    reference_count=1
                )
                db.add(new_file_hash)
                # 创建媒体记录（即使文件已存在也需要记录用户关联）
                try:
                    new_media = Media(
                        user_id=user_id,
                        hash=file_hash,
                        original_filename=secure_filename(f.filename)
                    )
                    db.add(new_media)
                    uploaded_files.append(f.filename)
                except Exception as e:
                    # 处理同一用户重复上传相同文件
                    print(f'Error inserting media record: {e}')
                    db.rollback()
                    continue
            return jsonify({
                'message': 'success',
                'uploaded': uploaded_files,
                'reused': reused_count
            }), 200
        return None
