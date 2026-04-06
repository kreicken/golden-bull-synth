# Golden Bull Hybrid Synthesizer

![Golden Bull UI Demo](bull.png)

A native, high-performance, retro-styled hybrid synthesizer built purely in Python. **No heavyweight VST wrappers or external bloated audio frameworks required.** The audio DSP engine compiles highly optimized vectorized math via NumPy directly against the real-time audio thread, making it blazingly fast even on low-end Linux hardware.

## Features

- **Hybrid DSP Engine**: 
  - **Subtractive Path**: Pure analog-style sawtooth waveform routed through a recursive 4-Pole Moog Ladder Filter.
  - **FM Path**: 2-Operator Phase Modulation (PM) engine generating complex metallic overtones. 
  - **Source Mixer**: Crossfade between raw sawtooth warmth and pure FM grit.
- **Dual Vector Envelopes**:
  - Independent 4-stage ADSR (Attack, Decay, Sustain, Release) envelope explicitly routed to modulate the Moog Cutoff Frequency.
  - Independent 4-stage ADSR envelope explicitly mapped to control dynamic sweeps of the FM Modulation Index.
- **Integrated Delay Line**: Built-in echo buffer matrix for spacious, trailing tails with adjustable time, feedback, and mix levels.
- **Arpeggiator**: Native lock-step arpeggiator engine featuring scale-quantization mapping, octave ranges, randomized pattern generation, and sync-rate divisors.
- **Retro Interface**: Programmed exclusively against Tkinter using the "PxPlus IBM VGA8" classic MS-DOS terminal typography. Optimized explicitly for touch-interfaces via custom variable-width Canvas sliders.
- **Preset Serialization**: Secure native-disk preset saving via JSON. State-matrices are dynamically preserved.

## Installation (Linux)

### 1. Requirements

Ensure you have Python 3 and the underlying system dependencies for `sounddevice` (PortAudio). On Debian/Ubuntu:

```bash
sudo apt-get update
sudo apt-get install python3-pip python3-venv libportaudio2 libasound-dev
```

### 2. Setup Virtual Environment

Clone the repository and set up a sandbox virtual environment:

```bash
git clone https://github.com/YOUR_GITHUB_NAME/golden-bull-synth.git
cd golden-bull-synth
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Font Recommendation
For the absolute best retro-aesthetic experience, install the [PxPlus IBM VGA8 TrueType Font](https://int10h.org/oldschool-pc-fonts/) natively into your `~/.fonts` directory. The UI defaults to standard system typefaces if this is missing.

## Usage

Boot the synthesis matrix from inside your virtual environment:

```bash
python3 main.py
```

### Controls:
- **Oscillator Key Triggers**: Your standard laptop keyboard (Keys: A, S, D, F, G, H, J, K) is mapped instantly to form a C4-C5 diatonic major scale. 
- **Modulation Sweep**: All UI sliders natively click/drag to sweep.

## Architecture Highlights
- Thread-safe bridging between the real-time `sounddevice` polling stream and the single-threaded `tkinter` event loop using explicit `threading.Lock()` hardware flags.
- Explicit frame-buffer chunking (BLOCK_SIZE 2048) coupled with aggressive `latency='high'` stream flags to ensure total stability against X-run stuttering during CPU spikes.

## License
Provided under the GNU General Public License v3.0 (GPL-3.0). You are free to copy, modify, and distribute the work, so long as modifications remain open source under the same license.
