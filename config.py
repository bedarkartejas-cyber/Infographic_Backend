import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API Keys (required)
    A2E_API_KEY = os.getenv("A2E_API_KEY")
    A2E_BASE_URL = os.getenv("A2E_BASE_URL")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    # Supabase Configuration (required)
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
    
    # Server Configuration
    ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
    PORT = int(os.getenv("PORT", "5000"))
    HOST = os.getenv("HOST", "0.0.0.0")
    WORKERS = int(os.getenv("WORKERS", "2"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "info")
    
    # Security
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")
    RATE_LIMIT = int(os.getenv("RATE_LIMIT", "100"))
    
    # Performance Settings
    MAX_IMAGES = 5  # Maximum images per request
    FILE_SIZE_LIMIT = 10 * 1024 * 1024  # 10MB max file size
    
    # Timeout Settings (in seconds)
    REQUEST_TIMEOUT = 300  # 5 minutes for long-running requests
    A2E_TIMEOUT = 600  # 10 minutes for A2E generation
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        missing = []
        
        required = [
            ("A2E_API_KEY", cls.A2E_API_KEY),
            ("A2E_BASE_URL", cls.A2E_BASE_URL),
            ("OPENAI_API_KEY", cls.OPENAI_API_KEY),
            ("SUPABASE_URL", cls.SUPABASE_URL),
            ("SUPABASE_SERVICE_KEY", cls.SUPABASE_SERVICE_KEY)
        ]
        
        for name, value in required:
            if not value:
                missing.append(name)
        
        if missing:
            raise ValueError(f"Missing required environment variables: {missing}")
        
        return True

config = Config()