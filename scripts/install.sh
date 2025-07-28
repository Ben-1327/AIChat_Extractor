#!/bin/bash

# AI Chat Extractor CLI - Installation Script
# This script installs the AI Chat Extractor CLI tool for Mac

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

echo -e "${BLUE}🚀 AI Chat Extractor CLI Installation${NC}"
echo -e "======================================"

# Check if Python 3.10+ is available
echo -e "${YELLOW}Checking Python version...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed. Please install Python 3.10 or later.${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.10"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
    echo -e "${RED}❌ Python $PYTHON_VERSION is installed, but Python $REQUIRED_VERSION or later is required.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python $PYTHON_VERSION is available${NC}"

# Check if pip is available
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}❌ pip3 is not available. Please install pip for Python 3.${NC}"
    exit 1
fi

# Create install directory
echo -e "${YELLOW}Creating installation directory...${NC}"
mkdir -p "$INSTALL_DIR"
mkdir -p "$VENV_DIR"
mkdir -p "$CONFIG_DIR"

# Create virtual environment
echo -e "${YELLOW}Creating virtual environment...${NC}"
if [ -d "$VENV_DIR" ]; then
    rm -rf "$VENV_DIR"
fi

python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -r requirements.txt

# Install packaging for version comparison in updater
pip install packaging

# Create the main executable script
echo -e "${YELLOW}Creating executable...${NC}"
cat > "$INSTALL_DIR/$BINARY_NAME" << EOF
#!/bin/bash

# AI Chat Extractor CLI - Executable Script
VENV_PATH="$VENV_DIR"
SCRIPT_PATH="\$(dirname "\$(dirname "\$(realpath "\$0")")")/src"

# Check if virtual environment exists
if [ ! -d "\$VENV_PATH" ]; then
    echo "❌ Virtual environment not found. Please reinstall AI Chat Extractor."
    exit 1
fi

# Activate virtual environment and run the script
export PYTHONPATH="\$SCRIPT_PATH:\$PYTHONPATH"
"\$VENV_PATH/bin/python" "\$SCRIPT_PATH/chat_extract.py" "\$@"
EOF

# Make executable
chmod +x "$INSTALL_DIR/$BINARY_NAME"

