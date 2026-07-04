"""
grid_ui.py — ASHERAH Hybrid Sequencer
A piano-roll step sequencer with scale-folded Y-axis,
DM1-style tabbed navigation, swipe-to-paint interaction,
and Moog-inspired aesthetic.

IPC: Communicates with Golden Bull Synth via UDP (127.0.0.1:12160)
MIDI: Virtual MIDI output via mido for external DAW routing.
"""

import sys
import os

# --- TETHERED MODE BOOTSTRAP ---
# We must set PULSE_SINK before ANY audio imports (like beats_engine -> sounddevice)
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
from tkinter import messagebox, filedialog
import time
import threading
import mido
import socket
import subprocess
import json
import numpy as np
import sounddevice as sd
from beats_engine import BeatsEngine, load_wav_sample, render_preset_sound
from presets import FACTORY_PRESETS
from music_theory import (
    get_scale_notes, get_scale_names, get_root_key_names,
    midi_to_freq, is_root_note
)

# Force sounddevice to use PulseAudio device if available
FORCE_DEVICE = None
if os.environ.get('PULSE_SINK'):
    try:
        devices = sd.query_devices()
        for i, d in enumerate(devices):
            if d['name'] == 'pulse' and d['max_output_channels'] > 0:
                FORCE_DEVICE = i
                sd.default.device = (None, i)
                print(f"DEBUG: Sounddevice forced to 'pulse' device (index {i})")
                break
    except Exception as e:
        print(f"DEBUG: Failed to force pulse device: {e}")

CONFIG_PATH = os.path.expanduser("~/.asherah_config.json")

# ─── Moog Theme Color Palette ────────────────────────────────────────
BG_DARK     = "#1a1a1a"   # Midnight Charcoal — main background
BG_GRID     = "#222222"   # Grid cell background
BG_ALT      = "#2a2a2a"   # Alternating 4-step group shade
AMBER       = "#e8a317"   # Moog Amber — active notes
RED_SIGNAL  = "#de1b4a"   # Signal Red — playhead LED
GOLD        = "#f4e022"   # Gold — labels & text
PURPLE      = "#5a37c3"   # Purple — accents & borders
ROOT_HI     = "#2a2200"   # Warm highlight for root note rows
MUTED       = "#444444"   # Disabled/inactive elements
LED_OFF     = "#333333"   # LED off state
TAB_ACTIVE  = AMBER
TAB_INACTIVE = "#2d2d2d"

# ─── Master Cell Size (shared by ROLL and BEATS) ────────────────────
PAD_SIZE     = 54          # Square cell px — used by BEATS pads AND ROLL step cells

# ─── Layout Constants ────────────────────────────────────────────────
LABEL_WIDTH  = 60          # Y-axis label panel width
SLOT_WIDTH   = 140         # Slot sidebar width
LED_HEIGHT   = PAD_SIZE    # LED strip height matches cell height
MAX_STEPS    = 64          # Maximum possible steps
STEP_W       = PAD_SIZE    # Step width (X) — matches pad size
CELL_H       = PAD_SIZE    # Cell height (Y) — matches pad size, fills vertical space
GRID_WIDTH   = MAX_STEPS * STEP_W  # Full 64-step canvas width (3456px, scrollable)
WINDOW_WIDTH = 1366        # Full C302 screen width

FONT         = ("PxPlus IBM VGA8", 10)
FONT_SM      = ("PxPlus IBM VGA8", 8)
FONT_LG      = ("PxPlus IBM VGA8", 16)
FONT_TITLE   = ("PxPlus IBM VGA8", 22)

# ─── Beats / Drum Machine Constants ─────────────────────────────
BEATS_LABEL_W    = 160
BEATS_NUM_TRACKS = 8
DEFAULT_TRACK_NAMES = ["KICK", "SNARE", "HI-HAT", "CLAP",
                        "TOM HI", "TOM LO", "PERC", "FX"]
TIME_SIGS = {
    "4/4":  {"steps": 32, "group": 4},
    "3/4":  {"steps": 24, "group": 4},
    "2/4":  {"steps": 16, "group": 4},
    "5/4":  {"steps": 40, "group": 4},
    "6/8":  {"steps": 24, "group": 3},
    "7/8":  {"steps": 28, "group": 2},
    "9/8":  {"steps": 36, "group": 3},
    "12/8": {"steps": 48, "group": 3},
}


class SnapSlider(tk.Canvas):
    """Custom slider with snapping and visual feedback for center position."""
    def __init__(self, parent, variable, from_val, to_val, command=None, length=120, height=18):
        super().__init__(parent, width=length, height=height, bg="#111111", highlightthickness=1, highlightbackground=PURPLE)
        self.variable = variable
        self.from_val = from_val
        self.to_val = to_val
        self.command = command
        self.length = length
        self.height = height
        
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<Button-1>", self.on_drag)
        self.variable.trace_add("write", lambda *args: self.draw())
        self.after(50, self.draw)

    def on_drag(self, event):
        x = max(0, min(event.x, self.length))
        ratio = x / self.length
        val = self.from_val + ratio * (self.to_val - self.from_val)
        
        # Snap to center logic for bi-directional sliders (Pan)
        if self.from_val < 0 < self.to_val:
            if abs(val) < 0.1: # 10% snap zone
                val = 0.0
        
        self.variable.set(val)
        if self.command:
            # Scale command usually passes a value string
            self.command(val)

    def draw(self):
        self.delete("all")
        try:
            val = self.variable.get()
        except: return
        
        ratio = (val - self.from_val) / (self.to_val - self.from_val)
        x = max(0, min(ratio * self.length, self.length))
        
        is_pan = (self.from_val < 0 < self.to_val)
        is_centered = is_pan and abs(val) < 0.001
        
        # UI Polish: Center indicator color
        fill_color = AMBER if is_centered else GOLD
        if not is_pan: fill_color = GOLD # Gain always gold

        if is_pan:
            cx = self.length / 2
            # Center line
            self.create_line(cx, 0, cx, self.height, fill=PURPLE, width=1)
            # Bi-directional fill
            self.create_rectangle(cx, 2, x, self.height-2, fill=fill_color, width=0)
        else:
            # Uni-directional fill
            self.create_rectangle(0, 0, x, self.height, fill=fill_color, width=0)
            
        # Knob
        kw = 8
        self.create_rectangle(x - kw/2, 0, x + kw/2, self.height, fill=fill_color, outline="#ffffff", width=1)


