"""Recursos libres descargados de GitHub (la red disponible en las tareas de ARVIS).

Reutiliza la caché del motor v4 (~/.cache/arvis_expedientes): voz Piper es_ES-davefx-medium (CC0)
y fuentes de google/fonts (SIL OFL 1.1).
"""
import os
import subprocess
import tarfile

from .config import CACHE

FUENTES = {
    "Inter.ttf": "ofl/inter/Inter%5Bopsz,wght%5D.ttf",
    "JetBrainsMono.ttf": "ofl/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf",
    "BebasNeue.ttf": "ofl/bebasneue/BebasNeue-Regular.ttf",
    "Oswald.ttf": "ofl/oswald/Oswald%5Bwght%5D.ttf",
}
MODELOS_VOZ = {   # voces Piper es_ES publicadas en GitHub (sherpa-onnx, release tts-models)
    "davefx": "es_ES-davefx-medium",        # CC0
    "sharvard": "es_ES-sharvard-medium",    # CC BY 3.0 (corpus Sharvard, Universidad de Edimburgo): crédito obligatorio
    "carlfm": "es_ES-carlfm-x_low",         # dominio público (MODEL_CARD), 16 kHz
}
VOZ_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-%s.tar.bz2"


def _bajar(url, dest, intentos=3):
    if os.path.exists(dest) and os.path.getsize(dest) > 1000:
        return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    err = None
    for _ in range(intentos):
        r = subprocess.run(["curl", "-sSL", "--fail", "-m", "300", "-o", dest + ".part", url], capture_output=True, text=True)
        if r.returncode == 0 and os.path.getsize(dest + ".part") > 1000:
            os.replace(dest + ".part", dest)
            return dest
        err = r.stderr
    raise RuntimeError("No se pudo descargar %s: %s" % (url, err))


def fuente(nombre):
    return _bajar("https://raw.githubusercontent.com/google/fonts/main/" + FUENTES[nombre], os.path.join(CACHE, "fonts", nombre))


def modelo_voz(nombre="sharvard"):
    m = MODELOS_VOZ[nombre]
    d = os.path.join(CACHE, "voice")
    onnx = os.path.join(d, "vits-piper-" + m, m + ".onnx")
    if os.path.exists(onnx):
        return onnx
    arc = _bajar(VOZ_URL % m, os.path.join(d, nombre + ".tar.bz2"))
    with tarfile.open(arc) as t:
        m = [x for x in t.getmembers() if x.name.endswith((".onnx", ".onnx.json", "MODEL_CARD"))]
        t.extractall(d, members=m, filter="data")
    return onnx


def preparar():
    for f in FUENTES:
        fuente(f)
    modelo_voz("sharvard")
    return CACHE


if __name__ == "__main__":
    print(preparar())
