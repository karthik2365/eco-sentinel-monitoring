"""
Base Agent Class

Provides common functionality for all AI agents in the Eco-Sentinel system.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional

from extensions import db, socketio
from services.events import emit_analysis
from models.analysis_incident import AgentLog

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the multi-agent pipeline.
    
    Provides:
    - Logging to database and WebSocket
    - Status management
    - Common interface for execution
    """
    
    def __init__(self, agent_id: str, name: str):
        """
        Initialize the agent.
        
        Args:
            agent_id: Unique identifier for the agent instance
            name: Human-readable agent name
        """
        self.agent_id = agent_id
        self.name = name
        self.status = "idle"
    
    def log_action(
        self,
        analysis_id: int,
        action: str,
        status: str = "success",
        reasoning: str = "",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an action to the database and emit WebSocket event.
        
        Args:
            analysis_id: ID of the current analysis
            action: Action being performed
            status: Status of the action ('success', 'error', 'info')
            reasoning: Explanation of the action
            details: Additional structured details
        """
        try:
            log_entry = AgentLog(
                analysis_id=analysis_id,
                agent_name=self.name,
                action=action,
                status=status,
                reasoning=reasoning,
                details=details or {},
                timestamp=datetime.utcnow()
            )
            db.session.add(log_entry)
            db.session.commit()

            # Emit WebSocket events
            self._emit_log(log_entry)
            
            if reasoning:
                self._emit_reasoning(analysis_id, reasoning)
                
        except Exception as e:
            logger.error(f"Error logging action for {self.name}: {e}")

    def update_status(self, new_status: str) -> None:
        """
        Update agent status and notify clients.
        
        Args:
            new_status: New status ('idle', 'working', 'completed', 'failed')
        """
        self.status = new_status
        
        emit_analysis('agent_status', {
            'analysis_id': getattr(self, 'analysis_id', None),
            'agent_name': self.name,
            'status': self.status,
            'timestamp': datetime.utcnow().isoformat()
        })
        


    def _emit_log(self, log_entry: AgentLog) -> None:
        """Emit log entry via WebSocket."""
        emit_analysis('new_log', {
            'analysis_id': log_entry.analysis_id,
            'timestamp': log_entry.timestamp.isoformat(),
            'agent': self.name,
            'message': f"{log_entry.action}: {log_entry.status}"
        })

    def _emit_reasoning(self, analysis_id: int, reasoning: str) -> None:
        """Emit agent reasoning via WebSocket."""
        emit_analysis('agent_reasoning', {
            'analysis_id': getattr(self, 'analysis_id', None),
            'agent_name': self.name,
            'reasoning': reasoning
        })

    @abstractmethod
    def execute(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Execute the agent's main task.
        
        This method must be implemented by all agent subclasses.
        
        Returns:
            Dict containing at minimum {'status': 'success'|'error', ...}
        """
        raise NotImplementedError("Agents must implement execute method")
