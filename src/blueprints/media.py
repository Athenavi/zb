import concurrent
import os
from pathlib import Path

from flask import Blueprint, request, render_template, url_for, abort, jsonify, send_file

from src.database import get_db_connection
from src.media.permissions import get_media_db
from src.media.processing import generate_video_thumbnail, generate_thumbnail
from src.user.authz.decorators import jwt_required

media_bp = Blueprint('media', __name__, template_folder='templates')


def create_media_blueprint(cache_instance, domain, base_dir):
    @cache_instance.memoize(6)
    def get_media_cached(user_id, page=1, per_page=20):
        return get_media_db(user_id, page, per_page)

    @media_bp.route('/thumbnail', methods=['GET'])
    def media_thumbnail():
        f_hash = request.args.get('data')
        f_type = request.args.get('type')
        thumb_path = Path(base_dir) / f"thumbnails/{f_hash}.jpg"
        thumb_dir = Path(base_dir) / "thumbnails"
        if not thumb_dir.exists():
            thumb_dir.mkdir(parents=True, exist_ok=True)

        if not thumb_path.exists():
            try:
                db = get_db_connection()
                cursor = db.cursor()
                cursor.execute(f"""
                        SELECT hash, filename, mime_type, storage_path 
                        FROM file_hashes 
                        WHERE hash = %s;
                    """, (f_hash,))
                result = cursor.fetchone()
                if not result:
                    print("No result found for the given f_hash")
                    return "File not found", 404
                file_path = Path(base_dir) / result[3]
                thumb_path = Path(base_dir) / f"thumbnails/{f_hash}.jpg"
                if not os.path.exists(thumb_path):
                    if f_type == "video":
                        generate_video_thumbnail(file_path, thumb_path)
                    else:
                        generate_thumbnail(file_path, thumb_path)
            finally:
                return send_file(thumb_path, as_attachment=False, mimetype='image/jpeg', max_age=360)
        return send_file(thumb_path)

    @media_bp.route('/shared')
    def get_image_path(f_hash=None):
        if f_hash is None:
            f_hash = request.args.get('data')
        if f_hash is None:
            return "File hash not provided", 400  # 如果没有提供hash，则返回错误信息
        try:
            db = get_db_connection()
            cursor = db.cursor()
            cursor.execute(f"""
                SELECT hash, filename, mime_type, storage_path 
                FROM file_hashes 
                WHERE hash = %s;
            """, (f_hash,))
            result = cursor.fetchone()
            if not result:
                print("No result found for the given f_hash")
                return "File not found", 404
            file_path = Path(base_dir) / result[3]
            return send_file(file_path, as_attachment=False, mimetype=result[2], max_age=360)
        except FileNotFoundError:
            abort(404)

    @media_bp.route('/media', methods=['GET'])
    @jwt_required
    def media(user_id):
        page = request.args.get('page', default=1, type=int)
        imgs, total_pages = get_media_cached(user_id, page=page, per_page=20)
        has_next_page = bool(total_pages - page)
        has_previous_page = bool(total_pages - 1)
        return render_template('Media_V2.html', imgs=imgs, url_for=url_for,
                               has_next_page=has_next_page, mediaType='img',
                               has_previous_page=has_previous_page, current_page=page,
                               domain=domain)

    @media_bp.route('/media', methods=['DELETE'])
    @jwt_required
    def media_delete(user_id):
        try:
            file_ids = request.args.get('file-id-list', '')
            if not file_ids:
                return jsonify({"message": "缺少文件ID列表"}), 400

            id_list = [int(id) for id in file_ids.split(',') if id.isdigit()]
            if len(id_list) != len(file_ids.split(',')):
                return jsonify({"message": "文件ID格式错误"}), 400

            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # 1. 获取待删除文件的哈希和存储路径
                    placeholders = ', '.join(['%s'] * len(id_list))
                    cursor.execute(f"""
                        SELECT m.id, m.hash, fh.storage_path 
                        FROM media m
                        JOIN file_hashes fh ON m.hash = fh.hash
                        WHERE m.id IN ({placeholders}) AND m.user_id = %s
                    """, id_list + [user_id])

                    target_files = cursor.fetchall()
                    if len(target_files) != len(id_list):
                        return jsonify({"message": "部分文件不存在或无权操作"}), 400

                    # 2. 删除媒体记录
                    cursor.execute(f"""
                        DELETE FROM media 
                        WHERE id IN ({placeholders}) AND user_id = %s
                    """, id_list + [user_id])
                    deleted_count = cursor.rowcount

                    # 3. 提交事务使触发器生效
                    conn.commit()

                    # 4. 检查哪些文件需要物理删除
                    deleted_files = []
                    for file in target_files:
                        cursor.execute("""
                            SELECT 1 FROM file_hashes 
                            WHERE hash = %s LIMIT 1
                        """, (file[1],))
                        if not cursor.fetchone():
                            try:
                                if os.path.exists(file[2]):
                                    os.remove(file[2])
                                    deleted_files.append(file[2])
                            except Exception as e:
                                print(f"文件删除失败: {file[2]} - {str(e)}")

                    return jsonify({
                        "message": "操作成功",
                        "deleted_records": deleted_count,
                        "deleted_files": deleted_files
                    }), 200
        except Exception as e:
            print(f"删除异常: {str(e)}")
            return jsonify({"message": "服务器错误", "error": str(e)}), 500

    return media_bp
