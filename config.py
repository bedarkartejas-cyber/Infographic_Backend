import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file for local development
load_dotenv()

# Configure logging for initialization
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Config:
    """
    Production-ready Configuration management.
    Centralizes all environment variables with strict validation.
    """
    # --- API Keys (Required) ---
    A2E_API_KEY = os.getenv("A2E_API_KEY")
    A2E_BASE_URL = os.getenv("A2E_BASE_URL")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    # --- Supabase Configuration (Required) ---
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
    # CRITICAL: Required for auth_middleware.py to verify JWT signatures
    SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
    
    # --- Server Configuration ---
    ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
    # Railway/Render provide the PORT dynamically
    PORT = int(os.getenv("PORT", "5000"))
    HOST = os.getenv("HOST", "0.0.0.0")
    WORKERS = int(os.getenv("WORKERS", "2"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "info")
    
    # --- Security ---
    # CRITICAL: Set this to your frontend URL in production
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").strip()
    RATE_LIMIT = int(os.getenv("RATE_LIMIT", "100"))
    
    # --- Performance & Constraints ---
    MAX_IMAGES = int(os.getenv("MAX_IMAGES", "5"))
    FILE_SIZE_LIMIT = int(os.getenv("FILE_SIZE_LIMIT", str(10 * 1024 * 1024)))  # 10MB default
    
    # --- Timeout Settings (Seconds) ---
    # Long timeouts are necessary for parallel image generation tasks
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "300"))
    A2E_TIMEOUT = int(os.getenv("A2E_TIMEOUT", "600"))

    @classmethod
    def validate(cls):
        """
        Validates that all required environment variables are present.
        Call this during app startup to fail fast if config is missing.
        """
        missing = []
        warnings = []
        
        # Critical variables
        required_vars = [
            ("A2E_API_KEY", cls.A2E_API_KEY),
            ("A2E_BASE_URL", cls.A2E_BASE_URL),
            ("OPENAI_API_KEY", cls.OPENAI_API_KEY),
            ("SUPABASE_URL", cls.SUPABASE_URL),
            ("SUPABASE_SERVICE_KEY", cls.SUPABASE_SERVICE_KEY),
            ("SUPABASE_JWT_SECRET", cls.SUPABASE_JWT_SECRET)
        ]
        
        for name, value in required_vars:
            if not value:
                missing.append(name)
        
        # Production-specific warnings
        if cls.ENVIRONMENT == "production":
            if not cls.ALLOWED_ORIGINS or cls.ALLOWED_ORIGINS == "*":
                warnings.append("ALLOWED_ORIGINS not set or set to '*' - CORS is wide open!")
            
            if cls.PORT == 5000 and "PORT" not in os.environ:
                warnings.append("PORT not set - using default 5000 (cloud platforms usually set this)")
        
        # Fail fast on missing critical vars
        if missing:
            error_msg = f"❌ CRITICAL: Missing required environment variables: {', '.join(missing)}"
            logger.error(error_msg)
            logger.error("Set these in your cloud platform's environment variables dashboard")
            raise ValueError(error_msg)
        
        # Log warnings
        for warning in warnings:
            logger.warning(f"⚠️  {warning}")
        
        # Success message
        logger.info(f"✅ Configuration validated successfully")
        logger.info(f"   Environment: {cls.ENVIRONMENT}")
        logger.info(f"   Port: {cls.PORT}")
        logger.info(f"   Workers: {cls.WORKERS}")
        logger.info(f"   Max Images: {cls.MAX_IMAGES}")
        logger.info(f"   Request Timeout: {cls.REQUEST_TIMEOUT}s")
        
        if cls.ALLOWED_ORIGINS and cls.ALLOWED_ORIGINS != "*":
            logger.info(f"   CORS Origins: {cls.ALLOWED_ORIGINS}")
        
        return True
    
    @classmethod
    def get_cors_origins(cls):
        """Parse ALLOWED_ORIGINS into a list"""
        if not cls.ALLOWED_ORIGINS or cls.ALLOWED_ORIGINS == "*":
            if cls.ENVIRONMENT == "production":
                logger.warning("⚠️  Using wildcard CORS in production!")
            return ["*"]
        
        # Split by comma and clean whitespace
        origins = [origin.strip() for origin in cls.ALLOWED_ORIGINS.split(",")]
        origins = [origin for origin in origins if origin]  # Remove empty strings
        
        return origins if origins else ["*"]

# Global instance
config = Config()

# Validate configuration on import for fail-fast behavior
try:
    config.validate()
except ValueError as e:
    # Re-raise to prevent app from starting with invalid config
    raise SystemExit(f"Configuration validation failed: {e}")
