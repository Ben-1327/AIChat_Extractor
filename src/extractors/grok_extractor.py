#!/usr/bin/env python3
"""
Grok Extractor for AI Chat Extractor
Extracts conversations from Grok (X.com) shared links.
"""

from typing import Optional
from bs4 import BeautifulSoup
import logging
from datetime import datetime

from models import Conversation, ChatMessage, MessageRole, ServiceType
from extractors.base_extractor import BaseExtractor

logger = logging.getLogger(__name__)

class GrokExtractor(BaseExtractor):
    """Extractor for Grok conversations"""
    
    def _parse_conversation(self, soup: BeautifulSoup, url: str) -> Optional[Conversation]:
        """
        Parse Grok conversation from HTML
        
        Args:
            soup: BeautifulSoup parsed HTML
            url: Original URL
            
        Returns:
            Conversation object or None if parsing failed
        """
        try:
            messages = []
            
            # Look for common patterns in Grok's HTML structure
            # Note: This is a placeholder implementation as the exact structure
            # would need to be determined from actual Grok share pages
            
            # Try to find conversation container
            conversation_container = (
                soup.find('div', {'data-testid': 'conversation'}) or
                soup.find('div', class_=lambda x: x and 'conversation' in x.lower()) or
                soup.find('main')
            )
            
            if not conversation_container:
                logger.warning("Could not find conversation container in Grok page")
                return None
            
            # Look for message elements
            message_elements = (
                conversation_container.find_all('div', {'data-testid': lambda x: x and 'message' in x}) or
                conversation_container.find_all('div', class_=lambda x: x and any(term in str(x).lower() for term in ['message', 'chat', 'response']))
            )
            
            if not message_elements:
                # Fallback: look for any div that might contain conversation text
                message_elements = conversation_container.find_all('div', string=True)
            
            sequence = 1
            for element in message_elements:
                content = self._clean_text(element.get_text())
                
                if not self._should_include_message(content):
                    continue
                
                # Determine message role based on context clues
                role = self._determine_message_role(element, content)
                
                message = ChatMessage(
                    role=role,
                    content=content,
                    sequence=sequence,
                    timestamp=datetime.now()  # Grok timestamps might not be available
                )
                
                messages.append(message)
                sequence += 1
            
            if not messages:
                logger.warning("No messages found in Grok conversation")
                return None
            
            # Try to extract title
            title = self._extract_title(soup)
            
            conversation = Conversation(
                messages=messages,
                service=ServiceType.GROK,
                title=title,
                url=url,
                extracted_at=datetime.now()
            )
            
            return conversation
            
        except Exception as e:
            logger.error(f"Error parsing Grok conversation: {e}")
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
        # Check for role indicators in classes or attributes
        element_str = str(element).lower()
        
        if any(indicator in element_str for indicator in ['user', 'human', 'you']):
            return MessageRole.USER
        elif any(indicator in element_str for indicator in ['grok', 'ai', 'assistant', 'bot']):
            return MessageRole.ASSISTANT
        
        # Fallback: alternate between user and assistant
        # This is a simple heuristic that might need refinement
        return MessageRole.USER if len(content) < 200 else MessageRole.ASSISTANT
    
    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract conversation title from page
        
        Args:
            soup: BeautifulSoup parsed HTML
            
        Returns:
            Title string or None
        """
        # Try various title selectors
        title_selectors = [
            'title',
            'h1',
            '[data-testid="conversation-title"]',
            '.conversation-title'
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                title = self._clean_text(element.get_text())
                if title and 'grok' not in title.lower():
                    return title
        
        return None