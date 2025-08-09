import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

# Google Drive API scope
SCOPES = ['https://www.googleapis.com/auth/drive.file']


class DriveService:
    """Service for uploading podcast files to Google Drive."""
    
    def __init__(self, credentials_path: str, token_path: Optional[str] = None):
        """
        Initialize Google Drive service.
        
        Args:
            credentials_path: Path to OAuth2 credentials JSON file
            token_path: Path to store/retrieve token (optional)
        """
        # Expand ~ to home directory
        self.credentials_path = os.path.expanduser(credentials_path)
        self.token_path = os.path.expanduser(token_path) if token_path else str(Path.home() / '.newsletter_podcast' / 'gdrive_token.json')
        self.service = None
        self.creds = None
        
        # Create token directory if needed
        os.makedirs(os.path.dirname(self.token_path), exist_ok=True)
        
    def authenticate(self) -> bool:
        """
        Authenticate with Google Drive API.
        
        Returns:
            True if authentication successful
        """
        try:
            # Load existing token if available
            if os.path.exists(self.token_path):
                self.creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
                logger.info(f"Loaded credentials from {self.token_path}")
                
            # If no valid credentials, get new ones
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    logger.info("Refreshing expired credentials")
                    self.creds.refresh(Request())
                else:
                    if not os.path.exists(self.credentials_path):
                        logger.error(f"Credentials file not found: {self.credentials_path}")
                        return False
                        
                    logger.info("Starting OAuth2 flow for new credentials")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, SCOPES)
                    self.creds = flow.run_local_server(port=0)
                    
                # Save credentials for next time
                with open(self.token_path, 'w') as token:
                    token.write(self.creds.to_json())
                logger.info(f"Saved credentials to {self.token_path}")
                
            # Build the Drive service
            self.service = build('drive', 'v3', credentials=self.creds)
            logger.info("Successfully authenticated with Google Drive")
            return True
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False
            
    def upload_podcast(self,
                      file_path: str,
                      folder_id: Optional[str] = None,
                      custom_name: Optional[str] = None,
                      podcast_date: Optional[datetime] = None,
                      summary: Optional[str] = None) -> Optional[str]:
        """
        Upload podcast file to Google Drive.
        
        Args:
            file_path: Path to the podcast file
            folder_id: ID of the Drive folder to upload to (optional)
            custom_name: Custom name for the file (optional)
            podcast_date: Date for the podcast (default: today)
            summary: Short summary for the filename (optional)
            
        Returns:
            File ID of uploaded file or None if failed
        """
        if not self.service:
            if not self.authenticate():
                return None
                
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return None
            
        try:
            # Generate filename
            if custom_name:
                filename = custom_name
            else:
                date_str = (podcast_date or datetime.now()).strftime("%Y-%m-%d")
                if summary:
                    # Clean and truncate summary
                    clean_summary = "".join(c for c in summary if c.isalnum() or c in " -_").strip()
                    clean_summary = " ".join(clean_summary.split()[:6])  # Max 6 words
                    filename = f"{date_str} - {clean_summary}.mp3"
                else:
                    filename = f"{date_str} - Newsletter Podcast.mp3"
                    
            logger.info(f"Uploading {file_path} as {filename}")
            
            # Prepare file metadata
            file_metadata = {
                'name': filename,
                'mimeType': 'audio/mpeg'
            }
            
            # Add to specific folder if provided
            if folder_id:
                file_metadata['parents'] = [folder_id]
                logger.info(f"Uploading to folder: {folder_id}")
                
            # Create media upload
            media = MediaFileUpload(
                file_path,
                mimetype='audio/mpeg',
                resumable=True
            )
            
            # Upload the file
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,webViewLink'
            ).execute()
            
            file_id = file.get('id')
            file_name = file.get('name')
            web_link = file.get('webViewLink')
            
            logger.info(f"Successfully uploaded: {file_name}")
            logger.info(f"File ID: {file_id}")
            logger.info(f"Web Link: {web_link}")
            
            return file_id
            
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return None
            
    def create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> Optional[str]:
        """
        Create a folder in Google Drive.
        
        Args:
            folder_name: Name of the folder to create
            parent_id: ID of parent folder (optional)
            
        Returns:
            Folder ID or None if failed
        """
        if not self.service:
            if not self.authenticate():
                return None
                
        try:
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            if parent_id:
                file_metadata['parents'] = [parent_id]
                
            file = self.service.files().create(
                body=file_metadata,
                fields='id,name'
            ).execute()
            
            folder_id = file.get('id')
            logger.info(f"Created folder '{folder_name}' with ID: {folder_id}")
            return folder_id
            
        except Exception as e:
            logger.error(f"Failed to create folder: {e}")
            return None
            
    def list_folders(self, parent_id: Optional[str] = None) -> list:
        """
        List folders in Google Drive.
        
        Args:
            parent_id: ID of parent folder to list (optional)
            
        Returns:
            List of folder dictionaries with 'id' and 'name'
        """
        if not self.service:
            if not self.authenticate():
                return []
                
        try:
            query = "mimeType='application/vnd.google-apps.folder' and trashed=false"
            if parent_id:
                query += f" and '{parent_id}' in parents"
                
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)',
                orderBy='name'
            ).execute()
            
            folders = results.get('files', [])
            logger.info(f"Found {len(folders)} folders")
            return folders
            
        except Exception as e:
            logger.error(f"Failed to list folders: {e}")
            return []
            
    def share_file(self, file_id: str, email: str, role: str = 'reader') -> bool:
        """
        Share a file with a specific email address.
        
        Args:
            file_id: ID of the file to share
            email: Email address to share with
            role: Permission role ('reader', 'writer', 'owner')
            
        Returns:
            True if sharing successful
        """
        if not self.service:
            if not self.authenticate():
                return False
                
        try:
            permission = {
                'type': 'user',
                'role': role,
                'emailAddress': email
            }
            
            self.service.permissions().create(
                fileId=file_id,
                body=permission,
                fields='id'
            ).execute()
            
            logger.info(f"Shared file {file_id} with {email} as {role}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to share file: {e}")
            return False