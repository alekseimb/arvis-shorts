"""Narración en español de España con Piper (local, gratis).

Voz de LIFEHACKS: «sharvard_m» = es_ES-sharvard-medium, hablante masculino, ajustes naturales del modelo.
Elegida por Aleksei el 18/11/2026 tras escuchar 4 muestras («No me gusta la voz, quiero que sea más natural»).
Licencia CC BY 3.0: la descripción de cada vídeo lleva el crédito (config.CREDITO_VOZ).
Adaptado de arvis_expedientes/voice.py (motor v4); davefx (CC0) queda como alternativa.
Devuelve el audio y el tiempo de cada palabra (repartido por fonemas dentro de cada frase; Piper sintetiza
frase a frase, así que el error queda dentro de la frase: suficiente para subtítulos de 1–4 palabras).
"""
import os
import re

import numpy as np
from scipy.signal import lfilter, resample_poly

from . import recursos
from .config import SR

_VOCES = {}
PRESETS = {
    # nombre: (modelo, hablante, length_scale, noise_scale, noise_w, ecualización)
    "sharvard_m": ("sharvard", 0, 1.0, 0.667, 0.8, None),          # LIFEHACKS desde el 18/11/2026
    "davefx_natural": ("davefx", None, 1.04, 0.75, 0.9, None),
    "davefx_tuto": ("davefx", None, 0.96, 0.62, 0.8, "corr"),       # la del primer montaje (descartada por Aleksei)
    "davefx": ("davefx", None, 1.06, 0.667, 0.8, "corr"),
    # ARVIS 5.0 (26/11/2026, Aleksei: «quiero que la voz sea más divertida»): más rápidas, más variación de entonación,
    # tono algo más agudo (sin cambiar la duración ni el timbre: rubberband con formantes conservados) y más brillo.
    # 7.º campo = semitonos.
    "sharvard_animado": ("sharvard", 0, 0.88, 0.80, 0.95, "brillo", 1.5),
    "davefx_animado": ("davefx", None, 0.90, 0.80, 0.95, "corr", 1.0),
    "sharvard_show": ("sharvard", 0, 0.84, 0.90, 1.0, "brillo", 2.5),
    # Más opciones (26/11/2026, Aleksei: «dame más opciones»)
    "sharvard_f_animada": ("sharvard", 1, 0.88, 0.80, 0.95, "brillo", 1.0),    # chica animada
    "sharvard_f_show": ("sharvard", 1, 0.84, 0.90, 1.0, "brillo", 2.0),        # chica muy enérgica
    "davefx_show": ("davefx", None, 0.84, 0.90, 1.0, "corr", 2.5),             # chico muy enérgico
    "davefx_radio": ("davefx", None, 0.92, 0.75, 0.90, "radio", -1.0),         # locutor de radio con gracia
    "sharvard_cartoon": ("sharvard", 0, 0.86, 0.90, 1.0, "brillo", 5.0),       # dibujos animados
    "carlfm_animado": ("carlfm", None, 0.90, 0.80, 0.95, "brillo", 1.0),       # otra voz de chico (calidad más baja, 16 kHz)
}


def _preset(nombre):
    p = PRESETS.get(nombre, PRESETS["sharvard_m"])
    return p[:6], (p[6] if len(p) > 6 else 0.0)


def _tono(x, semitonos):
    """Sube o baja el tono sin cambiar la duración (ffmpeg + rubberband, formantes conservados). Determinista."""
    if not semitonos:
        return x
    import subprocess
    import tempfile
    from scipy.io import wavfile
    with tempfile.TemporaryDirectory() as d:
        a, b = os.path.join(d, "a.wav"), os.path.join(d, "b.wav")
        wavfile.write(a, SR, x.astype(np.float32))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", a, "-af",
                        "rubberband=pitch=%.5f:formant=preserved:pitchq=quality" % (2 ** (semitonos / 12.0)),
                        "-c:a", "pcm_f32le", "-ar", str(SR), b], check=True)
        y = wavfile.read(b)[1].astype(np.float64)
    if len(y) >= len(x):
        return y[:len(x)]
    return np.concatenate([y, np.zeros(len(x) - len(y))])


