#!/usr/bin/env python3
"""
Base Extractor for AI Chat Extractor
Abstract base class for all service extractors.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import requests
from bs4 import BeautifulSoup
import logging
import time
import random

from models import Conversation, ServiceType

logger = logging.getLogger(__name__)

class BaseExtractor(ABC):
    """Abstract base class for all service extractors"""
    
    def __init__(self, service_type: ServiceType, config: Dict[str, Any]):
        self.service_type = service_type
        self.config = config
        self.session = requests.Session()
        
        # Set comprehensive headers to appear more like a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9,ja;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'DNT': '1',
        })
    
    def extract_conversation(self, url: str) -> Optional[Conversation]:
        """
        Extract conversation from URL
        
        Args:
            url: The share URL to extract from
            
        Returns:
            Conversation object or None if extraction failed
        """
        try:
            logger.info(f"Starting extraction from {url}")
            
            # Fetch HTML content
            html_content = self._fetch_html(url)
            if not html_content:
                logger.error("Failed to fetch HTML content")
                return None
            
            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract conversation using service-specific logic
            conversation = self._parse_conversation(soup, url)
            
            if conversation:
                logger.info(f"Successfully extracted {len(conversation.messages)} messages")
            else:
                logger.warning("No conversation data found")
            
            return conversation
            
        except Exception as e:
            logger.error(f"Error extracting conversation: {e}")
            return None
    
    def _fetch_html(self, url: str) -> Optional[str]:
        """
        Fetch HTML content from URL with retries
        
        Args:
            url: URL to fetch
            
        Returns:
            HTML content string or None if failed
        """
        max_retries = self.config.get('extraction', {}).get('max_retries', 3)
        timeout = self.config.get('extraction', {}).get('timeout', 30)
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"Fetching HTML (attempt {attempt + 1}/{max_retries})")
                
                # Add some randomization to avoid detection
                if attempt > 0:
                    time.sleep(random.uniform(2, 5))
                
                # Try to handle different types of URLs
                response = self.session.get(url, timeout=timeout, allow_redirects=True)
                
                # Special handling for 403 errors
                if response.status_code == 403:
                    logger.warning(f"403 Forbidden - trying with different headers")
                    # Try with minimal headers
                    minimal_headers = {
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                    }
                    response = self.session.get(url, timeout=timeout, headers=minimal_headers, allow_redirects=True)
                
                response.raise_for_status()
                
                logger.debug(f"Successfully fetched HTML ({len(response.text)} characters)")
                return response.text
                
            except requests.HTTPError as e:
                if e.response.status_code == 403:
                    logger.warning(f"Attempt {attempt + 1} failed with 403 Forbidden. This may be due to:")
                    logger.warning("1. The shared link requires authentication")
                    logger.warning("2. The service blocks automated requests")
                    logger.warning("3. The URL may be expired or invalid")
                else:
                    logger.warning(f"Attempt {attempt + 1} failed: {e}")
                    
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(1, 3)
                    logger.debug(f"Waiting {wait_time:.1f} seconds before retry...")
                    time.sleep(wait_time)
                continue
                
            except requests.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(1, 3)
                    logger.debug(f"Waiting {wait_time:.1f} seconds before retry...")
                    time.sleep(wait_time)
                continue
        
        logger.error(f"Failed to fetch HTML after {max_retries} attempts")
        return None
    
    @abstractmethod
    def _parse_conversation(self, soup: BeautifulSoup, url: str) -> Optional[Conversation]:
        """
        Parse conversation from BeautifulSoup object
        This method must be implemented by each service extractor
        
        Args:
            soup: BeautifulSoup parsed HTML
            url: Original URL for reference
            
        Returns:
            Conversation object or None if parsing failed
        """
        pass
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ""
        
        # Remove extra whitespace and normalize
        text = ' '.join(text.split())
        
        # Remove any remaining HTML entities
        from html import unescape
        text = unescape(text)
        
        return text.strip()
    
    def _should_include_message(self, content: str) -> bool:
        """Check if message content should be included"""
        if not content or not content.strip():
            return False
        
        min_length = self.config.get('extraction', {}).get('min_message_length', 1)
        return len(content.strip()) >= min_length