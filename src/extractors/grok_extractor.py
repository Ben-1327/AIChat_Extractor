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
            conversation_info = None
            all_text_content = []
            
            for script in script_tags:
                if script.string and ('conversation' in script.string.lower() or 'messages' in script.string.lower() or 'chat' in script.string.lower()):
                    logger.debug(f"Found potentially relevant script tag: {script.string[:200]}...")
                    # Try to extract JSON data
                    try:
                        import json
                        import re
                        
                        # Special handling for Next.js streaming data
                        if 'self.__next_f.push' in script.string:
                            logger.debug("Found Next.js streaming data - attempting extraction...")
                            
                            # Extract conversation metadata first
                            if not conversation_info:
                                conversation_info = self._extract_conversation_info(script.string)
                            
                            # Extract text content from this script
                            text_content = self._extract_text_content_from_stream(script.string)
                            if text_content:
                                all_text_content.extend(text_content)
                            
                            # Try the original extraction method as fallback
                            extracted_messages = self._extract_from_nextjs_stream(script.string)
                            if extracted_messages:
                                messages.extend(extracted_messages)
                                logger.info(f"Extracted {len(extracted_messages)} messages from Next.js stream")
                                continue
                        
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
            
            # Try to build conversation from collected text content
            if all_text_content and conversation_info:
                logger.debug(f"Attempting to build conversation from {len(all_text_content)} text chunks...")
                messages = self._build_conversation_from_text(all_text_content, conversation_info)
                if messages:
                    title = conversation_info.get('title') or self._extract_title(soup)
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
    
    def _extract_conversation_info(self, script_content: str) -> dict:
        """
        Extract conversation metadata from script content
        
        Args:
            script_content: JavaScript content containing conversation data
            
        Returns:
            Dictionary with conversation metadata
        """
        import json
        import re
        
        try:
            # Look for conversation object with metadata
            conv_pattern = r'"conversation":\s*(\{[^}]*"conversationId"[^}]*"title"[^}]*\})'
            match = re.search(conv_pattern, script_content)
            
            if match:
                conv_str = match.group(1)
                # Clean up escaped quotes
                cleaned_conv = conv_str.replace('\\"', '"')
                
                try:
                    conv_data = json.loads(cleaned_conv)
                    logger.debug(f"Extracted conversation info: {conv_data}")
                    return conv_data
                except json.JSONDecodeError:
                    pass
            
            # Alternative pattern - look for shareLinkId context
            share_pattern = r'"shareLinkId":\s*"[^"]+",\s*"conversation":\s*(\{[^}]+\})'
            match = re.search(share_pattern, script_content)
            
            if match:
                conv_str = match.group(1)
                cleaned_conv = conv_str.replace('\\"', '"')
                
                try:
                    conv_data = json.loads(cleaned_conv)
                    logger.debug(f"Extracted conversation info from shareLinkId context: {conv_data}")
                    return conv_data
                except json.JSONDecodeError:
                    pass
                    
        except Exception as e:
            logger.debug(f"Error extracting conversation info: {e}")
        
        return {}
    
    def _extract_text_content_from_stream(self, script_content: str) -> list:
        """
        Extract text content that looks like conversation messages from stream data
        
        Args:
            script_content: JavaScript content containing stream data
            
        Returns:
            List of text content strings
        """
        import re
        
        text_content = []
        
        try:
            # Look for Next.js stream chunks containing substantial text
            stream_pattern = r'self\.__next_f\.push\(\[\d+,"([^"]+)"\]\)'
            matches = re.finditer(stream_pattern, script_content)
            
            for match in matches:
                data_str = match.group(1)
                
                # Unescape the string
                unescaped = data_str.replace('\\"', '"').replace('\\\\', '\\').replace('\\n', '\n')
                
                # Look for content that looks like conversation text
                # Skip technical data and focus on substantial text content
                if (len(unescaped) > 50 and 
                    not unescaped.startswith(('{"', '[{', 'window.', 'var ', 'function')) and
                    not re.match(r'^\w+:', unescaped) and  # Skip simple key:value patterns
                    ('。' in unescaped or '、' in unescaped or len(unescaped.split()) > 10)):  # Japanese punctuation or long text
                    
                    # Clean up the text
                    clean_text = unescaped.strip()
                    
                    # Remove common technical prefixes
                    if clean_text.startswith(('T40', 'T42', 'T43', 'I[', 'metadata')):
                        continue
                    
                    # Extract meaningful content
                    if clean_text:
                        text_content.append(clean_text)
                        logger.debug(f"Extracted text content: {clean_text[:100]}...")
            
        except Exception as e:
            logger.debug(f"Error extracting text content: {e}")
        
        return text_content
    
    def _build_conversation_from_text(self, text_chunks: list, conversation_info: dict) -> list:
        """
        Build conversation messages from extracted text chunks
        
        Args:
            text_chunks: List of text content strings
            conversation_info: Conversation metadata
            
        Returns:
            List of ChatMessage objects
        """
        messages = []
        
        try:
            # Combine and process text chunks
            combined_text = '\n\n'.join(text_chunks)
            
            # Split into potential messages based on patterns
            # Look for patterns that indicate message boundaries
            
            # Pattern 1: "# 概要" style headers (typically Grok responses)
            grok_sections = []
            current_section = ""
            
            lines = combined_text.split('\n')
            
            for line in lines:
                line = line.strip()
                
                # Check for section headers that indicate new messages
                if (line.startswith('# ') or 
                    line.startswith('## ') or
                    line.startswith('- ユーザーの') or
                    line.startswith('- 技術的') or
                    (len(current_section) > 100 and line.startswith('- '))):
                    
                    # Save previous section if it's substantial
                    if current_section.strip() and len(current_section.strip()) > 20:
                        grok_sections.append(current_section.strip())
                    
                    current_section = line
                else:
                    if line:
                        current_section += '\n' + line
            
            # Add the last section
            if current_section.strip() and len(current_section.strip()) > 20:
                grok_sections.append(current_section.strip())
            
            # Create messages from sections
            sequence = 1
            
            # Try to infer user question from conversation context
            title = conversation_info.get('title', '')
            if title and title != 'AIチャット共有リンク自動メモ化':
                # Use title as potential user question
                user_message = ChatMessage(
                    role=MessageRole.USER,
                    content=title,
                    sequence=sequence,
                    timestamp=datetime.now()
                )
                messages.append(user_message)
                sequence += 1
                logger.debug(f"Created user message from title: {title}")
            
            # Add Grok responses
            for section in grok_sections:
                if len(section) > 20:  # Only include substantial content
                    grok_message = ChatMessage(
                        role=MessageRole.ASSISTANT,
                        content=section,
                        sequence=sequence,
                        timestamp=datetime.now()
                    )
                    messages.append(grok_message)
                    sequence += 1
                    logger.debug(f"Created Grok message: {section[:100]}...")
            
            # If we don't have any messages yet, try a simpler approach
            if not messages and combined_text.strip():
                # Create a single assistant message with all content
                content = self._clean_text(combined_text)
                if content and len(content) > 20:
                    message = ChatMessage(
                        role=MessageRole.ASSISTANT,
                        content=content,
                        sequence=1,
                        timestamp=datetime.now()
                    )
                    messages.append(message)
                    logger.debug(f"Created single message from combined text: {content[:100]}...")
            
            logger.info(f"Built {len(messages)} messages from text content")
            return messages
            
        except Exception as e:
            logger.debug(f"Error building conversation from text: {e}")
            return messages
    
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
            
            # Look for conversation data patterns in the script
            # Pattern 1: Direct conversation object with shareLinkId
            conv_pattern = r'\\"conversation\\":\s*\{[^}]*\\"conversationId\\"[^}]*\}'
            conv_matches = re.finditer(conv_pattern, script_content)
            
            for match in conv_matches:
                conv_data_str = match.group(0)
                logger.debug(f"Found conversation pattern: {conv_data_str[:200]}...")
                
                # Try to extract and parse the conversation object
                try:
                    # Clean up the escaped JSON
                    cleaned_data = conv_data_str.replace('\\"', '"')
                    
                    # Extract just the conversation object
                    conv_obj_match = re.search(r'"conversation":\s*(\{.*?\})', cleaned_data, re.DOTALL)
                    if conv_obj_match:
                        conv_json_str = conv_obj_match.group(1)
                        
                        # Handle potential issues with nested structures
                        try:
                            conv_data = json.loads(conv_json_str)
                            logger.debug("Successfully parsed conversation object")
                            
                            extracted_messages = self._extract_messages_from_conversation_data(conv_data)
                            if extracted_messages:
                                messages.extend(extracted_messages)
                                logger.info(f"Extracted {len(extracted_messages)} messages from conversation object")
                                return messages  # Return immediately on success
                                
                        except json.JSONDecodeError as e:
                            logger.debug(f"Failed to parse conversation object: {e}")
                            continue
                            
                except Exception as e:
                    logger.debug(f"Error processing conversation pattern: {e}")
                    continue
            
            # Pattern 2: Look for stream data containing conversation
            stream_pattern = r'self\.__next_f\.push\(\[(\d+),"([^"]+(?:\\"[^"]*)*)"?\]\)'
            stream_matches = re.finditer(stream_pattern, script_content)
            
            for match in stream_matches:
                stream_id = match.group(1)
                data_str = match.group(2)
                
                if 'conversation' in data_str and 'shareLinkId' in data_str:
                    logger.debug(f"Found conversation in stream {stream_id}: {data_str[:200]}...")
                    
                    # Extract conversation data more directly
                    # Look for the shareLinkId and conversation pattern
                    share_conv_pattern = r'\\"shareLinkId\\":\\"[^"]+\\",\\"conversation\\":\{[^}]+\}'
                    share_match = re.search(share_conv_pattern, data_str)
                    
                    if share_match:
                        share_data_str = share_match.group(0)
                        logger.debug(f"Found shareLinkId conversation data: {share_data_str[:200]}...")
                        
                        # Clean and extract conversation
                        cleaned = share_data_str.replace('\\"', '"')
                        conv_match = re.search(r'"conversation":(\{[^}]+\})', cleaned)
                        
                        if conv_match:
                            try:
                                conv_data = json.loads(conv_match.group(1))
                                logger.debug("Successfully parsed stream conversation object")
                                
                                extracted_messages = self._extract_messages_from_conversation_data(conv_data)
                                if extracted_messages:
                                    messages.extend(extracted_messages)
                                    logger.info(f"Extracted {len(extracted_messages)} messages from stream conversation")
                                    return messages  # Return immediately on success
                                    
                            except json.JSONDecodeError as e:
                                logger.debug(f"Failed to parse stream conversation: {e}")
                                continue
            
            # Pattern 3: Look for any large JSON structure containing conversation
            if not messages:
                logger.debug("Trying broader conversation search...")
                
                # Look for any occurrence of conversationId and try to extract surrounding context
                conv_id_pattern = r'\\"conversationId\\":\\"[^"]+\\"[^}]*\\"messages\\":\[[^\]]*\]'
                conv_id_matches = re.finditer(conv_id_pattern, script_content)
                
                for match in conv_id_matches:
                    context_str = match.group(0)
                    logger.debug(f"Found conversationId with messages: {context_str[:200]}...")
                    
                    # Try to extract messages array
                    msg_pattern = r'\\"messages\\":\[([^\]]*)\]'
                    msg_match = re.search(msg_pattern, context_str)
                    
                    if msg_match:
                        msg_array_str = msg_match.group(1)
                        logger.debug(f"Found messages array: {msg_array_str[:200]}...")
                        
                        # Try to parse messages
                        try:
                            # Clean up the string and try to parse
                            cleaned_msgs = msg_array_str.replace('\\"', '"')
                            
                            # Wrap in array brackets if needed
                            if not cleaned_msgs.startswith('['):
                                cleaned_msgs = '[' + cleaned_msgs + ']'
                            
                            messages_data = json.loads(cleaned_msgs)
                            
                            if isinstance(messages_data, list):
                                extracted_messages = self._extract_messages_from_raw_data(messages_data)
                                if extracted_messages:
                                    messages.extend(extracted_messages)
                                    logger.info(f"Extracted {len(extracted_messages)} messages from raw messages array")
                                    return messages
                                    
                        except json.JSONDecodeError as e:
                            logger.debug(f"Failed to parse messages array: {e}")
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
    
    def _extract_messages_from_raw_data(self, messages_data: list) -> list:
        """
        Extract messages from raw message array data
        
        Args:
            messages_data: List of raw message data
            
        Returns:
            List of ChatMessage objects
        """
        messages = []
        
        try:
            sequence = 1
            for item in messages_data:
                if not isinstance(item, dict):
                    # Skip non-dict items
                    continue
                
                # Extract content with various possible keys
                content = (
                    item.get('content') or
                    item.get('text') or
                    item.get('message') or
                    item.get('body') or
                    item.get('prompt') or
                    ''
                )
                
                # Handle nested content structure
                if isinstance(content, dict):
                    content = (
                        content.get('text') or
                        content.get('content') or
                        str(content)
                    )
                elif isinstance(content, list):
                    content = ' '.join(str(c) for c in content)
                
                content = self._clean_text(str(content))
                
                if not self._should_include_message(content):
                    continue
                
                # Extract role
                role_str = (
                    item.get('role') or
                    item.get('sender') or
                    item.get('author') or
                    item.get('type') or
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
                logger.debug(f"Extracted raw message {sequence-1}: {role.value} - {content[:100]}...")
            
            return messages
            
        except Exception as e:
            logger.debug(f"Error extracting from raw data: {e}")
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