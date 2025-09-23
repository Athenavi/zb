import shutil
from pathlib import Path

from flask import Blueprint, jsonify, send_from_directory, request

from src.config.theme import theme_safe_check, db_remove_theme, get_all_themes
from src.user.authz.decorators import admin_required

theme_bp = Blueprint('theme', __name__, template_folder='templates')


def create_theme_blueprint(cache_instance, base_dir):
    @theme_bp.route('/theme/<theme_id>')
    @cache_instance.cached(timeout=300)
    def get_theme_detail(theme_id):
        return theme_safe_check(theme_id=theme_id, channel=1)

    @theme_bp.route('/theme/<theme_id>/<img_name>')
    def get_screenshot(theme_id, img_name):
        if theme_id == 'default':
            return send_from_directory(base_dir, 'static/favicon.ico', mimetype='image/png', max_age=3600)
        try:
            theme_dir: Path = Path(base_dir) / 'templates' / 'theme' / theme_id
            return send_from_directory(theme_dir, img_name, mimetype='image/png', max_age=3600)
        except FileNotFoundError:
            print(f"File not found: {theme_id}/{img_name}")
            return jsonify(error='Image not found'), 404
        except Exception as e:
            print(f"Error in getting image: {e}")
            return jsonify(error='Failed to get image'), 500

    @theme_bp.route('/api/theme', methods=['DELETE'])
    @admin_required
    def delete_theme(user_id):
        theme_id = request.args.get('theme_id')
        if not theme_id:
            return jsonify({'error': 'Missing theme_id'}), 400

        if theme_id == 'default':
            return jsonify({'message': 'default Theme can not be deleted'}), 403

        theme_dir = Path(base_dir) / 'templates' / 'theme' / theme_id
        print(theme_dir)

        try:
            if not theme_dir.resolve().relative_to(Path(base_dir).resolve()):
                return jsonify({'error': 'Invalid theme path'}), 400
        except ValueError:
            return jsonify({'error': 'Path traversal attempt detected'}), 400

        # 检查目录存在性
        if not theme_dir.is_dir():
            return jsonify({'error': 'Theme not found'}), 404

        try:
            # 执行删除
            shutil.rmtree(theme_dir)
            current_theme = cache_instance.get('display_theme')
            if current_theme == theme_id:
                cache_instance.set('display_theme', 'default')
                # 可选：清理相关缓存模板
                cache_instance.delete_memoized('index')
            return jsonify({'message': 'Theme deleted successfully'}), 200

        except Exception as e:
            return jsonify({'error': f'Deletion failed: {str(e)}'}), 500

    @theme_bp.route('/api/theme', methods=['PUT'])
    @admin_required
    def change_display(user_id):
        theme_id = request.args.get('id')
        if not theme_id:
            return "failed403"

        all_themes = get_all_themes()
        if theme_id not in all_themes:
            return "failed001"

        if theme_safe_check(theme_id, channel=2):
            try:
                if db_remove_theme(user_id, theme_id):
                    return "success"
                else:
                    return "failed"
            except Exception as e:
                print(f"Error during theme change: {e}")
                return "failed500"
            finally:
                log_msg = f"{user_id} : ban {theme_id} theme"
                print(log_msg)
        else:
            return "failed"

    return theme_bp
