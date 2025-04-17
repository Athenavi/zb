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
                return send_file(thumb_path, as_attachment=False, mimetype='image/jpeg', max_age=2592000)
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
            return send_file(file_path, as_attachment=False, mimetype=result[2], max_age=2592000)
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
                    # 开启事务
                    conn.autocommit = False
                    pending_file_deletions = []

                    try:
                        # 1. 先查询要删除的文件信息
                        placeholders = ', '.join(['%s'] * len(id_list))
                        cursor.execute(f"""
                            SELECT m.id, m.hash, fh.storage_path 
                            FROM media m
                            JOIN file_hashes fh ON m.hash = fh.hash
                            WHERE m.id IN ({placeholders}) AND m.user_id = %s
                            FOR UPDATE  # 加锁防止并发修改
                        """, id_list + [user_id])

                        target_files = cursor.fetchall()
                        if len(target_files) != len(id_list):
                            conn.rollback()
                            return jsonify({"message": "部分文件不存在或无权操作"}), 400

                        # 2. 执行删除操作
                        cursor.execute(f"""
                            DELETE FROM media 
                            WHERE id IN ({placeholders}) AND user_id = %s
                        """, id_list + [user_id])
                        deleted_count = cursor.rowcount

                        # 3. 处理文件引用计数
                        file_hashes_to_check = set()
                        for file in target_files:
                            file_id, file_hash, storage_path = file
                            cursor.execute("""
                                UPDATE file_hashes 
                                SET reference_count = GREATEST(0, reference_count - 1)
                                WHERE hash = %s
                            """, (file_hash,))
                            file_hashes_to_check.add((file_hash, storage_path))

                        # 4. 检查需要物理删除的文件
                        for file_hash, storage_path in file_hashes_to_check:
                            cursor.execute("""
                                SELECT reference_count 
                                FROM file_hashes 
                                WHERE hash = %s
                            """, (file_hash,))
                            result = cursor.fetchone()

                            if result and result[0] == 0:
                                cursor.execute("""
                                    DELETE FROM file_hashes 
                                    WHERE hash = %s
                                """, (file_hash,))
                                pending_file_deletions.append(storage_path)

                        # 5. 提交事务
                        conn.commit()

                        # 6. 物理删除文件（事务成功后）
                        actually_deleted_files = []
                        for file_path in pending_file_deletions:
                            try:
                                if os.path.exists(file_path):
                                    os.remove(file_path)
                                    actually_deleted_files.append(file_path)
                            except Exception as e:
                                print(f"文件删除失败: {file_path} - {str(e)}")

                        return jsonify({
                            "message": "操作成功",
                            "deleted_records": deleted_count,
                            "deleted_files": actually_deleted_files
                        }), 200

                    except Exception as e:
                        conn.rollback()
                        print(f"数据库操作失败: {str(e)}")
                        return jsonify({"message": "服务器错误", "error": str(e)}), 500

        except Exception as e:
            print(f"请求处理异常: {str(e)}")
            return jsonify({"message": "服务器错误", "error": str(e)}), 500

    return media_bp
