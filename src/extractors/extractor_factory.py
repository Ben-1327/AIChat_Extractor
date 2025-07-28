#!/usr/bin/env python3
"""
Extractor Factory for AI Chat Extractor
Creates appropriate extractor instances based on service type.
"""

from typing import Dict, Any
import logging

from models import ServiceType
from extractors.base_extractor import BaseExtractor
from extractors.grok_extractor import GrokExtractor
from extractors.chatgpt_extractor import ChatGPTExtractor
from extractors.gemini_extractor import GeminiExtractor
from extractors.claude_extractor import ClaudeExtractor

logger = logging.getLogger(__name__)

class ExtractorFactory:
    """Factory class for creating service-specific extractors"""
    
    EXTRACTOR_CLASSES = {
        'grok': GrokExtractor,
        'chatgpt': ChatGPTExtractor,
        'gemini': GeminiExtractor,
        'claude': ClaudeExtractor,
    }
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
    
    def create_extractor(self, service: str) -> BaseExtractor:
        """
        Create an extractor instance for the specified service
        
        Args:
            service: Service name string
            
        Returns:
            Appropriate extractor instance
            
        Raises:
            ValueError: If service is not supported
        """
        service = service.lower()
        
        if service not in self.EXTRACTOR_CLASSES:
            supported_services = ', '.join(self.EXTRACTOR_CLASSES.keys())
            raise ValueError(f"Unsupported service: {service}. Supported services: {supported_services}")
        
        extractor_class = self.EXTRACTOR_CLASSES[service]
        service_type = ServiceType(service)
        
        logger.debug(f"Creating {service} extractor")
        return extractor_class(service_type, self.config)
    
    def get_supported_services(self) -> list:
        """Get list of supported service names"""
        return list(self.EXTRACTOR_CLASSES.keys())
    
    def is_supported_service(self, service: str) -> bool:
        """Check if a service is supported"""
        return service.lower() in self.EXTRACTOR_CLASSES