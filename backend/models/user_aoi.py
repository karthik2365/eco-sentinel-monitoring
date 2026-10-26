"""
User and AOI Models

Database models for user management and areas of interest.
"""

from datetime import datetime
from typing import Optional

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db, login_manager


@login_manager.user_loader
def load_user(user_id: str):
    """Load user by ID for Flask-Login."""
    return db.session.get(User, int(user_id))


class User(UserMixin, db.Model):
    """
    User account model.
    
    Attributes:
        id: Primary key
        username: Unique username
        email: Email address
        password_hash: Hashed password
        created_at: Account creation timestamp
    """
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    aois = db.relationship('AOI', backref='user', lazy='dynamic')

    def set_password(self, password: str) -> None:
        """Hash and store password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify password against stored hash."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self) -> str:
        return f'<User {self.username}>'


class AOI(db.Model):
    """
    Area of Interest model.
    
    Represents a geographic region being monitored for environmental changes.
    
    Attributes:
        id: Primary key
        user_id: Owner user ID
        name: Human-readable name
        geometry: GeoJSON geometry
        area_km2: Area in square kilometers
        monitoring_mode: 'watchdog' or 'on_demand'
        status: 'active', 'paused', etc.
        created_at: Creation timestamp
    """
    __tablename__ = 'aoi'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    geometry = db.Column(db.JSON, nullable=False)
    area_km2 = db.Column(db.Float)
    monitoring_mode = db.Column(db.String(20), default='on_demand')
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    analyses = db.relationship('Analysis', backref='aoi', lazy='dynamic')
    
    def __repr__(self) -> str:
        return f'<AOI {self.name}>'
