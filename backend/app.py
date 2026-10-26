"""
Eco-Sentinel Flask Application Factory
"""

import logging
import os
from typing import Optional, Type

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from config import Config, get_config
from extensions import db, socketio, login_manager

# Configure logging - suppress verbose libs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Silence verbose libraries
logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
# logging.getLogger('werkzeug').setLevel(logging.WARNING)


def create_app(config_class: Optional[Type[Config]] = None) -> Flask:
    if config_class is None:
        config_class = get_config()
    
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    if not config_class.validate():
        logger.warning("Configuration validation failed. Some features may not work.")
    
    _init_extensions(app)
    _register_blueprints(app)
    _register_routes(app)
    
    with app.app_context():
        _init_database(app)
        _init_services(app)
    
    if not app.testing:
        from services.scheduler import start_scheduler
        start_scheduler(app)
    logger.info(f"Eco-Sentinel application created with {config_class.__name__}")
    return app


def _init_extensions(app: Flask) -> None:
    db.init_app(app)
    # Use threading mode for gunicorn compatibility in production
    # For development with eventlet, this still works
    socketio.init_app(app, cors_allowed_origins="*", async_mode='threading')
    login_manager.init_app(app)
    CORS(app)



def _register_blueprints(app: Flask) -> None:
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.map import map_bp
    from routes.analysis import analysis_bp
    
    from routes.monitors import monitors_bp
    app.register_blueprint(monitors_bp, url_prefix='/api/monitors')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
    app.register_blueprint(map_bp, url_prefix='/api/map')
    app.register_blueprint(analysis_bp, url_prefix='/api/analysis')



def _register_routes(app: Flask) -> None:
    # Serve generated PDF reports
    @app.route('/reports/<path:filename>')
    def serve_report(filename: str):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    
    # Serve backend static files (images, etc.)
    @app.route('/static/<path:filename>')
    def serve_static(filename: str):
        return send_from_directory('static', filename)
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        from services.gee_service import gee_service
        return jsonify({
            'status': 'healthy',
            'services': {
                'api': 'online',
                'database': 'connected',
                'satellite': 'ready' if gee_service.is_initialized else 'unavailable',
                'ai': 'configured; validation occurs on analysis' if Config.has_openrouter_keys() else 'key required'
            }
        })
    
    # === Production Frontend Serving ===
    # Serve built Vite frontend assets
    @app.route('/assets/<path:filename>')
    def serve_frontend_assets(filename: str):
        return send_from_directory('static/frontend/assets', filename)
    
    # Serve frontend root files (favicon, etc.)
    @app.route('/vite.svg')
    def serve_vite_svg():
        return send_from_directory('static/frontend', 'vite.svg')
    
    # Catch-all: Serve index.html for SPA client-side routing
    # This must be registered LAST
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path: str):
        # Don't intercept API routes
        if path.startswith('api/') or path.startswith('socket.io'):
            return jsonify({'error': 'Not found'}), 404
        
        # Check if requesting a specific file that exists
        frontend_path = os.path.join(app.root_path, 'static', 'frontend')
        if os.path.exists(frontend_path):
            file_path = os.path.join(frontend_path, path)
            if os.path.isfile(file_path):
                return send_from_directory(frontend_path, path)
            # Return index.html for SPA routing
            return send_from_directory(frontend_path, 'index.html')
        
        # Fallback for development (frontend not built)
        return jsonify({'error': 'Frontend not built. Run npm run build in frontend/'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return jsonify({'error': 'Internal server error'}), 500


def _init_database(app: Flask) -> None:
    """Initialize database tables and create default user if needed."""
    from models.user_aoi import User
    
    from models.analysis_incident import Analysis, AgentLog
    db.create_all()
    # Interrupted daemon jobs cannot resume after a restart; surface them honestly.
    if not app.testing:
        for job in Analysis.query.filter(Analysis.status.in_(['pending', 'in_progress'])).all():
            job.status = 'failed'
            job.current_agent = 'Interrupted'
            db.session.add(AgentLog(analysis_id=job.id, agent_name='System', action='restart', status='error', reasoning='Server stopped before this analysis completed. Start a new analysis.'))
        db.session.commit()
    
    # Auto-create default admin user if no users exist
    if User.query.count() == 0:
        logger.info("No users found - creating default admin user...")
        admin = User(username='demo', email='demo@ecosentinel.local')
        admin.set_password('demo123')
        db.session.add(admin)
        db.session.commit()
        logger.info("Local demo account created")



def _init_services(app: Flask) -> None:
    """Initialize external services."""
    from services.gee_service import gee_service
    
    try:
        key_path = app.config.get('GEE_SERVICE_ACCOUNT')
        project_id = app.config.get('GEE_PROJECT_ID', 'agentathon')
        
        logger.info(f"Initializing GEE with key: {key_path}, project: {project_id}")
        
        success = gee_service.initialize(key_path, project_id)
        
        if success:
            logger.info("GEE service initialized successfully")
        else:
            logger.warning("GEE service initialization returned False - imagery features may not work")

    except Exception as e:
        logger.error(f"Failed to initialize GEE service: {e}")


os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)


if __name__ == '__main__':
    app = create_app()
    socketio.run(app, host='127.0.0.1', port=int(os.environ.get('PORT', 5050)), debug=False, use_reloader=False, allow_unsafe_werkzeug=True)
