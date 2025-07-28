#!/usr/bin/env python3
"""
HTML-based Extraction Components for AI Chat Extractor
Provides fallback HTML extraction when JSON methods fail.
"""

import logging
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup
from datetime import datetime

from models import ChatMessage, MessageRole, ServiceType
from extractors.common_extractor import ExtractionStrategy, ExtractionResult

logger = logging.getLogger(__name__)

class HTMLExtractionStrategy(ExtractionStrategy):
    """Strategy for HTML DOM-based extraction"""
    
    def __init__(self, service_type: ServiceType):
        self.service_type = service_type
        self.selectors = self._get_service_selectors()
    
    def _get_service_selectors(self) -> Dict[str, List[str]]:
        """Get service-specific CSS selectors"""
        base_selectors = {
            'conversation_containers': [
                '[data-testid="conversation"]',
                '[data-testid*="chat"]',
                'div[role="main"]',
                'main',
                '.conversation',
                '.chat-container',
                'article',
                'section'
            ],
            'message_elements': [
                '[data-testid*="message"]',
                '[data-message-author-role]',
                '.message',
                '.conversation-turn',
                '[class*="message"]',
                '[class*="turn"]',
                'div[role="presentation"]'
            ]
        }
        
        # Service-specific additions
        if self.service_type == ServiceType.CHATGPT:
            base_selectors['message_elements'].extend([
                '.user-message',
                '.assistant-message',
                '[data-testid="conversation-turn"]'
            ])
        elif self.service_type == ServiceType.CLAUDE:
            base_selectors['message_elements'].extend([
                '.human-message',
                '.assistant-message',
                '[data-role]'
            ])
        elif self.service_type == ServiceType.GEMINI:
            base_selectors['message_elements'].extend([
                '.user-message',
                '.model-message',
                '[data-role]'
            ])
        elif self.service_type == ServiceType.GROK:
            base_selectors['message_elements'].extend([
                '.grok-message',
                '.user-message',
                '[data-testid*="grok"]'
            ])
        
        return base_selectors
    
    def extract(self, soup: BeautifulSoup, url: str) -> ExtractionResult:
        """Extract using HTML DOM parsing"""
        try:
            # Find conversation container
            container = self._find_conversation_container(soup)
            if not container:
                logger.debug("No conversation container found")
                return ExtractionResult([], method="html", confidence=0.0)
            
            # Extract messages
            messages = self._extract_messages_from_container(container)
            
            # Extract title
            title = self._extract_title(soup)
            
            confidence = self.get_confidence_score(soup) if messages else 0.0
            
            return ExtractionResult(
                messages=messages,
                title=title,
                method="html",
                confidence=confidence
            )
        
        except Exception as e:
            logger.debug(f"HTML extraction failed: {e}")
            return ExtractionResult([], method="html", confidence=0.0)
    
    def get_confidence_score(self, soup: BeautifulSoup) -> float:
        """Calculate confidence score based on HTML structure"""
        score = 0.0
        
        # Check for conversation container
        container = self._find_conversation_container(soup)
        if container:
            score += 0.3
        
        # Check for message elements
        message_elements = self._find_message_elements(soup)
        if message_elements:
            score += 0.4
            # More messages = higher confidence
            score += min(0.3, len(message_elements) * 0.05)
        
        return min(1.0, score)
    
    def _find_conversation_container(self, soup: BeautifulSoup) -> Optional[Any]:
        """Find the main conversation container"""
        for selector in self.selectors['conversation_containers']:
            container = soup.select_one(selector)
            if container:
                # Verify it contains substantial content
                text_content = container.get_text().strip()
                if len(text_content) > 100:  # Reasonable threshold
                    logger.debug(f"Found conversation container with selector: {selector}")
                    return container
        
        # Fallback: use body if nothing else works
        return soup.find('body') or soup
    
    def _find_message_elements(self, container: Any) -> List[Any]:
        """Find message elements within container"""
        message_elements = []
        
        for selector in self.selectors['message_elements']:
            elements = container.select(selector)
            if elements:
                # Filter elements with substantial content
                substantial_elements = [
                    elem for elem in elements 
                    if len(elem.get_text().strip()) > 10
                ]
                if substantial_elements:
                    logger.debug(f"Found {len(substantial_elements)} messages with selector: {selector}")
                    return substantial_elements
        
        # Fallback: look for divs with substantial text
        all_divs = container.find_all('div')
        potential_messages = [
            div for div in all_divs 
            if 50 < len(div.get_text().strip()) < 5000  # Reasonable message length
            and not self._is_likely_ui_element(div)
        ]
        
        if potential_messages:
            logger.debug(f"Found {len(potential_messages)} potential message divs as fallback")
        
        return potential_messages
    
    def _is_likely_ui_element(self, element: Any) -> bool:
        """Check if element is likely a UI element rather than message content"""
        element_str = str(element).lower()
        ui_indicators = [
            'button', 'nav', 'header', 'footer', 'sidebar', 'menu',
            'toolbar', 'controls', 'settings', 'preferences'
        ]
        
        # Check classes and other attributes
        classes = element.get('class', [])
        class_str = ' '.join(classes).lower()
        
        return any(indicator in element_str or indicator in class_str 
                  for indicator in ui_indicators)
    
    def _extract_messages_from_container(self, container: Any) -> List[ChatMessage]:
        """Extract messages from conversation container"""
        message_elements = self._find_message_elements(container)
        
        if not message_elements:
            return []
        
        messages = []
        sequence = 1
        
        for element in message_elements:
            content = self._clean_text(element.get_text())
            
            if not content or len(content.strip()) < 5:
                continue
            
            # Determine role
            role = self._determine_message_role(element, content, sequence)
            
            message = ChatMessage(
                role=role,
                content=content,
                sequence=sequence,
                timestamp=datetime.now()
            )
            
            messages.append(message)
            sequence += 1
        
        return messages
    
    def _determine_message_role(self, element: Any, content: str, sequence: int) -> MessageRole:
        """Determine message role from element context"""
        # Check data attributes
        role_attr = element.get('data-message-author-role') or element.get('data-role')
        if role_attr:
            role_str = role_attr.lower()
            if role_str in ['user', 'human']:
                return MessageRole.USER
            elif role_str in ['assistant', 'ai', 'bot', 'model']:
                return MessageRole.ASSISTANT
            elif self.service_type == ServiceType.CHATGPT and role_str in ['chatgpt', 'gpt']:
                return MessageRole.ASSISTANT
            elif self.service_type == ServiceType.CLAUDE and role_str in ['claude']:
                return MessageRole.ASSISTANT
            elif self.service_type == ServiceType.GEMINI and role_str in ['gemini', 'bard']:
                return MessageRole.ASSISTANT
            elif self.service_type == ServiceType.GROK and role_str in ['grok']:
                return MessageRole.ASSISTANT
        
        # Check classes
        classes = element.get('class', [])
        class_str = ' '.join(classes).lower()
        
        user_indicators = ['user', 'human', 'you']
        assistant_indicators = ['assistant', 'ai', 'bot', 'model', 'gpt', 'claude', 'gemini', 'grok']
        
        if any(indicator in class_str for indicator in user_indicators):
            return MessageRole.USER
        elif any(indicator in class_str for indicator in assistant_indicators):
            return MessageRole.ASSISTANT
        
        # Check parent element context
        parent = element.parent
        if parent:
            parent_str = str(parent).lower()
            if any(indicator in parent_str for indicator in user_indicators):
                return MessageRole.USER
            elif any(indicator in parent_str for indicator in assistant_indicators):
                return MessageRole.ASSISTANT
        
        # Content-based heuristics
        if self._looks_like_user_message(content):
            return MessageRole.USER
        elif self._looks_like_assistant_message(content):
            return MessageRole.ASSISTANT
        
        # Final fallback: alternate based on sequence (assuming user starts)
        return MessageRole.USER if sequence % 2 == 1 else MessageRole.ASSISTANT
    
    def _looks_like_user_message(self, content: str) -> bool:
        """Check if content looks like a user message"""
        # User messages are often shorter and more question-like
        word_count = len(content.split())
        
        # Questions
        if content.strip().endswith('?'):
            return True
        
        # Short commands or requests
        if word_count < 20 and any(word in content.lower() 
                                 for word in ['please', 'can you', 'help', 'explain', 'tell me']):
            return True
        
        # Very short messages are likely from users
        if word_count < 10:
            return True
        
        return False
    
    def _looks_like_assistant_message(self, content: str) -> bool:
        """Check if content looks like an assistant message"""
        word_count = len(content.split())
        
        # Long detailed responses
        if word_count > 100:
            return True
        
        # Structured responses with formatting
        if any(indicator in content for indicator in ['# ', '## ', '1. ', '2. ', '- ', '* ']):
            return True
        
        # Professional/helpful language patterns
        helpful_patterns = [
            'I can help', 'I\'ll help', 'Here\'s', 'Let me', 'I understand',
            'Based on', 'According to', 'In summary', 'To answer'
        ]
        
        if any(pattern in content for pattern in helpful_patterns):
            return True
        
        return False
    
    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract conversation title from HTML"""
        title_selectors = [
            'title',
            'h1',
            '[data-testid="conversation-title"]',
            '.conversation-title',
            'header h1',
            '[aria-label*="title" i]'
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                title = self._clean_text(element.get_text())
                
                # Filter out generic titles
                if title and self._is_meaningful_title(title):
                    return title
        
        return None
    
    def _is_meaningful_title(self, title: str) -> bool:
        """Check if title is meaningful (not generic service name)"""
        title_lower = title.lower()
        
        # Generic terms to exclude
        generic_terms = [
            'chatgpt', 'claude', 'gemini', 'grok', 'bard',
            'openai', 'anthropic', 'google', 'x.com',
            'share', 'shared', 'conversation', 'chat'
        ]
        
        # Must have reasonable length
        if len(title.strip()) < 3:
            return False
        
        # Must not be just generic terms
        if any(term in title_lower for term in generic_terms) and len(title) < 50:
            return False
        
        return True
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ""
        
        # Remove extra whitespace and normalize
        text = ' '.join(text.split())
        
        # Remove HTML entities
        from html import unescape
        text = unescape(text)
        
        return text.strip()

class TextPatternExtractionStrategy(ExtractionStrategy):
    """Strategy for text pattern-based extraction (last resort)"""
    
    def __init__(self, service_type: ServiceType):
        self.service_type = service_type
    
    def extract(self, soup: BeautifulSoup, url: str) -> ExtractionResult:
        """Extract using text patterns as last resort"""
        try:
            # Get all text content
            text_content = soup.get_text()
            
            if len(text_content.strip()) < 100:
                return ExtractionResult([], method="text_pattern", confidence=0.0)
            
            # Try to find conversation patterns
            messages = self._extract_from_text_patterns(text_content)
            
            confidence = 0.2 if messages else 0.0  # Low confidence for text patterns
            
            return ExtractionResult(
                messages=messages,
                title=None,  # Usually can't extract meaningful title from text patterns
                method="text_pattern",
                confidence=confidence
            )
        
        except Exception as e:
            logger.debug(f"Text pattern extraction failed: {e}")
            return ExtractionResult([], method="text_pattern", confidence=0.0)
    
    def get_confidence_score(self, soup: BeautifulSoup) -> float:
        """Always low confidence for this fallback method"""
        return 0.2
    
    def _extract_from_text_patterns(self, text: str) -> List[ChatMessage]:
        """Extract messages from text using pattern matching"""
        messages = []
        
        # This is a very basic implementation
        # In practice, you'd implement more sophisticated pattern matching
        # based on the specific service's text formatting
        
        # Split text into potential sections
        lines = text.split('\n')
        current_content = []
        sequence = 1
        
        for line in lines:
            line = line.strip()
            
            if not line:
                continue
            
            # Simple heuristic: long lines might be message content
            if len(line) > 50:
                current_content.append(line)
            
            # If we have accumulated content and hit a potential boundary
            elif current_content and len(' '.join(current_content)) > 100:
                content = ' '.join(current_content)
                
                # Determine role (very basic heuristic)
                role = MessageRole.USER if sequence % 2 == 1 else MessageRole.ASSISTANT
                
                message = ChatMessage(
                    role=role,
                    content=content,
                    sequence=sequence,
                    timestamp=datetime.now()
                )
                
                messages.append(message)
                sequence += 1
                current_content = []
        
        # Add any remaining content
        if current_content:
            content = ' '.join(current_content)
            if len(content) > 50:
                role = MessageRole.USER if sequence % 2 == 1 else MessageRole.ASSISTANT
                message = ChatMessage(
                    role=role,
                    content=content,
                    sequence=sequence,
                    timestamp=datetime.now()
                )
                messages.append(message)
        
        return messages