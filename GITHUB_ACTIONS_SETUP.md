# GitHub Actions Setup - Daily Newsletter Podcast

This guide explains how to set up automated daily podcast generation using GitHub Actions.

## 🚀 Quick Setup (5 minutes)

### Step 1: Push your code to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/newspod.git
git push -u origin main
```

### Step 2: Add GitHub Secrets
Go to your repository → Settings → Secrets and variables → Actions → New repository secret

Add these 3 secrets:

#### 1. `PODCAST_CONFIG_JSON`
Copy your entire `config.json` content as a single secret. This makes it easy to:
- Add/remove email accounts
- Update API keys
- Change personalization settings
- Modify any configuration

**Important:** Set the Google Drive credentials path to `"gdrive_credentials.json"` (not a full path) so GitHub Actions can find it.

Example:
```json
{
  "emails": [
    {
      "address": "your.email@gmail.com",
      "password": "your-app-password",
      "imap_server": "imap.gmail.com"
    },
    {
      "address": "second.email@gmail.com",
      "password": "second-app-password",
      "imap_server": "imap.gmail.com"
    }
  ],
  "claude": {
    "api_key": "sk-ant-api03-...",
    "model": "claude-opus-4-20250514",
    "filter_model": "claude-3-5-haiku-20241022"
  },
  "elevenlabs": {
    "api_key": "sk_...",
    "voice_id": "voice_id_here"
  },
  "storage": {
    "type": "local",
    "upload_dir": "uploads"
  },
  "google_drive": {
    "enabled": true,
    "credentials_path": "gdrive_credentials.json",
    "folder_id": "your-folder-id"
  },
  "personalization": {
    "user_name": "Your Name",
    "user_role": "Your role",
    "interests": ["your", "interests"],
    "filter_mode": "smart"
  }
}
```

#### 2. `GDRIVE_CREDENTIALS_JSON`
Copy the entire content of your Google OAuth credentials JSON file (the one you downloaded from Google Cloud Console).

#### 3. `GDRIVE_TOKEN_JSON` (Required for Google Drive uploads)
**This is the authentication token that allows GitHub Actions to upload without browser login.**

To get this token:
1. **Run the script locally first** to trigger Google authentication
   ```bash
   python main.py --config config.json
   ```
2. Complete the browser authentication when prompted
3. Find the saved token file at `~/.newsletter_podcast/gdrive_token.json`
4. Copy the entire content of this token file
5. Add it as the `GDRIVE_TOKEN_JSON` secret

**Note:** This token may expire after several months. If Google Drive uploads start failing, regenerate the token locally and update this secret.

### Step 3: Test the workflow
1. Go to your repository → Actions → "Daily Newsletter Podcast Generation"
2. Click "Run workflow" → "Run workflow"
3. Wait 5-10 minutes for it to complete
4. Check your Google Drive folder for the podcast!

## ⏰ Schedule Details

- **Default schedule**: 7:00 AM ET every day (11:00 UTC)
- **To change the time**: Edit the cron expression in `.github/workflows/daily-podcast.yml`
  - Line: `- cron: '0 11 * * *'`
  - Format: `'minute hour * * *'` (in UTC time)
  - Use [crontab.guru](https://crontab.guru) to generate expressions

### Time Zone Examples:
- 7:00 AM ET: `'0 11 * * *'` (UTC-4 in summer, UTC-5 in winter)
- 7:00 AM PT: `'0 14 * * *'` (UTC-7 in summer, UTC-8 in winter)
- 7:00 AM GMT: `'0 7 * * *'`

## 📝 Managing Your Configuration

### Adding a new email account:
1. Go to repository → Settings → Secrets → Actions
2. Click on `PODCAST_CONFIG_JSON` → Update secret
3. Add the new email to the `emails` array
4. Save

### Updating API keys:
1. Go to repository → Settings → Secrets → Actions
2. Click on `PODCAST_CONFIG_JSON` → Update secret
3. Update the relevant API key
4. Save

### Changing personalization:
1. Go to repository → Settings → Secrets → Actions
2. Click on `PODCAST_CONFIG_JSON` → Update secret
3. Modify the `personalization` section
4. Save

## 🔍 Monitoring & Debugging

### Check run history:
- Go to repository → Actions to see all runs
- Click on any run to see detailed logs
- Download artifacts (MP3, scripts, metadata) from successful runs

### Email notifications:
GitHub will email you if a workflow fails. You can configure this in your GitHub notification settings.

### Manual runs:
You can trigger the podcast generation manually anytime:
1. Go to Actions → "Daily Newsletter Podcast Generation"
2. Click "Run workflow" → "Run workflow"

## 💾 Artifacts

Each run saves the following artifacts for 7 days:
- Generated MP3 files
- Podcast scripts (TXT)
- Metadata (JSON)

You can download these from the Actions run page.

## 🛠 Troubleshooting

### Common issues:

1. **"No newsletters found"**
   - Check if emails are in spam/promotional folders
   - Verify email account credentials are correct
   - Ensure IMAP is enabled in Gmail

2. **Google Drive upload failed - Authentication Issues**
   - **Most common issue**: Missing or expired `GDRIVE_TOKEN_JSON`
   - **Solution**: 
     1. Run the script locally to generate a new token
     2. Update the `GDRIVE_TOKEN_JSON` secret with the new token
   - **Prevention**: Tokens typically last several months but will eventually expire
   - **Alternative**: Set `"enabled": false` in google_drive config to skip Drive uploads

3. **Google Drive upload failed - Other Issues**
   - Check folder ID is correct (get from Drive URL)
   - Verify Drive API is enabled in Google Cloud Console
   - Ensure credentials path is set to `"gdrive_credentials.json"` in config

4. **Workflow timeout**
   - Default timeout is 30 minutes
   - Quick mode (`--quick`) should complete in 5-10 minutes
   - Check if email fetching is hanging

5. **API rate limits**
   - The workflow runs once per day by default
   - Consider using different API keys for manual testing

### Google Drive Authentication in GitHub Actions

**Why browser authentication doesn't work**: GitHub Actions runs in a headless environment without a browser, so the normal OAuth flow that opens a browser window will fail.

**Solution**: We use a pre-generated authentication token:
1. Authenticate locally on your computer (with browser access)
2. Save the resulting token as a GitHub secret
3. GitHub Actions uses this token to authenticate without needing a browser

**When to regenerate the token**:
- If you see "Token has expired" errors
- If Google Drive uploads suddenly stop working
- After changing Google account passwords
- Approximately every 6-12 months as a precaution

## 🎉 Benefits

- ✅ **Free**: 2000 minutes/month included with GitHub
- ✅ **Reliable**: Runs every day automatically
- ✅ **No maintenance**: No servers to manage
- ✅ **Version controlled**: Track changes to your configuration
- ✅ **Secure**: Secrets are encrypted and never exposed

---

Enjoy your automated daily newsletter podcasts! 🎧