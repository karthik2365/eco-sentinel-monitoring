"""
Flask Extensions Module

Centralizes initialization of Flask extensions to avoid circular imports.
Extensions are initialized without app context here, then bound to app in create_app().
"""

from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_login import LoginManager

# Database ORM
db = SQLAlchemy()

# WebSocket support for real-time updates
socketio = SocketIO()

# User session management
login_manager = LoginManager()
login_manager.session_protection = 'strong'

@login_manager.unauthorized_handler
def unauthorized():
    from flask import jsonify
    return jsonify({'error': 'Unauthorized', 'message': 'Please log in to access this resource'}), 401

@socketio.on('connect')
def socket_connect(auth=None):
    from utils.jwt_auth import decode_token
    from flask_socketio import join_room
    payload = decode_token((auth or {}).get('token', ''))
    if not payload:
        return False
    join_room(f"user:{payload['user_id']}")
