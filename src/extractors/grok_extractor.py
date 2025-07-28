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
            
            # Debug: Save HTML for analysis
            logger.debug("Analyzing Grok HTML structure...")
            
            # Look for script tags containing conversation data (common in modern SPAs)
            script_tags = soup.find_all('script')
            for script in script_tags:
                if script.string and ('conversation' in script.string.lower() or 'messages' in script.string.lower() or 'chat' in script.string.lower()):
                    logger.debug(f"Found potentially relevant script tag: {script.string[:200]}...")
                    # Try to extract JSON data
                    try:
                        import json
                        import re
                        
                        # Look for JSON patterns including Next.js streaming data
                        json_patterns = [
                            r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
                            r'window\.__NUXT__\s*=\s*({.*?});',
                            r'window\.__APP_STATE__\s*=\s*({.*?});',
                            r'"messages"\s*:\s*\[.*?\]',
                            r'"conversation"\s*:\s*{.*?}',
                            # Next.js streaming data patterns
                            r'self\.__next_f\.push\(\[.*?"conversation".*?\]\)',
                            r'"conversation":\s*{[^}]*"conversationId"[^}]*}',
                            r'"shareLinkId"[^}]*"conversation"[^}]*}',
                        ]
                        
                        # Special handling for Next.js streaming data
                        if 'self.__next_f.push' in script.string:
                            logger.debug("Found Next.js streaming data - attempting extraction...")
                            extracted_messages = self._extract_from_nextjs_stream(script.string)
                            if extracted_messages:
                                messages.extend(extracted_messages)
                                logger.info(f"Extracted {len(extracted_messages)} messages from Next.js stream")
                                continue
                        
                        for pattern in json_patterns:
                            matches = re.search(pattern, script.string, re.DOTALL)
                            if matches:
                                logger.debug(f"Found JSON pattern: {pattern}")
                                try:
                                    json_data = json.loads(matches.group(1))
                                    logger.debug(f"Successfully parsed JSON data")
                                    # Try to extract messages from JSON
                                    extracted_messages = self._extract_from_json(json_data)
                                    if extracted_messages:
                                        messages.extend(extracted_messages)
                                        logger.info(f"Extracted {len(extracted_messages)} messages from JSON")
                                except json.JSONDecodeError:
                                    continue
                    except Exception as e:
                        logger.debug(f"Error parsing script content: {e}")
            
            # If JSON extraction worked, return those messages
            if messages:
                title = self._extract_title(soup)
                conversation = Conversation(
                    messages=messages,
                    service=ServiceType.GROK,
                    title=title,
                    url=url,
                    extracted_at=datetime.now()
                )
                return conversation
            
            # Fallback to HTML parsing
            logger.debug("Falling back to HTML parsing...")
            
            # Try to find conversation container with more patterns
            conversation_selectors = [
                'div[data-testid="conversation"]',
                'div[class*="conversation"]',
                'div[class*="chat"]',
                'div[class*="message"]',
                'main',
                'div[role="main"]',
                'article',
                'section',
                '#root',
                '.app',
                '[data-testid*="chat"]',
                '[data-testid*="message"]'
            ]
            
            conversation_container = None
            for selector in conversation_selectors:
                container = soup.select_one(selector)
                if container:
                    logger.debug(f"Found container with selector: {selector}")
                    conversation_container = container
                    break
            
            if not conversation_container:
                logger.warning("Could not find conversation container in Grok page")
                # Debug: Print page structure
                logger.debug("Page structure analysis:")
                for tag in soup.find_all(['div', 'main', 'article', 'section'], limit=20):
                    classes = tag.get('class', [])
                    test_id = tag.get('data-testid', '')
                    role = tag.get('role', '')
                    id_attr = tag.get('id', '')
                    logger.debug(f"Tag: {tag.name}, classes: {classes}, testid: {test_id}, role: {role}, id: {id_attr}")
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
    
    def _extract_from_json(self, json_data: dict) -> list:
        """
        Extract messages from JSON data
        
        Args:
            json_data: Parsed JSON data
            
        Returns:
            List of ChatMessage objects
        """
        messages = []
        
        try:
            # Try different paths to find messages
            possible_paths = [
                ['conversation', 'messages'],
                ['messages'],
                ['chat', 'messages'],
                ['data', 'conversation', 'messages'],
                ['state', 'conversation', 'messages'],
                ['props', 'pageProps', 'conversation', 'messages']
            ]
            
            conversation_data = None
            for path in possible_paths:
                current = json_data
                try:
                    for key in path:
                        current = current[key]
                    if isinstance(current, list):
                        conversation_data = current
                        logger.debug(f"Found messages at path: {' -> '.join(path)}")
                        break
                except (KeyError, TypeError):
                    continue
            
            if not conversation_data:
                # Fallback: recursively search for any list that might contain messages
                conversation_data = self._find_messages_recursively(json_data)
            
            if not conversation_data:
                logger.debug("No message data found in JSON")
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
                    msg_data.get('type') or
                    'user'
                ).lower()
                
                content = (
                    msg_data.get('content') or 
                    msg_data.get('text') or 
                    msg_data.get('message') or 
                    msg_data.get('body') or
                    ''
                )
                
                if isinstance(content, list):
                    content = ' '.join(str(item) for item in content)
                elif isinstance(content, dict):
                    # Handle nested content structure
                    content = content.get('text') or content.get('content') or str(content)
                
                content = self._clean_text(str(content))
                
                if not self._should_include_message(content):
                    continue
                
                # Map role
                if role_str in ['user', 'human']:
                    role = MessageRole.USER
                elif role_str in ['assistant', 'grok', 'ai', 'bot', 'model']:
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
            
        except Exception as e:
            logger.debug(f"Error extracting from JSON: {e}")
            return messages
    
    def _find_messages_recursively(self, data, depth=0, max_depth=5):
        """
        Recursively search for message-like data structures
        
        Args:
            data: Data to search
            depth: Current recursion depth
            max_depth: Maximum recursion depth
            
        Returns:
            List of potential message objects or None
        """
        if depth > max_depth:
            return None
        
        if isinstance(data, dict):
            # Look for message-related keys
            for key, value in data.items():
                if key.lower() in ['messages', 'conversation', 'chat', 'turns']:
                    if isinstance(value, list) and len(value) > 0:
                        # Check if this looks like a message list
                        first_item = value[0]
                        if isinstance(first_item, dict) and any(k in first_item for k in ['content', 'text', 'message', 'role']):
                            logger.debug(f"Found potential messages under key: {key}")
                            return value
                
                # Recurse into nested structures
                result = self._find_messages_recursively(value, depth + 1, max_depth)
                if result:
                    return result
        
        elif isinstance(data, list):
            for item in data:
                result = self._find_messages_recursively(item, depth + 1, max_depth)
                if result:
                    return result
        
        return None
    
    def _extract_from_nextjs_stream(self, script_content: str) -> list:
        """
        Extract messages from Next.js streaming data format
        
        Args:
            script_content: JavaScript content containing Next.js stream data
            
        Returns:
            List of ChatMessage objects
        """
        messages = []
        
        try:
            import json
            import re
            
            logger.debug("Parsing Next.js streaming data...")
            
            # Find all Next.js stream push calls
            # Pattern: self.__next_f.push([number,"data"])
            stream_pattern = r'self\.__next_f\.push\(\[(\d+),"([^"]*?)"\]\)'
            matches = re.finditer(stream_pattern, script_content)
            
            for match in matches:
                stream_id = match.group(1)
                data_str = match.group(2)
                
                # Unescape the JSON string
                data_str = data_str.replace('\\"', '"').replace('\\\\', '\\')
                
                logger.debug(f"Found stream data {stream_id}: {data_str[:200]}...")
                
                # Look for conversation data in the stream
                if 'conversation' in data_str and 'shareLinkId' in data_str:
                    logger.debug("Found conversation stream data - attempting to parse...")
                    
                    # Try to extract JSON from the stream data
                    # Pattern: "[\"$\",\"$L26\",null,{...}]"
                    json_pattern = r'\[.*?\{.*?"conversation".*?\}.*?\]'
                    json_match = re.search(json_pattern, data_str, re.DOTALL)
                    
                    if json_match:
                        try:
                            # Parse the JSON array
                            json_data = json.loads(json_match.group(0))
                            logger.debug(f"Successfully parsed stream JSON: {type(json_data)}")
                            
                            # Extract conversation data from the array
                            # Usually in format: ["$", "component", null, {props}]
                            if isinstance(json_data, list) and len(json_data) >= 4:
                                props = json_data[3]  # Props object is typically at index 3
                                if isinstance(props, dict) and 'conversation' in props:
                                    conversation_data = props['conversation']
                                    logger.debug("Found conversation data in props")
                                    
                                    # Extract messages from conversation
                                    extracted_messages = self._extract_messages_from_conversation_data(conversation_data)
                                    if extracted_messages:
                                        messages.extend(extracted_messages)
                                        logger.info(f"Extracted {len(extracted_messages)} messages from Next.js stream")
                                        
                        except json.JSONDecodeError as e:
                            logger.debug(f"Failed to parse stream JSON: {e}")
                            continue
                    
                    # Alternative approach: look for direct conversation object patterns
                    if not messages:
                        conv_pattern = r'"conversation"\s*:\s*(\{[^}]*?"messages"[^}]*?\})'
                        conv_match = re.search(conv_pattern, data_str, re.DOTALL)
                        if conv_match:
                            try:
                                conv_json = json.loads(conv_match.group(1))
                                extracted_messages = self._extract_messages_from_conversation_data(conv_json)
                                if extracted_messages:
                                    messages.extend(extracted_messages)
                                    logger.info(f"Extracted {len(extracted_messages)} messages from conversation pattern")
                            except json.JSONDecodeError:
                                continue
            
            return messages
            
        except Exception as e:
            logger.debug(f"Error parsing Next.js stream: {e}")
            return messages
    
    def _extract_messages_from_conversation_data(self, conversation_data: dict) -> list:
        """
        Extract messages from conversation data structure
        
        Args:
            conversation_data: Dictionary containing conversation information
            
        Returns:
            List of ChatMessage objects
        """
        messages = []
        
        try:
            # Look for messages in various possible locations
            messages_data = None
            
            # Try different paths to find messages
            possible_paths = [
                ['messages'],
                ['turns'],
                ['entries'],
                ['conversationHistory'],
                ['history'],
                ['data', 'messages'],
                ['conversation', 'messages']
            ]
            
            for path in possible_paths:
                current = conversation_data
                try:
                    for key in path:
                        current = current[key]
                    if isinstance(current, list):
                        messages_data = current
                        logger.debug(f"Found messages at path: {' -> '.join(path)}")
                        break
                except (KeyError, TypeError):
                    continue
            
            if not messages_data:
                logger.debug("No messages array found in conversation data")
                return messages
            
            sequence = 1
            for msg_data in messages_data:
                if not isinstance(msg_data, dict):
                    continue
                
                # Extract content with various possible keys
                content = (
                    msg_data.get('content') or
                    msg_data.get('text') or
                    msg_data.get('message') or
                    msg_data.get('body') or
                    msg_data.get('prompt') or
                    ''
                )
                
                # Handle nested content structure
                if isinstance(content, dict):
                    content = (
                        content.get('text') or
                        content.get('content') or
                        content.get('message') or
                        str(content)
                    )
                elif isinstance(content, list):
                    # Join list items or extract text from objects
                    content_parts = []
                    for item in content:
                        if isinstance(item, dict):
                            content_parts.append(item.get('text') or item.get('content') or str(item))
                        else:
                            content_parts.append(str(item))
                    content = ' '.join(content_parts)
                
                content = self._clean_text(str(content))
                
                if not self._should_include_message(content):
                    continue
                
                # Extract role
                role_str = (
                    msg_data.get('role') or
                    msg_data.get('sender') or
                    msg_data.get('author') or
                    msg_data.get('type') or
                    msg_data.get('from') or
                    'user'
                ).lower()
                
                # Map role to MessageRole
                if role_str in ['user', 'human', 'you']:
                    role = MessageRole.USER
                elif role_str in ['assistant', 'grok', 'ai', 'bot', 'model', 'system']:
                    role = MessageRole.ASSISTANT
                else:
                    # Fallback: alternate based on sequence
                    role = MessageRole.USER if sequence % 2 == 1 else MessageRole.ASSISTANT
                
                message = ChatMessage(
                    role=role,
                    content=content,
                    sequence=sequence
                )
                
                messages.append(message)
                sequence += 1
                logger.debug(f"Extracted message {sequence-1}: {role.value} - {content[:100]}...")
            
            return messages
            
        except Exception as e:
            logger.debug(f"Error extracting from conversation data: {e}")
            return messages
    
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