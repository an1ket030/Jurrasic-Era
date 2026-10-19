"""
audio.py — Prehistoric Sound & Ambient Music Engine for JurassicEra.

Features:
  • Procedural synthesis of 3 atmospheric prehistoric ambient music loops:
      1. "Cretaceous Dawn"   — Warm ambient pad, deep tribal drone, gentle winds
      2. "Primeval Jungle"   — Shimmering water resonance, mysterious jungle chirps, low marimba
      3. "Titan's Domain"    — Deep rhythmic percussion, majestic brass chords, tense pulse
  • Procedural prehistoric sound effects (SFX):
      - roar:          Deep guttural apex predator roar
      - chirp:         High frequency herbivore call
      - footstep:      Heavy dinosaur ground thud
      - splash:        Water splash when drinking / wading
      - thunder:       Low reverberant thunder clap
      - god_power:     Celestial shimmer for admin actions
      - meteor_boom:   Cataclysmic explosion with seismic bass
  • Complete volume controls, track switching, and mute support.
"""

from __future__ import annotations

import math
import threading
import time
from typing import Callable

import numpy as np
import pygame

SAMPLE_RATE = 44100


def _make_stereo(mono: np.ndarray) -> np.ndarray:
    """Ensure audio array is int16 stereo (N, 2)."""
    mono = np.clip(mono, -32767, 32767).astype(np.int16)
    return np.column_stack([mono, mono])


def _synthesize_track_dawn(duration_s: float = 12.0) -> pygame.mixer.Sound:
    """Track 1: Cretaceous Dawn — Atmospheric low drone, warm pentatonic pads, wind."""
    n_samples = int(SAMPLE_RATE * duration_s)
    t = np.linspace(0, duration_s, n_samples, endpoint=False)
    
    # 1. Deep 55 Hz (A1) resonant tribal drone with gentle pulse
    drone = np.sin(2 * np.pi * 55.0 * t) * 6000
    drone += np.sin(2 * np.pi * 110.0 * t) * 3000
    drone *= (0.8 + 0.2 * np.sin(2 * np.pi * 0.2 * t))
    
    # 2. Pentatonic chords (D minor / F / G / A): 146.8 Hz, 174.6 Hz, 220.0 Hz, 261.6 Hz
    pad = np.zeros(n_samples)
    chord_freqs = [
        [146.83, 220.00, 293.66],  # Dm
        [174.61, 261.63, 349.23],  # F
        [196.00, 246.94, 293.66],  # G
        [220.00, 261.63, 329.63],  # Am
    ]
    section_len = n_samples // len(chord_freqs)
    for i, chord in enumerate(chord_freqs):
        idx_start = i * section_len
        idx_end = (i + 1) * section_len
        t_sec = t[idx_start:idx_end] - t[idx_start]
        dur_sec = duration_s / len(chord_freqs)
        # Smooth attack-decay envelope
        env = np.sin(np.pi * (t_sec / dur_sec)) ** 2
        for f in chord:
            pad[idx_start:idx_end] += (
                np.sin(2 * np.pi * f * t_sec)
                + 0.3 * np.sin(2 * np.pi * f * 2 * t_sec)
            ) * 1800 * env

    # 3. Soft tribal conga/djembe hits every 2 seconds
    percussion = np.zeros(n_samples)
    beat_interval = int(SAMPLE_RATE * 2.0)
    for b in range(0, n_samples, beat_interval):
        hit_len = min(SAMPLE_RATE, n_samples - b)
        t_hit = np.linspace(0, hit_len / SAMPLE_RATE, hit_len, endpoint=False)
        hit_env = np.exp(-12.0 * t_hit)
        pitch_drop = 90.0 * np.exp(-15.0 * t_hit) + 45.0
        hit = np.sin(2 * np.pi * pitch_drop * t_hit) * 7000 * hit_env
        percussion[b : b + hit_len] += hit

    # 4. Wind / atmospheric breath (filtered white noise)
    noise = np.random.uniform(-1, 1, n_samples)
    # Simple low pass via moving average
    kernel_size = 80
    kernel = np.ones(kernel_size) / kernel_size
    wind = np.convolve(noise, kernel, mode="same") * 2500
    wind *= (0.5 + 0.5 * np.sin(2 * np.pi * 0.15 * t))

    # Seamless loop crossfade (last 0.8s fades into start)
    mix = drone + pad + percussion + wind
    fade_len = int(SAMPLE_RATE * 0.8)
    fade_in = np.linspace(0, 1, fade_len)
    fade_out = np.linspace(1, 0, fade_len)
    mix[:fade_len] = mix[:fade_len] * fade_in + mix[-fade_len:] * fade_out
    mix = mix[:-fade_len]

    return pygame.sndarray.make_sound(_make_stereo(mix))


