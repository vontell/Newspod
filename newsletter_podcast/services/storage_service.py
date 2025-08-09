import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)


class StorageService:
    """Service for uploading and managing podcast audio files."""
    
    def __init__(self, storage_type: str = "local", config: Optional[Dict[str, Any]] = None):
        """
        Initialize storage service.
        
        Args:
            storage_type: Type of storage (local, s3, etc.)
            config: Storage configuration
        """
        self.storage_type = storage_type
        self.config = config or {}
        
    def upload_audio(self, 
                    file_path: str,
                    destination_name: Optional[str] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Upload audio file to storage.
        
        Args:
            file_path: Path to local audio file
            destination_name: Name for the uploaded file
            metadata: Additional metadata to store
            
        Returns:
            URL or path to uploaded file
        """
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return None
            
        if not destination_name:
            # Generate unique name based on date and content hash
            date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_hash = self._get_file_hash(file_path)[:8]
            extension = os.path.splitext(file_path)[1]
            destination_name = f"podcast_{date_str}_{file_hash}{extension}"
            
        if self.storage_type == "local":
            return self._upload_local(file_path, destination_name)
        elif self.storage_type == "s3":
            return self._upload_s3(file_path, destination_name, metadata)
        else:
            logger.error(f"Unsupported storage type: {self.storage_type}")
            return None
            
    def _upload_local(self, file_path: str, destination_name: str) -> Optional[str]:
        """Upload file to local storage."""
        try:
            upload_dir = self.config.get("upload_dir", "uploads")
            os.makedirs(upload_dir, exist_ok=True)
            
            destination = os.path.join(upload_dir, destination_name)
            
            # Copy file if not already in destination
            if os.path.abspath(file_path) != os.path.abspath(destination):
                import shutil
                shutil.copy2(file_path, destination)
                
            logger.info(f"File uploaded to {destination}")
            return destination
            
        except Exception as e:
            logger.error(f"Error uploading to local storage: {e}")
            return None
            
    def _upload_s3(self, file_path: str, destination_name: str, 
                   metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Upload file to AWS S3."""
        try:
            import boto3
            
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=self.config.get("aws_access_key_id"),
                aws_secret_access_key=self.config.get("aws_secret_access_key"),
                region_name=self.config.get("region", "us-east-1")
            )
            
            bucket_name = self.config.get("bucket_name")
            if not bucket_name:
                logger.error("S3 bucket name not configured")
                return None
                
            s3_key = f"{self.config.get('prefix', 'podcasts')}/{destination_name}"
            
            # Prepare upload arguments
            extra_args = {}
            if metadata:
                extra_args["Metadata"] = {str(k): str(v) for k, v in metadata.items()}
                
            # Upload file
            s3_client.upload_file(file_path, bucket_name, s3_key, ExtraArgs=extra_args)
            
            # Generate URL
            url = f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"
            logger.info(f"File uploaded to S3: {url}")
            return url
            
        except Exception as e:
            logger.error(f"Error uploading to S3: {e}")
            return None
            
    def _get_file_hash(self, file_path: str) -> str:
        """Generate hash of file contents."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            buf = f.read(65536)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(65536)
        return hasher.hexdigest()
        
    def generate_podcast_metadata(self, 
                                 script: str,
                                 audio_file: str,
                                 newsletters_count: int) -> Dict[str, Any]:
        """
        Generate metadata for the podcast episode.
        
        Args:
            script: The podcast script
            audio_file: Path to audio file
            newsletters_count: Number of newsletters summarized
            
        Returns:
            Metadata dictionary
        """
        file_size = os.path.getsize(audio_file) if os.path.exists(audio_file) else 0
        word_count = len(script.split())
        estimated_duration = word_count / 150  # Assuming 150 WPM
        
        return {
            "title": f"Newsletter Roundup - {datetime.now().strftime('%B %d, %Y')}",
            "date": datetime.now().isoformat(),
            "newsletters_count": newsletters_count,
            "word_count": word_count,
            "estimated_duration_minutes": round(estimated_duration, 1),
            "file_size_bytes": file_size,
            "file_hash": self._get_file_hash(audio_file) if os.path.exists(audio_file) else None,
            "script_preview": script[:200] + "..." if len(script) > 200 else script
        }