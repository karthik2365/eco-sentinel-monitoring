from flask import Blueprint, request, jsonify
from extensions import db
from models.user_aoi import AOI
from services.scheduler import Monitor
from utils.jwt_auth import jwt_required, get_current_user_id

monitors_bp = Blueprint('monitors', __name__)

@monitors_bp.route('', methods=['GET'])
@jwt_required
def list_monitors():
    rows = Monitor.query.join(AOI).filter(AOI.user_id == get_current_user_id()).all()
    return jsonify({'monitors': [m.to_dict() for m in rows]})

@monitors_bp.route('/<int:monitor_id>', methods=['PATCH'])
@jwt_required
def update_monitor(monitor_id):
    monitor = Monitor.query.join(AOI).filter(Monitor.id == monitor_id, AOI.user_id == get_current_user_id()).first()
    if not monitor:
        return jsonify({'error': 'Monitor not found'}), 404
    data = request.get_json() or {}
    if not isinstance(data.get('active'), bool):
        return jsonify({'error': 'active must be true or false'}), 400
    monitor.active = data['active']
    db.session.commit()
    return jsonify(monitor.to_dict())
