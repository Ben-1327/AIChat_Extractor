#!/usr/bin/env python3
"""
Claude Extractor for AI Chat Extractor
Extracts conversations from Claude shared links.
"""

from typing import Optional
from bs4 import BeautifulSoup
import logging
from datetime import datetime
import json

from models import Conversation, ChatMessage, MessageRole, ServiceType
from extractors.base_extractor import BaseExtractor

logger = logging.getLogger(__name__)

class ClaudeExtractor(BaseExtractor):
    """Extractor for Claude conversations"""
    
    def _parse_conversation(self, soup: BeautifulSoup, url: str) -> Optional[Conversation]:
        """
        Parse Claude conversation from HTML
        
        Args:
            soup: BeautifulSoup parsed HTML
            url: Original URL
            
        Returns:
            Conversation object or None if parsing failed
        """
        try:
            messages = []
            
            # Try to extract from script tags first (Claude often embeds data in JS)
            conversation_data = self._extract_from_script_tags(soup)
            if conversation_data:
                messages = self._parse_from_json_data(conversation_data)
            
            # Fallback to HTML parsing
            if not messages:
                messages = self._parse_from_html(soup)
            
            if not messages:
                logger.warning("No messages found in Claude conversation")
                return None
            
            # Try to extract title
            title = self._extract_title(soup)
            
            conversation = Conversation(
                messages=messages,
                service=ServiceType.CLAUDE,
                title=title,
                url=url,
                extracted_at=datetime.now()
            )
            
            return conversation
            
        except Exception as e:
            logger.error(f"Error parsing Claude conversation: {e}")
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
            
            # Look for JSON data containing conversation
            if any(keyword in script_content.lower() for keyword in ['conversation', 'messages', 'chat']):
                try:
                    # Common patterns for embedded data
                    if 'window.__INITIAL_STATE__' in script_content:
                        json_str = script_content.split('=', 1)[1].strip().rstrip(';')
                        return json.loads(json_str)
                    elif script_content.startswith('{') and script_content.endswith('}'):
                        return json.loads(script_content)
                    elif '"messages"' in script_content:
                        # Try to extract JSON from various embedding patterns
                        import re
                        json_match = re.search(r'\{.*"messages".*\}', script_content, re.DOTALL)
                        if json_match:
                            return json.loads(json_match.group())
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
        
        # Navigate through possible JSON structures
        conversation_data = None
        
        # Try different paths to find messages
        possible_paths = [
            ['conversation', 'messages'],
            ['messages'],
            ['chat', 'messages'],
            ['data', 'conversation', 'messages']
        ]
        
        for path in possible_paths:
            current = data
            try:
                for key in path:
                    current = current[key]
                if isinstance(current, list):
                    conversation_data = current
                    break
            except (KeyError, TypeError):
                continue
        
        if not conversation_data:
            # Fallback: look for any list that might contain messages
            for value in data.values():
                if isinstance(value, list) and value:
                    first_item = value[0]
                    if isinstance(first_item, dict) and any(key in first_item for key in ['role', 'content', 'text']):
                        conversation_data = value
                        break
        
        if not conversation_data:
            return messages
        
        sequence = 1
        for msg_data in conversation_data:
            if not isinstance(msg_data, dict):
                continue
            
            # Extract role and content with various possible keys
            role_str = (
                msg_data.get('role') or 
                msg_data.get('sender') or 
                msg_data.get('author') or 
                'user'
            ).lower()
            
            content = (
                msg_data.get('content') or 
                msg_data.get('text') or 
                msg_data.get('message') or 
                ''
            )
            
            if isinstance(content, list):
                content = ' '.join(str(item) for item in content)
            
            content = self._clean_text(str(content))
            
            if not self._should_include_message(content):
                continue
            
            # Map role
            if role_str in ['user', 'human']:
                role = MessageRole.USER
            elif role_str in ['assistant', 'claude', 'ai']:
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
        
        # Look for Claude-specific message containers
        conversation_container = (
            soup.find('div', {'data-testid': 'conversation'}) or
            soup.find('div', class_=lambda x: x and 'conversation' in str(x).lower()) or
            soup.find('main') or
            soup.find('div', {'role': 'main'})
        )
        
        if not conversation_container:
            conversation_container = soup
        
        # Try various selectors for message elements
        message_selectors = [
            '[data-testid*="message"]',
            '[class*="message"]',
            '.human-message, .assistant-message',
            '[role="presentation"]',
            'div[data-role]'
        ]
        
        message_elements = []
        for selector in message_selectors:
            elements = conversation_container.select(selector)
            if elements:
                message_elements = elements
                break
        
        # Fallback: look for alternating content blocks
        if not message_elements:
            # Find divs that might contain substantial text
            all_divs = conversation_container.find_all('div')
            message_elements = [
                div for div in all_divs 
                if len(div.get_text().strip()) > 50  # Reasonable message length
            ]
        
        sequence = 1
        for element in message_elements:
            content = self._clean_text(element.get_text())
            
            if not self._should_include_message(content):
                continue
            
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
        if element.get('data-role'):
            role_attr = element.get('data-role').lower()
            if role_attr in ['user', 'human']:
                return MessageRole.USER
            elif role_attr in ['assistant', 'claude']:
                return MessageRole.ASSISTANT
        
        # Check classes
        class_names = ' '.join(element.get('class', [])).lower()
        if any(indicator in class_names for indicator in ['user', 'human']):
            return MessageRole.USER
        elif any(indicator in class_names for indicator in ['assistant', 'claude', 'ai']):
            return MessageRole.ASSISTANT
        
        # Content-based heuristics for Claude
        # User messages often start with questions or are shorter
        if content.strip().endswith('?') or len(content.split()) < 40:
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
            '.conversation-title'
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                title = self._clean_text(element.get_text())
                # Filter out generic Claude page titles
                if title and not any(term in title.lower() for term in ['claude', 'anthropic']):
                    return title
        
        return None