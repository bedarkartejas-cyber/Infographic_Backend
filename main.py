import os
import time
import asyncio
from typing import Dict, List, Optional  # ADD THIS IMPORT
from cleaner import clean_text
from source_context import build_source_context
from brief_generator import generate_marketing_brief
from creative_angles import generate_creative_angles
from email_generator import generate_marketing_email
from image_prompt_generator import generate_image_prompts
from utils import parse_llm_json
from image_generator import generate_images_parallel, generate_images_parallel_async
from supabase_db import db

async def generate_marketing_assets_supabase(
    ppt_text: str, 
    website_text: str, 
    user_id: str,
    generation_id: str,
    image_count: int = 3
) -> Dict:
    """
    Generate all marketing assets and save to Supabase
    """
    print("\n" + "="*60)
    print(f"🚀 MARKETING GENERATION FOR USER: {user_id[:8]}")
    print(f"📊 GENERATION ID: {generation_id}")
    print("="*60)
    
    total_start = time.time()
    
    # 1. Clean Inputs
    clean_start = time.time()
    ppt_clean = clean_text(ppt_text)
    web_clean = clean_text(website_text)
    source_context = build_source_context(ppt_clean, web_clean)
    print(f"✅ Content cleaned in {time.time()-clean_start:.1f}s")

    # 2. Generate Brief
    brief_start = time.time()
    brief_raw = generate_marketing_brief(source_context)
    brief = parse_llm_json(brief_raw)
    print(f"✅ Brief generated in {time.time()-brief_start:.1f}s")

    # 3. Generate Angles
    angles_start = time.time()
    angles_raw = generate_creative_angles(brief, image_count)
    angles = parse_llm_json(angles_raw)
    print(f"✅ {len(angles.get('angles', []))} angles generated in {time.time()-angles_start:.1f}s")

    # 4. Generate Email
    email_start = time.time()
    email_raw = generate_marketing_email(brief)
    email = parse_llm_json(email_raw)
    print(f"✅ Email generated in {time.time()-email_start:.1f}s")

    # 5. Generate Image Prompts
    prompts_start = time.time()
    image_prompts_raw = generate_image_prompts(brief, angles)
    image_prompts = parse_llm_json(image_prompts_raw)
    prompt_count = len(image_prompts.get('prompts', []))
    print(f"✅ {prompt_count} image prompts generated in {time.time()-prompts_start:.1f}s")

    # 6. Save text assets to Supabase
    db.update_generation_assets(
        generation_id=generation_id,
        marketing_brief=brief,
        email_content=email,
        creative_angles=angles,
        image_prompts=image_prompts,
        total_images=prompt_count
    )

    # 7. Generate ALL Images in PARALLEL and save to Supabase
    print(f"\n🖼️  STARTING PARALLEL IMAGE GENERATION TO SUPABASE")
    images_start = time.time()
    generated_images = generate_images_parallel(
        image_prompts, 
        generation_id=generation_id,
        user_id=user_id,
        max_workers=image_count
    )
    images_time = time.time() - images_start
    print(f"✅ {len(generated_images)} images generated & saved to Supabase in {images_time:.1f}s")
    
    # 8. Mark generation as complete
    total_time = time.time() - total_start
    db.complete_generation(generation_id, total_time)
    
    print("\n" + "="*60)
    print(f"🎯 GENERATION COMPLETE")
    print(f"   Total time: {total_time:.1f} seconds")
    print(f"   Images: {len(generated_images)}")
    print(f"   Storage: Supabase ✅")
    print(f"   Generation ID: {generation_id}")
    print("="*60)
    
    return {
        "generation_id": generation_id,
        "marketing_brief": brief,
        "email": email,
        "ad_image_prompts": image_prompts,
        "generated_images": generated_images,
        "performance": {
            "total_time": round(total_time, 2),
            "image_generation_time": round(images_time, 2),
            "images_generated": len(generated_images),
            "images_requested": image_count,
            "storage": "supabase"
        }
    }

