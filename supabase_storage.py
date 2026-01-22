import os
import uuid
import logging
import requests
from datetime import datetime
from typing import Optional, Dict
from supabase_config import supabase_config

# Configure logging for production observability
logger = logging.getLogger(__name__)

class SupabaseStorage:
    """
    Production-ready handler for cloud image storage.
    Removed all local filesystem fallbacks to ensure data persistence 
    on ephemeral cloud hosting environments.
    """
    
    def __init__(self):
        # The bucket name must exist in your Supabase project
        self.bucket_name = "marketing-images"
    
    def upload_image_from_url(self, image_url: str, user_id: str, generation_id: str) -> Optional[Dict]:
        """
        Downloads an image from a source URL and uploads it directly to Supabase Storage.
        """
        try:
            logger.info(f"Starting image transfer for Generation: {generation_id}")
            
            # 1. Download image from the generation engine (A2E)
            # Using a stream and timeout to prevent hanging the worker
            response = requests.get(image_url, timeout=60, stream=True)
            response.raise_for_status()
            image_data = response.content
            
            # 2. Generate a structured, unique filename for organized storage
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            # Sanitize user_id for path safety
            safe_user_id = "".join(filter(str.isalnum, user_id))[:10]
            
            # Path format: {generation_id}/{user_prefix}_{timestamp}_{short_id}.png
            filename = f"{generation_id}/{safe_user_id}_{timestamp}_{unique_id}.png"
            
            # 3. Verify Supabase Configuration
            if not supabase_config or not supabase_config.is_configured():
                logger.error("Supabase Storage transfer failed: Provider not configured")
                return None
            
            client = supabase_config.get_client()
            
            # 4. Upload to Supabase Bucket
            # Production practice: Use content-type and upsert settings
            try:
                logger.info(f"Uploading to Supabase bucket '{self.bucket_name}': {filename}")
                
                # We perform the upload using the binary data retrieved
                client.storage.from_(self.bucket_name).upload(
                    path=filename,
                    file=image_data,
                    file_options={
                        "content-type": "image/png", 
                        "upsert": "true",
                        "cache-control": "3600"
                    }
                )
                
                # 5. Construct the public-facing URL
                public_url = supabase_config.get_storage_url(filename)
                
                logger.info(f"Successfully moved image to cloud storage: {filename}")
                
                return {
                    "storage_path": filename,
                    "public_url": public_url,
                    "filename": filename.split("/")[-1],
                    "storage_type": "supabase"
                }

            except Exception as upload_error:
                logger.error(f"Supabase Storage upload error: {str(upload_error)}")
                # In production, we do not fall back to local storage because 
                # local files are deleted on container restart.
                return None
            
        except requests.exceptions.RequestException as req_error:
            logger.error(f"Failed to download source image: {str(req_error)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in storage module: {str(e)}")
            return None

# Global instance for app-wide use
storage = SupabaseStorage()