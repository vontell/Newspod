import anthropic
from typing import List, Dict, Optional
import logging
from datetime import datetime
import json

from ..services.email_service import Newsletter

logger = logging.getLogger(__name__)


class SummarizationService:
    """Service for summarizing newsletters and generating podcast scripts using Claude."""
    
    def __init__(self, api_key: str, model: str = "claude-3-opus-20240229"):
        """
        Initialize Claude API service.
        
        Args:
            api_key: Anthropic API key
            model: Claude model to use
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        
    def summarize_newsletters(self, 
                            newsletters: List[Newsletter],
                            target_duration_minutes: int = 10,
                            words_per_minute: int = 150,
                            user_name: str = "Aaron",
                            user_role: str = "AI engineer at Anthropic") -> str:
        """
        Summarize multiple newsletters into a cohesive podcast script.
        
        Args:
            newsletters: List of Newsletter objects to summarize
            target_duration_minutes: Target duration for the podcast
            words_per_minute: Average speaking rate
            user_name: Name of the listener for personalization
            user_role: Professional role/context of the listener
            
        Returns:
            Formatted podcast script
        """
        if not newsletters:
            return "No newsletters found to summarize."
            
        target_word_count = target_duration_minutes * words_per_minute
        
        # Prepare newsletter content for Claude
        newsletter_content = self._format_newsletters_for_prompt(newsletters)
        
        # Create source list for reference
        sources = ", ".join(set(n.newsletter_source or n.sender for n in newsletters))
        
        # Create summarization prompt
        prompt = f"""You are creating a personalized podcast script for {user_name}, an {user_role}, summarizing today's newsletters. 
        
Here are {len(newsletters)} newsletters from the past 24 hours:

{newsletter_content}

Newsletter sources include: {sources}

Please create an engaging, personalized podcast script that:

PERSONALIZATION:
- Address {user_name} directly in a conversational way
- Tailor insights specifically for an {user_role}
- Highlight AI/ML developments, engineering insights, and industry trends relevant to Anthropic
- Connect topics to potential implications for AI safety, LLMs, and frontier AI research when relevant

CONTENT STRUCTURE:
1. Start with "Hey {user_name}," or similar personal greeting
2. Prioritize the MOST IMPORTANT and BREAKING news first (especially AI/tech developments)
3. Group related topics together, even if from different newsletters
4. ALWAYS mention which newsletter(s) each topic comes from (e.g., "According to Axios and The Information..." or "From AI Weekly's latest issue...")
5. When multiple sources cover the same topic, cite all sources briefly

DELIVERY:
- Natural, conversational tone - like a knowledgeable colleague briefing {user_name}
- Approximately {target_word_count} words ({target_duration_minutes} minutes at {words_per_minute} WPM)
- Include smooth transitions between topics
- End with a personalized closing and preview of what to watch for
- Use clear, simple language that's easy to understand when spoken
- Spell out abbreviations on first use
- Add brief context for why each topic matters to someone in AI

EXAMPLE SOURCE ATTRIBUTION:
"Both TechCrunch and Stratechery are reporting on the new model release..."
"The AI Newsletter highlights an interesting development..."
"According to Axios, and also covered in Protocol..."

