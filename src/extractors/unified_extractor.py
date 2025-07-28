#!/usr/bin/env python3
"""
Unified Extraction System for AI Chat Extractor
Coordinates multiple extraction strategies with fallback handling.
"""

import logging
from typing import Optional, List
from bs4 import BeautifulSoup
from datetime import datetime

from models import Conversation, ServiceType
from extractors.common_extractor import ExtractionResult, ExtractionError
from extractors.common_extractor import JSONExtractionStrategy
from extractors.html_extractor import HTMLExtractionStrategy, TextPatternExtractionStrategy

logger = logging.getLogger(__name__)

class UnifiedExtractor:
    """
    Coordinated extraction system with multiple strategies and fallback handling
    """
    
    def __init__(self, service_type: ServiceType, config: dict):
        self.service_type = service_type
        self.config = config
        
        # Initialize extraction strategies in order of preference
        self.strategies = [
            JSONExtractionStrategy(service_type),
            HTMLExtractionStrategy(service_type),
            TextPatternExtractionStrategy(service_type)
        ]
        
        # Track extraction attempts for debugging
        self.extraction_history = []
    
    def extract_conversation(self, soup: BeautifulSoup, url: str) -> Optional[Conversation]:
        """
        Extract conversation using multiple strategies with fallback
        
        Args:
            soup: BeautifulSoup parsed HTML
            url: Original URL for reference
            
        Returns:
            Conversation object or None if all strategies fail
        """
        self.extraction_history = []
        best_result = None
        
        logger.info(f"Starting unified extraction for {self.service_type.value}")
        
        # Try each strategy in order of preference
        for i, strategy in enumerate(self.strategies):
            strategy_name = strategy.__class__.__name__
            logger.debug(f"Attempting extraction with strategy {i+1}/{len(self.strategies)}: {strategy_name}")
            
            try:
                # Get confidence score first
                confidence = strategy.get_confidence_score(soup)
                logger.debug(f"{strategy_name} confidence score: {confidence:.2f}")
                
                # Skip low-confidence strategies if we already have a good result
                if best_result and best_result.confidence > 0.7 and confidence < 0.5:
                    logger.debug(f"Skipping {strategy_name} due to low confidence and existing good result")
                    continue
                
                # Attempt extraction
                result = strategy.extract(soup, url)
                
                # Log attempt
                self.extraction_history.append({
                    'strategy': strategy_name,
                    'success': result.success,
                    'message_count': len(result.messages),
                    'confidence': result.confidence,
                    'method': result.method
                })
                
                if result.success:
                    logger.info(f"{strategy_name} succeeded: {len(result.messages)} messages, confidence: {result.confidence:.2f}")
                    
                    # Update best result if this is better
                    if not best_result or result.confidence > best_result.confidence:
                        best_result = result
                    
                    # If we have high confidence, we can stop here
                    if result.confidence > 0.8:
                        logger.info(f"High confidence result achieved, stopping extraction attempts")
                        break
                else:
                    logger.debug(f"{strategy_name} failed: no messages extracted")
            
            except Exception as e:
                error_msg = f"{strategy_name} extraction failed with error: {e}"
                logger.debug(error_msg)
                
                self.extraction_history.append({
                    'strategy': strategy_name,
                    'success': False,
                    'error': str(e),
                    'confidence': 0.0
                })
        
        # Log extraction summary
        self._log_extraction_summary()
        
        # Return best result if we have one
        if best_result and best_result.success:
            return self._create_conversation(best_result, url)
        
        # If all strategies failed, log detailed information
        logger.warning("All extraction strategies failed")
        self._log_failure_analysis(soup)
        
        return None
    
    def _create_conversation(self, result: ExtractionResult, url: str) -> Conversation:
        """Create Conversation object from extraction result"""
        conversation = Conversation(
            messages=result.messages,
            service=self.service_type,
            title=result.title,
            url=url,
            extracted_at=datetime.now()
        )
        
        # Add extraction metadata
        conversation.extraction_method = result.method
        conversation.extraction_confidence = result.confidence
        
        return conversation
    
    def _log_extraction_summary(self):
        """Log summary of extraction attempts"""
        logger.info("Extraction attempt summary:")
        for i, attempt in enumerate(self.extraction_history, 1):
            if attempt['success']:
                logger.info(f"  {i}. {attempt['strategy']}: SUCCESS ({attempt['message_count']} messages, confidence: {attempt['confidence']:.2f})")
            else:
                error_info = f", error: {attempt.get('error', 'unknown')}" if 'error' in attempt else ""
                logger.info(f"  {i}. {attempt['strategy']}: FAILED{error_info}")
    
    def _log_failure_analysis(self, soup: BeautifulSoup):
        """Log detailed failure analysis to help debugging"""
        logger.debug("Failure analysis:")
        
        # Analyze page structure
        script_tags = soup.find_all('script')
        logger.debug(f"  - Found {len(script_tags)} script tags")
        
        json_scripts = 0
        for script in script_tags:
            if script.string and any(keyword in script.string.lower() 
                                   for keyword in ['conversation', 'messages', 'chat']):
                json_scripts += 1
        logger.debug(f"  - {json_scripts} scripts contain conversation-related keywords")
        
        # Analyze DOM structure
        divs = soup.find_all('div')
        logger.debug(f"  - Found {len(divs)} div elements")
        
        potential_messages = [
            div for div in divs 
            if 50 < len(div.get_text().strip()) < 2000
        ]
        logger.debug(f"  - {len(potential_messages)} divs with substantial text content")
        
        # Check for common class patterns
        message_classes = set()
        for div in divs:
            classes = div.get('class', [])
            for cls in classes:
                cls_lower = cls.lower()
                if any(keyword in cls_lower for keyword in ['message', 'chat', 'conversation', 'turn']):
                    message_classes.add(cls)
        
        if message_classes:
            logger.debug(f"  - Found message-related classes: {list(message_classes)[:5]}")
        else:
            logger.debug("  - No obvious message-related classes found")
    
    def get_extraction_stats(self) -> dict:
        """Get statistics about the last extraction attempt"""
        if not self.extraction_history:
            return {}
        
        successful_attempts = [a for a in self.extraction_history if a['success']]
        failed_attempts = [a for a in self.extraction_history if not a['success']]
        
        return {
            'total_attempts': len(self.extraction_history),
            'successful_attempts': len(successful_attempts),
            'failed_attempts': len(failed_attempts),
            'best_confidence': max((a.get('confidence', 0) for a in self.extraction_history), default=0),
            'strategies_used': [a['strategy'] for a in self.extraction_history],
            'final_success': len(successful_attempts) > 0
        }