def _synthesize_track_jungle(duration_s: float = 10.0) -> pygame.mixer.Sound:
    """Track 2: Primeval Jungle — Shimmering water drops, eerie jungle echoes, warm pad."""
    n_samples = int(SAMPLE_RATE * duration_s)
    t = np.linspace(0, duration_s, n_samples, endpoint=False)
    
    # Low ambient hum (65 Hz)
    hum = np.sin(2 * np.pi * 65.4 * t) * 4000

    # Resonant water drops / marimba pings at random intervals
    drops = np.zeros(n_samples)
    pitches = [440.0, 523.25, 659.25, 783.99, 880.0, 1046.5]
    np.random.seed(42)
    step = int(SAMPLE_RATE * 0.75)
    for p in range(0, n_samples - SAMPLE_RATE // 2, step):
        freq = np.random.choice(pitches)
        d_len = int(SAMPLE_RATE * 0.5)
        t_d = np.linspace(0, 0.5, d_len, endpoint=False)
        d_env = np.exp(-14.0 * t_d)
        d_wave = (
            np.sin(2 * np.pi * freq * t_d)
            + 0.4 * np.sin(2 * np.pi * freq * 2.02 * t_d)
        ) * 3500 * d_env
        drops[p : p + d_len] += d_wave

    # Prehistoric whistle / flute melody
    flute = np.zeros(n_samples)
    flute_notes = [220.0, 261.6, 293.6, 329.6, 392.0]
    sub_dur = duration_s / len(flute_notes)
    for i, fn in enumerate(flute_notes):
        st = int(i * sub_dur * SAMPLE_RATE)
        ed = min(n_samples, int((i + 1) * sub_dur * SAMPLE_RATE))
        t_sub = t[st:ed] - t[st]
        env = np.sin(np.pi * (t_sub / sub_dur)) ** 1.5
        vibrato = 1.0 + 0.015 * np.sin(2 * np.pi * 5.0 * t_sub)
        wave = np.sin(2 * np.pi * fn * vibrato * t_sub) * 2800 * env
        flute[st:ed] += wave

    mix = hum + drops + flute
    fade_len = int(SAMPLE_RATE * 0.6)
    fade_in = np.linspace(0, 1, fade_len)
    fade_out = np.linspace(1, 0, fade_len)
    mix[:fade_len] = mix[:fade_len] * fade_in + mix[-fade_len:] * fade_out
    mix = mix[:-fade_len]

    return pygame.sndarray.make_sound(_make_stereo(mix))


def _synthesize_track_titans(duration_s: float = 12.0) -> pygame.mixer.Sound:
    """Track 3: Titan's Domain — Heavy marching drums, majestic brass, ominous heart."""
    n_samples = int(SAMPLE_RATE * duration_s)
    t = np.linspace(0, duration_s, n_samples, endpoint=False)

    # Marching heavy footsteps / primal drums (every 1.5s)
    drums = np.zeros(n_samples)
    step = int(SAMPLE_RATE * 1.5)
    for s in range(0, n_samples, step):
        d_len = min(int(SAMPLE_RATE * 0.8), n_samples - s)
        t_d = np.linspace(0, d_len / SAMPLE_RATE, d_len, endpoint=False)
        env = np.exp(-7.0 * t_d)
        boom = (
            np.sin(2 * np.pi * (80.0 * np.exp(-12.0 * t_d) + 38.0) * t_d) * 9000
            + np.sin(2 * np.pi * 55.0 * t_d) * 4000
        ) * env
        drums[s : s + d_len] += boom

    # Brass swelling chords (low C / G / D#): 65.4 Hz, 98.0 Hz, 155.5 Hz
    brass = np.zeros(n_samples)
    chord = [65.41, 98.00, 130.81, 155.56]
    for f in chord:
        # Sawtooth harmonic approximation
        w = np.zeros(n_samples)
        for h in range(1, 6):
            w += (1.0 / h) * np.sin(2 * np.pi * f * h * t)
        pulse = 0.5 + 0.5 * np.sin(2 * np.pi * 0.33 * t)
        brass += w * 1800 * pulse

    mix = drums + brass
    fade_len = int(SAMPLE_RATE * 0.8)
    fade_in = np.linspace(0, 1, fade_len)
    fade_out = np.linspace(1, 0, fade_len)
    mix[:fade_len] = mix[:fade_len] * fade_in + mix[-fade_len:] * fade_out
    mix = mix[:-fade_len]

    return pygame.sndarray.make_sound(_make_stereo(mix))


def _synthesize_sfx(name: str) -> pygame.mixer.Sound:
    """Synthesize a specific sound effect on demand."""
    if name == "roar":
        # Deep guttural dinosaur roar (1.2s)
        dur = 1.2
        n = int(SAMPLE_RATE * dur)
        t = np.linspace(0, dur, n, endpoint=False)
        env = np.sin(np.pi * (t / dur)) ** 0.5 * np.exp(-1.5 * t)
        pitch = 110.0 - 45.0 * (t / dur) + 15.0 * np.sin(2 * np.pi * 35.0 * t)
        growl = np.sin(2 * np.pi * pitch * t) * 14000
        growl += np.sin(2 * np.pi * (pitch * 1.5) * t) * 8000
        noise = np.random.uniform(-1, 1, n) * 5000 * env
        mix = (growl * env) + noise
        return pygame.sndarray.make_sound(_make_stereo(mix))

    if name == "chirp":
        # Herbivore / hatchling chirp (0.35s)
        dur = 0.35
        n = int(SAMPLE_RATE * dur)
        t = np.linspace(0, dur, n, endpoint=False)
        env = np.sin(np.pi * (t / dur)) ** 2
        f = 900.0 + 600.0 * np.sin(2 * np.pi * 18.0 * t)
        mix = np.sin(2 * np.pi * f * t) * 9000 * env
        return pygame.sndarray.make_sound(_make_stereo(mix))

    if name == "footstep":
        # Heavy ground thud (0.3s)
        dur = 0.3
        n = int(SAMPLE_RATE * dur)
        t = np.linspace(0, dur, n, endpoint=False)
        env = np.exp(-18.0 * t)
        pitch = 75.0 * np.exp(-25.0 * t) + 35.0
        mix = np.sin(2 * np.pi * pitch * t) * 12000 * env
        return pygame.sndarray.make_sound(_make_stereo(mix))

    if name == "splash":
        # Water splash (0.45s)
        dur = 0.45
        n = int(SAMPLE_RATE * dur)
        t = np.linspace(0, dur, n, endpoint=False)
        env = np.exp(-10.0 * t)
        noise = np.random.uniform(-1, 1, n) * 9000 * env
        tone = np.sin(2 * np.pi * 320.0 * t) * 4000 * env
        return pygame.sndarray.make_sound(_make_stereo(noise + tone))

    if name == "thunder":
        # Thunder rumble (2.0s)
        dur = 2.0
        n = int(SAMPLE_RATE * dur)
        t = np.linspace(0, dur, n, endpoint=False)
        env = np.exp(-2.2 * t)
        noise = np.random.uniform(-1, 1, n) * 12000 * env
        low_sub = np.sin(2 * np.pi * 42.0 * t) * 14000 * env
        return pygame.sndarray.make_sound(_make_stereo(noise + low_sub))

    if name == "god_power":
        # Shimmering celestial magic chord for admin actions (0.7s)
        dur = 0.7
        n = int(SAMPLE_RATE * dur)
        t = np.linspace(0, dur, n, endpoint=False)
        env = np.sin(np.pi * (t / dur)) ** 1.2
        mix = np.zeros(n)
        for freq in [523.25, 659.25, 783.99, 1046.50, 1318.51]:
            mix += np.sin(2 * np.pi * freq * t) * 3500 * env
        return pygame.sndarray.make_sound(_make_stereo(mix))

    if name == "meteor_boom":
        # Massive seismic impact boom (3.0s)
        dur = 3.0
        n = int(SAMPLE_RATE * dur)
        t = np.linspace(0, dur, n, endpoint=False)
        env = np.exp(-1.8 * t)
        pitch = 140.0 * np.exp(-6.0 * t) + 30.0
        boom = np.sin(2 * np.pi * pitch * t) * 18000 * env
        noise = np.random.uniform(-1, 1, n) * 12000 * env
        return pygame.sndarray.make_sound(_make_stereo(boom + noise))

    # Fallback pop
    dur = 0.1
    n = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    return pygame.sndarray.make_sound(_make_stereo(np.sin(2 * np.pi * 440.0 * t) * 5000 * np.exp(-30.0 * t)))


class SoundEngine:
    """Manages background music playback and game sound effects."""

    TRACK_NAMES = ["Cretaceous Dawn", "Primeval Jungle", "Titan's Domain"]

    def __init__(self) -> None:
        self.enabled: bool = False
        self.music_volume: float = 0.65
        self.sfx_volume: float = 0.80
        self.current_track_idx: int = 0
        self.is_muted: bool = False

        self._tracks: list[pygame.mixer.Sound] = []
        self._sfx: dict[str, pygame.mixer.Sound] = {}
        self._music_channel: pygame.mixer.Channel | None = None
        self._sfx_channel: pygame.mixer.Channel | None = None
        self._initialized: bool = False

    def init(self) -> None:
        """Initialise mixer and synthesize music & sound assets."""
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2, buffer=1024)
            pygame.mixer.set_num_channels(16)
            self._music_channel = pygame.mixer.Channel(0)
            self._sfx_channel   = pygame.mixer.Channel(1)

            # Synthesize 3 ambient music tracks
            self._tracks = [
                _synthesize_track_dawn(),
                _synthesize_track_jungle(),
                _synthesize_track_titans(),
            ]

            # Pre-cache core SFX
            for name in ["roar", "chirp", "footstep", "splash", "thunder", "god_power", "meteor_boom"]:
                self._sfx[name] = _synthesize_sfx(name)

            self._initialized = True
            self.enabled = True
            self.play_music(self.current_track_idx)
        except Exception as e:
            print(f"[SoundEngine] Warning: Audio init failed ({e}). Running silent.")
            self.enabled = False

    def play_music(self, track_idx: int) -> None:
        if not self._initialized or not self.enabled or not self._music_channel:
            return
        if self.is_muted:
            return
        self.current_track_idx = track_idx % len(self._tracks)
        sound = self._tracks[self.current_track_idx]
        sound.set_volume(self.music_volume)
        self._music_channel.stop()
        self._music_channel.play(sound, loops=-1)

    def next_track(self) -> str:
        new_idx = (self.current_track_idx + 1) % len(self.TRACK_NAMES)
        self.play_music(new_idx)
        return self.TRACK_NAMES[self.current_track_idx]

    def prev_track(self) -> str:
        new_idx = (self.current_track_idx - 1) % len(self.TRACK_NAMES)
        self.play_music(new_idx)
        return self.TRACK_NAMES[self.current_track_idx]

    def toggle_mute(self) -> bool:
        self.is_muted = not self.is_muted
        if not self._music_channel:
            return self.is_muted
        if self.is_muted:
            self._music_channel.pause()
        else:
            self._music_channel.unpause()
            if not self._music_channel.get_busy():
                self.play_music(self.current_track_idx)
        return self.is_muted

    def set_music_volume(self, vol: float) -> None:
        self.music_volume = max(0.0, min(1.0, vol))
        if self._music_channel and not self.is_muted:
            self._music_channel.set_volume(self.music_volume)

    def play_sfx(self, name: str, volume: float = 1.0) -> None:
        if not self._initialized or not self.enabled or self.is_muted:
            return
        sound = self._sfx.get(name)
        if sound is None:
            try:
                sound = _synthesize_sfx(name)
                self._sfx[name] = sound
            except Exception:
                return
        sound.set_volume(max(0.0, min(1.0, volume * self.sfx_volume)))
        # Find an available SFX channel (channels 1-15)
        ch = pygame.mixer.find_channel(True)
        if ch and ch != self._music_channel:
            ch.play(sound)


# Global audio singleton
sound_engine = SoundEngine()
