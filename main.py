import sys
import os

# --- TETHERED MODE BOOTSTRAP ---
# We must set PULSE_SINK before ANY audio imports (like sounddevice)
# so that PortAudio/PulseAudio correctly picks up the virtual pipe.
if "--tethered" in sys.argv:
    track_num = 0
    for arg in sys.argv:
        if arg.startswith("--track="):
            try: track_num = int(arg.split("=")[1])
            except: pass
            break
    if "--track" in sys.argv:
        try:
            idx = sys.argv.index("--track")
            track_num = int(sys.argv[idx + 1])
        except: pass
    
    pipe_name = f"station_track_{track_num}_pipe"
    os.environ['PULSE_SINK'] = pipe_name
    os.environ['PULSE_PROP'] = "media.role=music"
    os.environ['ALSA_PCM'] = "pulse" # Force ALSA to use pulse plugin
    print(f"DEBUG: Tethered mode enabled. Sink: {pipe_name}")

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import numpy as np
import sounddevice as sd
import json
import random
import math
import threading
from PIL import Image, ImageTk
import socket
import subprocess
import mido
import time
from presets import FACTORY_PRESETS as PRESETS
from music_theory import SCALES, midi_to_freq, freq_to_midi

# Force sounddevice to use PulseAudio device if available
if os.environ.get('PULSE_SINK'):
    try:
        # We explicitly look for 'pulse' or 'default' if it maps to pulse
        devices = sd.query_devices()
        target_idx = None
        for i, d in enumerate(devices):
            if d['name'] == 'pulse' and d['max_output_channels'] > 0:
                target_idx = i
                break
        
        if target_idx is not None:
            sd.default.device = (None, target_idx)
            print(f"DEBUG: Sounddevice forced to 'pulse' device (index {target_idx})")
        else:
            # Fallback: try to find any device that isn't the hardware speaker if we can't find 'pulse'
            print("DEBUG: 'pulse' device not found, keeping system default.")
    except Exception as e:
        print(f"DEBUG: Failed to force pulse device: {e}")

try:
    from pedalboard import Pedalboard, Reverb, Delay, Chorus
    HAS_PEDALBOARD = True
except ImportError:
    HAS_PEDALBOARD = False

SAMPLE_RATE = 48000
BLOCK_SIZE = 2048
PRESETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "presets")

KEY_FREQS = {
    'a': 261.63, # C4
    's': 293.66, # D4
    'd': 329.63, # E4
    'f': 349.23, # F4
    'g': 392.00, # G4
    'h': 440.00, # A4
    'j': 493.88, # B4
    'k': 523.25  # C5
}

# Using imported midi/freq functions from music_theory.py

