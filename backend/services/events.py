from extensions import socketio, db
from models.analysis_incident import Analysis

def emit_analysis(event, data):
    analysis_id = data.get('analysis_id')
    job = db.session.get(Analysis, analysis_id) if analysis_id else None
    if job and job.aoi:
        socketio.emit(event, data, to=f'user:{job.aoi.user_id}')
