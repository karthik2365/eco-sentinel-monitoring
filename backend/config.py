"""
Eco-Sentinel Configuration Module

Manages application configuration with environment variable support.
All sensitive values should be set via environment variables or .env file.
"""

import os
import secrets
import logging
from typing import List, Optional
from dotenv import load_dotenv

# Load .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Configure module logger
logger = logging.getLogger(__name__)


def _local_secret():
    from pathlib import Path
    path = Path(__file__).parent / '.local-secret'
    if not path.exists():
        path.write_text(secrets.token_hex(32))
        path.chmod(0o600)
    return path.read_text().strip()


class Config:
    """
    Application configuration class.
    
    Loads configuration from environment variables with sensible defaults.
    Sensitive values (API keys, secrets) should NEVER be hardcoded.
    """
    
    # ----- Core Flask Settings -----
    SECRET_KEY: str = os.environ.get('SECRET_KEY') or _local_secret()
    DEBUG: bool = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    
    # ----- Database -----
    SQLALCHEMY_DATABASE_URI: str = os.environ.get('DATABASE_URL', 'sqlite:///eco_sentinel_local.db')
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    
    # ----- File Storage -----
    UPLOAD_FOLDER: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reports')
    MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024  # 16 MB max upload
    
    # ----- OpenRouter API Configuration -----
    # Multiple API keys for rotation (comma-separated in env)
    OPENROUTER_API_KEYS: List[str] = [
        k.strip() for k in os.environ.get('OPENROUTER_API_KEYS', '').split(',') if k.strip()
    ]
    
    # Fallback single keys (legacy support)
    OPENROUTER_API_KEY: Optional[str] = os.environ.get('OPENROUTER_API_KEY')
    GEMINI_FLASH_OR_KEY: Optional[str] = os.environ.get('GEMINI_FLASH_OR_KEY')
    GEMMA_IT_OR_KEY: Optional[str] = os.environ.get('GEMMA_IT_OR_KEY')
    
    @classmethod
    def get_api_keys(cls) -> List[str]:
        """Get all available API keys for rotation."""
        keys = [cls.OPENROUTER_API_KEY] if cls.OPENROUTER_API_KEY else list(cls.OPENROUTER_API_KEYS)
        # Add individual keys if not already in list
        for key in [cls.OPENROUTER_API_KEY, cls.GEMINI_FLASH_OR_KEY, cls.GEMMA_IT_OR_KEY]:
            if key and key not in keys:
                keys.append(key)
        return keys
    
    @classmethod
    def has_openrouter_keys(cls) -> bool:
        """Check if at least one OpenRouter API key is configured."""
        return len(cls.get_api_keys()) > 0
    
    # ----- Google Earth Engine Configuration -----
    GEE_SERVICE_ACCOUNT: str = os.environ.get('GEE_SERVICE_ACCOUNT') or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 
        'service-key.json'
    )
    GEE_PROJECT_ID: Optional[str] = os.environ.get('GEE_PROJECT_ID', 'agentathon')
    
    # ----- CORS Configuration -----
    CORS_HEADERS: str = 'Content-Type'
    CORS_ORIGINS: List[str] = os.environ.get('CORS_ORIGINS', '*').split(',')
    
    # ----- Application Constants -----
    DEFAULT_CLOUD_THRESHOLD: int = 30
    DEFAULT_THUMBNAIL_DIMENSIONS: int = 2048
    DATE_SEARCH_WINDOW_DAYS: int = 30
    
    @classmethod
    def validate(cls) -> bool:
        """
        Validate critical configuration settings.
        
        Returns:
            True if configuration is valid, False otherwise.
        """
        is_valid = True
        
        if not cls.has_openrouter_keys():
            logger.error("CRITICAL: No OpenRouter API keys configured!")
            is_valid = False
            
        if not os.path.exists(cls.GEE_SERVICE_ACCOUNT):
            logger.warning(f"GEE service account file not found: {cls.GEE_SERVICE_ACCOUNT}")
            
        if not cls.SECRET_KEY or len(cls.SECRET_KEY) < 32:
            logger.warning("SECRET_KEY should be at least 32 characters for production")
            
        return is_valid


class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True
    SQLALCHEMY_ECHO = False  # Disable SQL query logging


class ProductionConfig(Config):
    """Production environment configuration."""
    DEBUG = False
    SQLALCHEMY_ECHO = False
    
    # In production, SECRET_KEY must be set via environment
    @classmethod
    def validate(cls) -> bool:
        is_valid = super().validate()
        
        if os.environ.get('SECRET_KEY') is None:
            logger.error("CRITICAL: SECRET_KEY must be set in production!")
            is_valid = False
            
        return is_valid


class TestingConfig(Config):
    """Testing environment configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


# Configuration selector
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(env: Optional[str] = None) -> type:
    """
    Get configuration class based on environment.
    
    Args:
        env: Environment name ('development', 'production', 'testing')
        
    Returns:
        Configuration class for the specified environment.
    """
    if env is None:
        env = os.environ.get('FLASK_ENV', 'development')
    return config_by_name.get(env, Config)
