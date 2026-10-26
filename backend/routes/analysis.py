"""
Analysis API Routes

Provides endpoints for starting and monitoring environmental analysis.
"""

import logging
from datetime import datetime
from typing import Any, Dict

from flask import Blueprint, request, jsonify

from extensions import db
from models.user_aoi import AOI
from models.analysis_incident import Analysis, Report, AgentLog
from utils.jwt_auth import jwt_required, get_current_user_id
from services.orchestrator import orchestrator

logger = logging.getLogger(__name__)

analysis_bp = Blueprint('analysis', __name__)

@analysis_bp.before_request
@jwt_required
def require_auth():
    pass

def owned_analysis(analysis_id):
    return Analysis.query.join(AOI).filter(Analysis.id == analysis_id, AOI.user_id == get_current_user_id()).first()



def validate_date(date_string: str) -> bool:
    """Validate date string format (YYYY-MM-DD)."""
    try:
        datetime.strptime(date_string, '%Y-%m-%d')
        return True
    except (ValueError, TypeError):
        return False


@analysis_bp.route('/start', methods=['POST'])
def start_analysis():
    """
    Start a new analysis for an AOI.
    
    Request Body:
        aoi_id: int - ID of the area of interest
        start_date: str - Start date (YYYY-MM-DD)
        end_date: str - End date (YYYY-MM-DD)
        analysis_type: str - Optional, defaults to 'on_demand'
        
    Returns:
        JSON with analysis_id on success, error message on failure
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    
    # Validate required fields
    aoi_id = data.get('aoi_id')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    comparison = None
    if 'comparison_mode' in data:
        from services.comparison_service import comparison_request
        try:
            comparison = comparison_request(data)
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400
        start_date = comparison['historical']['targetDate']
        end_date = comparison['current']['targetDate']

    
    if not aoi_id:
        return jsonify({'error': 'aoi_id is required'}), 400
    
    if not start_date or not validate_date(start_date):
        return jsonify({'error': 'Valid start_date (YYYY-MM-DD) is required'}), 400
    
    if not end_date or not validate_date(end_date):
        return jsonify({'error': 'Valid end_date (YYYY-MM-DD) is required'}), 400
    
    if start_date >= end_date:
        return jsonify({'error': 'End date must be after start date.'}), 400
    if end_date > datetime.utcnow().date().isoformat():
        return jsonify({'error': 'Choose a date range ending today or earlier.'}), 400
    # Verify AOI exists
    aoi = AOI.query.filter_by(id=aoi_id, user_id=get_current_user_id()).first()
    if not aoi:
        return jsonify({'error': 'AOI not found'}), 404

    if Analysis.query.filter_by(aoi_id=aoi.id).filter(Analysis.status.in_(['pending', 'in_progress'])).first():
        return jsonify({'error': 'This area already has an analysis running.'}), 409
    from services.scheduler import Monitor, FREQUENCIES, THRESHOLDS
    analysis_type = data.get('analysis_type', 'on_demand')
    if analysis_type not in ('on_demand', 'watchdog'):
        return jsonify({'error': 'Unknown analysis type'}), 400
    if comparison and analysis_type != 'on_demand':
        return jsonify({'error': 'Date comparisons are on-demand operations.'}), 400
    if analysis_type == 'watchdog':
        if data.get('frequency') not in FREQUENCIES or data.get('threshold') not in THRESHOLDS:
            return jsonify({'error': 'Choose a valid frequency and alert threshold.'}), 400
    try:
        # Create Analysis Record
        analysis = Analysis(
            aoi_id=aoi_id,
            analysis_type=data.get('analysis_type', 'on_demand'),
            baseline_date=datetime.strptime(start_date, '%Y-%m-%d').date(),
            comparison_date=datetime.strptime(end_date, '%Y-%m-%d').date()
        )
        db.session.add(analysis)
        db.session.flush()
        if comparison:
            db.session.add(AgentLog(analysis_id=analysis.id, agent_name='System',
                action='comparison_request', status='info',
                reasoning='Compare selected historical imagery with the requested later period.', details=comparison))
        db.session.commit()
        
        logger.info(f"Created analysis #{analysis.id} for AOI #{aoi_id}")
        
        if analysis_type == 'watchdog':
            from datetime import timedelta
            monitor = Monitor.query.filter_by(aoi_id=aoi_id).first()
            if monitor is None:
                monitor = Monitor(aoi_id=aoi_id)
                db.session.add(monitor)
            monitor.frequency = data['frequency']
            monitor.threshold = data['threshold']
            monitor.active = True
            monitor.last_analysis_id = analysis.id
            monitor.next_run = datetime.utcnow() + timedelta(days=FREQUENCIES[monitor.frequency])
            aoi.monitoring_mode = 'watchdog'
            db.session.commit()
        # Trigger Orchestrator
        orchestrator.start_analysis(
            analysis.id,
            aoi.geometry,
            start_date,
            end_date
        )
        
        return jsonify({
            'message': 'Analysis started',
            'analysis_id': analysis.id
        }), 201
        
    except Exception as e:
        logger.error(f"Failed to start analysis: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to start analysis'}), 500


@analysis_bp.route('/<int:analysis_id>', methods=['GET'])
def get_analysis(analysis_id: int):
    """
    Get analysis status and details.
    
    Path Parameters:
        analysis_id: int - ID of the analysis
        
    Returns:
        JSON with analysis details on success, error message on failure
    """
    analysis = owned_analysis(analysis_id)
    
    if not analysis:
        return jsonify({'error': 'Analysis not found'}), 404
    
    # Get PDF URL from report if available
    pdf_url = None
    if analysis.report:
        pdf_url = analysis.report.pdf_url
    
    comparison_log = analysis.logs.filter_by(action='comparison_result').first()
    request_log = analysis.logs.filter_by(action='comparison_request').first()
    comparison = comparison_log.details if comparison_log else request_log.details if request_log else None
    return jsonify({
        'comparison': comparison,
        'id': analysis.id,
        'aoi_id': analysis.aoi_id,
        'status': analysis.status,
        'progress': analysis.progress,
        'current_agent': analysis.current_agent,
        'analysis_type': analysis.analysis_type,
        'created_at': analysis.created_at.isoformat() if analysis.created_at else None,
        'completed_at': analysis.completed_at.isoformat() if analysis.completed_at else None,
        'pdf_url': pdf_url,
        'logs': [{'agent': l.agent_name, 'message': l.reasoning, 'status': l.status} for l in analysis.logs.order_by(AgentLog.id).all()],
        'error': next((l.reasoning for l in analysis.logs.order_by(AgentLog.id.desc()).all() if l.status == 'error'), None),
        'incidents': [
            {
                'id': i.id,
                'category': i.category,
                'severity': i.severity,
                'confidence': i.confidence
            }
            for i in analysis.incidents
        ]
    })


@analysis_bp.route('/<int:analysis_id>', methods=['DELETE'])
def delete_analysis(analysis_id: int):
    """
    Delete an analysis and all associated data.
    
    Path Parameters:
        analysis_id: int - ID of the analysis
        
    Returns:
        JSON confirmation message on success, error message on failure
    """
    analysis = owned_analysis(analysis_id)
    
    if not analysis:
        return jsonify({'error': 'Analysis not found'}), 404
    
    if analysis.status in ('pending', 'in_progress'):
        return jsonify({'error': 'Wait for the running analysis to finish before deleting it.'}), 409
    try:
        # Delete associated reports and incidents (cascade should handle this)
        db.session.delete(analysis)
        db.session.commit()
        
        logger.info(f"Deleted analysis #{analysis_id}")
        
        return jsonify({
            'message': 'Analysis deleted successfully',
            'analysis_id': analysis_id
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to delete analysis #{analysis_id}: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to delete analysis'}), 500


@analysis_bp.route('/reports/<int:analysis_id>', methods=['GET'])
def get_report(analysis_id: int):
    """
    Get the generated report for an analysis.
    
    Path Parameters:
        analysis_id: int - ID of the analysis
        
    Returns:
        JSON with report content on success, error message on failure
    """
    if not owned_analysis(analysis_id):
        return jsonify({'error': 'Analysis not found'}), 404
    report = Report.query.filter_by(analysis_id=analysis_id).first()
    
    if not report:
        return jsonify({'error': 'Report not found'}), 404
    
    return jsonify({
        'id': report.id,
        'analysis_id': report.analysis_id,
        'title': report.title,
        'content_html': report.content_html,
        'pdf_url': report.pdf_url,
        'created_at': report.generated_at.isoformat() if report.generated_at else None
    })


@analysis_bp.route('/list', methods=['GET'])
def list_analyses():
    """
    List all analyses with optional filtering.
    
    Query Parameters:
        status: str - Filter by status (pending, in_progress, completed, failed)
        limit: int - Maximum number of results (default: 50)
        
    Returns:
        JSON array of analysis summaries
    """
    status_filter = request.args.get('status')
    limit = min(int(request.args.get('limit', 50)), 100)
    
    query = Analysis.query.join(AOI).filter(AOI.user_id == get_current_user_id()).order_by(Analysis.created_at.desc())
    
    if status_filter:
        query = query.filter(Analysis.status == status_filter)
    
    analyses = query.limit(limit).all()
    
    return jsonify([
        {
            'id': a.id,
            'aoi_id': a.aoi_id,
            'status': a.status,
            'progress': a.progress,
            'created_at': a.created_at.isoformat() if a.created_at else None,
            'incident_count': len(a.incidents)
        }
        for a in analyses
    ])
