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
from datetime import datetime

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
        help="AI chat share URL to extract from (or path to HTML file with --from-file)"
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
    
    parser.add_argument(
        "--from-file",
        action="store_true",
        help="Extract from a local HTML file instead of fetching from URL"
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
        
        # Validate URL or file path
        if args.from_file:
            # Check if file exists
            file_path = Path(args.url)
            if not file_path.exists():
                logger.error(f"File not found: {args.url}")
                return 1
            if not file_path.is_file():
                logger.error(f"Path is not a file: {args.url}")
                return 1
            logger.info(f"Reading from local file: {args.url}")
        else:
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
        if args.from_file:
            logger.info(f"Extracting conversation from file: {args.url}")
        else:
            logger.info(f"Extracting conversation from URL: {args.url}")
        
        # Track if we encountered specific errors
        extraction_error_type = None
        try:
            conversation = extractor.extract_conversation(args.url, from_file=args.from_file)
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            extraction_error_type = "exception"
            conversation = None
        
        if not conversation or not conversation.messages:
            logger.error("No conversation data extracted")
            
            # Provide helpful suggestions based on error type
            print("\n🔧 Troubleshooting Tips:")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            # Check for 403 errors in logs (simplified approach)
            print("📍 Common Issues & Solutions:")
            print("\n🚫 If you see '403 Forbidden' errors:")
            print("1. 🔐 The shared link may require login/authentication")
            print("2. 🔗 Verify the URL works in your browser first")
            print("3. ⏰ The shared link may have expired")
            print("4. 🛡️ The service may be blocking automated requests")
            print("5. ☁️ Cloudflare protection may be blocking the request")
            print("")
            print("💡 Manual Extraction Methods:")
            print("📄 Option 1 - Save HTML file:")
            print("1. Open the URL in your browser")
            print("2. Right-click → 'Save As' → Save as HTML file")
            print("3. Run: chat_extract /path/to/file.html --from-file --service [service]")
            print("")
            print("📝 Option 2 - Manual copy:")
            print("1. Open the URL in your browser")
            print("2. Copy the conversation text manually") 
            print("3. Convert to Obsidian Chat View format manually")
            
            print("\n🔧 Other possible issues:")
            print("1. 🔗 Check if the URL is correct and complete")
            print("2. 🌐 Verify your internet connection")
            print("3. 🔄 Try again in a few minutes")
            print("4. 📱 Test the URL accessibility in your browser")
            
            print("\n🆘 Need Help?")
            print("• 📖 Documentation: https://github.com/Ben-1327/AIChat_Extractor")
            print("• 🐛 Report issues: https://github.com/Ben-1327/AIChat_Extractor/issues")
            print("• 💬 Use --verbose flag for detailed error logs")
            
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