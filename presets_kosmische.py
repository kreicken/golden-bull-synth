"""
presets_kosmische.py — Golden Bull Synthesizer
Kosmische / Krautrock expansion preset bank + special request.

HOW TO USE:
  Open presets.py and paste each entry below into FACTORY_PRESETS,
  before the closing brace. Add a # -- KOSMISCHE PRESETS -- comment
  separator if you like.
"""

# ── KOSMISCHE PRESETS ────────────────────────────────────────────────────────

# Tangerine Dream — "Phaedra" (1974) sequenced Moog bassline.
# Slow-cycling filter env on Moog Modular. OSC3 sub (0.5) gives the thick
# low-mid body. Arp in Minor mode for the classic sequencer feel.
# d_time ≈ sixteenth at 112 BPM: 60 / (112 * 4) ≈ 0.134s
"Phaedra Sequence": {
    "cutoff": 800.0, "resonance": 0.55, "drive": 1.3,
    "env_amt": 5500.0, "env_atk": 0.01, "env_dec": 0.35, "env_sus": 0.15, "env_rel": 0.2,
    "fm_on": 0, "fm_blend": 0.0, "fm_idx": 0.0, "fm_ratio": 1.0,
    "fm_env_amt": 0.0, "fm_env_atk": 0.1, "fm_env_dec": 0.3, "fm_env_sus": 0.0, "fm_env_rel": 0.2,
    "osc3_on": 1, "osc3_ratio": 0.5, "osc3_blend": 0.3,
    "d_on": 1, "d_time": 0.134, "d_feed": 0.25, "d_mix": 0.12,
    "a_on": 1, "a_bpm": 112.0, "a_rate": 0.25, "a_scale": "Minor", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},

# Tangerine Dream — "Rubycon" (1975) drifting luminous lead.
# FM at ratio 2.0 at low index rounds the saw toward sine. OSC3 fifth adds
# hollow two-voice shimmer. Very slow filter attack — the note blooms in.
# Long high-feedback delay blurs repeats into a spatial wash.
# d_time ≈ dotted quarter at 72 BPM: 3*(60/(72*2)) ≈ 0.625s
"Rubycon Drift": {
    "cutoff": 1200.0, "resonance": 0.25, "drive": 1.0,
    "env_amt": 3500.0, "env_atk": 1.8, "env_dec": 1.0, "env_sus": 0.7, "env_rel": 3.5,
    "fm_on": 1, "fm_blend": 0.5, "fm_idx": 0.8, "fm_ratio": 2.0,
    "fm_env_amt": 2.0, "fm_env_atk": 2.5, "fm_env_dec": 1.5, "fm_env_sus": 0.4, "fm_env_rel": 3.0,
    "osc3_on": 1, "osc3_ratio": 1.498, "osc3_blend": 0.2,
    "d_on": 1, "d_time": 0.625, "d_feed": 0.7, "d_mix": 0.5,
    "a_on": 0, "a_bpm": 72.0, "a_rate": 0.25, "a_scale": "Minor", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},

# Klaus Schulze — "Irrlicht" / "Cyborg" (1972-73) massive slow drone.
# 4-second attack — the sound takes forever to open. Very high FM env swell
# means the timbre evolves dramatically over time. Sub OSC3 for tectonic
# weight. Long 1.0s delay, high feedback — repeats blur into one mass.
# Hold one or two notes; this is a pressure preset, not a melody preset.
"Schulze Monolith": {
    "cutoff": 600.0, "resonance": 0.4, "drive": 1.1,
    "env_amt": 7000.0, "env_atk": 4.0, "env_dec": 2.0, "env_sus": 0.5, "env_rel": 5.0,
    "fm_on": 1, "fm_blend": 0.3, "fm_idx": 3.0, "fm_ratio": 1.5,
    "fm_env_amt": 12.0, "fm_env_atk": 5.0, "fm_env_dec": 3.0, "fm_env_sus": 0.2, "fm_env_rel": 5.0,
    "osc3_on": 1, "osc3_ratio": 0.5, "osc3_blend": 0.25,
    "d_on": 1, "d_time": 1.0, "d_feed": 0.8, "d_mix": 0.55,
    "a_on": 0, "a_bpm": 60.0, "a_rate": 0.25, "a_scale": "Minor", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},