class ExtractorErrorHandler:
    """Centralized error handling for extraction processes"""
    
    @staticmethod
    def handle_extraction_error(error: Exception, service: str, url: str, context: str = "") -> ExtractionError:
        """
        Convert generic exceptions to structured ExtractionError
        
        Args:
            error: Original exception
            service: Service name (grok, chatgpt, etc.)
            url: URL being processed
            context: Additional context about where the error occurred
            
        Returns:
            Structured ExtractionError
        """
        error_msg = str(error)
        error_type = "general"
        
        # Categorize common error types
        if "403" in error_msg or "Forbidden" in error_msg:
            error_type = "access_denied"
        elif "404" in error_msg or "Not Found" in error_msg:
            error_type = "not_found"
        elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            error_type = "timeout"
        elif "json" in error_msg.lower() and "decode" in error_msg.lower():
            error_type = "json_parse_error"
        elif "connection" in error_msg.lower():
            error_type = "connection_error"
        elif "cloudflare" in error_msg.lower():
            error_type = "cloudflare_protection"
        
        # Create detailed error message
        detailed_msg = f"Extraction failed for {service}"
        if context:
            detailed_msg += f" in {context}"
        detailed_msg += f": {error_msg}"
        
        return ExtractionError(detailed_msg, error_type, service)
    
    @staticmethod
    def get_user_friendly_message(error: ExtractionError) -> str:
        """Get user-friendly error message with suggested solutions"""
        base_msg = f"Failed to extract conversation from {error.service or 'AI service'}"
        
        suggestions = {
            "access_denied": [
                "The shared link may require login/authentication",
                "Verify the URL works in your browser first",
                "The shared link may have expired",
                "The service may be blocking automated requests"
            ],
            "not_found": [
                "The shared link may be invalid or expired",
                "Check if the URL is correct",
                "The conversation may have been deleted"
            ],
            "timeout": [
                "The service may be slow to respond",
                "Try again later",
                "Check your internet connection"
            ],
            "json_parse_error": [
                "The page structure may have changed",
                "The service may have updated their format",
                "This might be a temporary issue"
            ],
            "connection_error": [
                "Check your internet connection",
                "The service may be temporarily unavailable",
                "Try again later"
            ],
            "cloudflare_protection": [
                "The service is using Cloudflare protection",
                "Install cloudscraper: pip install cloudscraper",
                "Try again with different timing"
            ]
        }
        
        error_suggestions = suggestions.get(error.error_type, [
            "This may be a temporary issue",
            "Try again later",
            "Check if the URL is accessible in your browser"
        ])
        
        full_msg = f"{base_msg}.\n\nPossible solutions:\n"
        for i, suggestion in enumerate(error_suggestions, 1):
            full_msg += f"{i}. {suggestion}\n"
        
        return full_msg.strip()
    
    @staticmethod
    def should_retry(error: ExtractionError) -> bool:
        """Determine if the operation should be retried"""
        non_retryable_types = ["access_denied", "not_found", "json_parse_error"]
        return error.error_type not in non_retryable_types