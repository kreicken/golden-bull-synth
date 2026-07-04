#!/bin/bash
# DAW Integration Bootloader for ASHERAH Production Suite

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR" || exit

echo "Creating Virtual Audio Pipe for DAW Integration..."
# Check if sink already exists to avoid duplicates
if ! pactl list short sinks | grep -q "Asherah_Pipe"; then
    pactl load-module module-null-sink sink_name=Asherah_Pipe sink_properties=device.description="Asherah_Virtual_Pipe" 2>/dev/null || true
fi

# Force PortAudio ALSA/Pulse to output to our new virtual pipe
export PULSE_SINK=Asherah_Pipe

if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "Launching Golden Bull Synth Engine in DAW Mode..."
python3 main.py

