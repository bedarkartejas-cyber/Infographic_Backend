import os
import time
import requests
import asyncio
import concurrent.futures
from typing import List, Dict, Any, Optional  # ADD THIS IMPORT
from dotenv import load_dotenv
from supabase_db import db

load_dotenv()

API_KEY = os.getenv("A2E_API_KEY")
BASE_URL = os.getenv("A2E_BASE_URL")

def generate_single_image_a2e(prompt: str, task_name: str = "Marketing_Gen") -> List[str]:
    """Generate single image using A2E API"""
    if not API_KEY or not BASE_URL:
        print(f"❌ Error: A2E credentials not found")
        return None

    clean_base_url = BASE_URL.rstrip('/')

    # 1. SUBMIT TASK
    try:
        start_url = f"{clean_base_url}/api/v1/userNanoBanana/start"
        payload = {"name": task_name, "prompt": prompt}
        headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
        
        print(f"   → Submitting: {prompt[:40]}...")
        response = requests.post(start_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        if data.get("code") != 0:
            print(f"   ❌ API Error: {data}")
            return None
            
        task_id = data["data"]["_id"]
        print(f"   ✅ Task Started (ID: {task_id[:8]})")
        
    except Exception as e:
        print(f"   ❌ Request failed: {e}")
        return None

    # 2. POLL FOR COMPLETION
    detail_url = f"{clean_base_url}/api/v1/userNanoBanana/detail/{task_id}"
    
    for attempt in range(30):  # Max 90 seconds (30 * 3)
        time.sleep(3)
        try:
            check_response = requests.get(detail_url, headers=headers, timeout=10)
            task_data = check_response.json().get("data", {})
            status = task_data.get("current_status")
            
            if status == "completed":
                print(f"   ✅ Task {task_id[:8]} completed")
                return task_data.get("image_urls", [])
            elif status == "failed":
                print(f"   ❌ Task Failed: {task_data.get('failed_message')}")
                return None
        except Exception as e:
            if attempt % 5 == 0:  # Log every 5 attempts
                print(f"   ⏳ Polling attempt {attempt+1} for {task_id[:8]}")
    
    print(f"   ❌ Timed out waiting for task {task_id[:8]}")
    return None

def process_single_image(item: Dict, index: int, generation_id: str, user_id: str) -> Optional[Dict]:
    """Process a single image generation task and save to Supabase"""
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
        
        # Save to Supabase (database + storage)
        saved_image = db.add_generated_image(
            generation_id=generation_id,
            user_id=user_id,
            angle_name=angle,
            image_summary=summary,
            prompt=raw_prompt,
            image_url=image_url,  # A2E temporary URL
            image_index=index,
            generation_time=generation_time
        )
        
        if saved_image:
            elapsed = time.time() - start_time
            print(f"   ✅ Completed & Saved: {angle} in {elapsed:.1f}s")
            return saved_image
    
    elapsed = time.time() - start_time
    print(f"   ❌ Failed: {angle} after {elapsed:.1f}s")
    return None

def generate_images_parallel(prompts_data: Dict, generation_id: str, user_id: str, max_workers: int = 3) -> List[Dict]:
    """
    Generate ALL images in parallel and save to Supabase
    """
    prompts_list = prompts_data.get("prompts", [])
    
    if not prompts_list:
        print("❌ No prompts to generate")
        return []
    
    print(f"\n🚀 STARTING PARALLEL IMAGE GENERATION")
    print(f"   Images: {len(prompts_list)}")
    print(f"   Workers: {max_workers}")
    print(f"   Generation ID: {generation_id}")
    print(f"   Storage: Supabase")
    print("-" * 50)
    
    start_time = time.time()
    
    # Process ALL images in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit ALL tasks at once
        future_to_item = {}
        for idx, item in enumerate(prompts_list):
            future = executor.submit(
                process_single_image, 
                item, idx, generation_id, user_id
            )
            future_to_item[future] = (item.get("angle_name", f"Angle_{idx}"), idx)
        
        # Collect results as they complete
        generated_results = []
        completed_count = 0
        
        for future in concurrent.futures.as_completed(future_to_item):
            angle_name, idx = future_to_item[future]
            completed_count += 1
            
            try:
                result = future.result(timeout=120)
                if result:
                    generated_results.append(result)
                    print(f"   📊 Progress: {completed_count}/{len(prompts_list)} images done")
            except Exception as e:
                print(f"   ❌ Error processing {angle_name}: {e}")
    
    total_time = time.time() - start_time
    
    print("-" * 50)
    print(f"✅ PARALLEL GENERATION COMPLETE")
    print(f"   Total time: {total_time:.1f} seconds")
    print(f"   Images generated: {len(generated_results)}/{len(prompts_list)}")
    print(f"   Storage: Supabase ✅")
    
    # Sort by index to maintain order
    generated_results.sort(key=lambda x: x.get("image_index", 0))
    
    return generated_results

async def generate_images_parallel_async(prompts_data: Dict, generation_id: str, user_id: str, max_concurrent: int = 3) -> List[Dict]:
    """
    Async version for parallel generation
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, 
        lambda: generate_images_parallel(prompts_data, generation_id, user_id, max_concurrent)
    )

def generate_images_from_prompts(prompts_data: Dict, generation_id: str, user_id: str) -> List[Dict]:
    """
    Main entry point - uses parallel generation with Supabase
    """
    return generate_images_parallel(prompts_data, generation_id, user_id, max_workers=3)