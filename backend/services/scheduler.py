"""Persistent local schedules. Checks run while this single local server is open."""
from datetime import datetime, timedelta
from threading import Thread, Event
from extensions import db
from models.user_aoi import AOI
from models.analysis_incident import Analysis

FREQUENCIES = {'daily': 1, 'weekly': 7, 'biweekly': 14}
THRESHOLDS = {'any': 0, 'moderate': 1, 'significant': 2, 'critical': 3}
SEVERITIES = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}

class Monitor(db.Model):
    __tablename__ = 'monitor'
    id = db.Column(db.Integer, primary_key=True)
    aoi_id = db.Column(db.Integer, db.ForeignKey('aoi.id'), nullable=False, unique=True)
    frequency = db.Column(db.String(20), nullable=False)
    threshold = db.Column(db.String(20), nullable=False)
    active = db.Column(db.Boolean, default=True)
    next_run = db.Column(db.DateTime, nullable=False)
    last_analysis_id = db.Column(db.Integer)
    aoi = db.relationship(AOI)

    def to_dict(self):
        last = db.session.get(Analysis, self.last_analysis_id) if self.last_analysis_id else None
        alerts = [] if not last or last.status != 'completed' else [i.category for i in last.incidents if SEVERITIES.get(i.severity,0) >= THRESHOLDS[self.threshold]]
        return {'id': self.id, 'name': self.aoi.name, 'frequency': self.frequency,
                'threshold': self.threshold, 'active': self.active,
                'next_run': self.next_run.isoformat() + 'Z', 'last_analysis_id': self.last_analysis_id,
                'last_status': last.status if last else None, 'alerts': alerts}


def run_due(app):
    from services.orchestrator import orchestrator
    with app.app_context():
        now = datetime.utcnow()
        for monitor in Monitor.query.filter(Monitor.active.is_(True), Monitor.next_run <= now).all():
            if Analysis.query.filter_by(aoi_id=monitor.aoi_id).filter(Analysis.status.in_(['pending','in_progress'])).first():
                continue
            end = now.date(); start = end - timedelta(days=30)
            analysis = Analysis(aoi_id=monitor.aoi_id, analysis_type='watchdog', baseline_date=start, comparison_date=end)
            db.session.add(analysis); db.session.flush()
            monitor.last_analysis_id = analysis.id
            monitor.next_run = now + timedelta(days=FREQUENCIES[monitor.frequency])
            db.session.commit()
            orchestrator.start_analysis(analysis.id, monitor.aoi.geometry, start.isoformat(), end.isoformat())


def start_scheduler(app):
    stop = Event()
    def loop():
        while not stop.wait(60):
            try:
                run_due(app)
            except Exception:
                app.logger.exception('Scheduled check failed')
    Thread(target=loop, name='eco-watchdog', daemon=True).start()
    app.extensions['eco_scheduler_stop'] = stop
