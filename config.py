import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # A2E API Settings
    A2E_API_KEY = os.getenv("A2E_API_KEY")
    A2E_BASE_URL = os.getenv("A2E_BASE_URL")
    
    # Performance Settings
    MAX_IMAGES_DEFAULT = 2
    MAX_IMAGES_FAST = 1
    MAX_IMAGES_FULL = 3
    
    # Timeout Settings (in seconds)
    A2E_SUBMIT_TIMEOUT = 15
    A2E_POLL_INTERVAL = 2
    A2E_MAX_POLL_TIME = 45  # 45 seconds per image max
    
    # Parallel Processing
    MAX_PARALLEL_IMAGES = 2  # Max 2 images at once
    
    # Supabase
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
    
    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        missing = []
        
        if not cls.A2E_API_KEY:
            missing.append("A2E_API_KEY")
        if not cls.A2E_BASE_URL:
            missing.append("A2E_BASE_URL")
        if not cls.OPENAI_API_KEY:
            missing.append("OPENAI_API_KEY")
        
        if missing:
            print(f"⚠️  Missing environment variables: {missing}")
            return False
        
        return True

config = Config()