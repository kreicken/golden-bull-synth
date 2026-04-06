import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
import sounddevice as sd
import json
import os
import random
import math
import threading
from PIL import Image, ImageTk

SAMPLE_RATE = 44100
BLOCK_SIZE = 2048

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

SCALES = {
    "Major": [0, 2, 4, 5, 7, 9, 11],
    "Minor": [0, 2, 3, 5, 7, 8, 10],
    "Dorian": [0, 2, 3, 5, 7, 9, 10],
    "Phrygian": [0, 1, 3, 5, 7, 8, 10],
    "Lydian": [0, 2, 4, 6, 7, 9, 11],
    "Mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "Pentatonic Major": [0, 2, 4, 7, 9],
    "Pentatonic Minor": [0, 3, 5, 7, 10],
    "Blues": [0, 3, 4, 5, 7, 10],
    "Chromatic": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
}

def freq_to_midi(f):
    return 69 + 12 * np.log2(f / 440.0)

def midi_to_freq(m):
    return 440.0 * 2.0**((m - 69) / 12.0)

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
        
        # FM Audio Control Params
        self.fm_on = True
        self.fm_blend = 0.0
        self.fm_index = 0.0
        self.fm_ratio = 1.0
        
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
        
        self.arp_on = False
        self.arp_scale_name = "Major"
        self.arp_octaves = 1
        self.arp_length = 4 
        self.arp_random = False
        self.arp_duration_beats = 0.25 
        self.arp_bpm = 120.0
        self.arp_pool = []
        
        # Internal DSP States
        self.is_playing = False
        self.base_midi = 60
        self.current_freq = 440.0
        
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
        self._sp_env_amt = 5000.0
        self._sp_env_atk = 0.05
        self._sp_env_dec = 0.3
        self._sp_env_sus = 0.5
        self._sp_env_rel = 0.2
        
        self._sp_fm_on = True
        self._sp_fm_blend = 0.0
        self._sp_fm_idx = 0.0
        self._sp_fm_ratio = 1.0
        self._sp_fm_env_amt = 5.0
        self._sp_fm_env_atk = 0.1
        self._sp_fm_env_dec = 0.5
        self._sp_fm_env_sus = 0.0
        self._sp_fm_env_rel = 0.2
        
        self._sp_d_on = True
        self._sp_d_time = 0.3
        self._sp_d_feed = 0.3
        self._sp_d_mix = 0.2
        
        self._sp_arp_on = False
        self._sp_arp_rnd = False
        self._sp_arp_bpm = 120.0
        self._sp_arp_dur = 0.25
        self._sp_arp_pool = []
        
        self.scope_callback = None
        
        self.stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            channels=1,
            callback=self.audio_callback,
            latency='high'
        )
        
    def start(self):
        self.stream.start()
        
    def stop(self):
        self.stream.stop()
        
    def set_note(self, freq):
        with self.lock:
            self.current_freq = freq
            self.base_midi = round(freq_to_midi(freq))
            self.is_playing = True
            
            self.env_state = 1 # Trigger Filter Attack
            self.fm_env_state = 1 # Trigger FM Attack
            
            if self.arp_on:
                self.arp_sample_counter = 0
                self.arp_step = 0
                self._recalc_arp_pool_internal()
        
    def release_note(self):
        with self.lock:
            self.is_playing = False
            self.env_state = 4 # Release Switch
            self.fm_env_state = 4 
        
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
                self._sp_env_amt = self.env_amt
                self._sp_env_atk = self.env_atk
                self._sp_env_dec = self.env_dec
                self._sp_env_sus = self.env_sus
                self._sp_env_rel = self.env_rel
                
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
                
                self._sp_arp_on = self.arp_on
                self._sp_arp_rnd = self.arp_random
                self._sp_arp_bpm = self.arp_bpm
                self._sp_arp_dur = self.arp_duration_beats
                self._sp_arp_pool = list(self.arp_pool) 
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
                        self.fm_env_state = 1
                    self.arp_sample_counter += 1
            
            freq_array[i] = self.current_freq
            
            # Key Release Overrides
            if not self._sp_playing and self.env_state != 0 and self.env_state != 4:
                self.env_state = 4 
            if not self._sp_playing and self.fm_env_state != 0 and self.fm_env_state != 4:
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

        if self._sp_playing:
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
                
                mixed_src_array = saw_val * (1.0 - self._sp_fm_blend) + fm_val * self._sp_fm_blend
                x_array = mixed_src_array * self._sp_drive
            else:
                x_array = saw_val * self._sp_drive
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
        
        outdata[:, 0] = np.clip(filtered, -1.0, 1.0)
        
        if self.scope_callback:
            self.scope_callback(filtered.copy())


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
        self.create_rectangle(x - hw/2, 0, x + hw/2, self.slider_width, fill=self.fg_color, outline="#000000", width=2)


