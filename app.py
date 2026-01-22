import os
import json
import time
import logging
from typing import Optional
import asyncio
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header, Depends, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

# Configure structured logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Suppress noisy logs
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

# Import production config
try:
    from config import config
    CONFIG_LOADED = True
    # Validate config on import
    if hasattr(config, 'validate'):
        config.validate()
    logger.info("✅ Production configuration loaded")
except ImportError as e:
    logger.error(f"❌ Failed to load config module: {e}")
    CONFIG_LOADED = False
    raise
except Exception as e:
    logger.error(f"❌ Configuration validation failed: {e}")
    CONFIG_LOADED = False
    raise

# Import application modules
try:
    from supabase_db import db
    from main import generate_marketing_assets, generate_marketing_assets_stream
    MODULES_LOADED = True
    logger.info("✅ Application modules loaded")
except ImportError as e:
    logger.error(f"❌ Failed to import application modules: {e}")
    MODULES_LOADED = False
    raise

# Import utilities
try:
    from app_utils import extract_text_from_pptx, extract_text_from_url_sync
    UTILS_LOADED = True
    logger.info("✅ Utility modules loaded")
except ImportError as e:
    logger.error(f"❌ Failed to import utility modules: {e}")
    UTILS_LOADED = False
    raise

# Import authentication middleware
try:
    from auth_middleware import get_user_id_from_token, get_user_id_from_header
    AUTH_LOADED = True
    logger.info("✅ Authentication middleware loaded")
except ImportError as e:
    logger.error(f"⚠️ Failed to load auth middleware: {e}")
    AUTH_LOADED = False

# Determine environment
ENVIRONMENT = config.ENVIRONMENT if CONFIG_LOADED else os.getenv("ENVIRONMENT", "production")

# Create FastAPI app with production settings
app = FastAPI(
    title="Marketing Generator API",
    description="Generate marketing assets with TRUE PARALLEL image generation",
    version="3.0.0",
    docs_url="/docs" if ENVIRONMENT == "development" else None,
    redoc_url="/redoc" if ENVIRONMENT == "development" else None,
    openapi_url="/openapi.json" if ENVIRONMENT == "development" else None,
)

# CORS configuration - restrict in production
if ENVIRONMENT == "production":
    allowed_origins = config.ALLOWED_ORIGINS.split(",") if CONFIG_LOADED else []
    if not allowed_origins:
        logger.warning("⚠️ ALLOWED_ORIGINS not set in production, defaulting to empty")
        allowed_origins = []
else:
    allowed_origins = ["*"]  # Allow all in development

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-User-ID"],
    max_age=3600,
)

# Add GZip compression for better performance
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Dependency for authentication
async def get_current_user_id(request: Request) -> str:
    """
    Production authentication - prefers JWT token, falls back to header for development
    """
    # Try JWT token first (production)
    if AUTH_LOADED:
        try:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                user_id = await get_user_id_from_token(request)
                logger.debug(f"Authenticated user via JWT: {user_id[:8]}...")
                return user_id
        except HTTPException as jwt_error:
            # Only log if it was a real auth error, not just missing header
            if jwt_error.status_code != 401:
                logger.warning(f"JWT auth failed: {jwt_error.detail}")
        except Exception as e:
            logger.warning(f"JWT auth error: {e}")
    
    # Fallback to X-User-ID header (for development/testing)
    user_id = request.headers.get("X-User-ID")
    if user_id:
        logger.debug(f"Using X-User-ID header: {user_id[:8]}...")
        return user_id
    
    # No authentication provided
    if ENVIRONMENT == "production":
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide Authorization Bearer token or X-User-ID header"
        )
    
    # Default user for development
    logger.warning("⚠️ No authentication provided, using 'demo-user' for development")
    return "demo-user"

