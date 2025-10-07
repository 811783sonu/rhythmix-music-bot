#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}Rhythmix X Bot - Setup Script${NC}"
echo -e "${GREEN}================================${NC}\n"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    echo "Please install Python 3.9 or higher"
    exit 1
fi

echo -e "${GREEN}✓${NC} Python found: $(python3 --version)"

# Check if FFmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo -e "${YELLOW}⚠${NC} FFmpeg not found. Installing..."
    
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt-get update
        sudo apt-get install -y ffmpeg
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        brew install ffmpeg
    else
        echo -e "${RED}Please install FFmpeg manually${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓${NC} FFmpeg found"
fi

# Create virtual environment
echo -e "\n${YELLOW}Creating virtual environment...${NC}"
python3 -m venv venv

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Install requirements
echo -e "\n${YELLOW}Installing Python packages...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

echo -e "\n${GREEN}✓${NC} All dependencies installed!"

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo -e "\n${YELLOW}Creating .env file...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✓${NC} Created .env file"
    echo -e "${YELLOW}⚠ Please edit .env and add your credentials${NC}"
else
    echo -e "${GREEN}✓${NC} .env file already exists"
fi

# Create downloads directory
mkdir -p downloads
echo -e "${GREEN}✓${NC} Created downloads directory"

# Display next steps
echo -e "\n${GREEN}================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}================================${NC}\n"

echo -e "${YELLOW}Next Steps:${NC}"
echo -e "1. Edit .env file with your credentials:"
echo -e "   ${YELLOW}nano .env${NC}"
echo -e "\n2. Activate virtual environment:"
echo -e "   ${YELLOW}source venv/bin/activate${NC}"
echo -e "\n3. Run the bot:"
echo -e "   ${YELLOW}python main.py${NC}"
echo -e "\n${GREEN}Happy Music Streaming! 🎵${NC}\n"