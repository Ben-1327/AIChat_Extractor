#!/usr/bin/env python3
"""
ChatGPT Extractor for AI Chat Extractor
Extracts conversations from ChatGPT shared links.
"""

from typing import Optional
from bs4 import BeautifulSoup
import logging
from datetime import datetime
import json

from models import Conversation, ChatMessage, MessageRole, ServiceType
from extractors.base_extractor import BaseExtractor

logger = logging.getLogger(__name__)

class ChatGPTExtractor(BaseExtractor):
    """Extractor for ChatGPT conversations"""
    
    def _parse_conversation(self, soup: BeautifulSoup, url: str) -> Optional[Conversation]:
        """
        Parse ChatGPT conversation from HTML
        
        Args:
            soup: BeautifulSoup parsed HTML
            url: Original URL
            
        Returns:
            Conversation object or None if parsing failed
        """
        try:
            messages = []
            
            # ChatGPT shared conversations often have a specific structure
            # Look for conversation data in script tags first
            conversation_data = self._extract_from_script_tags(soup)
            if conversation_data:
                messages = self._parse_from_json_data(conversation_data)
            
            # Fallback to HTML parsing if JSON extraction fails
            if not messages:
                messages = self._parse_from_html(soup)
            
            if not messages:
                logger.warning("No messages found in ChatGPT conversation")
                return None
            
            # Try to extract title
            title = self._extract_title(soup)
            
            conversation = Conversation(
                messages=messages,
                service=ServiceType.CHATGPT,
                title=title,
                url=url,
                extracted_at=datetime.now()
            )
            
            return conversation
            
        except Exception as e:
            logger.error(f"Error parsing ChatGPT conversation: {e}")
            return None
    
    def _extract_from_script_tags(self, soup: BeautifulSoup) -> Optional[dict]:
        """
        Extract conversation data from script tags
        
        Args:
            soup: BeautifulSoup parsed HTML
            
        Returns:
            Conversation data dictionary or None
        """
        script_tags = soup.find_all('script')
        
        for script in script_tags:
            if not script.string:
                continue
                
            script_content = script.string.strip()
            
            # Look for JSON data that might contain conversation
            if 'conversation' in script_content.lower() or 'messages' in script_content.lower():
                try:
                    # Try to extract JSON from various patterns
                    if script_content.startswith('window.__INITIAL_STATE__'):
                        json_str = script_content.split('=', 1)[1].strip().rstrip(';')
                        return json.loads(json_str)
                    elif script_content.startswith('{') and script_content.endswith('}'):
                        return json.loads(script_content)
                except json.JSONDecodeError:
                    continue
        
        return None
    
    def _parse_from_json_data(self, data: dict) -> list:
        """
        Parse messages from JSON data
        
        Args:
            data: JSON data dictionary
            
        Returns:
            List of ChatMessage objects
        """
        messages = []
        
        # Navigate through common JSON structures
        conversation_data = (
            data.get('conversation', {}) or
            data.get('messages', []) or
            data.get('chat', {})
        )
        
        if isinstance(conversation_data, dict):
            conversation_data = conversation_data.get('messages', [])
        
        sequence = 1
        for msg_data in conversation_data:
            if not isinstance(msg_data, dict):
                continue
            
            role_str = msg_data.get('role', msg_data.get('author', {}).get('role', 'user'))
            content = msg_data.get('content', '')
            
            if isinstance(content, dict):
                # Handle nested content structure
                content = content.get('parts', [''])[0] if 'parts' in content else str(content)
            
            content = self._clean_text(str(content))
            
            if not self._should_include_message(content):
                continue
            
            # Map role
            if role_str.lower() in ['user', 'human']:
                role = MessageRole.USER
            elif role_str.lower() in ['assistant', 'chatgpt', 'gpt']:
                role = MessageRole.ASSISTANT
            else:
                role = MessageRole.SYSTEM
            
            message = ChatMessage(
                role=role,
                content=content,
                sequence=sequence
            )
            
            messages.append(message)
            sequence += 1
        
        return messages
    
    def _parse_from_html(self, soup: BeautifulSoup) -> list:
        """
        Parse messages from HTML structure
        
        Args:
            soup: BeautifulSoup parsed HTML
            
        Returns:
            List of ChatMessage objects
        """
        messages = []
        
        # Look for common ChatGPT message containers
        message_selectors = [
            '[data-message-author-role]',
            '.conversation-turn',
            '[class*="message"]',
            '[class*="conversation"]'
        ]
        
        message_elements = []
        for selector in message_selectors:
            elements = soup.select(selector)
            if elements:
                message_elements = elements
                break
        
        sequence = 1
        for element in message_elements:
            content = self._clean_text(element.get_text())
            
            if not self._should_include_message(content):
                continue
            
            # Determine role from element attributes or content
            role = self._determine_message_role(element, content)
            
            message = ChatMessage(
                role=role,
                content=content,
                sequence=sequence,
                timestamp=datetime.now()
            )
            
            messages.append(message)
            sequence += 1
        
        return messages
    
    def _determine_message_role(self, element, content: str) -> MessageRole:
        """
        Determine message role based on element context
        
        Args:
            element: BeautifulSoup element
            content: Message content
            
        Returns:
            MessageRole
        """
        # Check data attributes
        role_attr = element.get('data-message-author-role')
        if role_attr:
            if role_attr.lower() in ['user', 'human']:
                return MessageRole.USER
            elif role_attr.lower() in ['assistant', 'chatgpt']:
                return MessageRole.ASSISTANT
        
        # Check classes
        class_str = ' '.join(element.get('class', [])).lower()
        if any(indicator in class_str for indicator in ['user', 'human']):
            return MessageRole.USER
        elif any(indicator in class_str for indicator in ['assistant', 'gpt', 'ai']):
            return MessageRole.ASSISTANT
        
        # Fallback heuristic
        return MessageRole.USER if len(content.split()) < 50 else MessageRole.ASSISTANT
    
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
            '.conversation-header h1',
            'header h1'
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                title = self._clean_text(element.get_text())
                # Filter out generic ChatGPT page titles
                if title and not any(term in title.lower() for term in ['chatgpt', 'openai', 'share']):
                    return title
        
        return None