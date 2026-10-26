"""
Map and AOI API Routes
"""

import logging
from typing import Any, Dict

from flask import Blueprint, request, jsonify

from extensions import db
from models.user_aoi import AOI
from utils.jwt_auth import jwt_required, get_current_user_id

logger = logging.getLogger(__name__)

map_bp = Blueprint('map', __name__)


def validate_geometry(geometry):
    from utils.geometry import polygon
    try:
        polygon(geometry)
        return True
    except (ValueError, TypeError, IndexError):
        return False


@map_bp.route('/aoi', methods=['POST'])
@jwt_required
def create_aoi():
    """Create a new Area of Interest."""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'Request body required'}), 400
    
    name = data.get('name', '').strip()
    geometry = data.get('geometry')
    
    if not name:
        name = f"AOI-{get_current_user_id()}"
    
    if not validate_geometry(geometry):
        return jsonify({'success': False, 'error': 'Valid geometry is required'}), 400
    
    try:
        new_aoi = AOI(
            user_id=get_current_user_id(),
            name=name,
            geometry=geometry,
            area_km2=data.get('area_km2', 0.0),
            monitoring_mode=data.get('monitoring_mode', 'on-demand'),
            status='active'
        )
        
        db.session.add(new_aoi)
        db.session.commit()
        
        logger.info(f"Created AOI #{new_aoi.id}: {name}")
        
        return jsonify({
            'success': True,
            'aoi': {
                'id': new_aoi.id,
                'name': new_aoi.name,
                'geometry': new_aoi.geometry,
                'area_km2': new_aoi.area_km2,
                'status': new_aoi.status
            }
        }), 201
        
    except Exception as e:
        logger.error(f"Failed to create AOI: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@map_bp.route('/aoi', methods=['GET'])
@jwt_required
def list_aois():
    """List all AOIs for the current user."""
    aois = AOI.query.filter_by(user_id=get_current_user_id()).all()
    
    return jsonify({
        'success': True,
        'aois': [
            {
                'id': aoi.id,
                'name': aoi.name,
                'geometry': aoi.geometry,
                'area_km2': aoi.area_km2,
                'monitoring_mode': aoi.monitoring_mode,
                'status': aoi.status,
                'created_at': aoi.created_at.isoformat() if aoi.created_at else None
            }
            for aoi in aois
        ]
    })


@map_bp.route('/aoi/<int:aoi_id>', methods=['GET'])
@jwt_required
def get_aoi(aoi_id: int):
    """Get a specific AOI."""
    aoi = AOI.query.filter_by(id=aoi_id, user_id=get_current_user_id()).first()
    
    if not aoi:
        return jsonify({'success': False, 'error': 'AOI not found'}), 404
    
    return jsonify({
        'success': True,
        'aoi': {
            'id': aoi.id,
            'name': aoi.name,
            'geometry': aoi.geometry,
            'area_km2': aoi.area_km2,
            'monitoring_mode': aoi.monitoring_mode,
            'status': aoi.status,
            'created_at': aoi.created_at.isoformat() if aoi.created_at else None
        }
    })


@map_bp.route('/aoi/<int:aoi_id>', methods=['DELETE'])
@jwt_required
def delete_aoi(aoi_id: int):
    """Delete an AOI."""
    aoi = AOI.query.filter_by(id=aoi_id, user_id=get_current_user_id()).first()
    
    if not aoi:
        return jsonify({'success': False, 'error': 'AOI not found'}), 404
    
    if aoi.analyses.count():
        return jsonify({'error': 'This area has analyses. Delete its finished analyses first.'}), 409
    try:
        db.session.delete(aoi)
        db.session.commit()
        logger.info(f"Deleted AOI #{aoi_id}")
        return jsonify({'success': True, 'message': 'AOI deleted'})
    except Exception as e:
        logger.error(f"Failed to delete AOI: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@map_bp.route('/preview', methods=['POST'])
@jwt_required
def get_preview():
    from services.gee_service import gee_service
    import time
    
    
    start_time = time.time()
    
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'Request body required'}), 400
    
    geometry = data.get('geometry')
    
    if not validate_geometry(geometry):
        return jsonify({'success': False, 'error': 'Valid geometry is required'}), 400
    
    start_date = data.get('startDate', '2024-01-01')
    end_date = data.get('endDate', '2024-04-30')
    from routes.analysis import validate_date
    if not validate_date(start_date) or not validate_date(end_date) or start_date >= end_date:
        return jsonify({'error': 'Choose a valid date range, with the end after the start.'}), 400
    try:
        cloud_cover = max(1, min(int(data.get('cloudCover', 30)), 100))
    except (ValueError, TypeError):
        return jsonify({'error': 'Cloud cover must be a number.'}), 400
    if not gee_service.is_initialized:
        return jsonify({'error': 'Google Earth Engine is unavailable. Check the local service account configuration.'}), 503
    layer_type = data.get('layerType', 'rgb')
    
    if layer_type not in ('rgb', 'ndvi'):
        layer_type = 'rgb'
    
    try:

        
        result, _ = gee_service.get_quality_imagery(
            geometry, start_date, end_date, layer_type, adaptive=data.get("expandWindow", False) is True
        )
        return jsonify({'success': True, **result})

    except Exception as e:
        logger.error(f"Preview generation failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