Format the script with clear paragraph breaks for natural speech pauses."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            script = response.content[0].text
            logger.info(f"Generated script of approximately {len(script.split())} words")
            return script
            
        except Exception as e:
            logger.error(f"Error generating script: {e}")
            return f"Error generating podcast script: {str(e)}"
            
    def summarize_single_newsletter(self, newsletter: Newsletter) -> Dict[str, str]:
        """
        Create a detailed summary of a single newsletter.
        
        Args:
            newsletter: Newsletter object to summarize
            
        Returns:
            Dictionary with summary components
        """
        prompt = f"""Analyze this newsletter and provide a structured summary:

Subject: {newsletter.subject}
From: {newsletter.sender}
Date: {newsletter.date.strftime("%Y-%m-%d %H:%M")}

Content:
{newsletter.body[:5000]}  # Truncate very long newsletters

Please provide:
1. A one-sentence summary of the main topic
2. 3-5 key takeaways (bullet points)
3. Any important dates, numbers, or statistics mentioned
4. A 2-3 sentence detailed summary

Format as JSON with keys: "main_topic", "key_takeaways", "important_data", "detailed_summary"
"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Try to parse as JSON, fallback to text if it fails
            result_text = response.content[0].text
            try:
                return json.loads(result_text)
            except json.JSONDecodeError:
                return {"detailed_summary": result_text}
                
        except Exception as e:
            logger.error(f"Error summarizing newsletter: {e}")
            return {"error": str(e)}
            
    def generate_podcast_segments(self, 
                                newsletters: List[Newsletter],
                                segment_duration_minutes: int = 2) -> List[Dict[str, str]]:
        """
        Generate individual podcast segments for each newsletter.
        
        Args:
            newsletters: List of Newsletter objects
            segment_duration_minutes: Target duration for each segment
            
        Returns:
            List of segment scripts
        """
        segments = []
        words_per_segment = segment_duration_minutes * 150
        
        for i, newsletter in enumerate(newsletters):
            prompt = f"""Create a {segment_duration_minutes}-minute podcast segment about this newsletter:

Subject: {newsletter.subject}
From: {newsletter.newsletter_source or newsletter.sender}
Content: {newsletter.body[:3000]}

Create an engaging, conversational script of approximately {words_per_segment} words that:
1. Introduces the newsletter source
2. Explains the main topic
3. Highlights the most interesting insights
4. Ends with a smooth transition to the next segment

This is segment {i+1} of {len(newsletters)}."""

            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=1000,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                segments.append({
                    "newsletter_source": newsletter.newsletter_source or "Unknown",
                    "subject": newsletter.subject,
                    "script": response.content[0].text
                })
                
            except Exception as e:
                logger.error(f"Error generating segment for {newsletter.subject}: {e}")
                segments.append({
                    "newsletter_source": newsletter.newsletter_source or "Unknown",
                    "subject": newsletter.subject,
                    "script": f"Error generating segment: {str(e)}"
                })
                
        return segments
        
    def _format_newsletters_for_prompt(self, newsletters: List[Newsletter]) -> str:
        """Format newsletters for inclusion in prompt."""
        formatted = []
        
        for i, newsletter in enumerate(newsletters, 1):
            formatted.append(f"""
Newsletter {i}:
Source: {newsletter.newsletter_source or newsletter.sender}
Subject: {newsletter.subject}
Date: {newsletter.date.strftime("%Y-%m-%d %H:%M")}
---
{newsletter.body[:3000]}  # Truncate to avoid token limits
---
""")
            
        return "\n".join(formatted)
    
    def generate_podcast_title(self, newsletters: List[Newsletter], max_words: int = 6) -> str:
        """
        Generate a concise title summarizing the podcast content.
        
        Args:
            newsletters: List of newsletters being summarized
            max_words: Maximum words in the title
            
        Returns:
            Short descriptive title
        """
        if not newsletters:
            return "Newsletter Roundup"
            
        # Prepare newsletter summaries
        newsletter_summaries = []
        for n in newsletters[:5]:  # Limit to avoid token issues
            newsletter_summaries.append(f"- {n.subject} (from {n.newsletter_source or n.sender})")
            
        prompt = f"""Generate a concise, descriptive title (max {max_words} words) summarizing these newsletters:

{chr(10).join(newsletter_summaries)}

The title should:
- Capture the most important/common theme
- Be specific and informative
- Use clear, simple language
- Be suitable for a filename (no special characters)

Return ONLY the title, nothing else."""

        try:
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",  # Use fast model for title
                max_tokens=50,
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            
            title = response.content[0].text.strip()
            # Clean for filename use
            title = "".join(c for c in title if c.isalnum() or c in " -_").strip()
            words = title.split()
            
            if len(words) > max_words:
                title = " ".join(words[:max_words])
                
            return title or "Newsletter Roundup"
            
        except Exception as e:
            logger.error(f"Error generating title: {e}")
            return "Newsletter Roundup"