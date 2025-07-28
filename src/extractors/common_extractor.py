#!/usr/bin/env python3
"""
Common Extraction Components for AI Chat Extractor
Provides unified extraction patterns and error handling.
"""

import json
import re
import logging
from typing import Optional, Dict, List, Any, Tuple
from abc import ABC, abstractmethod
from bs4 import BeautifulSoup
from datetime import datetime

from models import ChatMessage, MessageRole, ServiceType

logger = logging.getLogger(__name__)

class ExtractionResult:
    """Container for extraction results with metadata"""
    
    def __init__(self, messages: List[ChatMessage], title: Optional[str] = None, 
                 method: Optional[str] = None, confidence: float = 0.0):
        self.messages = messages
        self.title = title
        self.method = method  # Which extraction method was successful
        self.confidence = confidence  # Confidence score (0.0 - 1.0)
        self.success = len(messages) > 0

class ExtractionError(Exception):
    """Base exception for extraction errors"""
    
    def __init__(self, message: str, error_type: str = "general", service: Optional[str] = None):
        super().__init__(message)
        self.error_type = error_type
        self.service = service
        self.timestamp = datetime.now()

class JSONExtractor:
    """Unified JSON data extraction from various script tag patterns"""
    
    def __init__(self, service_type: ServiceType):
        self.service_type = service_type
    
    def extract_from_script_tags(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Extract all potential JSON data from script tags
        
        Returns:
            List of parsed JSON objects found in scripts
        """
        json_data_list = []
        script_tags = soup.find_all('script')
        
        for script in script_tags:
            if not script.string:
                continue
                
            script_content = script.string.strip()
            
            # Skip empty or very short scripts
            if len(script_content) < 50:
                continue
            
            # Try multiple extraction patterns
            extracted_data = self._try_extraction_patterns(script_content)
            if extracted_data:
                json_data_list.extend(extracted_data)
        
        logger.debug(f"Extracted {len(json_data_list)} JSON objects from script tags")
        return json_data_list
    
    def _try_extraction_patterns(self, script_content: str) -> List[Dict[str, Any]]:
        """Try multiple patterns to extract JSON data"""
        extracted_data = []
        
        # Pattern 1: Common initial state patterns
        initial_state_patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
            r'window\.__NUXT__\s*=\s*({.*?});',
            r'window\.__APP_STATE__\s*=\s*({.*?});',
            r'window\.__PRELOADED_STATE__\s*=\s*({.*?});',
        ]
        
        for pattern in initial_state_patterns:
            matches = re.finditer(pattern, script_content, re.DOTALL)
            for match in matches:
                try:
                    data = json.loads(match.group(1))
                    extracted_data.append(data)
                    logger.debug(f"Successfully extracted data with pattern: {pattern[:30]}...")
                except json.JSONDecodeError:
                    continue
        
        # Pattern 2: Next.js streaming data (for Grok)
        if self.service_type == ServiceType.GROK:
            nextjs_data = self._extract_nextjs_stream(script_content)
            extracted_data.extend(nextjs_data)
        
        # Pattern 3: Direct JSON objects
        json_patterns = [
            r'({[^{}]*"conversation"[^{}]*"messages"[^{}]*})',
            r'({[^{}]*"messages"[^{}]*\[[^\]]*\][^{}]*})',
            r'({[^{}]*"chat"[^{}]*"messages"[^{}]*})',
        ]
        
        for pattern in json_patterns:
            matches = re.finditer(pattern, script_content, re.DOTALL)
            for match in matches:
                try:
                    data = json.loads(match.group(1))
                    extracted_data.append(data)
                    logger.debug(f"Successfully extracted direct JSON object")
                except json.JSONDecodeError:
                    continue
        
        return extracted_data
    
    def _extract_nextjs_stream(self, script_content: str) -> List[Dict[str, Any]]:
        """Extract data from Next.js streaming format"""
        extracted_data = []
        
        try:
            # Pattern for Next.js streaming data
            stream_pattern = r'self\.__next_f\.push\(\[(\d+),"([^"]+(?:\\"[^"]*)*)"?\]\)'
            matches = re.finditer(stream_pattern, script_content)
            
            for match in matches:
                data_str = match.group(2)
                
                # Skip if this doesn't look like conversation data
                if not any(keyword in data_str for keyword in ['conversation', 'messages', 'shareLinkId']):
                    continue
                
                # Clean up escaped JSON
                cleaned_data = data_str.replace('\\"', '"').replace('\\\\', '\\')
                
                # Try to find JSON objects in the stream data
                json_objects = self._find_json_in_stream(cleaned_data)
                extracted_data.extend(json_objects)
        
        except Exception as e:
            logger.debug(f"Error extracting Next.js stream data: {e}")
        
        return extracted_data
    
    def _find_json_in_stream(self, stream_data: str) -> List[Dict[str, Any]]:
        """Find JSON objects within stream data"""
        json_objects = []
        
        # Pattern to find conversation objects
        conv_patterns = [
            r'"conversation":\s*(\{[^{}]*"conversationId"[^{}]*\})',
            r'"shareLinkId"[^}]*"conversation":\s*(\{[^{}]*\})',
            r'(\{[^{}]*"conversationId"[^{}]*"messages"[^{}]*\})',
        ]
        
        for pattern in conv_patterns:
            matches = re.finditer(pattern, stream_data)
            for match in matches:
                try:
                    obj = json.loads(match.group(1))
                    json_objects.append(obj)
                    logger.debug("Extracted JSON object from stream data")
                except json.JSONDecodeError:
                    continue
        
        return json_objects

class MessageParser:
    """Unified message parsing from various data structures"""
    
    def __init__(self, service_type: ServiceType):
        self.service_type = service_type
    
    def parse_messages_from_json(self, json_data_list: List[Dict[str, Any]]) -> List[ChatMessage]:
        """
        Parse messages from list of JSON data objects
        
        Returns:
            List of parsed ChatMessage objects
        """
        all_messages = []
        
        for json_data in json_data_list:
            messages = self._extract_messages_from_single_json(json_data)
            if messages:
                all_messages.extend(messages)
        
        # Remove duplicates and sort by sequence
        unique_messages = self._deduplicate_messages(all_messages)
        unique_messages.sort(key=lambda m: m.sequence)
        
        # Reassign sequences to ensure continuity
        for i, message in enumerate(unique_messages, 1):
            message.sequence = i
        
        return unique_messages
    
    def _extract_messages_from_single_json(self, json_data: Dict[str, Any]) -> List[ChatMessage]:
        """Extract messages from a single JSON data object"""
        messages = []
        
        # Try different paths to find messages
        message_paths = [
            ['conversation', 'messages'],
            ['messages'],
            ['chat', 'messages'],
            ['data', 'conversation', 'messages'],
            ['state', 'conversation', 'messages'],
            ['props', 'pageProps', 'conversation', 'messages'],
            ['turns'],
            ['entries'],
            ['conversationHistory'],
            ['history']
        ]
        
        messages_data = self._find_data_at_paths(json_data, message_paths)
        
        if not messages_data:
            # Fallback: recursively search for message-like structures
            messages_data = self._find_messages_recursively(json_data)
        
        if messages_data and isinstance(messages_data, list):
            messages = self._parse_message_list(messages_data)
        
        return messages
    
    def _find_data_at_paths(self, data: Dict[str, Any], paths: List[List[str]]) -> Optional[Any]:
        """Find data at specified paths"""
        for path in paths:
            current = data
            try:
                for key in path:
                    current = current[key]
                if isinstance(current, list) and current:
                    logger.debug(f"Found messages at path: {' -> '.join(path)}")
                    return current
            except (KeyError, TypeError):
                continue
        return None
    
    def _find_messages_recursively(self, data: Any, depth: int = 0, max_depth: int = 5) -> Optional[List]:
        """Recursively search for message-like data structures"""
        if depth > max_depth:
            return None
        
        if isinstance(data, dict):
            # Look for message-related keys
            for key, value in data.items():
                if key.lower() in ['messages', 'conversation', 'chat', 'turns', 'entries']:
                    if isinstance(value, list) and self._looks_like_messages(value):
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
    
    def _looks_like_messages(self, data: List) -> bool:
        """Check if a list looks like it contains messages"""
        if not data or len(data) == 0:
            return False
        
        # Check first few items
        for item in data[:3]:
            if isinstance(item, dict):
                # Look for message-like keys
                message_keys = ['content', 'text', 'message', 'body', 'role', 'author', 'sender']
                if any(key in item for key in message_keys):
                    return True
        
        return False
    
    def _parse_message_list(self, messages_data: List[Dict[str, Any]]) -> List[ChatMessage]:
        """Parse a list of message data into ChatMessage objects"""
        messages = []
        sequence = 1
        
        for msg_data in messages_data:
            if not isinstance(msg_data, dict):
                continue
            
            # Extract content
            content = self._extract_content(msg_data)
            if not content or len(content.strip()) < 1:
                continue
            
            # Extract role
            role = self._extract_role(msg_data, sequence)
            
            # Create message
            message = ChatMessage(
                role=role,
                content=content,
                sequence=sequence,
                timestamp=datetime.now()
            )
            
            messages.append(message)
            sequence += 1
        
        return messages
    
    def _extract_content(self, msg_data: Dict[str, Any]) -> str:
        """Extract content from message data"""
        # Try different content keys
        content_keys = ['content', 'text', 'message', 'body', 'prompt']
        
        for key in content_keys:
            if key in msg_data:
                content = msg_data[key]
                
                # Handle nested content structures
                if isinstance(content, dict):
                    # Try common nested patterns
                    if 'parts' in content and isinstance(content['parts'], list):
                        content = ' '.join(str(part) for part in content['parts'])
                    elif 'text' in content:
                        content = content['text']
                    elif 'content' in content:
                        content = content['content']
                    else:
                        content = str(content)
                
                elif isinstance(content, list):
                    content = ' '.join(str(item) for item in content)
                
                # Clean and return
                content = self._clean_text(str(content))
                if content:
                    return content
        
        return ""
    
    def _extract_role(self, msg_data: Dict[str, Any], sequence: int) -> MessageRole:
        """Extract and map message role"""
        # Try different role keys
        role_keys = ['role', 'sender', 'author', 'type', 'from']
        
        for key in role_keys:
            if key in msg_data:
                role_str = str(msg_data[key]).lower()
                
                # Map to MessageRole
                if role_str in ['user', 'human', 'you']:
                    return MessageRole.USER
                elif role_str in ['assistant', 'ai', 'bot', 'model', 'system']:
                    return MessageRole.ASSISTANT
                elif self.service_type == ServiceType.CHATGPT and role_str in ['chatgpt', 'gpt']:
                    return MessageRole.ASSISTANT
                elif self.service_type == ServiceType.CLAUDE and role_str in ['claude']:
                    return MessageRole.ASSISTANT
                elif self.service_type == ServiceType.GEMINI and role_str in ['gemini', 'bard']:
                    return MessageRole.ASSISTANT
                elif self.service_type == ServiceType.GROK and role_str in ['grok']:
                    return MessageRole.ASSISTANT
        
        # Fallback: alternate based on sequence (assuming user starts)
        return MessageRole.USER if sequence % 2 == 1 else MessageRole.ASSISTANT
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content with proper encoding handling"""
        if not text:
            return ""
        
        # Ensure text is properly decoded string
        if isinstance(text, bytes):
            try:
                text = text.decode('utf-8', errors='replace')
            except UnicodeDecodeError:
                text = text.decode('latin-1', errors='replace')
        
        # Convert to string if it's not already
        text = str(text)
        
        # Remove HTML entities safely
        try:
            from html import unescape
            text = unescape(text)
        except Exception:
            # If HTML unescape fails, continue without it
            pass
        
        # Remove extra whitespace and normalize
        text = ' '.join(text.split())
        
        # Ensure text contains only valid Unicode characters
        try:
            # Encode and decode to catch any encoding issues
            text = text.encode('utf-8', errors='replace').decode('utf-8')
        except Exception:
            # Fallback: remove any problematic characters
            text = ''.join(char for char in text if ord(char) < 65536)
        
        return text.strip()
    
    def _deduplicate_messages(self, messages: List[ChatMessage]) -> List[ChatMessage]:
        """Remove duplicate messages based on content and role"""
        seen = set()
        unique_messages = []
        
        for message in messages:
            # Create a signature for the message
            signature = f"{message.role.value}:{message.content[:100]}"
            
            if signature not in seen:
                seen.add(signature)
                unique_messages.append(message)
        
        return unique_messages

class ExtractionStrategy(ABC):
    """Abstract base class for extraction strategies"""
    
    @abstractmethod
    def extract(self, soup: BeautifulSoup, url: str) -> ExtractionResult:
        """Extract conversation data using this strategy"""
        pass
    
    @abstractmethod
    def get_confidence_score(self, soup: BeautifulSoup) -> float:
        """Return confidence score for this strategy (0.0 - 1.0)"""
        pass

class JSONExtractionStrategy(ExtractionStrategy):
    """Strategy for JSON-based extraction"""
    
    def __init__(self, service_type: ServiceType):
        self.service_type = service_type
        self.json_extractor = JSONExtractor(service_type)
        self.message_parser = MessageParser(service_type)
    
    def extract(self, soup: BeautifulSoup, url: str) -> ExtractionResult:
        """Extract using JSON data from script tags"""
        try:
            # Extract JSON data
            json_data_list = self.json_extractor.extract_from_script_tags(soup)
            
            if not json_data_list:
                return ExtractionResult([], method="json", confidence=0.0)
            
            # Parse messages
            messages = self.message_parser.parse_messages_from_json(json_data_list)
            
            # Extract title if possible
            title = self._extract_title_from_json(json_data_list) or self._extract_title_from_html(soup)
            
            confidence = self.get_confidence_score(soup) if messages else 0.0
            
            return ExtractionResult(
                messages=messages,
                title=title,
                method="json",
                confidence=confidence
            )
        
        except Exception as e:
            logger.debug(f"JSON extraction failed: {e}")
            return ExtractionResult([], method="json", confidence=0.0)
    
    def get_confidence_score(self, soup: BeautifulSoup) -> float:
        """Calculate confidence score based on JSON availability"""
        script_tags = soup.find_all('script')
        json_indicators = 0
        total_scripts = len(script_tags)
        
        for script in script_tags:
            if script.string and any(keyword in script.string.lower() 
                                   for keyword in ['conversation', 'messages', 'chat']):
                json_indicators += 1
        
        # Higher confidence if we find multiple JSON indicators
        if total_scripts > 0:
            return min(0.9, json_indicators / total_scripts * 2)
        return 0.1
    
    def _extract_title_from_json(self, json_data_list: List[Dict[str, Any]]) -> Optional[str]:
        """Try to extract title from JSON data"""
        for json_data in json_data_list:
            title = self._find_title_in_json(json_data)
            if title:
                return title
        return None
    
    def _find_title_in_json(self, data: Dict[str, Any], depth: int = 0) -> Optional[str]:
        """Recursively find title in JSON data"""
        if depth > 3:  # Prevent infinite recursion
            return None
        
        if isinstance(data, dict):
            # Check for title keys
            title_keys = ['title', 'name', 'subject', 'conversationTitle']
            for key in title_keys:
                if key in data and isinstance(data[key], str):
                    title = data[key].strip()
                    if title and len(title) > 0:
                        return title
            
            # Recurse into nested objects
            for value in data.values():
                if isinstance(value, (dict, list)):
                    title = self._find_title_in_json(value, depth + 1)
                    if title:
                        return title
        
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    title = self._find_title_in_json(item, depth + 1)
                    if title:
                        return title
        
        return None
    
    def _extract_title_from_html(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract title from HTML elements"""
        title_selectors = [
            'title',
            'h1',
            '[data-testid="conversation-title"]',
            '.conversation-title',
            'header h1'
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                title = element.get_text().strip()
                # Filter out generic titles
                generic_terms = ['chatgpt', 'claude', 'gemini', 'grok', 'openai', 'anthropic', 'google', 'share']
                if title and not any(term in title.lower() for term in generic_terms):
                    return title
        
        return None