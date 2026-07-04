"""
beats_engine.py — ASHERAH Drum Machine Audio Engine
8-track sample/synth drum machine with independent playback.
Loads WAV samples or renders Golden Bull presets to one-shot buffers.
"""

import numpy as np
import sounddevice as sd
import wave
import threading

try:
    from pedalboard import Pedalboard, Reverb, Delay
    HAS_PEDALBOARD = True
except ImportError:
    HAS_PEDALBOARD = False

SAMPLE_RATE = 48000
MAX_VOICE_LENGTH = int(SAMPLE_RATE * 3.0)  # 3 seconds max per voice


def load_wav_sample(filepath):
    """Load a WAV file and return a float32 numpy array (mono, normalized)."""
    try:
        with wave.open(filepath, 'rb') as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()

            raw = wf.readframes(n_frames)

            if sampwidth == 1:
                data = np.frombuffer(raw, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0
            elif sampwidth == 2:
                data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            elif sampwidth == 3:
                samples = []
                for i in range(0, len(raw), 3):
                    val = int.from_bytes(raw[i:i+3], byteorder='little', signed=True)
                    samples.append(val / 8388608.0)
                data = np.array(samples, dtype=np.float32)
            elif sampwidth == 4:
                data = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
            else:
                return None

            # Convert to mono if stereo
            if n_channels > 1:
                data = data.reshape(-1, n_channels)
                data = data.mean(axis=1)

            # Resample if needed (linear interpolation)
            if framerate != SAMPLE_RATE:
                duration = len(data) / framerate
                new_len = int(duration * SAMPLE_RATE)
                indices = np.linspace(0, len(data) - 1, new_len)
                data = np.interp(indices, np.arange(len(data)), data)

            if len(data) > MAX_VOICE_LENGTH:
                data = data[:MAX_VOICE_LENGTH]

            # Normalize
            peak = np.max(np.abs(data))
            if peak > 0.001:
                data = data / peak * 0.9

            return data.astype(np.float32)
    except Exception as e:
        print(f"Error loading WAV '{filepath}': {e}")
        return None


def render_preset_sound(preset, midi_note, duration=1.5, sample_rate=SAMPLE_RATE):
    """
    Render a Golden Bull preset to a numpy array (one-shot drum hit).
    Uses a simplified offline version of the main synth engine.
    """
    frames = int(duration * sample_rate)
    freq = 440.0 * 2.0 ** ((midi_note - 69) / 12.0)

    # Extract preset params
    cutoff = preset.get("cutoff", 1000.0)
    resonance = preset.get("resonance", 0.0)
    drive = preset.get("drive", 1.0)

    env_amt = preset.get("env_amt", 5000.0)
    env_atk = max(preset.get("env_atk", 0.05), 0.001)
    env_dec = max(preset.get("env_dec", 0.3), 0.001)
    env_sus = preset.get("env_sus", 0.5)
    env_rel = max(preset.get("env_rel", 0.2), 0.001)

    fm_on = preset.get("fm_on", 0)
    fm_blend = preset.get("fm_blend", 0.0)
    fm_idx = preset.get("fm_idx", 0.0)
    fm_ratio = preset.get("fm_ratio", 1.0)

    fm_env_amt = preset.get("fm_env_amt", 0.0)
    fm_env_atk = max(preset.get("fm_env_atk", 0.1), 0.001)
    fm_env_dec = max(preset.get("fm_env_dec", 0.5), 0.001)
    fm_env_sus = preset.get("fm_env_sus", 0.0)
    fm_env_rel = max(preset.get("fm_env_rel", 0.2), 0.001)

    osc3_on = preset.get("osc3_on", 0)
    osc3_ratio = preset.get("osc3_ratio", 1.0)
    osc3_blend = preset.get("osc3_blend", 0.0)

    # Gate length: hold through attack+decay, then release
    gate_samples = int((env_atk + env_dec + 0.05) * sample_rate)
    gate_samples = min(gate_samples, frames - int(env_rel * sample_rate))
    gate_samples = max(gate_samples, int(0.05 * sample_rate))

    # ── Envelope rates for vectorized ADSR ───────────────────────
    atk_rate = 1.0 / (env_atk * sample_rate)
    dec_rate = 1.0 / (env_dec * sample_rate)
    rel_rate = 1.0 / (env_rel * sample_rate)
    fm_atk_rate = 1.0 / (fm_env_atk * sample_rate)
    fm_dec_rate = 1.0 / (fm_env_dec * sample_rate)
    fm_rel_rate = 1.0 / (fm_env_rel * sample_rate)

    # ── Generate ADSR envelope (vectorized) ─────────────────────────
    def _make_adsr(frames, atk_r, dec_r, sus_lvl, rel_r, gate_s):
        """Build a sample-accurate ADSR envelope as a numpy array."""
        env = np.zeros(frames, dtype=np.float32)
        # Attack phase
        atk_end = min(int(1.0 / atk_r), gate_s, frames)
        if atk_end > 0:
            env[:atk_end] = np.linspace(0.0, 1.0, atk_end, dtype=np.float32)
        # Decay phase
        dec_end = min(atk_end + int((1.0 - sus_lvl) / dec_r), gate_s, frames)
        if dec_end > atk_end:
            env[atk_end:dec_end] = np.linspace(1.0, sus_lvl, dec_end - atk_end, dtype=np.float32)
        # Sustain phase
        if gate_s > dec_end:
            env[dec_end:gate_s] = sus_lvl
        # Release phase
        rel_end = min(gate_s + int(sus_lvl / rel_r if rel_r > 0 else frames), frames)
        if rel_end > gate_s:
            start_val = env[gate_s - 1] if gate_s > 0 else sus_lvl
            env[gate_s:rel_end] = np.linspace(start_val, 0.0, rel_end - gate_s, dtype=np.float32)
        return env

    env_array    = _make_adsr(frames, atk_rate, dec_rate, env_sus, rel_rate, gate_samples)
    fm_env_array = _make_adsr(frames, fm_atk_rate, fm_dec_rate, fm_env_sus, fm_rel_rate, gate_samples)

    # ── Oscillators ──────────────────────────────────────────────
    t = np.arange(frames) / sample_rate
    phase = (freq * t) % 1.0
    saw = 2.0 * phase - 1.0

    if fm_on:
        mod_phase = (freq * fm_ratio * t) % 1.0
        current_fm_idx = fm_idx + fm_env_array * fm_env_amt
        mod_val = np.sin(2.0 * np.pi * mod_phase)
        fm_osc = np.sin(2.0 * np.pi * phase + current_fm_idx * mod_val)

        if osc3_on and osc3_blend > 0.0:
            osc3_phase = (freq * osc3_ratio * t) % 1.0
            osc3_val = 2.0 * osc3_phase - 1.0
        else:
            osc3_val = np.zeros(frames)

        osc1_level = max(0.0, 1.0 - fm_blend - osc3_blend)
        x_array = (saw * osc1_level + fm_osc * fm_blend + osc3_val * osc3_blend) * drive
    else:
        if osc3_on and osc3_blend > 0.0:
            osc3_phase = (freq * osc3_ratio * t) % 1.0
            osc3_val = 2.0 * osc3_phase - 1.0
            osc1_level = max(0.0, 1.0 - osc3_blend)
            x_array = (saw * osc1_level + osc3_val * osc3_blend) * drive
        else:
            x_array = saw * drive

    # ── Moog ladder filter ───────────────────────────────────────
    r = resonance * 4.0
    cutoff_arr = cutoff + env_array * env_amt
    cutoff_arr = np.clip(cutoff_arr, 20.0, 20000.0)
    f_norm = np.minimum(cutoff_arr / (sample_rate / 2.0), 0.99) * 1.5

    y0 = y1 = y2 = y3 = 0.0
    filtered = np.zeros(frames)

    for i in range(frames):
        f = f_norm[i]
        x_in = x_array[i] - r * y3
        y0 += f * (x_in - y0)
        y1 += f * (y0 - y1)
        y2 += f * (y1 - y2)
        y3 += f * (y2 - y3)
        y3 = max(-3.0, min(3.0, y3))
        filtered[i] = y3

    # Apply amplitude envelope
    filtered *= env_array

    # Normalize
    peak = np.max(np.abs(filtered))
    if peak > 0.001:
        filtered = filtered / peak * 0.9

    # Trim trailing silence (vectorized)
    nonzero = np.nonzero(np.abs(filtered) > 0.001)[0]
    if len(nonzero):
        last_nonzero = nonzero[-1]
        tail = min(int(0.02 * sample_rate), frames - last_nonzero - 1)
        filtered = filtered[:last_nonzero + tail + 1]

    return filtered.astype(np.float32)


class BeatsEngine:
    """Audio engine for the 8-track drum machine.
    
    Each track has a pre-rendered audio buffer (from WAV or synth preset).
    When triggered, the buffer plays back one-shot with per-track volume.
    Multiple tracks can play simultaneously.
    """

    def __init__(self, num_tracks=8, device=None, sink_name=None):
        self.num_tracks = num_tracks
        self.sample_rate = SAMPLE_RATE
        self.sink_name = sink_name

        # Track audio buffers (pre-rendered)
        self.track_buffers = [None] * num_tracks
        self.track_volumes = [0.8] * num_tracks
        self.track_pans = [0.0] * num_tracks # -1.0 to 1.0
        self.track_mutes = [False] * num_tracks
        self.track_solos = [False] * num_tracks

        # Tethered state export
        self.last_out_frame = np.zeros(64, dtype=np.float32)
        self.master_volume = 0.8
        self.fx_reverb = 0.0
        self.fx_delay = 0.0

        if HAS_PEDALBOARD:
            self.board = Pedalboard([
                Reverb(room_size=0.6, wet_level=0.0),
                Delay(delay_seconds=0.3, feedback=0.4, mix=0.0)
            ])

        # Active voices: list of [track_idx, playback_position]
        self.active_voices = []
        self.voice_lock = threading.Lock()

        # Audio stream
        self.stream = sd.OutputStream(
            device=device,
            samplerate=SAMPLE_RATE,
            blocksize=512,
            channels=2,
            callback=self._audio_callback,
            latency='low'
        )
        self.stream.start()

        if self.sink_name:
            import os
            import subprocess
            import time
            threading.Thread(target=self._anchor_to_tether, daemon=True).start()

    def _anchor_to_tether(self):
        """Programmatically move this process's audio stream to the virtual pipe."""
        import os
        import subprocess
        import time
        time.sleep(1.2) # Wait for stream to register
        try:
            pid = os.getpid()
            inputs = subprocess.check_output(["pactl", "list", "sink-inputs"]).decode()
            
            # Find our sink-input ID and move it
            # BeatsEngine might share a PID with grid_ui.py
            current_input_id = None
            sections = inputs.split("Sink Input #")
            for section in sections:
                if f"application.process.id = \"{pid}\"" in section:
                    # Check if it's already on the right sink
                    if f"Sink: {self.sink_name}" in section:
                        continue 
                    current_input_id = section.split("\n")[0].strip()
                    if current_input_id:
                        subprocess.run(["pactl", "move-sink-input", current_input_id, self.sink_name])
                        print(f"DEBUG: Successfully anchored beats (PID {pid}) to {self.sink_name}")
        except Exception as e:
            print(f"DEBUG: Beats failed to anchor: {e}")

    def set_track_buffer(self, track_idx, buffer):
        """Set the audio buffer for a track."""
        if 0 <= track_idx < self.num_tracks:
            self.track_buffers[track_idx] = buffer

    def trigger_track(self, track_idx):
        """Trigger playback of a track's sound."""
        if track_idx < 0 or track_idx >= self.num_tracks:
            return
        if self.track_buffers[track_idx] is None:
            return
        if self.track_mutes[track_idx]:
            return

        with self.voice_lock:
            # Retrigger: remove existing voice for this track
            self.active_voices = [v for v in self.active_voices if v[0] != track_idx]
            self.active_voices.append([track_idx, 0])

    def _audio_callback(self, outdata, frames, time_info, status):
        """Mix all active voices into stereo output."""
        output_l = np.zeros(frames, dtype=np.float32)
        output_r = np.zeros(frames, dtype=np.float32)

        with self.voice_lock:
            any_solo = any(self.track_solos)
            finished = []
            for i, voice in enumerate(self.active_voices):
                track_idx, pos = voice
                
                # Check Solo/Mute
                if any_solo and not self.track_solos[track_idx]:
                    continue
                if self.track_mutes[track_idx]:
                    continue

                buf = self.track_buffers[track_idx]
                if buf is None:
                    finished.append(i)
                    continue

                remaining = len(buf) - pos
                if remaining <= 0:
                    finished.append(i)
                    continue

                n = min(frames, remaining)
                chunk = buf[pos:pos + n]
                
                vol = self.track_volumes[track_idx]
                pan = self.track_pans[track_idx]
                
                l_mul = np.clip(1.0 - pan, 0.0, 1.0)
                r_mul = np.clip(1.0 + pan, 0.0, 1.0)
                
                output_l[:n] += chunk * vol * l_mul
                output_r[:n] += chunk * vol * r_mul
                
                voice[1] = pos + n
                if pos + n >= len(buf):
                    finished.append(i)

            for i in reversed(finished):
                if i < len(self.active_voices):
                    self.active_voices.pop(i)

        # Apply Master Volume and FX
        mix_stereo = np.zeros((frames, 2), dtype=np.float32)
        mix_stereo[:, 0] = output_l * self.master_volume
        mix_stereo[:, 1] = output_r * self.master_volume

        if HAS_PEDALBOARD:
            self.board[0].wet_level = self.fx_reverb
            self.board[1].mix = self.fx_delay
            # Pedalboard expects (channels, frames)
            mix_stereo = self.board(mix_stereo.T, sample_rate=SAMPLE_RATE).T

        outdata[:] = np.clip(mix_stereo, -1.0, 1.0)
        # Capture mono snippet for tethered state file
        self.last_out_frame = ((mix_stereo[:64, 0] + mix_stereo[:64, 1]) * 0.5).copy()

    def stop_all(self):
        """Kill all active voices."""
        with self.voice_lock:
            self.active_voices.clear()

    def shutdown(self):
        """Stop the audio stream."""
        self.stop_all()
        try:
            self.stream.stop()
        except Exception:
            pass
