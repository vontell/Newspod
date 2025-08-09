import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
from dataclasses import dataclass
import json
import os
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class Newsletter:
    """Data class representing a newsletter email."""
    subject: str
    sender: str
    date: datetime
    body: str
    html_body: Optional[str] = None
    newsletter_source: Optional[str] = None


class EmailService:
    """Service for fetching and processing newsletter emails."""
    
    def __init__(self, email_address: str, password: str, 
                 imap_server: str = "imap.gmail.com", 
                 imap_port: int = 993):
        """
        Initialize email service with credentials.
        
        Args:
            email_address: Email address to fetch newsletters from
            password: Email password or app-specific password
            imap_server: IMAP server address
            imap_port: IMAP server port
        """
        self.email_address = email_address
        self.password = password
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.connection = None
        
    def connect(self) -> bool:
        """Establish connection to email server."""
        try:
            self.connection = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self.connection.login(self.email_address, self.password)
            logger.info(f"Successfully connected to {self.imap_server}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to email server: {e}")
            return False
            
    def disconnect(self):
        """Close connection to email server."""
        if self.connection:
            try:
                self.connection.close()
                self.connection.logout()
            except:
                pass
                
    def fetch_newsletters(self, 
                         hours_lookback: int = 24,
                         folder: str = "INBOX",
                         newsletter_filters: Optional[List[str]] = None,
                         use_cache: bool = False,
                         cache_dir: str = ".cache") -> List[Newsletter]:
        """
        Fetch newsletters from the past N hours.
        
        Args:
            hours_lookback: How many hours to look back
            folder: Email folder to search
            newsletter_filters: List of sender addresses or subject keywords to filter
            use_cache: Whether to use cached results if available
            cache_dir: Directory to store cache files
            
        Returns:
            List of Newsletter objects
        """
        # Generate cache key based on parameters
        cache_key = self._generate_cache_key(hours_lookback, folder, newsletter_filters)
        cache_path = os.path.join(cache_dir, f"newsletters_{cache_key}.json")
        
        # Check cache if enabled
        if use_cache and os.path.exists(cache_path):
            try:
                cache_time = datetime.fromtimestamp(os.path.getmtime(cache_path))
                cache_age = datetime.now() - cache_time
                
                # Use cache if less than 1 hour old
                if cache_age.total_seconds() < 3600:
                    logger.info(f"Using cached newsletters from {cache_path}")
                    return self._load_cached_newsletters(cache_path)
                else:
                    logger.info("Cache expired, fetching fresh newsletters")
            except Exception as e:
                logger.warning(f"Error reading cache: {e}")
        
        # Fetch fresh newsletters if not using cache or cache miss
        if not self.connection:
            if not self.connect():
                return []
                
        try:
            self.connection.select(folder)
            
            # Calculate date for search
            since_date = (datetime.now() - timedelta(hours=hours_lookback)).strftime("%d-%b-%Y")
            
            # Build search criteria
            search_criteria = f'(SINCE "{since_date}")'
            
            # Search for emails
            _, data = self.connection.search(None, search_criteria)
            email_ids = data[0].split()
            
            newsletters = []
            
            for email_id in email_ids:
                _, data = self.connection.fetch(email_id, "(RFC822)")
                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                # Extract email details
                subject = self._decode_header(msg["Subject"])
                sender = self._decode_header(msg["From"])
                date = self._parse_date(msg["Date"])
                
                # Check if this is a newsletter based on filters
                if newsletter_filters and not self._is_newsletter(subject, sender, newsletter_filters):
                    continue
                    
                # Extract body
                body, html_body = self._extract_body(msg)
                
                newsletter = Newsletter(
                    subject=subject,
                    sender=sender,
                    date=date,
                    body=body,
                    html_body=html_body,
                    newsletter_source=self._identify_newsletter_source(sender)
                )
                
                newsletters.append(newsletter)
                
            logger.info(f"Fetched {len(newsletters)} newsletters")
            
            # Save to cache if enabled
            if use_cache:
                self._save_newsletters_to_cache(newsletters, cache_path)
                
            return newsletters
            
        except Exception as e:
            logger.error(f"Error fetching newsletters: {e}")
            return []
            
    def _decode_header(self, header: str) -> str:
        """Decode email header handling various encodings."""
        if not header:
            return ""
            
        decoded_parts = decode_header(header)
        result = ""
        
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                result += part.decode(encoding or "utf-8", errors="ignore")
            else:
                result += part
                
        return result
        
    def _parse_date(self, date_str: str) -> datetime:
        """Parse email date string to datetime object."""
        from email.utils import parsedate_to_datetime
        try:
            return parsedate_to_datetime(date_str)
        except:
            return datetime.now()
            
    def _extract_body(self, msg) -> tuple:
        """Extract plain text and HTML body from email message."""
        plain_body = ""
        html_body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                if "attachment" not in content_disposition:
                    if content_type == "text/plain":
                        plain_body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                    elif content_type == "text/html":
                        html_body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
        else:
            plain_body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
            
        return plain_body, html_body
        
    def _is_newsletter(self, subject: str, sender: str, filters: List[str]) -> bool:
        """Check if email matches newsletter filters."""
        combined = f"{subject} {sender}".lower()
        return any(f.lower() in combined for f in filters)
        
    def _identify_newsletter_source(self, sender: str) -> str:
        """Try to identify the newsletter source from sender."""
        # Extract domain or organization name
        if "@" in sender:
            domain = sender.split("@")[1].split(">")[0]
            return domain.split(".")[0].capitalize()
        return "Unknown"
        
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
        
    def _generate_cache_key(self, hours_lookback: int, folder: str, 
                          newsletter_filters: Optional[List[str]]) -> str:
        """Generate a unique cache key based on fetch parameters."""
        key_data = {
            "email": self.email_address,
            "hours": hours_lookback,
            "folder": folder,
            "filters": sorted(newsletter_filters) if newsletter_filters else []
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()[:12]
        
    def _save_newsletters_to_cache(self, newsletters: List[Newsletter], cache_path: str):
        """Save newsletters to cache file."""
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            
            cache_data = []
            for newsletter in newsletters:
                cache_data.append({
                    "subject": newsletter.subject,
                    "sender": newsletter.sender,
                    "date": newsletter.date.isoformat(),
                    "body": newsletter.body,
                    "html_body": newsletter.html_body,
                    "newsletter_source": newsletter.newsletter_source
                })
                
            with open(cache_path, "w") as f:
                json.dump(cache_data, f, indent=2)
                
            logger.info(f"Cached {len(newsletters)} newsletters to {cache_path}")
            
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")
            
    def _load_cached_newsletters(self, cache_path: str) -> List[Newsletter]:
        """Load newsletters from cache file."""
        with open(cache_path, "r") as f:
            cache_data = json.load(f)
            
        newsletters = []
        for item in cache_data:
            newsletter = Newsletter(
                subject=item["subject"],
                sender=item["sender"],
                date=datetime.fromisoformat(item["date"]),
                body=item["body"],
                html_body=item.get("html_body"),
                newsletter_source=item.get("newsletter_source")
            )
            newsletters.append(newsletter)
            
        return newsletters