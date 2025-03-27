import io
import os
import shutil
from datetime import datetime
from pathlib import Path

from flask import jsonify, request
from werkzeug.utils import secure_filename

from src.database import get_db_connection
from src.upload.check import is_allowed_file


def upload_article(file, upload_folder, allowed_size):
    # 验证文件格式和大小
    if not file.filename.endswith('.md') or file.content_length > allowed_size:
        return 'Invalid file format or file too large.', 400

    # 使用 pathlib 创建上传文件夹
    upload_path = Path(upload_folder)
    upload_path.mkdir(parents=True, exist_ok=True)

    # 构建文件路径
    file_path = upload_path / file.filename

    # 避免文件名冲突
    if file_path.is_file():
        return 'Upload failed, the file already exists.', 400

    # 保存文件
    file.save(str(file_path))  # 确保转换为字符串
    shutil.copy(str(file_path), str(Path('articles') / file.filename))
    return None


def handle_user_upload(user_name, user_id, allowed_size, allowed_types):
    if not user_name:
        return jsonify({'message': 'failed, user not authenticated'}), 403

    if not request.files.getlist('file'):
        return jsonify({'message': 'no files uploaded'}), 400

    try:
        allowed_types = allowed_types
        user_dir = os.path.join('media', user_name)
        os.makedirs(user_dir, exist_ok=True)
        file_records = []
        with get_db_connection() as db:
            with db.cursor() as cursor:
                for f in request.files.getlist('file'):
                    if not is_allowed_file(f.filename, allowed_types):
                        print(f'User: {user_name}, File {f.filename} not allowed')
                        continue

                    if f.content_length > allowed_size:
                        return jsonify({'message': f'File size exceeds the limit of {allowed_size}'}), 413

                    newfile_name = secure_filename(str(f.filename))
                    user_dir = str(user_dir)

                    newfile_path = os.path.join(user_dir, newfile_name)
                    old_thumb_path = os.path.join(user_dir, 'thumbs', newfile_name)

                    if isinstance(f, io.BytesIO):
                        with open(newfile_path, 'wb') as file:
                            file.write(f.getvalue())
                    else:
                        f.save(newfile_path)

                    if os.path.isfile(old_thumb_path):
                        os.remove(old_thumb_path)

                    file_type = (
                        'image' if f.filename.lower().endswith(
                            ('.jpg', '.jpeg', '.png', '.webp', '.jfif', '.pjpeg', '.pjp')
                        ) else 'video' if f.filename.lower().endswith('.mp4')
                        else 'document'
                    )

                    cursor.execute("SELECT `id` FROM `media` WHERE `file_path`=%s", (newfile_path,))
                    existing_record = cursor.fetchone()

                    if existing_record:
                        cursor.execute(
                            "UPDATE `media` SET `updated_at`=%s WHERE `id`=%s",
                            (datetime.now(), existing_record[0])
                        )
                    else:
                        file_records.append(
                            (user_id, newfile_path, file_type, datetime.now(), datetime.now())
                        )
                        print(f'User: {user_name}, Uploaded file: {newfile_name}')

                if file_records:
                    insert_query = ("INSERT INTO `media` (`user_id`, `file_path`, `file_type`, `created_at`, "
                                    "`updated_at`) VALUES (%s, %s, %s, %s, %s)")
                    cursor.executemany(insert_query, file_records)
                else:
                    print(f'User: {user_name}, No valid files uploaded')
                    return jsonify({'message': 'no valid files uploaded'}), 200

            db.commit()

        return jsonify({'message': 'success'}), 200

    except Exception as e:
        print(f"Error in file upload: {e}")
        return jsonify({'message': 'failed', 'error': str(e)}), 500
