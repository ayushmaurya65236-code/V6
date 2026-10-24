"""Polyphonic procedural mixer preserved from AURA LINK V5."""

from __future__ import annotations

import threading

import numpy as np

import config

try:
    import sounddevice as sd

    _SD_AVAILABLE = True
except Exception:
    sd = None
    _SD_AVAILABLE = False


def _fade(wave_arr, sr=config.SAMPLE_RATE, fade_ms=15):
    n = int(sr * fade_ms / 1000)
    n = min(n, len(wave_arr) // 2)
    if n <= 0:
        return wave_arr
    out = wave_arr.copy()
    out[:n] *= np.linspace(0, 1, n)
    out[-n:] *= np.linspace(1, 0, n)
    return out


def _sine(freq, duration, sr=config.SAMPLE_RATE, amp=0.5):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    return np.sin(2 * np.pi * freq * t) * amp


def _sweep(f0, f1, duration, sr=config.SAMPLE_RATE, amp=0.3):
    n = int(sr * duration)
    freq = np.linspace(f0, f1, n)
    phase = 2 * np.pi * np.cumsum(freq) / sr
    return np.sin(phase) * amp


def _noise(duration, sr=config.SAMPLE_RATE, amp=0.08):
    return np.random.uniform(-1, 1, int(sr * duration)) * amp


def _mix(*waves):
    length = max(len(w) for w in waves)
    out = np.zeros(length)
    for w in waves:
        out[: len(w)] += w
    peak = np.max(np.abs(out)) if len(out) else 0
    if peak > 1:
        out /= peak
    return out


def gen_power_rumble(duration=0.9):
    return _fade(_sweep(40, 60, duration, amp=0.35) + _noise(duration, amp=0.03), fade_ms=40)


def gen_activation(duration=0.35):
    env = np.linspace(1, 0.2, int(config.SAMPLE_RATE * duration))
    return _fade(_sine(240, duration, amp=0.25) * env, fade_ms=10)


def gen_scan_sweep(duration=0.6):
    return _fade(_sweep(350, 2400, duration, amp=0.22))


def gen_click(duration=0.035, freq=1400):
    return _fade(_sine(freq, duration, amp=0.35), fade_ms=4)


def gen_rise(duration=0.8):
    return _fade(_sweep(220, 880, duration, amp=0.28))


def gen_confirm(duration=0.5):
    return _fade(
        _mix(
            _sine(130.81, duration, amp=0.30),
            _sine(261.63, duration, amp=0.22),
            _sine(392.00, duration, amp=0.16),
        ),
        fade_ms=30,
    )


def gen_pulse(duration=0.10, freq=880):
    return _fade(_sine(freq, duration, amp=0.25), fade_ms=6)


def gen_warning(duration=0.3):
    a = _sine(520, duration * 0.5, amp=0.25)
    b = _sine(360, duration * 0.5, amp=0.25)
    return _fade(np.concatenate([a, b]), fade_ms=10)


def gen_hand_acquire(duration=0.15):
    t1 = _sweep(1200, 2400, duration * 0.5, amp=0.25)
    t2 = _sine(2400, duration * 0.5, amp=0.22)
    return _fade(np.concatenate([t1, t2]), fade_ms=6)


def gen_hand_lost(duration=0.18):
    return _fade(_sweep(1800, 500, duration, amp=0.18), fade_ms=10)


def gen_led_on_harmonic(duration=0.28):
    bloom = _mix(
        _sine(523.25, duration * 0.5, amp=0.25),
        _sine(659.25, duration * 0.5, amp=0.25),
        _sine(783.99, duration * 0.5, amp=0.22),
    )
    sweep = _sweep(400, 1100, duration * 0.5, amp=0.18)
    return _fade(np.concatenate([sweep, bloom]), fade_ms=12)


def gen_led_off_harmonic(duration=0.28):
    bloom = _mix(
        _sine(783.99, duration * 0.5, amp=0.22),
        _sine(587.33, duration * 0.5, amp=0.22),
        _sine(392.00, duration * 0.5, amp=0.26),
    )
    sweep = _sweep(1100, 300, duration * 0.5, amp=0.18)
    return _fade(np.concatenate([bloom, sweep]), fade_ms=15)


def gen_system_reset():
    c1 = gen_click(0.04, freq=1600)
    gap = np.zeros(int(config.SAMPLE_RATE * 0.04))
    c2 = gen_click(0.04, freq=1200)
    return np.concatenate([c1, gap, c2])


def gen_power_down(duration=0.55):
    low = _sweep(160, 30, duration, amp=0.35)
    hiss = _noise(duration, amp=0.04) * np.linspace(1, 0, int(config.SAMPLE_RATE * duration))
    return _fade(low + hiss, fade_ms=30)


def gen_shutter(duration=0.12):
    env = np.exp(-np.linspace(0, 9, int(config.SAMPLE_RATE * duration)))
    return _fade(_noise(duration, amp=0.5) * env + _sine(2200, duration, amp=0.08) * env, fade_ms=3)


def gen_reconnect():
    a = _sine(660, 0.07, amp=0.22)
    b = _sine(880, 0.07, amp=0.22)
    c = _sine(1320, 0.12, amp=0.22)
    return _fade(np.concatenate([a, b, c]), fade_ms=6)


SOUND_FOR_LABEL = {
    "LED ON": "led_on",
    "LED OFF": "led_off",
    "LED BLINK": "pulse",
    "E-STOP": "warning",
}


class AudioEngine:
    MAX_VOICES = 12

    def __init__(self, volume: float = 0.8) -> None:
        self.available = _SD_AVAILABLE
        self.muted = not self.available
        self.volume = volume
        self._cache: dict[str, np.ndarray] = {}
        self._voices: list = []
        self._lock = threading.Lock()
        self._stream = None
        if self.available:
            try:
                self._build_cache()
                self._stream = sd.OutputStream(
                    samplerate=config.SAMPLE_RATE,
                    channels=1,
                    dtype="float32",
                    callback=self._callback,
                )
                self._stream.start()
            except Exception:
                self.available = False
                self.muted = True
                self._stream = None

    def _build_cache(self) -> None:
        sounds = {
            "power": gen_power_rumble(),
            "activate": gen_activation(),
            "scan": gen_scan_sweep(),
            "click": gen_click(),
            "rise": gen_rise(),
            "ready": gen_confirm(),
            "pulse": gen_pulse(),
            "warning": gen_warning(),
            "hand_acquire": gen_hand_acquire(),
            "hand_lost": gen_hand_lost(),
            "led_on": gen_led_on_harmonic(),
            "led_off": gen_led_off_harmonic(),
            "reset": gen_system_reset(),
            "power_down": gen_power_down(),
            "shutter": gen_shutter(),
            "reconnect": gen_reconnect(),
        }
        for name, raw in sounds.items():
            self._cache[name] = np.clip(raw, -1.0, 1.0).astype(np.float32)

    def _callback(self, outdata, frames, time_info, status) -> None:
        out = np.zeros(frames, dtype=np.float32)
        with self._lock:
            alive = []
            for data, pos, gain in self._voices:
                chunk = data[pos : pos + frames]
                out[: len(chunk)] += chunk * gain
                pos += frames
                if pos < len(data):
                    alive.append([data, pos, gain])
            self._voices = alive
        out *= self.volume
        np.clip(out, -1.0, 1.0, out=out)
        outdata[:, 0] = out

    def play(self, name: str, gain: float = 1.0) -> None:
        if not self.available or self.muted or name not in self._cache:
            return
        with self._lock:
            if len(self._voices) >= self.MAX_VOICES:
                self._voices.pop(0)
            self._voices.append([self._cache[name], 0, gain])

    def toggle_mute(self) -> None:
        if not self.available:
            return
        self.muted = not self.muted
        if not self.muted:
            self.play("click")

    def set_muted(self, muted: bool) -> None:
        if not self.available:
            self.muted = True
            return
        self.muted = bool(muted)

    def change_volume(self, delta: float) -> None:
        self.volume = max(0.0, min(1.0, self.volume + delta))
        self.play("click")

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(1.0, float(volume)))

    def close(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
