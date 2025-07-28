#!/usr/bin/env python3
"""
Service Detector for AI Chat Extractor
Automatically detects AI service from URL.
"""

import re
from urllib.parse import urlparse
from typing import Optional
import logging

from models import ServiceType

logger = logging.getLogger(__name__)

class ServiceDetector:
    """Detects AI service from URL patterns"""
    
    SERVICE_PATTERNS = {
        ServiceType.GROK: [
            r'grok\.x\.com',
            r'x\.com/grok',
        ],
        ServiceType.CHATGPT: [
            r'chat\.openai\.com',
            r'chatgpt\.com',
        ],
        ServiceType.GEMINI: [
            r'gemini\.google\.com',
            r'bard\.google\.com',
        ],
        ServiceType.CLAUDE: [
            r'claude\.ai',
            r'anthropic\.com/claude',
        ]
    }
    
    def detect_service(self, url: str) -> Optional[str]:
        """
        Detect AI service from URL
        
        Args:
            url: The URL to analyze
            
        Returns:
            Service name string or None if not detected
        """
        try:
            parsed_url = urlparse(url.lower())
            domain = parsed_url.netloc
            path = parsed_url.path
            full_match = f"{domain}{path}"
            
            logger.debug(f"Detecting service for URL: {url}")
            logger.debug(f"Domain: {domain}, Path: {path}")
            
            for service_type, patterns in self.SERVICE_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, full_match):
                        service_name = service_type.value
                        logger.info(f"Detected service: {service_name}")
                        return service_name
            
            logger.warning(f"Could not detect service from URL: {url}")
            return None
            
        except Exception as e:
            logger.error(f"Error detecting service from URL {url}: {e}")
            return None
    
    def is_supported_service(self, url: str) -> bool:
        """Check if the URL is from a supported service"""
        return self.detect_service(url) is not None
    
    def get_supported_domains(self) -> list:
        """Get list of all supported domain patterns"""
        domains = []
        for patterns in self.SERVICE_PATTERNS.values():
            domains.extend(patterns)
        return domains