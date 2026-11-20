"""Sonido: música propia (arvis_lifehacks.musica.base, compuesta por código) + efectos sintetizados + mezcla con ducking.

Efectos nuevos para la vida real: monedas, burbujas, error, éxito, tic (contador), salpicadura, «sube».
Ningún sonido de terceros: todo se genera aquí (sin licencias).
"""
import numpy as np
from scipy.signal import butter, lfilter

from arvis_lifehacks import musica

SR = 48000


def _hp(x, fc):
    b, a = butter(2, fc / (SR / 2), btype="high")
    return lfilter(b, a, x)


def _lp(x, fc):
    b, a = butter(2, fc / (SR / 2))
    return lfilter(b, a, x)


def efecto(tipo, rng):
    t = lambda s: np.arange(int(s * SR)) / SR  # noqa: E731
    if tipo in ("clic", "tecla", "whoosh", "pop", "ding"):
        return musica.efecto(tipo, rng)
    if tipo == "monedas":
        out = np.zeros(int(0.7 * SR))
        for k in range(5):
            tt = t(0.22)
            f = rng.uniform(2600, 4200)
            s = (np.sin(2 * np.pi * f * tt) + 0.6 * np.sin(2 * np.pi * f * 1.47 * tt)) * np.exp(-tt * 22) * 0.09
            a = int(k * 0.09 * SR)
            out[a:a + len(s)] += s[: len(out) - a]
        return out
    if tipo == "burbujas":
        out = np.zeros(int(0.6 * SR))
        for k in range(7):
            tt = t(0.07)
            f0 = rng.uniform(500, 1100)
            s = np.sin(2 * np.pi * (f0 + 1800 * tt / tt[-1]) * tt) * np.exp(-tt * 40) * 0.08
            a = int(rng.uniform(0, 0.5) * SR)
            out[a:a + len(s)] += s[: len(out) - a]
        return out
    if tipo == "error":
        tt = t(0.42)
        s = np.sign(np.sin(2 * np.pi * 150 * tt)) * 0.5 + np.sin(2 * np.pi * 300 * tt) * 0.5
        env = np.where(tt < 0.18, 1.0, np.where(tt < 0.22, 0.0, 1.0)) * np.exp(-tt * 3)
        return _lp(s * env, 1800) * 0.16
    if tipo == "exito":
        out = np.zeros(int(0.9 * SR))
        for k, f in enumerate((784.0, 987.8, 1318.5)):
            tt = t(0.5)
            s = (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * 2 * f * tt)) * np.exp(-tt * 7) * 0.12
            a = int(k * 0.09 * SR)
            out[a:a + len(s)] += s[: len(out) - a]
        return out
    if tipo == "tic":
        tt = t(0.03)
        return _hp(rng.standard_normal(len(tt)), 3000) * np.exp(-tt * 200) * 0.16
    if tipo == "salpicadura":
        tt = t(0.45)
        return _lp(_hp(rng.standard_normal(len(tt)), 600), 5000) * np.exp(-tt * 9) * 0.22
    if tipo == "sube":
        tt = t(0.4)
        return np.sin(2 * np.pi * (300 + 900 * (tt / tt[-1]) ** 2) * tt) * np.sin(np.pi * tt / tt[-1]) * 0.12
    if tipo == "golpe":
        tt = t(0.3)
        return np.sin(2 * np.pi * (60 + 90 * np.exp(-tt * 25)) * tt) * np.exp(-tt * 12) * 0.35
    return np.zeros(1)


def mezclar(voz, dur, efectos, semilla=0, nivel_musica_db=-19.0):
    """voz: array mono a 48 kHz. efectos: [(t, tipo)]. Devuelve estéreo float32 (sin normalizar: lo hace loudnorm)."""
    n = int(dur * SR)
    v = np.zeros(n)
    v[: min(n, len(voz))] = voz[:n]
    m = musica.base(dur, semilla, bpm=116)
    m = m[:n] if len(m) >= n else np.pad(m, (0, n - len(m)))
    m = m / (np.max(np.abs(m)) or 1) * 10 ** (nivel_musica_db / 20)
    env = np.convolve(np.abs(v), np.ones(int(0.12 * SR)) / int(0.12 * SR), mode="same")
    duck = np.where(env > 0.02, 10 ** (-7 / 20), 1.0)
    duck = np.convolve(duck, np.ones(int(0.2 * SR)) / int(0.2 * SR), mode="same")
    fx = np.zeros(n)
    rng = np.random.default_rng(semilla + 11)
    for t, tipo in efectos:
        e = efecto(tipo, rng)
        a = int(t * SR)
        if 0 <= a < n:
            fx[a:a + len(e)] += e[: n - a]
    mezcla = v * 0.95 + m * duck + fx * 0.9
    pico = np.max(np.abs(mezcla)) or 1
    if pico > 0.98:
        mezcla = mezcla / pico * 0.98
    return np.stack([mezcla, mezcla], axis=1).astype(np.float32)
