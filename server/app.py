#!/usr/bin/env python3
"""
Newspod Server - FastAPI server with Supabase authentication
Provides automated daily podcast generation for authenticated users.
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
from supabase import create_client, Client
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

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
security = HTTPBearer()

# Global variables
supabase: Client = None
scheduler: AsyncIOScheduler = None


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
    schedule_time: str = "08:00"  # Daily generation time (HH:MM)
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
    global supabase, scheduler

    # Initialize Supabase
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")

    if not supabase_url or not supabase_key:
        logger.warning("SUPABASE_URL and SUPABASE_ANON_KEY not set - running in demo mode")
        supabase = None
    else:
        try:
            supabase = create_client(supabase_url, supabase_key)
            logger.info("Supabase client initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Supabase: {e} - running in demo mode")
            supabase = None

    # Initialize scheduler
    scheduler = AsyncIOScheduler()
    if supabase:
        try:
            await setup_scheduled_jobs()
        except Exception as e:
            logger.warning(f"Failed to setup scheduled jobs: {e}")
    scheduler.start()
    logger.info("Scheduler started")

    yield

    # Cleanup
    if scheduler:
        scheduler.shutdown()
        logger.info("Scheduler stopped")


# Create FastAPI app
app = FastAPI(
    title="Newspod Server",
    description="Automated newsletter podcast generation with user authentication",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Get current authenticated user from JWT token"""
    if supabase is None:
        # Demo mode - return mock user
        return {
            'id': 'demo-user-123',
            'email': 'demo@example.com',
            'user_metadata': {'full_name': 'Demo User'}
        }

    try:
        # Verify JWT token with Supabase
        response = supabase.auth.get_user(credentials.credentials)
        if response.user:
            return response.user
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_user_config(user_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve user configuration from database"""
    if supabase is None:
        # Demo mode - return mock config
        if user_id == 'demo-user-123':
            return {
                'config': {
                    'emails': [{'address': 'demo@example.com', 'password': 'demo', 'imap_server': 'demo.com'}],
                    'claude_api_key': 'demo-key',
                    'elevenlabs_api_key': 'demo-key',
                    'personalization': {'user_name': 'Demo', 'interests': ['Demo']},
                    'schedule_time': '08:00',
                    'timezone': 'UTC'
                }
            }
        return None

    try:
        response = supabase.table('user_configs').select('*').eq('user_id', user_id).single().execute()
        return response.data if response.data else None
    except Exception as e:
        logger.error(f"Error fetching user config: {e}")
        return None


async def save_user_config(user_id: str, config: Dict[str, Any]) -> bool:
    """Save user configuration to database"""
    if supabase is None:
        # Demo mode - always return success
        logger.info(f"Demo mode: would save config for user {user_id}")
        return True

    try:
        # Upsert user configuration
        response = supabase.table('user_configs').upsert({
            'user_id': user_id,
            'config': config,
            'updated_at': datetime.utcnow().isoformat()
        }).execute()
        return True
    except Exception as e:
        logger.error(f"Error saving user config: {e}")
        return False


async def generate_podcast_for_user(user_id: str, config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Generate podcast for a specific user"""
    try:
        logger.info(f"Generating podcast for user {user_id}")

        if NewsletterPodcastGenerator is None:
            logger.warning("NewsletterPodcastGenerator not available - returning mock result")
            result = {
                'success': True,
                'newsletters_found': 0,
                'message': 'Mock generation - NewsletterPodcastGenerator not available'
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

        # Save generation log
        log_entry = {
            'user_id': user_id,
            'generated_at': datetime.utcnow().isoformat(),
            'success': result['success'],
            'newsletters_found': result['newsletters_found'],
            'result': result
        }

        if supabase:
            supabase.table('generation_logs').insert(log_entry).execute()
        else:
            logger.info(f"Demo mode: would save generation log for user {user_id}")

        logger.info(f"Podcast generation completed for user {user_id}: {result['success']}")
        return result

    except Exception as e:
        logger.error(f"Error generating podcast for user {user_id}: {e}")
        return {
            'success': False,
            'errors': [str(e)],
            'newsletters_found': 0
        }


async def setup_scheduled_jobs():
    """Set up scheduled jobs for all users"""
    if supabase is None:
        logger.info("Demo mode: skipping scheduled jobs setup")
        return

    try:
        # Get all users with configurations
        response = supabase.table('user_configs').select('user_id, config').execute()

        for user_config in response.data:
            user_id = user_config['user_id']
            config = user_config['config']

            # Extract schedule information
            schedule_time = config.get('schedule_time', '08:00')
            timezone = config.get('timezone', 'UTC')

            # Parse time
            hour, minute = map(int, schedule_time.split(':'))

            # Create cron trigger
            trigger = CronTrigger(
                hour=hour,
                minute=minute,
                timezone=timezone
            )

            # Add job
            scheduler.add_job(
                func=generate_podcast_for_user,
                trigger=trigger,
                args=[user_id, config],
                id=f"daily_podcast_{user_id}",
                replace_existing=True
            )

            logger.info(f"Scheduled daily job for user {user_id} at {schedule_time} {timezone}")

    except Exception as e:
        logger.error(f"Error setting up scheduled jobs: {e}")


# API Routes

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Newspod Server is running", "timestamp": datetime.utcnow().isoformat()}


@app.post("/auth/signup")
async def sign_up(user_data: UserSignUp):
    """User registration endpoint"""
    try:
        response = supabase.auth.sign_up({
            "email": user_data.email,
            "password": user_data.password,
            "options": {
                "data": {
                    "full_name": user_data.full_name
                }
            }
        })

        if response.user:
            return {
                "message": "User created successfully",
                "user": response.user,
                "session": response.session
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to create user")

    except Exception as e:
        logger.error(f"Signup error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/auth/signin")
async def sign_in(user_data: UserSignIn):
    """User authentication endpoint"""
    try:
        response = supabase.auth.sign_in_with_password({
            "email": user_data.email,
            "password": user_data.password
        })

        if response.user:
            return {
                "message": "Authentication successful",
                "user": response.user,
                "session": response.session
            }
        else:
            raise HTTPException(status_code=401, detail="Invalid credentials")

    except Exception as e:
        logger.error(f"Signin error: {e}")
        raise HTTPException(status_code=401, detail="Invalid credentials")


@app.post("/auth/signout")
async def sign_out(current_user: Dict[str, Any] = Depends(get_current_user)):
    """User logout endpoint"""
    try:
        supabase.auth.sign_out()
        return {"message": "Signed out successfully"}
    except Exception as e:
        logger.error(f"Signout error: {e}")
        raise HTTPException(status_code=500, detail="Failed to sign out")


@app.get("/user/profile")
async def get_profile(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get user profile"""
    return {"user": current_user}


@app.get("/user/config")
async def get_config(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get user configuration"""
    user_id = current_user.id
    config = await get_user_config(user_id)

    if not config:
        raise HTTPException(status_code=404, detail="User configuration not found")

    return {"config": config['config']}


@app.post("/user/config")
async def update_config(
    config: UserConfig,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update user configuration"""
    user_id = current_user.id

    # Save configuration
    success = await save_user_config(user_id, config.dict())

    if not success:
        raise HTTPException(status_code=500, detail="Failed to save configuration")

    # Update scheduled job
    try:
        # Remove existing job
        scheduler.remove_job(f"daily_podcast_{user_id}")
    except:
        pass  # Job might not exist yet

    # Add new job
    schedule_time = config.schedule_time
    timezone = config.timezone
    hour, minute = map(int, schedule_time.split(':'))

    trigger = CronTrigger(
        hour=hour,
        minute=minute,
        timezone=timezone
    )

    scheduler.add_job(
        func=generate_podcast_for_user,
        trigger=trigger,
        args=[user_id, config.dict()],
        id=f"daily_podcast_{user_id}",
        replace_existing=True
    )

    return {"message": "Configuration updated successfully"}


@app.post("/podcast/generate")
async def generate_podcast(
    request: PodcastGenerationRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Manually trigger podcast generation"""
    user_id = current_user.id

    # Get user configuration
    user_config_data = await get_user_config(user_id)
    if not user_config_data:
        raise HTTPException(status_code=404, detail="User configuration not found")

    config = user_config_data['config']

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
    user_id = current_user.id

    if supabase is None:
        # Demo mode - return mock history
        return {
            "history": [
                {
                    "id": "demo-1",
                    "user_id": user_id,
                    "generated_at": "2024-10-08T10:00:00Z",
                    "success": True,
                    "newsletters_found": 3,
                    "result": {"success": True, "message": "Demo generation"}
                }
            ]
        }

    try:
        response = supabase.table('generation_logs')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('generated_at', desc=True)\
            .limit(limit)\
            .execute()

        return {"history": response.data}
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch history")


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )