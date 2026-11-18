"""Música de fondo y efectos generados por código (composición propia, sin licencias de terceros).

Base electrónica suave a 112 BPM (pads + arpegio + percusión ligera), siempre ≥ 16 dB por debajo de la voz
y con «ducking» automático cuando habla el narrador. Efectos: clic, tecleo, whoosh, pop y «ding» de resultado.
"""
import numpy as np
from scipy.signal import butter, lfilter

from .config import SR

ACORDES = [  # progresiones (frecuencias de La menor / Fa / Do / Sol y variantes) — una por semilla
    [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [261.63, 329.63, 392.0], [196.0, 246.94, 293.66]],
    [[196.0, 246.94, 293.66], [220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [261.63, 329.63, 392.0]],
    [[146.83, 174.61, 220.0], [174.61, 220.0, 261.63], [130.81, 164.81, 196.0], [196.0, 246.94, 293.66]],
]


def _lp(x, fc):
    b, a = butter(2, fc / (SR / 2))
    return lfilter(b, a, x)


def _hp(x, fc):
    b, a = butter(2, fc / (SR / 2), btype="high")
    return lfilter(b, a, x)


def base(dur, semilla=0, bpm=112):
    rng = np.random.default_rng(semilla)
    n = int(dur * SR) + SR
    out = np.zeros(n)
    beat = 60.0 / bpm
    compas = 4 * beat
    prog = ACORDES[semilla % len(ACORDES)]
    t_c = np.arange(int(compas * SR)) / SR
    env_pad = np.minimum(1, t_c / 0.4) * np.minimum(1, (compas - t_c) / 0.5)
    k = 0
    pos = 0
    while pos < n:
        ac = prog[k % len(prog)]
        pad = sum(np.sin(2 * np.pi * f * t_c + rng.uniform(0, 6)) + 0.4 * np.sin(2 * np.pi * f * 2.003 * t_c) for f in ac)
        seg = _lp(pad * env_pad * 0.06, 1800)
        # arpegio en semicorcheas
        paso = beat / 2
        tn = np.arange(int(paso * SR)) / SR
        env_n = np.exp(-tn * 9)
        for j in range(8):
            f = ac[j % 3] * (2 if j % 4 in (1, 3) else 1)
            nota = np.sin(2 * np.pi * f * tn) * env_n * 0.035
            a = int(j * paso * SR)
            seg[a:a + len(nota)] += nota[: len(seg) - a]
        # bombo suave y hi-hat
        for j in range(4):
            a = int(j * beat * SR)
            tk = np.arange(int(0.25 * SR)) / SR
            kick = np.sin(2 * np.pi * (55 + 70 * np.exp(-tk * 30)) * tk) * np.exp(-tk * 14) * 0.11
            seg[a:a + len(kick)] += kick[: len(seg) - a]
            h = int((j * beat + beat / 2) * SR)
            hat = _hp(rng.standard_normal(int(0.04 * SR)), 7000) * np.exp(-np.arange(int(0.04 * SR)) / SR * 90) * 0.02
            seg[h:h + len(hat)] += hat[: len(seg) - h]
        e = min(n, pos + len(seg))
        out[pos:e] += seg[: e - pos]
        pos += len(seg)
        k += 1
    out = out[: int(dur * SR)]
    fade = int(1.2 * SR)
    out[-fade:] *= np.linspace(1, 0, fade)
    out[: int(0.3 * SR)] *= np.linspace(0, 1, int(0.3 * SR))
    return out


def efecto(tipo, rng=None):
    rng = rng or np.random.default_rng(1)
    if tipo == "clic":
        t = np.arange(int(0.05 * SR)) / SR
        return _hp(rng.standard_normal(len(t)), 2500) * np.exp(-t * 160) * 0.35
    if tipo == "tecla":
        t = np.arange(int(0.03 * SR)) / SR
        return _hp(rng.standard_normal(len(t)), 3500) * np.exp(-t * 220) * 0.12
    if tipo == "whoosh":
        t = np.arange(int(0.35 * SR)) / SR
        ruido = _lp(rng.standard_normal(len(t)), 3000)
        return ruido * np.sin(np.pi * t / t[-1]) ** 2 * 0.18
    if tipo == "pop":
        t = np.arange(int(0.12 * SR)) / SR
        return np.sin(2 * np.pi * (520 + 500 * t / t[-1]) * t) * np.exp(-t * 30) * 0.22
    if tipo == "ding":
        t = np.arange(int(0.9 * SR)) / SR
        return (np.sin(2 * np.pi * 1318.5 * t) + 0.5 * np.sin(2 * np.pi * 1975.5 * t)) * np.exp(-t * 5) * 0.16
    return np.zeros(1)


def mezclar(voz, dur, efectos, semilla=0, nivel_musica_db=-17.0):
    """voz: array a SR. efectos: [(t, tipo)]. Devuelve la mezcla estéreo float32."""
    n = int(dur * SR)
    v = np.zeros(n)
    v[: min(n, len(voz))] = voz[:n]
    m = base(dur, semilla)
    m = m[:n] if len(m) >= n else np.pad(m, (0, n - len(m)))
    m = m / (np.max(np.abs(m)) or 1) * 10 ** (nivel_musica_db / 20)
    # ducking: baja 6 dB la música mientras hay voz
    env = np.convolve(np.abs(v), np.ones(int(0.12 * SR)) / int(0.12 * SR), mode="same")
    duck = np.where(env > 0.02, 10 ** (-6 / 20), 1.0)
    duck = np.convolve(duck, np.ones(int(0.2 * SR)) / int(0.2 * SR), mode="same")
    fx = np.zeros(n)
    rng = np.random.default_rng(semilla + 7)
    for t, tipo in efectos:
        e = efecto(tipo, rng)
        a = int(t * SR)
        if 0 <= a < n:
            fx[a:a + len(e)] += e[: n - a]
    mezcla = v * 0.92 + m * duck + fx
    pico = np.max(np.abs(mezcla)) or 1
    if pico > 0.98:
        mezcla = mezcla / pico * 0.98
    return np.stack([mezcla, mezcla], axis=1).astype(np.float32)