def _voz(modelo):
    if modelo not in _VOCES:
        from piper import PiperVoice
        _VOCES[modelo] = PiperVoice.load(recursos.modelo_voz(modelo))
    return _VOCES[modelo]


def _peq(x, f0, gain_db, q=0.9, kind="peak"):
    A = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * f0 / SR
    alpha = np.sin(w0) / (2 * q)
    cw = np.cos(w0)
    sA = np.sqrt(A)
    if kind == "peak":
        b = [1 + alpha * A, -2 * cw, 1 - alpha * A]
        a = [1 + alpha / A, -2 * cw, 1 - alpha / A]
    elif kind == "low":
        b = [A * ((A + 1) - (A - 1) * cw + 2 * sA * alpha), 2 * A * ((A - 1) - (A + 1) * cw), A * ((A + 1) - (A - 1) * cw - 2 * sA * alpha)]
        a = [(A + 1) + (A - 1) * cw + 2 * sA * alpha, -2 * ((A - 1) + (A + 1) * cw), (A + 1) + (A - 1) * cw - 2 * sA * alpha]
    else:
        b = [A * ((A + 1) + (A - 1) * cw + 2 * sA * alpha), -2 * A * ((A - 1) + (A + 1) * cw), A * ((A + 1) + (A - 1) * cw - 2 * sA * alpha)]
        a = [(A + 1) - (A - 1) * cw + 2 * sA * alpha, 2 * ((A - 1) - (A + 1) * cw), (A + 1) - (A - 1) * cw - 2 * sA * alpha]
    b = np.array(b) / a[0]
    a = np.array(a) / a[0]
    return lfilter(b, a, x)


def _acabado(x, eq):
    if eq == "corr":   # parche de voz v2 del 13/11/2026: cuerpo, menos nasal, más aire
        x = _peq(x, 120, 3, 0.7, "low")
        x = _peq(x, 1400, -5, 1.0)
        x = _peq(x, 5000, 4, 0.7, "high")
    elif eq == "radio":    # locutor: cuerpo en graves, presencia y aire
        x = _peq(x, 120, 3, 0.7, "low")
        x = _peq(x, 2500, 2, 0.9)
        x = _peq(x, 6000, 2, 0.7, "high")
    elif eq == "brillo":   # ARVIS 5.0 «más divertida»: menos peso en graves, más presencia y aire
        x = _peq(x, 150, -2, 0.7, "low")
        x = _peq(x, 3000, 3, 0.9)
        x = _peq(x, 7000, 3, 0.7, "high")
    return x


def _frases(texto, n):
    partes = [p for p in re.split(r"(?<=[.!?…])\s+", texto) if p.strip()]
    if len(partes) == n:
        return partes
    if n == 1:
        return [texto]
    while len(partes) > n:
        partes[-2] += " " + partes.pop()
    while len(partes) < n:
        partes.append("")
    return partes


class _Trozo:
    def __init__(self, audio, fonemas, sr=22050):
        self.audio_float_array = audio
        self.phonemes = fonemas
        self.sr = sr


