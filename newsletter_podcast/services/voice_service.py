import requests
import logging
from typing import Optional, Dict, Any, List
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class VoiceService:
    """Service for converting text to speech using ElevenLabs API."""
    
    def __init__(self, api_key: str, voice_id: Optional[str] = None):
        """
        Initialize ElevenLabs service.
        
        Args:
            api_key: ElevenLabs API key
            voice_id: ID of the voice to use (optional, will use default if not provided)
        """
        self.api_key = api_key
        self.base_url = "https://api.elevenlabs.io/v1"
        self.headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key
        }
        self.voice_id = voice_id
        
    def get_available_voices(self) -> List[Dict[str, Any]]:
        """Get list of available voices."""
        url = f"{self.base_url}/voices"
        headers = {
            "Accept": "application/json",
            "xi-api-key": self.api_key
        }
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json().get("voices", [])
        except Exception as e:
            logger.error(f"Error fetching voices: {e}")
            return []
            
    def set_voice_by_name(self, name: str) -> bool:
        """Set voice by name instead of ID."""
        voices = self.get_available_voices()
        
        for voice in voices:
            if voice.get("name", "").lower() == name.lower():
                self.voice_id = voice.get("voice_id")
                logger.info(f"Set voice to {name} (ID: {self.voice_id})")
                return True
                
        logger.warning(f"Voice '{name}' not found")
        return False
        
    def text_to_speech(self, 
                      text: str,
                      output_path: Optional[str] = None,
                      model_id: str = "eleven_monolingual_v1",
                      stability: float = 0.5,
                      similarity_boost: float = 0.5) -> Optional[str]:
        """
        Convert text to speech using ElevenLabs API.
        
        Args:
            text: Text to convert to speech
            output_path: Path to save audio file (optional)
            model_id: ElevenLabs model ID
            stability: Voice stability (0-1)
            similarity_boost: Voice similarity boost (0-1)
            
        Returns:
            Path to saved audio file or None if failed
        """
        if not self.voice_id:
            # Try to get default voice
            voices = self.get_available_voices()
            if voices:
                self.voice_id = voices[0]["voice_id"]
                logger.info(f"Using default voice: {voices[0]['name']}")
            else:
                logger.error("No voice ID provided and couldn't fetch default")
                return None
                
        url = f"{self.base_url}/text-to-speech/{self.voice_id}"
        
        data = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost
            }
        }
        
        try:
            logger.info(f"Generating audio for {len(text.split())} words...")
            response = requests.post(url, json=data, headers=self.headers)
            response.raise_for_status()
            
            # Determine output path
            if not output_path:
                output_path = f"podcast_{Path.cwd().name}_{os.getpid()}.mp3"
                
            # Save audio file
            with open(output_path, "wb") as f:
                f.write(response.content)
                
            logger.info(f"Audio saved to {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error generating audio: {e}")
            return None
            
    def text_to_speech_stream(self, 
                            text: str,
                            chunk_size: int = 1024) -> Optional[bytes]:
        """
        Convert text to speech and return audio data as bytes (for streaming).
        
        Args:
            text: Text to convert
            chunk_size: Size of chunks for streaming
            
        Returns:
            Audio data as bytes or None if failed
        """
        if not self.voice_id:
            logger.error("No voice ID configured")
            return None
            
        url = f"{self.base_url}/text-to-speech/{self.voice_id}/stream"
        
        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }
        
        headers = self.headers.copy()
        headers["Accept"] = "audio/mpeg"
        
        try:
            response = requests.post(url, json=data, headers=headers, stream=True)
            response.raise_for_status()
            
            # Collect all chunks
            audio_data = b""
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    audio_data += chunk
                    
            return audio_data
            
        except Exception as e:
            logger.error(f"Error in streaming audio: {e}")
            return None
            
    def generate_podcast_with_segments(self,
                                     segments: List[Dict[str, str]],
                                     output_dir: str = "podcast_segments",
                                     combine: bool = True) -> List[str]:
        """
        Generate audio for multiple podcast segments.
        
        Args:
            segments: List of segment scripts
            output_dir: Directory to save audio files
            combine: Whether to combine segments into one file
            
        Returns:
            List of paths to audio files
        """
        os.makedirs(output_dir, exist_ok=True)
        audio_files = []
        
        for i, segment in enumerate(segments):
            output_path = os.path.join(output_dir, f"segment_{i+1}.mp3")
            result = self.text_to_speech(segment["script"], output_path)
            
            if result:
                audio_files.append(result)
            else:
                logger.warning(f"Failed to generate audio for segment {i+1}")
                
        if combine and audio_files and len(audio_files) > 1:
            # Combine audio files (requires ffmpeg)
            combined_path = os.path.join(output_dir, "complete_podcast.mp3")
            if self._combine_audio_files(audio_files, combined_path):
                return [combined_path]
                
        return audio_files
        
    def _combine_audio_files(self, input_files: List[str], output_file: str) -> bool:
        """
        Combine multiple audio files using ffmpeg.
        
        Args:
            input_files: List of audio file paths
            output_file: Output file path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            import subprocess
            
            # Create a file list for ffmpeg
            list_file = "filelist.txt"
            with open(list_file, "w") as f:
                for file in input_files:
                    f.write(f"file '{file}'\n")
                    
            # Run ffmpeg to concatenate
            cmd = ["ffmpeg", "-f", "concat", "-safe", "0", "-i", list_file, 
                   "-c", "copy", "-y", output_file]
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Clean up
            os.remove(list_file)
            
            logger.info(f"Combined audio saved to {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error combining audio files: {e}")
            return False