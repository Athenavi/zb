"""
Dashboard 评论配置模块
包含评论系统配置功能
"""
import inspect
from datetime import datetime

from flask import request, render_template, jsonify

from src.auth_utils import admin_required
from src.extensions import limiter
from src.models import User, db, SystemSettings
from . import admin_bp


@admin_bp.route('/comment-config', methods=['GET', 'POST'])
@admin_required
@limiter.limit("10 per minute")
def admin_comment_config(user_id):
    """评论系统配置页面"""
    try:
        # 获取当前用户信息
        current_user = db.session.query(User).filter_by(id=user_id).first()

        if request.method == 'POST':
            # 处理表单提交
            try:
                # 获取所有Giscus配置参数
                giscus_config = {
                    'giscus_repo': request.form.get('giscus_repo', '').strip(),
                    'giscus_repo_id': request.form.get('giscus_repo_id', '').strip(),
                    'giscus_category': request.form.get('giscus_category', '').strip(),
                    'giscus_category_id': request.form.get('giscus_category_id', '').strip(),
                    'giscus_mapping': request.form.get('giscus_mapping', 'pathname'),
                    'giscus_strict': request.form.get('giscus_strict', '0'),
                    'giscus_reactions_enabled': request.form.get('giscus_reactions_enabled', '1'),
                    'giscus_emit_metadata': request.form.get('giscus_emit_metadata', '0'),
                    'giscus_input_position': request.form.get('giscus_input_position', 'top'),
                    'giscus_theme': request.form.get('giscus_theme', 'preferred_color_scheme'),
                    'giscus_lang': request.form.get('giscus_lang', 'zh-CN'),
                    'giscus_loading': request.form.get('giscus_loading', 'lazy')
                }

                # 自动纠错和验证
                corrected_config = auto_correct_giscus_config(giscus_config)

                # 保存配置到系统设置
                for key, value in corrected_config.items():
                    setting = db.session.query(SystemSettings).filter_by(key=key).first()
                    if setting:
                        setting.value = value
                        setting.updated_at = datetime.now()
                        setting.updated_by = user_id
                    else:
                        setting = SystemSettings(
                            key=key,
                            value=value,
                            updated_at=datetime.now(),
                            updated_by=user_id
                        )
                        db.session.add(setting)

                db.session.commit()

                return jsonify({
                    'success': True,
                    'message': '评论配置保存成功'
                })

            except Exception as e:
                db.session.rollback()
                return jsonify({
                    'success': False,
                    'message': f'保存配置失败: {str(e)}'
                })

        # GET请求 - 显示配置页面
        # 获取现有配置
        system_settings = db.session.query(SystemSettings).all()
        settings_dict = {setting.key: setting.value for setting in system_settings}

        return render_template('dashboard/comment_config.html',
                               settings=settings_dict,
                               current_user=current_user)

    except Exception as e:
        return jsonify({'error': str(e)})
    finally:
        current_func_name = inspect.currentframe().f_code.co_name
        # 输出当前视图名称和操作人ID
        print(f"==>{current_func_name}, User ID: {user_id}")


def auto_correct_giscus_config(config):
    """
    自动纠错Giscus配置
    """
    corrected = config.copy()

    # 验证和修正仓库名称格式
    repo = corrected['giscus_repo']
    if repo:
        # 检查是否包含斜杠
        if '/' not in repo:
            # 尝试智能修复 - 如果只有一个斜杠，添加默认仓库
            parts = repo.split('/')
            if len(parts) == 1:
                # 如果只有用户名，添加默认仓库名
                corrected['giscus_repo'] = f"{repo}/repo"  # 这里可以改为更有意义的默认值
                print(f"警告: 仓库名称格式不正确，已更正为: {corrected['giscus_repo']}")
        else:
            # 分割并清理仓库名
            parts = repo.split('/')
            if len(parts) >= 2:
                username = parts[0].strip()
                reponame = '/'.join(parts[1:]).strip()  # 处理仓库名中可能包含的斜杠
                corrected['giscus_repo'] = f"{username}/{reponame}"

    # 验证映射方式
    valid_mappings = ['pathname', 'url', 'title', 'og:title', 'specific', 'number']
    if corrected['giscus_mapping'] not in valid_mappings:
        corrected['giscus_mapping'] = 'pathname'  # 默认值

    # 验证严格模式值
    if corrected['giscus_strict'] not in ['0', '1']:
        corrected['giscus_strict'] = '0'

    # 验证表情反应启用值
    if corrected['giscus_reactions_enabled'] not in ['0', '1']:
        corrected['giscus_reactions_enabled'] = '1'

    # 验证发送元数据值
    if corrected['giscus_emit_metadata'] not in ['0', '1']:
        corrected['giscus_emit_metadata'] = '0'

    # 验证输入框位置
    if corrected['giscus_input_position'] not in ['top', 'bottom']:
        corrected['giscus_input_position'] = 'top'

    # 验证主题
    valid_themes = ['light', 'dark', 'dark_dimmed', 'dark_high_contrast', 'preferred_color_scheme']
    if corrected['giscus_theme'] not in valid_themes:
        corrected['giscus_theme'] = 'preferred_color_scheme'

    # 验证语言
    valid_langs = ['zh-CN', 'zh-TW', 'en', 'es', 'fr', 'ja', 'ko', 'ru']
    if corrected['giscus_lang'] not in valid_langs:
        corrected['giscus_lang'] = 'zh-CN'

    # 验证加载方式
    if corrected['giscus_loading'] not in ['eager', 'lazy']:
        corrected['giscus_loading'] = 'lazy'

    return corrected
