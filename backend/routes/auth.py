"""
Authentication API Routes

Provides endpoints for user authentication using JWT tokens.
"""

import logging

from flask import Blueprint, request, jsonify

from extensions import db
from models.user_aoi import User
from utils.jwt_auth import create_access_token, decode_token, jwt_required, get_current_user_id

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Authenticate user and return JWT token.
    
    Request Body:
        username: str
        password: str
        
    Returns:
        JSON with token and user info on success
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    user = User.query.filter_by(username=username).first()
    
    if user and user.check_password(password):
        token = create_access_token(user.id, user.username)
        logger.info(f"User '{username}' logged in")
        
        return jsonify({
            'message': 'Login successful',
            'token': token,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email
            }
        })
    
    return jsonify({'error': 'Invalid credentials'}), 401


@auth_bp.route('/status', methods=['GET'])
@jwt_required
def status():
    """Check authentication status (requires valid token)."""
    user = User.query.get(get_current_user_id())
    
    if user:
        return jsonify({
            'authenticated': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email
            }
        })
    
    return jsonify({'authenticated': False}), 401


@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user."""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    
    if not username or len(username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters'}), 400
    
    if not email or '@' not in email:
        return jsonify({'error': 'Valid email required'}), 400
    
    if not password or len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username taken'}), 409
    
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 409
    
    try:
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        # Auto-login: return token
        token = create_access_token(user.id, user.username)
        logger.info(f"New user registered: {username}")
        
        return jsonify({
            'message': 'Registration successful',
            'token': token,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email
            }
        }), 201
        
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        db.session.rollback()
        return jsonify({'error': 'Registration failed'}), 500
