import hashlib
import os
import uuid

import magic
from flask import jsonify, request
from werkzeug.utils import secure_filename

from src.database import get_db_connection


def handle_user_upload(user_id, allowed_size, allowed_mimes, check_existing=False):
    if not request.files.getlist('file'):
        return jsonify({'message': 'no files uploaded'}), 400

    try:
        uploaded_files = []
        with get_db_connection() as db:
            cursor = db.cursor()

            for f in request.files.getlist('file'):
                # 校验基础属性
                if f.content_length > allowed_size:
                    return jsonify({'message': f'File size exceeds limit: {allowed_size / 1024 / 1024}MB'}), 413

                # 读取文件内容并计算哈希
                file_data = f.read()
                file_hash = hashlib.sha256(file_data).hexdigest()
                f.seek(0)  # 重置文件指针

                if check_existing:
                    try:
                        cursor.execute(
                            """SELECT hash
                               FROM media
                               WHERE hash = %s
                                 and user_id = %s""",
                            (file_hash, user_id)
                        )
                        existing_file = cursor.fetchone()
                        if existing_file:
                            pass
                    except Exception as e:
                        return jsonify({'message': 'failed', 'error': str(e)}), 500

                # 校验MIME类型
                mime_type = magic.from_buffer(file_data, mime=True)
                if mime_type not in allowed_mimes:
                    print(f'Rejected: User {user_id}, Invalid MIME {mime_type}')
                    continue

                # 检查哈希是否已存在
                cursor.execute(
                    """SELECT hash, storage_path
                       FROM file_hashes
                       WHERE hash = %s
                         AND mime_type = %s""",
                    (file_hash, mime_type)
                )
                existing_file = cursor.fetchone()

                storage_path = None
                if existing_file:
                    # 复用已有文件
                    storage_path = existing_file[1]
                    print(f'Reuse existing file: {storage_path}')
                    # 增加引用计数
                    cursor.execute(
                        """UPDATE file_hashes
                           SET reference_count = reference_count + 1
                           WHERE hash = %s
                             AND mime_type = %s""",
                        (file_hash, mime_type)
                    )
                else:
                    # 生成存储路径（哈希分片目录）
                    hash_prefix = file_hash[:2]
                    hash_subdir = os.path.join('hashed_files', hash_prefix)
                    os.makedirs(hash_subdir, exist_ok=True)

                    # 保存文件（示例路径格式：hashed_files/ab/abcdef12345...）
                    filename = f.filename
                    storage_path = os.path.join(hash_subdir, file_hash)
                    with open(storage_path, 'wb') as dest:
                        dest.write(file_data)

                    # 插入文件哈希记录
                    cursor.execute(
                        """INSERT INTO file_hashes
                               (hash, filename, file_size, mime_type, storage_path, reference_count)
                           VALUES (%s, %s, %s, %s, %s, 1)
                           ON CONFLICT (hash, mime_type) DO UPDATE SET reference_count = file_hashes.reference_count + 1""",
                        (file_hash, filename, len(file_data), mime_type, storage_path)
                    )

                # 插入媒体记录（即使文件已存在也需要记录用户关联）
                try:
                    cursor.execute(
                        """INSERT INTO media
                               (user_id, hash, original_filename)
                           VALUES (%s, %s, %s)""",
                        (user_id, file_hash, secure_filename(f.filename))
                    )
                    uploaded_files.append(f.filename)
                except Exception as e:
                    # 处理同一用户重复上传相同文件
                    print(f'Error inserting media record: {e}')
                    db.rollback()
                    continue

            db.commit()
            return jsonify({
                'message': 'success',
                'uploaded': uploaded_files,
                'reused': len(request.files) - len(uploaded_files)
            }), 200

    except Exception as e:
        print(f"Upload Error: {str(e)}")
        db.rollback()
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
        file_url = f"/static/cover/{filename}"
        return jsonify({"code": 200, "msg": "上传成功", "data": file_url}), 200
    else:
        return jsonify({"code": 400, "msg": "文件类型不支持"}), 400
