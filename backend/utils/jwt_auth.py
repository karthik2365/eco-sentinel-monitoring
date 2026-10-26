"""
JWT Authentication Utility

Provides JWT token creation and validation for stateless authentication.
Tokens survive server restarts since they're validated by signature.
"""

import jwt as pyjwt
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, Callable

from flask import request, jsonify, g

from config import Config


# Token expiry (24 hours)
TOKEN_EXPIRY_HOURS = 24


def create_access_token(user_id: int, username: str) -> str:
    """
    Create a JWT access token for a user.
    
    Args:
        user_id: User's database ID
        username: User's username
        
    Returns:
        JWT token string
    """
    payload = {
        'user_id': user_id,
        'username': username,
        'exp': datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS),
        'iat': datetime.utcnow()
    }
    
    return pyjwt.encode(payload, Config.SECRET_KEY, algorithm='HS256')


def decode_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded payload dict or None if invalid
    """
    try:
        payload = pyjwt.decode(token, Config.SECRET_KEY, algorithms=['HS256'])
        return payload
    except pyjwt.ExpiredSignatureError:
        return None
    except pyjwt.InvalidTokenError:
        return None


def jwt_required(f: Callable) -> Callable:
    """
    Decorator to require valid JWT token for a route.
    
    Sets g.current_user_id and g.current_username on success.
    Returns 401 if token is missing or invalid.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        payload = decode_token(token)
        if not payload:
            return jsonify({'error': 'Token is invalid or expired'}), 401
        
        # Set user info in flask g object
        g.current_user_id = payload['user_id']
        g.current_username = payload['username']
        
        return f(*args, **kwargs)
    
    return decorated


def get_current_user_id() -> Optional[int]:
    """Get current user ID from g object."""
    return getattr(g, 'current_user_id', None)
