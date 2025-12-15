from flask import Blueprint, jsonify, render_template, request

from plugins.manager import PluginManager
from src.auth import admin_required
from src.extensions import db
from src.models import User

plugin_bp = Blueprint('plugin_bp', __name__, url_prefix='/api/plugins')

# 初始化插件管理器（延迟到应用上下文中）
plugins_manager = None


def init_plugin_manager(app):
    """在应用上下文中初始化插件管理器"""
    global plugins_manager
    with app.app_context():
        plugins_manager = PluginManager(app)
        plugins_manager.load_plugins()
        
        # 特殊处理直播插件的模型和蓝图
        live_plugin = plugins_manager.plugins.get('live')
        if live_plugin:
            # 初始化直播模型
            from plugins.live.models import init_models
            live_models = init_models(db)
            
            # 初始化直播蓝图
            from plugins.live.blueprints import init_blueprints
            live_bp, admin_live_bp = init_blueprints(**live_models)
            
            # 注册直播蓝图
            app.register_blueprint(live_bp)
            app.register_blueprint(admin_live_bp)
        
        plugins_manager.register_blueprints()


@plugin_bp.route('/install', methods=['POST'])
def install_plugin():
    # 实际应用中这里应该处理插件的安装
    return jsonify({
        'status': 'error',
        'message': 'Plugin installation not implemented yet'
    })


@plugin_bp.route('/uninstall/<plugin_name>', methods=['DELETE'])
def uninstall_plugin(plugin_name):  # 修复：添加缺失的参数
    # 实际应用中这里应该处理插件的卸载
    return jsonify({
        'status': 'error',
        'message': f'Plugin {plugin_name} uninstallation not implemented yet'
    })


@plugin_bp.route('/')
@admin_required
def plugin_dashboard(user_id):
    plugins = plugins_manager.get_plugin_list()
    current_user = User.query.get(user_id)
    return render_template('dashboard/plugins.html', plugins=plugins, current_user=current_user)


@plugin_bp.route('/toggle/<plugin_name>', methods=['POST'])
def toggle_plugin(plugin_name):
    data = request.get_json()
    new_state = data.get('state', False)

    if new_state:
        success = plugins_manager.enable_plugin(plugin_name)
    else:
        success = plugins_manager.disable_plugin(plugin_name)

    return jsonify({
        'status': 'success' if success else 'error',
        'message': f'插件 {plugin_name} 已{"启用" if new_state else "禁用"}',
        'new_state': new_state
    })