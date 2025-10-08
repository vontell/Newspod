#!/usr/bin/env python3
"""
Simple Newspod Server - FastAPI server without Supabase dependencies for testing
Demonstrates the API structure and authentication patterns.
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import asyncio
from contextlib import asynccontextmanager

# Add parent directory to Python path to import newsletter_podcast
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import uvicorn

try:
    from newsletter_podcast.podcast_generator import NewsletterPodcastGenerator
except ImportError:
    # Fallback for testing without full dependencies
    NewsletterPodcastGenerator = None
    logging.warning("NewsletterPodcastGenerator not available - server running in API-only mode")


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Security
security = HTTPBearer(auto_error=False)

# Mock user store (in production, this would be Supabase)
MOCK_USERS = {
    "demo@example.com": {
        "id": "demo-user-123",
        "email": "demo@example.com",
        "password": "demo123",
        "user_metadata": {"full_name": "Demo User"}
    }
}

# Mock config store
MOCK_CONFIGS = {
    "demo-user-123": {
        "emails": [{"address": "demo@example.com", "password": "demo", "imap_server": "demo.com"}],
        "claude_api_key": "demo-key",
        "elevenlabs_api_key": "demo-key",
        "personalization": {"user_name": "Demo", "interests": ["Demo"]},
        "schedule_time": "08:00",
        "timezone": "UTC"
    }
}

# Mock history
MOCK_HISTORY = {
    "demo-user-123": [
        {
            "id": "demo-1",
            "user_id": "demo-user-123",
            "generated_at": "2024-10-08T10:00:00Z",
            "success": True,
            "newsletters_found": 3,
            "result": {"success": True, "message": "Demo generation completed"}
        }
    ]
}


class UserConfig(BaseModel):
    """User configuration for podcast generation"""
    emails: List[Dict[str, str]]
    claude_api_key: str
    elevenlabs_api_key: str
    elevenlabs_voice_id: Optional[str] = None
    google_drive_enabled: bool = False
    google_drive_credentials_path: Optional[str] = None
    google_drive_folder_id: Optional[str] = None
    personalization: Dict[str, Any]
    schedule_time: str = "08:00"
    timezone: str = "UTC"


class UserSignUp(BaseModel):
    """User signup request"""
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserSignIn(BaseModel):
    """User signin request"""
    email: EmailStr
    password: str


class PodcastGenerationRequest(BaseModel):
    """Manual podcast generation request"""
    hours_lookback: int = 24
    target_duration_minutes: int = 10
    newsletter_filters: Optional[List[str]] = None
    segmented: bool = False
    segment_duration: int = 2


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager"""
    logger.info("Simple Newspod Server starting up...")
    yield
    logger.info("Simple Newspod Server shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Newspod Server (Simple Demo)",
    description="Demo version of automated newsletter podcast generation server",
    version="1.0.0-demo",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Dict[str, Any]:
    """Get current authenticated user from JWT token"""
    # In demo mode, accept any token or no token
    if not credentials or credentials.credentials == "demo-token":
        return MOCK_USERS["demo@example.com"]

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials. Use 'demo-token' or no token for demo.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def generate_podcast_for_user(user_id: str, config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Generate podcast for a specific user"""
    try:
        logger.info(f"Generating podcast for user {user_id}")

        if NewsletterPodcastGenerator is None:
            logger.info("NewsletterPodcastGenerator not available - returning mock result")
            result = {
                'success': True,
                'newsletters_found': 2,
                'message': 'Mock generation completed successfully',
                'script_path': f'/mock/output/{user_id}/script.txt',
                'audio_path': f'/mock/output/{user_id}/podcast.mp3'
            }
        else:
            # Create podcast generator with user config
            generator = NewsletterPodcastGenerator(config)

            # Generate podcast
            result = generator.generate_podcast(
                hours_lookback=kwargs.get('hours_lookback', 24),
                target_duration_minutes=kwargs.get('target_duration_minutes', 10),
                newsletter_filters=kwargs.get('newsletter_filters'),
                output_dir=f"output/{user_id}",
                quick_mode=kwargs.get('quick_mode', False)
            )

        # Add to mock history
        if user_id not in MOCK_HISTORY:
            MOCK_HISTORY[user_id] = []

        MOCK_HISTORY[user_id].insert(0, {
            "id": f"gen-{len(MOCK_HISTORY[user_id])}",
            "user_id": user_id,
            "generated_at": datetime.utcnow().isoformat(),
            "success": result['success'],
            "newsletters_found": result['newsletters_found'],
            "result": result
        })

        logger.info(f"Podcast generation completed for user {user_id}: {result['success']}")
        return result

    except Exception as e:
        logger.error(f"Error generating podcast for user {user_id}: {e}")
        return {
            'success': False,
            'errors': [str(e)],
            'newsletters_found': 0
        }


# API Routes

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Newspod Server (Simple Demo) is running",
        "timestamp": datetime.utcnow().isoformat(),
        "note": "This is a demo version. Use 'demo-token' as Bearer token or no auth."
    }


@app.post("/auth/signup")
async def sign_up(user_data: UserSignUp):
    """User registration endpoint (demo)"""
    # In demo mode, just return success
    user = {
        "id": "new-user-" + str(hash(user_data.email)),
        "email": user_data.email,
        "user_metadata": {"full_name": user_data.full_name}
    }

    return {
        "message": "User created successfully (demo)",
        "user": user,
        "session": {"access_token": "demo-token"}
    }


@app.post("/auth/signin")
async def sign_in(user_data: UserSignIn):
    """User authentication endpoint (demo)"""
    # In demo mode, accept demo credentials
    if user_data.email == "demo@example.com" and user_data.password == "demo123":
        user = MOCK_USERS["demo@example.com"]
        return {
            "message": "Authentication successful",
            "user": user,
            "session": {"access_token": "demo-token"}
        }

    raise HTTPException(status_code=401, detail="Invalid credentials. Try demo@example.com / demo123")


@app.post("/auth/signout")
async def sign_out(current_user: Dict[str, Any] = Depends(get_current_user)):
    """User logout endpoint"""
    return {"message": "Signed out successfully (demo)"}


@app.get("/user/profile")
async def get_profile(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get user profile"""
    return {"user": current_user}


@app.get("/user/config")
async def get_config(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get user configuration"""
    user_id = current_user["id"]
    config = MOCK_CONFIGS.get(user_id)

    if not config:
        raise HTTPException(status_code=404, detail="User configuration not found")

    return {"config": config}


@app.post("/user/config")
async def update_config(
    config: UserConfig,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update user configuration"""
    user_id = current_user["id"]

    # Save configuration to mock store
    MOCK_CONFIGS[user_id] = config.dict()

    return {"message": "Configuration updated successfully (demo)"}


@app.post("/podcast/generate")
async def generate_podcast(
    request: PodcastGenerationRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Manually trigger podcast generation"""
    user_id = current_user["id"]

    # Get user configuration
    config = MOCK_CONFIGS.get(user_id)
    if not config:
        raise HTTPException(status_code=404, detail="User configuration not found")

    # Generate podcast
    result = await generate_podcast_for_user(
        user_id=user_id,
        config=config,
        hours_lookback=request.hours_lookback,
        target_duration_minutes=request.target_duration_minutes,
        newsletter_filters=request.newsletter_filters
    )

    return {"result": result}


@app.get("/podcast/history")
async def get_podcast_history(
    limit: int = 10,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get user's podcast generation history"""
    user_id = current_user["id"]
    history = MOCK_HISTORY.get(user_id, [])

    return {"history": history[:limit]}


if __name__ == "__main__":
    uvicorn.run(
        "simple_app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )