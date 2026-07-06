#!/bin/bash
set -e

# Resolve directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=== Installing Golden Bull Synth ==="

# Install system packages (requires sudo)
echo "Installing system packages..."
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv libportaudio2 libasound-dev pkg-config libjack-jackd2-dev python3-tk

# Create virtual environment
echo "Setting up Python virtual environment..."
python3 -m venv venv

# Activate and install dependencies
echo "Installing dependencies..."
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt

# Create Desktop Launcher
echo "Creating Desktop Launcher..."
DESKTOP_FILE="$HOME/Desktop/golden-bull-synth.desktop"
cat <<EOF > "$DESKTOP_FILE"
[Desktop Entry]
Version=1.0
Type=Application
Name=Golden Bull Synth
Comment=ASHERAH Production Suite & Golden Bull Synth
Exec=bash $DIR/start.sh
Icon=$DIR/bull.png
Terminal=false
Categories=AudioVideo;Audio;
EOF
chmod +x "$DESKTOP_FILE"

echo "=== Installation Complete! ==="
echo "You can now start the Synth using the shortcut on your Desktop."