def _piper(texto, preset, ritmo, cache=None):
    """Trozos de Piper. Con `cache` (carpeta), la voz se guarda la primera vez (int16, 22 050 Hz, comprimida) y se reutiliza:
    Piper no es determinista (ruido aleatorio), así que volver a montar el mismo guion daría otra entonación y otros tiempos.
    Con la caché, el vídeo que aprobó Aleksei se puede reconstruir igual (ARVIS 5.0)."""
    import hashlib
    clave = hashlib.sha1(("%s|%.4f|%s" % (preset, ritmo, texto)).encode("utf-8")).hexdigest()[:16]
    ruta = os.path.join(cache, clave + ".npz") if cache else None
    if ruta and os.path.exists(ruta):
        z = np.load(ruta, allow_pickle=False)
        n = int(z["n"])
        sr = int(z["sr"]) if "sr" in z else 22050
        return [_Trozo(z["a%d" % i].astype(np.float32) / 32767.0, list(str(z["f%d" % i])), sr) for i in range(n)]
    from piper.config import SynthesisConfig
    (modelo, hablante, ls, ns, nw, eq), _ = _preset(preset)
    v = _voz(modelo)
    trozos = list(v.synthesize(texto, syn_config=SynthesisConfig(speaker_id=hablante, length_scale=ls * ritmo,
                                                                 noise_scale=ns, noise_w_scale=nw)))
    sr = int(getattr(getattr(v, "config", None), "sample_rate", 22050) or 22050)
    q = [np.clip(np.round(ch.audio_float_array.astype(np.float64) * 32767), -32767, 32767).astype(np.int16) for ch in trozos]
    f = ["".join(ch.phonemes) if ch.phonemes else "" for ch in trozos]
    if ruta:
        os.makedirs(cache, exist_ok=True)
        datos = {"n": np.array(len(q)), "sr": np.array(sr)}
        for i, (a, fo) in enumerate(zip(q, f)):
            datos["a%d" % i], datos["f%d" % i] = a, np.array(fo)
        np.savez_compressed(ruta + ".part.npz", **datos)
        os.replace(ruta + ".part.npz", ruta)
    return [_Trozo(a.astype(np.float32) / 32767.0, list(fo), sr) for a, fo in zip(q, f)]


def sintetizar(texto, preset="sharvard_m", ritmo=1.0, cache=None):
    """Devuelve (audio float32 48 kHz mono, [{w, t0, t1}]). ritmo < 1 = más rápido (solo para ajustar el gancho).
    cache: carpeta donde guardar/reutilizar la voz de este guion (ver _piper)."""
    (modelo, hablante, ls, ns, nw, eq), semitonos = _preset(preset)
    texto = re.sub(r"\s+", " ", texto).strip()
    trozos = _piper(texto, preset, ritmo, cache)
    piezas, palabras, t, hueco = [], [], 0.0, 0.0
    for ch, ftxt in zip(trozos, _frases(texto, len(trozos))):
        from math import gcd
        sr0 = getattr(ch, "sr", 22050)
        k = gcd(SR, sr0)
        a = resample_poly(ch.audio_float_array.astype(np.float64), SR // k, sr0 // k)   # 22050 (o 16000) → 48000
        nz = np.where(np.abs(a) > 0.01)[0]
        if len(nz):
            a = a[max(0, nz[0] - int(0.02 * SR)): nz[-1] + int(0.06 * SR)]
        dur = len(a) / SR
        ws = ftxt.split()
        fon = [w for w in ("".join(ch.phonemes) if ch.phonemes else ftxt).split(" ") if w]
        pesos = []
        for i, w in enumerate(ws):
            n = len(fon[i]) if len(fon) == len(ws) else max(1, len(re.sub(r"\W", "", w)))
            if re.search(r"[,;:]$", w):
                n += 3
            pesos.append(max(1, n))
        tot, acc, lead = float(sum(pesos) or 1), 0.0, 0.03
        span = max(0.1, dur - lead - 0.05)
        for w, p in zip(ws, pesos):
            w0 = t + lead + span * acc / tot
            acc += p
            palabras.append({"w": w, "t0": round(w0, 3), "t1": round(t + lead + span * acc / tot, 3)})
        piezas.append(a)
        hueco = 0.30 if ftxt.rstrip().endswith(("?", "!")) else 0.24
        piezas.append(np.zeros(int(hueco * SR)))
        t += dur + hueco
    if piezas:
        piezas.pop()
        t -= hueco
    audio = np.concatenate(piezas) if piezas else np.zeros(1)
    audio = _tono(_acabado(audio, eq), semitonos)
    pico = float(np.max(np.abs(audio))) or 1.0
    return (audio / pico * 0.85).astype(np.float32), palabras
