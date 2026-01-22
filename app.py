import os
import re
import json
import time
import uuid
import logging
from io import BytesIO
from typing import Optional
import asyncio
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.gzip import GZipMiddleware
from pptx import Presentation
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

from supabase_db import db
from main import generate_marketing_assets, generate_marketing_assets_stream

app = FastAPI(
    title="Marketing Generator API",
    description="Generate marketing assets with TRUE PARALLEL image generation",
    version="3.0.0",
    docs_url="/docs" if os.getenv("ENVIRONMENT") == "development" else None,
    redoc_url="/redoc" if os.getenv("ENVIRONMENT") == "development" else None,
)

# Production CORS settings
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    max_age=3600,
)

# Add GZip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Serve static files in production
os.makedirs("local_images", exist_ok=True)
app.mount("/local_images", StaticFiles(directory="local_images"), name="local_images")

# --- CONFIGURATION ---
TIMEOUT = (10, 60)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}

# Rate limiting (simple in-memory)
request_counts = {}
RATE_LIMIT = int(os.getenv("RATE_LIMIT", "100"))  # requests per minute

@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    current_time = time.time()
    
    # Clean old entries
    request_counts[client_ip] = [
        t for t in request_counts.get(client_ip, [])
        if current_time - t < 60
    ]
    
    # Check rate limit
    if len(request_counts[client_ip]) >= RATE_LIMIT:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Try again in a minute."}
        )
    
    request_counts[client_ip].append(current_time)
    response = await call_next(request)
    return response

def extract_text_from_pptx(file_content):
    """Extract text from PPTX file"""
    try:
        prs = Presentation(BytesIO(file_content))
        full_text_output = []

        for i, slide in enumerate(prs.slides, start=1):
            slide_content = []
            slide_content.append(f"--- SLIDE {i} ---")

            try:
                if slide.shapes.title and slide.shapes.title.text.strip():
                    title_text = slide.shapes.title.text.strip()
                    slide_content.append(f"[Title]: {title_text}")
            except:
                pass

            text_shapes = []
            for shape in slide.shapes:
                if not shape.has_text_frame: 
                    continue
                if shape == slide.shapes.title: 
                    continue
                text_shapes.append(shape)
            
            text_shapes.sort(key=lambda s: (s.top, s.left))

            for shape in text_shapes:
                for paragraph in shape.text_frame.paragraphs:
                    text = paragraph.text.strip()
                    if text:
                        slide_content.append(text)

            if slide.has_notes_slide:
                notes_frame = slide.notes_slide.notes_text_frame
                if notes_frame:
                    notes_text = notes_frame.text.strip()
                    if notes_text:
                        slide_content.append(f"\n[Speaker Notes]:\n{notes_text}")

            full_text_output.append("\n".join(slide_content))

        return "\n\n".join(full_text_output)

    except Exception as e:
        logger.error(f"Error reading PPTX: {e}")
        return ""

