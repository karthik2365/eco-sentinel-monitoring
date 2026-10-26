"""
Eco-Sentinel AI Agents Package

This package contains the multi-agent system for environmental monitoring:
- ImageryAgent: Acquires satellite imagery from Google Earth Engine
- DetectionAgent: Performs change detection analysis
- ClassificationAgent: Classifies detected changes using Gemini AI
- InvestigationAgent: Adds context and historical data
- ReportingAgent: Generates professional PDF reports
"""

from .base_agent import BaseAgent
from .imagery_agent import ImageryAgent
from .detection_agent import DetectionAgent
from .classification_agent import ClassificationAgent
from .investigation_agent import InvestigationAgent
from .reporting_agent import ReportingAgent

__all__ = [
    "BaseAgent",
    "ImageryAgent",
    "DetectionAgent",
    "ClassificationAgent",
    "InvestigationAgent",
    "ReportingAgent",
]
