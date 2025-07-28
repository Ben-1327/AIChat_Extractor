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
    
    def extract_conversation(self, url_or_path: str, from_file: bool = False) -> Optional[Conversation]:
        """
        Extract conversation from URL or local file
        
        Args:
            url_or_path: The share URL or file path to extract from
            from_file: If True, treat url_or_path as a local file path
            
        Returns:
            Conversation object or None if extraction failed
        """
        try:
            if from_file:
                logger.info(f"Starting extraction from local file: {url_or_path}")
                html_content = self._read_local_file(url_or_path)
                source_url = f"file://{url_or_path}"
            else:
                logger.info(f"Starting extraction from URL: {url_or_path}")
                html_content = self._fetch_html(url_or_path)
                source_url = url_or_path
            
            if not html_content:
                logger.error("Failed to get HTML content")
                return None
            
            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract conversation using service-specific logic
            conversation = self._parse_conversation(soup, source_url)
            
            if conversation:
                logger.info(f"Successfully extracted {len(conversation.messages)} messages")
            else:
                logger.warning("No conversation data found")
            
            return conversation
            
        except Exception as e:
            logger.error(f"Error extracting conversation: {e}")
            return None
    
    def _read_local_file(self, file_path: str) -> Optional[str]:
        """
        Read HTML content from local file
        
        Args:
            file_path: Path to the HTML file
            
        Returns:
            HTML content string or None if failed
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.debug(f"Successfully read local file ({len(content)} characters)")
            return content
        except Exception as e:
            logger.error(f"Failed to read local file {file_path}: {e}")
            return None
    
    def _fetch_html(self, url: str) -> Optional[str]:
        """
        Fetch HTML content from URL with advanced anti-detection techniques
        
        Args:
            url: URL to fetch
            
        Returns:
            HTML content string or None if failed
        """
        max_retries = self.config.get('extraction', {}).get('max_retries', 3)
        timeout = self.config.get('extraction', {}).get('timeout', 30)
        
        # Create different header sets to try
        header_sets = [
            # Chrome on macOS (most common)
            {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Referer': 'https://www.google.com/',
            },
            # Safari on macOS
            {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
            },
            # Firefox on macOS
            {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
            },
            # Minimal headers
            {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            }
        ]
        
        for attempt in range(max_retries):
            # Use different header set for each attempt
            headers = header_sets[attempt % len(header_sets)]
            
            try:
                logger.debug(f"Fetching HTML (attempt {attempt + 1}/{max_retries})")
                logger.debug(f"Using User-Agent: {headers.get('User-Agent', '')[:50]}...")
                
                # Add randomization to avoid detection patterns
                if attempt > 0:
                    wait_time = random.uniform(3, 8)
                    logger.debug(f"Waiting {wait_time:.1f} seconds to avoid detection...")
                    time.sleep(wait_time)
                
                # Create a fresh session for each attempt to avoid session tracking
                fresh_session = requests.Session()
                fresh_session.headers.update(headers)
                
                # Try to mimic real browser behavior
                response = fresh_session.get(
                    url, 
                    timeout=timeout, 
                    allow_redirects=True,
                    stream=False
                )
                
                logger.debug(f"Response status: {response.status_code}")
                logger.debug(f"Response headers: {dict(response.headers)}")
                
                # Handle different response codes
                if response.status_code == 200:
                    logger.debug(f"Successfully fetched HTML ({len(response.text)} characters)")
                    return response.text
                    
                elif response.status_code == 403:
                    logger.warning(f"403 Forbidden with header set {attempt + 1}")
                    
                    # Check if this is a Cloudflare challenge
                    if 'cf-mitigated' in response.headers or 'cloudflare' in response.headers.get('server', '').lower():
                        logger.info("Detected Cloudflare protection - attempting bypass...")
                        cloudflare_result = self._try_cloudflare_bypass(url, timeout)
                        if cloudflare_result:
                            return cloudflare_result
                    
                    # Try alternative approach for 403
                    if attempt == max_retries - 1:
                        # Last attempt - try with completely different approach
                        logger.info("Trying alternative fetch method...")
                        return self._try_alternative_fetch(url, timeout)
                    continue
                    
                elif response.status_code == 429:
                    # Rate limited - wait longer
                    wait_time = random.uniform(10, 20)
                    logger.warning(f"Rate limited (429) - waiting {wait_time:.1f} seconds...")
                    time.sleep(wait_time)
                    continue
                    
                else:
                    response.raise_for_status()
                
            except requests.HTTPError as e:
                status_code = e.response.status_code if e.response else None
                logger.warning(f"Attempt {attempt + 1} failed with HTTP {status_code}: {e}")
                
                if status_code == 403:
                    if attempt == max_retries - 1:
                        logger.error("All attempts failed with 403 Forbidden")
                        logger.error("This shared link may require:")
                        logger.error("1. User authentication/login")
                        logger.error("2. Special access permissions")
                        logger.error("3. The link may be expired or private")
                        logger.error("4. The service may be blocking automated access")
                        return None
                        
            except requests.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                
            # Wait before next attempt with jitter
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) + random.uniform(2, 5)
                logger.debug(f"Waiting {wait_time:.1f} seconds before retry...")
                time.sleep(wait_time)
        
        logger.error(f"Failed to fetch HTML after {max_retries} attempts")
        return None
    
    def _try_cloudflare_bypass(self, url: str, timeout: int) -> Optional[str]:
        """
        Try to bypass Cloudflare protection using cloudscraper
        
        Args:
            url: URL to fetch
            timeout: Request timeout
            
        Returns:
            HTML content or None if failed
        """
        try:
            import cloudscraper
            logger.info("Attempting Cloudflare bypass with cloudscraper...")
            
            # Create cloudscraper session
            scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'darwin',  # macOS
                    'desktop': True
                }
            )
            
            # Set additional headers to appear more browser-like
            scraper.headers.update({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'en-US,en;q=0.9,ja;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0',
            })
            
            response = scraper.get(url, timeout=timeout)
            
            if response.status_code == 200:
                logger.info(f"Successfully bypassed Cloudflare protection ({len(response.text)} characters)")
                return response.text
            else:
                logger.warning(f"Cloudscraper failed with status code: {response.status_code}")
                return None
                
        except ImportError:
            logger.debug("cloudscraper not available - install with: pip install cloudscraper")
            return None
        except Exception as e:
            logger.warning(f"Cloudscraper failed: {e}")
            return None
    
    def _try_alternative_fetch(self, url: str, timeout: int) -> Optional[str]:
        """
        Try alternative methods to fetch content when standard methods fail
        
        Args:
            url: URL to fetch
            timeout: Request timeout
            
        Returns:
            HTML content or None
        """
        logger.info("Attempting alternative fetch methods...")
        
        try:
            # Method 1: Try cloudscraper (most effective for Cloudflare)
            cloudflare_result = self._try_cloudflare_bypass(url, timeout)
            if cloudflare_result:
                return cloudflare_result
            
            # Method 2: Try with requests-html (if available)
            try:
                import requests_html
                logger.debug("Trying with requests-html...")
                
                r_session = requests_html.HTMLSession()
                r = r_session.get(url, timeout=timeout)
                if r.status_code == 200:
                    logger.info("Successfully fetched with requests-html")
                    return r.text
            except ImportError:
                logger.debug("requests-html not available")
            except Exception as e:
                logger.debug(f"requests-html failed: {e}")
            
            # Method 3: Try with different session configuration
            logger.debug("Trying with alternative session configuration...")
            alt_session = requests.Session()
            alt_session.headers.clear()
            alt_session.headers.update({
                'User-Agent': 'curl/7.68.0',
                'Accept': '*/*',
            })
            
            response = alt_session.get(url, timeout=timeout)
            if response.status_code == 200:
                logger.info("Successfully fetched with alternative session")
                return response.text
                
        except Exception as e:
            logger.debug(f"Alternative fetch methods failed: {e}")
        
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