class AudioEngine:
    def __init__(self):
        self.lock = threading.Lock()
        
        # Filter Audio Control Params
        self.cutoff = 1000.0
        self.resonance = 0.0
        self.drive = 1.0
        
        self.env_amt = 5000.0
        self.env_atk = 0.05
        self.env_dec = 0.3
        self.env_sus = 0.5
        self.env_rel = 0.2
        self.env_val = 0.0
        self.env_state = 0 # 0=IDLE, 1=ATK, 2=DEC, 3=SUS, 4=REL

        # VCA (Loudness) Envelope
        self.vca_atk = 0.01
        self.vca_dec = 0.3
        self.vca_sus = 1.0
        self.vca_rel = 0.1
        self.vca_val = 0.0
        self.vca_state = 0
        
        # FM Audio Control Params
        self.fm_on = True
        self.fm_blend = 0.0
        self.fm_index = 0.0
        self.fm_ratio = 1.0
        
        self.osc3_on = True
        self.osc3_ratio = 1.0      # detune: 0.5 = sub octave, 1.0 = unison,
                                   # 1.498 = fifth, 2.0 = octave up
        self.osc3_blend = 0.0      # mix level 0.0–1.0
        self.osc3_phase = 0.0
        
        self.fm_env_amt = 5.0
        self.fm_env_atk = 0.1
        self.fm_env_dec = 0.5
        self.fm_env_sus = 0.0
        self.fm_env_rel = 0.2
        self.fm_env_val = 0.0
        self.fm_env_state = 0
        
        # FX Params
        self.delay_on = True
        self.delay_time = 0.3
        self.delay_feedback = 0.3
        self.delay_mix = 0.2

        self.chorus_on = False
        self.chorus_rate = 1.0
        self.chorus_depth = 0.25
        self.chorus_mix = 0.0
        
        self.arp_on = False
        self.arp_scale_name = "Major"
        self.arp_octaves = 1
        self.arp_length = 4 
        self.arp_random = False
        self.arp_duration_beats = 0.25 
        self.arp_bpm = 120.0
        self.arp_pool = []

        # Master Mixer
        self.pan = 0.0          # -1.0 (L) to 1.0 (R)
        self.master_volume = 0.8
        self.reverb_wet = 0.0
        self.delay_wet = 0.0
        
        # Pedalboard setup
        if HAS_PEDALBOARD:
            self.board = Pedalboard([
                Chorus(rate_hz=1.0, depth=0.25, mix=0.0),
                Reverb(room_size=0.6, wet_level=0.0),
                Delay(delay_seconds=0.3, feedback=0.4, mix=0.0)
            ])
        
        # Internal DSP States
        self.is_playing = False
        self.base_midi = 60
        self.current_freq = 440.0
        self.velocity = 1.0
        self.note_stack = [] # Stack of (midi, freq, velocity) tuples for legato/monophonic priority
        
        self.phase = 0.0
        self.mod_phase = 0.0
        self.y0 = self.y1 = self.y2 = self.y3 = 0.0
        
        self.delay_len = SAMPLE_RATE * 2
        self.delay_buffer = np.zeros(self.delay_len)
        self.delay_idx = 0
        
        self.arp_sample_counter = 0
        self.arp_step = 0
        
        # Shadow states for lock-free audio thread mirroring
        self._sp_playing = False
        self._sp_cutoff = 1000.0
        self._sp_res = 0.0
        self._sp_drive = 1.0
        self._sp_vel = 1.0
        self._sp_env_amt = 5000.0
        self._sp_env_atk = 0.05
        self._sp_env_dec = 0.3
        self._sp_env_sus = 0.5
        self._sp_env_rel = 0.2

        self._sp_vca_atk = 0.01
        self._sp_vca_dec = 0.3
        self._sp_vca_sus = 1.0
        self._sp_vca_rel = 0.1
        
        self._sp_fm_on = True
        self._sp_fm_blend = 0.0
        self._sp_fm_idx = 0.0
        self._sp_fm_ratio = 1.0
        
        self._sp_osc3_on    = True
        self._sp_osc3_ratio = 1.0
        self._sp_osc3_blend = 0.0
        self._sp_fm_env_amt = 5.0
        self._sp_fm_env_atk = 0.1
        self._sp_fm_env_dec = 0.5
        self._sp_fm_env_sus = 0.0
        self._sp_fm_env_rel = 0.2
        
        self._sp_pan = 0.0
        self._sp_master_vol = 0.8
        self._sp_reverb_wet = 0.0
        self._sp_delay_wet = 0.0
        
        self._sp_d_on = True
        self._sp_d_time = 0.3
        self._sp_d_feed = 0.3
        self._sp_d_mix = 0.2

        self._sp_c_on = False
        self._sp_c_rate = 1.0
        self._sp_c_depth = 0.25
        self._sp_c_mix = 0.0
        
        self._sp_arp_on = False
        self._sp_arp_rnd = False
        self._sp_arp_bpm = 120.0
        self._sp_arp_dur = 0.25
        self._sp_arp_pool = []
        
        self.scope_callback = None
        
        # Consistent Retro Green Colors
        self.theme_green = "#00FF00" 
        self.theme_black = "#000000"
        self.theme_grey = "#444444"
        self.theme_gold = "#FFD700"
        
        self.stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            channels=2,
            callback=self.audio_callback,
            latency='high'
        )

        # Tethered mode: last audio frame for state file export
        self.last_out_frame = np.zeros(64, dtype=np.float32)
        
    def start(self):
        self.stream.start()
        # If tethered, ensure the sink exists and move our stream to it
        if "--tethered" in sys.argv:
            threading.Thread(target=self._anchor_to_tether, daemon=True).start()
        
    def _anchor_to_tether(self):
        """Programmatically move this process's audio stream to the virtual pipe."""
        time.sleep(1.0) # Wait for stream to register with PulseAudio
        try:
            track_num = 0
            for arg in sys.argv:
                if arg.startswith("--track="):
                    track_num = int(arg.split("=")[1])
                    break
            if "--track" in sys.argv:
                idx = sys.argv.index("--track")
                track_num = int(sys.argv[idx + 1])
            
            sink_name = f"station_track_{track_num}_pipe"
            
            # 1. Ensure sink exists
            sinks = subprocess.check_output(["pactl", "list", "short", "sinks"]).decode()
            if sink_name not in sinks:
                subprocess.run(["pactl", "load-module", "module-null-sink", 
                                f"sink_name={sink_name}", 
                                f"sink_properties=device.description={sink_name}"])
                time.sleep(0.5)

            # 2. Find our sink-input ID and move it
            pid = os.getpid()
            inputs = subprocess.check_output(["pactl", "list", "sink-inputs"]).decode()
            
            current_input_id = None
            sections = inputs.split("Sink Input #")
            for section in sections:
                if f"application.process.id = \"{pid}\"" in section:
                    current_input_id = section.split("\n")[0].strip()
                    break
            
            if current_input_id:
                subprocess.run(["pactl", "move-sink-input", current_input_id, sink_name])
                print(f"DEBUG: Successfully anchored synth (PID {pid}) to {sink_name}")
        except Exception as e:
            print(f"DEBUG: Failed to anchor to tether: {e}")

    def stop(self):
        self.stream.stop()
        
    def set_note(self, freq, vel=None, legato=False):
        with self.lock:
            midi = int(round(freq_to_midi(freq)))
            # Remove if already in stack to move to top
            self.note_stack = [n for n in self.note_stack if n[0] != midi]
            self.note_stack.append((midi, freq, vel if vel is not None else self.velocity))
            self._apply_top_note(legato=legato)

    def release_note(self, freq=None):
        with self.lock:
            if freq is not None:
                midi = int(round(freq_to_midi(freq)))
                self.note_stack = [n for n in self.note_stack if n[0] != midi]
            else:
                # If no freq provided, clear stack as a fallback (kill-all/sequencer)
                self.note_stack = []

            if not self.note_stack:
                self.is_playing = False
                self.env_state = 4 # Release Switch
                self.vca_state = 4
                self.fm_env_state = 4
            else:
                self._apply_top_note(legato=True)

    def _apply_top_note(self, legato=False):
        if not self.note_stack: return
        midi, freq, vel = self.note_stack[-1]
        self.current_freq = freq
        self.base_midi = midi
        self.velocity = vel
        self.is_playing = True
        
        if not legato:
            self.env_state = 1
            self.vca_state = 1
            self.fm_env_state = 1
            
            if self.arp_on:
                self.arp_sample_counter = 0
                self.arp_step = 0
                self._recalc_arp_pool_internal()

    def _recalc_arp_pool_internal(self):
        scale_offsets = SCALES.get(self.arp_scale_name, SCALES["Major"])
        pool = []
        for oct in range(self.arp_octaves):
            for offset in scale_offsets:
                pool.append(self.base_midi + offset + 12 * oct)
        self.arp_pool = pool[:self.arp_length]

    def update_arp_pool(self):
        with self.lock:
            if self.is_playing:
                self._recalc_arp_pool_internal()

    def audio_callback(self, outdata, frames, time, status):
        # 1. Fast Parameter State Capture (Non-Blocking)
        if self.lock.acquire(blocking=False):
            try:
                self._sp_playing = self.is_playing
                
                self._sp_cutoff = self.cutoff
                self._sp_res = self.resonance
                self._sp_drive = self.drive
                self._sp_vel = self.velocity
                self._sp_env_amt = self.env_amt
                self._sp_env_atk = self.env_atk
                self._sp_env_dec = self.env_dec
                self._sp_env_sus = self.env_sus
                self._sp_env_rel = self.env_rel
                
                self._sp_vca_atk = self.vca_atk
                self._sp_vca_dec = self.vca_dec
                self._sp_vca_sus = self.vca_sus
                self._sp_vca_rel = self.vca_rel

                self._sp_fm_on = self.fm_on
                self._sp_fm_blend = self.fm_blend
                self._sp_fm_idx = self.fm_index
                self._sp_fm_ratio = self.fm_ratio
                self._sp_fm_env_amt = self.fm_env_amt
                self._sp_fm_env_atk = self.fm_env_atk
                self._sp_fm_env_dec = self.fm_env_dec
                self._sp_fm_env_sus = self.fm_env_sus
                self._sp_fm_env_rel = self.fm_env_rel
                
                self._sp_d_on = self.delay_on
                self._sp_d_time = self.delay_time
                self._sp_d_feed = self.delay_feedback
                self._sp_d_mix = self.delay_mix

                self._sp_c_on = self.chorus_on
                self._sp_c_rate = self.chorus_rate
                self._sp_c_depth = self.chorus_depth
                self._sp_c_mix = self.chorus_mix

                self._sp_pan = self.pan
                self._sp_master_vol = self.master_volume
                self._sp_reverb_wet = self.reverb_wet
                self._sp_delay_wet = self.delay_wet
                
                # Sync pedalboard params
                if HAS_PEDALBOARD:
                    self.board[0].rate_hz = self._sp_c_rate
                    self.board[0].depth = self._sp_c_depth
                    self.board[0].mix = self._sp_c_mix if self._sp_c_on else 0.0
                    self.board[1].wet_level = self._sp_reverb_wet
                    self.board[2].mix = self._sp_delay_wet
                
                self._sp_arp_on = self.arp_on
                self._sp_arp_rnd = self.arp_random
                self._sp_arp_bpm = self.arp_bpm
                self._sp_arp_dur = self.arp_duration_beats
                self._sp_arp_pool = list(self.arp_pool) 
                
                self._sp_osc3_on    = self.osc3_on
                self._sp_osc3_ratio = self.osc3_ratio
                self._sp_osc3_blend = self.osc3_blend
            finally:
                self.lock.release()
                
        r = self._sp_res * 4.0
        d_mix = self._sp_d_mix
        d_feed = self._sp_d_feed
        d_samples = int(self._sp_d_time * SAMPLE_RATE)
        buf_len = self.delay_len
        
        filtered = np.zeros(frames)
        d_idx = self.delay_idx

        # Pre-Compile Filter Envelope Array
        env_array = np.zeros(frames)
        atk_rate = 1.0 / (max(self._sp_env_atk, 0.001) * SAMPLE_RATE)
        dec_rate = 1.0 / (max(self._sp_env_dec, 0.001) * SAMPLE_RATE)
        rel_rate = 1.0 / (max(self._sp_env_rel, 0.001) * SAMPLE_RATE)
        sus_lev = self._sp_env_sus
        
        # Pre-Compile FM Envelope Array
        fm_env_array = np.zeros(frames)
        fm_atk_rate = 1.0 / (max(self._sp_fm_env_atk, 0.001) * SAMPLE_RATE)
        fm_dec_rate = 1.0 / (max(self._sp_fm_env_dec, 0.001) * SAMPLE_RATE)
        fm_rel_rate = 1.0 / (max(self._sp_fm_env_rel, 0.001) * SAMPLE_RATE)
        fm_sus_lev = self._sp_fm_env_sus

        # Pre-Compile VCA Envelope Array
        vca_env_array = np.zeros(frames)
        vca_atk_rate = 1.0 / (max(self._sp_vca_atk, 0.001) * SAMPLE_RATE)
        vca_dec_rate = 1.0 / (max(self._sp_vca_dec, 0.001) * SAMPLE_RATE)
        vca_rel_rate = 1.0 / (max(self._sp_vca_rel, 0.001) * SAMPLE_RATE)
        vca_sus_lev = self._sp_vca_sus
        
        freq_array = np.full(frames, self.current_freq)

        # Vector State Sync Loop
        for i in range(frames):
            
            # ARP Engine Stepping
            if self._sp_playing and self._sp_arp_on and len(self._sp_arp_pool) > 0:
                samples_per_step = int((60.0 / self._sp_arp_bpm) * SAMPLE_RATE * self._sp_arp_dur)
                if samples_per_step > 0:
                    if self.arp_sample_counter >= samples_per_step:
                        self.arp_sample_counter = 0
                        if self._sp_arp_rnd:
                            self.arp_step = random.randint(0, len(self._sp_arp_pool) - 1)
                        else:
                            self.arp_step = (self.arp_step + 1) % len(self._sp_arp_pool)
                        self.current_freq = midi_to_freq(self._sp_arp_pool[self.arp_step])
                        
                        # Retrigger Envelopes
                        self.env_state = 1 
                        self.vca_state = 1
                        self.fm_env_state = 1
                    self.arp_sample_counter += 1
            
            freq_array[i] = self.current_freq
            
            # Key Release Overrides
            if not self._sp_playing:
                if self.env_state != 0 and self.env_state != 4:
                    self.env_state = 4 
                if self.vca_state != 0 and self.vca_state != 4:
                    self.vca_state = 4
                if self.fm_env_state != 0 and self.fm_env_state != 4:
                    self.fm_env_state = 4
                
            # Filter ADSR Tick
            if self.env_state == 1:
                self.env_val += atk_rate
                if self.env_val >= 1.0:
                    self.env_val = 1.0
                    self.env_state = 2
            elif self.env_state == 2:
                self.env_val -= dec_rate
                if self.env_val <= sus_lev:
                    self.env_val = sus_lev
                    self.env_state = 3
            elif self.env_state == 4:
                self.env_val -= rel_rate
                if self.env_val <= 0.0:
                    self.env_val = 0.0
                    self.env_state = 0
            env_array[i] = self.env_val

            # VCA ADSR Tick
            if self.vca_state == 1:
                self.vca_val += vca_atk_rate
                if self.vca_val >= 1.0:
                    self.vca_val = 1.0
                    self.vca_state = 2
            elif self.vca_state == 2:
                self.vca_val -= vca_dec_rate
                if self.vca_val <= vca_sus_lev:
                    self.vca_val = vca_sus_lev
                    self.vca_state = 3
            elif self.vca_state == 4:
                self.vca_val -= vca_rel_rate
                if self.vca_val <= 0.0:
                    self.vca_val = 0.0
                    self.vca_state = 0
            vca_env_array[i] = self.vca_val
            
            # FM SWELL ADSR Tick
            if self.fm_env_state == 1:
                self.fm_env_val += fm_atk_rate
                if self.fm_env_val >= 1.0:
                    self.fm_env_val = 1.0
                    self.fm_env_state = 2
            elif self.fm_env_state == 2:
                self.fm_env_val -= fm_dec_rate
                if self.fm_env_val <= fm_sus_lev:
                    self.fm_env_val = fm_sus_lev
                    self.fm_env_state = 3
            elif self.fm_env_state == 4:
                self.fm_env_val -= fm_rel_rate
                if self.fm_env_val <= 0.0:
                    self.fm_env_val = 0.0
                    self.fm_env_state = 0
            fm_env_array[i] = self.fm_env_val

        # Active if EITHER playing OR VCA is still releasing
        if self._sp_playing or self.vca_state != 0:
            # OSCILLATORS: Vectorized Phase math
            dt_array = freq_array / SAMPLE_RATE
            phases_cont = self.phase + np.cumsum(dt_array)
            phases = phases_cont % 1.0
            self.phase = phases_cont[-1] % 1.0
            
            saw_val = 2.0 * phases - 1.0
            
            if self._sp_fm_on:
                dt_mod_array = dt_array * self._sp_fm_ratio
                mod_phases_cont = self.mod_phase + np.cumsum(dt_mod_array)
                mod_phases = mod_phases_cont % 1.0
                self.mod_phase = mod_phases_cont[-1] % 1.0
                
                # Apply Dynamic FM Swell envelope to the base Index
                current_fm_idx_array = self._sp_fm_idx + (fm_env_array * self._sp_fm_env_amt)
                
                mod_val = np.sin(2.0 * np.pi * mod_phases)
                fm_val = np.sin(2.0 * np.pi * phases + current_fm_idx_array * mod_val)
                
                # OSC 3 — ratio-detuned sawtooth
                if self._sp_osc3_on and self._sp_osc3_blend > 0.0:
                    dt_osc3 = (freq_array * self._sp_osc3_ratio) / SAMPLE_RATE
                    osc3_phases_cont = self.osc3_phase + np.cumsum(dt_osc3)
                    osc3_phases = osc3_phases_cont % 1.0
                    self.osc3_phase = osc3_phases_cont[-1] % 1.0
                    osc3_val = 2.0 * osc3_phases - 1.0
                else:
                    osc3_val = np.zeros(frames)
                    self.osc3_phase = (self.osc3_phase + np.sum(freq_array / SAMPLE_RATE)) % 1.0

                # Three-way mix — blends should sum to <= 1.0
                osc1_level = max(0.0, 1.0 - self._sp_fm_blend - self._sp_osc3_blend)
                mixed_src_array = (
                    saw_val  * osc1_level +
                    fm_val   * self._sp_fm_blend +
                    osc3_val * self._sp_osc3_blend
                )
                x_array = mixed_src_array * self._sp_drive * self._sp_vel * vca_env_array
            else:
                x_array = saw_val * self._sp_drive * self._sp_vel * vca_env_array
        else:
            x_array = np.zeros(frames)
            
        # Modulate dynamic Cutoff vector mapping
        cutoff_array = self._sp_cutoff + (env_array * self._sp_env_amt)
        cutoff_array = np.clip(cutoff_array, 20.0, 20000.0)
        f_norm_array = np.minimum(cutoff_array / (SAMPLE_RATE / 2.0), 0.99)
        f_val_array = f_norm_array * 1.5
            
        # Recursive Moog Feedback Loop 
        y0, y1, y2, y3 = self.y0, self.y1, self.y2, self.y3
        delay_buf = self.delay_buffer

        for i in range(frames):
            
            f_val = f_val_array[i]
            x = x_array[i]
            x_in = x - r * y3
            y0 += f_val * (x_in - y0)
            y1 += f_val * (y0 - y1)
            y2 += f_val * (y1 - y2)
            y3 += f_val * (y2 - y3)
            
            if y3 > 3.0: y3 = 3.0
            elif y3 < -3.0: y3 = -3.0
            
            out_sample = y3
            
            if self._sp_d_on:
                r_idx = int((d_idx - d_samples)) % buf_len
                d_out = delay_buf[r_idx]
                
                delay_buf[d_idx] = out_sample + d_out * d_feed
                d_idx = (d_idx + 1) % buf_len
                
                filtered[i] = out_sample * (1.0 - d_mix) + d_out * d_mix
            else:
                filtered[i] = out_sample
            
        self.y0, self.y1, self.y2, self.y3 = y0, y1, y2, y3
        self.delay_idx = d_idx
        
        vol = self._sp_master_vol
        pan_val = self._sp_pan
        l_mul = np.clip(1.0 - pan_val, 0.0, 1.0)
        r_mul = np.clip(1.0 + pan_val, 0.0, 1.0)

        out_stereo = np.zeros((frames, 2), dtype=np.float32)
        out_stereo[:, 0] = filtered * l_mul * vol
        out_stereo[:, 1] = filtered * r_mul * vol

        # Apply Pedalboard FX
        if HAS_PEDALBOARD:
            # Pedalboard expects (channels, frames)
            out_stereo = self.board(out_stereo.T, sample_rate=SAMPLE_RATE).T

        outdata[:] = np.clip(out_stereo, -1.0, 1.0)
        
        if self.scope_callback:
            self.scope_callback(filtered.copy())

        # Capture snippet for tethered state file
        self.last_out_frame = filtered[:64].copy()


