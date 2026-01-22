import os
import time
import asyncio
from typing import Dict, List, Optional
from cleaner import clean_text
from source_context import build_source_context
from brief_generator import generate_marketing_brief
from creative_angles import generate_creative_angles
from email_generator import generate_marketing_email
from image_prompt_generator import generate_image_prompts
from utils import parse_llm_json
from image_generator import generate_images_parallel, generate_images_parallel_async
from supabase_db import db

async def generate_marketing_assets(
    ppt_text: str, 
    website_text: str, 
    user_id: str,
    generation_id: str,
    image_count: int = 3
) -> Dict:
    """
    Generate all marketing assets with TRUE PARALLEL image generation
    ALL images start simultaneously, no timeouts
    """
    print("\n" + "="*60)
    print(f"🚀 TRUE PARALLEL GENERATION")
    print(f"📊 USER: {user_id[:8]}")
    print(f"📊 ID: {generation_id}")
    print(f"📊 IMAGES: {image_count} (ALL START TOGETHER)")
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

    # 7. TRUE PARALLEL IMAGE GENERATION - ALL START SIMULTANEOUSLY
    print(f"\n🖼️  STARTING TRUE PARALLEL IMAGE GENERATION")
    print(f"   Mode: ALL {prompt_count} IMAGES START AT ONCE")
    print(f"   No timeouts - Let A2E take as long as needed")
    
    images_start = time.time()
    generated_images = generate_images_parallel(
        image_prompts, 
        generation_id=generation_id,
        user_id=user_id
    )
    images_time = time.time() - images_start
    
    # 8. Mark generation as complete
    total_time = time.time() - total_start
    db.complete_generation(generation_id, total_time)
    
    print("\n" + "="*60)
    print(f"🎯 GENERATION COMPLETE")
    print(f"   Total time: {total_time:.0f} seconds")
    print(f"   Images generated: {len(generated_images)}/{prompt_count}")
    print(f"   Image generation time: {images_time:.0f}s")
    print(f"   True parallel: ✅ (all started together)")
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
            "parallel_mode": "true_parallel",
            "timeouts": "none"
        }
    }

async def generate_marketing_assets_stream(
    ppt_text: str, 
    website_text: str, 
    user_id: str,
    generation_id: str,
    image_count: int = 3
):
    """
    Streaming generator with TRUE PARALLEL image generation
    """
    print(f"\n🔄 Starting streaming generation")
    print(f"📊 User: {user_id[:8]}")
    print(f"📊 Images: {image_count}")
    print(f"📊 Mode: TRUE PARALLEL STREAMING")
    
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
    
    # Save text assets
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

    # 5. TRUE PARALLEL IMAGE GENERATION
    print(f"\n🚀 Launching TRUE PARALLEL: {prompt_count} images ALL AT ONCE")
    images_start = time.time()
    generated_images = await generate_images_parallel_async(
        image_prompts, 
        generation_id=generation_id,
        user_id=user_id
    )
    
    # 6. Yield each image as it completes
    for idx, img_data in enumerate(generated_images):
        img_data["sequence"] = idx + 1
        img_data["total"] = len(generated_images)
        yield {"type": "image", "data": img_data, "timestamp": time.time()}
    
    # 7. Mark generation as complete
    images_time = time.time() - images_start
    total_time = time.time() - total_start
    db.complete_generation(generation_id, total_time)
    
    print(f"✅ All {len(generated_images)} images completed in {images_time:.0f}s")
    print(f"✅ True parallel: All {prompt_count} started simultaneously")
    
    # 8. Completion message
    yield {
        "type": "complete", 
        "message": f"Generated {len(generated_images)} images",
        "generation_id": generation_id,
        "performance": {
            "total_time": round(total_time, 2),
            "image_generation_time": round(images_time, 2),
            "images_generated": len(generated_images),
            "parallel_mode": "true_parallel",
            "note": "All images started simultaneously, no timeouts"
        },
        "timestamp": time.time()
    }