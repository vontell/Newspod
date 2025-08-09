#!/usr/bin/env python3
"""
Newsletter Podcast Generator
Main entry point for generating podcasts from email newsletters.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

from newsletter_podcast.podcast_generator import NewsletterPodcastGenerator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """Load configuration from JSON file."""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Generate podcasts from email newsletters")
    parser.add_argument("--config", required=True, help="Path to configuration JSON file")
    parser.add_argument("--hours", type=int, default=24, help="Hours to look back for newsletters (default: 24)")
    parser.add_argument("--duration", type=int, default=10, help="Target podcast duration in minutes (default: 10)")
    parser.add_argument("--output", default="output", help="Output directory (default: output)")
    parser.add_argument("--filters", nargs="*", help="Newsletter filter keywords")
    parser.add_argument("--segmented", action="store_true", help="Generate segmented podcast")
    parser.add_argument("--segment-duration", type=int, default=2, help="Duration of each segment in minutes (default: 2)")
    parser.add_argument("--quick", action="store_true", help="Quick mode: Use cached emails and generate 25%% shorter script")
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Create generator
    generator = NewsletterPodcastGenerator(config)
    
    # Generate podcast
    logger.info("=" * 50)
    logger.info("Newsletter Podcast Generator")
    if args.quick:
        logger.info("** QUICK MODE ENABLED **")
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)
    
    if args.segmented:
        result = generator.generate_segmented_podcast(
            hours_lookback=args.hours,
            segment_duration_minutes=args.segment_duration,
            newsletter_filters=args.filters,
            output_dir=args.output
        )
    else:
        result = generator.generate_podcast(
            hours_lookback=args.hours,
            target_duration_minutes=args.duration,
            newsletter_filters=args.filters,
            output_dir=args.output,
            quick_mode=args.quick
        )
    
    # Print results
    logger.info("=" * 50)
    logger.info("Generation Complete")
    logger.info(f"Success: {result['success']}")
    logger.info(f"Newsletters found: {result['newsletters_found']}")
    
    if result['success']:
        logger.info(f"Script: {result.get('script_path', 'N/A')}")
        logger.info(f"Audio: {result.get('audio_path', 'N/A')}")
        logger.info(f"Uploaded: {result.get('uploaded_url', 'N/A')}")
    else:
        logger.error(f"Errors: {', '.join(result.get('errors', []))}")
        
    logger.info("=" * 50)
    
    # Save full results
    results_path = os.path.join(args.output, f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(results_path, 'w') as f:
        json.dump(result, f, indent=2)
    logger.info(f"Full results saved to: {results_path}")
    
    return 0 if result['success'] else 1


if __name__ == "__main__":
    sys.exit(main())