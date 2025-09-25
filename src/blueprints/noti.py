from flask import Blueprint

from src.notification import read_current_notification, get_notifications, read_all_notifications
from src.user.authz.decorators import jwt_required

noti_bp = Blueprint('noti', __name__, url_prefix='/noti')

from flask import request


@noti_bp.route('/api/messages/read', methods=['POST'])
@jwt_required
def read_notification(user_id):
    nid = request.args.get('nid')
    return read_current_notification(user_id, nid)


@noti_bp.route('/api/messages', methods=['GET'])
@jwt_required
def fetch_message(user_id):
    return get_notifications(user_id)


@noti_bp.route('/api/messages/read_all', methods=['POST'])
@jwt_required
def mark_all_as_read(user_id):
    return read_all_notifications(user_id)
