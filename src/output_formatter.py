#!/usr/bin/env python3
"""
Output Formatter for AI Chat Extractor
Formats conversations into Obsidian Chat View compatible Markdown.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import logging

from models import Conversation, ChatMessage, MessageRole
from extractors.text_normalizer import TextNormalizer

logger = logging.getLogger(__name__)

class ObsidianChatFormatter:
    """Formats conversations into Obsidian Chat View format"""
    
    def __init__(self, config: Dict[str, Any], style_overrides: Optional[str] = None):
        self.config = config
        self.styles = self._parse_styles(style_overrides)
    
    def format_conversation(self, conversation: Conversation) -> str:
        """
        Format a conversation into Obsidian Chat View Markdown
        
        Args:
            conversation: Conversation object to format
            
        Returns:
            Formatted Markdown string
        """
        try:
            logger.info(f"Formatting conversation with {len(conversation.messages)} messages")
            
            lines = []
            
            # Add metadata header if enabled
            if self.config.get('output', {}).get('include_metadata', True):
                lines.extend(self._format_metadata(conversation))
                lines.append("")  # Empty line after metadata
            
            # Start chat view block
            lines.append("```chat")
            
            # Add styles
            lines.extend(self._format_styles())
            
            # Add colors
            lines.extend(self._format_colors())
            
            # Add messages
            for message in conversation.messages:
                formatted_message = self._format_message(message, conversation.service.value)
                if formatted_message:
                    lines.extend(formatted_message)
            
            # Add extraction log if enabled
            if self.config.get('output', {}).get('add_extraction_log', True):
                lines.extend(self._format_extraction_log(conversation))
            
            # End chat view block
            lines.append("```")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error formatting conversation: {e}")
            return f"Error formatting conversation: {e}"
    
    def _parse_styles(self, style_overrides: Optional[str]) -> Dict[str, Any]:
        """
        Parse style overrides from command line
        
        Args:
            style_overrides: Style string like "header=h3,mw=75"
            
        Returns:
            Merged styles dictionary
        """
        styles = self.config.get('default_styles', {}).copy()
        
        if style_overrides:
            try:
                for override in style_overrides.split(','):
                    if '=' in override:
                        key, value = override.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # Handle special keys
                        if key == 'mw':
                            key = 'max_width'
                        
                        # Convert to appropriate type
                        if key == 'max_width':
                            styles[key] = int(value)
                        elif key in ['show_timestamps', 'show_sequence']:
                            styles[key] = value.lower() in ['true', '1', 'yes']
                        else:
                            styles[key] = value
                            
            except Exception as e:
                logger.warning(f"Error parsing style overrides: {e}")
        
        return styles
    
    def _format_metadata(self, conversation: Conversation) -> list:
        """
        Format conversation metadata
        
        Args:
            conversation: Conversation object
            
        Returns:
            List of metadata lines
        """
        lines = []
        
        # Title
        if conversation.title:
            header_level = self.styles.get('header', 'h3')
            header_prefix = '#' * int(header_level[1:]) if header_level.startswith('h') else '###'
            lines.append(f"{header_prefix} {conversation.title}")
        
        # Source URL if enabled
        if self.config.get('output', {}).get('include_source_url', True) and conversation.url:
            lines.append(f"**Source:** {conversation.url}")
        
        # Service and extraction info
        lines.append(f"**Service:** {conversation.service.value.title()}")
        lines.append(f"**Extracted:** {conversation.extracted_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Messages:** {len(conversation.messages)}")
        
        return lines
    
    def _format_styles(self) -> list:
        """
        Format chat view styles
        
        Returns:
            List of style lines
        """
        lines = []
        
        # Max width
        max_width = self.styles.get('max_width', 75)
        lines.append(f"mw={max_width}")
        
        return lines
    
    def _format_colors(self) -> list:
        """
        Format color definitions
        
        Returns:
            List of color lines
        """
        lines = []
        colors = self.config.get('colors', {})
        
        for role, color in colors.items():
            lines.append(f"{role}={color}")
        
        return lines
    
    def _format_message(self, message: ChatMessage, service: str) -> Optional[list]:
        """
        Format a single message for chat view
        
        Args:
            message: ChatMessage object
            service: Service name
            
        Returns:
            List of message lines or None if message should be skipped
        """
        if not message.content.strip():
            return None
        
        lines = []
        
        # Determine sender name
        if message.role == MessageRole.USER:
            sender = "user"
        elif message.role == MessageRole.ASSISTANT:
            sender = service.title()
        else:
            sender = "system"
        
        # Format message header with optional metadata
        header_parts = [sender]
        subtext_parts = []
        
        # Add timestamp if enabled and available
        if self.styles.get('show_timestamps', True) and message.timestamp:
            subtext_parts.append(message.timestamp.strftime('%H:%M:%S'))
        
        # Add sequence number if enabled
        if self.styles.get('show_sequence', True) and message.sequence:
            subtext_parts.append(f"#{message.sequence}")
        
        # Normalize message content
        normalized_content = TextNormalizer.normalize_text(message.content)
        
        # Build message line
        if subtext_parts:
            subtext = " | ".join(subtext_parts)
            lines.append(f"< {sender} | {normalized_content} | {subtext}")
        else:
            lines.append(f"< {sender} | {normalized_content}")
        
        return lines
    
    def _format_extraction_log(self, conversation: Conversation) -> list:
        """
        Format extraction log comment
        
        Args:
            conversation: Conversation object
            
        Returns:
            List of log lines
        """
        lines = []
        lines.append("")  # Empty line before log
        lines.append("# Extraction Log")
        lines.append(f"# Extracted from: {conversation.url}")
        lines.append(f"# Service: {conversation.service.value}")
        lines.append(f"# Timestamp: {conversation.extracted_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"# Total messages: {len(conversation.messages)}")
        lines.append(f"# User messages: {len(conversation.get_user_messages())}")
        lines.append(f"# Assistant messages: {len(conversation.get_assistant_messages())}")
        
        return lines