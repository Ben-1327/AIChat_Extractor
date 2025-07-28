#!/usr/bin/env python3
"""
Gemini Extractor for AI Chat Extractor
Extracts conversations from Gemini shared links.
"""

from typing import Optional
from bs4 import BeautifulSoup
import logging
from datetime import datetime

from models import Conversation, ChatMessage, MessageRole, ServiceType
from extractors.base_extractor import BaseExtractor

logger = logging.getLogger(__name__)

class GeminiExtractor(BaseExtractor):
    """Extractor for Gemini conversations"""
    
    def _parse_conversation(self, soup: BeautifulSoup, url: str) -> Optional[Conversation]:
        """
        Parse Gemini conversation from HTML
        
        Args:
            soup: BeautifulSoup parsed HTML
            url: Original URL
            
        Returns:
            Conversation object or None if parsing failed
        """
        try:
            messages = []
            
            # Look for Gemini-specific conversation structure
            conversation_container = (
                soup.find('div', {'role': 'main'}) or
                soup.find('div', class_=lambda x: x and 'conversation' in str(x).lower()) or
                soup.find('main') or
                soup.find('div', {'data-testid': lambda x: x and 'conversation' in str(x)})
            )
            
            if not conversation_container:
                logger.warning("Could not find conversation container in Gemini page")
                return None
            
            # Look for message elements with various possible selectors
            message_selectors = [
                '[data-testid*="message"]',
                '[class*="message"]',
                '[class*="turn"]',
                '.user-message, .model-message',  # Common Gemini classes
                'div[role="presentation"]'
            ]
            
            message_elements = []
            for selector in message_selectors:
                elements = conversation_container.select(selector)
                if elements:
                    message_elements = elements
                    break
            
            # Fallback: find divs that might contain conversation text
            if not message_elements:
                all_divs = conversation_container.find_all('div')
                message_elements = [div for div in all_divs if div.get_text().strip()]
            
            sequence = 1
            for element in message_elements:
                content = self._clean_text(element.get_text())
                
                if not self._should_include_message(content):
                    continue
                
                # Determine message role
                role = self._determine_message_role(element, content)
                
                message = ChatMessage(
                    role=role,
                    content=content,
                    sequence=sequence,
                    timestamp=datetime.now()
                )
                
                messages.append(message)
                sequence += 1
            
            if not messages:
                logger.warning("No messages found in Gemini conversation")
                return None
            
            # Try to extract title
            title = self._extract_title(soup)
            
            conversation = Conversation(
                messages=messages,
                service=ServiceType.GEMINI,
                title=title,
                url=url,
                extracted_at=datetime.now()
            )
            
            return conversation
            
        except Exception as e:
            logger.error(f"Error parsing Gemini conversation: {e}")
            return None
    
    def _determine_message_role(self, element, content: str) -> MessageRole:
        """
        Determine message role based on element context and content
        
        Args:
            element: BeautifulSoup element
            content: Message content
            
        Returns:
            MessageRole
        """
        element_str = str(element).lower()
        
        # Check for role indicators in attributes and classes
        if element.get('data-role'):
            role_attr = element.get('data-role').lower()
            if role_attr in ['user', 'human']:
                return MessageRole.USER
            elif role_attr in ['model', 'gemini', 'assistant']:
                return MessageRole.ASSISTANT
        
        # Check classes
        class_names = ' '.join(element.get('class', [])).lower()
        if any(indicator in class_names for indicator in ['user', 'human']):
            return MessageRole.USER
        elif any(indicator in class_names for indicator in ['model', 'gemini', 'assistant', 'ai']):
            return MessageRole.ASSISTANT
        
        # Check parent elements for context
        parent = element.parent
        if parent:
            parent_str = str(parent).lower()
            if any(indicator in parent_str for indicator in ['user', 'human']):
                return MessageRole.USER
            elif any(indicator in parent_str for indicator in ['model', 'gemini', 'assistant']):
                return MessageRole.ASSISTANT
        
        # Content-based heuristics
        # User messages tend to be shorter and more question-like
        if '?' in content or len(content.split()) < 30:
            return MessageRole.USER
        else:
            return MessageRole.ASSISTANT
    
    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract conversation title from page
        
        Args:
            soup: BeautifulSoup parsed HTML
            
        Returns:
            Title string or None
        """
        title_selectors = [
            'title',
            'h1',
            '[data-testid="conversation-title"]',
            'header h1',
            '.conversation-title',
            '[aria-label*="title"]'
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                title = self._clean_text(element.get_text())
                # Filter out generic Gemini page titles
                if title and not any(term in title.lower() for term in ['gemini', 'google', 'bard']):
                    return title
        
        return None