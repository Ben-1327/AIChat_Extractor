#!/usr/bin/env python3
"""
Update Manager for AI Chat Extractor
Handles automatic updates from GitHub releases.
"""

import requests
import json
import os
import sys
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, Dict, Any
import logging
from packaging import version

logger = logging.getLogger(__name__)

class UpdateManager:
    """Manages automatic updates from GitHub"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.github_repo = self.config.get('update', {}).get('github_repo', 'yourusername/ai-chat-extractor')
        self.current_version = self._get_current_version()
    
    def check_and_update(self) -> bool:
        """
        Check for updates and install if available
        
        Returns:
            True if update was successful, False otherwise
        """
        try:
            logger.info("Checking for updates...")
            
            latest_release = self._get_latest_release()
            if not latest_release:
                logger.info("Could not fetch latest release information")
                return False
            
            latest_version = latest_release.get('tag_name', '').lstrip('v')
            if not latest_version:
                logger.warning("Could not determine latest version")
                return False
            
            logger.info(f"Current version: {self.current_version}")
            logger.info(f"Latest version: {latest_version}")
            
            if self._is_newer_version(latest_version, self.current_version):
                print(f"🔄 New version available: {latest_version}")
                print(f"📝 Release notes: {latest_release.get('name', 'No title')}")
                
                if latest_release.get('body'):
                    print(f"📋 Changes:\n{latest_release['body'][:200]}...")
                
                # Ask for confirmation unless auto-update is enabled
                if not self.config.get('update', {}).get('auto_update', False):
                    response = input("\nDo you want to update now? (y/N): ")
                    if response.lower() not in ['y', 'yes']:
                        print("Update cancelled")
                        return False
                
                return self._perform_update(latest_release)
            else:
                print("✅ You are already using the latest version")
                return True
                
        except Exception as e:
            logger.error(f"Error during update check: {e}")
            print(f"❌ Update check failed: {e}")
            return False
    
    def _get_current_version(self) -> str:
        """Get current version from package or fallback"""
        try:
            # Try to get version from the main module
            from chat_extract import VERSION
            return VERSION
        except ImportError:
            return "0.1.0"  # Fallback version
    
    def _get_latest_release(self) -> Optional[Dict[str, Any]]:
        """
        Fetch latest release information from GitHub API
        
        Returns:
            Release information dictionary or None
        """
        try:
            api_url = f"https://api.github.com/repos/{self.github_repo}/releases/latest"
            
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch release information: {e}")
            return None
    
    def _is_newer_version(self, latest: str, current: str) -> bool:
        """
        Compare versions to determine if update is needed
        
        Args:
            latest: Latest version string
            current: Current version string
            
        Returns:
            True if latest is newer than current
        """
        try:
            return version.parse(latest) > version.parse(current)
        except Exception as e:
            logger.warning(f"Error comparing versions: {e}")
            # Fallback to string comparison
            return latest != current and latest > current
    
    def _perform_update(self, release_info: Dict[str, Any]) -> bool:
        """
        Download and install the update
        
        Args:
            release_info: GitHub release information
            
        Returns:
            True if update was successful
        """
        try:
            print("📥 Downloading update...")
            
            # Find the appropriate asset to download
            asset_url = self._find_download_asset(release_info)
            if not asset_url:
                print("❌ Could not find download asset")
                return False
            
            # Download the update
            update_file = self._download_update(asset_url)
            if not update_file:
                print("❌ Failed to download update")
                return False
            
            print("🔧 Installing update...")
            
            # Install the update
            success = self._install_update(update_file)
            
            # Cleanup
            try:
                os.unlink(update_file)
            except:
                pass
            
            if success:
                print("✅ Update installed successfully!")
                print("🔄 Please restart the application to use the new version")
                return True
            else:
                print("❌ Failed to install update")
                return False
                
        except Exception as e:
            logger.error(f"Error performing update: {e}")
            print(f"❌ Update failed: {e}")
            return False
    
    def _find_download_asset(self, release_info: Dict[str, Any]) -> Optional[str]:
        """
        Find the appropriate download asset from release
        
        Args:
            release_info: GitHub release information
            
        Returns:
            Download URL or None
        """
        assets = release_info.get('assets', [])
        
        # Look for source code archive or appropriate binary
        for asset in assets:
            name = asset.get('name', '').lower()
            if name.endswith('.zip') and 'source' in name:
                return asset.get('browser_download_url')
        
        # Fallback to zipball
        return release_info.get('zipball_url')
    
    def _download_update(self, url: str) -> Optional[str]:
        """
        Download update file
        
        Args:
            url: Download URL
            
        Returns:
            Path to downloaded file or None
        """
        try:
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
                for chunk in response.iter_content(chunk_size=8192):
                    temp_file.write(chunk)
                
                return temp_file.name
                
        except Exception as e:
            logger.error(f"Error downloading update: {e}")
            return None
    
    def _install_update(self, update_file: str) -> bool:
        """
        Install the downloaded update
        
        Args:
            update_file: Path to update file
            
        Returns:
            True if installation was successful
        """
        try:
            # Get current installation directory
            current_dir = Path(__file__).parent.parent
            
            # Create backup
            backup_dir = current_dir.parent / f"backup_{self.current_version}"
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            shutil.copytree(current_dir, backup_dir)
            
            # Extract update
            with tempfile.TemporaryDirectory() as temp_dir:
                with zipfile.ZipFile(update_file, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                # Find the extracted directory
                extracted_items = list(Path(temp_dir).iterdir())
                if len(extracted_items) == 1 and extracted_items[0].is_dir():
                    source_dir = extracted_items[0]
                else:
                    source_dir = Path(temp_dir)
                
                # Copy new files
                src_dir = source_dir / 'src'
                if src_dir.exists():
                    # Remove old source files
                    if (current_dir / 'src').exists():
                        shutil.rmtree(current_dir / 'src')
                    
                    # Copy new source files
                    shutil.copytree(src_dir, current_dir / 'src')
                
                # Copy other important files
                for file_name in ['requirements.txt', 'setup.py', 'README.md']:
                    src_file = source_dir / file_name
                    if src_file.exists():
                        shutil.copy2(src_file, current_dir / file_name)
            
            print(f"📁 Backup created at: {backup_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Error installing update: {e}")
            
            # Try to restore backup
            try:
                if backup_dir.exists():
                    if current_dir.exists():
                        shutil.rmtree(current_dir)
                    shutil.move(backup_dir, current_dir)
                    print("🔄 Restored from backup due to installation error")
            except:
                pass
            
            return False