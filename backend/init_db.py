"""
Database Initialization Script

Initializes the database with tables and seed data.
Run with: python init_db.py
"""

import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def init_db():
    """Initialize database tables and create demo data."""
    from app import create_app
    from extensions import db
    from models.user_aoi import User, AOI
    
    app = create_app()
    
    with app.app_context():
        logger.info("Creating database tables...")
        db.create_all()
        
        # Create demo user if not exists
        if not User.query.filter_by(username='demo').first():
            logger.info("Creating demo user...")
            user = User(username='admin', email='demo@example.com')
            user.set_password('password123')
            db.session.add(user)
            db.session.commit()
            
            logger.info("Demo data created successfully!")
            logger.info("  Username: demo")
            logger.info("  Password: demo123")
        else:
            logger.info("Demo data already exists")
        
        logger.info("Database initialization complete!")


def reset_db():
    """Drop all tables and reinitialize. USE WITH CAUTION!"""
    from app import create_app
    from extensions import db
    
    app = create_app()
    
    with app.app_context():
        logger.warning("Dropping all tables...")
        db.drop_all()
        logger.info("Tables dropped")
    
    init_db()


if __name__ == '__main__':
    # Ensure upload folder exists
    from config import Config
    
    if not os.path.exists(Config.UPLOAD_FOLDER):
        os.makedirs(Config.UPLOAD_FOLDER)
        logger.info(f"Created upload folder: {Config.UPLOAD_FOLDER}")
    
    # Check for reset flag
    if len(sys.argv) > 1 and sys.argv[1] == '--reset':
        confirm = input("This will DELETE ALL DATA. Type 'yes' to confirm: ")
        if confirm.lower() == 'yes':
            reset_db()
        else:
            logger.info("Reset cancelled")
    else:
        init_db()
