from flask import Blueprint, jsonify, session as flask_session
from flask_login import login_required, current_user

from src.models import UserSession

session_bp = Blueprint('session', __name__)


@session_bp.route('/api/sessions', methods=['GET'])
@login_required
def get_my_sessions():
    """获取当前用户的所有活跃会话"""
    active_sessions = UserSession.get_active_sessions(current_user.id)

    return jsonify({
        'sessions': [s.to_dict() for s in active_sessions],
        'total_count': len(active_sessions)
    })


@session_bp.route('/api/sessions/<session_id>', methods=['DELETE'])
@login_required
def logout_session(session_id):
    """退出特定会话"""
    success = current_user.logout_session(session_id)

    if success:
        return jsonify({'message': '会话已退出'})
    else:
        return jsonify({'error': '会话不存在或无权操作'}), 404


@session_bp.route('/api/sessions/others', methods=['DELETE'])
@login_required
def logout_other_sessions():
    """退出除当前会话外的所有其他会话"""
    current_session_id = flask_session.get('internal_sid')
    count = current_user.logout_all_other_sessions(current_session_id)

    return jsonify({
        'message': f'已退出 {count} 个其他会话',
        'logged_out_count': count
    })


@session_bp.route('/api/sessions/current', methods=['GET'])
@login_required
def get_current_session():
    """获取当前会话信息"""
    current_session = current_user.get_current_session()

    if current_session:
        return jsonify({'session': current_session.to_dict()})
    else:
        return jsonify({'error': '未找到当前会话'}), 404