class CanvasSlider(tk.Canvas):
    def __init__(self, parent, variable, from_val, to_val, command, resolution, length, width, bg_color, fg_color, fill_color, trough_color):
        super().__init__(parent, width=length, height=width, bg=trough_color, highlightthickness=2, highlightbackground=fg_color)
        self.variable = variable
        self.from_val = from_val
        self.to_val = max(to_val, from_val + 1e-6) # prevent div/0
        self.command = command
        self.resolution = resolution
        self.slider_length = length
        self.slider_width = width
        self.fill_color = fill_color
        self.fg_color = fg_color
        
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<Button-1>", self.on_drag)
        
        self.variable.trace_add("write", self.draw)
        self.after(50, self.draw)
        
    def on_drag(self, event):
        x = max(0, min(event.x, self.slider_length))
        ratio = x / self.slider_length
        val = self.from_val + ratio * (self.to_val - self.from_val)
        if self.resolution > 0:
            val = round(val / self.resolution) * self.resolution
        self.variable.set(val)
        self.command()
            
    def draw(self, *args):
        self.delete("all")
        val = self.variable.get()
        ratio = (val - self.from_val) / (self.to_val - self.from_val)
        ratio = max(0.0, min(1.0, ratio))
        x = ratio * self.slider_length
        
        if x > 0:
            self.create_rectangle(0, 0, x, self.slider_width, fill=self.fill_color, width=0)
            
        hw = 12
        self.create_rectangle(x - hw/2, 0, x + hw/2, self.slider_width, fill=self.fg_color, outline="#888888", width=1)