@app.get("/")
async def index():
    """Root endpoint with API information"""
    return JSONResponse(
        content={
            "message": "🚀 Marketing Generator API v3.0",
            "version": "3.0.0",
            "status": "running",
            "environment": ENVIRONMENT,
            "production": ENVIRONMENT == "production",
            "authentication": "JWT + X-User-ID header" if AUTH_LOADED else "X-User-ID header only",
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
                "GET /api/generations/{id}": "Get specific generation",
                "GET /health": "Health check"
            },
            "limits": {
                "max_images": 5,
                "max_file_size": f"{config.FILE_SIZE_LIMIT // (1024*1024)}MB" if CONFIG_LOADED else "10MB",
                "timeout": f"{config.REQUEST_TIMEOUT // 60} minutes" if CONFIG_LOADED else "5 minutes"
            }
        }
    )

@app.get("/health")
async def health_check():
    """Comprehensive health check endpoint for production monitoring"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "marketing-generator",
        "version": "3.0.0",
        "environment": ENVIRONMENT,
        "production": ENVIRONMENT == "production",
        "components": {}
    }
    
    # Check database connection
    try:
        if MODULES_LOADED:
            client = db._get_client()
            if client:
                # Try a simple query to verify connectivity
                try:
                    # Test Supabase connection with a simple query
                    response = client.table("marketing_generations").select("count", count="exact").limit(1).execute()
                    health_status["components"]["database"] = {
                        "status": "healthy",
                        "type": "supabase",
                        "tables_accessible": True
                    }
                except Exception as query_error:
                    health_status["components"]["database"] = {
                        "status": "degraded",
                        "error": f"Query failed: {str(query_error)[:100]}",
                        "type": "supabase"
                    }
                    health_status["status"] = "degraded"
            else:
                health_status["components"]["database"] = {
                    "status": "unhealthy",
                    "error": "Client not initialized",
                    "type": "unknown"
                }
                health_status["status"] = "unhealthy"
        else:
            health_status["components"]["database"] = {
                "status": "unhealthy",
                "error": "Modules not loaded",
                "type": "unknown"
            }
            health_status["status"] = "unhealthy"
    except Exception as db_error:
        health_status["components"]["database"] = {
            "status": "unhealthy",
            "error": str(db_error)[:200],
            "type": "unknown"
        }
        health_status["status"] = "unhealthy"
    
    # Check configuration
    health_status["components"]["configuration"] = {
        "status": "healthy" if CONFIG_LOADED else "unhealthy",
        "loaded": CONFIG_LOADED,
        "environment": ENVIRONMENT
    }
    
    # Check modules
    health_status["components"]["modules"] = {
        "status": "healthy" if MODULES_LOADED else "unhealthy",
        "loaded": MODULES_LOADED,
        "utils_loaded": UTILS_LOADED,
        "auth_loaded": AUTH_LOADED
    }
    
    # If any component is unhealthy, return 503
    if health_status["status"] == "unhealthy":
        return JSONResponse(
            status_code=503,
            content=health_status
        )
    
    return health_status

@app.post("/api/generate")
async def generate_api(
    website_url: Optional[str] = Form(None),
    ppt_file: Optional[UploadFile] = File(None),
    image_count: int = Form(3),
    user_id: str = Depends(get_current_user_id)  # Secure production authentication
):
    """
    Generate marketing assets with TRUE PARALLEL image generation
    
    Authentication: JWT Bearer token (production) or X-User-ID header (development)
    """
    if not MODULES_LOADED or not UTILS_LOADED:
        raise HTTPException(status_code=503, detail="Service modules not loaded")
    
    start_time = time.time()
    
    logger.info(f"🚀 Generation request - User: {user_id[:8]}..., Images: {image_count}")
    
    # Validate inputs using config
    if image_count < 1 or image_count > config.MAX_IMAGES:
        raise HTTPException(
            status_code=400,
            detail=f"image_count must be between 1 and {config.MAX_IMAGES}"
        )
    
    if not website_url and not ppt_file:
        raise HTTPException(
            status_code=400,
            detail="Either website_url or ppt_file must be provided"
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
                    
            logger.info(f"🌐 Extracting content from: {website_url}")
            website_text = await asyncio.to_thread(
                extract_text_from_url_sync, 
                website_url,
                timeout=config.REQUEST_TIMEOUT
            )
            
            if not website_text:
                logger.warning(f"⚠️ No content extracted from website: {website_url}")
                if not ppt_file:  # Only warn if this is the only source
                    logger.warning("⚠️ Website returned no extractable content")
        
        # Extract PPT content
        if ppt_file and ppt_file.filename:
            if not ppt_file.filename.lower().endswith(('.pptx', '.ppt')):
                raise HTTPException(
                    status_code=400,
                    detail="Only PPTX/PPT files are supported"
                )
            
            logger.info(f"📊 Processing PPT file: {ppt_file.filename}")
            file_content = await ppt_file.read()
            
            # File size check using config
            if len(file_content) > config.FILE_SIZE_LIMIT:
                raise HTTPException(
                    status_code=400,
                    detail=f"PPT file size exceeds {config.FILE_SIZE_LIMIT // (1024*1024)}MB limit"
                )
                
            ppt_text = extract_text_from_pptx(file_content)
            if not ppt_text:
                logger.warning(f"⚠️ No content extracted from PPT: {ppt_file.filename}")
                if not website_url:  # Only warn if this is the only source
                    logger.warning("⚠️ PPT file contains no extractable text content")
        
        if not ppt_text and not website_text:
            raise HTTPException(
                status_code=400, 
                detail="No content found in the provided sources"
            )
        
        # Create generation session
        try:
            logger.info(f"📝 Creating generation session for user: {user_id[:8]}...")
            generation_id = db.create_generation_session(
                user_id=user_id,
                website_url=website_url,
                ppt_text=ppt_text,
                website_text=website_text
            )
            logger.info(f"✅ Generation session created: {generation_id}")
        except Exception as db_error:
            logger.error(f"❌ Failed to create generation session: {db_error}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize generation session"
            )
        
        logger.info(f"🚀 Starting TRUE PARALLEL generation: {generation_id}")
        
        try:
            # Run TRUE PARALLEL generation
            results = await generate_marketing_assets(
                ppt_text=ppt_text,
                website_text=website_text,
                user_id=user_id,
                generation_id=generation_id,
                image_count=min(image_count, config.MAX_IMAGES)
            )
            
            total_time = time.time() - start_time
            results["generation_time"] = round(total_time, 2)
            
            logger.info(f"✅ Generation completed in {total_time:.0f}s: {generation_id}")
            logger.info(f"📊 Generated {len(results.get('generated_images', []))} images")
            
            return {
                "success": True,
                "generation_id": generation_id,
                "user_id": user_id,
                "mode": "true_parallel",
                "data": results,
                "performance": {
                    "total_time": round(total_time, 2),
                    "images_generated": len(results.get('generated_images', [])),
                    "parallel_mode": "true_parallel",
                    "timeout_setting": config.REQUEST_TIMEOUT
                }
            }
            
        except HTTPException:
            raise
        except Exception as gen_error:
            logger.error(f"❌ Generation failed: {gen_error}", exc_info=True)
            try:
                db.fail_generation(generation_id, str(gen_error)[:500])
            except Exception as fail_error:
                logger.error(f"❌ Failed to mark generation as failed: {fail_error}")
            raise HTTPException(
                status_code=500, 
                detail="Generation process failed"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error in generate_api: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/generate-stream")
async def generate_stream_api(
    website_url: Optional[str] = Form(None),
    ppt_file: Optional[UploadFile] = File(None),
    image_count: int = Form(3),
    user_id: str = Depends(get_current_user_id)  # Secure production authentication
):
    """
    Stream generation progress with TRUE PARALLEL image generation
    
    Authentication: JWT Bearer token (production) or X-User-ID header (development)
    """
    if not MODULES_LOADED or not UTILS_LOADED:
        raise HTTPException(status_code=503, detail="Service modules not loaded")
    
    logger.info(f"📡 Stream generation request - User: {user_id[:8]}...")
    
    # Validate inputs using config
    if image_count < 1 or image_count > config.MAX_IMAGES:
        raise HTTPException(
            status_code=400,
            detail=f"image_count must be between 1 and {config.MAX_IMAGES}"
        )
    
    try:
        website_text = ""
        ppt_text = ""
        
        # Extract content
        if website_url:
            from urllib.parse import urlparse
            parsed = urlparse(website_url)
            if not all([parsed.scheme, parsed.netloc]):
                raise HTTPException(status_code=400, detail="Invalid website URL")
            
            logger.info(f"🌐 Extracting content from: {website_url}")
            website_text = await asyncio.to_thread(
                extract_text_from_url_sync, 
                website_url,
                timeout=config.REQUEST_TIMEOUT
            )
        
        if ppt_file and ppt_file.filename and ppt_file.filename.lower().endswith(('.pptx', '.ppt')):
            logger.info(f"📊 Processing PPT file: {ppt_file.filename}")
            file_content = await ppt_file.read()
            
            # File size check using config
            if len(file_content) > config.FILE_SIZE_LIMIT:
                raise HTTPException(
                    status_code=400,
                    detail=f"PPT file size exceeds {config.FILE_SIZE_LIMIT // (1024*1024)}MB limit"
                )
                
            ppt_text = extract_text_from_pptx(file_content)
        
        if not ppt_text and not website_text:
            raise HTTPException(status_code=400, detail="No content found.")
        
        # Create generation session
        try:
            logger.info(f"📝 Creating generation session for streaming: {user_id[:8]}...")
            generation_id = db.create_generation_session(
                user_id=user_id,
                website_url=website_url,
                ppt_text=ppt_text,
                website_text=website_text
            )
            logger.info(f"✅ Stream session created: {generation_id}")
        except Exception as db_error:
            logger.error(f"❌ Failed to create generation session: {db_error}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize generation session"
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
                    "mode": "true_parallel",
                    "timeout": config.REQUEST_TIMEOUT
                }) + "\n"
                
                # Stream TRUE PARALLEL generation
                async for chunk in generate_marketing_assets_stream(
                    ppt_text=ppt_text,
                    website_text=website_text,
                    user_id=user_id,
                    generation_id=generation_id,
                    image_count=min(image_count, config.MAX_IMAGES)
                ):
                    yield json.dumps(chunk) + "\n"
                
                # Send completion
                yield json.dumps({
                    "type": "complete",
                    "timestamp": time.time(),
                    "generation_id": generation_id,
                    "mode": "true_parallel",
                    "message": "Generation completed successfully"
                }) + "\n"
                
            except Exception as e:
                logger.error(f"❌ Stream generation error: {e}", exc_info=True)
                try:
                    db.fail_generation(generation_id, str(e)[:500])
                except Exception as fail_error:
                    logger.error(f"❌ Failed to mark generation as failed: {fail_error}")
                
                yield json.dumps({
                    "type": "error",
                    "timestamp": time.time(),
                    "message": "Generation failed",
                    "generation_id": generation_id,
                    "error_type": type(e).__name__
                }) + "\n"
        
        return StreamingResponse(
            generate(),
            media_type='application/x-ndjson',
            headers={
                "X-Accel-Buffering": "no",
                "Cache-Control": "no-cache",
                "X-Generation-ID": generation_id,
                "X-User-ID": user_id,
                "X-Timeout": str(config.REQUEST_TIMEOUT)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Stream endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/generations")
async def get_user_generations(
    user_id: str = Depends(get_current_user_id),  # Secure production authentication
    limit: int = 20
):
    """Get all generations for current user - PRODUCTION VERSION (no memory fallback)"""
    if not MODULES_LOADED:
        raise HTTPException(status_code=503, detail="Service modules not loaded")
    
    try:
        logger.info(f"📋 Getting generations for user: {user_id[:8]}..., limit: {limit}")
        
        # Get generations from database ONLY - no memory fallback in production
        # This ensures consistency across multiple worker processes
        generations = []
        
        try:
            # Try to get from Supabase
            client = db._get_client()
            if client:
                # Query generations for this user
                response = client.table("marketing_generations") \
                    .select("*") \
                    .eq("user_id", user_id) \
                    .order("created_at", desc=True) \
                    .limit(min(limit, 100)) \
                    .execute()
                
                if response.data:
                    for gen in response.data:
                        # Get associated images
                        images_response = client.table("marketing_images") \
                            .select("*") \
                            .eq("generation_id", gen["id"]) \
                            .order("image_index") \
                            .execute()
                        
                        gen["images"] = images_response.data if images_response.data else []
                        gen["storage"] = "supabase"
                        generations.append(gen)
            
            logger.info(f"✅ Retrieved {len(generations)} generations from database")
            
        except Exception as db_error:
            logger.error(f"❌ Database query failed: {db_error}")
            # In production, we don't fall back to memory
            raise HTTPException(
                status_code=503,
                detail="Database service temporarily unavailable"
            )
        
        return {
            "success": True,
            "user_id": user_id,
            "count": len(generations),
            "generations": generations,
            "storage": "database"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting generations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/generations/{generation_id}")
async def get_generation(
    generation_id: str,
    user_id: str = Depends(get_current_user_id)  # Secure production authentication
):
    """Get specific generation by ID - PRODUCTION VERSION (no memory fallback)"""
    if not MODULES_LOADED:
        raise HTTPException(status_code=503, detail="Service modules not loaded")
    
    try:
        logger.info(f"🔍 Getting generation: {generation_id} for user: {user_id[:8]}...")
        
        # Get from database ONLY - no memory fallback in production
        generation = None
        
        try:
            client = db._get_client()
            if client:
                # Get generation with user validation
                response = client.table("marketing_generations") \
                    .select("*") \
                    .eq("id", generation_id) \
                    .eq("user_id", user_id) \
                    .single() \
                    .execute()
                
                if response.data:
                    # Get associated images
                    images_response = client.table("marketing_images") \
                        .select("*") \
                        .eq("generation_id", generation_id) \
                        .order("image_index") \
                        .execute()
                    
                    generation = response.data
                    generation["images"] = images_response.data if images_response.data else []
                    generation["storage"] = "supabase"
            
            if not generation:
                logger.warning(f"⚠️ Generation not found or access denied: {generation_id}")
                raise HTTPException(
                    status_code=404, 
                    detail="Generation not found or access denied"
                )
            
            logger.info(f"✅ Retrieved generation: {generation_id}")
            
        except Exception as db_error:
            logger.error(f"❌ Database query failed: {db_error}")
            raise HTTPException(
                status_code=503,
                detail="Database service temporarily unavailable"
            )
        
        return {
            "success": True,
            "generation": generation,
            "storage": generation.get("storage", "unknown")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting generation {generation_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with structured logging"""
    logger.warning(f"⚠️ HTTP {exc.status_code} at {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.now().isoformat(),
            "path": request.url.path
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions - log internally, return generic error"""
    logger.error(f"❌ Unhandled exception at {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "status_code": 500,
            "timestamp": datetime.now().isoformat()
        }
    )

# Application startup event
@app.on_event("startup")
async def startup_event():
    """Run on application startup - production initialization"""
    logger.info(f"""
    ╔══════════════════════════════════════════════════════╗
    ║    🚀 Marketing Generator API - Production Ready     ║
    ╠══════════════════════════════════════════════════════╣
    ║  Environment: {ENVIRONMENT:<30} ║
    ║  Mode:       Production                              ║
    ║  Auth:       {'JWT + Header' if AUTH_LOADED else 'Header Only':<30} ║
    ║  Timeout:    {config.REQUEST_TIMEOUT//60} minutes                        ║
    ╚══════════════════════════════════════════════════════╝
    """)
    
    if allowed_origins:
        logger.info(f"✅ CORS allowed origins: {allowed_origins}")
    else:
        logger.warning("⚠️ No CORS origins configured in production")
    
    if not MODULES_LOADED:
        logger.critical("❌ CRITICAL: Application modules failed to load")
    else:
        logger.info("✅ All modules loaded successfully")

# For local development only (not used in production)
if __name__ == "__main__":
    import uvicorn
    
    if ENVIRONMENT == "production":
        logger.warning("⚠️ Running production code in development mode")
    
    port = config.PORT if CONFIG_LOADED else int(os.getenv("PORT", "5000"))
    host = config.HOST if CONFIG_LOADED else os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"🏃 Starting development server on {host}:{port}")
    
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=ENVIRONMENT == "development",
        log_level="info",
        timeout_keep_alive=config.REQUEST_TIMEOUT
    )