#!/usr/bin/env python3
"""
Enhanced Service Detector for AI Chat Extractor
Automatically detects AI service from URL with shared link identification.
"""

import re
from urllib.parse import urlparse
from typing import Optional, Dict, Tuple
import logging

from models import ServiceType

logger = logging.getLogger(__name__)

class LinkType:
    """Types of AI service links"""
    SHARED_CONVERSATION = "shared_conversation"
    REGULAR_CHAT = "regular_chat"
    UNKNOWN = "unknown"

class ServiceDetector:
    """Enhanced detector for AI service and link type identification"""
    
    # Base service patterns
    SERVICE_PATTERNS = {
        ServiceType.GROK: [
            r'grok\.x\.com',
            r'x\.com/grok',
            r'grok\.com',
        ],
        ServiceType.CHATGPT: [
            r'chat\.openai\.com',
            r'chatgpt\.com',
        ],
        ServiceType.GEMINI: [
            r'gemini\.google\.com',
            r'bard\.google\.com',
            r'g\.co/gemini',
        ],
        ServiceType.CLAUDE: [
            r'claude\.ai',
            r'anthropic\.com/claude',
        ]
    }
    
    # Shared link patterns for each service
    SHARED_LINK_PATTERNS = {
        ServiceType.GROK: [
            r'/share/[a-f0-9-]+',
            r'/grok/share/[a-f0-9-]+',
            r'/conversation/[a-f0-9-]+',
        ],
        ServiceType.CHATGPT: [
            r'/share/[a-f0-9-]+',
            r'/c/[a-f0-9-]+',
            r'/chat/[a-f0-9-]+',
        ],
        ServiceType.GEMINI: [
            r'/share/[a-f0-9-]+',
            r'/conversation/[a-f0-9-]+',
        ],
        ServiceType.CLAUDE: [
            r'/chat/[a-f0-9-]+',
            r'/conversation/[a-f0-9-]+',
        ]
    }
    
    # Regular chat patterns (non-shared)
    REGULAR_CHAT_PATTERNS = {
        ServiceType.GROK: [
            r'/grok$',
            r'/grok/$',
            r'/grok\?',
        ],
        ServiceType.CHATGPT: [
            r'/chat$',
            r'/chat/$',
            r'/chat\?',
            r'/$'  # root path
        ],
        ServiceType.GEMINI: [
            r'/app$',
            r'/app/$',
            r'/app\?',
            r'/$'  # root path
        ],
        ServiceType.CLAUDE: [
            r'/chat$',
            r'/chat/$',
            r'/chat\?',
            r'/$'  # root path
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
        service_info = self.analyze_url(url)
        return service_info['service'] if service_info['service'] else None
    
    def analyze_url(self, url: str) -> Dict[str, Optional[str]]:
        """
        Comprehensive URL analysis for service and link type detection
        
        Args:
            url: The URL to analyze
            
        Returns:
            Dictionary with 'service', 'link_type', and 'confidence' keys
        """
        try:
            parsed_url = urlparse(url.lower())
            domain = parsed_url.netloc
            path = parsed_url.path
            full_match = f"{domain}{path}"
            
            logger.debug(f"Analyzing URL: {url}")
            logger.debug(f"Domain: {domain}, Path: {path}")
            
            # First, detect the service
            detected_service = None
            for service_type, patterns in self.SERVICE_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, full_match):
                        detected_service = service_type
                        logger.debug(f"Detected service: {service_type.value}")
                        break
                if detected_service:
                    break
            
            if not detected_service:
                logger.debug(f"Could not detect service from URL: {url}")
                return {
                    'service': None,
                    'link_type': LinkType.UNKNOWN,
                    'confidence': 0.0
                }
            
            # Now determine link type
            link_type, confidence = self._determine_link_type(detected_service, path)
            
            result = {
                'service': detected_service.value,
                'link_type': link_type,
                'confidence': confidence
            }
            
            logger.info(f"URL analysis result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing URL {url}: {e}")
            return {
                'service': None,
                'link_type': LinkType.UNKNOWN,
                'confidence': 0.0
            }
    
    def _determine_link_type(self, service_type: ServiceType, path: str) -> Tuple[str, float]:
        """
        Determine if this is a shared link or regular chat
        
        Args:
            service_type: Detected service type
            path: URL path component
            
        Returns:
            Tuple of (link_type, confidence_score)
        """
        # Check for shared link patterns first
        shared_patterns = self.SHARED_LINK_PATTERNS.get(service_type, [])
        for pattern in shared_patterns:
            if re.search(pattern, path):
                logger.debug(f"Matched shared link pattern: {pattern}")
                return LinkType.SHARED_CONVERSATION, 0.9
        
        # Check for regular chat patterns
        regular_patterns = self.REGULAR_CHAT_PATTERNS.get(service_type, [])
        for pattern in regular_patterns:
            if re.search(pattern, path):
                logger.debug(f"Matched regular chat pattern: {pattern}")
                return LinkType.REGULAR_CHAT, 0.8
        
        # If no specific pattern matches, make educated guess
        # Shared links typically have longer, random-looking IDs
        if re.search(r'/[a-f0-9]{8,}', path):
            logger.debug("Guessing shared link based on long hex ID")
            return LinkType.SHARED_CONVERSATION, 0.6
        elif len(path.strip('/')) == 0:
            logger.debug("Guessing regular chat based on root path")
            return LinkType.REGULAR_CHAT, 0.5
        else:
            logger.debug("Could not determine link type")
            return LinkType.UNKNOWN, 0.3
    
    def is_shared_link(self, url: str) -> bool:
        """
        Check if URL is a shared conversation link
        
        Args:
            url: URL to check
            
        Returns:
            True if this appears to be a shared conversation link
        """
        analysis = self.analyze_url(url)
        return analysis['link_type'] == LinkType.SHARED_CONVERSATION
    
    def is_regular_chat(self, url: str) -> bool:
        """
        Check if URL is a regular chat interface
        
        Args:
            url: URL to check
            
        Returns:
            True if this appears to be a regular chat interface
        """
        analysis = self.analyze_url(url)
        return analysis['link_type'] == LinkType.REGULAR_CHAT
    
    def is_supported_service(self, url: str) -> bool:
        """Check if the URL is from a supported service"""
        return self.detect_service(url) is not None
    
    def get_extraction_difficulty(self, url: str) -> str:
        """
        Estimate extraction difficulty based on URL type
        
        Args:
            url: URL to analyze
            
        Returns:
            Difficulty level: 'easy', 'medium', 'hard'
        """
        analysis = self.analyze_url(url)
        
        if analysis['link_type'] == LinkType.SHARED_CONVERSATION:
            return 'easy'  # Shared links are usually static and easier to extract
        elif analysis['link_type'] == LinkType.REGULAR_CHAT:
            return 'hard'  # Regular chats often require authentication
        else:
            return 'medium'  # Unknown type
    
    def get_supported_domains(self) -> list:
        """Get list of all supported domain patterns"""
        domains = []
        for patterns in self.SERVICE_PATTERNS.values():
            domains.extend(patterns)
        return domains
    
    def get_service_info(self, url: str) -> Dict[str, str]:
        """
        Get comprehensive service information
        
        Args:
            url: URL to analyze
            
        Returns:
            Dictionary with service details
        """
        analysis = self.analyze_url(url)
        
        info = {
            'service': analysis['service'] or 'unknown',
            'link_type': analysis['link_type'],
            'difficulty': self.get_extraction_difficulty(url),
            'confidence': f"{analysis['confidence']:.1f}",
            'supported': analysis['service'] is not None
        }
        
        # Add service-specific recommendations
        if analysis['service']:
            service_type = ServiceType(analysis['service'])
            if service_type == ServiceType.GROK:
                info['notes'] = 'Grok uses Next.js streaming data format'
            elif service_type == ServiceType.CHATGPT:
                info['notes'] = 'ChatGPT often embeds data in __INITIAL_STATE__'
            elif service_type == ServiceType.CLAUDE:
                info['notes'] = 'Claude may use various JSON embedding patterns'
            elif service_type == ServiceType.GEMINI:
                info['notes'] = 'Gemini primarily uses HTML DOM structure'
        
        return info