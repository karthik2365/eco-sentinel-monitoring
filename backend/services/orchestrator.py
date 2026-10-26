"""
Eco-Sentinel Multi-Agent Orchestrator

Coordinates the execution of the AI agent pipeline for environmental analysis.
Manages agent lifecycle, progress tracking, and error handling.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from flask import current_app
import traceback
from datetime import datetime
from typing import Any, Dict, Optional

from extensions import db, socketio
from services.events import emit_analysis
from models.analysis_incident import Analysis, Incident, AgentLog

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Orchestrates the multi-agent analysis pipeline.
    
    The pipeline consists of:
    1. ImageryAgent - Acquires satellite imagery
    2. DetectionAgent - Detects changes
    3. ClassificationAgent - Classifies incidents
    4. InvestigationAgent - Adds context
    5. ReportingAgent - Generates reports
    """
    
    # Progress milestones for each stage
    PROGRESS_MILESTONES = {
        'imagery': 5,
        'detection': 25,
        'classification': 50,
        'investigation': 70,
        'reporting': 85,
        'complete': 100
    }
    
    def __init__(self):
        """Initialize the orchestrator with lazy-loaded agents."""
        self._imagery_agent = None
        self._detection_agent = None
        self._classification_agent = None
        self._investigation_agent = None
        self._reporting_agent = None
        self._app = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="eco-analysis")
    
    @property
    def imagery_agent(self):
        if self._imagery_agent is None:
            from agents.imagery_agent import ImageryAgent
            self._imagery_agent = ImageryAgent()
        return self._imagery_agent
    
    @property
    def detection_agent(self):
        if self._detection_agent is None:
            from agents.detection_agent import DetectionAgent
            self._detection_agent = DetectionAgent()
        return self._detection_agent
    
    @property
    def classification_agent(self):
        if self._classification_agent is None:
            from agents.classification_agent import ClassificationAgent
            self._classification_agent = ClassificationAgent()
        return self._classification_agent
    
    @property
    def investigation_agent(self):
        if self._investigation_agent is None:
            from agents.investigation_agent import InvestigationAgent
            self._investigation_agent = InvestigationAgent()
        return self._investigation_agent
    
    @property
    def reporting_agent(self):
        if self._reporting_agent is None:
            from agents.reporting_agent import ReportingAgent
            self._reporting_agent = ReportingAgent()
        return self._reporting_agent
    
    def _get_app(self):
        """Get or create Flask app instance for thread context."""
        if self._app is None:
            from app import create_app
            self._app = create_app()
        return self._app

    def start_analysis(
        self, 
        analysis_id: int, 
        aoi_geometry: Dict[str, Any], 
        start_date: str, 
        end_date: str
    ) -> None:
        """
        Start the analysis pipeline in a background thread.
        
        Args:
            analysis_id: ID of the analysis record
            aoi_geometry: GeoJSON geometry of the area of interest
            start_date: Start date for imagery search (YYYY-MM-DD)
            end_date: End date for imagery search (YYYY-MM-DD)
        """
        self._app = current_app._get_current_object()
        self._executor.submit(self._run_pipeline, analysis_id, aoi_geometry, start_date, end_date)
        logger.info(f"Analysis #{analysis_id} started")

    def _run_pipeline(
        self, 
        analysis_id: int, 
        aoi_geometry: Dict[str, Any], 
        start_date: str, 
        end_date: str
    ) -> None:
        """
        Execute the full analysis pipeline.
        
        This runs in a separate thread and requires its own app context.
        """
        app = self._get_app()
        
        with app.app_context():
            try:

                # Get analysis record
                analysis = db.session.get(Analysis, analysis_id)
                if not analysis:
                    logger.error(f"Analysis {analysis_id} not found")
                    return
                
                # Update to in progress
                self._update_analysis_status(
                    analysis, 
                    status="in_progress",
                    agent=self.imagery_agent.name,
                    progress=self.PROGRESS_MILESTONES['imagery']
                )
                
                from services.gemini_service import gemini_service
                for agent in (self.imagery_agent, self.detection_agent, self.classification_agent, self.investigation_agent, self.reporting_agent):
                    agent.analysis_id = analysis_id
                request_log = analysis.logs.filter_by(action='comparison_request').first()
                if request_log:
                    from services.comparison_service import acquire_comparison, save_comparison
                    comparison, paths = acquire_comparison(analysis_id, aoi_geometry, request_log.details)
                    # The dated visual and numeric comparison never depends on an AI key.
                    if len(paths) != 2:
                        comparison.update(aiStatus='unavailable', message='One period has no usable image. Choose another date; the available image is shown below.')
                        save_comparison(analysis_id, comparison)
                        self._comparison_ready(analysis, comparison['message'])
                        return
                    if not all(comparison[side]['readyForAnalysis'] for side in ('historical', 'current')):
                        comparison.update(aiStatus='limited_coverage', message='Visual comparison is ready. AI interpretation is skipped because one period has incomplete coverage. Vegetation measurements use only pixels present in both periods.')
                        save_comparison(analysis_id, comparison)
                        self._comparison_ready(analysis, comparison['message'])
                        return
                    try:
                        gemini_service.check_connection()
                    except Exception as exc:
                        comparison.update(aiStatus='unavailable', message='Image and vegetation comparisons are ready. AI interpretation is unavailable: ' + str(exc))
                        save_comparison(analysis_id, comparison)
                        self._comparison_ready(analysis, comparison['message'])
                        return
                    comparison.update(aiStatus='running', message='Images ready; AI is comparing the two periods.')
                    save_comparison(analysis_id, comparison)
                    result_imagery = {'current_path': paths['current'], 'baseline_path': paths['historical'],
                                      'current_url': comparison['current']['imageUrl']}
                else:
                    # Preserve the existing scheduled / legacy analysis workflow.
                    gemini_service.check_connection()
                    result_imagery = self._execute_stage(
                        analysis_id, self.imagery_agent.name,
                        lambda: self.imagery_agent.execute(analysis_id, aoi_geometry, start_date, end_date))
                    if not result_imagery:
                        return

                self._update_analysis_status(
                    analysis,
                    agent=self.detection_agent.name,
                    progress=self.PROGRESS_MILESTONES['detection']
                )
                
                # Stage 2: Change Detection
                result_detection = self._execute_stage(
                    analysis_id,
                    self.detection_agent.name,
                    lambda: self.detection_agent.execute(
                        analysis_id,
                        current_image_url=result_imagery["current_path"],
                        baseline_image_url=result_imagery["baseline_path"],
                        aoi_geometry=aoi_geometry,
                        baseline_date=None
                    )
                )
                if not result_detection:
                    return
                
                self._update_analysis_status(
                    analysis,
                    agent=self.classification_agent.name,
                    progress=self.PROGRESS_MILESTONES['classification']
                )
                
                # Stage 3: Classification
                result_classification = self._execute_stage(
                    analysis_id,
                    self.classification_agent.name,
                    lambda: self.classification_agent.execute(
                        analysis_id,
                        image_url=result_imagery["current_url"], # Use URL for speed
                        detected_regions=result_detection["detected_regions"]
                    )
                )
                if not result_classification:
                    return
                
                # Save incidents to database
                incidents_data = result_classification["incidents"]
                saved_incidents = self._save_incidents(analysis_id, incidents_data)
                
                self._update_analysis_status(
                    analysis,
                    agent=self.investigation_agent.name,
                    progress=self.PROGRESS_MILESTONES['investigation']
                )
                
                # Stage 4: Investigation
                result_investigation = self._execute_stage(
                    analysis_id,
                    self.investigation_agent.name,
                    lambda: self.investigation_agent.execute(
                        analysis_id,
                        incidents=saved_incidents
                    )
                )
                if not result_investigation:
                    return
                
                self._update_analysis_status(
                    analysis,
                    agent=self.reporting_agent.name,
                    progress=self.PROGRESS_MILESTONES['reporting']
                )
                
                # Stage 5: Report Generation
                # We pass the Baseline (Before) and Current (After) image paths
                result_report = self._execute_stage(
                    analysis_id,
                    self.reporting_agent.name,
                    lambda: self.reporting_agent.execute(
                        analysis_id,
                        incidents=result_investigation["incidents"],
                        report_title=f"Eco-Sentinel Analysis {analysis_id}",
                        image_urls=[
                            result_imagery.get("baseline_path"), # Before
                            result_imagery.get("current_path")   # After
                        ]
                    )
                )
                if not result_report:
                    return
                
                if request_log:
                    comparison.update(aiStatus='completed', message='Image comparison and AI report ready.')
                    save_comparison(analysis_id, comparison)
                # Complete
                analysis.progress = self.PROGRESS_MILESTONES['complete']
                analysis.status = "completed"
                analysis.current_agent = "None"
                analysis.completed_at = datetime.utcnow()
                db.session.commit()
                
                self._emit_progress(analysis_id, 100, "Completed")
                
                logger.info(f"Analysis #{analysis_id} completed")
                
                emit_analysis('analysis_complete', {'analysis_id': analysis_id})
                
            except Exception as e:
                logger.error(f"Pipeline Error: {e}")
                logger.error(traceback.format_exc())
                self._fail_analysis(analysis_id, str(e))
    
    def _comparison_ready(self, analysis, message):
        analysis.status = 'comparison_ready'
        analysis.progress = 100
        analysis.current_agent = 'Comparison ready'
        analysis.completed_at = datetime.utcnow()
        db.session.commit()
        self._emit_progress(analysis.id, 100, message)
        emit_analysis('analysis_complete', {'analysis_id': analysis.id})

    def _execute_stage(
        self, 
        analysis_id: int, 
        stage_name: str, 
        executor: callable
    ) -> Optional[Dict[str, Any]]:
        """
        Execute a pipeline stage with error handling.
        
        Args:
            analysis_id: Analysis record ID
            stage_name: Human-readable stage name
            executor: Callable that executes the stage
            
        Returns:
            Stage result dict if successful, None if failed
        """
        try:
            result = executor()
            
            if result.get("status") != "success":
                error_msg = result.get("error", f"{stage_name} Failed")
                logger.error(f"{stage_name} failed: {error_msg}")
                self._fail_analysis(analysis_id, error_msg)
                return None
            

            return result
            
        except Exception as e:
            logger.error(f"{stage_name} error: {e}")
            self._fail_analysis(analysis_id, str(e))
            return None
    
    def _save_incidents(
        self, 
        analysis_id: int, 
        incidents_data: list
    ) -> list:
        """Save detected incidents to the database."""
        saved_incidents = []
        

        
        for inc_data in incidents_data:
            new_incident = Incident(
                analysis_id=analysis_id,
                category=inc_data.get("category", "Unknown"),
                severity=inc_data.get("severity", "medium"),
                confidence=inc_data.get("confidence", 0.5),
                description=inc_data.get("description", ""),
                location=inc_data.get("location"),
                affected_area=inc_data.get("affected_area")
            )
            db.session.add(new_incident)
            saved_incidents.append(inc_data)
        
        db.session.commit()

        
        return saved_incidents
    
    def _update_analysis_status(
        self,
        analysis: Analysis,
        status: Optional[str] = None,
        agent: Optional[str] = None,
        progress: Optional[int] = None
    ) -> None:
        """Update analysis record and emit progress event."""
        if status:
            analysis.status = status
        if agent:
            analysis.current_agent = agent
        if progress:
            analysis.progress = progress
            
        db.session.commit()
        
        if progress and agent:
            self._emit_progress(analysis.id, progress, agent)

    def _fail_analysis(self, analysis_id: int, reason: str) -> None:
        """Mark analysis as failed and notify clients."""
        try:
            analysis = db.session.get(Analysis, analysis_id)
            if analysis:
                comparison_log = analysis.logs.filter_by(action='comparison_result').first()
                if comparison_log:
                    details = dict(comparison_log.details)
                    details.update(aiStatus='failed', message='Image comparison remains available. AI report could not finish: ' + reason)
                    comparison_log.details = details
                analysis.status = "failed"
                analysis.current_agent = "Failed"
                db.session.commit()
        except Exception as e:
            logger.error(f"Failed to update analysis status: {e}")
            
        from models.analysis_incident import AgentLog
        db.session.add(AgentLog(analysis_id=analysis_id, agent_name='System', action='pipeline_failed', status='error', reasoning=reason))
        db.session.commit()
        emit_analysis('analysis_failed', {
            'analysis_id': analysis_id, 
            'reason': reason
        })
        
        logger.error(f"Analysis #{analysis_id} failed: {reason}")

    def _emit_progress(self, analysis_id: int, percent: int, stage: str) -> None:
        """Emit progress update via WebSocket."""
        emit_analysis('analysis_progress', {
            'analysis_id': analysis_id,
            'progress': percent,
            'current_stage': stage
        })


# Singleton instance
orchestrator = Orchestrator()
