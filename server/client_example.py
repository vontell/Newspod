#!/usr/bin/env python3
"""
Example client for Newspod Server
Demonstrates how to authenticate and interact with the server API
"""

import requests
import json
from typing import Optional, Dict, Any


class NewspodClient:
    """Client for interacting with Newspod Server"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.token: Optional[str] = None
        self.session = requests.Session()

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with authorization token"""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def signup(self, email: str, password: str, full_name: Optional[str] = None) -> Dict[str, Any]:
        """Register a new user"""
        data = {
            "email": email,
            "password": password
        }
        if full_name:
            data["full_name"] = full_name

        response = self.session.post(
            f"{self.base_url}/auth/signup",
            json=data,
            headers=self._get_headers()
        )
        response.raise_for_status()

        result = response.json()
        if result.get("session", {}).get("access_token"):
            self.token = result["session"]["access_token"]

        return result

    def signin(self, email: str, password: str) -> Dict[str, Any]:
        """Sign in user"""
        data = {
            "email": email,
            "password": password
        }

        response = self.session.post(
            f"{self.base_url}/auth/signin",
            json=data,
            headers=self._get_headers()
        )
        response.raise_for_status()

        result = response.json()
        if result.get("session", {}).get("access_token"):
            self.token = result["session"]["access_token"]

        return result

    def get_profile(self) -> Dict[str, Any]:
        """Get user profile"""
        response = self.session.get(
            f"{self.base_url}/user/profile",
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    def get_config(self) -> Dict[str, Any]:
        """Get user configuration"""
        response = self.session.get(
            f"{self.base_url}/user/config",
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    def update_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Update user configuration"""
        response = self.session.post(
            f"{self.base_url}/user/config",
            json=config,
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    def generate_podcast(
        self,
        hours_lookback: int = 24,
        target_duration_minutes: int = 10,
        newsletter_filters: Optional[list] = None
    ) -> Dict[str, Any]:
        """Manually trigger podcast generation"""
        data = {
            "hours_lookback": hours_lookback,
            "target_duration_minutes": target_duration_minutes
        }
        if newsletter_filters:
            data["newsletter_filters"] = newsletter_filters

        response = self.session.post(
            f"{self.base_url}/podcast/generate",
            json=data,
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    def get_history(self, limit: int = 10) -> Dict[str, Any]:
        """Get podcast generation history"""
        response = self.session.get(
            f"{self.base_url}/podcast/history?limit={limit}",
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()


def main():
    """Example usage of the Newspod client"""
    client = NewspodClient()

    print("=== Newspod Client Example ===")

    # Example configuration
    example_config = {
        "emails": [
            {
                "address": "your.email@gmail.com",
                "password": "your-app-password",
                "imap_server": "imap.gmail.com"
            }
        ],
        "claude_api_key": "your-claude-api-key",
        "elevenlabs_api_key": "your-elevenlabs-api-key",
        "elevenlabs_voice_id": None,
        "google_drive_enabled": False,
        "personalization": {
            "user_name": "John",
            "user_role": "Software Engineer",
            "interests": ["AI", "Technology", "Programming"],
            "filter_mode": "smart"
        },
        "schedule_time": "08:00",
        "timezone": "UTC"
    }

    try:
        # Sign in (you'll need to register first)
        email = input("Email: ")
        password = input("Password: ")

        signin_result = client.signin(email, password)
        print(f"✅ Signed in successfully")

        # Get profile
        profile = client.get_profile()
        print(f"👤 User: {profile['user']['email']}")

        # Update configuration
        print("📝 Updating configuration...")
        config_result = client.update_config(example_config)
        print(f"✅ Configuration updated")

        # Generate podcast
        print("🎙️ Generating podcast...")
        generation_result = client.generate_podcast(
            hours_lookback=24,
            target_duration_minutes=5
        )
        print(f"✅ Podcast generation triggered")
        print(f"📊 Result: {generation_result['result']['success']}")

        # Get history
        history = client.get_history(limit=5)
        print(f"📚 Recent generations: {len(history['history'])}")

    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        print(f"Response: {e.response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()