# Copy source files to a permanent location
echo -e "${YELLOW}Installing source files...${NC}"
SOURCE_DIR="$HOME/.local/share/$APP_NAME/src"
mkdir -p "$SOURCE_DIR"
cp -r src/* "$SOURCE_DIR/"

# Update the executable to point to the correct source location
cat > "$INSTALL_DIR/$BINARY_NAME" << EOF
#!/bin/bash

# AI Chat Extractor CLI - Executable Script
VENV_PATH="$VENV_DIR"
SCRIPT_PATH="$SOURCE_DIR"

# Check if virtual environment exists
if [ ! -d "\$VENV_PATH" ]; then
    echo "❌ Virtual environment not found. Please reinstall AI Chat Extractor."
    exit 1
fi

# Activate virtual environment and run the script
export PYTHONPATH="\$SCRIPT_PATH:\$PYTHONPATH"
"\$VENV_PATH/bin/python" "\$SCRIPT_PATH/chat_extract.py" "\$@"
EOF

chmod +x "$INSTALL_DIR/$BINARY_NAME"

# Check if ~/bin is in PATH
echo -e "${YELLOW}Checking PATH configuration...${NC}"
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo -e "${YELLOW}Adding $INSTALL_DIR to PATH...${NC}"
    
    # Determine shell and config file to use
    SHELL_CONFIG=""
    if [ -n "$ZSH_VERSION" ] || [ "$SHELL" = "/bin/zsh" ] || [ "$SHELL" = "/usr/bin/zsh" ]; then
        SHELL_CONFIG="$HOME/.zshrc"
    elif [ -n "$BASH_VERSION" ] || [ "$SHELL" = "/bin/bash" ] || [ "$SHELL" = "/usr/bin/bash" ]; then
        # Try .bash_profile first, then .bashrc
        if [ -f "$HOME/.bash_profile" ] && [ -w "$HOME/.bash_profile" ]; then
            SHELL_CONFIG="$HOME/.bash_profile"
        elif [ -f "$HOME/.bashrc" ] && [ -w "$HOME/.bashrc" ]; then
            SHELL_CONFIG="$HOME/.bashrc"
        else
            # Create .bashrc if neither exists or both are not writable
            SHELL_CONFIG="$HOME/.bashrc"
        fi
    else
        SHELL_CONFIG="$HOME/.profile"
    fi
    
    # Ensure the config file exists and is writable
    if [ ! -f "$SHELL_CONFIG" ]; then
        touch "$SHELL_CONFIG" 2>/dev/null
    fi
    
    # Check if we can write to the config file
    if [ -w "$SHELL_CONFIG" ]; then
        # Add PATH export if not already present
        if ! grep -q "export PATH.*$INSTALL_DIR" "$SHELL_CONFIG" 2>/dev/null; then
            echo "" >> "$SHELL_CONFIG"
            echo "# AI Chat Extractor CLI" >> "$SHELL_CONFIG"
            echo "export PATH=\"$INSTALL_DIR:\$PATH\"" >> "$SHELL_CONFIG"
            echo -e "${GREEN}✅ Added $INSTALL_DIR to PATH in $SHELL_CONFIG${NC}"
            echo -e "${YELLOW}⚠️  Please restart your terminal or run: source $SHELL_CONFIG${NC}"
        else
            echo -e "${GREEN}✅ $INSTALL_DIR is already in PATH${NC}"
        fi
    else
        # If we can't write to the file, provide manual instructions
        echo -e "${RED}⚠️  Cannot write to $SHELL_CONFIG (permission denied)${NC}"
        echo -e "${YELLOW}Please manually add the following line to your shell configuration file:${NC}"
        echo -e "${BLUE}export PATH=\"$INSTALL_DIR:\$PATH\"${NC}"
        echo -e ""
        echo -e "You can do this by running:"
        echo -e "${BLUE}echo 'export PATH=\"$INSTALL_DIR:\$PATH\"' >> $SHELL_CONFIG${NC}"
        echo -e "or"
        echo -e "${BLUE}echo 'export PATH=\"$INSTALL_DIR:\$PATH\"' | sudo tee -a $SHELL_CONFIG${NC}"
    fi
else
    echo -e "${GREEN}✅ $INSTALL_DIR is already in PATH${NC}"
fi

# Create default configuration file
echo -e "${YELLOW}Creating default configuration...${NC}"
if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    cp config/default_config.yaml "$CONFIG_DIR/config.yaml"
    echo -e "${GREEN}✅ Default configuration created at $CONFIG_DIR/config.yaml${NC}"
else
    echo -e "${YELLOW}⚠️  Configuration file already exists, skipping...${NC}"
fi

# Test installation
echo -e "${YELLOW}Testing installation...${NC}"
if "$INSTALL_DIR/$BINARY_NAME" --version &> /dev/null; then
    echo -e "${GREEN}✅ Installation successful!${NC}"
else
    echo -e "${RED}❌ Installation test failed${NC}"
    exit 1
fi

echo -e ""
echo -e "${GREEN}🎉 AI Chat Extractor CLI has been installed successfully!${NC}"
echo -e ""
echo -e "Usage:"
echo -e "  $BINARY_NAME [URL] [OPTIONS]"
echo -e ""
echo -e "Examples:"
echo -e "  $BINARY_NAME https://chat.openai.com/share/abc123"
echo -e "  $BINARY_NAME https://claude.ai/share/xyz789 --output ~/Documents/Chats"
echo -e ""
echo -e "Configuration:"
echo -e "  Edit: $CONFIG_DIR/config.yaml"
echo -e ""
echo -e "For help:"
echo -e "  $BINARY_NAME --help"
echo -e ""

if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo -e "${YELLOW}⚠️  Remember to restart your terminal or run:${NC}"
    echo -e "  source $SHELL_CONFIG"
    echo -e ""
fi