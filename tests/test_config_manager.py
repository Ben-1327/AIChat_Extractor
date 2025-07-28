#!/usr/bin/env python3
"""
Tests for ConfigManager
"""

import unittest
import tempfile
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config_manager import ConfigManager

class TestConfigManager(unittest.TestCase):
    """Test cases for ConfigManager"""
    
    def setUp(self):
        # Create temporary directory for test config
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "test_config.yaml"
        self.config_manager = ConfigManager(str(self.config_path))
    
    def tearDown(self):
        # Clean up temporary directory
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_create_default_config(self):
        """Test default config creation"""
        config = self.config_manager.load_config()
        
        # Check that default config was created
        self.assertTrue(self.config_path.exists())
        
        # Check for expected keys
        expected_keys = ['default_output', 'default_styles', 'colors', 'extraction', 'output', 'update']
        for key in expected_keys:
            self.assertIn(key, config)
    
    def test_get_nested_value(self):
        """Test nested value retrieval"""
        config = self.config_manager.load_config()
        
        # Test existing nested value
        user_color = self.config_manager.get_nested_value(config, 'colors.user')
        self.assertEqual(user_color, 'blue')
        
        # Test non-existing nested value with default
        missing_value = self.config_manager.get_nested_value(config, 'colors.missing', 'default')
        self.assertEqual(missing_value, 'default')
        
        # Test deeply nested value
        header_style = self.config_manager.get_nested_value(config, 'default_styles.header')
        self.assertEqual(header_style, 'h3')
    
    def test_update_config(self):
        """Test config updating"""
        # Load initial config
        initial_config = self.config_manager.load_config()
        
        # Update config
        updates = {
            'default_output': '/tmp/test_output',
            'new_key': 'new_value'
        }
        self.config_manager.update_config(updates)
        
        # Load updated config
        updated_config = self.config_manager.load_config()
        
        # Check updates were applied
        self.assertEqual(updated_config['default_output'], '/tmp/test_output')
        self.assertEqual(updated_config['new_key'], 'new_value')
        
        # Check other values are preserved
        self.assertEqual(updated_config['colors']['user'], 'blue')

if __name__ == '__main__':
    unittest.main()