class SynthGUI:
    def __init__(self, master, audio_engine, udp_port=12160):
        self.master = master
        self.audio_engine = audio_engine
        self.udp_port = udp_port
        self.master.title("GOLDEN BULL HYBRID SYNTHESIZER")
        self.master.geometry("1100x900") # Adjusted for VCA panel
        
        self.bg_color = "#18224b"     # Dark Navy (Third Color)
        self.fg_color = "#f4e022"     # Yellow (First Color)
        self.accent_purple = "#5a37c3" # Purple (Second Color)
        self.accent_red = "#de1b4a"    # Red (Fourth Color)
        
        self.font = ("PxPlus IBM VGA8", 12)
        self.title_font = ("PxPlus IBM VGA8", 22)
        
        self.master.configure(bg=self.bg_color)
        self.settings_file = "settings.json"
        
        try:
            self.icon_img = Image.open("bull.png")
            self.taskbar_icon = ImageTk.PhotoImage(self.icon_img)
            self.master.iconphoto(True, self.taskbar_icon)
        except Exception as e:
            print(f"Warning: Could not load window icon: {e}")
            self.icon_img = None
            
        self.active_key = None
        
        self.setup_ui()
        self.bind_events()
        
        self.audio_engine.scope_callback = self.update_scope
        self.master.after(60, self.render_scope_loop)
        self.scope_buffer = np.zeros(BLOCK_SIZE)
        self.start_udp_server()
        self.start_midi_listener()
        
    def start_midi_listener(self):
        self.midi_in_ports = {}
        threading.Thread(target=self.midi_input_loop, daemon=True).start()

    def midi_input_loop(self):
        while True:
            try:
                available = mido.get_input_names()
                # Remove stale ports
                stale = [name for name in self.midi_in_ports if name not in available]
                for name in stale:
                    try: self.midi_in_ports[name].close()
                    except: pass
                    del self.midi_in_ports[name]
                    print(f"MIDI Disconnected: {name}")

                for port_name in available:
                    if port_name not in self.midi_in_ports:
                        if "Through" in port_name: continue # Skip through ports
                        try:
                            port = mido.open_input(port_name, callback=self.midi_callback)
                            self.midi_in_ports[port_name] = port
                            print(f"MIDI Connected: {port_name}")
                        except: pass
                
                time.sleep(2)
            except Exception:
                time.sleep(5)

    def midi_callback(self, msg):
        if msg.type == 'note_on':
            if msg.velocity > 0:
                self.audio_engine.set_note(midi_to_freq(msg.note), vel=msg.velocity / 127.0)
            else:
                self.audio_engine.release_note(midi_to_freq(msg.note))
        elif msg.type == 'note_off':
            self.audio_engine.release_note(midi_to_freq(msg.note))

    def start_udp_server(self):
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.udp_sock.bind(('127.0.0.1', self.udp_port))
        except OSError:
            pass # Port already in use, skip IPC if standalone or colliding
        self.udp_sock.setblocking(False)
        self.poll_udp()
        
    def poll_udp(self):
        try:
            while True:
                data, addr = self.udp_sock.recvfrom(4096)
                self.handle_ipc(data, addr)
        except BlockingIOError:
            pass
        except Exception as e:
            pass
        self.master.after(5, self.poll_udp)
        
    def handle_ipc(self, data, addr):
        try:
            msg = json.loads(data.decode('utf-8'))
            action = msg.get("action")
            
            if action == "PARAM_UPDATE":
                with self.audio_engine.lock:
                    for k, v in msg.get("params", {}).items():
                        if hasattr(self.audio_engine, k):
                            setattr(self.audio_engine, k, float(v))
            elif action == "TRIGGER":
                freq = msg.get("freq", 440.0)
                vel = msg.get("vel", 1.0)
                legato = msg.get("legato", False)
                
                # Apply per-slot mixing parameters if provided
                with self.audio_engine.lock:
                    if "pan" in msg:
                        self.audio_engine.pan = float(msg["pan"])
                    if "reverb_wet" in msg:
                        self.audio_engine.reverb_wet = float(msg["reverb_wet"])
                    if "delay_wet" in msg:
                        self.audio_engine.delay_wet = float(msg["delay_wet"])
                        
                self.audio_engine.set_note(freq, vel=vel, legato=legato)
            elif action == "RELEASE":
                self.audio_engine.release_note()
            elif action == "REQUEST_STATE":
                state = {
                    "cutoff": self.cutoff_var.get(),
                    "resonance": self.res_var.get(),
                    "drive": self.drive_var.get(),
                    "fm_index": self.fm_idx_var.get(),
                    "fm_ratio": self.fm_ratio_var.get(),
                    "env_amt": self.env_amt_var.get(),
                    "chorus_mix": self.chorus_mix_var.get(),
                    "reverb_wet": self.reverb_wet_var.get()
                }
                reply = json.dumps({"action": "STATE_REPLY", "state": state}).encode('utf-8')
                self.udp_sock.sendto(reply, addr)
        except Exception as e:
            pass

    def setup_ui(self):
        header_frame = tk.Frame(self.master, bg=self.bg_color)
        header_frame.pack(pady=10)
        
        if hasattr(self, 'icon_img') and self.icon_img:
            try:
                scaled_img = self.icon_img.resize((60, 60), Image.LANCZOS)
                self.header_logo = ImageTk.PhotoImage(scaled_img)
                logo_btn = tk.Button(header_frame, image=self.header_logo, bg=self.bg_color,
                    activebackground=self.accent_purple, relief=tk.FLAT, bd=0,
                    command=self.show_preset_menu, cursor="hand2")
                logo_btn.pack(side=tk.LEFT, padx=10)
            except Exception as e:
                print(f"Warning: Could not load header icon: {e}")

        header = tk.Label(header_frame, text="GOLDEN BULL HYBRID SYNTHESIZER", bg=self.bg_color, fg=self.fg_color, font=self.title_font)
        header.pack(side=tk.LEFT, padx=10)
        
        # ASHERAH SEQUENCER BUTTON - PROMOTED TO HEADER
        self.seq_btn = tk.Button(header_frame, text="[ OPEN ASHERAH SEQUENCER ]", bg=self.accent_red, fg=self.fg_color, font=self.font, command=lambda: subprocess.Popen([sys.executable, "grid_ui.py"]), activebackground=self.fg_color, activeforeground=self.bg_color, relief=tk.RAISED, pady=5)
        self.seq_btn.pack(side=tk.LEFT, padx=30)
        
        if hasattr(self, 'header_logo'):
            user_preset_btn = tk.Button(header_frame, image=self.header_logo, bg=self.bg_color,
                activebackground=self.accent_purple, relief=tk.FLAT, bd=0,
                command=self.show_user_preset_menu, cursor="hand2")
            user_preset_btn.pack(side=tk.LEFT, padx=10)
        
        main_frame = tk.Frame(self.master, bg=self.bg_color)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        # --- SPLIT ROW 1 (Moog & Envelopes) ---
        top_split = tk.Frame(main_frame, bg=self.bg_color)
        top_split.pack(fill=tk.X, pady=5)
        
        controls_frame = tk.LabelFrame(top_split, text=" MOOG LADDER ", bg=self.bg_color, fg=self.fg_color, font=self.font, highlightthickness=2, highlightbackground=self.accent_purple, labelanchor='n')
        controls_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))
        
        self.cutoff_var = tk.DoubleVar(value=1000.0)
        self.create_control_row(controls_frame, "CUTOFF", self.cutoff_var, 20.0, 20000.0, self.update_params, length=120)
        
        self.res_var = tk.DoubleVar(value=0.0)
        self.create_control_row(controls_frame, "RESON.", self.res_var, 0.0, 1.0, self.update_params, resolution=0.01, length=120)
        
        self.drive_var = tk.DoubleVar(value=1.0)
        self.create_control_row(controls_frame, "DRIVE", self.drive_var, 1.0, 5.0, self.update_params, resolution=0.1, length=120)

        env_frame = tk.LabelFrame(top_split, text=" FILTER ADSR ", bg=self.bg_color, fg=self.fg_color, font=self.font, highlightthickness=2, highlightbackground=self.accent_purple, labelanchor='n')
        env_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5,0))
        
        self.env_amt_var = tk.DoubleVar(value=5000.0)
        self.create_control_row(env_frame, "ENV AMT", self.env_amt_var, -8000.0, 8000.0, self.update_env, 10.0, length=120)
        
        self.env_atk_var = tk.DoubleVar(value=0.05)
        self.create_control_row(env_frame, "ATTACK", self.env_atk_var, 0.01, 3.0, self.update_env, 0.01, length=120)
        
        self.env_dec_var = tk.DoubleVar(value=0.3)
        self.create_control_row(env_frame, "DECAY", self.env_dec_var, 0.01, 3.0, self.update_env, 0.01, length=120)
        
        self.env_sus_var = tk.DoubleVar(value=0.5)
        self.create_control_row(env_frame, "SUSTAIN", self.env_sus_var, 0.0, 1.0, self.update_env, 0.01, length=120)
        
        self.env_rel_var = tk.DoubleVar(value=0.2)
        self.create_control_row(env_frame, "RELEASE", self.env_rel_var, 0.01, 3.0, self.update_env, 0.01, length=120)

        vca_frame = tk.LabelFrame(top_split, text=" LOUDNESS CONTOUR ", bg=self.bg_color, fg=self.fg_color, font=self.font, highlightthickness=2, highlightbackground=self.accent_purple, labelanchor='n')
        vca_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5,0))
        
        self.vca_atk_var = tk.DoubleVar(value=0.01)
        self.create_control_row(vca_frame, "ATTACK", self.vca_atk_var, 0.01, 3.0, self.update_vca, 0.01, length=120)
        
        self.vca_dec_var = tk.DoubleVar(value=0.3)
        self.create_control_row(vca_frame, "DECAY", self.vca_dec_var, 0.01, 3.0, self.update_vca, 0.01, length=120)
        
        self.vca_sus_var = tk.DoubleVar(value=1.0)
        self.create_control_row(vca_frame, "SUSTAIN", self.vca_sus_var, 0.0, 1.0, self.update_vca, 0.01, length=120)
        
        self.vca_rel_var = tk.DoubleVar(value=0.1)
        self.create_control_row(vca_frame, "RELEASE", self.vca_rel_var, 0.01, 3.0, self.update_vca, 0.01, length=120)


        # --- SPLIT ROW 2 (FM ENGINE & FM ADSR) ---
        fm_split = tk.Frame(main_frame, bg=self.bg_color)
        fm_split.pack(fill=tk.X, pady=5)
        
        fm_frame = tk.LabelFrame(fm_split, text=" FM CONTROLS ", bg=self.bg_color, fg=self.fg_color, font=self.font, highlightthickness=2, highlightbackground=self.accent_purple, labelanchor='n')
        fm_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))
        
        fm_top = tk.Frame(fm_frame, bg=self.bg_color)
        fm_top.pack(fill=tk.X, padx=10, pady=2)
        
        tk.Label(fm_top, text="FM ENGINE STATE:", bg=self.bg_color, fg=self.fg_color, font=self.font).pack(side=tk.LEFT, padx=5)
        
        self.fm_on_var = tk.IntVar(value=1)
        tk.Radiobutton(fm_top, text=" ON ", variable=self.fm_on_var, value=1, command=self.update_fm, indicatoron=0, bg=self.accent_purple, fg=self.fg_color, selectcolor=self.bg_color, font=self.font).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(fm_top, text=" OFF ", variable=self.fm_on_var, value=0, command=self.update_fm, indicatoron=0, bg=self.accent_purple, fg=self.fg_color, selectcolor=self.bg_color, font=self.font).pack(side=tk.LEFT, padx=5)
        
        self.fm_blend_var = tk.DoubleVar(value=0.0)
        self.create_control_row(fm_frame, "BLEND", self.fm_blend_var, 0.0, 1.0, self.update_fm, resolution=0.01, length=120)
        
        self.fm_idx_var = tk.DoubleVar(value=0.0)
        self.create_control_row(fm_frame, "BASE ID", self.fm_idx_var, 0.0, 20.0, self.update_fm, resolution=0.1, length=120)
        
        self.fm_ratio_var = tk.DoubleVar(value=1.0)
        self.create_control_row(fm_frame, "RATIO", self.fm_ratio_var, 0.25, 10.0, self.update_fm, resolution=0.01, length=120)
        
        fm_env_frame = tk.LabelFrame(fm_split, text=" FM SWELL ADSR ", bg=self.bg_color, fg=self.fg_color, font=self.font, highlightthickness=2, highlightbackground=self.accent_purple, labelanchor='n')
        fm_env_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5,0))
        
        self.fm_env_amt_var = tk.DoubleVar(value=5.0)
        self.create_control_row(fm_env_frame, "ENV AMT", self.fm_env_amt_var, -20.0, 20.0, self.update_fm_env, 0.1, length=120)
        
        self.fm_env_atk_var = tk.DoubleVar(value=0.1)
        self.create_control_row(fm_env_frame, "ATTACK", self.fm_env_atk_var, 0.01, 3.0, self.update_fm_env, 0.01, length=120)
        
        self.fm_env_dec_var = tk.DoubleVar(value=0.5)
        self.create_control_row(fm_env_frame, "DECAY", self.fm_env_dec_var, 0.01, 3.0, self.update_fm_env, 0.01, length=120)
        
        self.fm_env_sus_var = tk.DoubleVar(value=0.0)
        self.create_control_row(fm_env_frame, "SUSTAIN", self.fm_env_sus_var, 0.0, 1.0, self.update_fm_env, 0.01, length=120)
        
        self.fm_env_rel_var = tk.DoubleVar(value=0.2)
        self.create_control_row(fm_env_frame, "RELEASE", self.fm_env_rel_var, 0.01, 3.0, self.update_fm_env, 0.01, length=120)

        osc3_frame = tk.LabelFrame(
            fm_split, text=" OSC 3 ",
            bg=self.bg_color, fg=self.fg_color, font=self.font,
            highlightthickness=2, highlightbackground=self.accent_purple,
            labelanchor='n'
        )
        osc3_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        # ON/OFF toggle
        osc3_top = tk.Frame(osc3_frame, bg=self.bg_color)
        osc3_top.pack(fill=tk.X, padx=10, pady=2)
        tk.Label(osc3_top, text="OSC 3 STATE:", bg=self.bg_color,
                 fg=self.fg_color, font=self.font).pack(side=tk.LEFT, padx=5)
        self.osc3_on_var = tk.IntVar(value=1)
        tk.Radiobutton(osc3_top, text=" ON ", variable=self.osc3_on_var,
                       value=1, command=self.update_osc3, indicatoron=0,
                       bg=self.accent_purple, fg=self.fg_color,
                       selectcolor=self.bg_color, font=self.font).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(osc3_top, text=" OFF ", variable=self.osc3_on_var,
                       value=0, command=self.update_osc3, indicatoron=0,
                       bg=self.accent_purple, fg=self.fg_color,
                       selectcolor=self.bg_color, font=self.font).pack(side=tk.LEFT, padx=5)

        # RATIO knob — covers sub (0.5), unison (1.0), fifth (1.498), octave (2.0)
        self.osc3_ratio_var = tk.DoubleVar(value=1.0)
        self.create_control_row(osc3_frame, "RATIO", self.osc3_ratio_var,
                                0.25, 4.0, self.update_osc3,
                                resolution=0.001, length=120)

        # BLEND knob
        self.osc3_blend_var = tk.DoubleVar(value=0.0)
        self.create_control_row(osc3_frame, "BLEND", self.osc3_blend_var,
                                0.0, 1.0, self.update_osc3,
                                resolution=0.01, length=120)


        # --- SIDE-BY-SIDE SPLIT ROW (Delay & Arpeggiator) ---
        mid_row_split = tk.Frame(main_frame, bg=self.bg_color)
        mid_row_split.pack(fill=tk.X, pady=5)

        # --- EFFECTS (Delay, Chorus, Reverb) ---
        fx_frame = tk.LabelFrame(mid_row_split, text=" EFFECTS ", bg=self.bg_color, fg=self.fg_color, font=self.font, highlightthickness=2, highlightbackground=self.accent_purple, labelanchor='n')
        fx_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))
        
        fx_top = tk.Frame(fx_frame, bg=self.bg_color)
        fx_top.pack(fill=tk.X, padx=10, pady=2)
        
        tk.Label(fx_top, text="DELAY:", bg=self.bg_color, fg=self.fg_color, font=self.font).pack(side=tk.LEFT, padx=5)
        self.delay_on_var = tk.IntVar(value=1)
        tk.Radiobutton(fx_top, text=" ON ", variable=self.delay_on_var, value=1, command=self.update_fx, indicatoron=0, bg=self.accent_purple, fg=self.fg_color, selectcolor=self.bg_color, font=self.font).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(fx_top, text=" OFF ", variable=self.delay_on_var, value=0, command=self.update_fx, indicatoron=0, bg=self.accent_purple, fg=self.fg_color, selectcolor=self.bg_color, font=self.font).pack(side=tk.LEFT, padx=5)
        
        self.delay_time_var = tk.DoubleVar(value=0.3)
        self.create_control_row(fx_frame, "TIME", self.delay_time_var, 0.01, 2.0, self.update_fx, 0.01, length=150)
        
        self.delay_feed_var = tk.DoubleVar(value=0.3)
        self.create_control_row(fx_frame, "FEED", self.delay_feed_var, 0.0, 0.95, self.update_fx, 0.01, length=150)
        
        self.delay_mix_var = tk.DoubleVar(value=0.2)
        self.create_control_row(fx_frame, "D-MIX", self.delay_mix_var, 0.0, 1.0, self.update_fx, 0.01, length=150)

        # Chorus Controls
        tk.Frame(fx_frame, height=2, bg=self.accent_purple).pack(fill=tk.X, pady=5)
        
        chorus_top = tk.Frame(fx_frame, bg=self.bg_color)
        chorus_top.pack(fill=tk.X, padx=10, pady=2)
        tk.Label(chorus_top, text="CHORUS:", bg=self.bg_color, fg=self.fg_color, font=self.font).pack(side=tk.LEFT, padx=5)
        self.chorus_on_var = tk.IntVar(value=0)
        tk.Radiobutton(chorus_top, text=" ON ", variable=self.chorus_on_var, value=1, command=self.update_fx, indicatoron=0, bg=self.accent_purple, fg=self.fg_color, selectcolor=self.bg_color, font=self.font).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(chorus_top, text=" OFF ", variable=self.chorus_on_var, value=0, command=self.update_fx, indicatoron=0, bg=self.accent_purple, fg=self.fg_color, selectcolor=self.bg_color, font=self.font).pack(side=tk.LEFT, padx=5)
        
        self.chorus_rate_var = tk.DoubleVar(value=1.0)
        self.create_control_row(fx_frame, "RATE", self.chorus_rate_var, 0.1, 10.0, self.update_fx, 0.1, length=150)
        
        self.chorus_depth_var = tk.DoubleVar(value=0.25)
        self.create_control_row(fx_frame, "DEPTH", self.chorus_depth_var, 0.0, 1.0, self.update_fx, 0.01, length=150)
        
        self.chorus_mix_var = tk.DoubleVar(value=0.0)
        self.create_control_row(fx_frame, "C-MIX", self.chorus_mix_var, 0.0, 1.0, self.update_fx, 0.01, length=150)

        # Reverb Control
        tk.Frame(fx_frame, height=2, bg=self.accent_purple).pack(fill=tk.X, pady=5)
        self.reverb_wet_var = tk.DoubleVar(value=0.0)
        self.create_control_row(fx_frame, "REVERB", self.reverb_wet_var, 0.0, 1.0, self.update_fx, 0.01, length=150)

        # --- ARPEGGIATOR ---
        arp_frame = tk.LabelFrame(mid_row_split, text=" ARPEGGIATOR MATRIX ", bg=self.bg_color, fg=self.fg_color, font=self.font, highlightthickness=2, highlightbackground=self.accent_purple, labelanchor='n')
        arp_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5,0))
        
        arp_1 = tk.Frame(arp_frame, bg=self.bg_color)
        arp_1.pack(fill=tk.X, padx=10, pady=5)
        
        self.arp_on_var = tk.IntVar(value=0)
        tk.Checkbutton(arp_1, text="ARP ON", variable=self.arp_on_var, command=self.update_arp, bg=self.bg_color, fg="#FF0000", font=self.font, selectcolor="#000000").pack(side=tk.LEFT, padx=5)
        
        tk.Label(arp_1, text="BPM:", bg=self.bg_color, fg=self.fg_color, font=self.font).pack(side=tk.LEFT, padx=(10, 2))
        self.arp_bpm_var = tk.DoubleVar(value=120.0)
        tk.Scale(arp_1, variable=self.arp_bpm_var, from_=40, to=280, orient=tk.HORIZONTAL, bg=self.bg_color, fg=self.fg_color, command=lambda _: self.update_arp(), length=120, showvalue=False).pack(side=tk.LEFT)
        tk.Entry(arp_1, textvariable=self.arp_bpm_var, width=5, bg=self.bg_color, fg=self.fg_color, font=self.font).pack(side=tk.LEFT)
        
        tk.Label(arp_1, text="  RATE:", bg=self.bg_color, fg=self.fg_color, font=self.font).pack(side=tk.LEFT, padx=(10,0))
        self.arp_rate_var = tk.DoubleVar(value=0.25)
        rates = [("1/4", 1.0), ("1/8", 0.5), ("1/16", 0.25)]
        for text, val in rates:
            tk.Radiobutton(arp_1, text=text, variable=self.arp_rate_var, value=val, command=self.update_arp, indicatoron=0, bg=self.accent_purple, fg=self.fg_color, selectcolor=self.bg_color, width=4).pack(side=tk.LEFT, padx=2)

        arp_2 = tk.Frame(arp_frame, bg=self.bg_color)
        arp_2.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(arp_2, text="SCALE:", bg=self.bg_color, fg=self.fg_color, font=self.font).pack(side=tk.LEFT)
        self.arp_scale_var = tk.StringVar(value="Major")
        opt = tk.OptionMenu(arp_2, self.arp_scale_var, *SCALES.keys(), command=lambda _: self.update_arp())
        opt.config(bg="#000055", fg=self.fg_color, font=self.font, highlightthickness=0)
        opt["menu"].config(bg="#0000aa", fg=self.fg_color, font=self.font)
        opt.pack(side=tk.LEFT, padx=5)

        tk.Label(arp_2, text=" OCT:", bg=self.bg_color, fg=self.fg_color, font=self.font).pack(side=tk.LEFT)
        self.arp_oct_var = tk.IntVar(value=1)
        for val in [1, 2, 3]:
            tk.Radiobutton(arp_2, text=str(val), variable=self.arp_oct_var, value=val, command=self.update_arp, indicatoron=0, bg=self.accent_purple, fg=self.fg_color, selectcolor=self.bg_color, width=2).pack(side=tk.LEFT, padx=1)

        tk.Label(arp_2, text=" LEN:", bg=self.bg_color, fg=self.fg_color, font=self.font).pack(side=tk.LEFT, padx=(5,0))
        self.arp_len_var = tk.IntVar(value=4)
        for val in [1, 2, 3, 4, 5, 6]:
            tk.Radiobutton(arp_2, text=str(val), variable=self.arp_len_var, value=val, command=self.update_arp, indicatoron=0, bg=self.accent_purple, fg=self.fg_color, selectcolor=self.bg_color, width=2).pack(side=tk.LEFT, padx=1)

        self.arp_rand_var = tk.IntVar(value=0)
        tk.Checkbutton(arp_2, text="RND", variable=self.arp_rand_var, command=self.update_arp, indicatoron=0, bg=self.accent_purple, fg=self.fg_color, selectcolor=self.bg_color, width=4).pack(side=tk.LEFT, padx=10)


        
        # --- OSCILLOSCOPE ---
        scope_frame = tk.LabelFrame(main_frame, text=" SIGNAL VIZ ", bg=self.bg_color, fg=self.fg_color, font=self.font)
        scope_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.canvas = tk.Canvas(scope_frame, bg="#0e142d", highlightthickness=2, highlightbackground=self.accent_purple)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        footer = tk.Label(self.master, text="PLAY KEYS ONSCREEN: A S D F G H J K", bg=self.bg_color, fg=self.accent_purple, font=("PxPlus IBM VGA8", 10))
        footer.pack(pady=2)
        
        # Initialize internal state sync
        self.update_params()
        self.update_vca()
        self.update_env()
        self.update_fm()
        self.update_fm_env()
        self.update_fx()
        self.update_arp()
        self.update_osc3()

    def show_preset_menu(self):
        """Open a popup menu of factory presets when the bull icon is clicked."""
        menu = tk.Menu(self.master, tearoff=0, bg="#0e142d", fg=self.fg_color,
            activebackground=self.accent_purple, activeforeground=self.fg_color,
            font=self.font, bd=2, relief=tk.RAISED)
        has_vintage = False
        for name in PRESETS:
            # Add visual separator for the vintage bank
            if not has_vintage and name in ["Eagle FX", "Eagle Space Arp", "Lucky Man Lead", "Lucky Man Sweep", "Tarkus Lead"]:
                menu.add_separator()
                menu.add_command(label="      ── VINTAGE ──", state=tk.DISABLED)
                has_vintage = True
            
            menu.add_command(label=f"  {name}", command=lambda n=name: self.apply_preset(n))
        # Position near the bull icon
        try:
            menu.tk_popup(self.master.winfo_rootx() + 20, self.master.winfo_rooty() + 80)
        finally:
            menu.grab_release()

    def apply_preset(self, name):
        """Load a factory preset by name — sets all UI variables and syncs to engine."""
        p = PRESETS.get(name)
        if not p:
            return

        # Moog Ladder
        self.cutoff_var.set(p["cutoff"])
        self.res_var.set(p["resonance"])
        self.drive_var.set(p["drive"])

        # VCA (Loudness Contour)
        self.vca_atk_var.set(p.get("vca_atk", 0.01))
        self.vca_dec_var.set(p.get("vca_dec", 0.3))
        self.vca_sus_var.set(p.get("vca_sus", 1.0))
        self.vca_rel_var.set(p.get("vca_rel", 0.1))

        # Filter ADSR
        self.env_amt_var.set(p["env_amt"])
        self.env_atk_var.set(p["env_atk"])
        self.env_dec_var.set(p["env_dec"])
        self.env_sus_var.set(p["env_sus"])
        self.env_rel_var.set(p["env_rel"])

        # FM Engine
        self.fm_on_var.set(p["fm_on"])
        self.fm_blend_var.set(p["fm_blend"])
        self.fm_idx_var.set(p["fm_idx"])
        self.fm_ratio_var.set(p["fm_ratio"])

        # Oscillator 3
        self.osc3_on_var.set(p.get("osc3_on", 1))
        self.osc3_ratio_var.set(p.get("osc3_ratio", 1.0))
        self.osc3_blend_var.set(p.get("osc3_blend", 0.0))

        # FM ADSR
        self.fm_env_amt_var.set(p["fm_env_amt"])
        self.fm_env_atk_var.set(p["fm_env_atk"])
        self.fm_env_dec_var.set(p["fm_env_dec"])
        self.fm_env_sus_var.set(p["fm_env_sus"])
        self.fm_env_rel_var.set(p["fm_env_rel"])

        # Delay
        self.delay_on_var.set(p.get("d_on", 0))
        self.delay_time_var.set(p.get("d_time", 0.3))
        self.delay_feed_var.set(p.get("d_feed", 0.3))
        self.delay_mix_var.set(p.get("d_mix", 0.0))

        # Chorus
        self.chorus_on_var.set(p.get("c_on", 0))
        self.chorus_rate_var.set(p.get("c_rate", 1.0))
        self.chorus_depth_var.set(p.get("c_depth", 0.25))
        self.chorus_mix_var.set(p.get("c_mix", 0.0))
        
        # Reverb
        self.reverb_wet_var.set(p.get("reverb_wet", 0.0))

        # Arpeggiator
        self.arp_on_var.set(p["a_on"])
        self.arp_bpm_var.set(p["a_bpm"])
        self.arp_rate_var.set(p["a_rate"])
        self.arp_scale_var.set(p["a_scale"])
        self.arp_oct_var.set(p["a_oct"])
        self.arp_len_var.set(p["a_len"])
        self.arp_rand_var.set(p["a_rnd"])

        # Sync all to audio engine
        self.update_params()
        self.update_vca()
        self.update_env()
        self.update_fm()
        self.update_fm_env()
        self.update_fx()
        self.update_arp()
        self.update_osc3()

        # Update tethered state
        self._tethered_preset_name = name

    def show_user_preset_menu(self):
        """Open a popup menu for user presets (save/load/delete)."""
        menu = tk.Menu(self.master, tearoff=0, bg="#0e142d", fg=self.fg_color,
            activebackground=self.accent_purple, activeforeground=self.fg_color,
            font=self.font, bd=2, relief=tk.RAISED)

        # Save New
        menu.add_command(label="\u2795  Save New Preset...", command=self.save_user_preset)
        menu.add_separator()

        # List existing user presets
        user_presets = self._list_user_presets()
        if user_presets:
            for name in user_presets:
                sub = tk.Menu(menu, tearoff=0, bg="#0e142d", fg=self.fg_color,
                    activebackground=self.accent_purple, activeforeground=self.fg_color,
                    font=self.font)
                sub.add_command(label="Load", command=lambda n=name: self.load_user_preset(n))
                sub.add_command(label="Overwrite", command=lambda n=name: self.save_user_preset(overwrite=n))
                sub.add_command(label="Delete", command=lambda n=name: self.delete_user_preset(n))
                menu.add_cascade(label=f"\u25B6  {name}", menu=sub)
        else:
            menu.add_command(label="(no saved presets)", state=tk.DISABLED)

        try:
            menu.tk_popup(self.master.winfo_rootx() + self.master.winfo_width() - 200,
                          self.master.winfo_rooty() + 80)
        finally:
            menu.grab_release()

    def _list_user_presets(self):
        """Return sorted list of user preset names."""
        os.makedirs(PRESETS_DIR, exist_ok=True)
        presets = []
        for f in sorted(os.listdir(PRESETS_DIR)):
            if f.endswith(".json"):
                presets.append(f[:-5])
        return presets

    def _get_current_state(self):
        """Snapshot all current parameter values into a dict."""
        return {
            "cutoff": self.cutoff_var.get(),
            "resonance": self.res_var.get(),
            "drive": self.drive_var.get(),
            "vca_atk": self.vca_atk_var.get(),
            "vca_dec": self.vca_dec_var.get(),
            "vca_sus": self.vca_sus_var.get(),
            "vca_rel": self.vca_rel_var.get(),
            "env_amt": self.env_amt_var.get(),
            "env_atk": self.env_atk_var.get(),
            "env_dec": self.env_dec_var.get(),
            "env_sus": self.env_sus_var.get(),
            "env_rel": self.env_rel_var.get(),
            "fm_on": self.fm_on_var.get(),
            "fm_blend": self.fm_blend_var.get(),
            "fm_idx": self.fm_idx_var.get(),
            "fm_ratio": self.fm_ratio_var.get(),
            "osc3_on": self.osc3_on_var.get(),
            "osc3_ratio": self.osc3_ratio_var.get(),
            "osc3_blend": self.osc3_blend_var.get(),
            "fm_env_amt": self.fm_env_amt_var.get(),
            "fm_env_atk": self.fm_env_atk_var.get(),
            "fm_env_dec": self.fm_env_dec_var.get(),
            "fm_env_sus": self.fm_env_sus_var.get(),
            "fm_env_rel": self.fm_env_rel_var.get(),
            "d_on": self.delay_on_var.get(),
            "d_time": self.delay_time_var.get(),
            "d_feed": self.delay_feed_var.get(),
            "d_mix": self.delay_mix_var.get(),
            "c_on": self.chorus_on_var.get(),
            "c_rate": self.chorus_rate_var.get(),
            "c_depth": self.chorus_depth_var.get(),
            "c_mix": self.chorus_mix_var.get(),
            "reverb_wet": self.reverb_wet_var.get(),
            "a_on": self.arp_on_var.get(),
            "a_bpm": self.arp_bpm_var.get(),
            "a_rate": self.arp_rate_var.get(),
            "a_scale": self.arp_scale_var.get(),
            "a_oct": self.arp_oct_var.get(),
            "a_len": self.arp_len_var.get(),
            "a_rnd": self.arp_rand_var.get(),
        }

    def save_user_preset(self, overwrite=None):
        """Save current settings as a named user preset."""
        if overwrite:
            name = overwrite
        else:
            name = simpledialog.askstring(
                "Save Preset", "Enter a name for this preset:",
                parent=self.master
            )
            if not name or not name.strip():
                return
            name = name.strip()

        filepath = os.path.join(PRESETS_DIR, f"{name}.json")
        data = self._get_current_state()
        try:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
            messagebox.showinfo("Saved", f"Preset '{name}' saved.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save preset: {e}")

    def load_user_preset(self, name):
        """Load a user preset by name."""
        filepath = os.path.join(PRESETS_DIR, f"{name}.json")
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            self.apply_preset_data(data)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load preset: {e}")

    def delete_user_preset(self, name):
        """Delete a user preset."""
        if messagebox.askyesno("Delete Preset", f"Delete preset '{name}'?"):
            filepath = os.path.join(PRESETS_DIR, f"{name}.json")
            try:
                os.remove(filepath)
                messagebox.showinfo("Deleted", f"Preset '{name}' removed.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete: {e}")

    def apply_preset_data(self, p):
        """Apply a preset dict to all UI variables and sync to engine."""
        self.cutoff_var.set(p.get("cutoff", 1000.0))
        self.res_var.set(p.get("resonance", 0.0))
        self.drive_var.set(p.get("drive", 1.0))

        self.vca_atk_var.set(p.get("vca_atk", 0.01))
        self.vca_dec_var.set(p.get("vca_dec", 0.3))
        self.vca_sus_var.set(p.get("vca_sus", 1.0))
        self.vca_rel_var.set(p.get("vca_rel", 0.1))

        self.env_amt_var.set(p.get("env_amt", 5000.0))
        self.env_atk_var.set(p.get("env_atk", 0.05))
        self.env_dec_var.set(p.get("env_dec", 0.3))
        self.env_sus_var.set(p.get("env_sus", 0.5))
        self.env_rel_var.set(p.get("env_rel", 0.2))
        self.fm_on_var.set(p.get("fm_on", 1))
        self.fm_blend_var.set(p.get("fm_blend", 0.0))
        self.fm_idx_var.set(p.get("fm_idx", 0.0))
        self.fm_ratio_var.set(p.get("fm_ratio", 1.0))
        self.osc3_on_var.set(p.get("osc3_on", 1))
        self.osc3_ratio_var.set(p.get("osc3_ratio", 1.0))
        self.osc3_blend_var.set(p.get("osc3_blend", 0.0))
        self.fm_env_amt_var.set(p.get("fm_env_amt", 5.0))
        self.fm_env_atk_var.set(p.get("fm_env_atk", 0.1))
        self.fm_env_dec_var.set(p.get("fm_env_dec", 0.5))
        self.fm_env_sus_var.set(p.get("fm_env_sus", 0.0))
        self.fm_env_rel_var.set(p.get("fm_env_rel", 0.2))
        self.delay_on_var.set(p.get("d_on", 1))
        self.delay_time_var.set(p.get("d_time", 0.3))
        self.delay_feed_var.set(p.get("d_feed", 0.3))
        self.delay_mix_var.set(p.get("d_mix", 0.2))

        self.chorus_on_var.set(p.get("c_on", 0))
        self.chorus_rate_var.set(p.get("c_rate", 1.0))
        self.chorus_depth_var.set(p.get("c_depth", 0.25))
        self.chorus_mix_var.set(p.get("c_mix", 0.0))
        self.reverb_wet_var.set(p.get("reverb_wet", 0.0))

        self.arp_on_var.set(p.get("a_on", 0))
        self.arp_bpm_var.set(p.get("a_bpm", 120.0))
        self.arp_rate_var.set(p.get("a_rate", 0.25))
        self.arp_scale_var.set(p.get("a_scale", "Major"))
        self.arp_oct_var.set(p.get("a_oct", 1))
        self.arp_len_var.set(p.get("a_len", 4))
        self.arp_rand_var.set(p.get("a_rnd", 0))
        # Sync all to audio engine
        self.update_params()
        self.update_vca()
        self.update_env()
        self.update_fm()
        self.update_fm_env()
        self.update_fx()
        self.update_arp()
        self.update_osc3()

    def create_control_row(self, parent, label_text, var, from_val, to_val, command, resolution=1.0, length=300):
        row = tk.Frame(parent, bg=self.bg_color)
        row.pack(fill=tk.X, padx=10, pady=5)
        
        lbl = tk.Label(row, text=label_text, bg=self.bg_color, fg=self.fg_color, font=self.font, width=7, anchor='w')
        lbl.pack(side=tk.LEFT)
        
        # Custom Canvas Slider with Rich Palette Accents
        slider = CanvasSlider(row, variable=var, from_val=from_val, to_val=to_val, command=lambda: command(), resolution=resolution, length=length, width=40, bg_color=self.bg_color, fg_color=self.fg_color, fill_color=self.accent_purple, trough_color="#0e142d")
        slider.pack(side=tk.LEFT, padx=5)
        
        vcmd = (self.master.register(self.validate_float), '%P')
        entry = tk.Entry(row, textvariable=var, validate='key', validatecommand=vcmd, bg=self.bg_color, fg=self.fg_color, font=self.font, width=6, insertbackground=self.fg_color)
        entry.pack(side=tk.LEFT)
        entry.bind("<Return>", lambda e: command())
        entry.bind("<FocusOut>", lambda e: command())
        
    def validate_float(self, new_value):
        if not new_value:
            return True
        try:
            float(new_value)
            return True
        except ValueError:
            return False
            
    def update_vca(self):
        with self.audio_engine.lock:
            self.audio_engine.vca_atk = self.vca_atk_var.get()
            self.audio_engine.vca_dec = self.vca_dec_var.get()
            self.audio_engine.vca_sus = self.vca_sus_var.get()
            self.audio_engine.vca_rel = self.vca_rel_var.get()
            
    def update_env(self):
        with self.audio_engine.lock:
            self.audio_engine.env_amt = self.env_amt_var.get()
            self.audio_engine.env_atk = self.env_atk_var.get()
            self.audio_engine.env_dec = self.env_dec_var.get()
            self.audio_engine.env_sus = self.env_sus_var.get()
            self.audio_engine.env_rel = self.env_rel_var.get()
            
    def update_fm(self):
        with self.audio_engine.lock:
            self.audio_engine.fm_on = bool(self.fm_on_var.get())
            self.audio_engine.fm_blend = self.fm_blend_var.get()
            self.audio_engine.fm_index = self.fm_idx_var.get()
            self.audio_engine.fm_ratio = self.fm_ratio_var.get()
            
    def update_osc3(self):
        with self.audio_engine.lock:
            self.audio_engine.osc3_on    = bool(self.osc3_on_var.get())
            self.audio_engine.osc3_ratio = self.osc3_ratio_var.get()
            self.audio_engine.osc3_blend = self.osc3_blend_var.get()
            
    def update_fm_env(self):
        with self.audio_engine.lock:
            self.audio_engine.fm_env_amt = self.fm_env_amt_var.get()
            self.audio_engine.fm_env_atk = self.fm_env_atk_var.get()
            self.audio_engine.fm_env_dec = self.fm_env_dec_var.get()
            self.audio_engine.fm_env_sus = self.fm_env_sus_var.get()
            self.audio_engine.fm_env_rel = self.fm_env_rel_var.get()
            
    def update_params(self):
        with self.audio_engine.lock:
            self.audio_engine.cutoff = self.cutoff_var.get()
            self.audio_engine.resonance = self.res_var.get()
            self.audio_engine.drive = self.drive_var.get()
        
    def update_fx(self):
        with self.audio_engine.lock:
            self.audio_engine.delay_on = bool(self.delay_on_var.get())
            self.audio_engine.delay_time = self.delay_time_var.get()
            self.audio_engine.delay_feedback = self.delay_feed_var.get()
            self.audio_engine.delay_mix = self.delay_mix_var.get()
            
            self.audio_engine.chorus_on = bool(self.chorus_on_var.get())
            self.audio_engine.chorus_rate = self.chorus_rate_var.get()
            self.audio_engine.chorus_depth = self.chorus_depth_var.get()
            self.audio_engine.chorus_mix = self.chorus_mix_var.get()
            
            self.audio_engine.reverb_wet = self.reverb_wet_var.get()
        
    def update_arp(self):
        with self.audio_engine.lock:
            self.audio_engine.arp_on = bool(self.arp_on_var.get())
            self.audio_engine.arp_bpm = self.arp_bpm_var.get()
            self.audio_engine.arp_duration_beats = self.arp_rate_var.get()
            self.audio_engine.arp_scale_name = self.arp_scale_var.get()
            self.audio_engine.arp_octaves = self.arp_oct_var.get()
            self.audio_engine.arp_length = self.arp_len_var.get()
            self.audio_engine.arp_random = bool(self.arp_rand_var.get())
        self.audio_engine.update_arp_pool()
        
    def bind_events(self):
        self.master.bind("<KeyPress>", self.on_key_press)
        self.master.bind("<KeyRelease>", self.on_key_release)
        
    def on_key_press(self, event):
        key = event.keysym.lower()
        if key in KEY_FREQS:
            if self.active_key != key:
                self.active_key = key
                self.audio_engine.set_note(KEY_FREQS[key])
                
    def on_key_release(self, event):
        key = event.keysym.lower()
        if key in KEY_FREQS:
            self.audio_engine.release_note(KEY_FREQS[key])
            if key == self.active_key:
                self.active_key = None
            
    def update_scope(self, buffer):
        self.scope_buffer = buffer
        
    def render_scope_loop(self):
        self.canvas.delete("wave")
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        
        if width > 1 and height > 1 and len(self.scope_buffer) > 0:
            mid_y = height / 2
            scale_y = height / 2.5
            
            step = max(1, len(self.scope_buffer) // 100) 
            dx = width / 100.0
            points = []
            
            x = 0
            for i in range(0, len(self.scope_buffer), step):
                if x >= width:
                    break
                y = mid_y - (self.scope_buffer[i] * scale_y)
                points.extend([x, y])
                x += dx
                
            if len(points) >= 4:
                self.canvas.create_line(points, fill=self.accent_red, width=3, tags="wave")
                
        self.master.after(60, self.render_scope_loop)
        
    def save_settings(self):
        data = {
            "fm_on": self.fm_on_var.get(),
            "fm_blend": self.fm_blend_var.get(),
            "fm_idx": self.fm_idx_var.get(),
            "fm_ratio": self.fm_ratio_var.get(),
            "osc3_on": self.osc3_on_var.get(),
            "osc3_ratio": self.osc3_ratio_var.get(),
            "osc3_blend": self.osc3_blend_var.get(),
            "fm_env_amt": self.fm_env_amt_var.get(),
            "fm_env_atk": self.fm_env_atk_var.get(),
            "fm_env_dec": self.fm_env_dec_var.get(),
            "fm_env_sus": self.fm_env_sus_var.get(),
            "fm_env_rel": self.fm_env_rel_var.get(),
            "cutoff": self.cutoff_var.get(),
            "resonance": self.res_var.get(),
            "drive": self.drive_var.get(),
            "env_amt": self.env_amt_var.get(),
            "env_atk": self.env_atk_var.get(),
            "env_dec": self.env_dec_var.get(),
            "env_sus": self.env_sus_var.get(),
            "env_rel": self.env_rel_var.get(),
            "d_on": self.delay_on_var.get(),
            "d_time": self.delay_time_var.get(),
            "d_feed": self.delay_feed_var.get(),
            "d_mix": self.delay_mix_var.get(),
            "a_on": self.arp_on_var.get(),
            "a_bpm": self.arp_bpm_var.get(),
            "a_rate": self.arp_rate_var.get(),
            "a_scale": self.arp_scale_var.get(),
            "a_oct": self.arp_oct_var.get(),
            "a_len": self.arp_len_var.get(),
            "a_rnd": self.arp_rand_var.get()
        }
        try:
            with open(self.settings_file, "w") as f:
                json.dump(data, f)
            messagebox.showinfo("Saved", "Settings saved securely!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")
            
    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r") as f:
                    data = json.load(f)
                    
                self.fm_on_var.set(data.get("fm_on", 1))
                self.fm_blend_var.set(data.get("fm_blend", 0.0))
                self.fm_idx_var.set(data.get("fm_idx", 0.0))
                self.fm_ratio_var.set(data.get("fm_ratio", 1.0))
                
                self.osc3_on_var.set(data.get("osc3_on", 1))
                self.osc3_ratio_var.set(data.get("osc3_ratio", 1.0))
                self.osc3_blend_var.set(data.get("osc3_blend", 0.0))
                
                self.fm_env_amt_var.set(data.get("fm_env_amt", 5.0))
                self.fm_env_atk_var.set(data.get("fm_env_atk", 0.1))
                self.fm_env_dec_var.set(data.get("fm_env_dec", 0.5))
                self.fm_env_sus_var.set(data.get("fm_env_sus", 0.0))
                self.fm_env_rel_var.set(data.get("fm_env_rel", 0.2))
                
                self.cutoff_var.set(data.get("cutoff", 1000.0))
                self.res_var.set(data.get("resonance", 0.0))
                self.drive_var.set(data.get("drive", 1.0))
                
                self.env_amt_var.set(data.get("env_amt", 5000.0))
                self.env_atk_var.set(data.get("env_atk", 0.05))
                self.env_dec_var.set(data.get("env_dec", 0.3))
                self.env_sus_var.set(data.get("env_sus", 0.5))
                self.env_rel_var.set(data.get("env_rel", 0.2))
                
                self.delay_on_var.set(data.get("d_on", 1))
                self.delay_time_var.set(data.get("d_time", 0.3))
                self.delay_feed_var.set(data.get("d_feed", 0.3))
                self.delay_mix_var.set(data.get("d_mix", 0.2))
                
                self.arp_on_var.set(data.get("a_on", 0))
                self.arp_bpm_var.set(data.get("a_bpm", 120.0))
                self.arp_rate_var.set(data.get("a_rate", 0.25))
                self.arp_scale_var.set(data.get("a_scale", "Major"))
                self.arp_oct_var.set(data.get("a_oct", 1))
                self.arp_len_var.set(data.get("a_len", 4))
                self.arp_rand_var.set(data.get("a_rnd", 0))
                
                self.update_env()
                self.update_fm()
                self.update_fm_env()
                self.update_params()
                self.update_fx()
                self.update_arp()
                self.update_osc3()
                messagebox.showinfo("Loaded", "Settings loaded into matrix!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load: {e}")
        else:
            messagebox.showwarning("No Preset", "No settings found locally.")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--tethered', action='store_true', help='Run in tethered DAW mode')
    parser.add_argument('--track', type=int, default=0, help='DAW track index (0-based)')
    args = parser.parse_args()

    root = tk.Tk()

    audio_engine = AudioEngine()
    try:
        audio_engine.start()
    except Exception as e:
        print(f"Failed to start audio stream: {e}")

    udp_port = 12160 + args.track if args.tethered else 12160
    app = SynthGUI(root, audio_engine, udp_port=udp_port)
    app._tethered_preset_name = "(init)"

    # Tethered mode UI banner + state file writer
    if args.tethered:
        state_file = f"/tmp/station_track_{args.track}_state.json"
        track_num = args.track + 1

        # Amber banner across the top of the window
        tether_bar = tk.Frame(root, bg="#b87800", height=22)
        tether_bar.pack(side=tk.TOP, fill=tk.X, before=root.winfo_children()[0])
        tk.Label(tether_bar, text=f"⬡  TETHERED  →  STATION MASTER  TRK {track_num}",
                 bg="#b87800", fg="#000000", font=("PxPlus IBM VGA8", 11, "bold")).pack(side=tk.LEFT, padx=10)
        root.title(f"GOLDEN BULL  [TRK {track_num}]")

        def _write_state():
            try:
                waveform = audio_engine.last_out_frame.tolist()
                state = {"preset": app._tethered_preset_name, "waveform": waveform}
                with open(state_file, 'w') as f:
                    json.dump(state, f)
            except Exception:
                pass
            root.after(100, _write_state)

        root.after(100, _write_state)

    def on_closing():
        audio_engine.stop()
        root.destroy()
        os._exit(0)

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.focus_set()
    root.mainloop()

if __name__ == "__main__":
    main()
