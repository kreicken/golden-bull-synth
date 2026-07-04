#!/bin/bash
# Bootloader for ASHERAH Production Suite

# Ensure we are in the project directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR" || exit

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "Launching Golden Bull Synth Engine..."
python3 main.py

