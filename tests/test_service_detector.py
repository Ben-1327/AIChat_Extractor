#!/usr/bin/env python3
"""
Tests for ServiceDetector
"""

import unittest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from extractors.service_detector import ServiceDetector

class TestServiceDetector(unittest.TestCase):
    """Test cases for ServiceDetector"""
    
    def setUp(self):
        self.detector = ServiceDetector()
    
    def test_detect_grok_service(self):
        """Test Grok URL detection"""
        test_urls = [
            "https://grok.x.com/share/abc123",
            "https://x.com/grok/chat/xyz789",
            "https://grok.com/share/bGVnYWN5_ec075326-11ef-43c6-804e-a66269554e76",
            "https://grok.com/chat/de64d505-8cd3-45a6-9023-74fe351d86b3",
        ]
        
        for url in test_urls:
            with self.subTest(url=url):
                result = self.detector.detect_service(url)
                self.assertEqual(result, "grok")
    
    def test_detect_chatgpt_service(self):
        """Test ChatGPT URL detection"""
        test_urls = [
            "https://chat.openai.com/share/abc123",
            "https://chatgpt.com/share/xyz789",
            "https://chatgpt.com/c/6885c4e8-7c2c-832d-a1b2-9c52925434a1",
            "https://chatgpt.com/share/688759e5-ee2c-8002-9c42-bd3638c2f625",
        ]
        
        for url in test_urls:
            with self.subTest(url=url):
                result = self.detector.detect_service(url)
                self.assertEqual(result, "chatgpt")
    
    def test_detect_gemini_service(self):
        """Test Gemini URL detection"""
        test_urls = [
            "https://gemini.google.com/share/abc123",
            "https://bard.google.com/share/xyz789",
            "https://gemini.google.com/u/1/app/7b0661ec349ada92",
            "https://g.co/gemini/share/dd9051d9712f",
        ]
        
        for url in test_urls:
            with self.subTest(url=url):
                result = self.detector.detect_service(url)
                self.assertEqual(result, "gemini")
    
    def test_detect_claude_service(self):
        """Test Claude URL detection"""
        test_urls = [
            "https://claude.ai/chat/abc123",
            "https://anthropic.com/claude/share/xyz789",
            "https://claude.ai/chat/a1e8c91f-59fe-44e4-b2da-542b9809d7d2",
            "https://claude.ai/share/3f88bb56-06f8-49bf-87b3-65633b9b34ab",
        ]
        
        for url in test_urls:
            with self.subTest(url=url):
                result = self.detector.detect_service(url)
                self.assertEqual(result, "claude")
    
    def test_unsupported_service(self):
        """Test unsupported URL"""
        unsupported_urls = [
            "https://example.com/chat/abc123",
            "https://google.com/search?q=test",
            "invalid-url",
        ]
        
        for url in unsupported_urls:
            with self.subTest(url=url):
                result = self.detector.detect_service(url)
                self.assertIsNone(result)
    
    def test_is_supported_service(self):
        """Test is_supported_service method"""
        # Supported URLs
        supported_urls = [
            "https://chat.openai.com/share/abc123",
            "https://claude.ai/chat/xyz789"
        ]
        
        for url in supported_urls:
            with self.subTest(url=url):
                self.assertTrue(self.detector.is_supported_service(url))
        
        # Unsupported URLs
        unsupported_urls = [
            "https://example.com/chat/abc123",
            "invalid-url"
        ]
        
        for url in unsupported_urls:
            with self.subTest(url=url):
                self.assertFalse(self.detector.is_supported_service(url))

if __name__ == '__main__':
    unittest.main()