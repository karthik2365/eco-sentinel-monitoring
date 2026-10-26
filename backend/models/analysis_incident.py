"""
Analysis and Incident Models

Database models for analysis tracking, incidents, logs, and reports.
"""

from datetime import datetime
from typing import Optional

from extensions import db


class Analysis(db.Model):
    """
    Analysis job tracking model.
    
    Represents a single analysis run on an AOI.
    
    Attributes:
        id: Primary key
        aoi_id: Associated area of interest
        analysis_type: Type of analysis ('on_demand', 'scheduled', etc.)
        baseline_date: Start date for analysis
        comparison_date: End date for analysis
        status: 'pending', 'in_progress', 'completed', 'failed'
        progress: Completion percentage (0-100)
        current_agent: Currently active agent name
        created_at: Creation timestamp
        completed_at: Completion timestamp
    """
    __tablename__ = 'analysis'
    
    id = db.Column(db.Integer, primary_key=True)
    aoi_id = db.Column(db.Integer, db.ForeignKey('aoi.id'), nullable=False, index=True)
    analysis_type = db.Column(db.String(50), default='on_demand')
    baseline_date = db.Column(db.Date)
    comparison_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='pending', index=True)
    progress = db.Column(db.Integer, default=0)
    current_agent = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    completed_at = db.Column(db.DateTime)
    
    # Relationships
    incidents = db.relationship('Incident', backref='analysis', lazy='select', cascade='all, delete-orphan')
    logs = db.relationship('AgentLog', backref='analysis', lazy='dynamic', cascade='all, delete-orphan')
    report = db.relationship('Report', backref='analysis', uselist=False, lazy='select', cascade='all, delete-orphan')
    
    def __repr__(self) -> str:
        return f'<Analysis {self.id} - {self.status}>'


class Incident(db.Model):
    """
    Detected environmental incident model.
    
    Represents a single detected environmental change or violation.
    
    Attributes:
        id: Primary key
        analysis_id: Parent analysis
        category: Type of incident (deforestation, construction, etc.)
        severity: Severity level (low, medium, high, critical)
        confidence: Detection confidence score (0-1)
        location: GeoJSON point of incident center
        affected_area: Area affected in square kilometers
        description: Detailed description
        gemini_analysis: Raw AI analysis text
        evidence_urls: List of supporting image URLs
        detected_at: Detection timestamp
    """
    __tablename__ = 'incident'
    
    id = db.Column(db.Integer, primary_key=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey('analysis.id'), nullable=False, index=True)
    category = db.Column(db.String(50), index=True)
    severity = db.Column(db.String(20), index=True)
    confidence = db.Column(db.Float)
    location = db.Column(db.JSON)
    affected_area = db.Column(db.Float)
    description = db.Column(db.Text)
    gemini_analysis = db.Column(db.Text)
    evidence_urls = db.Column(db.JSON)
    detected_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f'<Incident {self.id} - {self.category}>'


class AgentLog(db.Model):
    """
    Agent activity log model.
    
    Stores detailed logs of agent actions for debugging and audit.
    
    Attributes:
        id: Primary key
        analysis_id: Parent analysis
        agent_name: Name of the agent
        action: Action performed
        status: Status of the action
        reasoning: Agent's reasoning/explanation
        details: Additional structured details
        timestamp: Action timestamp
    """
    __tablename__ = 'agent_log'
    
    id = db.Column(db.Integer, primary_key=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey('analysis.id'), nullable=False, index=True)
    agent_name = db.Column(db.String(50), index=True)
    action = db.Column(db.String(100))
    status = db.Column(db.String(20))
    reasoning = db.Column(db.Text)
    details = db.Column(db.JSON)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self) -> str:
        return f'<AgentLog {self.agent_name} - {self.action}>'


class Report(db.Model):
    """
    Generated report model.
    
    Stores the generated report content and PDF reference.
    
    Attributes:
        id: Primary key
        analysis_id: Parent analysis (one-to-one)
        title: Report title
        content_html: Full HTML content
        pdf_url: URL/path to generated PDF
        generated_at: Generation timestamp
    """
    __tablename__ = 'report'
    
    id = db.Column(db.Integer, primary_key=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey('analysis.id'), nullable=False, unique=True)
    title = db.Column(db.String(200))
    content_html = db.Column(db.Text)
    pdf_url = db.Column(db.String(200))
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f'<Report {self.id} - {self.title}>'
