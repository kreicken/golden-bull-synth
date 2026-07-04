"""
music_theory.py — ASHERAH Hybrid Sequencer
Scale folding engine and music theory utilities.
Generates dynamic Y-axis note sets based on root key and scale/mode selection.
"""

import numpy as np

# ─── Chromatic Note Names ─────────────────────────────────────────────
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Enharmonic display names (prefer flats for certain contexts)
ENHARMONIC = {
    "C#": "Db", "D#": "Eb", "F#": "Gb", "G#": "Ab", "A#": "Bb"
}

# ─── Scale / Mode Definitions ────────────────────────────────────────
# Intervals are semitone offsets from the root
SCALES = {
    "Major":             [0, 2, 4, 5, 7, 9, 11],
    "Minor":             [0, 2, 3, 5, 7, 8, 10],
    "Dorian":            [0, 2, 3, 5, 7, 9, 10],
    "Phrygian":          [0, 1, 3, 5, 7, 8, 10],
    "Lydian":            [0, 2, 4, 6, 7, 9, 11],
    "Mixolydian":        [0, 2, 4, 5, 7, 9, 10],
    "Pentatonic Major":  [0, 2, 4, 7, 9],
    "Pentatonic Minor":  [0, 3, 5, 7, 10],
    "Blues":              [0, 3, 4, 5, 7, 10],
    "Chromatic":         [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    "Harmonic Minor":    [0, 2, 3, 5, 7, 8, 11],
    "Melodic Minor":     [0, 2, 3, 5, 7, 9, 11],
    "Whole Tone":        [0, 2, 4, 6, 8, 10],
}

# Root key name to MIDI pitch class (C=0, C#=1, ... B=11)
ROOT_KEYS = {name: i for i, name in enumerate(NOTE_NAMES)}


def midi_to_note_name(midi_note):
    """Convert a MIDI note number to a display string like 'G2' or 'Bb3'."""
    octave = (midi_note // 12) - 1
    pitch_class = midi_note % 12
    name = NOTE_NAMES[pitch_class]
    return f"{name}{octave}"


def midi_to_freq(midi_note):
    """Convert MIDI note number to frequency in Hz."""
    return 440.0 * 2.0 ** ((midi_note - 69) / 12.0)


def freq_to_midi(freq):
    """Convert frequency in Hz to MIDI note number."""
    return 69 + 12 * np.log2(freq / 440.0)


def is_root_note(midi_note, root_name):
    """Check if a MIDI note is the tonic of the given root key."""
    root_pc = ROOT_KEYS.get(root_name, 0)
    return (midi_note % 12) == root_pc


def get_scale_notes(root_name, scale_name, octave_lo=2, octave_hi=6):
    """
    Generate a list of (midi_note, display_name) tuples for the given
    root key and scale, filtered to the specified octave range.
    
    The list is returned in ascending pitch order (low to high).
    For piano roll display, the caller should reverse it so high notes
    appear at the top of the Y-axis.
    
    Args:
        root_name:  Root key string, e.g. "G", "C#", "Bb"
        scale_name: Scale/mode name from SCALES dict
        octave_lo:  Lowest octave to include (default 2)
        octave_hi:  Highest octave to include (default 6)
    
    Returns:
        List of (midi_note, display_name) tuples, ascending.
        Example: [(43, "G2"), (45, "A2"), (46, "Bb2"), ...]
    """
    root_pc = ROOT_KEYS.get(root_name, 0)
    intervals = SCALES.get(scale_name, SCALES["Chromatic"])
    
    midi_lo = (octave_lo + 1) * 12  # Octave 2 = MIDI 36
    midi_hi = (octave_hi + 1) * 12 + 11  # Octave 6 = MIDI 83..95
    
    notes = []
    for midi_note in range(midi_lo, midi_hi + 1):
        # Check if this note's pitch class is in the scale
        pc = (midi_note - root_pc) % 12
        if pc in intervals:
            display = midi_to_note_name(midi_note)
            notes.append((midi_note, display))
    
    return notes


def get_scale_names():
    """Return a list of all available scale/mode names."""
    return list(SCALES.keys())


def get_root_key_names():
    """Return a list of all 12 root key names."""
    return list(NOTE_NAMES)
