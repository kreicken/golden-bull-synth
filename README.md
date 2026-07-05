# ASHERAH Production Suite & Golden Bull Synth

![ASHERAH Suite](bull.png)

**ASHERAH** is a high-performance, retro-styled hybrid production environment for Linux. It combines a sophisticated 4-track Piano Roll sequencer and an 8-track Drum Machine with the **Golden Bull** synthesis engine. 

Built purely in Python, this suite leverages NumPy for vectorized DSP and `python-pedalboard` for studio-grade stereo effects, delivering a professional audio experience without the bloat of traditional DAW wrappers.

## 🚀 The Dual-Window Architecture

The suite operates in a **Master/Engine** configuration:
1.  **ASHERAH (The Brain)**: The primary command center (`grid_ui.py`). It handles the Piano Roll, Drum Machine, Master Clock, and mixing/panning logic.
2.  **Golden Bull (The Voice)**: The high-fidelity synth engine (`main.py`). It receives real-time instructions from ASHERAH via low-latency UDP IPC.

## ✨ Core Features

### ASHERAH Sequencer
- **Consolidated Workspace**: Seamlessly switch between the **ROLL** (Synth) and **BEATS** (Drums) tabs.
- **Polyrhythmic Piano Roll**: 4 independent tracks with scale-folded Y-axis (Minor/Major/Pentatonic).
- **8-Track Drum Machine**: Hybrid engine supporting external WAV samples or rendered Golden Bull one-shots.
- **Precision Mixing**: Integrated per-track **Gain**, **Pan** (with snap-to-origin), and **Studio FX** (Reverb/Delay).
- **Virtual MIDI Output**: Route your sequences directly into DAWs like Bitwig, Reaper, or Ardour.

### Golden Bull Synth Engine
- **Hybrid DSP**: Crossfade between raw Sawtooth warmth and complex FM grit.
- **Moog Ladder Filter**: Recursive 4-pole filter with dedicated ADSR envelope.
- **Stereo Signal Path**: Native stereo output with per-voice panning and master volume.
- **Arpeggiator**: Sync-locked arpeggiator with octave ranges and pattern randomization.

## 🛠️ Installation (Linux)

You can install all dependencies and set up a Desktop Launcher automatically using the installer script, or install manually.

### Option A: Automated Installation (Recommended)
This will install system audio packages, set up a python virtual environment, install requirements, and create a Desktop launcher:
```bash
git clone https://github.com/kreicken/golden-bull-synth.git
cd golden-bull-synth
chmod +x install.sh
./install.sh
```

### Option B: Manual Installation
1. Install system dependencies:
```bash
sudo apt-get update
sudo apt-get install python3-pip python3-venv libportaudio2 libasound-dev
```
2. Clone, setup virtual environment, and install dependencies:
```bash
git clone https://github.com/kreicken/golden-bull-synth.git
cd golden-bull-synth
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Font Setup (Recommended)
For the authentic retro aesthetic, install the **PxPlus IBM VGA8** font. The UI will fallback to system fonts if missing.

## 🎹 Usage

Launch the entire suite with a single command:
```bash
./start.sh
```

### Tips:
- **Project Persistence**: Use the `SAVE` and `OPEN` buttons in the transport bar to preserve your patterns and sample selections.
- **Sample Browser**: In the BEATS tab, use the "Set as Default" button in the browser to lock your samples directory for future sessions.
- **Stereo Mixing**: Use the Pan sliders at the bottom of each tab. They will snap to the center and change color to **AMBER** when perfectly balanced.

## 🎛️ DAW Integration & Piping

ASHERAH is designed to play nicely with professional DAWs like Bitwig, Reaper, and Ardour.

### 1. MIDI Sync & Control
ASHERAH creates a virtual MIDI port named **"Asherah Sequencer"** upon launch.
- **Note Routing**: Set your DAW's track input to "Asherah Sequencer" to record the MIDI output of the Piano Roll live.
- **Clock Sync**: ASHERAH sends standard MIDI Clock (24 PPQN). In your DAW, enable "Receive MIDI Clock" from the Asherah port to sync your DAW's transport and BPM to the sequencer.

### 2. Audio Routing (PipeWire/JACK)
Since ASHERAH is a standalone application, you can route its audio into your DAW using Linux's modular audio system:
- **STATION MASTER DAW Integration**: We have implemented native support! Simply launch ASHERAH using `./pipe_to_daw.sh`. Then, open STATION MASTER DAW and select **"🌟 ASHERAH VIRTUAL PIPE"** from the Input Device dropdown. Your track will now record the pure Golden Bull audio stream perfectly.
- **Using qpwgraph / Carla**: Launch your routing tool and you will see "Golden Bull" and "Beats Engine" as stereo output nodes. Simply drag-and-drop connections to your DAW's "Audio Input" nodes.
- **Recording**: Create a Stereo Track in your DAW, set its input to the routed ASHERAH nodes, and hit Record to capture the high-fidelity NumPy-generated audio directly.

## 📜 License
ASHERAH is released under the GNU General Public License v3.0 (GPL-3.0).
