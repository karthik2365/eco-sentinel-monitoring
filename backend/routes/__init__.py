"""
Eco-Sentinel API Routes Package

Contains Flask blueprints for:
- auth: Authentication endpoints
- dashboard: Dashboard metrics
- map: Map and AOI operations
- analysis: Analysis operations and reports
"""

from .auth import auth_bp
from .dashboard import dashboard_bp
from .map import map_bp
from .analysis import analysis_bp

__all__ = [
    "auth_bp",
    "dashboard_bp",
    "map_bp",
    "analysis_bp",
]