def extract_text_from_url_sync(url: str):
    """Sync web scraping"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        html_content = response.text
        
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return ""
        
        soup = BeautifulSoup(html_content, "html.parser")
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
            tag.decompose()

        text = soup.get_text(separator="\n")
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()
        
    except Exception as e:
        logger.error(f"Error scraping URL: {e}")
        return ""

@app.get("/")
async def index():
    return JSONResponse(
        content={
            "message": "🚀 Marketing Generator API v3.0",
            "version": "3.0.0",
            "status": "running",
            "environment": os.getenv("ENVIRONMENT", "production"),
            "features": [
                "TRUE PARALLEL image generation",
                "All images start simultaneously",
                "No timeouts - Let A2E work at its pace",
                "PPTX content extraction",
                "Website content scraping", 
                "Marketing brief generation",
                "Creative angles generation",
                "Email copy generation",
                "Image prompt generation",
                "Supabase storage integration"
            ],
            "endpoints": {
                "POST /api/generate": "Generate all assets at once (TRUE PARALLEL)",
                "POST /api/generate-stream": "Stream generation progress (TRUE PARALLEL)",
                "GET /api/generations": "Get user's generations",
                "GET /api/generations/{id}": "Get specific generation"
            },
            "rate_limit": f"{RATE_LIMIT} requests per minute"
        }
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check database connection
        db_status = "healthy" if db._get_client() else "unhealthy"
        
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "datetime": datetime.now().isoformat(),
            "service": "marketing-generator",
            "version": "3.0.0",
            "mode": "TRUE_PARALLEL",
            "database": db_status,
            "environment": os.getenv("ENVIRONMENT", "production")
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )

@app.post("/api/generate")
async def generate_api(
    website_url: Optional[str] = Form(None),
    ppt_file: Optional[UploadFile] = File(None),
    image_count: int = Form(3),
    x_user_id: Optional[str] = Header(None)
):
    """
    🚀 GENERATE MODE: TRUE PARALLEL image generation
    """
    start_time = time.time()
    user_id = x_user_id or "demo-user"
    
    logger.info(f"Generation request - User: {user_id}, Images: {image_count}")
    
    # Validate inputs
    if image_count < 1 or image_count > 5:
        raise HTTPException(
            status_code=400,
            detail="image_count must be between 1 and 5"
        )
    
    if not website_url and not ppt_file:
        raise HTTPException(
            status_code=400,
            detail="Either website_url or ppt_file must be provided"
        )
    
    if ppt_file and ppt_file.filename:
        if not ppt_file.filename.lower().endswith(('.pptx', '.ppt')):
            raise HTTPException(
                status_code=400,
                detail="Only PPTX/PPT files are supported"
            )
    
    website_text = ""
    ppt_text = ""
    
    try:
        # Extract website content
        if website_url:
            from urllib.parse import urlparse
            parsed = urlparse(website_url)
            if not all([parsed.scheme, parsed.netloc]):
                raise HTTPException(status_code=400, detail="Invalid website URL")
                    
            website_text = await asyncio.to_thread(extract_text_from_url_sync, website_url)
            logger.info(f"Extracted {len(website_text)} chars from website")
        
        # Extract PPT content
        if ppt_file and ppt_file.filename:
            logger.info(f"Processing PPT file: {ppt_file.filename}")
            file_content = await ppt_file.read()
            
            # File size check (10MB max)
            if len(file_content) > 10 * 1024 * 1024:
                raise HTTPException(
                    status_code=400,
                    detail="PPT file size exceeds 10MB limit"
                )
                
            ppt_text = extract_text_from_pptx(file_content)
            logger.info(f"Extracted {len(ppt_text)} chars from PPT")
        
        if not ppt_text and not website_text:
            raise HTTPException(
                status_code=400, 
                detail="No content found in the provided sources"
            )
        
        # Create generation session
        generation_id = db.create_generation_session(
            user_id=user_id,
            website_url=website_url,
            ppt_text=ppt_text,
            website_text=website_text
        )
        
        logger.info(f"Starting TRUE PARALLEL generation: {generation_id}")
        
        try:
            # Run TRUE PARALLEL generation
            results = await generate_marketing_assets(
                ppt_text=ppt_text,
                website_text=website_text,
                user_id=user_id,
                generation_id=generation_id,
                image_count=image_count
            )
            
            total_time = time.time() - start_time
            results["generation_time"] = round(total_time, 2)
            
            logger.info(f"Generation completed in {total_time:.0f}s: {generation_id}")
            
            return {
                "success": True,
                "generation_id": generation_id,
                "user_id": user_id,
                "mode": "true_parallel",
                "data": results,
                "performance": {
                    "total_time": round(total_time, 2),
                    "images_generated": len(results.get('generated_images', [])),
                    "parallel_mode": "true_parallel"
                }
            }
            
        except Exception as gen_error:
            logger.error(f"Generation failed: {gen_error}")
            db.fail_generation(generation_id, str(gen_error))
            raise HTTPException(
                status_code=500, 
                detail=f"Generation failed: {str(gen_error)}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/generate-stream")
async def generate_stream_api(
    website_url: Optional[str] = Form(None),
    ppt_file: Optional[UploadFile] = File(None),
    image_count: int = Form(3),
    x_user_id: Optional[str] = Header(None)
):
    """
    📡 STREAMING MODE: Real-time TRUE PARALLEL progress
    """
    user_id = x_user_id or "demo-user"
    
    logger.info(f"Stream generation request - User: {user_id}")
    
    # Validate inputs
    if image_count < 1 or image_count > 5:
        raise HTTPException(
            status_code=400,
            detail="image_count must be between 1 and 5"
        )
    
    try:
        website_text = ""
        ppt_text = ""
        
        # Extract content
        if website_url:
            website_text = await asyncio.to_thread(extract_text_from_url_sync, website_url)
        
        if ppt_file and ppt_file.filename and ppt_file.filename.endswith(('.pptx', '.ppt')):
            file_content = await ppt_file.read()
            
            # File size check
            if len(file_content) > 10 * 1024 * 1024:
                raise HTTPException(
                    status_code=400,
                    detail="PPT file size exceeds 10MB limit"
                )
                
            ppt_text = extract_text_from_pptx(file_content)
        
        if not ppt_text and not website_text:
            raise HTTPException(status_code=400, detail="No content found.")
        
        # Create generation session
        generation_id = db.create_generation_session(
            user_id=user_id,
            website_url=website_url,
            ppt_text=ppt_text,
            website_text=website_text
        )
        
        async def generate():
            try:
                # Send start event
                yield json.dumps({
                    "type": "start",
                    "timestamp": time.time(),
                    "generation_id": generation_id,
                    "user_id": user_id,
                    "image_count": image_count,
                    "mode": "true_parallel"
                }) + "\n"
                
                # Stream TRUE PARALLEL generation
                async for chunk in generate_marketing_assets_stream(
                    ppt_text=ppt_text,
                    website_text=website_text,
                    user_id=user_id,
                    generation_id=generation_id,
                    image_count=image_count
                ):
                    yield json.dumps(chunk) + "\n"
                
                # Send completion
                yield json.dumps({
                    "type": "complete",
                    "timestamp": time.time(),
                    "generation_id": generation_id,
                    "mode": "true_parallel"
                }) + "\n"
                
            except Exception as e:
                logger.error(f"Stream generation error: {e}")
                db.fail_generation(generation_id, str(e))
                
                yield json.dumps({
                    "type": "error",
                    "timestamp": time.time(),
                    "message": "Internal server error",
                    "generation_id": generation_id
                }) + "\n"
        
        return StreamingResponse(
            generate(),
            media_type='application/x-ndjson',
            headers={
                "X-Accel-Buffering": "no",
                "Cache-Control": "no-cache",
                "X-Generation-ID": generation_id,
                "X-User-ID": user_id
            }
        )
        
    except Exception as e:
        logger.error(f"Stream endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/generations")
async def get_user_generations(
    x_user_id: Optional[str] = Header(None),
    limit: int = 20
):
    """Get all generations for current user"""
    try:
        user_id = x_user_id or "demo-user"
        
        # For memory storage
        user_generations = []
        for gen_id, gen_data in db._memory_generations.items():
            if gen_data.get("user_id") == user_id:
                images = db._memory_images.get(gen_id, [])
                gen_data["images"] = images
                gen_data["storage"] = "memory"
                user_generations.append(gen_data)
        
        # Sort by created_at (newest first)
        user_generations.sort(
            key=lambda x: x.get("created_at", ""), 
            reverse=True
        )
        
        # Apply limit
        user_generations = user_generations[:min(limit, 100)]
        
        return {
            "success": True,
            "user_id": user_id,
            "count": len(user_generations),
            "generations": user_generations
        }
        
    except Exception as e:
        logger.error(f"Error getting generations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/generations/{generation_id}")
async def get_generation(
    generation_id: str,
    x_user_id: Optional[str] = Header(None)
):
    """Get specific generation by ID"""
    try:
        user_id = x_user_id or "demo-user"
        
        generation = db.get_generation(generation_id, user_id)
        
        if not generation:
            raise HTTPException(
                status_code=404, 
                detail="Generation not found or access denied"
            )
        
        return {
            "success": True,
            "generation": generation,
            "storage": generation.get("storage", "unknown")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting generation {generation_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": time.time()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "timestamp": time.time()
        }
    )

# Production server entry point
def run_server():
    import uvicorn
    
    port = int(os.getenv("PORT", "5000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"Starting server on {host}:{port}")
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'production')}")
    
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        workers=int(os.getenv("WORKERS", "2")),
        log_level=os.getenv("LOG_LEVEL", "info"),
        timeout_keep_alive=600,
        access_log=False  # Disable access logs in production for better performance
    )

if __name__ == "__main__":
    run_server()