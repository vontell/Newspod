# Newspod Server

A FastAPI server that provides automated daily podcast generation from email newsletters with Supabase authentication.

## Features

- 🔐 **Supabase Authentication**: User registration, login, and JWT token validation
- 📧 **Multi-Email Support**: Users can configure multiple email accounts for newsletter sources
- 🎙️ **Automated Generation**: Daily scheduled podcast generation based on user preferences
- ⚙️ **User Configuration**: Personalized settings for podcast content and generation
- 📊 **Generation History**: Track and view past podcast generations
- 🔄 **Manual Triggers**: On-demand podcast generation via API

## Quick Start

### 1. Setup Supabase

1. Create a new Supabase project at https://supabase.com
2. Go to Settings → API to get your project URL and API keys
3. Run the SQL schema from `supabase_schema.sql` in your Supabase SQL editor

### 2. Environment Configuration

1. Copy `.env.example` to `.env`
2. Fill in your Supabase credentials:

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Server

```bash
python app.py
```

The server will start at `http://localhost:8000`

## API Endpoints

### Authentication

- `POST /auth/signup` - User registration
- `POST /auth/signin` - User login
- `POST /auth/signout` - User logout

### User Management

- `GET /user/profile` - Get user profile
- `GET /user/config` - Get user configuration
- `POST /user/config` - Update user configuration

### Podcast Generation

- `POST /podcast/generate` - Manually trigger podcast generation
- `GET /podcast/history` - Get generation history

## User Configuration

Users can configure their podcast generation with:

```json
{
  "emails": [
    {
      "address": "user@gmail.com",
      "password": "app-password",
      "imap_server": "imap.gmail.com"
    }
  ],
  "claude_api_key": "your-claude-key",
  "elevenlabs_api_key": "your-elevenlabs-key",
  "elevenlabs_voice_id": "voice-id",
  "personalization": {
    "user_name": "John",
    "user_role": "Engineer",
    "interests": ["AI", "Technology"]
  },
  "schedule_time": "08:00",
  "timezone": "UTC"
}
```

## Scheduled Jobs

The server automatically schedules daily podcast generation for each user based on their configured time and timezone. Jobs are managed using APScheduler and persist across server restarts.

## Security

- JWT-based authentication via Supabase
- Row Level Security (RLS) policies protect user data
- CORS configured for web clients
- Environment variables for sensitive configuration

## Deployment

For production deployment:

1. Set appropriate CORS origins
2. Use environment variables for all secrets
3. Configure proper logging
4. Set up monitoring and health checks
5. Use a production WSGI server like Gunicorn

```bash
gunicorn app:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```