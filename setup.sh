#!/bin/bash

# Exit on error
set -e

echo "Setting up Voice to Text..."

# Check and install system dependencies
echo "Checking system dependencies..."
if ! command -v unzip &> /dev/null; then
    echo "Installing unzip..."
    sudo pacman -S --noconfirm unzip
fi

if ! command -v wget &> /dev/null; then
    echo "Installing wget..."
    sudo pacman -S --noconfirm wget
fi

# Install system dependencies for sounddevice
echo "Installing system dependencies for audio..."
sudo pacman -S --noconfirm portaudio python-pip

# Create virtual environment
echo "Creating virtual environment..."
python -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Run system check and get model recommendation
echo "Running system check..."
python system_check.py

# Get the recommended model URL from the JSON file
MODEL_URL=$(python -c "import json; f=open('system_info.json'); data=json.load(f); print(data['model_recommendation']['download_url'])")

# Download Vosk model
echo "Downloading recommended Vosk model..."
mkdir -p ~/.vosk
cd ~/.vosk
wget "$MODEL_URL"
MODEL_ZIP=$(basename "$MODEL_URL")
unzip "$MODEL_ZIP"
mv "${MODEL_ZIP%.*}" model
cd -

echo "Setup complete! You can now run the application with:"
echo "source venv/bin/activate"
echo "python voicetotext.py" 