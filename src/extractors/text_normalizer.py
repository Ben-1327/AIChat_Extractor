#!/usr/bin/env python3
"""
Text Normalizer for AI Chat Extractor
Provides robust text normalization and encoding handling to prevent character corruption.
"""

import re
import unicodedata
import logging
from typing import Optional, Union

logger = logging.getLogger(__name__)

class TextNormalizer:
    """Robust text normalization and encoding handler"""
    
    @staticmethod
    def normalize_text(text: Union[str, bytes, None]) -> str:
        """
        Normalize text with comprehensive encoding and character handling
        
        Args:
            text: Input text in various formats
            
        Returns:
            Normalized UTF-8 string
        """
        if not text:
            return ""
        
        # Handle bytes input
        if isinstance(text, bytes):
            text = TextNormalizer._decode_bytes(text)
        
        # Convert to string
        text = str(text)
        
        # Remove null bytes and other problematic characters
        text = text.replace('\x00', '').replace('\ufffd', '')
        
        # Normalize Unicode characters
        try:
            # Use NFC normalization to combine characters properly
            text = unicodedata.normalize('NFC', text)
        except Exception as e:
            logger.debug(f"Unicode normalization failed: {e}")
        
        # Remove or replace problematic characters
        text = TextNormalizer._clean_problematic_chars(text)
        
        # Normalize whitespace
        text = TextNormalizer._normalize_whitespace(text)
        
        # Remove HTML entities safely
        text = TextNormalizer._decode_html_entities(text)
        
        # Final encoding validation
        text = TextNormalizer._validate_utf8(text)
        
        return text.strip()
    
    @staticmethod
    def _decode_bytes(data: bytes) -> str:
        """Decode bytes to string with fallback encodings"""
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                decoded = data.decode(encoding)
                # Verify the decoded string is valid
                decoded.encode('utf-8')
                return decoded
            except (UnicodeDecodeError, UnicodeEncodeError):
                continue
        
        # Last resort: decode with errors='replace'
        return data.decode('utf-8', errors='replace')
    
    @staticmethod
    def _clean_problematic_chars(text: str) -> str:
        """Remove or replace problematic characters"""
        # Remove control characters except common whitespace
        text = ''.join(char for char in text 
                      if unicodedata.category(char)[0] != 'C' or char in '\n\r\t ')
        
        # Replace common problematic sequences
        replacements = {
            '\u200b': '',  # zero-width space
            '\u200c': '',  # zero-width non-joiner
            '\u200d': '',  # zero-width joiner
            '\ufeff': '',  # byte order mark
            '\u00a0': ' ', # non-breaking space
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        return text
    
    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        """Normalize whitespace characters"""
        # Replace various whitespace characters with regular spaces
        text = re.sub(r'[\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]', ' ', text)
        
        # Normalize line breaks
        text = re.sub(r'\r\n', '\n', text)
        text = re.sub(r'\r', '\n', text)
        
        # Collapse multiple spaces (but preserve single newlines)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n+', '\n', text)
        
        return text
    
    @staticmethod
    def _decode_html_entities(text: str) -> str:
        """Safely decode HTML entities"""
        try:
            import html
            text = html.unescape(text)
        except Exception as e:
            logger.debug(f"HTML entity decoding failed: {e}")
        
        # Manual fallback for common entities
        common_entities = {
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&#39;': "'",
            '&nbsp;': ' ',
        }
        
        for entity, replacement in common_entities.items():
            text = text.replace(entity, replacement)
        
        return text
    
    @staticmethod
    def _validate_utf8(text: str) -> str:
        """Validate and ensure text is proper UTF-8"""
        try:
            # Try to encode/decode to catch any remaining issues
            encoded = text.encode('utf-8', errors='strict')
            return encoded.decode('utf-8')
        except UnicodeEncodeError:
            # Fallback with replacement
            logger.debug("UTF-8 validation failed, using replacement encoding")
            return text.encode('utf-8', errors='replace').decode('utf-8')
    
    @staticmethod
    def normalize_json_string(json_str: str) -> str:
        """Normalize JSON string content specifically"""
        if not json_str:
            return ""
        
        # First normalize the text
        normalized = TextNormalizer.normalize_text(json_str)
        
        # Handle escaped sequences in JSON
        try:
            # Fix common JSON escape issues
            normalized = normalized.replace('\\"', '"')
            normalized = normalized.replace('\\\\', '\\')
            normalized = normalized.replace('\\/', '/')
        except Exception as e:
            logger.debug(f"JSON string normalization failed: {e}")
        
        return normalized
    
    @staticmethod
    def is_valid_message_content(text: str) -> bool:
        """Check if text appears to be valid message content"""
        if not text or len(text.strip()) < 1:
            return False
        
        # Check for excessive control characters or garbled text
        control_char_count = sum(1 for char in text if unicodedata.category(char)[0] == 'C')
        control_ratio = control_char_count / len(text) if text else 0
        
        # Reject text with too many control characters
        if control_ratio > 0.3:
            logger.debug(f"Rejecting text with high control character ratio: {control_ratio}")
            return False
        
        # Check for reasonable character distribution
        printable_chars = sum(1 for char in text if unicodedata.category(char)[0] not in ['Cc', 'Cf'])
        printable_ratio = printable_chars / len(text) if text else 0
        
        if printable_ratio < 0.7:
            logger.debug(f"Rejecting text with low printable character ratio: {printable_ratio}")
            return False
        
        return True