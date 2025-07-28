#!/usr/bin/env python3
"""
Configuration Manager for AI Chat Extractor
Handles loading and managing configuration files.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages configuration files and settings"""
    
    DEFAULT_CONFIG_DIR = Path.home() / ".config" / "ai_chat_extractor"
    DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize config manager with optional custom config path"""
        self.config_path = Path(config_path) if config_path else self.DEFAULT_CONFIG_FILE
        self.config_dir = self.config_path.parent
        
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file, creating default if needed"""
        try:
            if not self.config_path.exists():
                logger.info(f"Config file not found at {self.config_path}, creating default")
                self._create_default_config()
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                
            logger.debug(f"Loaded config from {self.config_path}")
            return config or {}
            
        except Exception as e:
            logger.warning(f"Failed to load config from {self.config_path}: {e}")
            logger.info("Using default configuration")
            return self._get_default_config()
    
    def save_config(self, config: Dict[str, Any]) -> None:
        """Save configuration to file"""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
                
            logger.info(f"Saved config to {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save config to {self.config_path}: {e}")
            raise
    
    def _create_default_config(self) -> None:
        """Create default configuration file"""
        default_config = self._get_default_config()
        self.save_config(default_config)
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration dictionary"""
        return {
            'default_output': '~/Documents/Obsidian/Conversations',
            'default_styles': {
                'header': 'h3',
                'max_width': 75,
                'show_timestamps': True,
                'show_sequence': True
            },
            'colors': {
                'user': 'blue',
                'Grok': 'yellow',
                'ChatGPT': 'green',
                'Gemini': 'purple',
                'Claude': 'orange',
                'assistant': 'gray',
                'system': 'red'
            },
            'extraction': {
                'remove_duplicates': True,
                'min_message_length': 1,
                'max_retries': 3,
                'timeout': 30
            },
            'output': {
                'filename_template': 'conversation_{service}_{timestamp}.md',
                'include_metadata': True,
                'include_source_url': True,
                'add_extraction_log': True
            },
            'update': {
                'check_on_startup': False,
                'github_repo': 'yourusername/ai-chat-extractor',
                'auto_update': False
            }
        }
    
    def get_nested_value(self, config: Dict[str, Any], key_path: str, default: Any = None) -> Any:
        """Get nested configuration value using dot notation (e.g., 'colors.user')"""
        keys = key_path.split('.')
        value = config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def update_config(self, updates: Dict[str, Any]) -> None:
        """Update configuration with new values"""
        config = self.load_config()
        config.update(updates)
        self.save_config(config)