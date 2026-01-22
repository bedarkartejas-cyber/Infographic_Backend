import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

class SupabaseConfig:
    """Supabase configuration"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SupabaseConfig, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize Supabase client"""
        self.url = os.getenv("SUPABASE_URL")
        self.anon_key = os.getenv("SUPABASE_ANON_KEY")
        self.service_key = os.getenv("SUPABASE_SERVICE_KEY")
        
        print(f"🔗 Supabase URL: {self.url}")
        
        # ALWAYS use service key to bypass RLS
        if self.url and self.service_key:
            try:
                print("🔑 Using SERVICE ROLE key (bypasses RLS)")
                self.client = create_client(self.url, self.service_key)
                print("✅ Supabase client initialized with service role")
            except Exception as e:
                print(f"❌ Failed to initialize with service key: {e}")
                self.client = None
        elif self.url and self.anon_key:
            try:
                print("⚠️  Using ANON key (might have RLS issues)")
                self.client = create_client(self.url, self.anon_key)
                print("✅ Supabase client initialized with anon key")
            except Exception as e:
                print(f"❌ Failed to initialize with anon key: {e}")
                self.client = None
        else:
            print("⚠️  Supabase credentials not found")
            self.client = None
    
    def get_client(self) -> Client:
        """Get Supabase client"""
        return self.client
    
    def is_configured(self) -> bool:
        """Check if Supabase is properly configured"""
        return self.client is not None
    
    def get_storage_url(self, path: str) -> str:
        """Get public URL for storage file"""
        if not self.url:
            return f"local/{path}"
        return f"{self.url}/storage/v1/object/public/marketing-images/{path}"

# Global instance
supabase_config = SupabaseConfig()