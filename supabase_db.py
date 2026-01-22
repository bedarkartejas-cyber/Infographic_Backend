import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from supabase_config import supabase_config
from supabase_storage import storage

class MarketingDB:
    """Database operations"""
    
    def __init__(self):
        self.storage = storage
        self.table_generations = "marketing_generations"
        self.table_images = "marketing_images"
        
        # In-memory fallback
        self._memory_generations = {}
        self._memory_images = {}
    
    def _get_client(self):
        """Get Supabase client"""
        if supabase_config and supabase_config.is_configured():
            return supabase_config.get_client()
        return None
    
    def _validate_uuid(self, user_id: str) -> str:
        """Convert string to valid UUID if needed"""
        if not user_id:
            return str(uuid.uuid4())
        
        # If it's already a UUID, return it
        try:
            uuid.UUID(user_id)
            return user_id
        except ValueError:
            # Convert string to UUID hash (for foreign key compatibility)
            return str(uuid.uuid5(uuid.NAMESPACE_DNS, user_id))
    
    def create_generation_session(
        self, 
        user_id: str,
        ppt_file_url: Optional[str] = None,
        website_url: Optional[str] = None,
        ppt_text: Optional[str] = None,
        website_text: Optional[str] = None
    ) -> str:
        """Create a new marketing generation session"""
        try:
            generation_id = str(uuid.uuid4())
            
            # Use original user_id as TEXT, not UUID
            data = {
                "id": generation_id,
                "user_id": user_id,  # Keep as TEXT, not UUID
                "ppt_file_url": ppt_file_url,
                "website_url": website_url,
                "ppt_text": ppt_text[:5000] if ppt_text else None,
                "website_text": website_text[:5000] if website_text else None,
                "status": "processing",
                "total_images": 0,
                "completed_images": 0,
                "created_at": datetime.now().isoformat()
            }
            
            print(f"📝 Creating generation session: {generation_id}")
            print(f"   User: {user_id}")
            
            client = self._get_client()
            if client:
                try:
                    # Clean data for Supabase (remove None values)
                    supabase_data = {k: v for k, v in data.items() if v is not None}
                    
                    response = client.table(self.table_generations).insert(supabase_data).execute()
                    if response.data:
                        print(f"✅ Generation session created in Supabase: {generation_id}")
                        return generation_id
                    else:
                        print("⚠️  Supabase insert returned no data")
                except Exception as e:
                    print(f"⚠️  Supabase insert failed: {e}")
            
            # Fallback to memory
            raise HTTPException(status_code=503, detail="Database connection failed. Data cannot be saved.")
            
        except Exception as e:
            print(f"❌ Failed to create generation session: {e}")
            # Still return an ID
            generation_id = str(uuid.uuid4())
            self._memory_generations[generation_id] = {
                "id": generation_id,
                "user_id": user_id,
                "status": "processing",
                "created_at": datetime.now().isoformat()
            }
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
        """Update generation with text assets"""
        try:
            data = {
                "marketing_brief": marketing_brief,
                "email_content": email_content,
                "creative_angles": creative_angles,
                "image_prompts": image_prompts,
                "total_images": total_images,
                "updated_at": datetime.now().isoformat()
            }
            
            client = self._get_client()
            if client:
                try:
                    response = client.table(self.table_generations) \
                        .update(data) \
                        .eq("id", generation_id) \
                        .execute()
                    
                    if len(response.data) > 0:
                        print(f"✅ Updated assets in Supabase: {generation_id}")
                        return True
                except Exception as e:
                    print(f"⚠️  Supabase update failed: {e}")
            
            # Fallback to memory
            if generation_id in self._memory_generations:
                self._memory_generations[generation_id].update(data)
                print(f"✅ Updated assets in memory: {generation_id}")
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ Failed to update generation assets: {e}")
            return False
    
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
        """Add a generated image"""
        try:
            print(f"🖼️  Processing image {image_index+1}: {angle_name}")
            
            # Upload image
            storage_info = self.storage.upload_image_from_url(image_url, user_id, generation_id)
            
            if not storage_info:
                print(f"❌ Failed to upload image: {angle_name}")
                return None
            
            # Create image record
            image_id = str(uuid.uuid4())
            
            image_data = {
                "id": image_id,
                "generation_id": generation_id,
                "user_id": user_id,  # Keep as TEXT
                "angle_name": angle_name[:255],
                "image_summary": image_summary[:1000] if image_summary else "",
                "prompt": prompt[:2000] if prompt else "",
                "image_url": storage_info["public_url"],
                "supabase_storage_path": storage_info["storage_path"],
                "storage_type": storage_info.get("storage_type", "unknown"),
                "image_index": image_index,
                "generation_time": generation_time,
                "created_at": datetime.now().isoformat()
            }
            
            # Try Supabase
            client = self._get_client()
            if client:
                try:
                    response = client.table(self.table_images).insert(image_data).execute()
                    if response.data:
                        print(f"✅ Image saved to Supabase: {angle_name}")
                        self._increment_completed_images(generation_id)
                        return response.data[0]
                except Exception as e:
                    print(f"⚠️  Supabase image insert failed: {e}")
            
            # Fallback to memory
            if generation_id not in self._memory_images:
                self._memory_images[generation_id] = []
            
            self._memory_images[generation_id].append(image_data)
            
            # Update memory generation
            if generation_id in self._memory_generations:
                current = self._memory_generations[generation_id].get("completed_images", 0)
                self._memory_generations[generation_id]["completed_images"] = current + 1
            
            print(f"✅ Image saved to memory: {angle_name}")
            return image_data
            
        except Exception as e:
            print(f"❌ Failed to add generated image: {e}")
            return None
    
    def _increment_completed_images(self, generation_id: str):
        """Increment completed images count"""
        try:
            client = self._get_client()
            if not client:
                return
            
            # Update count directly
            client.table(self.table_generations) \
                .update({"completed_images": client.table(self.table_generations)
                    .select("completed_images")
                    .eq("id", generation_id)
                    .single()
                    .execute()
                    .data["completed_images"] + 1}) \
                .eq("id", generation_id) \
                .execute()
                    
        except Exception as e:
            print(f"Warning: Could not increment completed images: {e}")
    
    def complete_generation(
        self,
        generation_id: str,
        generation_time: float
    ) -> bool:
        """Mark generation as complete - ADD THIS METHOD"""
        try:
            data = {
                "status": "completed",
                "generation_time": generation_time,
                "updated_at": datetime.now().isoformat()
            }
            
            client = self._get_client()
            if client:
                try:
                    response = client.table(self.table_generations) \
                        .update(data) \
                        .eq("id", generation_id) \
                        .execute()
                    
                    if len(response.data) > 0:
                        print(f"✅ Generation completed in Supabase: {generation_id}")
                        return True
                except Exception as e:
                    print(f"⚠️  Supabase complete generation failed: {e}")
            
            # Fallback to memory
            if generation_id in self._memory_generations:
                self._memory_generations[generation_id].update(data)
                print(f"✅ Generation completed in memory: {generation_id}")
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ Failed to complete generation: {e}")
            return False
    
    def fail_generation(self, generation_id: str, error_message: str) -> bool:
        """Mark generation as failed"""
        try:
            data = {
                "status": "failed",
                "error_message": error_message[:500],
                "updated_at": datetime.now().isoformat()
            }
            
            client = self._get_client()
            if client:
                try:
                    response = client.table(self.table_generations) \
                        .update(data) \
                        .eq("id", generation_id) \
                        .execute()
                    
                    return len(response.data) > 0
                except Exception as e:
                    print(f"Supabase fail generation error: {e}")
            
            # Fallback to memory
            if generation_id in self._memory_generations:
                self._memory_generations[generation_id].update(data)
                return True
            
            return False
            
        except Exception as e:
            print(f"Failed to mark generation as failed: {e}")
            return False
    
    def get_generation(self, generation_id: str, user_id: Optional[str] = None) -> Optional[Dict]:
        """Get a generation by ID"""
        try:
            client = self._get_client()
            
            if client:
                # Try Supabase first
                query = client.table(self.table_generations).select("*").eq("id", generation_id)
                
                if user_id:
                    query = query.eq("user_id", user_id)
                
                try:
                    response = query.single().execute()
                    if response.data:
                        # Get associated images
                        images_response = client.table(self.table_images) \
                            .select("*") \
                            .eq("generation_id", generation_id) \
                            .order("image_index") \
                            .execute()
                        
                        generation_data = response.data
                        generation_data["images"] = images_response.data if images_response.data else []
                        generation_data["storage"] = "supabase"
                        
                        return generation_data
                except Exception as e:
                    print(f"Supabase query failed: {e}")
            
            # Check memory storage
            if generation_id in self._memory_generations:
                generation_data = self._memory_generations[generation_id]
                
                # Check user permission
                if user_id and generation_data.get("user_id") != user_id:
                    return None
                
                # Get images from memory
                images = self._memory_images.get(generation_id, [])
                generation_data["images"] = images
                generation_data["storage"] = "memory"
                
                return generation_data
            
            return None
            
        except Exception as e:
            print(f"Error getting generation: {e}")
            return None

# Global instance
db = MarketingDB()