class SynthGUI:
    def __init__(self, master, audio_engine):
        self.master = master
        self.audio_engine = audio_engine
        self.master.title("GOLDEN BULL HYBRID SYNTHESIZER")
        self.master.geometry("1050x1050") 
        
        self.bg_color = "#0000AA"
        self.fg_color = "#FFD700" 
        self.font = ("PxPlus IBM VGA8", 12)
        self.title_font = ("PxPlus IBM VGA8", 20)
        
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
        
    def setup_ui(self):
        header_frame = tk.Frame(self.master, bg=self.bg_color)
        header_frame.pack(pady=10)
        
        if hasattr(self, 'icon_img') and self.icon_img:
            try:
                scaled_img = self.icon_img.resize((60, 60), Image.LANCZOS)
                self.header_logo = ImageTk.PhotoImage(scaled_img)
                tk.Label(header_frame, image=self.header_logo, bg=self.bg_color).pack(side=tk.LEFT, padx=10)
            except Exception as e:
                print(f"Warning: Could not load header icon: {e}")

        header = tk.Label(header_frame, text="GOLDEN BULL HYBRID SYNTHESIZER", bg=self.bg_color, fg=self.fg_color, font=self.title_font)
        header.pack(side=tk.LEFT, padx=10)
        
        if hasattr(self, 'header_logo'):
            tk.Label(header_frame, image=self.header_logo, bg=self.bg_color).pack(side=tk.LEFT, padx=10)
        
        main_frame = tk.Frame(self.master, bg=self.bg_color)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        # --- SPLIT ROW 1 (Moog & Envelopes) ---
        top_split = tk.Frame(main_frame, bg=self.bg_color)
        top_split.pack(fill=tk.X, pady=5)
        
        controls_frame = tk.LabelFrame(top_split, text=" MOOG LADDER ", bg=self.bg_color, fg=self.fg_color, font=self.font)
        controls_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))
        
        self.cutoff_var = tk.DoubleVar(value=1000.0)
        self.create_control_row(controls_frame, "CUTOFF", self.cutoff_var, 20.0, 20000.0, self.update_params, length=120)
        
        self.res_var = tk.DoubleVar(value=0.0)
        self.create_control_row(controls_frame, "RESON.", self.res_var, 0.0, 1.0, self.update_params, resolution=0.01, length=120)
        
        self.drive_var = tk.DoubleVar(value=1.0)
        self.create_control_row(controls_frame, "DRIVE", self.drive_var, 1.0, 5.0, self.update_params, resolution=0.1, length=120)

        env_frame = tk.LabelFrame(top_split, text=" FILTER ADSR ", bg=self.bg_color, fg=self.fg_color, font=self.font)
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


        # --- SPLIT ROW 2 (FM ENGINE & FM ADSR) ---
        fm_split = tk.Frame(main_frame, bg=self.bg_color)
        fm_split.pack(fill=tk.X, pady=5)
        
        fm_frame = tk.LabelFrame(fm_split, text=" FM CONTROLS ", bg=self.bg_color, fg=self.fg_color, font=self.font)
        fm_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))
        
        fm_top = tk.Frame(fm_frame, bg=self.bg_color)
        fm_top.pack(fill=tk.X, padx=10, pady=2)
        
        tk.Label(fm_top, text="FM ENGINE STATE:", bg=self.bg_color, fg=self.fg_color, font=self.font).pack(side=tk.LEFT, padx=5)
        
        self.fm_on_var = tk.IntVar(value=1)
        tk.Radiobutton(fm_top, text=" ON ", variable=self.fm_on_var, value=1, command=self.update_fm, indicatoron=0, bg="#000055", fg=self.fg_color, selectcolor="#AA0000", font=self.font).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(fm_top, text=" OFF ", variable=self.fm_on_var, value=0, command=self.update_fm, indicatoron=0, bg="#000055", fg=self.fg_color, selectcolor="#AA0000", font=self.font).pack(side=tk.LEFT, padx=5)
        
        self.fm_blend_var = tk.DoubleVar(value=0.0)
        self.create_control_row(fm_frame, "BLEND", self.fm_blend_var, 0.0, 1.0, self.update_fm, resolution=0.01, length=120)
        
        self.fm_idx_var = tk.DoubleVar(value=0.0)
        self.create_control_row(fm_frame, "BASE ID", self.fm_idx_var, 0.0, 20.0, self.update_fm, resolution=0.1, length=120)
        
        self.fm_ratio_var = tk.DoubleVar(value=1.0)
        self.create_control_row(fm_frame, "RATIO", self.fm_ratio_var, 0.25, 10.0, self.update_fm, resolution=0.01, length=120)
        
        fm_env_frame = tk.LabelFrame(fm_split, text=" FM SWELL ADSR ", bg=self.bg_color, fg=self.fg_color, font=self.font)
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


        # --- EFFECTS (Delay) ---
        fx_frame = tk.LabelFrame(main_frame, text=" EFFECTS (DELAY) ", bg=self.bg_color, fg=self.fg_color, font=self.font)
        fx_frame.pack(fill=tk.X, pady=5)
        
        fx_top = tk.Frame(fx_frame, bg=self.bg_color)
        fx_top.pack(fill=tk.X, padx=10, pady=2)
        
        tk.Label(fx_top, text="DELAY STATE:", bg=self.bg_color, fg=self.fg_color, font=self.font).pack(side=tk.LEFT, padx=5)
        self.delay_on_var = tk.IntVar(value=1)
        tk.Radiobutton(fx_top, text=" ON ", variable=self.delay_on_var, value=1, command=self.update_fx, indicatoron=0, bg="#000055", fg=self.fg_color, selectcolor="#AA0000", font=self.font).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(fx_top, text=" OFF ", variable=self.delay_on_var, value=0, command=self.update_fx, indicatoron=0, bg="#000055", fg=self.fg_color, selectcolor="#AA0000", font=self.font).pack(side=tk.LEFT, padx=5)
        
        self.delay_time_var = tk.DoubleVar(value=0.3)
        self.create_control_row(fx_frame, "TIME (s)", self.delay_time_var, 0.01, 2.0, self.update_fx, 0.01, length=300)
        
        self.delay_feed_var = tk.DoubleVar(value=0.3)
        self.create_control_row(fx_frame, "FEEDBCK", self.delay_feed_var, 0.0, 0.95, self.update_fx, 0.01, length=300)
        
        self.delay_mix_var = tk.DoubleVar(value=0.2)
        self.create_control_row(fx_frame, "MIX", self.delay_mix_var, 0.0, 1.0, self.update_fx, 0.01, length=300)

        # --- ARPEGGIATOR ---
        arp_frame = tk.LabelFrame(main_frame, text=" ARPEGGIATOR MATRIX ", bg=self.bg_color, fg=self.fg_color, font=self.font)
        arp_frame.pack(fill=tk.X, pady=5)
        
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
            tk.Radiobutton(arp_1, text=text, variable=self.arp_rate_var, value=val, command=self.update_arp, indicatoron=0, bg="#000055", fg=self.fg_color, selectcolor="#AA0000", width=4).pack(side=tk.LEFT, padx=2)

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
            tk.Radiobutton(arp_2, text=str(val), variable=self.arp_oct_var, value=val, command=self.update_arp, indicatoron=0, bg="#000055", fg=self.fg_color, selectcolor="#AA0000", width=2).pack(side=tk.LEFT, padx=1)

        tk.Label(arp_2, text=" LEN:", bg=self.bg_color, fg=self.fg_color, font=self.font).pack(side=tk.LEFT, padx=(5,0))
        self.arp_len_var = tk.IntVar(value=4)
        for val in [1, 2, 3, 4, 5, 6]:
            tk.Radiobutton(arp_2, text=str(val), variable=self.arp_len_var, value=val, command=self.update_arp, indicatoron=0, bg="#000055", fg=self.fg_color, selectcolor="#AA0000", width=2).pack(side=tk.LEFT, padx=1)

        self.arp_rand_var = tk.IntVar(value=0)
        tk.Checkbutton(arp_2, text="RND", variable=self.arp_rand_var, command=self.update_arp, indicatoron=0, bg="#000055", fg=self.fg_color, selectcolor="#AA0000", width=4).pack(side=tk.LEFT, padx=10)

        # --- SETTINGS I/O ---
        settings_frame = tk.Frame(main_frame, bg=self.bg_color)
        settings_frame.pack(fill=tk.X, pady=5)
        
        save_btn = tk.Button(settings_frame, text="[ SAVE BASE PRESET ]", bg=self.bg_color, fg=self.fg_color, font=self.font, command=self.save_settings, activebackground=self.fg_color, activeforeground=self.bg_color, relief=tk.FLAT)
        save_btn.pack(side=tk.LEFT, padx=10)
        
        load_btn = tk.Button(settings_frame, text="[ LOAD BASE PRESET ]", bg=self.bg_color, fg=self.fg_color, font=self.font, command=self.load_settings, activebackground=self.fg_color, activeforeground=self.bg_color, relief=tk.FLAT)
        load_btn.pack(side=tk.LEFT, padx=10)
        
        # --- OSCILLOSCOPE ---
        scope_frame = tk.LabelFrame(main_frame, text=" SIGNAL VIZ ", bg=self.bg_color, fg=self.fg_color, font=self.font)
        scope_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.canvas = tk.Canvas(scope_frame, bg="#000000", highlightthickness=2, highlightbackground=self.fg_color)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        footer = tk.Label(self.master, text="PLAY KEYS ONSCREEN: A S D F G H J K", bg=self.bg_color, fg="#AAAAFF", font=("PxPlus IBM VGA8", 10))
        footer.pack(pady=2)
        
        # Initialize internal state sync
        self.update_params()
        self.update_env()
        self.update_fm()
        self.update_fm_env()
        self.update_fx()
        self.update_arp()
        
    def create_control_row(self, parent, label_text, var, from_val, to_val, command, resolution=1.0, length=300):
        row = tk.Frame(parent, bg=self.bg_color)
        row.pack(fill=tk.X, padx=10, pady=5)
        
        lbl = tk.Label(row, text=label_text, bg=self.bg_color, fg=self.fg_color, font=self.font, width=7, anchor='w')
        lbl.pack(side=tk.LEFT)
        
        # Custom Canvas Slider with Rich Gold-Red "#E65100" Left Fill
        slider = CanvasSlider(row, variable=var, from_val=from_val, to_val=to_val, command=lambda: command(), resolution=resolution, length=length, width=40, bg_color=self.bg_color, fg_color=self.fg_color, fill_color="#E65100", trough_color="#000055")
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
        if key == self.active_key:
            self.audio_engine.release_note()
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
                self.canvas.create_line(points, fill=self.fg_color, width=2, tags="wave")
                
        self.master.after(60, self.render_scope_loop)
        
    def save_settings(self):
        data = {
            "fm_on": self.fm_on_var.get(),
            "fm_blend": self.fm_blend_var.get(),
            "fm_idx": self.fm_idx_var.get(),
            "fm_ratio": self.fm_ratio_var.get(),
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
                messagebox.showinfo("Loaded", "Settings loaded into matrix!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load: {e}")
        else:
            messagebox.showwarning("No Preset", "No settings found locally.")

def main():
    root = tk.Tk()
    
    audio_engine = AudioEngine()
    try:
        audio_engine.start()
    except Exception as e:
        print(f"Failed to start audio stream: {e}")
    
    app = SynthGUI(root, audio_engine)
    
    def on_closing():
        audio_engine.stop()
        root.destroy()
        os._exit(0)
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.focus_set()
    root.mainloop()

if __name__ == "__main__":
    main()
