import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import json
import os

from .services.email_service import EmailService, Newsletter
from .services.summarization_service import SummarizationService
from .services.voice_service import VoiceService
from .services.storage_service import StorageService
from .services.newsletter_filter import NewsletterFilter
from .services.drive_service import DriveService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NewsletterPodcastGenerator:
    """Main orchestrator for generating podcasts from newsletters."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize podcast generator with configuration.
        
        Args:
            config: Configuration dictionary with service credentials
        """
        self.config = config
        
        # Initialize email services for each account
        self.email_services = []
        
        # Support both old single email format and new multiple emails format
        if "emails" in config:
            # New format: multiple emails
            for email_config in config["emails"]:
                service = EmailService(
                    email_address=email_config["address"],
                    password=email_config["password"],
                    imap_server=email_config.get("imap_server", "imap.gmail.com")
                )
                self.email_services.append(service)
        elif "email" in config:
            # Old format: single email (backward compatibility)
            service = EmailService(
                email_address=config["email"]["address"],
                password=config["email"]["password"],
                imap_server=config["email"].get("imap_server", "imap.gmail.com")
            )
            self.email_services.append(service)
        else:
            raise ValueError("No email configuration found")
            
        logger.info(f"Configured {len(self.email_services)} email account(s)")
        
        # Initialize other services
        self.summarization_service = SummarizationService(
            api_key=config["claude"]["api_key"],
            model=config["claude"].get("model", "claude-3-opus-20240229")
        )
        
        self.voice_service = VoiceService(
            api_key=config["elevenlabs"]["api_key"],
            voice_id=config["elevenlabs"].get("voice_id")
        )
        
        self.storage_service = StorageService(
            storage_type=config.get("storage", {}).get("type", "local"),
            config=config.get("storage", {})
        )
        
        # Initialize newsletter filter if smart filtering is enabled
        self.personalization = config.get("personalization", {})
        if self.personalization.get("filter_mode") == "smart":
            self.newsletter_filter = NewsletterFilter(
                api_key=config["claude"]["api_key"],
                model=config["claude"].get("filter_model", "claude-3-haiku-20240307")
            )
        else:
            self.newsletter_filter = None
            
        # Initialize Google Drive service if enabled
        gdrive_config = config.get("google_drive", {})
        if gdrive_config.get("enabled", False):
            self.drive_service = DriveService(
                credentials_path=gdrive_config.get("credentials_path")
            )
            self.drive_folder_id = gdrive_config.get("folder_id")
        else:
            self.drive_service = None
            self.drive_folder_id = None
        
    def generate_podcast(self,
                        hours_lookback: int = 24,
                        target_duration_minutes: int = 10,
                        newsletter_filters: Optional[List[str]] = None,
                        output_dir: str = "output",
                        quick_mode: bool = False) -> Dict[str, Any]:
        """
        Generate a complete podcast from newsletters.
        
        Args:
            hours_lookback: How many hours to look back for newsletters
            target_duration_minutes: Target podcast duration
            newsletter_filters: Optional filters for newsletter selection
            output_dir: Directory for output files
            quick_mode: Use cached emails and generate shorter script (25%)
            
        Returns:
            Dictionary with podcast generation results
        """
        os.makedirs(output_dir, exist_ok=True)
        
        result = {
            "success": False,
            "start_time": datetime.now().isoformat(),
            "newsletters_found": 0,
            "script_path": None,
            "audio_path": None,
            "uploaded_url": None,
            "errors": []
        }
        
        try:
            # Step 1: Fetch newsletters from all accounts
            if quick_mode:
                logger.info("QUICK MODE: Using cached newsletters if available...")
                target_duration_minutes = max(2, int(target_duration_minutes * 0.25))  # 25% duration
                logger.info(f"Target duration reduced to {target_duration_minutes} minutes")
                
            logger.info(f"Fetching newsletters from {len(self.email_services)} account(s)...")
            all_newsletters = []
            
            # Fetch from each email account
            for i, email_service in enumerate(self.email_services, 1):
                try:
                    logger.info(f"Fetching from account {i}/{len(self.email_services)}: {email_service.email_address}")
                    
                    # Use simple filters if smart filtering is enabled (will refine later)
                    # Otherwise use provided filters
                    if self.newsletter_filter and not newsletter_filters:
                        simple_filters = self.newsletter_filter.get_simple_filters(
                            user_role=self.personalization.get("user_role", "professional"),
                            interests=self.personalization.get("interests", [])
                        )
                    else:
                        simple_filters = newsletter_filters
                        
                    account_newsletters = email_service.fetch_newsletters(
                        hours_lookback=hours_lookback,
                        newsletter_filters=simple_filters,
                        use_cache=quick_mode,
                        cache_dir=os.path.join(output_dir, ".cache")
                    )
                    all_newsletters.extend(account_newsletters)
                    logger.info(f"Found {len(account_newsletters)} newsletters from {email_service.email_address}")
                    
                except Exception as e:
                    logger.error(f"Error fetching from {email_service.email_address}: {e}")
                    result["errors"].append(f"Failed to fetch from {email_service.email_address}: {str(e)}")
                    
            newsletters = all_newsletters
            logger.info(f"Total newsletters fetched: {len(newsletters)}")
            
            # Step 1.5: Apply smart filtering if enabled
            if self.newsletter_filter and self.personalization.get("filter_mode") == "smart":
                logger.info("Applying smart newsletter filtering...")
                
                filtered_results = self.newsletter_filter.filter_newsletters_parallel(
                    newsletters=newsletters,
                    user_name=self.personalization.get("user_name", "User"),
                    user_role=self.personalization.get("user_role", "professional"),
                    interests=self.personalization.get("interests", []),
                    max_workers=10
                )
                
                # Extract just the newsletters from the results
                newsletters = [newsletter for newsletter, result in filtered_results]
                
                # Save filtering results for debugging
                filter_results_path = os.path.join(output_dir, f"filter_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
                filter_data = [
                    {
                        "subject": newsletter.subject,
                        "source": newsletter.newsletter_source,
                        "relevance_score": result.relevance_score,
                        "reason": result.reason,
                        "topics": result.topics
                    }
                    for newsletter, result in filtered_results
                ]
                with open(filter_results_path, "w") as f:
                    json.dump(filter_data, f, indent=2)
                logger.info(f"Filter results saved to {filter_results_path}")
                
                logger.info(f"Smart filtering: {len(all_newsletters)} → {len(newsletters)} newsletters")
            
            result["newsletters_found"] = len(newsletters)
            
            if not newsletters:
                logger.warning("No newsletters found")
                result["errors"].append("No newsletters found in the specified time period")
                return result
                
            # Save newsletter metadata
            self._save_newsletter_metadata(newsletters, output_dir)
            
            # Step 2: Generate podcast script
            logger.info(f"Generating script from {len(newsletters)} newsletters...")
            
            # Get personalization settings from config or use defaults
            user_name = self.config.get("personalization", {}).get("user_name", "Aaron")
            user_role = self.config.get("personalization", {}).get("user_role", "AI engineer at Anthropic")
            
            script = self.summarization_service.summarize_newsletters(
                newsletters=newsletters,
                target_duration_minutes=target_duration_minutes,
                user_name=user_name,
                user_role=user_role
            )
            
            # Save script
            script_path = os.path.join(output_dir, f"podcast_script_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
            with open(script_path, "w") as f:
                f.write(script)
            result["script_path"] = script_path
            
            logger.info(f"Script saved to {script_path}")
            
            # Step 3: Generate audio
            logger.info("Generating audio...")
            audio_filename = f"podcast_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
            audio_path = os.path.join(output_dir, audio_filename)
            
            generated_audio = self.voice_service.text_to_speech(
                text=script,
                output_path=audio_path
            )
            
            if not generated_audio:
                result["errors"].append("Failed to generate audio")
                return result
                
            result["audio_path"] = generated_audio
            
            # Step 4: Upload audio to local storage
            logger.info("Uploading audio to local storage...")
            metadata = self.storage_service.generate_podcast_metadata(
                script=script,
                audio_file=generated_audio,
                newsletters_count=len(newsletters)
            )
            
            uploaded_url = self.storage_service.upload_audio(
                file_path=generated_audio,
                metadata=metadata
            )
            
            if uploaded_url:
                result["uploaded_url"] = uploaded_url
                result["success"] = True
                
                # Save metadata
                metadata_path = os.path.join(output_dir, f"podcast_metadata_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
                metadata["audio_url"] = uploaded_url
                with open(metadata_path, "w") as f:
                    json.dump(metadata, f, indent=2)
                result["metadata_path"] = metadata_path
            else:
                result["errors"].append("Failed to upload audio to local storage")
                
            # Step 5: Upload to Google Drive if enabled
            if self.drive_service and result["success"]:
                logger.info("Uploading to Google Drive...")
                
                # Generate a concise title
                podcast_title = self.summarization_service.generate_podcast_title(newsletters)
                logger.info(f"Generated title: {podcast_title}")
                
                # Upload to Drive
                drive_file_id = self.drive_service.upload_podcast(
                    file_path=generated_audio,
                    folder_id=self.drive_folder_id,
                    podcast_date=datetime.now(),
                    summary=podcast_title
                )
                
                if drive_file_id:
                    result["google_drive_id"] = drive_file_id
                    result["google_drive_link"] = f"https://drive.google.com/file/d/{drive_file_id}/view"
                    logger.info(f"Successfully uploaded to Google Drive: {result['google_drive_link']}")
                    
                    # Update metadata
                    metadata["google_drive_id"] = drive_file_id
                    metadata["google_drive_link"] = result["google_drive_link"]
                    metadata["podcast_title"] = podcast_title
                    with open(metadata_path, "w") as f:
                        json.dump(metadata, f, indent=2)
                else:
                    result["errors"].append("Failed to upload to Google Drive")
                    logger.warning("Google Drive upload failed, but local upload succeeded")
                
        except Exception as e:
            logger.error(f"Error generating podcast: {e}")
            result["errors"].append(str(e))
            
        finally:
            result["end_time"] = datetime.now().isoformat()
            # Disconnect all email services
            for email_service in self.email_services:
                try:
                    email_service.disconnect()
                except:
                    pass
            
        return result
        
    def generate_segmented_podcast(self,
                                  hours_lookback: int = 24,
                                  segment_duration_minutes: int = 2,
                                  newsletter_filters: Optional[List[str]] = None,
                                  output_dir: str = "output") -> Dict[str, Any]:
        """
        Generate a podcast with individual segments for each newsletter.
        
        Args:
            hours_lookback: How many hours to look back
            segment_duration_minutes: Duration of each segment
            newsletter_filters: Optional newsletter filters
            output_dir: Output directory
            
        Returns:
            Generation results
        """
        os.makedirs(output_dir, exist_ok=True)
        segments_dir = os.path.join(output_dir, "segments")
        os.makedirs(segments_dir, exist_ok=True)
        
        result = {
            "success": False,
            "newsletters_found": 0,
            "segments": [],
            "errors": []
        }
        
        try:
            # Fetch newsletters
            newsletters = self.email_service.fetch_newsletters(
                hours_lookback=hours_lookback,
                newsletter_filters=newsletter_filters
            )
            
            result["newsletters_found"] = len(newsletters)
            
            if not newsletters:
                result["errors"].append("No newsletters found")
                return result
                
            # Generate segments
            logger.info(f"Generating {len(newsletters)} segments...")
            segments = self.summarization_service.generate_podcast_segments(
                newsletters=newsletters,
                segment_duration_minutes=segment_duration_minutes
            )
            
            # Generate audio for each segment
            audio_files = self.voice_service.generate_podcast_with_segments(
                segments=segments,
                output_dir=segments_dir,
                combine=True
            )
            
            result["segments"] = segments
            result["audio_files"] = audio_files
            
            # Upload combined podcast if available
            if audio_files and os.path.exists(audio_files[0]):
                uploaded_url = self.storage_service.upload_audio(audio_files[0])
                result["uploaded_url"] = uploaded_url
                result["success"] = True
                
        except Exception as e:
            logger.error(f"Error in segmented generation: {e}")
            result["errors"].append(str(e))
            
        finally:
            # Disconnect all email services
            for email_service in self.email_services:
                try:
                    email_service.disconnect()
                except:
                    pass
            
        return result
        
    def _save_newsletter_metadata(self, newsletters: List[Newsletter], output_dir: str):
        """Save newsletter metadata to JSON file."""
        metadata = []
        
        for newsletter in newsletters:
            metadata.append({
                "subject": newsletter.subject,
                "sender": newsletter.sender,
                "date": newsletter.date.isoformat(),
                "source": newsletter.newsletter_source,
                "preview": newsletter.body[:200] + "..." if len(newsletter.body) > 200 else newsletter.body
            })
            
        metadata_path = os.path.join(output_dir, f"newsletters_metadata_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
            
        logger.info(f"Newsletter metadata saved to {metadata_path}")