# CAN — "Halleluwah" / "Mushroom" (Tago Mago, 1971).
# Irmin Schmidt: raw, overdriven, percussive. Fast filter decay, near-zero
# sustain = plucked staccato character. OSC3 at fifth adds the odd dissonant
# interval CAN favored. No delay — CAN was always dry and present.
"CAN Machine": {
    "cutoff": 3500.0, "resonance": 0.45, "drive": 1.7,
    "env_amt": 5000.0, "env_atk": 0.01, "env_dec": 0.18, "env_sus": 0.05, "env_rel": 0.12,
    "fm_on": 1, "fm_blend": 0.3, "fm_idx": 1.5, "fm_ratio": 1.0,
    "fm_env_amt": 3.0, "fm_env_atk": 0.01, "fm_env_dec": 0.25, "fm_env_sus": 0.0, "fm_env_rel": 0.1,
    "osc3_on": 1, "osc3_ratio": 1.498, "osc3_blend": 0.2,
    "d_on": 0, "d_time": 0.3, "d_feed": 0.3, "d_mix": 0.0,
    "a_on": 0, "a_bpm": 120.0, "a_rate": 0.25, "a_scale": "Minor", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},

# Cluster / Harmonia — detuned ambient organ drone (1974-75).
# Moebius and Roedelius: pads that hovered without resolution.
# OSC1 + OSC3 at 1.008 = slow meditative beat frequency. FM softens the saw.
# Very long 6s release — notes breathe out slowly and never feel abrupt.
"Cluster Drift": {
    "cutoff": 2200.0, "resonance": 0.2, "drive": 1.0,
    "env_amt": 2000.0, "env_atk": 0.5, "env_dec": 0.8, "env_sus": 0.75, "env_rel": 6.0,
    "fm_on": 1, "fm_blend": 0.3, "fm_idx": 0.6, "fm_ratio": 1.0,
    "fm_env_amt": 1.0, "fm_env_atk": 1.0, "fm_env_dec": 1.0, "fm_env_sus": 0.5, "fm_env_rel": 4.0,
    "osc3_on": 1, "osc3_ratio": 1.008, "osc3_blend": 0.4,
    "d_on": 1, "d_time": 0.55, "d_feed": 0.45, "d_mix": 0.25,
    "a_on": 0, "a_bpm": 80.0, "a_rate": 0.25, "a_scale": "Major", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},

# ── SPECIAL REQUEST ───────────────────────────────────────────────────────────

# Calvin-Maysun Pink — "Green Girl" twinkly delay synth.
# Glassy bell-adjacent: instant attack, fast decay, zero sustain — each note
# shimmers then vanishes; the delay cascade carries it forward. FM at ratio
# 3.0 at moderate index = glassy inharmonic sparkle (Rhodes/marimba upper
# partial character). OSC3 at octave up (2.0) adds the twinkle top end on
# attack. Dotted-eighth delay at ~95 BPM creates the overlapping shimmer
# cascade heard in the song.
# d_time = dotted eighth at 95 BPM: 3*(60/(95*2)) ≈ 0.474s
"Sag - A": {
    "cutoff": 7000.0, "resonance": 0.12, "drive": 1.0,
    "env_amt": 1500.0, "env_atk": 0.005, "env_dec": 0.4, "env_sus": 0.0, "env_rel": 0.6,
    "fm_on": 1, "fm_blend": 0.5, "fm_idx": 4.5, "fm_ratio": 3.0,
    "fm_env_amt": 6.0, "fm_env_atk": 0.005, "fm_env_dec": 0.35, "fm_env_sus": 0.0, "fm_env_rel": 0.5,
    "osc3_on": 1, "osc3_ratio": 2.0, "osc3_blend": 0.15,
    "d_on": 1, "d_time": 0.474, "d_feed": 0.55, "d_mix": 0.4,
    "a_on": 0, "a_bpm": 95.0, "a_rate": 0.25, "a_scale": "Major", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},
