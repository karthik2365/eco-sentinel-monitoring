"""
Dashboard API Routes

Provides endpoints for dashboard metrics and analytics.
"""

import logging

from flask import Blueprint, jsonify

from extensions import db
from models.user_aoi import AOI
from models.analysis_incident import Analysis, Incident
from utils.jwt_auth import jwt_required, get_current_user_id

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/metrics', methods=['GET'])
@jwt_required
def get_metrics():
    """Get dashboard metrics for the current user."""
    user_aois = AOI.query.filter_by(user_id=get_current_user_id()).all()
    aoi_ids = [a.id for a in user_aois]
    
    if not aoi_ids:
        return jsonify({
            'active_monitoring': 0,
            'analyses_completed': 0,
            'analyses_in_progress': 0,
            'incidents_detected': 0,
            'recent_analyses': []
        })
    
    analyses = Analysis.query.filter(Analysis.aoi_id.in_(aoi_ids)).all()
    analysis_ids = [a.id for a in analyses]
    
    completed_count = sum(1 for a in analyses if a.status == 'completed')
    in_progress_count = sum(1 for a in analyses if a.status == 'in_progress')
    
    incidents_count = 0
    if analysis_ids:
        incidents_count = Incident.query.filter(
            Incident.analysis_id.in_(analysis_ids)
        ).count()
    
    recent_analyses = sorted(
        analyses,
        key=lambda a: a.created_at or 0,
        reverse=True
    )[:10]

    return jsonify({
        'active_monitoring': len(user_aois),
        'analyses_completed': completed_count,
        'analyses_in_progress': in_progress_count,
        'incidents_detected': incidents_count,
        'recent_analyses': [
            {
                'id': a.id,
                'aoi_name': a.aoi.name if a.aoi else 'Unknown',
                'status': a.status,
                'progress': a.progress,
                'current_agent': a.current_agent,
                'date': a.created_at.isoformat() if a.created_at else None
            }
            for a in recent_analyses
        ]
    })


@dashboard_bp.route('/summary', methods=['GET'])
@jwt_required
def get_summary():
    """Get a high-level summary for the dashboard."""
    user_aois = AOI.query.filter_by(user_id=get_current_user_id()).all()
    aoi_ids = [a.id for a in user_aois]
    
    severity_counts = {
        'critical': 0,
        'high': 0,
        'medium': 0,
        'low': 0
    }
    
    if aoi_ids:
        analysis_ids = [
            a.id for a in Analysis.query.filter(Analysis.aoi_id.in_(aoi_ids)).all()
        ]
        
        if analysis_ids:
            incidents = Incident.query.filter(
                Incident.analysis_id.in_(analysis_ids)
            ).all()
            
            for inc in incidents:
                severity = (inc.severity or 'medium').lower()
                if severity in severity_counts:
                    severity_counts[severity] += 1
    
    return jsonify({
        'total_aois': len(aoi_ids),
        'severity_breakdown': severity_counts,
        'total_incidents': sum(severity_counts.values())
    })
