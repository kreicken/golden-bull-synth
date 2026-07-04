# Golden Bull & ASHERAH Workspace Overview

## What is it?
The **ASHERAH Production Suite & Golden Bull Synth** is a high-performance, retro-styled hybrid production environment for Linux. It combines a 4-track Piano Roll sequencer and an 8-track Drum Machine with the Golden Bull synthesis engine.

## Key Components
1. **`grid_ui.py` (ASHERAH - The Brain)**: The primary command center. It provides the GUI for the Piano Roll, Drum Machine (BEATS tab), Master Clock, and mixing/panning logic.
2. **`main.py` (Golden Bull - The Voice)**: The high-fidelity synth engine. It generates audio using NumPy (raw Sawtooth warmth, FM grit, Moog Ladder Filter, etc.) and receives real-time instructions.
3. **`beats_engine.py`**: Handles the drum machine logic, supporting external WAV samples or rendered Golden Bull one-shots.
4. **`presets.py` & `presets_kosmische.py`**: Libraries for factory presets that can be loaded into the synth or assigned to sequencer tracks.

## How it works with Station DAW
The suite is designed for standalone use, but has deep integration with the **Station Master DAW**:
- **Standalone Audio Routing**: Using `pipe_to_daw.sh`, the suite creates a PulseAudio null sink named `Asherah_Pipe`. You can select this virtual pipe as an input source in Station DAW or other Linux DAWs (via PipeWire/JACK) to record the audio.
- **Direct Tethering**: Station DAW can directly launch and manage Golden Bull or ASHERAH as if they were plugins. It sets up dedicated IPC and PulseAudio sinks (`station_track_X_pipe`) to capture the specific output of the synth directly into a DAW track.

## Up to Speed / Future Sessions
- **Architecture**: The application operates in a Master/Engine multi-process configuration. `grid_ui.py` controls timing and sequencing, sending low-latency UDP IPC messages to `main.py` which handles the audio callback loop.
- **Audio Processing**: Relies heavily on vectorized `numpy` operations for DSP to avoid traditional DAW bloat and ensure fast execution. 
- **Dependencies**: Uses `python-pedalboard` for effects, `numpy`, and standard Linux audio libraries (`libportaudio2`). Run from the `venv` virtual environment.
