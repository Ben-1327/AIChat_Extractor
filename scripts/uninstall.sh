#!/bin/bash

# AI Chat Extractor CLI - Uninstallation Script
# This script removes the AI Chat Extractor CLI tool from Mac

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="ai-chat-extractor"
BINARY_NAME="chat_extract"
INSTALL_DIR="$HOME/bin"
VENV_DIR="$HOME/.local/share/$APP_NAME"
CONFIG_DIR="$HOME/.config/ai_chat_extractor"

echo -e "${BLUE}🗑️  AI Chat Extractor CLI Uninstallation${NC}"
echo -e "========================================="

# Ask for confirmation
echo -e "${YELLOW}This will remove AI Chat Extractor CLI and all its files.${NC}"
echo -e "${YELLOW}Your conversations will NOT be deleted.${NC}"
echo -e ""
read -p "Are you sure you want to continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Uninstallation cancelled.${NC}"
    exit 0
fi

# Remove executable
echo -e "${YELLOW}Removing executable...${NC}"
if [ -f "$INSTALL_DIR/$BINARY_NAME" ]; then
    rm "$INSTALL_DIR/$BINARY_NAME"
    echo -e "${GREEN}✅ Removed $INSTALL_DIR/$BINARY_NAME${NC}"
else
    echo -e "${YELLOW}⚠️  Executable not found${NC}"
fi

# Remove virtual environment and source files
echo -e "${YELLOW}Removing virtual environment and source files...${NC}"
if [ -d "$VENV_DIR" ]; then
    rm -rf "$VENV_DIR"
    echo -e "${GREEN}✅ Removed $VENV_DIR${NC}"
else
    echo -e "${YELLOW}⚠️  Virtual environment directory not found${NC}"
fi

# Ask about configuration files
echo -e ""
echo -e "${YELLOW}Do you want to remove configuration files?${NC}"
echo -e "${YELLOW}(This includes your custom settings)${NC}"
read -p "Remove config files? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -d "$CONFIG_DIR" ]; then
        rm -rf "$CONFIG_DIR"
        echo -e "${GREEN}✅ Removed configuration directory: $CONFIG_DIR${NC}"
    else
        echo -e "${YELLOW}⚠️  Configuration directory not found${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Configuration files preserved at: $CONFIG_DIR${NC}"
fi

# Clean up PATH (optional)
echo -e "${YELLOW}Checking PATH configuration...${NC}"

# Determine shell config file
if [ -n "$ZSH_VERSION" ]; then
    SHELL_CONFIG="$HOME/.zshrc"
elif [ -n "$BASH_VERSION" ]; then
    SHELL_CONFIG="$HOME/.bash_profile"
    if [ ! -f "$SHELL_CONFIG" ]; then
        SHELL_CONFIG="$HOME/.bashrc"
    fi
else
    SHELL_CONFIG="$HOME/.profile"
fi

# Check if PATH entry exists and offer to remove it
if [ -f "$SHELL_CONFIG" ] && grep -q "# AI Chat Extractor CLI" "$SHELL_CONFIG"; then
    echo -e ""
    echo -e "${YELLOW}Found PATH entry in $SHELL_CONFIG${NC}"
    read -p "Remove PATH entry? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Create a backup
        cp "$SHELL_CONFIG" "$SHELL_CONFIG.backup.$(date +%Y%m%d_%H%M%S)"
        
        # Remove the PATH entry and the comment
        sed -i.tmp '/# AI Chat Extractor CLI/d' "$SHELL_CONFIG"
        sed -i.tmp "\|export PATH.*$INSTALL_DIR|d" "$SHELL_CONFIG"
        rm "$SHELL_CONFIG.tmp"
        
        echo -e "${GREEN}✅ Removed PATH entry from $SHELL_CONFIG${NC}"
        echo -e "${YELLOW}⚠️  Backup created: $SHELL_CONFIG.backup.*${NC}"
        echo -e "${YELLOW}⚠️  Please restart your terminal or run: source $SHELL_CONFIG${NC}"
    else
        echo -e "${YELLOW}⚠️  PATH entry preserved${NC}"
    fi
fi

# Clean up empty directories
echo -e "${YELLOW}Cleaning up empty directories...${NC}"

# Remove ~/bin if it's empty and was created by us
if [ -d "$INSTALL_DIR" ] && [ -z "$(ls -A $INSTALL_DIR)" ]; then
    rmdir "$INSTALL_DIR" 2>/dev/null && echo -e "${GREEN}✅ Removed empty directory: $INSTALL_DIR${NC}" || true
fi

# Remove ~/.local/share directory if empty
LOCAL_SHARE_DIR="$(dirname "$VENV_DIR")"
if [ -d "$LOCAL_SHARE_DIR" ] && [ -z "$(ls -A $LOCAL_SHARE_DIR)" ]; then
    rmdir "$LOCAL_SHARE_DIR" 2>/dev/null && echo -e "${GREEN}✅ Removed empty directory: $LOCAL_SHARE_DIR${NC}" || true
fi

# Final verification
echo -e "${YELLOW}Verifying uninstallation...${NC}"
if command -v "$BINARY_NAME" &> /dev/null; then
    echo -e "${RED}⚠️  Command '$BINARY_NAME' is still available (may be in PATH cache)${NC}"
    echo -e "${YELLOW}Please restart your terminal to complete the uninstallation.${NC}"
else
    echo -e "${GREEN}✅ Command '$BINARY_NAME' is no longer available${NC}"
fi

echo -e ""
echo -e "${GREEN}🎉 AI Chat Extractor CLI has been uninstalled successfully!${NC}"
echo -e ""

if [ -d "$CONFIG_DIR" ]; then
    echo -e "${YELLOW}Note: Configuration files are preserved at:${NC}"
    echo -e "  $CONFIG_DIR"
    echo -e ""
fi

echo -e "Thank you for using AI Chat Extractor CLI!"
echo -e ""