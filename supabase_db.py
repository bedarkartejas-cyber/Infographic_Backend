import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from supabase_config import supabase_config
from supabase_storage import storage

# Configure logging for production observability
logger = logging.getLogger(__name__)

class MarketingDB:
    """
    Production-ready Database operations for Supabase.
    Removes in-memory fallbacks to ensure data consistency across multiple server workers.
    """
    
    def __init__(self):
        self.storage = storage
        self.table_generations = "marketing_generations"
        self.table_images = "marketing_images"
    
    def _get_client(self):
        """Get initialized Supabase client or raise error in production"""
        if supabase_config and supabase_config.is_configured():
            return supabase_config.get_client()
        raise ConnectionError("Supabase is not configured. Check environment variables.")
    
    def create_generation_session(
        self, 
        user_id: str,
        ppt_file_url: Optional[str] = None,
        website_url: Optional[str] = None,
        ppt_text: Optional[str] = None,
        website_text: Optional[str] = None
    ) -> str:
        """Create a new marketing generation session record"""
        generation_id = str(uuid.uuid4())
        
        data = {
            "id": generation_id,
            "user_id": user_id, 
            "ppt_file_url": ppt_file_url,
            "website_url": website_url,
            "ppt_text": ppt_text[:5000] if ppt_text else None,
            "website_text": website_text[:5000] if website_text else None,
            "status": "processing",
            "total_images": 0,
            "completed_images": 0,
            "created_at": datetime.now().isoformat()
        }
        
        # Clean data for Supabase (remove None values)
        supabase_data = {k: v for k, v in data.items() if v is not None}
        
        client = self._get_client()
        response = client.table(self.table_generations).insert(supabase_data).execute()
        
        if not response.data:
            logger.error(f"Failed to persist generation session: {generation_id}")
            raise RuntimeError("Database insertion failed")
            
        logger.info(f"Generation session persisted: {generation_id}")
        return generation_id
    
    def update_generation_assets(
        self,
        generation_id: str,
        marketing_brief: Dict,
        email_content: Dict,
        creative_angles: Dict,
        image_prompts: Dict,
        total_images: int
    ) -> bool:
        """Update generation with generated LLM text assets"""
        data = {
            "marketing_brief": marketing_brief,
            "email_content": email_content,
            "creative_angles": creative_angles,
            "image_prompts": image_prompts,
            "total_images": total_images,
            "updated_at": datetime.now().isoformat()
        }
        
        client = self._get_client()
        response = client.table(self.table_generations) \
            .update(data) \
            .eq("id", generation_id) \
            .execute()
        
        return len(response.data) > 0
    
    def add_generated_image(
        self,
        generation_id: str,
        user_id: str,
        angle_name: str,
        image_summary: str,
        prompt: str,
        image_url: str,
        image_index: int,
        generation_time: float
    ) -> Optional[Dict]:
        """Uploads image to storage and adds metadata record to DB"""
        # Upload to Cloud Storage
        storage_info = self.storage.upload_image_from_url(image_url, user_id, generation_id)
        
        if not storage_info:
            logger.error(f"Storage upload failed for image index {image_index}")
            return None
        
        image_data = {
            "id": str(uuid.uuid4()),
            "generation_id": generation_id,
            "user_id": user_id,
            "angle_name": angle_name[:255],
            "image_summary": image_summary[:1000] if image_summary else "",
            "prompt": prompt[:2000] if prompt else "",
            "image_url": storage_info["public_url"],
            "supabase_storage_path": storage_info["storage_path"],
            "storage_type": storage_info.get("storage_type", "supabase"),
            "image_index": image_index,
            "generation_time": generation_time,
            "created_at": datetime.now().isoformat()
        }
        
        client = self._get_client()
        response = client.table(self.table_images).insert(image_data).execute()
        
        if response.data:
            self._increment_completed_images(generation_id)
            return response.data[0]
        
        return None
    
    def _increment_completed_images(self, generation_id: str):
        """
        Increments completed image count. 
        In production, this uses a select-then-update pattern.
        """
        try:
            client = self._get_client()
            # Get current count
            res = client.table(self.table_generations) \
                .select("completed_images") \
                .eq("id", generation_id) \
                .single() \
                .execute()
            
            if res.data:
                new_count = res.data["completed_images"] + 1
                client.table(self.table_generations) \
                    .update({"completed_images": new_count}) \
                    .eq("id", generation_id) \
                    .execute()
        except Exception as e:
            logger.warning(f"Could not increment counter for {generation_id}: {e}")
    
    def complete_generation(self, generation_id: str, generation_time: float) -> bool:
        """Mark generation status as completed"""
        data = {
            "status": "completed",
            "generation_time": generation_time,
            "updated_at": datetime.now().isoformat()
        }
        
        client = self._get_client()
        response = client.table(self.table_generations) \
            .update(data) \
            .eq("id", generation_id) \
            .execute()
        
        return len(response.data) > 0
    
    def fail_generation(self, generation_id: str, error_message: str) -> bool:
        """Log failure status to DB"""
        data = {
            "status": "failed",
            "error_message": str(error_message)[:500],
            "updated_at": datetime.now().isoformat()
        }
        
        client = self._get_client()
        response = client.table(self.table_generations) \
            .update(data) \
            .eq("id", generation_id) \
            .execute()
        
        return len(response.data) > 0
    
    def get_generation(self, generation_id: str, user_id: Optional[str] = None) -> Optional[Dict]:
        """Fetch generation and joined images from Supabase"""
        client = self._get_client()
        query = client.table(self.table_generations).select("*").eq("id", generation_id)
        
        if user_id:
            query = query.eq("user_id", user_id)
        
        response = query.single().execute()
        if not response.data:
            return None
            
        # Fetch associated images
        images_response = client.table(self.table_images) \
            .select("*") \
            .eq("generation_id", generation_id) \
            .order("image_index") \
            .execute()
        
        generation_data = response.data
        generation_data["images"] = images_response.data if images_response.data else []
        generation_data["storage"] = "supabase"
        
        return generation_data

# Global instance for app-wide use
db = MarketingDB()