# Newspod - Personal Newsletter Podcast Generator

Transform your daily newsletters into a personalized podcast, narrated by AI and delivered straight to your Google Drive for easy listening on any device.

## 🎙️ What it does

Newspod automatically:
- **Fetches newsletters** from multiple email accounts
- **Intelligently filters** content using Claude AI based on your interests
- **Generates personalized scripts** tailored to your role and preferences
- **Creates audio podcasts** using ElevenLabs voice synthesis
- **Uploads to Google Drive** with smart naming for easy mobile access

Perfect for busy professionals who want to consume their newsletters during commutes, workouts, or any time reading isn't convenient.

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Gmail account(s) with app passwords
- Anthropic API key (Claude)
- ElevenLabs API key
- Google Cloud project (for Drive uploads)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd newspod
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up configuration**
   ```bash
   cp config.sample.json config.json
   ```
   Edit `config.json` with your credentials (see Configuration section)

4. **Run your first podcast**
   ```bash
   python main.py --config config.json
   ```

## ⚙️ Configuration

### 1. Email Setup (Multiple Accounts Supported)

```json
"emails": [
  {
    "address": "your.email@gmail.com",
    "password": "xxxx xxxx xxxx xxxx",  // Gmail app password
    "imap_server": "imap.gmail.com"
  },
  {
    "address": "second.email@gmail.com",
    "password": "yyyy yyyy yyyy yyyy",
    "imap_server": "imap.gmail.com"
  }
]
```

**Getting Gmail App Passwords:**
1. Enable 2-Factor Authentication on your Google account
2. Go to [Google App Passwords](https://myaccount.google.com/apppasswords)
3. Create a new app password for "Mail"
4. Enable IMAP in Gmail settings

### 2. API Keys

```json
"claude": {
  "api_key": "sk-ant-api03-...",
  "model": "claude-3-opus-20240229",
  "filter_model": "claude-3-5-haiku-20241022"  // Fast model for filtering
},
"elevenlabs": {
  "api_key": "sk_...",
  "voice_id": "voice_id_here"  // Optional, uses default if not specified
}
```

### 3. Google Drive Setup

```json
"google_drive": {
  "enabled": true,
  "credentials_path": "~/path/to/oauth_credentials.json",
  "folder_id": "your-drive-folder-id"
}
```

**Setting up Google Drive:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable Google Drive API
4. Create OAuth 2.0 credentials (Desktop app type)
5. Download the credentials JSON
6. Get folder ID from Drive URL: `https://drive.google.com/drive/folders/FOLDER_ID`

### 4. Personalization

```json
"personalization": {
  "user_name": "Your Name",
  "user_role": "Your role/title",
  "interests": ["AI/ML", "tech news", "startups"],
  "filter_mode": "smart"  // or "simple" for keyword-only filtering
}
```

## 📱 Usage

### Basic Commands

```bash
# Generate a 10-minute podcast
python main.py --config config.json

# Quick mode: 2.5-minute summary using cached emails
python main.py --config config.json --quick

# Custom duration
python main.py --config config.json --duration 15

# Look back 48 hours instead of 24
python main.py --config config.json --hours 48

# Filter specific newsletters
python main.py --config config.json --filters "TechCrunch" "AI Weekly"
```

### Output Structure

```
output/
├── .cache/                    # Cached newsletters
├── podcast_script_*.txt       # Generated scripts
├── podcast_*.mp3             # Audio files
├── newsletters_metadata_*.json # Newsletter details
├── filter_results_*.json     # AI filtering decisions
└── results_*.json           # Complete generation results
```

## 🧠 Smart Features

### Intelligent Newsletter Filtering
- Uses Claude AI to evaluate newsletter relevance
- Considers your role, interests, and content quality
- Filters out pure marketing/promotional content
- Parallel processing for fast evaluation
- Detailed logging of filtering decisions

### Personalized Scripts
- Addresses you by name with conversational tone
- Tailored insights for your specific role
- Prioritizes breaking news and important updates
- **Always cites sources** for each topic
- Groups related topics from different newsletters

### Smart Naming
- Auto-generates concise titles using AI
- Files named as: `YYYY-MM-DD - Brief Topic Summary.mp3`
- Perfect for organizing in Google Drive

## 🔧 Advanced Features

### Multiple Email Accounts
Fetches and combines newsletters from all configured accounts

### Caching
- Newsletters cached for 1 hour
- Quick mode (`--quick`) uses cached content
- Reduces API calls and speeds up testing

### Google Drive Integration
- Automatic upload after generation
- Smart file naming with date and AI-generated summary
- Direct links for mobile access
- One-time OAuth setup

## 📊 How It Works

1. **Email Fetching**: Connects via IMAP to fetch emails from past 24 hours
2. **Smart Filtering**: Claude evaluates each newsletter's relevance
3. **Script Generation**: Creates personalized, conversational podcast script
4. **Voice Synthesis**: ElevenLabs converts script to natural speech
5. **Upload**: Saves locally and optionally to Google Drive

## 🎯 Perfect For

- **Commuters**: Turn reading time into listening time
- **Busy Professionals**: Stay informed while multitasking
- **AI Enthusiasts**: Get personalized AI/tech news summaries
- **Newsletter Subscribers**: Finally tackle that newsletter backlog

## 📈 Future Enhancements

- RSS feed support
- Scheduled generation via cron
- Web interface
- Multiple voices for different sections
- Background music/sound effects
- Podcast RSS feed generation
- Mobile app integration

## 🐛 Troubleshooting

### Common Issues

1. **Gmail Authentication Failed**
   - Ensure 2FA is enabled
   - Use app password, not account password
   - Enable IMAP in Gmail settings

2. **No Newsletters Found**
   - Check spam/promotional folders
   - Adjust filter criteria
   - Try simple mode before smart filtering

3. **Google Drive Upload Failed**
   - Re-authenticate by deleting token file
   - Check folder ID is correct
   - Ensure Drive API is enabled

4. **JSON Parse Errors in Filtering**
   - Normal when AI adds extra commentary
   - System handles gracefully with fallbacks

## 📄 License

This project is for personal use. Feel free to adapt for your needs!

---

Built with ❤️ to solve the daily newsletter overload problem.