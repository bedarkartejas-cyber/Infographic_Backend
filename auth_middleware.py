import os
import jwt
from fastapi import HTTPException, Request
from typing import Optional
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

# PRODUCTION SECRET: This must be set in your hosting provider (Railway/Render)
# Find this in Supabase Dashboard -> Project Settings -> API -> JWT Secret
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

async def get_user_id_from_token(request: Request) -> str:
    """
    Extracts and verifies the user_id from a Supabase JWT token.
    This version strictly verifies the signature and expiration.
    """
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header"
        )
    
    token = auth_header.replace("Bearer ", "")
    
    if not SUPABASE_JWT_SECRET:
        # Critical security check for production
        raise HTTPException(
            status_code=500,
            detail="Server misconfiguration: JWT secret not found"
        )
    
    try:
        # Verify the token against the Supabase secret
        # Supabase uses HS256 for its JWTs
        decoded = jwt.decode(
            token, 
            SUPABASE_JWT_SECRET, 
            algorithms=["HS256"],
            audience="authenticated" # Standard Supabase audience
        )
        
        user_id = decoded.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: no user_id")
        
        return user_id
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

async def get_user_id_from_header(request: Request) -> str:
    """
    FOR TESTING ONLY: Get user_id from custom header.
    Should be disabled or protected in production.
    """
    user_id = request.headers.get("X-User-ID")
    
    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="X-User-ID header is required"
        )
    
    return user_id