class AsherahSequencer:
    """ASHERAH Hybrid Sequencer — Piano Roll with Scale Fold."""

    def __init__(self, master, tx_pipe=None, udp_port=12160):
        self.master = master
        self.tx_pipe = tx_pipe

        # UDP IPC setup for standalone mode
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_addr = ("127.0.0.1", udp_port)

        # ── Tethered Sink Management ─────────────────────────────
        self.tether_sink = None
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
            self.tether_sink = f"station_track_{track_num}_pipe"
            
            # Ensure sink exists
            try:
                sinks = subprocess.check_output(["pactl", "list", "short", "sinks"]).decode()
                if self.tether_sink not in sinks:
                    subprocess.run(["pactl", "load-module", "module-null-sink", 
                                    f"sink_name={self.tether_sink}", 
                                    f"sink_properties=device.description={self.tether_sink}"])
            except: pass

        self.master.title("ASHERAH HYBRID SEQUENCER")
        self.master.configure(bg=BG_DARK)

        # Start maximized — fills the C302 screen (1366×768)
        try:
            self.master.attributes("-zoomed", True)
        except Exception:
            self.master.geometry(f"{WINDOW_WIDTH}x768+0+0")

        # ── Sequencer State ──────────────────────────────────────────
        self.is_playing = False
        self.bpm = 120.0
        self.num_slots = 4
        self.active_slot = 0
        self.slot_step_counts = {i: 16 for i in range(self.num_slots)}
        self.slot_current_steps = {i: -1 for i in range(self.num_slots)}
        self.slot_volumes = {i: 0.8 for i in range(self.num_slots)}
        self.slot_pans = {i: 0.0 for i in range(self.num_slots)} # -1 to 1
        self.slot_mutes = {i: False for i in range(self.num_slots)}
        self.slot_solos = {i: False for i in range(self.num_slots)}
        self.slot_reverb = {i: 0.0 for i in range(self.num_slots)}
        self.slot_delay = {i: 0.0 for i in range(self.num_slots)}
        self.master_volume = 0.8
        self.mono_mode = False

        # Clipboard for Copy/Paste
        self.clipboard = None # Can be ROLL steps or BEATS pattern

        # Scale fold state
        self.root_key = "C"
        self.scale_name = "Minor"
        self.scale_notes = []  # List of (midi_note, display_name)

        # Step data: list of step dicts
        # Each: {"stepIndex", "midiNote", "velocity", "length", "isSlide", "instrumentSlot"}
        self.steps = []
        # Lookup cache: (instrumentSlot, stepIndex) -> list of steps
        # Rebuilt whenever self.steps changes. Never queried directly from clock.
        self._steps_cache = {}  # type: dict[tuple, list]

        # Paint mode tracking
        self._paint_mode = None  # "paint" or "erase"
        self._last_paint_cell = None

        # MIDI output
        try:
            self.midi_out = mido.open_output('Asherah Sequencer', virtual=True)
        except Exception as e:
            print(f"Warning: Could not create Virtual MIDI Output: {e}")
            self.midi_out = None
        self.last_midi_note = None

        # ── Beats / Drum Machine State ─────────────────────────────
        self.beats_engine = BeatsEngine(BEATS_NUM_TRACKS, device=FORCE_DEVICE, sink_name=self.tether_sink)
        self.beats_time_sig = "4/4"
        self.beats_current_step = -1
        self.beats_active_track = 0
        
        # Load config
        self.config = {"last_sample_dir": os.path.expanduser("~")}
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r") as f:
                    self.config.update(json.load(f))
            except: pass
        self.last_sample_dir = self.config.get("last_sample_dir", os.path.expanduser("~"))

        from music_theory import midi_to_note_name
        self._beats_note_list = [(m, midi_to_note_name(m)) for m in range(24, 84)]

        self.beats_tracks = []
        for i in range(BEATS_NUM_TRACKS):
            self.beats_tracks.append({
                "name": DEFAULT_TRACK_NAMES[i],
                "source_type": "synth",
                "sample_path": "",
                "preset_name": "Init",
                "midi_note": 36 + i * 3,
                "pattern": [0] * MAX_STEPS,
                "volume": 0.8,
                "pan": 0.0,
                "mute": False,
                "solo": False,
            })

        self.tap_times = []

        # ── Build UI ─────────────────────────────────────────────────
        self._build_top_bar()
        self._build_tab_nav()
        self._build_transport()
        self._build_tab_frames()
        self._rebuild_scale()
        self._show_tab("ROLL")

    # ─────────────────────────────────────────────────────────────────
    # UI CONSTRUCTION
    # ─────────────────────────────────────────────────────────────────

    def _build_top_bar(self):
        """Title + Root Key + Scale/Mode dropdowns — always visible."""
        bar = tk.Frame(self.master, bg=BG_DARK)
        bar.pack(fill=tk.X, padx=10, pady=(10, 5))

        # Title
        tk.Label(bar, text="ASHERAH", font=FONT_TITLE, bg=BG_DARK, fg=GOLD).pack(side=tk.LEFT, padx=(5, 20))

        # Root Key
        tk.Label(bar, text="ROOT:", font=FONT, bg=BG_DARK, fg=GOLD).pack(side=tk.LEFT, padx=(10, 2))
        self.root_var = tk.StringVar(value=self.root_key)
        root_menu = tk.OptionMenu(bar, self.root_var, *get_root_key_names(), command=self._on_scale_change)
        root_menu.config(bg=PURPLE, fg=GOLD, font=FONT, highlightthickness=0, activebackground=AMBER, activeforeground=BG_DARK)
        root_menu["menu"].config(bg=BG_DARK, fg=GOLD, font=FONT_SM)
        root_menu.pack(side=tk.LEFT, padx=2)

        # Scale / Mode
        tk.Label(bar, text="SCALE:", font=FONT, bg=BG_DARK, fg=GOLD).pack(side=tk.LEFT, padx=(15, 2))
        self.scale_var = tk.StringVar(value=self.scale_name)
        scale_menu = tk.OptionMenu(bar, self.scale_var, *get_scale_names(), command=self._on_scale_change)
        scale_menu.config(bg=PURPLE, fg=GOLD, font=FONT, highlightthickness=0, activebackground=AMBER, activeforeground=BG_DARK)
        scale_menu["menu"].config(bg=BG_DARK, fg=GOLD, font=FONT_SM)
        scale_menu.pack(side=tk.LEFT, padx=2)

    def _build_tab_nav(self):
        """Tabbed navigation: ROLL | BEATS | MIXER | FX."""
        nav = tk.Frame(self.master, bg=BG_DARK)
        nav.pack(fill=tk.X, padx=10, pady=(0, 2))

        self.tab_buttons = {}
        for tab_name in ["ROLL", "BEATS"]:
            btn = tk.Button(
                nav, text=tab_name, font=FONT, width=10,
                bg=TAB_INACTIVE, fg=GOLD,
                activebackground=AMBER, activeforeground=BG_DARK,
                relief=tk.FLAT, bd=0, pady=6,
                command=lambda t=tab_name: self._show_tab(t)
            )
            btn.pack(side=tk.LEFT, padx=1)
            self.tab_buttons[tab_name] = btn

    def _build_transport(self):
        """Transport bar: Play/Stop, BPM, Step Count, Mono toggle."""
        transport = tk.Frame(self.master, bg="#111111", highlightthickness=1, highlightbackground=PURPLE)
        transport.pack(fill=tk.X, padx=10, pady=(0, 5))

        # Play / Stop
        self.play_btn = tk.Button(
            transport, text="▶ PLAY", font=FONT, width=10,
            bg="#004400", fg="#00ff00",
            activebackground=AMBER, activeforeground=BG_DARK,
            relief=tk.FLAT, command=self.toggle_playback
        )
        self.play_btn.pack(side=tk.LEFT, padx=10, pady=6)

        # Save / Open
        tk.Button(
            transport, text="SAVE", font=FONT, width=6,
            bg=PURPLE, fg=GOLD, activebackground=AMBER,
            activeforeground=BG_DARK, relief=tk.FLAT,
            command=self._save_project
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            transport, text="OPEN", font=FONT, width=6,
            bg=PURPLE, fg=GOLD, activebackground=AMBER,
            activeforeground=BG_DARK, relief=tk.FLAT,
            command=self._load_project
        ).pack(side=tk.LEFT, padx=2)

        # BPM
        tk.Label(transport, text="BPM:", font=FONT, bg="#111111", fg=GOLD).pack(side=tk.LEFT, padx=(20, 2))
        self.bpm_var = tk.DoubleVar(value=self.bpm)
        self.bpm_str_var = tk.StringVar(value=str(int(self.bpm)))
        
        bpm_scale = tk.Scale(
            transport, variable=self.bpm_var, from_=40, to=280,
            orient=tk.HORIZONTAL, length=150, showvalue=False,
            bg="#111111", fg=GOLD, troughcolor=BG_DARK,
            highlightthickness=0, sliderlength=15,
            command=self._on_slider_change
        )
        bpm_scale.pack(side=tk.LEFT, padx=2)
        self.bpm_entry = tk.Entry(
            transport, textvariable=self.bpm_str_var, width=6,
            bg=BG_DARK, fg=GOLD, font=FONT, insertbackground=GOLD
        )
        self.bpm_entry.bind("<Return>", self._on_bpm_change)
        self.bpm_entry.bind("<FocusOut>", self._on_bpm_change)

        # Beat LED (Metronome)
        self.beat_led = tk.Canvas(transport, width=15, height=15, bg=BG_DARK, highlightthickness=0)
        self.beat_led.pack(side=tk.LEFT, padx=(10, 5))
        self._draw_beat_led(False)

        # Tap Tempo Button
        self.tap_btn = tk.Button(
            transport, text="TAP", font=FONT, width=4,
            bg=PURPLE, fg=GOLD, activebackground=AMBER,
            activeforeground=BG_DARK, relief=tk.FLAT,
            command=self._on_tap_tempo
        )
        self.tap_btn.pack(side=tk.LEFT, padx=5)

        # Master Volume
        tk.Label(transport, text="MASTER VOL:", font=FONT, bg="#111111", fg=GOLD).pack(side=tk.LEFT, padx=(20, 2))
        self.master_vol_var = tk.DoubleVar(value=self.master_volume)
        SnapSlider(transport, self.master_vol_var, 0.0, 1.2, self._on_master_vol_change).pack(side=tk.LEFT, padx=2)

        # Mono Mode toggle
        self.mono_var = tk.IntVar(value=0)
        self.mono_btn = tk.Checkbutton(
            transport, text="MONO", variable=self.mono_var,
            indicatoron=0, font=FONT, width=6,
            bg=TAB_INACTIVE, fg=GOLD, selectcolor=RED_SIGNAL,
            activebackground=AMBER, activeforeground=BG_DARK,
            command=self._on_mono_toggle
        )
        self.mono_btn.pack(side=tk.RIGHT, padx=10)

        # Clear Button
        self.clear_btn = tk.Button(
            transport, text="CLEAR", font=FONT, width=8,
            bg="#440000", fg=GOLD,
            activebackground=RED_SIGNAL, activeforeground=BG_DARK,
            relief=tk.FLAT, command=self.clear_grid
        )
        self.clear_btn.pack(side=tk.RIGHT, padx=5)

        # Synth Button - To return to Golden Bull
        self.synth_btn = tk.Button(
            transport, text="SYNTH", font=FONT, width=8,
            bg=PURPLE, fg=GOLD,
            activebackground=AMBER, activeforeground=BG_DARK,
            relief=tk.FLAT, command=lambda: subprocess.Popen([sys.executable, "main.py"])
        )
        self.synth_btn.pack(side=tk.RIGHT, padx=5)

    def _build_tab_frames(self):
        """Create the content frames for each tab."""
        self.tab_container = tk.Frame(self.master, bg=BG_DARK)
        self.tab_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.tab_frames = {}

        # ── ROLL TAB ─────────────────────────────────────────────────
        steps_frame = tk.Frame(self.tab_container, bg=BG_DARK)
        self.tab_frames["ROLL"] = steps_frame

        # LED Strip
        self.led_canvas = tk.Canvas(
            steps_frame, width=GRID_WIDTH, height=LED_HEIGHT,
            bg=BG_DARK, highlightthickness=0
        )
        self.led_canvas.pack(anchor="e", padx=(LABEL_WIDTH + SLOT_WIDTH, 0), pady=(0, 2))

        # Piano Roll area (labels + grid side by side)
        roll_frame = tk.Frame(steps_frame, bg=BG_DARK)
        roll_frame.pack(fill=tk.BOTH, expand=True)

        # Slot Selector Sidebar
        self.slot_canvas = tk.Canvas(
            roll_frame, width=SLOT_WIDTH, bg=BG_DARK,
            highlightthickness=0
        )
        self.slot_canvas.pack(side=tk.LEFT, fill=tk.Y)
        self.slot_canvas.bind("<Button-1>", self._on_slot_click)

        # Y-axis note labels (scrollable)
        self.label_canvas = tk.Canvas(
            roll_frame, width=LABEL_WIDTH, bg=BG_DARK,
            highlightthickness=0
        )
        self.label_canvas.pack(side=tk.LEFT, fill=tk.Y)

        # Main grid canvas (scrollable)
        grid_outer = tk.Frame(roll_frame, bg=BG_DARK)
        grid_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.grid_canvas = tk.Canvas(
            grid_outer, bg="#000000",
            highlightthickness=1, highlightbackground=PURPLE
        )
        self.grid_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbar for vertical scrolling
        self.scroll_y = tk.Scrollbar(
            grid_outer, orient=tk.VERTICAL,
            command=self._on_scroll_y,
            bg=BG_DARK, troughcolor=BG_DARK
        )
        self.scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.grid_canvas.config(yscrollcommand=self._sync_scroll)
        self.label_canvas.config(yscrollcommand=self._sync_scroll)

        # Horizontal Scrollbar for ROLL
        self.scroll_x = tk.Scrollbar(
            grid_outer, orient=tk.HORIZONTAL,
            command=self._on_scroll_x,
            bg=BG_DARK, troughcolor=BG_DARK
        )
        self.scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.grid_canvas.config(xscrollcommand=self._sync_scroll_x)

        # Bind interactions
        self.grid_canvas.bind("<Button-1>", self._on_grid_click)
        self.grid_canvas.bind("<B1-Motion>", self._on_grid_drag)
        self.grid_canvas.bind("<ButtonRelease-1>", self._on_grid_release)

        # ── Slot Config Panel (bottom) ──────────────────────────────
        slot_config = tk.Frame(steps_frame, bg="#111111", highlightthickness=1, highlightbackground=PURPLE)
        slot_config.pack(fill=tk.X, pady=(5, 0))

        self.slot_config_label = tk.Label(slot_config, text="SLOT CONFIG: 0", font=FONT, bg="#111111", fg=AMBER)
        self.slot_config_label.pack(anchor="w", padx=10, pady=(5, 2))

        mix_row = tk.Frame(slot_config, bg="#111111")
        mix_row.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(mix_row, text="GAIN:", font=FONT_SM, bg="#111111", fg=GOLD).pack(side=tk.LEFT)
        self.slot_vol_var = tk.DoubleVar(value=0.8)
        SnapSlider(mix_row, self.slot_vol_var, 0.0, 1.2, self._on_slot_mix_change, length=100).pack(side=tk.LEFT, padx=5)

        tk.Label(mix_row, text="PAN:", font=FONT_SM, bg="#111111", fg=GOLD).pack(side=tk.LEFT, padx=(15, 0))
        self.slot_pan_var = tk.DoubleVar(value=0.0)
        SnapSlider(mix_row, self.slot_pan_var, -1.0, 1.0, self._on_slot_mix_change, length=100).pack(side=tk.LEFT, padx=5)
        
        # FX Row
        fx_row = tk.Frame(slot_config, bg="#111111")
        fx_row.pack(fill=tk.X, padx=10, pady=(0, 5))

        tk.Label(fx_row, text="REVERB:", font=FONT_SM, bg="#111111", fg=GOLD).pack(side=tk.LEFT)
        self.slot_rev_var = tk.DoubleVar(value=0.0)
        SnapSlider(fx_row, self.slot_rev_var, 0.0, 1.0, self._on_slot_mix_change, length=100).pack(side=tk.LEFT, padx=5)

        tk.Label(fx_row, text="DELAY:", font=FONT_SM, bg="#111111", fg=GOLD).pack(side=tk.LEFT, padx=(15, 0))
        self.slot_del_var = tk.DoubleVar(value=0.0)
        SnapSlider(fx_row, self.slot_del_var, 0.0, 1.0, self._on_slot_mix_change, length=100).pack(side=tk.LEFT, padx=5)

        # Copy/Paste Row
        cp_row = tk.Frame(slot_config, bg="#111111")
        cp_row.pack(fill=tk.X, padx=10, pady=(0, 5))
        
        tk.Button(cp_row, text="COPY SLOT", font=FONT_SM, bg=TAB_INACTIVE, fg=GOLD,
                  command=self._copy_slot, relief=tk.FLAT, width=12).pack(side=tk.LEFT)
        tk.Button(cp_row, text="PASTE SLOT", font=FONT_SM, bg=TAB_INACTIVE, fg=GOLD,
                  command=self._paste_slot, relief=tk.FLAT, width=12).pack(side=tk.LEFT, padx=5)

        # Mute/Solo in config panel
        self.slot_mute_var = tk.IntVar(value=0)
        tk.Checkbutton(cp_row, text="MUTE", variable=self.slot_mute_var,
                       indicatoron=0, font=FONT_SM, width=8,
                       bg=TAB_INACTIVE, fg=GOLD, selectcolor=RED_SIGNAL,
                       command=self._on_slot_mute_toggle).pack(side=tk.LEFT, padx=(20, 5))
        
        self.slot_solo_var = tk.IntVar(value=0)
        tk.Checkbutton(cp_row, text="SOLO", variable=self.slot_solo_var,
                       indicatoron=0, font=FONT_SM, width=8,
                       bg=TAB_INACTIVE, fg=GOLD, selectcolor=AMBER,
                       command=self._on_slot_solo_toggle).pack(side=tk.LEFT, padx=5)

        # Mouse wheel scrolling
        self.grid_canvas.bind("<Button-4>", lambda e: self._on_mousewheel(-3))
        self.grid_canvas.bind("<Button-5>", lambda e: self._on_mousewheel(3))
        self.label_canvas.bind("<Button-4>", lambda e: self._on_mousewheel(-3))
        self.label_canvas.bind("<Button-5>", lambda e: self._on_mousewheel(3))
        
        self._draw_slot_sidebar()

        # ── BEATS TAB ─────────────────────────────────────────────
        self._build_beats_tab()

        # ── MIXER TAB (Stub) ─────────────────────────────────────────
        mixer_frame = tk.Frame(self.tab_container, bg=BG_DARK)
        self.tab_frames["MIXER"] = mixer_frame
        tk.Label(mixer_frame, text="MIXER — COMING SOON", font=FONT_LG, bg=BG_DARK, fg=MUTED).pack(expand=True)

        # ── FX TAB (Stub) ────────────────────────────────────────────
        fx_frame = tk.Frame(self.tab_container, bg=BG_DARK)
        self.tab_frames["FX"] = fx_frame
        tk.Label(fx_frame, text="FX — COMING SOON", font=FONT_LG, bg=BG_DARK, fg=MUTED).pack(expand=True)

    # ─────────────────────────────────────────────────────────────────
    # TAB NAVIGATION
    # ─────────────────────────────────────────────────────────────────

    def _show_tab(self, tab_name):
        """Switch to the selected tab."""
        for name, frame in self.tab_frames.items():
            frame.pack_forget()
        self.tab_frames[tab_name].pack(fill=tk.BOTH, expand=True)

        for name, btn in self.tab_buttons.items():
            if name == tab_name:
                btn.config(bg=TAB_ACTIVE, fg=BG_DARK)
            else:
                btn.config(bg=TAB_INACTIVE, fg=GOLD)
        
        # Ensure sidebar is drawn if returning to ROLL
        if tab_name == "ROLL":
            self._draw_slot_sidebar()
            self._draw_grid()
            self._draw_led_strip()

        # Refresh BEATS tab if switching to it
        if tab_name == "BEATS":
            self._draw_beats_sidebar()
            self._draw_beats_grid()
            self._draw_beats_leds()
            self._update_beats_config_panel()

    def _draw_slot_sidebar(self):
        """Draw the 16-slot track selector sidebar with +/- step controls."""
        self.slot_canvas.delete("all")
        h = self.slot_canvas.winfo_height()
        if h < 10: h = 600
        slot_h = h / self.num_slots

        for i in range(self.num_slots):
            y1 = i * slot_h
            y2 = y1 + slot_h
            mid_y = y1 + slot_h/2

            # Active slot highlight
            bg = "#333333" if i == self.active_slot else BG_DARK
            self.slot_canvas.create_rectangle(0, y1, SLOT_WIDTH, y2, fill=bg, outline=MUTED)

            # Slot name
            label_color = AMBER if i == self.active_slot else GOLD
            self.slot_canvas.create_text(8, mid_y, text=f"TRK{i+1:02}", fill=label_color, anchor="w", font=FONT_SM)

            # Step count display
            steps = self.slot_step_counts[i]
            self.slot_canvas.create_text(65, mid_y, text=str(steps), fill=GOLD, anchor="center", font=FONT_SM)

            # - Button
            self.slot_canvas.create_rectangle(45, mid_y-7, 55, mid_y+7, fill=PURPLE, outline="", tags=f"minus_{i}")
            self.slot_canvas.create_text(50, mid_y, text="-", fill=GOLD, font=FONT_SM, tags=f"minus_{i}")

            # + Button
            self.slot_canvas.create_rectangle(75, mid_y-7, 85, mid_y+7, fill=PURPLE, outline="", tags=f"plus_{i}")
            self.slot_canvas.create_text(80, mid_y, text="+", fill=GOLD, font=FONT_SM, tags=f"plus_{i}")

            # Mini playhead LED
            led_color = RED_SIGNAL if (self.is_playing and self.slot_current_steps[i] >= 0) else LED_OFF
            self.slot_canvas.create_oval(SLOT_WIDTH - 15, mid_y - 4, SLOT_WIDTH - 7, mid_y + 4, fill=led_color, outline="")

            # Mute Button
            mute_bg = RED_SIGNAL if self.slot_mutes[i] else "#333333"
            self.slot_canvas.create_rectangle(95, mid_y-8, 110, mid_y+8, fill=mute_bg, outline=MUTED, tags=f"mute_{i}")
            self.slot_canvas.create_text(102, mid_y, text="M", fill=GOLD, font=FONT_SM, tags=f"mute_{i}")

            # Solo Button
            solo_bg = AMBER if self.slot_solos[i] else "#333333"
            self.slot_canvas.create_rectangle(112, mid_y-8, 127, mid_y+8, fill=solo_bg, outline=MUTED, tags=f"solo_{i}")
            self.slot_canvas.create_text(119, mid_y, text="S", fill=GOLD, font=FONT_SM, tags=f"solo_{i}")

    def _on_slot_click(self, e):
        """Switch active slot on click."""
        slot_idx = int(e.y // (self.slot_canvas.winfo_height() / self.num_slots))
        if 0 <= slot_idx < self.num_slots:
            # Handle +/- button clicks
            if 40 <= e.x <= 60:
                self._change_slot_steps(slot_idx, -1)
            elif 70 <= e.x <= 90:
                self._change_slot_steps(slot_idx, 1)
            elif 95 <= e.x <= 110:
                self.slot_mutes[slot_idx] = not self.slot_mutes[slot_idx]
            elif 112 <= e.x <= 127:
                self.slot_solos[slot_idx] = not self.slot_solos[slot_idx]
            else:
                self.active_slot = slot_idx
            
            self._draw_slot_sidebar()
            self._draw_grid()
            self._draw_led_strip()
            self._update_slot_config_panel()

    def _update_slot_config_panel(self):
        """Update the ROLL slot config panel to reflect selected slot settings."""
        self.slot_config_label.config(text=f"SLOT CONFIG: {self.active_slot}")
        self.slot_vol_var.set(self.slot_volumes[self.active_slot])
        self.slot_pan_var.set(self.slot_pans[self.active_slot])
        self.slot_rev_var.set(self.slot_reverb[self.active_slot])
        self.slot_del_var.set(self.slot_delay[self.active_slot])
        self.slot_mute_var.set(1 if self.slot_mutes[self.active_slot] else 0)
        self.slot_solo_var.set(1 if self.slot_solos[self.active_slot] else 0)

    def _on_slot_mute_toggle(self):
        """Toggle mute for active ROLL slot."""
        self.slot_mutes[self.active_slot] = bool(self.slot_mute_var.get())
        self._draw_slot_sidebar()

    def _on_slot_solo_toggle(self):
        """Toggle solo for active ROLL slot."""
        self.slot_solos[self.active_slot] = bool(self.slot_solo_var.get())
        self._draw_slot_sidebar()

    def _change_slot_steps(self, slot_idx, delta):
        """Adjust step count for a slot, clamping 1-64."""
        old_val = self.slot_step_counts[slot_idx]
        new_val = max(1, min(MAX_STEPS, old_val + delta))
        self.slot_step_counts[slot_idx] = new_val
        
        # If length reduced below current playhead, reset head
        if new_val <= self.slot_current_steps[slot_idx]:
             self.slot_current_steps[slot_idx] = 0

    def clear_grid(self):
        """Wipe all notes from the sequencer."""
        if tk.messagebox.askyesno("Clear Matrix", "Wipe all notes from the current sequence?"):
            self.steps = []
            self._steps_cache.clear()
            self._draw_grid()

    # ─────────────────────────────────────────────────────────────────
    # SCALE FOLD & Y-AXIS
    # ─────────────────────────────────────────────────────────────────

    def _on_scale_change(self, *_):
        """Called when root key or scale dropdown changes."""
        self.root_key = self.root_var.get()
        self.scale_name = self.scale_var.get()
        self._rebuild_scale()

    def _rebuild_scale(self):
        """Regenerate the Y-axis notes and redraw everything."""
        self.scale_notes = get_scale_notes(self.root_key, self.scale_name, octave_lo=2, octave_hi=6)
        self.scale_notes = list(reversed(self.scale_notes))

        # Build a fast row-lookup: midi_note -> row index
        self._midi_to_row = {mn: i for i, (mn, _) in enumerate(self.scale_notes)}

        # Remove steps no longer in scale and rebuild cache
        valid_midis = set(self._midi_to_row)
        self.steps = [s for s in self.steps if s["midiNote"] in valid_midis]
        self._rebuild_steps_cache()

        self._draw_led_strip()
        self._draw_grid()
        self._draw_slot_sidebar()

    def _rebuild_steps_cache(self):
        """Rebuild the (slot, stepIndex) -> [step, ...] lookup dict."""
        cache = {}
        for s in self.steps:
            key = (s["instrumentSlot"], s["stepIndex"])
            if key not in cache:
                cache[key] = []
            cache[key].append(s)
        self._steps_cache = cache

    def _get_row_for_midi(self, midi_note):
        """Return the row index for a given MIDI note, or -1 if not in scale."""
        return self._midi_to_row.get(midi_note, -1)

    def _get_midi_for_row(self, row):
        """Return the MIDI note for a given row index."""
        if 0 <= row < len(self.scale_notes):
            return self.scale_notes[row][0]
        return -1

    # ─────────────────────────────────────────────────────────────────
    # LED STRIP
    # ─────────────────────────────────────────────────────────────────

    def _draw_led_strip(self):
        """Draw a 64-step LED strip, graying out inactive steps for the ACTIVE slot."""
        self.led_canvas.config(scrollregion=(0, 0, GRID_WIDTH, LED_HEIGHT))
        self.led_canvas.delete("all")
        led_r = STEP_W // 5          # Scale LED radius to cell size
        active_limit = self.slot_step_counts[self.active_slot]
        current_step = self.slot_current_steps[self.active_slot]

        for i in range(MAX_STEPS):
            cx = i * STEP_W + STEP_W / 2
            cy = LED_HEIGHT / 2
            color = RED_SIGNAL if i == current_step else LED_OFF
            self.led_canvas.create_oval(
                cx - led_r, cy - led_r, cx + led_r, cy + led_r,
                fill=color, outline="", tags=f"led_{i}"
            )

    def _update_led(self, step_idx):
        """Update only the two changed LED ovals (fast path: prev off, curr on)."""
        prev = getattr(self, '_led_prev_step', -1)
        if prev == step_idx:
            return
        num_steps = self.slot_step_counts[self.active_slot]
        if 0 <= prev < num_steps:
            self.led_canvas.itemconfig(f"led_{prev}", fill=LED_OFF)
        if 0 <= step_idx < num_steps:
            self.led_canvas.itemconfig(f"led_{step_idx}", fill=RED_SIGNAL)
        self._led_prev_step = step_idx

    # ─────────────────────────────────────────────────────────────────
    # PIANO ROLL GRID DRAWING
    # ─────────────────────────────────────────────────────────────────

    def _draw_grid(self):
        """Redraw grid for the ACTIVE slot, graying out steps beyond its limit."""
        num_rows = len(self.scale_notes)
        grid_h = num_rows * CELL_H
        active_limit = self.slot_step_counts[self.active_slot]

        # Configure scroll regions
        self.grid_canvas.config(scrollregion=(0, 0, GRID_WIDTH, grid_h))
        self.label_canvas.config(scrollregion=(0, 0, LABEL_WIDTH, grid_h))

        self.grid_canvas.delete("all")
        self.label_canvas.delete("all")

        # ── Draw rows ────────────────────────────────────────────────
        for r in range(num_rows):
            midi_note, display = self.scale_notes[r]
            y1 = r * CELL_H
            y2 = y1 + CELL_H
            is_root = is_root_note(midi_note, self.root_key)

            # Row background on label canvas
            label_bg = ROOT_HI if is_root else BG_DARK
            self.label_canvas.create_rectangle(0, y1, LABEL_WIDTH, y2, fill=label_bg, outline="")
            self.label_canvas.create_text(
                LABEL_WIDTH - 5, y1 + CELL_H / 2,
                text=display, fill=(AMBER if is_root else GOLD), anchor="e", font=FONT_SM
            )

            # ── Draw 64 cells for this row ────────────────────────────
            for c in range(MAX_STEPS):
                x1 = c * STEP_W
                x2 = x1 + STEP_W
                
                if c >= active_limit:
                    bg = "#111111" # Grayed out background
                    outline_color = "#1a1a1a"
                else:
                    group = c // 4
                    if is_root: bg = ROOT_HI
                    elif group % 2 == 0: bg = BG_GRID
                    else: bg = BG_ALT
                    outline_color = MUTED

                self.grid_canvas.create_rectangle(
                    x1, y1, x2, y2, fill=bg, outline=outline_color,
                    tags=(f"cell_{r}_{c}", "cell")
                )

        # ── Draw active notes ONLY FOR THIS SLOT ──────────────────────
        # (Filtering ensures we only see notes within the active length)
        for step in self.steps:
            if step.get("instrumentSlot", 0) == self.active_slot and step["stepIndex"] < active_limit:
                self._draw_note(step)

        # ── Draw playhead ────────────────────────────────────────────
        current_step = self.slot_current_steps[self.active_slot]
        if 0 <= current_step < active_limit:
            self._draw_playhead(current_step)

        # Horizontal gridlines
        for r in range(num_rows + 1):
            y = r * CELL_H
            self.grid_canvas.create_line(0, y, GRID_WIDTH, y, fill=MUTED, tags="gridline")
            self.label_canvas.create_line(0, y, LABEL_WIDTH, y, fill=MUTED)

        # Vertical beat lines (every 4 steps)
        for c in range(MAX_STEPS + 1):
            x = c * STEP_W
            if c > active_limit: continue
            width = 2 if c % 4 == 0 else 1
            color = PURPLE if c % 4 == 0 else MUTED
            self.grid_canvas.create_line(x, 0, x, grid_h, fill=color, width=width, tags="gridline")

    def _draw_note(self, step):
        """Draw a single note on the grid using fixed STEP_W."""
        row = self._get_row_for_midi(step["midiNote"])
        if row < 0: return

        col = step["stepIndex"]
        length = step.get("length", 1)

        x1 = col * STEP_W + 1
        y1 = row * CELL_H + 1
        x2 = (col + length) * STEP_W - 1
        y2 = y1 + CELL_H - 2

        current_step = self.slot_current_steps[self.active_slot]
        color = RED_SIGNAL if col == current_step else AMBER
        if step.get("isSlide", False): color = "#c07810"

        self.grid_canvas.create_rectangle(
            x1, y1, x2, y2, fill=color, outline="",
            tags=(f"note_{row}_{col}", "note")
        )

    def _draw_playhead(self, col):
        """Draw playhead using fixed STEP_W."""
        num_rows = len(self.scale_notes)
        x1 = col * STEP_W
        x2 = x1 + STEP_W
        self.grid_canvas.create_rectangle(
            x1, 0, x2, num_rows * CELL_H,
            fill="", outline=RED_SIGNAL, width=2,
            tags="playhead"
        )

    # ─────────────────────────────────────────────────────────────────
    # SCROLLING
    # ─────────────────────────────────────────────────────────────────

    def _on_scroll_y(self, *args):
        self.grid_canvas.yview(*args)
        self.label_canvas.yview(*args)

    def _sync_scroll(self, *args):
        self.scroll_y.set(*args)
        self.grid_canvas.yview("moveto", args[0])
        self.label_canvas.yview("moveto", args[0])

    def _on_scroll_x(self, *args):
        self.grid_canvas.xview(*args)
        self.led_canvas.xview(*args)

    def _sync_scroll_x(self, *args):
        self.scroll_x.set(*args)
        self.led_canvas.xview("moveto", args[0])

    def _on_beats_scroll_x(self, *args):
        self.beats_grid_canvas.xview(*args)
        self.beats_led_canvas.xview(*args)

    def _sync_beats_scroll_x(self, *args):
        self.beats_scroll_x.set(*args)
        self.beats_led_canvas.xview("moveto", args[0])

    def _on_mousewheel(self, delta):
        self.grid_canvas.yview_scroll(delta, "units")
        self.label_canvas.yview_scroll(delta, "units")

    # ─────────────────────────────────────────────────────────────────
    # INTERACTION HANDLERS (Swipe-to-Paint)
    # ─────────────────────────────────────────────────────────────────

    def _canvas_to_cell(self, event):
        """Convert canvas event coordinates to (row, col) using fixed STEP_W."""
        # Convert to canvas coordinates (accounting for scroll)
        cx = self.grid_canvas.canvasx(event.x)
        cy = self.grid_canvas.canvasy(event.y)

        col = int(cx // STEP_W)
        row = int(cy // CELL_H)

        num_rows = len(self.scale_notes)
        if 0 <= col < MAX_STEPS and 0 <= row < num_rows:
            return (row, col)
        return None

    def _get_step_at(self, row, col):
        """Find a step at the given row/col in the ACTIVE slot (O(1) cache lookup)."""
        midi_note = self._get_midi_for_row(row)
        for s in self._steps_cache.get((self.active_slot, col), []):
            if s["midiNote"] == midi_note:
                return s
        return None

    def _on_grid_click(self, event):
        """Handle initial click — enforce active_limit."""
        cell = self._canvas_to_cell(event)
        if cell is None: return

        row, col = cell
        active_limit = self.slot_step_counts[self.active_slot]
        if col >= active_limit: return # Cannot paint in grayed out area

        existing = self._get_step_at(row, col)

        if existing:
            # Start ERASE mode
            self._paint_mode = "erase"
            self._remove_step(row, col)
        else:
            # Start PAINT mode
            self._paint_mode = "paint"
            self._place_step(row, col)

        self._last_paint_cell = cell

    def _on_grid_drag(self, event):
        """Handle drag — enforce active_limit."""
        cell = self._canvas_to_cell(event)
        if cell is None or cell == self._last_paint_cell: return

        row, col = cell
        active_limit = self.slot_step_counts[self.active_slot]
        if col >= active_limit: return

        if self._paint_mode == "paint":
            self._place_step(row, col)
        elif self._paint_mode == "erase":
            self._remove_step(row, col)

        self._last_paint_cell = cell

    def _on_grid_release(self, event):
        """End paint/erase stroke."""
        self._paint_mode = None
        self._last_paint_cell = None
        # Detect legato after painting is done
        self._detect_legato()

    def _place_step(self, row, col):
        """Place a note at (row, col)."""
        midi_note = self._get_midi_for_row(row)
        if midi_note < 0:
            return

        # Mono mode: remove other notes in this column
        if self.mono_mode:
            self.steps = [s for s in self.steps if s["stepIndex"] != col]
            # Partial cache invalidation: remove all entries for this col across all slots
            self._steps_cache = {k: v for k, v in self._steps_cache.items() if k[1] != col}

        # Don't duplicate
        existing = self._get_step_at(row, col)
        if existing:
            return

        step = {
            "stepIndex": col,
            "midiNote": midi_note,
            "velocity": 100,
            "length": 1,
            "isSlide": False,
            "instrumentSlot": self.active_slot
        }
        self.steps.append(step)
        # Update cache incrementally
        key = (self.active_slot, col)
        if key not in self._steps_cache:
            self._steps_cache[key] = []
        self._steps_cache[key].append(step)
        self._draw_note(step)

    def _remove_step(self, row, col):
        """Remove a note at (row, col) in the ACTIVE slot."""
        midi_note = self._get_midi_for_row(row)
        self.steps = [s for s in self.steps
                      if not (s["instrumentSlot"] == self.active_slot
                              and s["stepIndex"] == col
                              and s["midiNote"] == midi_note)]
        # Incrementally update cache for this key only
        key = (self.active_slot, col)
        if key in self._steps_cache:
            self._steps_cache[key] = [s for s in self._steps_cache[key] if s["midiNote"] != midi_note]
            if not self._steps_cache[key]:
                del self._steps_cache[key]
        # Erase visual
        self.grid_canvas.delete(f"note_{row}_{col}")
        self._redraw_cell_bg(row, col)

    def _redraw_cell_bg(self, row, col):
        """Redraw just the background of a single cell using fixed STEP_W."""
        if row >= len(self.scale_notes):
            return
        midi_note = self.scale_notes[row][0]
        is_root = is_root_note(midi_note, self.root_key)
        x1 = col * STEP_W
        x2 = x1 + STEP_W
        y1 = row * CELL_H
        y2 = y1 + CELL_H

        group = col // 4
        if is_root:
            bg = ROOT_HI
        elif group % 2 == 0:
            bg = BG_GRID
        else:
            bg = BG_ALT

        self.grid_canvas.create_rectangle(
            x1, y1, x2, y2, fill=bg, outline=MUTED,
            tags=(f"cell_{row}_{col}", "cell")
        )

    def _on_bpm_change(self, *_):
        """Validate and update BPM from text entry. Finalized on Enter/FocusOut."""
        try:
            val = float(self.bpm_str_var.get())
            self.bpm = max(30.0, min(300.0, val))
            self.bpm_str_var.set(str(int(self.bpm)))
        except (ValueError, tk.TclError):
            self.bpm_str_var.set(str(int(self.bpm)))

    def _on_tap_tempo(self, *_):
        """Calculate BPM based on rhythmic taps."""
        now = time.time()
        # Reset if too long since last tap (more than 3 seconds)
        if self.tap_times and (now - self.tap_times[-1] > 3.0):
            self.tap_times = []
            
        self.tap_times.append(now)
        self.tap_times = self.tap_times[-8:] # Keep last 8
        
        if len(self.tap_times) >= 2:
            intervals = np.diff(self.tap_times)
            avg_interval = np.mean(intervals)
            if avg_interval > 0:
                bpm = 60.0 / avg_interval
                bpm = float(round(max(30.0, min(300.0, bpm)), 1))
                self.bpm = bpm
                self.bpm_str_var.set(str(int(bpm)))

    def _draw_beat_led(self, active=False):
        """Draw the metronome LED state."""
        self.beat_led.delete("all")
        color = AMBER if active else LED_OFF
        self.beat_led.create_oval(2, 2, 13, 13, fill=color, outline="")

    def _detect_legato(self):
        """Detect adjacent notes on the same pitch and mark as slide, per slot."""
        # Group steps by (instrumentSlot, midiNote)
        by_note = {}
        for s in self.steps:
            key = (s.get("instrumentSlot", 0), s["midiNote"])
            if key not in by_note:
                by_note[key] = []
            by_note[key].append(s)

        for key, note_steps in by_note.items():
            note_steps.sort(key=lambda s: s["stepIndex"])
            for i in range(1, len(note_steps)):
                prev = note_steps[i - 1]
                curr = note_steps[i]
                if curr["stepIndex"] == prev["stepIndex"] + prev.get("length", 1):
                    curr["isSlide"] = True
                else:
                    curr["isSlide"] = False

    # ─────────────────────────────────────────────────────────────────
    # TRANSPORT & CONTROLS
    # ─────────────────────────────────────────────────────────────────

    def _on_slider_change(self, val):
        """BPM slider update."""
        self.bpm = float(val)
        self.bpm_str_var.set(str(int(self.bpm)))

    def _on_master_vol_change(self, val):
        """Global master volume update."""
        self.master_volume = float(val)
        # Update synth
        self.send_ipc({"action": "PARAM_UPDATE", "params": {"master_volume": self.master_volume}})
        # Update drums
        self.beats_engine.master_volume = self.master_volume

    def _on_slot_mix_change(self, _=None):
        """Per-slot mixing for the Piano Roll."""
        self.slot_volumes[self.active_slot] = self.slot_vol_var.get()
        self.slot_pans[self.active_slot] = self.slot_pan_var.get()
        self.slot_reverb[self.active_slot] = self.slot_rev_var.get()
        self.slot_delay[self.active_slot] = self.slot_del_var.get()

    def _on_beats_mix_change(self, _=None):
        """Per-track mixing for the Drum Machine."""
        t = self.beats_tracks[self.beats_active_track]
        t["volume"] = self.beats_vol_var.get()
        t["pan"] = self.beats_pan_var.get()
        self.beats_engine.track_volumes[self.beats_active_track] = t["volume"]
        self.beats_engine.track_pans[self.beats_active_track] = t["pan"]
        
        # Also sync global engine FX from these sliders (shared for all drums)
        self.beats_engine.fx_reverb = self.beats_rev_var.get()
        self.beats_engine.fx_delay = self.beats_del_var.get()
        self._draw_beats_sidebar()

    def _on_step_count_change(self):
        """Deprecated: Use _on_slot_click for per-slot changes."""
        pass

    def _on_mono_toggle(self):
        self.mono_mode = bool(self.mono_var.get())

    def toggle_playback(self):
        self.is_playing = not self.is_playing
        if self.is_playing:
            self.play_btn.config(text="■ STOP", bg="#440000", fg="#ff4444")
            if hasattr(self, 'beats_play_btn'):
                self.beats_play_btn.config(text="■ STOP BEATS", bg="#440000", fg="#ff4444")
            # Reset all slots
            for i in range(self.num_slots):
                self.slot_current_steps[i] = -1
            # Reset beats
            self.beats_current_step = -1
            if hasattr(self, '_beats_render_all_tracks'):
                self._beats_render_all_tracks()
                
            # MIDI Start
            if self.midi_out:
                try: self.midi_out.send(mido.Message('start'))
                except: pass

            threading.Thread(target=self._clock_engine, daemon=True).start()
        else:
            self.play_btn.config(text="▶ PLAY", bg="#004400", fg="#00ff00")
            if hasattr(self, 'beats_play_btn'):
                self.beats_play_btn.config(text="▶ PLAY BEATS", bg="#004400", fg="#00ff00")
            self.send_ipc({"action": "RELEASE"})
            if hasattr(self, 'beats_engine'):
                self.beats_engine.stop_all()

            # MIDI Stop
            if self.midi_out:
                try: self.midi_out.send(mido.Message('stop'))
                except: pass
            
            # Reset visual LEDS
            self._draw_led_strip()
            self._draw_grid()
            self._draw_slot_sidebar()
            if hasattr(self, '_draw_beats_leds'):
                self._draw_beats_leds()
                self._draw_beats_grid()

    # ─────────────────────────────────────────────────────────────────
    # CLOCK ENGINE
    # ─────────────────────────────────────────────────────────────────

    def _clock_engine(self):
        """High precision perf_counter loop — zero-lag multi-track sequencing."""
        while self.is_playing:
            start_time = time.perf_counter()

            # Advance all slots independently
            next_step_map = {}
            for slot_idx in range(self.num_slots):
                self.slot_current_steps[slot_idx] = (self.slot_current_steps[slot_idx] + 1) % self.slot_step_counts[slot_idx]
                next_step_map[slot_idx] = self.slot_current_steps[slot_idx]

            # Collect active notes across ALL slots for this tick — O(1) cache lookup
            any_solo = any(self.slot_solos.values())
            active_notes = []
            for slot_idx, step_idx in next_step_map.items():
                if any_solo:
                    if not self.slot_solos[slot_idx]: continue
                elif self.slot_mutes[slot_idx]:
                    continue

                for s in self._steps_cache.get((slot_idx, step_idx), []):
                    active_notes.append(s)

            # Release previous notes (Monophonic IPC optimization)
            if self.midi_out and self.last_midi_note is not None:
                continuing = any(s.get("isSlide", False) and s["midiNote"] == self.last_midi_note for s in active_notes)
                if not continuing:
                    self.midi_out.send(mido.Message('note_off', note=self.last_midi_note))
                    self.send_ipc({"action": "RELEASE"})
                    self.last_midi_note = None

            # Trigger new notes
            for note in active_notes:
                slot = note.get("instrumentSlot", 0)
                freq = midi_to_freq(note["midiNote"])
                # Apply per-slot Gain and Pan (with safety for reduced slot count)
                slot_vol = self.slot_volumes.get(slot, 0.8)
                slot_pan = self.slot_pans.get(slot, 0.0)
                slot_rev = self.slot_reverb.get(slot, 0.0)
                slot_del = self.slot_delay.get(slot, 0.0)
                
                vel = (note["velocity"] / 127.0) * slot_vol
                legato = note.get("isSlide", False)

                self.send_ipc({
                    "action": "TRIGGER",
                    "freq": freq,
                    "vel": vel,
                    "pan": slot_pan,
                    "reverb_wet": slot_rev,
                    "delay_wet": slot_del,
                    "legato": legato
                })

                if self.midi_out:
                    if not legato:
                        midi_note = note["midiNote"]
                        self.midi_out.send(mido.Message(
                            'note_on', note=midi_note,
                            velocity=note["velocity"]
                        ))
                        self.last_midi_note = midi_note

            # ── MIDI CLOCK (24 PPQN) ─────────────────────────────────
            # Since our engine runs at 16th note resolution, we send
            # 6 clocks per step (6 * 4 = 24).
            if self.midi_out:
                try:
                    for _ in range(6):
                        self.midi_out.send(mido.Message('clock'))
                except: pass

            # ── Visual Metronome ─────────────────────────────────────
            # Flash on every Quarter Note (every 4 steps of a 16th-note grid)
            master_step = next_step_map.get(0, 0) # Use Slot 0 as reference
            if master_step % 4 == 0:
                self._draw_beat_led(True)
                self.master.after(50, lambda: self._draw_beat_led(False))

            # Release if gate is empty this tick
            if not active_notes and self.last_midi_note is not None:
                if self.midi_out:
                    self.midi_out.send(mido.Message('note_off', note=self.last_midi_note))
                self.send_ipc({"action": "RELEASE"})
                self.last_midi_note = None

            # --- BEATS LOGIC ---
            if hasattr(self, 'beats_time_sig'):
                num_beats_steps = TIME_SIGS[self.beats_time_sig]["steps"]
                self.beats_current_step = (self.beats_current_step + 1) % num_beats_steps
                b_step = self.beats_current_step
                any_beats_solo = any(t.get("solo") for t in self.beats_tracks)
                for track_idx in range(BEATS_NUM_TRACKS):
                    t = self.beats_tracks[track_idx]
                    if t["pattern"][b_step]:
                        if any_beats_solo:
                            if not t.get("solo"): continue
                        elif t["mute"]:
                            continue
                        self.beats_engine.trigger_track(track_idx)
                
                # GUI update for beats
                self.master.after(0, self._on_beats_step_tick, b_step)

            # GUI update for piano roll
            self.master.after(0, self._on_step_tick, next_step_map)

            # Burn clock
            sec_per_beat = 60.0 / self.bpm
            sec_per_16th = sec_per_beat / 4.0
            while time.perf_counter() - start_time < sec_per_16th:
                if not self.is_playing: break
                time.sleep(0.001)

    def _on_step_tick(self, step_map):
        """Called on the main thread — update LED and playhead only (no full sidebar redraw)."""
        active_step = step_map.get(self.active_slot, 0)

        # Fast LED update (toggles only 2 canvas items)
        self._update_led(active_step)

        # Move playhead
        self.grid_canvas.delete("playhead")
        self._draw_playhead(active_step)

        # Flash active notes at current step for visual feedback
        self.grid_canvas.delete("active_trigger")
        for s in self._steps_cache.get((self.active_slot, active_step), []):
            row = self._get_row_for_midi(s["midiNote"])
            if row >= 0:
                x1 = active_step * STEP_W + 1
                y1 = row * CELL_H + 1
                self.grid_canvas.create_rectangle(
                    x1, y1, x1 + STEP_W - 2, y1 + CELL_H - 2,
                    fill=RED_SIGNAL, outline="",
                    tags=(f"note_{row}_{active_step}", "note", "active_trigger")
                )

    # ─────────────────────────────────────────────────────────────────
    # IPC (Unified Pipe / UDP)
    # ─────────────────────────────────────────────────────────────────

    def send_ipc(self, msg):
        """Unified sender for Pipe (internal) or UDP (standalone) IPC."""
        try:
            if self.tx_pipe:
                self.tx_pipe.send(msg)
            else:
                data = json.dumps(msg).encode('utf-8')
                self.udp_sock.sendto(data, self.udp_addr)
        except Exception as e:
            print(f"IPC Error: {e}")

    # ─────────────────────────────────────────────────────────────────
    # BEATS TAB — DM1-STYLE DRUM MACHINE
    # ─────────────────────────────────────────────────────────────────

    def _build_beats_tab(self):
        """Build the full BEATS drum machine tab."""
        beats_frame = tk.Frame(self.tab_container, bg=BG_DARK)
        self.tab_frames["BEATS"] = beats_frame

        # ── Top bar: Time signature + transport ──────────────────────
        beats_top = tk.Frame(beats_frame, bg="#111111",
                             highlightthickness=1, highlightbackground=PURPLE)
        beats_top.pack(fill=tk.X, pady=(0, 5))

        tk.Label(beats_top, text="TIME SIG:", font=FONT,
                 bg="#111111", fg=GOLD).pack(side=tk.LEFT, padx=(10, 2))
        self.beats_sig_var = tk.StringVar(value=self.beats_time_sig)
        sig_menu = tk.OptionMenu(beats_top, self.beats_sig_var,
                                 *TIME_SIGS.keys(),
                                 command=self._on_beats_time_sig_change)
        sig_menu.config(bg=PURPLE, fg=GOLD, font=FONT, highlightthickness=0,
                        activebackground=AMBER, activeforeground=BG_DARK)
        sig_menu["menu"].config(bg=BG_DARK, fg=GOLD, font=FONT_SM)
        sig_menu.pack(side=tk.LEFT, padx=2)

        self.beats_play_btn = tk.Button(
            beats_top, text="▶ PLAY BEATS", font=FONT, width=14,
            bg="#004400", fg="#00ff00",
            activebackground=AMBER, activeforeground=BG_DARK,
            relief=tk.FLAT, command=self.toggle_playback
        )
        self.beats_play_btn.pack(side=tk.LEFT, padx=(20, 5), pady=6)

        # Save / Open for Beats
        tk.Button(
            beats_top, text="SAVE", font=FONT, width=6,
            bg=PURPLE, fg=GOLD, activebackground=AMBER,
            activeforeground=BG_DARK, relief=tk.FLAT,
            command=self._save_project
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            beats_top, text="OPEN", font=FONT, width=6,
            bg=PURPLE, fg=GOLD, activebackground=AMBER,
            activeforeground=BG_DARK, relief=tk.FLAT,
            command=self._load_project
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            beats_top, text="CLEAR", font=FONT, width=8,
            bg="#440000", fg=GOLD,
            activebackground=RED_SIGNAL, activeforeground=BG_DARK,
            relief=tk.FLAT, command=self.clear_beats_grid
        ).pack(side=tk.RIGHT, padx=10, pady=6)

        # ── LED strip area (above grid) ──────────────────────────────
        # LED lives inside a frame so it can expand with the window
        led_row = tk.Frame(beats_frame, bg=BG_DARK)
        led_row.pack(fill=tk.X, pady=(10, 2))
        # Spacer matching the sidebar width
        tk.Frame(led_row, width=BEATS_LABEL_W, bg=BG_DARK).pack(side=tk.LEFT)
        self.beats_led_canvas = tk.Canvas(
            led_row, height=20,
            bg=BG_DARK, highlightthickness=0
        )
        self.beats_led_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # ── Grid area: sidebar + scrollable grid ─────────────────────
        grid_area = tk.Frame(beats_frame, bg=BG_DARK)
        grid_area.pack(fill=tk.BOTH, expand=True)

        self.beats_sidebar = tk.Canvas(
            grid_area, width=BEATS_LABEL_W, bg=BG_DARK,
            highlightthickness=0
        )
        self.beats_sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.beats_sidebar.bind("<Button-1>", self._on_beats_track_click)

        # Wrap canvas + scrollbar in an inner frame so scrollbar is
        # always positioned directly below the canvas (like ROLL tab)
        beats_grid_outer = tk.Frame(grid_area, bg=BG_DARK)
        beats_grid_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.beats_grid_canvas = tk.Canvas(
            beats_grid_outer,
            height=BEATS_NUM_TRACKS * PAD_SIZE,
            bg="#000000", highlightthickness=1, highlightbackground=PURPLE
        )
        self.beats_grid_canvas.pack(side=tk.TOP, fill=tk.X, expand=False)
        self.beats_grid_canvas.bind("<Button-1>", self._on_beats_grid_click)
        self.beats_grid_canvas.bind("<B1-Motion>", self._on_beats_grid_drag)
        self.beats_grid_canvas.bind("<ButtonRelease-1>", self._on_beats_grid_release)

        # Horizontal Scrollbar lives inside beats_grid_outer
        self.beats_scroll_x = tk.Scrollbar(
            beats_grid_outer, orient=tk.HORIZONTAL,
            command=self._on_beats_scroll_x,
            bg=BG_DARK, troughcolor=BG_DARK
        )
        self.beats_scroll_x.pack(side=tk.TOP, fill=tk.X)
        self.beats_grid_canvas.config(xscrollcommand=self._sync_beats_scroll_x)

        self._beats_paint_mode = None
        self._beats_last_cell = None

        # ── Config panel (bottom) ────────────────────────────────────
        config_outer = tk.Frame(beats_frame, bg="#111111",
                                highlightthickness=1, highlightbackground=PURPLE)
        config_outer.pack(fill=tk.X, pady=(5, 0))

        self.beats_config_label = tk.Label(
            config_outer, text="TRACK CONFIG: KICK", font=FONT,
            bg="#111111", fg=AMBER
        )
        self.beats_config_label.pack(anchor="w", padx=10, pady=(5, 2))

        # Source row
        src_row = tk.Frame(config_outer, bg="#111111")
        src_row.pack(fill=tk.X, padx=10, pady=2)

        tk.Label(src_row, text="SOURCE:", font=FONT,
                 bg="#111111", fg=GOLD).pack(side=tk.LEFT)

        self.beats_source_var = tk.StringVar(value="synth")
        tk.Radiobutton(
            src_row, text="SAMPLE", variable=self.beats_source_var,
            value="sample", command=self._on_beats_source_change,
            indicatoron=0, font=FONT,
            bg=TAB_INACTIVE, fg=GOLD, selectcolor=PURPLE,
            activebackground=AMBER, activeforeground=BG_DARK, width=8
        ).pack(side=tk.LEFT, padx=(10, 2))

        tk.Radiobutton(
            src_row, text="SYNTH", variable=self.beats_source_var,
            value="synth", command=self._on_beats_source_change,
            indicatoron=0, font=FONT,
            bg=TAB_INACTIVE, fg=GOLD, selectcolor=PURPLE,
            activebackground=AMBER, activeforeground=BG_DARK, width=8
        ).pack(side=tk.LEFT, padx=2)

        self.beats_sample_frame = tk.Frame(src_row, bg="#111111")
        self.beats_sample_path_var = tk.StringVar(value="No file loaded")
        tk.Label(self.beats_sample_frame,
                 textvariable=self.beats_sample_path_var,
                 font=FONT_SM, bg="#111111", fg=MUTED, width=35,
                 anchor="w").pack(side=tk.LEFT)
        tk.Button(
            self.beats_sample_frame, text="BROWSE", font=FONT_SM,
            bg=PURPLE, fg=GOLD, activebackground=AMBER,
            activeforeground=BG_DARK,
            command=self._on_beats_browse_sample, relief=tk.FLAT
        ).pack(side=tk.LEFT, padx=5)

        # Mix Row
        beats_mix = tk.Frame(config_outer, bg="#111111")
        beats_mix.pack(fill=tk.X, padx=10, pady=(5, 2))

        tk.Label(beats_mix, text="GAIN:", font=FONT_SM, bg="#111111", fg=GOLD).pack(side=tk.LEFT)
        self.beats_vol_var = tk.DoubleVar(value=0.8)
        SnapSlider(beats_mix, self.beats_vol_var, 0.0, 1.2, self._on_beats_mix_change).pack(side=tk.LEFT, padx=5)

        tk.Label(beats_mix, text="PAN:", font=FONT_SM, bg="#111111", fg=GOLD).pack(side=tk.LEFT, padx=(15, 0))
        self.beats_pan_var = tk.DoubleVar(value=0.0)
        SnapSlider(beats_mix, self.beats_pan_var, -1.0, 1.0, self._on_beats_mix_change).pack(side=tk.LEFT, padx=5)

        self.beats_mute_var = tk.IntVar(value=0)
        tk.Checkbutton(
            beats_mix, text="MUTE", variable=self.beats_mute_var,
            indicatoron=0, font=FONT, width=6,
            bg=TAB_INACTIVE, fg=GOLD, selectcolor=RED_SIGNAL,
            activebackground=AMBER, activeforeground=BG_DARK,
            command=self._on_beats_mute_toggle
        ).pack(side=tk.LEFT, padx=(20, 5))

        self.beats_solo_var = tk.IntVar(value=0)
        tk.Checkbutton(
            beats_mix, text="SOLO", variable=self.beats_solo_var,
            indicatoron=0, font=FONT, width=6,
            bg=TAB_INACTIVE, fg=GOLD, selectcolor=AMBER,
            activebackground=AMBER, activeforeground=BG_DARK,
            command=self._on_beats_solo_toggle
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            beats_mix, text="▶ PREVIEW", font=FONT, width=10,
            bg=PURPLE, fg=GOLD,
            activebackground=AMBER, activeforeground=BG_DARK,
            relief=tk.FLAT, command=self._on_beats_preview
        ).pack(side=tk.LEFT, padx=5)

        # Beats FX Row
        beats_fx = tk.Frame(config_outer, bg="#111111")
        beats_fx.pack(fill=tk.X, padx=10, pady=(0, 10))

        tk.Label(beats_fx, text="REVERB:", font=FONT_SM, bg="#111111", fg=GOLD).pack(side=tk.LEFT)
        self.beats_rev_var = tk.DoubleVar(value=0.0)
        SnapSlider(beats_fx, self.beats_rev_var, 0.0, 1.0, self._on_beats_mix_change).pack(side=tk.LEFT, padx=5)

        tk.Label(beats_fx, text="DELAY:", font=FONT_SM, bg="#111111", fg=GOLD).pack(side=tk.LEFT, padx=(20, 0))
        self.beats_del_var = tk.DoubleVar(value=0.0)
        SnapSlider(beats_fx, self.beats_del_var, 0.0, 1.0, self._on_beats_mix_change).pack(side=tk.LEFT, padx=5)

        # Beats Copy/Paste Row
        bcp_row = tk.Frame(config_outer, bg="#111111")
        bcp_row.pack(fill=tk.X, padx=10, pady=(0, 5))
        
        tk.Button(bcp_row, text="COPY TRACK", font=FONT_SM, bg=TAB_INACTIVE, fg=GOLD,
                  command=self._copy_beats_track, relief=tk.FLAT, width=12).pack(side=tk.LEFT)
        tk.Button(bcp_row, text="PASTE TRACK", font=FONT_SM, bg=TAB_INACTIVE, fg=GOLD,
                  command=self._paste_beats_track, relief=tk.FLAT, width=12).pack(side=tk.LEFT, padx=5)

        # Synth controls frame
        self.beats_synth_frame = tk.Frame(src_row, bg="#111111")
        tk.Label(self.beats_synth_frame, text="PRESET:", font=FONT_SM,
                 bg="#111111", fg=GOLD).pack(side=tk.LEFT)
        self.beats_preset_var = tk.StringVar(value="Init")
        preset_menu = tk.OptionMenu(self.beats_synth_frame,
                                     self.beats_preset_var,
                                     *list(FACTORY_PRESETS.keys()),
                                     command=self._on_beats_preset_change)
        preset_menu.config(bg=PURPLE, fg=GOLD, font=FONT_SM,
                           highlightthickness=0,
                           activebackground=AMBER, activeforeground=BG_DARK)
        preset_menu["menu"].config(bg=BG_DARK, fg=GOLD, font=FONT_SM)
        preset_menu.pack(side=tk.LEFT, padx=2)

        tk.Label(self.beats_synth_frame, text="NOTE:", font=FONT_SM,
                 bg="#111111", fg=GOLD).pack(side=tk.LEFT, padx=(10, 2))
        note_names = [n[1] for n in self._beats_note_list]
        self.beats_note_var = tk.StringVar(value="C2")
        note_menu = tk.OptionMenu(self.beats_synth_frame,
                                   self.beats_note_var, *note_names,
                                   command=self._on_beats_note_change)
        note_menu.config(bg=PURPLE, fg=GOLD, font=FONT_SM,
                         highlightthickness=0,
                         activebackground=AMBER, activeforeground=BG_DARK)
        note_menu["menu"].config(bg=BG_DARK, fg=GOLD, font=FONT_SM)
        note_menu.pack(side=tk.LEFT, padx=2)

        # Show correct source panel
        self._on_beats_source_change()

    # ── BEATS: Drawing ───────────────────────────────────────────────

    def _draw_beats_grid(self):
        """Draw the 8-track step grid for the current time signature."""
        self.beats_grid_canvas.delete("all")
        sig = TIME_SIGS[self.beats_time_sig]
        num_steps = sig["steps"]
        group = sig["group"]
        grid_w = num_steps * PAD_SIZE
        grid_h = BEATS_NUM_TRACKS * PAD_SIZE
        self.beats_grid_canvas.config(scrollregion=(0, 0, grid_w, grid_h))

        for track in range(BEATS_NUM_TRACKS):
            y1 = track * PAD_SIZE
            y2 = y1 + PAD_SIZE
            is_active = (track == self.beats_active_track)

            for step in range(num_steps):
                x1 = step * PAD_SIZE
                x2 = x1 + PAD_SIZE
                g = step // group
                if is_active:
                    bg = "#2a2a00" if g % 2 == 0 else "#222200"
                else:
                    bg = BG_GRID if g % 2 == 0 else BG_ALT

                self.beats_grid_canvas.create_rectangle(
                    x1, y1, x2, y2, fill=bg, outline=MUTED,
                    tags=(f"beat_{track}_{step}", "beat_cell")
                )

                # Draw active pad
                if self.beats_tracks[track]["pattern"][step]:
                    pad_color = RED_SIGNAL if self.beats_tracks[track]["mute"] else AMBER
                    self.beats_grid_canvas.create_rectangle(
                        x1 + 3, y1 + 3, x2 - 3, y2 - 3,
                        fill=pad_color, outline="",
                        tags=(f"pad_{track}_{step}", "pad")
                    )

        # Beat group lines (vertical)
        for step in range(num_steps + 1):
            x = step * PAD_SIZE
            if step % group == 0:
                self.beats_grid_canvas.create_line(
                    x, 0, x, grid_h, fill=PURPLE, width=2, tags="gridline"
                )

        # Track dividers (horizontal)
        for track in range(BEATS_NUM_TRACKS + 1):
            y = track * PAD_SIZE
            self.beats_grid_canvas.create_line(
                0, y, num_steps * PAD_SIZE, y, fill=MUTED, tags="gridline"
            )

        # Draw playhead if active
        if self.is_playing and 0 <= self.beats_current_step < num_steps:
            self._draw_beats_playhead(self.beats_current_step)

    def _draw_beats_playhead(self, step):
        """Draw the playhead column highlight."""
        self.beats_grid_canvas.delete("beats_playhead")
        x1 = step * PAD_SIZE
        x2 = x1 + PAD_SIZE
        grid_h = BEATS_NUM_TRACKS * PAD_SIZE
        self.beats_grid_canvas.create_rectangle(
            x1, 0, x2, grid_h,
            fill="", outline=RED_SIGNAL, width=2, tags="beats_playhead"
        )

    def _draw_beats_leds(self):
        """Draw the LED strip for the beats grid."""
        sig = TIME_SIGS[self.beats_time_sig]
        num_steps = sig["steps"]
        self.beats_led_canvas.config(scrollregion=(0, 0, num_steps * PAD_SIZE, 20))
        self.beats_led_canvas.delete("all")
        num_steps = sig["steps"]
        led_r = 5
        for i in range(num_steps):
            cx = i * PAD_SIZE + PAD_SIZE / 2
            cy = 10
            color = RED_SIGNAL if i == self.beats_current_step else LED_OFF
            self.beats_led_canvas.create_oval(
                cx - led_r, cy - led_r, cx + led_r, cy + led_r,
                fill=color, outline="", tags=f"beats_led_{i}"
            )

    def _draw_beats_sidebar(self):
        """Draw track pads with names, sample indicators, and mute/solo status."""
        self.beats_sidebar.delete("all")
        w = self.beats_sidebar.winfo_width()
        if w < 10: w = BEATS_LABEL_W
        
        for i, t in enumerate(self.beats_tracks):
            y1 = i * PAD_SIZE
            y2 = y1 + PAD_SIZE
            
            # Highlight active track
            bg = "#333333" if i == self.beats_active_track else BG_DARK
            self.beats_sidebar.create_rectangle(0, y1, w, y2, fill=bg, outline=MUTED)
            
            # Status Indicators (Mute/Solo)
            if t.get("solo"):
                self.beats_sidebar.create_rectangle(2, y1+2, 6, y2-2, fill=AMBER, outline="")
            elif t["mute"]:
                self.beats_sidebar.create_rectangle(2, y1+2, 6, y2-2, fill=RED_SIGNAL, outline="")

            # Text: Track Name + Sample
            label = t["name"]
            if t["source_type"] == "sample" and t["sample_path"]:
                fname = os.path.basename(t["sample_path"])
                label = f"{t['name']}: {fname}"
            
            fg = GOLD
            if i == self.beats_active_track: fg = AMBER
            
            self.beats_sidebar.create_text(
                12, y1 + PAD_SIZE/2, text=label, anchor="w",
                font=FONT_SM, fill=fg
            )

            # Mute Button
            mute_bg = RED_SIGNAL if t["mute"] else "#333333"
            self.beats_sidebar.create_rectangle(w-45, y1+12, w-28, y2-12, fill=mute_bg, outline=MUTED, tags=f"bmute_{i}")
            self.beats_sidebar.create_text(w-36, y1 + PAD_SIZE/2, text="M", fill=GOLD, font=FONT_SM, tags=f"bmute_{i}")

            # Solo Button
            solo_bg = AMBER if t.get("solo") else "#333333"
            self.beats_sidebar.create_rectangle(w-25, y1+12, w-8, y2-12, fill=solo_bg, outline=MUTED, tags=f"bsolo_{i}")
            self.beats_sidebar.create_text(w-16, y1 + PAD_SIZE/2, text="S", fill=GOLD, font=FONT_SM, tags=f"bsolo_{i}")

    # ── BEATS: Interaction ───────────────────────────────────────────

    def _beats_grid_to_cell(self, event):
        """Convert canvas event to (track, step) or None."""
        cx = self.beats_grid_canvas.canvasx(event.x)
        cy = self.beats_grid_canvas.canvasy(event.y)
        step = int(cx // PAD_SIZE)
        track = int(cy // PAD_SIZE)
        num_steps = TIME_SIGS[self.beats_time_sig]["steps"]
        if 0 <= step < num_steps and 0 <= track < BEATS_NUM_TRACKS:
            return (track, step)
        return None

    def _on_beats_grid_click(self, event):
        """Handle initial click on the beats grid."""
        cell = self._beats_grid_to_cell(event)
        if cell is None:
            return
        track, step = cell
        pat = self.beats_tracks[track]["pattern"]
        if pat[step]:
            self._beats_paint_mode = "erase"
            pat[step] = 0
        else:
            self._beats_paint_mode = "paint"
            pat[step] = 1
        self._beats_last_cell = cell
        self._draw_beats_grid()

    def _on_beats_grid_drag(self, event):
        """Handle drag painting on the beats grid."""
        cell = self._beats_grid_to_cell(event)
        if cell is None or cell == self._beats_last_cell:
            return
        track, step = cell
        pat = self.beats_tracks[track]["pattern"]
        if self._beats_paint_mode == "paint":
            pat[step] = 1
        elif self._beats_paint_mode == "erase":
            pat[step] = 0
        self._beats_last_cell = cell
        self._draw_beats_grid()

    def _on_beats_grid_release(self, event):
        """End paint/erase stroke."""
        self._beats_paint_mode = None
        self._beats_last_cell = None

    def _on_beats_track_click(self, event):
        """Handle clicking a track in the sidebar to select it."""
        track = int(event.y // PAD_SIZE)
        if 0 <= track < BEATS_NUM_TRACKS:
            w = self.beats_sidebar.winfo_width()
            if w < 10: w = BEATS_LABEL_W
            
            if w - 45 <= event.x <= w - 28:
                t["mute"] = not t["mute"]
                self.beats_engine.track_mutes[track] = t["mute"]
            elif w - 25 <= event.x <= w - 8:
                t["solo"] = not t.get("solo", False)
                self.beats_engine.track_solos[track] = t["solo"]
            else:
                self.beats_active_track = track
                
            self._draw_beats_sidebar()
            self._draw_beats_grid()
            self._update_beats_config_panel()

    # ── BEATS: Config Panel ──────────────────────────────────────────

    def _update_beats_config_panel(self):
        """Update the config panel to reflect the active track's settings."""
        t = self.beats_tracks[self.beats_active_track]
        self.beats_config_label.config(text=f"TRACK CONFIG: {t['name']}")
        self.beats_source_var.set(t["source_type"])
        self.beats_vol_var.set(t["volume"])
        self.beats_pan_var.set(t.get("pan", 0.0))
        self.beats_rev_var.set(self.beats_engine.fx_reverb)
        self.beats_del_var.set(self.beats_engine.fx_delay)
        self.beats_mute_var.set(1 if t["mute"] else 0)
        self.beats_solo_var.set(1 if t.get("solo", False) else 0)

        if t["source_type"] == "sample":
            path = t["sample_path"]
            self.beats_sample_path_var.set(
                os.path.basename(path) if path else "No file loaded"
            )
        else:
            self.beats_preset_var.set(t["preset_name"])
            # Find note name from midi note
            for midi, name in self._beats_note_list:
                if midi == t["midi_note"]:
                    self.beats_note_var.set(name)
                    break

        self._on_beats_source_change()

    def _on_beats_source_change(self):
        """Show/hide sample vs synth controls based on source selection."""
        src = self.beats_source_var.get()
        self.beats_tracks[self.beats_active_track]["source_type"] = src

        if src == "sample":
            self.beats_synth_frame.pack_forget()
            self.beats_sample_frame.pack(side=tk.LEFT, padx=(15, 0))
        else:
            self.beats_sample_frame.pack_forget()
            self.beats_synth_frame.pack(side=tk.LEFT, padx=(15, 0))

        self._draw_beats_sidebar()


    def _on_beats_solo_toggle(self):
        """Toggle solo state for current track."""
        t = self.beats_tracks[self.beats_active_track]
        t["solo"] = bool(self.beats_solo_var.get())
        self.beats_engine.track_solos[self.beats_active_track] = t["solo"]
        self._draw_beats_sidebar()

    # ── COPY / PASTE LOGIC ───────────────────────────────────────────

    def _copy_slot(self):
        """Copy all notes from the current ROLL slot."""
        slot_notes = [dict(s) for s in self.steps if s["instrumentSlot"] == self.active_slot]
        self.clipboard = {"type": "ROLL", "data": slot_notes}

    def _paste_slot(self):
        """Paste notes into the current ROLL slot."""
        if not self.clipboard or self.clipboard["type"] != "ROLL":
            return
        
        # Remove existing notes in target slot
        self.steps = [s for s in self.steps if s["instrumentSlot"] != self.active_slot]
        
        # Add new notes with updated slot index
        for s in self.clipboard["data"]:
            new_s = dict(s)
            new_s["instrumentSlot"] = self.active_slot
            self.steps.append(new_s)
            
        self._rebuild_steps_cache()
        self._draw_grid()

    def _copy_beats_track(self):
        """Copy the pattern from the current BEATS track."""
        t = self.beats_tracks[self.beats_active_track]
        self.clipboard = {"type": "BEATS", "data": list(t["pattern"])}

    def _paste_beats_track(self):
        """Paste pattern into the current BEATS track."""
        if not self.clipboard or self.clipboard["type"] != "BEATS":
            return
        
        t = self.beats_tracks[self.beats_active_track]
        t["pattern"] = list(self.clipboard["data"])
        self._draw_beats_grid()

    # ─────────────────────────────────────────────────────────────────

    def _save_project(self):
        """Save the entire Asherah project (Roll & Beats) to a JSON file."""
        path = filedialog.asksaveasfilename(
            title="Save Asherah Project",
            defaultextension=".json",
            filetypes=[("Asherah Project", "*.json")]
        )
        if not path: return
        
        data = {
            "bpm": self.bpm,
            "root_key": self.root_key,
            "scale_name": self.scale_name,
            "mono_mode": self.mono_mode,
            "roll": {
                "steps": self.steps,
                "slot_step_counts": self.slot_step_counts
            },
            "beats": {
                "time_sig": self.beats_time_sig,
                "tracks": self.beats_tracks
            }
        }
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=4)
            messagebox.showinfo("Success", "Project saved successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

    def _load_project(self):
        """Load an Asherah project from a JSON file."""
        path = filedialog.askopenfilename(
            title="Open Asherah Project",
            filetypes=[("Asherah Project", "*.json")]
        )
        if not path: return
        
        try:
            with open(path, "r") as f:
                data = json.load(f)
            
            # BPM
            self.bpm = data.get("bpm", 120)
            self.bpm_var.set(self.bpm)
            self.bpm_str_var.set(str(int(self.bpm)))
            
            # Root / Scale
            self.root_key = data.get("root_key", "C")
            self.scale_name = data.get("scale_name", "Minor")
            self.root_var.set(self.root_key)
            self.scale_var.set(self.scale_name)
            
            # Mono
            self.mono_mode = data.get("mono_mode", False)
            self.mono_var.set(1 if self.mono_mode else 0)
            
            # Roll
            roll = data.get("roll", {})
            self.steps = roll.get("steps", [])
            counts = roll.get("slot_step_counts", {})
            # JSON keys are strings, convert back to int
            self.slot_step_counts = {int(k): v for k, v in counts.items()}
            
            # Beats
            beats = data.get("beats", {})
            self.beats_time_sig = beats.get("time_sig", "4/4")
            self.beats_sig_var.set(self.beats_time_sig)
            self.beats_tracks = beats.get("tracks", self.beats_tracks)
            
            # Refresh all
            self._rebuild_scale() 
            
            # Reload samples for beats
            for i, track in enumerate(self.beats_tracks):
                if track["source_type"] == "sample" and track["sample_path"]:
                    if os.path.exists(track["sample_path"]):
                        self._beats_render_track(i)
                else:
                    # Rerender synth tracks
                    self._beats_render_track(i)
            
            self._draw_grid()
            self._draw_led_strip()
            self._draw_slot_sidebar()
            self._draw_beats_sidebar()
            self._draw_beats_grid()
            
            messagebox.showinfo("Success", "Project loaded successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load: {e}")

    def _set_default_sample_dir(self, directory):
        """Set the permanent default samples location."""
        self.config["last_sample_dir"] = directory
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump(self.config, f)
            self.last_sample_dir = directory
            messagebox.showinfo("Config", f"Default sample directory set to:\n{directory}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config: {e}")

    def _on_beats_browse_sample(self):
        """Open a custom-built file browser dialog to avoid system dialog rendering bugs."""
        self._open_custom_file_browser(self.last_sample_dir)

    def _open_custom_file_browser(self, start_dir):
        """Fully custom file browser: Toplevel + Listbox, no system dialog."""
        current_dir = [os.path.abspath(start_dir)]

        dlg = tk.Toplevel(self.master)
        dlg.title("Load Sample")
        dlg.configure(bg=BG_DARK)
        dlg.geometry("680x480")
        dlg.transient(self.master)
        dlg.grab_set()

        # ── Directory bar ─────────────────────────────────────────────
        dir_frame = tk.Frame(dlg, bg="#111111")
        dir_frame.pack(fill=tk.X, padx=8, pady=(8, 2))
        tk.Label(dir_frame, text="DIR:", font=FONT_SM, bg="#111111", fg=GOLD).pack(side=tk.LEFT)
        dir_var = tk.StringVar(value=current_dir[0])
        dir_label = tk.Label(dir_frame, textvariable=dir_var, font=FONT_SM,
                             bg="#111111", fg=AMBER, anchor="w")
        dir_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        up_btn = tk.Button(dir_frame, text="▲ UP", font=FONT_SM, width=6,
                           bg=PURPLE, fg=GOLD, relief=tk.FLAT,
                           activebackground=AMBER, activeforeground=BG_DARK)
        up_btn.pack(side=tk.RIGHT, padx=4)

        # ── File list ──────────────────────────────────────────────────
        list_frame = tk.Frame(dlg, bg=BG_DARK)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        scrollbar = tk.Scrollbar(list_frame, bg=BG_DARK, troughcolor="#111111")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        listbox = tk.Listbox(
            list_frame, yscrollcommand=scrollbar.set,
            font=FONT, bg="#111111", fg=GOLD, selectbackground=PURPLE,
            selectforeground=GOLD, activestyle="none", borderwidth=0,
            highlightthickness=1, highlightbackground=PURPLE
        )
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)

        # ── Selected file display ──────────────────────────────────────
        sel_frame = tk.Frame(dlg, bg="#111111")
        sel_frame.pack(fill=tk.X, padx=8, pady=(2, 4))
        tk.Label(sel_frame, text="FILE:", font=FONT_SM, bg="#111111", fg=GOLD).pack(side=tk.LEFT)
        sel_var = tk.StringVar(value="")
        sel_entry = tk.Entry(sel_frame, textvariable=sel_var, font=FONT_SM,
                             bg=BG_DARK, fg=GOLD, insertbackground=GOLD,
                             highlightthickness=1, highlightbackground=PURPLE)
        sel_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        # ── Buttons ───────────────────────────────────────────────────
        btn_frame = tk.Frame(dlg, bg=BG_DARK)
        btn_frame.pack(fill=tk.X, padx=8, pady=(0, 8))
        open_btn = tk.Button(btn_frame, text="OPEN", font=FONT, width=10,
                             bg=PURPLE, fg=GOLD, relief=tk.FLAT,
                             activebackground=AMBER, activeforeground=BG_DARK)
        open_btn.pack(side=tk.RIGHT, padx=4)
        
        tk.Button(btn_frame, text="SET AS DEFAULT", font=FONT_SM, width=15,
                  bg="#444444", fg=GOLD, relief=tk.FLAT,
                  activebackground=AMBER, activeforeground=BG_DARK,
                  command=lambda: self._set_default_sample_dir(current_dir[0])).pack(side=tk.LEFT, padx=4)

        tk.Button(btn_frame, text="CANCEL", font=FONT, width=10,
                  bg=TAB_INACTIVE, fg=GOLD, relief=tk.FLAT,
                  activebackground=RED_SIGNAL, activeforeground=BG_DARK,
                  command=dlg.destroy).pack(side=tk.RIGHT, padx=4)

        # ── Populate helper ──────────────────────────────────────────
        def populate(path):
            listbox.delete(0, tk.END)
            current_dir[0] = path
            dir_var.set(path)
            try:
                entries = os.listdir(path)
            except PermissionError:
                entries = []
            dirs  = sorted([e for e in entries if os.path.isdir(os.path.join(path, e))], key=str.lower)
            files = sorted([e for e in entries if e.lower().endswith(".wav")], key=str.lower)
            for d in dirs:
                listbox.insert(tk.END, f"📁 {d}")
            for f in files:
                listbox.insert(tk.END, f"  {f}")

        populate(current_dir[0])

        def on_select(event):
            sel = listbox.curselection()
            if not sel:
                return
            raw = listbox.get(sel[0]).strip()
            # Strip folder icon prefix
            name = raw.lstrip("📁").strip()
            full = os.path.join(current_dir[0], name)
            if os.path.isdir(full):
                populate(full)
                sel_var.set("")
            else:
                sel_var.set(name)

        listbox.bind("<Double-1>", on_select)
        listbox.bind("<<ListboxSelect>>", lambda e: (
            lambda s: (
                sel_var.set(listbox.get(s[0]).strip().lstrip("📁").strip())
                if s and not os.path.isdir(os.path.join(current_dir[0],
                    listbox.get(s[0]).strip().lstrip("📁").strip()))
                else None
            )
        )(listbox.curselection()))

        def go_up():
            parent = os.path.dirname(current_dir[0])
            if parent != current_dir[0]:
                populate(parent)
                sel_var.set("")

        up_btn.config(command=go_up)

        def do_open():
            name = sel_var.get().strip()
            if not name:
                return
            full_path = os.path.join(current_dir[0], name)
            if os.path.isfile(full_path):
                self.last_sample_dir = current_dir[0]
                t = self.beats_tracks[self.beats_active_track]
                t["sample_path"] = full_path
                t["source_type"] = "sample"
                self.beats_sample_path_var.set(name)
                self._beats_render_track(self.beats_active_track)
                self._draw_beats_sidebar()
                dlg.destroy()

        open_btn.config(command=do_open)
        dlg.bind("<Return>", lambda e: do_open())



    def _on_beats_preset_change(self, _=None):
        """Handle preset dropdown change for the active track."""
        t = self.beats_tracks[self.beats_active_track]
        t["preset_name"] = self.beats_preset_var.get()
        t["source_type"] = "synth"
        self._beats_render_track(self.beats_active_track)

    def _on_beats_note_change(self, _=None):
        """Handle note dropdown change for the active track."""
        note_name = self.beats_note_var.get()
        for midi, name in self._beats_note_list:
            if name == note_name:
                self.beats_tracks[self.beats_active_track]["midi_note"] = midi
                break
        self._beats_render_track(self.beats_active_track)

    def _on_beats_volume_change(self, val):
        """Handle volume slider change."""
        vol = float(val)
        t = self.beats_tracks[self.beats_active_track]
        t["volume"] = vol
        self.beats_engine.track_volumes[self.beats_active_track] = vol
        self.beats_vol_label.config(text=f"{int(vol * 100)}%")

    def _on_beats_mute_toggle(self):
        """Handle mute button toggle."""
        t = self.beats_tracks[self.beats_active_track]
        t["mute"] = bool(self.beats_mute_var.get())
        self.beats_engine.track_mutes[self.beats_active_track] = t["mute"]
        self._draw_beats_sidebar()
        self._draw_beats_grid()

    def _on_beats_time_sig_change(self, _=None):
        """Handle time signature dropdown change."""
        self.beats_time_sig = self.beats_sig_var.get()
        self.beats_current_step = -1
        self._draw_beats_grid()
        self._draw_beats_leds()

    def _on_beats_preview(self):
        """Preview the active track's sound."""
        self._beats_render_track(self.beats_active_track)
        self.beats_engine.trigger_track(self.beats_active_track)

    # ── BEATS: Audio Rendering ───────────────────────────────────────

    def _beats_render_track(self, track_idx):
        """Load or render the audio buffer for a track."""
        t = self.beats_tracks[track_idx]

        if t["source_type"] == "sample" and t["sample_path"]:
            buf = load_wav_sample(t["sample_path"])
            if buf is not None:
                self.beats_engine.set_track_buffer(track_idx, buf)
            else:
                print(f"Failed to load sample: {t['sample_path']}")
        elif t["source_type"] == "synth":
            preset = FACTORY_PRESETS.get(t["preset_name"])
            if preset:
                buf = render_preset_sound(preset, t["midi_note"])
                self.beats_engine.set_track_buffer(track_idx, buf)

    def _beats_render_all_tracks(self):
        """Render audio buffers for all tracks."""
        for i in range(BEATS_NUM_TRACKS):
            self._beats_render_track(i)

    # ── BEATS: Transport & Clock ─────────────────────────────────────

    def _on_beats_step_tick(self, step):
        """Called on the main thread — update LED and playhead visuals."""
        # Update LED strip
        sig = TIME_SIGS[self.beats_time_sig]
        num_steps = sig["steps"]
        self.beats_led_canvas.itemconfig("all", fill=LED_OFF)
        if 0 <= step < num_steps:
            self.beats_led_canvas.itemconfig(f"beats_led_{step}",
                                              fill=RED_SIGNAL)

        # Update playhead
        self.beats_grid_canvas.delete("beats_playhead")
        if 0 <= step < num_steps:
            self._draw_beats_playhead(step)

        # Flash active pads at current step
        for track_idx in range(BEATS_NUM_TRACKS):
            if self.beats_tracks[track_idx]["pattern"][step]:
                x1 = step * PAD_SIZE + 3
                y1 = track_idx * PAD_SIZE + 3
                x2 = x1 + PAD_SIZE - 6
                y2 = y1 + PAD_SIZE - 6
                self.beats_grid_canvas.create_rectangle(
                    x1, y1, x2, y2, fill=RED_SIGNAL, outline="",
                    tags=("pad_flash", "beats_playhead")
                )

    def clear_beats_grid(self):
        """Wipe all patterns from the drum machine."""
        if messagebox.askyesno("Clear Beats",
                               "Wipe all beat patterns?"):
            for t in self.beats_tracks:
                t["pattern"] = [0] * MAX_STEPS
            self._draw_beats_grid()


# ─── Legacy Compatibility ────────────────────────────────────────────

# Keep old class name for backward compatibility with main.py imports
GridSequencerUI = AsherahSequencer

def run_ui_process(tx_pipe):
    """Legacy launcher for multiprocessing Pipe mode."""
    root = tk.Tk()

    try:
        from PIL import Image, ImageTk
        icon_img = Image.open("bull.png")
        taskbar_icon = ImageTk.PhotoImage(icon_img)
        root.iconphoto(True, taskbar_icon)
    except:
        pass

    app = AsherahSequencer(root, tx_pipe)
    root.mainloop()


# ─── Standalone Launcher ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--tethered', action='store_true', help='Run in tethered DAW mode')
    parser.add_argument('--track', type=int, default=0, help='DAW track index (0-based)')
    args = parser.parse_args()

    root = tk.Tk()

    try:
        from PIL import Image, ImageTk
        icon_img = Image.open("bull.png")
        taskbar_icon = ImageTk.PhotoImage(icon_img)
        root.iconphoto(True, taskbar_icon)
    except Exception as e:
        print(f"Icon warning: {e}")

    udp_port = 12160 + args.track if args.tethered else 12160
    app = AsherahSequencer(root, tx_pipe=None, udp_port=udp_port)

    if args.tethered:
        import threading
        track_num = args.track + 1
        state_file = f"/tmp/station_track_{args.track}_state.json"

        # Amber tethered banner at top of window
        tether_bar = tk.Frame(root, bg="#b87800", height=22)
        tether_bar.pack(side=tk.TOP, fill=tk.X, before=root.winfo_children()[0])
        tk.Label(tether_bar,
                 text=f"⬡  TETHERED  →  STATION MASTER  TRK {track_num}",
                 bg="#b87800", fg="#000000",
                 font=("PxPlus IBM VGA8", 11, "bold")).pack(side=tk.LEFT, padx=10)
        root.title(f"ASHERAH  [TRK {track_num}]")

        # Write state file periodically for the DAW waveform display
        def _write_state():
            try:
                # Snapshot a waveform from the beats engine if available
                waveform = [0.0] * 64
                if hasattr(app, 'beats_engine') and app.beats_engine is not None:
                    buf = getattr(app.beats_engine, 'last_out_frame', None)
                    if buf is not None:
                        waveform = buf[:64].tolist()
                state = {"preset": "ASHERAH", "waveform": waveform}
                with open(state_file, 'w') as f:
                    json.dump(state, f)
            except Exception:
                pass
            root.after(100, _write_state)

        root.after(100, _write_state)

    root.mainloop()
