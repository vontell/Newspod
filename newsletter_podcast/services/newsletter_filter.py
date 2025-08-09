import anthropic
from typing import List, Dict, Optional, Tuple
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from dataclasses import dataclass

from ..services.email_service import Newsletter

logger = logging.getLogger(__name__)


@dataclass
class FilterResult:
    """Result of newsletter filtering."""
    is_relevant: bool
    relevance_score: float
    reason: str
    topics: List[str]


class NewsletterFilter:
    """Intelligent newsletter filtering using Claude."""
    
    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307"):
        """
        Initialize newsletter filter.
        
        Args:
            api_key: Anthropic API key
            model: Claude model to use (Haiku recommended for speed/cost)
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        
    def filter_newsletters_parallel(self,
                                   newsletters: List[Newsletter],
                                   user_name: str,
                                   user_role: str,
                                   interests: List[str],
                                   max_workers: int = 10) -> List[Tuple[Newsletter, FilterResult]]:
        """
        Filter newsletters in parallel using Claude.
        
        Args:
            newsletters: List of newsletters to filter
            user_name: User's name for personalization
            user_role: User's professional role
            interests: List of user interests
            max_workers: Maximum parallel workers
            
        Returns:
            List of tuples (newsletter, filter_result) for relevant newsletters
        """
        logger.info(f"Filtering {len(newsletters)} newsletters using Claude...")
        
        relevant_newsletters = []
        
        with ThreadPoolExecutor(max_workers=min(max_workers, len(newsletters))) as executor:
            # Submit all filtering tasks
            future_to_newsletter = {
                executor.submit(
                    self._filter_single_newsletter,
                    newsletter,
                    user_name,
                    user_role,
                    interests
                ): newsletter
                for newsletter in newsletters
            }
            
            # Process results as they complete
            for future in as_completed(future_to_newsletter):
                newsletter = future_to_newsletter[future]
                try:
                    result = future.result()
                    if result.is_relevant:
                        relevant_newsletters.append((newsletter, result))
                        logger.info(f"✓ Relevant: {newsletter.subject[:50]}... (score: {result.relevance_score})")
                    else:
                        logger.info(f"✗ Filtered out: {newsletter.subject[:50]}...")
                        
                except Exception as e:
                    logger.error(f"Error filtering newsletter {newsletter.subject}: {e}")
                    # Include newsletter with error to not lose it
                    error_result = FilterResult(
                        is_relevant=True,
                        relevance_score=0.5,
                        reason=f"Error during filtering: {str(e)}",
                        topics=[]
                    )
                    relevant_newsletters.append((newsletter, error_result))
                    
        # Sort by relevance score
        relevant_newsletters.sort(key=lambda x: x[1].relevance_score, reverse=True)
        
        logger.info(f"Filtered {len(newsletters)} newsletters to {len(relevant_newsletters)} relevant items")
        return relevant_newsletters
        
    def _filter_single_newsletter(self,
                                newsletter: Newsletter,
                                user_name: str,
                                user_role: str,
                                interests: List[str]) -> FilterResult:
        """
        Filter a single newsletter using Claude.
        
        Args:
            newsletter: Newsletter to evaluate
            user_name: User's name
            user_role: User's role
            interests: User's interests
            
        Returns:
            FilterResult with relevance information
        """
        # Truncate content to avoid token limits
        content_preview = newsletter.body[:2000] if newsletter.body else ""
        
        prompt = f"""Evaluate if this newsletter contains relevant NEWS or UPDATES for {user_name}, who works as {user_role}.

User interests: {", ".join(interests)}

Newsletter details:
Subject: {newsletter.subject}
From: {newsletter.sender}
Source: {newsletter.newsletter_source}
Content preview: {content_preview}

Determine if this contains:
1. Breaking news or important updates in user's field
2. New product announcements or features
3. Industry trends or insights
4. Research findings or technical developments
5. Relevant business or policy changes
6. Is relevant to their personal life or things they need to get done

DO NOT include:
- Promotional content without news value
- Pure marketing or sales pitches
- Repeated/recycled content

Respond with JSON only:
{{
    "is_relevant": true/false,
    "relevance_score": 0.0-1.0,
    "reason": "brief explanation",
    "topics": ["topic1", "topic2"]
}}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            
            result_text = response.content[0].text.strip()
            
            # Try to extract JSON if it's embedded in other text
            json_str = result_text
            
            # Look for JSON object in the response
            if "{" in result_text and "}" in result_text:
                # Find the first { and last } to extract JSON
                start_idx = result_text.find("{")
                # Find matching closing brace
                brace_count = 0
                end_idx = start_idx
                for i in range(start_idx, len(result_text)):
                    if result_text[i] == "{":
                        brace_count += 1
                    elif result_text[i] == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            end_idx = i + 1
                            break
                            
                if end_idx > start_idx:
                    json_str = result_text[start_idx:end_idx]
            
            # Try to parse JSON response
            try:
                result_data = json.loads(json_str)
                return FilterResult(
                    is_relevant=result_data.get("is_relevant", False),
                    relevance_score=float(result_data.get("relevance_score", 0.0)),
                    reason=result_data.get("reason", "No reason provided"),
                    topics=result_data.get("topics", [])
                )
            except json.JSONDecodeError:
                # Fallback if Claude doesn't return valid JSON
                logger.warning(f"Invalid JSON from Claude. Extracted: {json_str[:100]}...")
                # Try to determine relevance from the text
                is_relevant = "true" in result_text.lower() and "is_relevant" in result_text
                return FilterResult(
                    is_relevant=is_relevant,
                    relevance_score=0.5 if is_relevant else 0.0,
                    reason="JSON parse error - decision based on text analysis",
                    topics=[]
                )
                
        except Exception as e:
            logger.error(f"Error calling Claude API: {e}")
            raise
            
    def get_simple_filters(self, user_role: str, interests: List[str]) -> List[str]:
        """
        Generate simple keyword filters based on user profile.
        
        Args:
            user_role: User's role
            interests: User's interests
            
        Returns:
            List of keyword filters
        """
        # Extract keywords from role
        role_keywords = user_role.lower().split()
        
        # Combine with interests
        all_keywords = role_keywords + [i.lower() for i in interests]
        
        # Add common newsletter indicators
        newsletter_indicators = ["newsletter", "weekly", "daily", "digest", "update", "news"]
        
        # Remove duplicates and return
        return list(set(all_keywords + newsletter_indicators))