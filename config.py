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
    # In production, change this to your specific frontend URL (e.g., https://myapp.vercel.app)
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
    RATE_LIMIT = int(os.getenv("RATE_LIMIT", "100"))
    
    # --- Performance & Constraints ---
    MAX_IMAGES = 5  
    FILE_SIZE_LIMIT = 10 * 1024 * 1024  # 10MB
    
    # --- Timeout Settings (Seconds) ---
    # Long timeouts are necessary for parallel image generation tasks
    REQUEST_TIMEOUT = 300  
    A2E_TIMEOUT = 600  

    @classmethod
    def validate(cls):
        """
        Validates that all required environment variables are present.
        Call this during app startup to fail fast if config is missing.
        """
        missing = []
        
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
        
        if missing:
            error_msg = f"PRODUCTION ERROR: Missing required environment variables: {', '.join(missing)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info(f"Configuration validated successfully in {cls.ENVIRONMENT} mode.")
        return True

# Global instance
config = Config()

# Validate configuration on import for fail-fast behavior
if config.ENVIRONMENT == "production":
    config.validate()