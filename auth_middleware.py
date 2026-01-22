from fastapi import HTTPException, Request
from typing import Optional
import jwt
import os
from supabase_config import supabase_config

async def get_user_id_from_token(request: Request) -> str:
    """
    Extract user_id from JWT token in Authorization header
    Returns a user_id string or raises HTTPException
    """
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header"
        )
    
    token = auth_header.replace("Bearer ", "")
    
    try:
        # You can decode JWT to get user_id
        # Supabase JWT structure: {"sub": "user-id", ...}
        decoded = jwt.decode(
            token, 
            options={"verify_signature": False}  # For demo, in production verify signature
        )
        
        user_id = decoded.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: no user_id")
        
        return user_id
        
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

async def get_user_id_from_header(request: Request) -> str:
    """
    Alternative: Get user_id from custom header (for testing)
    """
    user_id = request.headers.get("X-User-ID")
    
    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="X-User-ID header is required"
        )
    
    return user_id