"""
presets.py — Golden Bull Synthesizer
Shared factory preset definitions.
Used by both main.py (synth engine) and grid_ui.py (ASHERAH sequencer).

OSC 3 RATIO REFERENCE:
  0.5    = sub octave (one octave below OSC 1)
  1.0    = unison (same pitch, pure thickening)
  1.004  = ~+7 cents sharp (oscillator beating / warmth)
  1.498  = perfect fifth above
  2.0    = octave above
  3.0    = octave + fifth above
"""

FACTORY_PRESETS = {

# ── GENERAL PRESETS ──────────────────────────────────────────────────────────

# Juno-60 Pad — classic Roland-style chorus pad.
# Pure sawtooth with OSC3 at 1.002 for slight beating. 
# The magic is in the Chorus: slow rate, moderate depth, 50% mix.
"Juno-60 Pad": {
    "cutoff": 1200.0, "resonance": 0.15, "drive": 1.0,
    "vca_atk": 0.2, "vca_dec": 0.5, "vca_sus": 0.7, "vca_rel": 1.2,
    "env_amt": 2000.0, "env_atk": 0.2, "env_dec": 0.5, "env_sus": 0.7, "env_rel": 1.2,
    "fm_on": 0, "fm_blend": 0.0, "fm_idx": 0.0, "fm_ratio": 1.0,
    "fm_env_amt": 0.0, "fm_env_atk": 0.1, "fm_env_dec": 0.3, "fm_env_sus": 0.0, "fm_env_rel": 0.2,
    "osc3_on": 1, "osc3_ratio": 1.002, "osc3_blend": 0.25,
    "c_on": 1, "c_rate": 1.2, "c_depth": 0.3, "c_mix": 0.5,
    "d_on": 1, "d_time": 0.4, "d_feed": 0.2, "d_mix": 0.15,
    "reverb_wet": 0.2,
    "a_on": 0, "a_bpm": 120.0, "a_rate": 0.25, "a_scale": "Major", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},

# Prophet's Call — classic Sequential Circuits-style lead.
# OSC1 saw + OSC3 at 1.006 (~+10 cents) creates gentle dual-VCO beating.
# Resonant filter with moderate env sweep. Light delay for space.
"Prophet's Call": {
    "cutoff": 2500.0, "resonance": 0.65, "drive": 1.5,
    "vca_atk": 0.01, "vca_dec": 0.25, "vca_sus": 0.7, "vca_rel": 0.2,
    "env_amt": 4000.0, "env_atk": 0.01, "env_dec": 0.25, "env_sus": 0.6, "env_rel": 0.3,
    "fm_on": 0, "fm_blend": 0.0, "fm_idx": 0.0, "fm_ratio": 1.0,
    "fm_env_amt": 0.0, "fm_env_atk": 0.1, "fm_env_dec": 0.3, "fm_env_sus": 0.0, "fm_env_rel": 0.2,
    "osc3_on": 1, "osc3_ratio": 1.006, "osc3_blend": 0.35,
    "d_on": 1, "d_time": 0.35, "d_feed": 0.25, "d_mix": 0.15,
    "a_on": 0, "a_bpm": 120.0, "a_rate": 0.25, "a_scale": "Major", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},

# Midnight Bass — deep sub bass. OSC3 one octave below OSC1 for serious
# low-end weight. FM off. Drive pushed. No delay — keeps the low end tight.
"Midnight Bass": {
    "cutoff": 400.0, "resonance": 0.3, "drive": 2.5,
    "vca_atk": 0.01, "vca_dec": 0.4, "vca_sus": 0.6, "vca_rel": 0.15,
    "env_amt": 3000.0, "env_atk": 0.01, "env_dec": 0.4, "env_sus": 0.2, "env_rel": 0.15,
    "fm_on": 0, "fm_blend": 0.0, "fm_idx": 0.0, "fm_ratio": 1.0,
    "fm_env_amt": 0.0, "fm_env_atk": 0.1, "fm_env_dec": 0.5, "fm_env_sus": 0.0, "fm_env_rel": 0.2,
    "osc3_on": 1, "osc3_ratio": 0.5, "osc3_blend": 0.3,
    "d_on": 0, "d_time": 0.3, "d_feed": 0.3, "d_mix": 0.0,
    "a_on": 0, "a_bpm": 120.0, "a_rate": 0.25, "a_scale": "Major", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},

# Crystal Bell — FM bell tones. OSC3 at 3x ratio adds a high partial that
# reinforces the inharmonic FM overtones. Percussive decay, long release.
"Crystal Bell": {
    "cutoff": 8000.0, "resonance": 0.1, "drive": 1.0,
    "vca_atk": 0.01, "vca_dec": 1.2, "vca_sus": 0.0, "vca_rel": 1.0,
    "env_amt": 2000.0, "env_atk": 0.01, "env_dec": 1.5, "env_sus": 0.0, "env_rel": 1.0,
    "fm_on": 1, "fm_blend": 0.55, "fm_idx": 6.0, "fm_ratio": 3.0,
    "fm_env_amt": 8.0, "fm_env_atk": 0.01, "fm_env_dec": 1.2, "fm_env_sus": 0.0, "fm_env_rel": 0.8,
    "osc3_on": 1, "osc3_ratio": 3.0, "osc3_blend": 0.15,
    "d_on": 1, "d_time": 0.45, "d_feed": 0.5, "d_mix": 0.35,
    "a_on": 0, "a_bpm": 120.0, "a_rate": 0.25, "a_scale": "Major", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},

# Blade Runner — slow Vangelis-esque pad. OSC3 at a perfect fifth creates
# the hollow two-voice CS-80/Oberheim texture. Slow FM swell adds movement.
# High delay feedback for long spatial trails.
"Blade Runner": {
    "cutoff": 3000.0, "resonance": 0.4, "drive": 1.2,
    "vca_atk": 1.5, "vca_dec": 1.0, "vca_sus": 0.8, "vca_rel": 2.5,
    "env_amt": 2500.0, "env_atk": 1.5, "env_dec": 0.8, "env_sus": 0.7, "env_rel": 2.0,
    "fm_on": 1, "fm_blend": 0.35, "fm_idx": 3.0, "fm_ratio": 2.0,
    "fm_env_amt": 4.0, "fm_env_atk": 2.0, "fm_env_dec": 1.0, "fm_env_sus": 0.3, "fm_env_rel": 2.5,
    "osc3_on": 1, "osc3_ratio": 1.498, "osc3_blend": 0.25,
    "d_on": 1, "d_time": 0.6, "d_feed": 0.65, "d_mix": 0.4,
    "a_on": 0, "a_bpm": 120.0, "a_rate": 0.25, "a_scale": "Major", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},

# Orbital Organ — Hammond-style additive simulation. OSC1 (fundamental) +
# FM at ratio 1.0 (body/even harmonics) + OSC3 at 2.0 (octave, 8'+4' drawbar).
# Low FM index keeps it musical. Light short delay simulates room/Leslie.
"Orbital Organ": {
    "cutoff": 5000.0, "resonance": 0.15, "drive": 1.0,
    "vca_atk": 0.05, "vca_dec": 0.2, "vca_sus": 0.9, "vca_rel": 0.3,
    "env_amt": 1000.0, "env_atk": 0.08, "env_dec": 0.2, "env_sus": 0.9, "env_rel": 0.3,
    "fm_on": 1, "fm_blend": 0.45, "fm_idx": 2.5, "fm_ratio": 1.0,
    "fm_env_amt": 1.5, "fm_env_atk": 0.3, "fm_env_dec": 0.5, "fm_env_sus": 0.8, "fm_env_rel": 0.4,
    "osc3_on": 1, "osc3_ratio": 2.0, "osc3_blend": 0.2,
    "d_on": 1, "d_time": 0.2, "d_feed": 0.2, "d_mix": 0.1,
    "a_on": 0, "a_bpm": 120.0, "a_rate": 0.25, "a_scale": "Major", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},

# Solar Wind — massive evolving ambient texture. OSC3 sub anchors the ground
# beneath swirling FM. High FM env amt means timbre morphs dramatically over
# the slow attack. Hold a note 8+ seconds to hear the full evolution.
"Solar Wind": {
    "cutoff": 1500.0, "resonance": 0.5, "drive": 1.0,
    "vca_atk": 2.0, "vca_dec": 2.0, "vca_sus": 0.5, "vca_rel": 3.0,
    "env_amt": 6000.0, "env_atk": 2.5, "env_dec": 1.5, "env_sus": 0.4, "env_rel": 3.0,
    "fm_on": 1, "fm_blend": 0.35, "fm_idx": 4.0, "fm_ratio": 1.5,
    "fm_env_amt": 10.0, "fm_env_atk": 3.0, "fm_env_dec": 2.0, "fm_env_sus": 0.1, "fm_env_rel": 3.0,
    "osc3_on": 1, "osc3_ratio": 0.5, "osc3_blend": 0.2,
    "d_on": 1, "d_time": 0.8, "d_feed": 0.75, "d_mix": 0.5,
    "a_on": 0, "a_bpm": 120.0, "a_rate": 0.25, "a_scale": "Major", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},

# Brass Stab — punchy horn stab. OSC3 at 2.0 (octave up, low blend) adds
# the bright attack splat of a real brass section. Short percussive envelope.
# FM gives the rough metallic edge. No delay — stabs need to be dry and tight.
"Brass Stab": {
    "cutoff": 1200.0, "resonance": 0.2, "drive": 1.8,
    "vca_atk": 0.01, "vca_dec": 0.15, "vca_sus": 0.0, "vca_rel": 0.1,
    "env_amt": 6000.0, "env_atk": 0.01, "env_dec": 0.15, "env_sus": 0.0, "env_rel": 0.1,
    "fm_on": 1, "fm_blend": 0.45, "fm_idx": 4.0, "fm_ratio": 1.0,
    "fm_env_amt": 6.0, "fm_env_atk": 0.01, "fm_env_dec": 0.2, "fm_env_sus": 0.0, "fm_env_rel": 0.1,
    "osc3_on": 1, "osc3_ratio": 2.0, "osc3_blend": 0.15,
    "d_on": 0, "d_time": 0.3, "d_feed": 0.3, "d_mix": 0.0,
    "a_on": 0, "a_bpm": 120.0, "a_rate": 0.25, "a_scale": "Major", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},

# Ghost Choir — spectral vocal pad. FM ratio 2.0 creates formant-like
# resonances. OSC3 at a perfect fifth simulates choral voice doubling.
# Slow attack and long release lets the voices swell in and breathe out.
"Ghost Choir": {
    "cutoff": 2000.0, "resonance": 0.35, "drive": 1.0,
    "vca_atk": 1.2, "vca_dec": 1.0, "vca_sus": 0.8, "vca_rel": 2.5,
    "env_amt": 3000.0, "env_atk": 1.0, "env_dec": 0.5, "env_sus": 0.8, "env_rel": 2.0,
    "fm_on": 1, "fm_blend": 0.5, "fm_idx": 2.0, "fm_ratio": 2.0,
    "fm_env_amt": 3.0, "fm_env_atk": 1.5, "fm_env_dec": 1.0, "fm_env_sus": 0.5, "fm_env_rel": 2.0,
    "osc3_on": 1, "osc3_ratio": 1.498, "osc3_blend": 0.2,
    "d_on": 1, "d_time": 0.5, "d_feed": 0.6, "d_mix": 0.45,
    "a_on": 0, "a_bpm": 120.0, "a_rate": 0.25, "a_scale": "Major", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},

# d_time = dotted eighth note at 130 BPM: 3 * (60 / (130 * 2)) ≈ 0.346s
# Neon Arp — fast arpeggiator preset. OSC3 at octave up adds sparkle to
# high-register arp notes. Delay dotted-eighth locks arp into a cascade effect.
"Neon Arp": {
    "cutoff": 6000.0, "resonance": 0.3, "drive": 1.0,
    "vca_atk": 0.01, "vca_dec": 0.2, "vca_sus": 0.5, "vca_rel": 0.15,
    "env_amt": 3000.0, "env_atk": 0.01, "env_dec": 0.2, "env_sus": 0.3, "env_rel": 0.15,
    "fm_on": 1, "fm_blend": 0.25, "fm_idx": 1.5, "fm_ratio": 1.0,
    "fm_env_amt": 2.0, "fm_env_atk": 0.01, "fm_env_dec": 0.3, "fm_env_sus": 0.0, "fm_env_rel": 0.2,
    "osc3_on": 1, "osc3_ratio": 2.0, "osc3_blend": 0.2,
    "d_on": 1, "d_time": 0.346, "d_feed": 0.4, "d_mix": 0.3,
    "a_on": 1, "a_bpm": 130.0, "a_rate": 0.25, "a_scale": "Major", "a_oct": 2, "a_len": 4, "a_rnd": 0,
},

# Init — clean blank slate for patch building. All FX and FM off.
# OSC3 on but blend at 0.0 — silent until user raises the knob.
"Init": {
    "cutoff": 1000.0, "resonance": 0.0, "drive": 1.0,
    "vca_atk": 0.01, "vca_dec": 0.3, "vca_sus": 1.0, "vca_rel": 0.1,
    "env_amt": 5000.0, "env_atk": 0.05, "env_dec": 0.3, "env_sus": 0.5, "env_rel": 0.2,
    "fm_on": 0, "fm_blend": 0.0, "fm_idx": 0.0, "fm_ratio": 1.0,
    "fm_env_amt": 0.0, "fm_env_atk": 0.1, "fm_env_dec": 0.5, "fm_env_sus": 0.0, "fm_env_rel": 0.2,
    "osc3_on": 1, "osc3_ratio": 1.0, "osc3_blend": 0.0,
    "d_on": 0, "d_time": 0.3, "d_feed": 0.3, "d_mix": 0.0,
    "a_on": 0, "a_bpm": 120.0, "a_rate": 0.25, "a_scale": "Major", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},

# ── VINTAGE PRESETS ──────────────────────────────────────────────────────────

# Inspired by: Steve Miller Band — "Fly Like an Eagle" (1976) sustained wash.
# Roland SH-2000 single oscillator, wide-open filter, nearly no resonance.
# The cascading wash is created entirely by high-feedback delay — OSC3 off,
# the delay IS the second voice. Adding OSC3 would muddy the pristine wash.
# d_time ≈ dotted eighth at 96 BPM: 3 * (60 / (96 * 2)) = 0.469s
"Eagle FX": {
    "cutoff": 7500.0, "resonance": 0.05, "drive": 1.0,
    "vca_atk": 0.1, "vca_dec": 0.3, "vca_sus": 1.0, "vca_rel": 0.5,
    "env_amt": 300.0, "env_atk": 0.04, "env_dec": 0.2, "env_sus": 1.0, "env_rel": 0.5,
    "fm_on": 0, "fm_blend": 0.0, "fm_idx": 0.0, "fm_ratio": 1.0,
    "fm_env_amt": 0.0, "fm_env_atk": 0.01, "fm_env_dec": 0.1, "fm_env_sus": 0.0, "fm_env_rel": 0.1,
    "osc3_on": 0, "osc3_ratio": 1.0, "osc3_blend": 0.0,
    "d_on": 1, "d_time": 0.469, "d_feed": 0.65, "d_mix": 0.55,
    "a_on": 0, "a_bpm": 96.0, "a_rate": 0.25, "a_scale": "Major", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},

# Inspired by: Steve Miller Band — "Fly Like an Eagle" intro arpeggio.
# Single-oscillator purity — OSC3 and FM both off. The overlapping delay
# cascade at dotted-eighth rhythm creates the illusion of multiple voices.
# d_time = dotted eighth at 96 BPM: 3 * (60 / (96 * 2)) ≈ 0.469s
"Eagle Space Arp": {
    "cutoff": 6500.0, "resonance": 0.1, "drive": 1.0,
    "vca_atk": 0.01, "vca_dec": 0.2, "vca_sus": 0.7, "vca_rel": 0.2,
    "env_amt": 800.0, "env_atk": 0.01, "env_dec": 0.15, "env_sus": 0.7, "env_rel": 0.2,
    "fm_on": 0, "fm_blend": 0.0, "fm_idx": 0.0, "fm_ratio": 1.0,
    "fm_env_amt": 0.0, "fm_env_atk": 0.01, "fm_env_dec": 0.2, "fm_env_sus": 0.0, "fm_env_rel": 0.15,
    "osc3_on": 0, "osc3_ratio": 1.0, "osc3_blend": 0.0,
    "d_on": 1, "d_time": 0.469, "d_feed": 0.6, "d_mix": 0.45,
    "a_on": 1, "a_bpm": 96.0, "a_rate": 0.25, "a_scale": "Major", "a_oct": 2, "a_len": 4, "a_rnd": 0,
},

# Inspired by: ELP — "Lucky Man" (1970) Moog Modular lead synth.
# The Moog Modular used three detuned oscillators — that slow beating between
# them is the entire character of the sound. FM is OFF. OSC3 at 1.004 (~+7
# cents) against OSC1 creates authentic oscillator beating. No FM, no delay —
# just two slightly-out-of-tune sawtooth waves through a wide-open Moog filter.
"Lucky Man Lead": {
    "cutoff": 8000.0, "resonance": 0.1, "drive": 1.1,
    "vca_atk": 0.02, "vca_dec": 0.3, "vca_sus": 0.9, "vca_rel": 0.4,
    "env_amt": 500.0, "env_atk": 0.02, "env_dec": 0.3, "env_sus": 0.85, "env_rel": 0.5,
    "fm_on": 0, "fm_blend": 0.0, "fm_idx": 0.0, "fm_ratio": 1.0,
    "fm_env_amt": 0.0, "fm_env_atk": 0.05, "fm_env_dec": 0.4, "fm_env_sus": 0.8, "fm_env_rel": 0.5,
    "osc3_on": 1, "osc3_ratio": 1.004, "osc3_blend": 0.4,
    "d_on": 0, "d_time": 0.35, "d_feed": 0.2, "d_mix": 0.0,
    "a_on": 0, "a_bpm": 120.0, "a_rate": 0.25, "a_scale": "Major", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},

# Inspired by: ELP — "Lucky Man" climactic Moog filter sweep.
# High resonance + very slow filter attack = the iconic sweep that closes the
# song. OSC3 at sub (0.5) adds weight — the original Moog had serious low-end.
# FM off. Hold a long note and let the envelope open the filter over 1.3s.
"Lucky Man Sweep": {
    "cutoff": 300.0, "resonance": 0.82, "drive": 1.2,
    "vca_atk": 0.5, "vca_dec": 1.0, "vca_sus": 0.8, "vca_rel": 1.5,
    "env_amt": 7500.0, "env_atk": 1.3, "env_dec": 0.5, "env_sus": 0.6, "env_rel": 1.5,
    "fm_on": 0, "fm_blend": 0.0, "fm_idx": 0.0, "fm_ratio": 1.0,
    "fm_env_amt": 0.0, "fm_env_atk": 0.5, "fm_env_dec": 0.5, "fm_env_sus": 0.6, "fm_env_rel": 1.0,
    "osc3_on": 1, "osc3_ratio": 0.5, "osc3_blend": 0.2,
    "d_on": 0, "d_time": 0.35, "d_feed": 0.25, "d_mix": 0.0,
    "a_on": 0, "a_bpm": 120.0, "a_rate": 0.25, "a_scale": "Major", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},

# Inspired by: ELP — "Tarkus" (1971) Keith Emerson aggressive Moog lead.
# Bright, biting, highly resonant. OSC3 at a perfect fifth (1.498) creates
# the two-voice interval aggression. FM ratio 2.0 at index 2.0 gives the
# metallic Moog edge. Drive pushed. Fast filter attack — punchy and mean.
"Tarkus Lead": {
    "cutoff": 2000.0, "resonance": 0.55, "drive": 1.6,
    "vca_atk": 0.01, "vca_dec": 0.2, "vca_sus": 0.6, "vca_rel": 0.2,
    "env_amt": 6000.0, "env_atk": 0.01, "env_dec": 0.3, "env_sus": 0.5, "env_rel": 0.25,
    "fm_on": 1, "fm_blend": 0.3, "fm_idx": 2.0, "fm_ratio": 2.0,
    "fm_env_amt": 4.0, "fm_env_atk": 0.01, "fm_env_dec": 0.4, "fm_env_sus": 0.2, "fm_env_rel": 0.3,
    "osc3_on": 1, "osc3_ratio": 1.498, "osc3_blend": 0.25,
    "d_on": 0, "d_time": 0.3, "d_feed": 0.3, "d_mix": 0.0,
    "a_on": 0, "a_bpm": 120.0, "a_rate": 0.25, "a_scale": "Major", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},
# ── KOSMISCHE PRESETS ────────────────────────────────────────────────────────

# Tangerine Dream — "Phaedra" (1974) sequenced Moog bassline.
# Slow-cycling filter env on Moog Modular. OSC3 sub (0.5) gives the thick
# low-mid body. Arp in Minor mode for the classic sequencer feel.
# d_time ≈ sixteenth at 112 BPM: 60 / (112 * 4) ≈ 0.134s
"Phaedra Sequence": {
    "cutoff": 800.0, "resonance": 0.55, "drive": 1.3,
    "vca_atk": 0.01, "vca_dec": 0.3, "vca_sus": 0.4, "vca_rel": 0.15,
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
    "vca_atk": 1.5, "vca_dec": 1.0, "vca_sus": 0.8, "vca_rel": 3.0,
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
    "vca_atk": 3.0, "vca_dec": 2.0, "vca_sus": 0.4, "vca_rel": 4.0,
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
    "vca_atk": 0.01, "vca_dec": 0.15, "vca_sus": 0.0, "vca_rel": 0.1,
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
    "vca_atk": 0.5, "vca_dec": 1.0, "vca_sus": 0.8, "vca_rel": 5.0,
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
    "vca_atk": 0.005, "vca_dec": 0.4, "vca_sus": 0.0, "vca_rel": 0.6,
    "env_amt": 1500.0, "env_atk": 0.005, "env_dec": 0.4, "env_sus": 0.0, "env_rel": 0.6,
    "fm_on": 1, "fm_blend": 0.5, "fm_idx": 4.5, "fm_ratio": 3.0,
    "fm_env_amt": 6.0, "fm_env_atk": 0.005, "fm_env_dec": 0.35, "fm_env_sus": 0.0, "fm_env_rel": 0.5,
    "osc3_on": 1, "osc3_ratio": 2.0, "osc3_blend": 0.15,
    "d_on": 1, "d_time": 0.474, "d_feed": 0.55, "d_mix": 0.4,
    "a_on": 0, "a_bpm": 95.0, "a_rate": 0.25, "a_scale": "Major", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},

# ── MODERN & CUSTOM ──────────────────────────────────────────────────────────

# Dystopian Lead — aggressive, biting FM lead.
# High FM index and pushed drive for metallic grit.
"Dystopian Lead": {
    "cutoff": 1800.0, "resonance": 0.6, "drive": 2.2,
    "vca_atk": 0.01, "vca_dec": 0.3, "vca_sus": 0.6, "vca_rel": 0.2,
    "env_amt": 5000.0, "env_atk": 0.01, "env_dec": 0.3, "env_sus": 0.4, "env_rel": 0.2,
    "fm_on": 1, "fm_blend": 0.6, "fm_idx": 8.0, "fm_ratio": 2.0,
    "fm_env_amt": 4.0, "fm_env_atk": 0.01, "fm_env_dec": 0.4, "fm_env_sus": 0.2, "fm_env_rel": 0.2,
    "osc3_on": 1, "osc3_ratio": 1.006, "osc3_blend": 0.2,
    "d_on": 1, "d_time": 0.15, "d_feed": 0.3, "d_mix": 0.2,
    "a_on": 0, "a_bpm": 120.0, "a_rate": 0.25, "a_scale": "Major", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},

# Ethereal Pad — slow-blooming, "shimmer" pad.
# High FM ratio creates airy sparkle; sub OSC3 adds grounding weight.
"Ethereal Pad": {
    "cutoff": 3000.0, "resonance": 0.2, "drive": 1.0,
    "vca_atk": 2.0, "vca_dec": 1.5, "vca_sus": 0.8, "vca_rel": 3.5,
    "env_amt": 2500.0, "env_atk": 2.5, "env_dec": 1.0, "env_sus": 0.8, "env_rel": 4.0,
    "fm_on": 1, "fm_blend": 0.4, "fm_idx": 2.0, "fm_ratio": 4.0,
    "fm_env_amt": 3.0, "fm_env_atk": 3.0, "fm_env_dec": 2.0, "fm_env_sus": 0.5, "fm_env_rel": 4.0,
    "osc3_on": 1, "osc3_ratio": 0.5, "osc3_blend": 0.2,
    "d_on": 1, "d_time": 0.8, "d_feed": 0.75, "d_mix": 0.5,
    "a_on": 0, "a_bpm": 120.0, "a_rate": 0.25, "a_scale": "Major", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},

# Cosmic Harpsichord — plucked, metallic, spatial.
# Fast FM envelope and high ratio for the "pluck"; long delay trails for space.
"Cosmic Harpsichord": {
    "cutoff": 6000.0, "resonance": 0.3, "drive": 1.1,
    "vca_atk": 0.001, "vca_dec": 0.3, "vca_sus": 0.0, "vca_rel": 0.6,
    "env_amt": 2000.0, "env_atk": 0.001, "env_dec": 0.25, "env_sus": 0.0, "env_rel": 0.8,
    "fm_on": 1, "fm_blend": 0.4, "fm_idx": 5.0, "fm_ratio": 6.0,
    "fm_env_amt": 8.0, "fm_env_atk": 0.001, "fm_env_dec": 0.2, "fm_env_sus": 0.0, "fm_env_rel": 0.5,
    "osc3_on": 1, "osc3_ratio": 2.0, "osc3_blend": 0.15,
    "d_on": 1, "d_time": 0.45, "d_feed": 0.6, "d_mix": 0.35,
    "a_on": 0, "a_bpm": 120.0, "a_rate": 0.25, "a_scale": "Major", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},

# Kid Icarus Arp — 8-bit NES style rapid arpeggio.
# Fast minor-scale arp and gated envelope for authentic chiptune feel.
"Kid Icarus Arp": {
    "cutoff": 9000.0, "resonance": 0.0, "drive": 1.0,
    "vca_atk": 0.001, "vca_dec": 0.1, "vca_sus": 0.8, "vca_rel": 0.1,
    "env_amt": 500.0, "env_atk": 0.001, "env_dec": 0.1, "env_sus": 0.5, "env_rel": 0.05,
    "fm_on": 1, "fm_blend": 0.3, "fm_idx": 1.0, "fm_ratio": 1.0,
    "fm_env_amt": 0.0, "fm_env_atk": 0.01, "fm_env_dec": 0.1, "fm_env_sus": 0.0, "fm_env_rel": 0.1,
    "osc3_on": 0, "osc3_ratio": 1.0, "osc3_blend": 0.0,
    "d_on": 0, "d_time": 0.3, "d_feed": 0.3, "d_mix": 0.0,
    "a_on": 1, "a_bpm": 140.0, "a_rate": 0.125, "a_scale": "Minor", "a_oct": 2, "a_len": 4, "a_rnd": 0,
},
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

# ── MODERN & CUSTOM ──────────────────────────────────────────────────────────

# Dystopian Lead — aggressive, biting FM lead.
# High FM index and pushed drive for metallic grit.
"Dystopian Lead": {
    "cutoff": 1800.0, "resonance": 0.6, "drive": 2.2,
    "env_amt": 5000.0, "env_atk": 0.01, "env_dec": 0.3, "env_sus": 0.4, "env_rel": 0.2,
    "fm_on": 1, "fm_blend": 0.6, "fm_idx": 8.0, "fm_ratio": 2.0,
    "fm_env_amt": 4.0, "fm_env_atk": 0.01, "fm_env_dec": 0.4, "fm_env_sus": 0.2, "fm_env_rel": 0.2,
    "osc3_on": 1, "osc3_ratio": 1.006, "osc3_blend": 0.2,
    "d_on": 1, "d_time": 0.15, "d_feed": 0.3, "d_mix": 0.2,
    "a_on": 0, "a_bpm": 120.0, "a_rate": 0.25, "a_scale": "Major", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},

# Ethereal Pad — slow-blooming, "shimmer" pad.
# High FM ratio creates airy sparkle; sub OSC3 adds grounding weight.
"Ethereal Pad": {
    "cutoff": 3000.0, "resonance": 0.2, "drive": 1.0,
    "env_amt": 2500.0, "env_atk": 2.5, "env_dec": 1.0, "env_sus": 0.8, "env_rel": 4.0,
    "fm_on": 1, "fm_blend": 0.4, "fm_idx": 2.0, "fm_ratio": 4.0,
    "fm_env_amt": 3.0, "fm_env_atk": 3.0, "fm_env_dec": 2.0, "fm_env_sus": 0.5, "fm_env_rel": 4.0,
    "osc3_on": 1, "osc3_ratio": 0.5, "osc3_blend": 0.2,
    "d_on": 1, "d_time": 0.8, "d_feed": 0.75, "d_mix": 0.5,
    "a_on": 0, "a_bpm": 120.0, "a_rate": 0.25, "a_scale": "Major", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},

# Cosmic Harpsichord — plucked, metallic, spatial.
# Fast FM envelope and high ratio for the "pluck"; long delay trails for space.
"Cosmic Harpsichord": {
    "cutoff": 6000.0, "resonance": 0.3, "drive": 1.1,
    "env_amt": 2000.0, "env_atk": 0.001, "env_dec": 0.25, "env_sus": 0.0, "env_rel": 0.8,
    "fm_on": 1, "fm_blend": 0.4, "fm_idx": 5.0, "fm_ratio": 6.0,
    "fm_env_amt": 8.0, "fm_env_atk": 0.001, "fm_env_dec": 0.2, "fm_env_sus": 0.0, "fm_env_rel": 0.5,
    "osc3_on": 1, "osc3_ratio": 2.0, "osc3_blend": 0.15,
    "d_on": 1, "d_time": 0.45, "d_feed": 0.6, "d_mix": 0.35,
    "a_on": 0, "a_bpm": 120.0, "a_rate": 0.25, "a_scale": "Major", "a_oct": 1, "a_len": 4, "a_rnd": 0,
},

# Kid Icarus Arp — 8-bit NES style rapid arpeggio.
# Fast minor-scale arp and gated envelope for authentic chiptune feel.
"Kid Icarus Arp": {
    "cutoff": 9000.0, "resonance": 0.0, "drive": 1.0,
    "env_amt": 500.0, "env_atk": 0.001, "env_dec": 0.1, "env_sus": 0.5, "env_rel": 0.05,
    "fm_on": 1, "fm_blend": 0.3, "fm_idx": 1.0, "fm_ratio": 1.0,
    "fm_env_amt": 0.0, "fm_env_atk": 0.01, "fm_env_dec": 0.1, "fm_env_sus": 0.0, "fm_env_rel": 0.1,
    "osc3_on": 0, "osc3_ratio": 1.0, "osc3_blend": 0.0,
    "d_on": 0, "d_time": 0.3, "d_feed": 0.3, "d_mix": 0.0,
    "a_on": 1, "a_bpm": 140.0, "a_rate": 0.125, "a_scale": "Minor", "a_oct": 2, "a_len": 4, "a_rnd": 0,
},
}
