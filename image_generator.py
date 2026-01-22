import os
import time
import requests
import asyncio
import concurrent.futures
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from supabase_db import db

load_dotenv()

API_KEY = os.getenv("A2E_API_KEY")
BASE_URL = os.getenv("A2E_BASE_URL")

def generate_single_image_a2e(prompt: str, task_name: str = "Marketing_Gen") -> List[str]:
    """Generate single image using A2E API - SIMPLE VERSION"""
    if not API_KEY or not BASE_URL:
        print(f"❌ Error: A2E credentials not found")
        return None

    clean_base_url = BASE_URL.rstrip('/')

    # 1. SUBMIT TASK
    try:
        start_url = f"{clean_base_url}/api/v1/userNanoBanana/start"
        payload = {"name": task_name, "prompt": prompt}
        headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
        
        print(f"   → Submitting: {prompt[:30]}...")
        response = requests.post(start_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        if data.get("code") != 0:
            print(f"   ❌ API Error: {data}")
            return None
            
        task_id = data["data"]["_id"]
        print(f"   ✅ Task Submitted: {task_id[:8]}")
        
    except Exception as e:
        print(f"   ❌ Request failed: {e}")
        return None

    # 2. POLL FOR COMPLETION (NO TIMEOUT - WAIT UNTIL DONE)
    detail_url = f"{clean_base_url}/api/v1/userNanoBanana/detail/{task_id}"
    
    start_time = time.time()
    last_status = ""
    
    while True:
        time.sleep(3)  # Check every 3 seconds
        
        try:
            check_response = requests.get(detail_url, headers=headers, timeout=10)
            task_data = check_response.json().get("data", {})
            status = task_data.get("current_status")
            
            # Log status changes
            if status != last_status:
                last_status = status
                elapsed = time.time() - start_time
                print(f"   ⏳ Status: {status} ({elapsed:.0f}s)")
            
            if status == "completed":
                elapsed = time.time() - start_time
                print(f"   ✅ Task completed in {elapsed:.0f}s")
                return task_data.get("image_urls", [])
            elif status == "failed":
                print(f"   ❌ Task Failed: {task_data.get('failed_message', 'Unknown')}")
                return None
                
        except Exception:
            continue  # Keep polling on any error

def process_single_image(item: Dict, index: int, generation_id: str, user_id: str) -> Optional[Dict]:
    """Process a single image generation task"""
    angle = item.get("angle_name", f"Angle_{index}")
    raw_prompt = item.get("prompt", "")
    summary = item.get("summary", "")
    
    print(f"  🚀 Starting image {index+1}: {angle}")
    start_time = time.time()
    
    # Generate image via A2E
    urls = generate_single_image_a2e(raw_prompt, f"Marketing_Gen_{index}")
    
    if urls and len(urls) > 0:
        image_url = urls[0]
        generation_time = time.time() - start_time
        
        # Save to storage
        saved_image = db.add_generated_image(
            generation_id=generation_id,
            user_id=user_id,
            angle_name=angle,
            image_summary=summary,
            prompt=raw_prompt,
            image_url=image_url,
            image_index=index,
            generation_time=generation_time
        )
        
        if saved_image:
            elapsed = time.time() - start_time
            print(f"   ✅ Completed & Saved: {angle} in {elapsed:.0f}s")
            return saved_image
    
    elapsed = time.time() - start_time
    print(f"   ❌ Failed: {angle} after {elapsed:.0f}s")
    return None

def generate_images_parallel(prompts_data: Dict, generation_id: str, user_id: str) -> List[Dict]:
    """
    Generate ALL images in TRUE PARALLEL
    NO TIMEOUTS - Let A2E take as long as it needs
    """
    prompts_list = prompts_data.get("prompts", [])
    
    if not prompts_list:
        print("❌ No prompts to generate")
        return []
    
    print(f"\n🚀 TRUE PARALLEL IMAGE GENERATION")
    print(f"   Images: {len(prompts_list)}")
    print(f"   Mode: ALL IMAGES START SIMULTANEOUSLY")
    print(f"   Strategy: No timeouts, wait for all")
    print("-" * 50)
    
    start_time = time.time()
    
    # Use ThreadPoolExecutor - ALL images start at once
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(prompts_list)) as executor:
        # Submit ALL tasks at ONCE - TRUE PARALLEL
        future_to_item = {}
        for idx, item in enumerate(prompts_list):
            future = executor.submit(
                process_single_image, 
                item, idx, generation_id, user_id
            )
            future_to_item[future] = (item.get("angle_name", f"Angle_{idx}"), idx)
        
        # Collect results - NO TIMEOUTS
        generated_results = []
        completed_count = 0
        
        for future in concurrent.futures.as_completed(future_to_item):
            angle_name, idx = future_to_item[future]
            completed_count += 1
            
            try:
                # NO TIMEOUT - Wait as long as needed
                result = future.result()
                if result:
                    generated_results.append(result)
                    print(f"   📊 Progress: {completed_count}/{len(prompts_list)} images done")
            except Exception as e:
                print(f"   ❌ Error processing {angle_name}: {e}")
    
    total_time = time.time() - start_time
    
    print("-" * 50)
    print(f"✅ PARALLEL GENERATION COMPLETE")
    print(f"   Total time: {total_time:.0f} seconds")
    print(f"   Images generated: {len(generated_results)}/{len(prompts_list)}")
    print(f"   True parallel: Yes (all started together)")
    
    # Sort by index to maintain order
    generated_results.sort(key=lambda x: x.get("image_index", 0))
    
    return generated_results

async def generate_images_parallel_async(prompts_data: Dict, generation_id: str, user_id: str) -> List[Dict]:
    """
    Async version for parallel generation
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, 
        lambda: generate_images_parallel(prompts_data, generation_id, user_id)
    )

def generate_images_from_prompts(prompts_data: Dict, generation_id: str, user_id: str) -> List[Dict]:
    """
    Main entry point
    """
    return generate_images_parallel(prompts_data, generation_id, user_id)