async def generate_marketing_assets_stream_supabase(
    ppt_text: str, 
    website_text: str, 
    user_id: str,
    generation_id: str,
    image_count: int = 3
):
    """
    Streaming generator with Supabase storage
    """
    print(f"\n🔄 Starting streaming generation for user: {user_id[:8]}")
    print(f"📊 Generation ID: {generation_id}")
    
    total_start = time.time()
    
    # 1. Clean Inputs
    ppt_clean = clean_text(ppt_text)
    web_clean = clean_text(website_text)
    source_context = build_source_context(ppt_clean, web_clean)

    # 2. Generate & Yield Brief IMMEDIATELY
    brief_start = time.time()
    brief_raw = await asyncio.to_thread(generate_marketing_brief, source_context)
    brief = parse_llm_json(brief_raw)
    print(f"✅ Brief ready in {time.time()-brief_start:.1f}s")
    yield {"type": "brief", "data": brief, "timestamp": time.time()}

    # 3. Generate Angles & Email IN PARALLEL
    parallel_start = time.time()
    angles_task = asyncio.to_thread(generate_creative_angles, brief, image_count)
    email_task = asyncio.to_thread(generate_marketing_email, brief)
    
    angles_raw, email_raw = await asyncio.gather(angles_task, email_task)
    
    angles = parse_llm_json(angles_raw)
    email = parse_llm_json(email_raw)
    print(f"✅ Angles & Email ready in {time.time()-parallel_start:.1f}s")
    
    yield {"type": "email", "data": email, "timestamp": time.time()}

    # 4. Generate Image Prompts
    prompts_start = time.time()
    image_prompts_raw = await asyncio.to_thread(generate_image_prompts, brief, angles)
    image_prompts = parse_llm_json(image_prompts_raw)
    prompt_count = len(image_prompts.get("prompts", []))
    print(f"✅ Image prompts ready in {time.time()-prompts_start:.1f}s")
    
    # 5. Save text assets to Supabase
    db.update_generation_assets(
        generation_id=generation_id,
        marketing_brief=brief,
        email_content=email,
        creative_angles=angles,
        image_prompts=image_prompts,
        total_images=prompt_count
    )
    
    # Tell frontend we're starting image generation
    yield {"type": "image_start", "count": prompt_count, "timestamp": time.time()}

    # 6. Generate ALL Images in TRUE PARALLEL to Supabase
    print(f"\n🚀 Launching {prompt_count} images in parallel to Supabase...")
    images_start = time.time()
    generated_images = await generate_images_parallel_async(
        image_prompts, 
        generation_id=generation_id,
        user_id=user_id,
        max_concurrent=image_count
    )
    
    # 7. Yield each image as it completes
    for idx, img_data in enumerate(generated_images):
        img_data["sequence"] = idx + 1
        img_data["total"] = len(generated_images)
        yield {"type": "image", "data": img_data, "timestamp": time.time()}
    
    # 8. Mark generation as complete
    images_time = time.time() - images_start
    total_time = time.time() - total_start
    db.complete_generation(generation_id, total_time)
    
    print(f"✅ All {len(generated_images)} images completed & saved to Supabase in {images_time:.1f}s")
    
    # 9. Signal completion
    yield {
        "type": "complete", 
        "message": f"Generated {len(generated_images)} images",
        "generation_id": generation_id,
        "performance": {
            "total_time": round(total_time, 2),
            "image_generation_time": round(images_time, 2),
            "images_per_minute": round(len(generated_images) / (total_time/60), 1),
            "storage": "supabase"
        },
        "timestamp": time.time()
    }

# Legacy functions for backward compatibility
def generate_marketing_assets(ppt_text: str, website_text: str, image_count: int = 3):
    """Legacy function - throws error to force Supabase usage"""
    raise Exception("Use generate_marketing_assets_supabase with user_id and generation_id")

def generate_marketing_assets_stream(ppt_text: str, website_text: str, image_count: int = 3):
    """Legacy function - throws error to force Supabase usage"""
    raise Exception("Use generate_marketing_assets_stream_supabase with user_id and generation_id")