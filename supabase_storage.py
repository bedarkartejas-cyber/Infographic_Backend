import os
import uuid
from datetime import datetime
from typing import Optional, Dict
import requests
from supabase_config import supabase_config

class SupabaseStorage:
    """Handle image uploads to Supabase Storage"""
    
    def __init__(self):
        self.bucket_name = "marketing-images"
        self.local_fallback_dir = "local_images"
        os.makedirs(self.local_fallback_dir, exist_ok=True)
    
    def upload_image_from_url(self, image_url: str, user_id: str, generation_id: str) -> Optional[Dict]:
        """Upload image from URL to Supabase Storage"""
        try:
            print(f"📤 Uploading image...")
            
            # Download image from A2E
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            image_data = response.content
            
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            safe_user_id = (user_id or "user").replace('-', '')[:10]
            filename = f"{generation_id}/{safe_user_id}_{timestamp}_{unique_id}.png"
            
            # Try Supabase
            if supabase_config and supabase_config.is_configured():
                client = supabase_config.get_client()
                if client:
                    try:
                        print(f"   → Uploading to Supabase: {filename}")
                        
                        # Fix: Ensure bucket URL has trailing slash
                        try:
                            # Test bucket access
                            buckets = client.storage.list_buckets()
                            bucket_exists = any(b.name == self.bucket_name for b in buckets)
                            if not bucket_exists:
                                print(f"   ⚠️  Bucket '{self.bucket_name}' doesn't exist")
                                print(f"   ⚠️  Create it in Supabase Dashboard: Storage → New Bucket")
                        except:
                            pass
                        
                        # Upload with retry
                        try:
                            result = client.storage.from_(self.bucket_name).upload(
                                file=image_data,
                                path=filename,
                                file_options={
                                    "content-type": "image/png", 
                                    "upsert": "true",
                                    "cache-control": "3600"
                                }
                            )
                            
                            # Get public URL
                            public_url = supabase_config.get_storage_url(filename)
                            print(f"   ✅ Uploaded to Supabase: {filename}")
                            
                            return {
                                "storage_path": filename,
                                "public_url": public_url,
                                "filename": filename.split("/")[-1],
                                "storage_type": "supabase"
                            }
                        except Exception as upload_error:
                            # Try alternative upload method
                            print(f"   ⚠️  Standard upload failed: {upload_error}")
                            print(f"   ⚠️  Trying fallback upload method...")
                            
                            # Save to temp file first
                            import tempfile
                            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                                tmp.write(image_data)
                                tmp_path = tmp.name
                            
                            try:
                                with open(tmp_path, 'rb') as f:
                                    result = client.storage.from_(self.bucket_name).upload(
                                        path=filename,
                                        file=f
                                    )
                                
                                os.unlink(tmp_path)
                                public_url = supabase_config.get_storage_url(filename)
                                print(f"   ✅ Uploaded via fallback: {filename}")
                                
                                return {
                                    "storage_path": filename,
                                    "public_url": public_url,
                                    "filename": filename.split("/")[-1],
                                    "storage_type": "supabase"
                                }
                            except Exception as e2:
                                os.unlink(tmp_path)
                                raise e2
                            
                    except Exception as e:
                        print(f"   ⚠️  Supabase upload failed: {e}")
            
            # Fallback to local storage
            print(f"   → Saving locally (Supabase failed)")
            
            # Create directory for generation
            gen_dir = os.path.join(self.local_fallback_dir, generation_id)
            os.makedirs(gen_dir, exist_ok=True)
            
            local_filename = f"{safe_user_id}_{timestamp}_{unique_id}.png"
            local_path = os.path.join(gen_dir, local_filename)
            
            # Save locally
            with open(local_path, 'wb') as f:
                f.write(image_data)
            
            # Create a relative URL
            relative_path = f"local_images/{generation_id}/{local_filename}"
            
            print(f"   ✅ Saved locally: {relative_path}")
            
            return {
                "storage_path": relative_path,
                "public_url": f"/{relative_path}",
                "filename": local_filename,
                "storage_type": "local"
            }
            
        except Exception as e:
            print(f"❌ Error uploading image: {e}")
            return None

# Global instance
storage = SupabaseStorage()