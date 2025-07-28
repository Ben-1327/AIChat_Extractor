#!/usr/bin/env python3
"""
Data models for AI Chat Extractor
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class MessageRole(Enum):
    """Message role enumeration"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class ServiceType(Enum):
    """Supported AI service types"""
    GROK = "grok"
    CHATGPT = "chatgpt"
    GEMINI = "gemini"
    CLAUDE = "claude"

@dataclass
class ChatMessage:
    """Represents a single chat message"""
    role: MessageRole
    content: str
    timestamp: Optional[datetime] = None
    sequence: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if isinstance(self.role, str):
            self.role = MessageRole(self.role.lower())

@dataclass
class Conversation:
    """Represents a complete conversation"""
    messages: List[ChatMessage]
    service: ServiceType
    title: Optional[str] = None
    url: Optional[str] = None
    extracted_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if isinstance(self.service, str):
            self.service = ServiceType(self.service.lower())
        if self.extracted_at is None:
            self.extracted_at = datetime.now()
    
    def get_user_messages(self) -> List[ChatMessage]:
        """Get all user messages"""
        return [msg for msg in self.messages if msg.role == MessageRole.USER]
    
    def get_assistant_messages(self) -> List[ChatMessage]:
        """Get all assistant messages"""
        return [msg for msg in self.messages if msg.role == MessageRole.ASSISTANT]
    
    def get_message_count(self) -> int:
        """Get total message count"""
        return len(self.messages)
    
    def add_message(self, message: ChatMessage) -> None:
        """Add a message to the conversation"""
        if message.sequence is None:
            message.sequence = len(self.messages) + 1
        self.messages.append(message)