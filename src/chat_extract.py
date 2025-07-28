#!/usr/bin/env python3
"""
AI Chat Extractor CLI
Extract AI chat conversations from shared links and convert to Obsidian Chat View format.
"""

import argparse
import sys
import os
from pathlib import Path
from urllib.parse import urlparse
import logging

from config_manager import ConfigManager
from extractors.service_detector import ServiceDetector
from extractors.extractor_factory import ExtractorFactory
from output_formatter import ObsidianChatFormatter
from updater import UpdateManager

VERSION = "0.1.0"

def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def print_tos_warning():
    """Print Terms of Service warning"""
    print("\n⚠️  Terms of Service Warning:")
    print("This tool performs web scraping for personal use only.")
    print("Please ensure you comply with the Terms of Service of the respective platforms.")
    print("Use at your own risk and responsibility.\n")

def validate_url(url: str) -> bool:
    """Validate if the provided URL is valid"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Extract AI chat conversations and convert to Obsidian Chat View format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  chat_extract https://chat.openai.com/share/abc123
  chat_extract https://grok.x.com/share/xyz789 --output ~/Documents/Chats
  chat_extract https://claude.ai/chat/abc123 --service claude --verbose
        """
    )
    
    parser.add_argument(
        "url",
        help="AI chat share URL to extract from"
    )
    
    parser.add_argument(
        "--output", "-o",
        help="Output directory for the conversation file (default: from config)"
    )
    
    parser.add_argument(
        "--config", "-c",
        help="Configuration file path (default: ~/.config/ai_chat_extractor/config.yaml)"
    )
    
    parser.add_argument(
        "--service", "-s",
        choices=["grok", "chatgpt", "gemini", "claude"],
        help="Manually specify the AI service (default: auto-detect from URL)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--styles",
        help="Override chat view styles (format: 'header=h3,mw=75')"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"AI Chat Extractor v{VERSION}"
    )
    
    parser.add_argument(
        "--update",
        action="store_true",
        help="Check for and install updates from GitHub"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    try:
        # Handle update request
        if args.update:
            logger.info("Checking for updates...")
            update_manager = UpdateManager()
            update_manager.check_and_update()
            return 0
        
        # Validate URL
        if not validate_url(args.url):
            logger.error(f"Invalid URL: {args.url}")
            return 1
        
        # Print ToS warning
        print_tos_warning()
        
        # Load configuration
        logger.info("Loading configuration...")
        config_manager = ConfigManager(args.config)
        config = config_manager.load_config()
        
        # Detect service
        if args.service:
            service = args.service
            logger.info(f"Using manually specified service: {service}")
        else:
            detector = ServiceDetector()
            service = detector.detect_service(args.url)
            if not service:
                logger.error(f"Could not detect AI service from URL: {args.url}")
                return 1
            logger.info(f"Detected service: {service}")
        
        # Create extractor
        logger.info("Initializing extractor...")
        extractor_factory = ExtractorFactory()
        extractor = extractor_factory.create_extractor(service)
        
        # Extract conversation
        logger.info(f"Extracting conversation from {args.url}...")
        conversation = extractor.extract_conversation(args.url)
        
        if not conversation or not conversation.messages:
            logger.error("No conversation data extracted")
            return 1
        
        logger.info(f"Extracted {len(conversation.messages)} messages")
        
        # Format output
        logger.info("Formatting output...")
        formatter = ObsidianChatFormatter(config, args.styles)
        markdown_content = formatter.format_conversation(conversation)
        
        # Determine output path
        output_dir = args.output or config.get('default_output', '~/Documents/Conversations')
        output_dir = Path(output_dir).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        filename_template = config.get('output', {}).get('filename_template', 
                                                       'conversation_{service}_{timestamp}.md')
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = filename_template.format(
            service=service,
            timestamp=timestamp
        )
        
        output_path = output_dir / filename
        
        # Save file
        logger.info(f"Saving conversation to {output_path}")
        output_path.write_text(markdown_content, encoding='utf-8')
        
        print(f"✅ Successfully extracted conversation!")
        print(f"📁 Saved to: {output_path}")
        print(f"📊 Messages: {len(conversation.messages)}")
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())