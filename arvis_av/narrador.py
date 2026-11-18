"""Narrador: voz sintética en español, gratuita y local (Piper + voz davefx, CC0).

La voz se obtiene sin coste del paquete de sherpa-onnx en GitHub Releases
(Hugging Face no es accesible desde los contenedores de las tareas programadas):
  https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-es_ES-davefx-medium.tar.bz2
Ruta configurable con ARVIS_VOZ. Intérprete con piper-tts instalado: ARVIS_PIPER_PY.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

VOZ = Path(os.environ.get("ARVIS_VOZ", "/home/user/voces/vits-piper-es_ES-davefx-medium/es_ES-davefx-medium.onnx"))
PY = os.environ.get("ARVIS_PIPER_PY", "python3.13")
URL_VOZ = ("https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/"
           "vits-piper-es_ES-davefx-medium.tar.bz2")


def duracion(f: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                         capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def sintetizar(texto: str, salida: Path, velocidad: float = 0.92) -> Path:
    """Genera WAV mono 22,05 kHz. velocidad <1 = más rápido (length_scale de Piper)."""
    if not VOZ.exists():
        raise FileNotFoundError(f"Voz no encontrada en {VOZ}. Descárgala de {URL_VOZ}")
    subprocess.run([PY, "-m", "piper", "-m", str(VOZ), "-f", str(salida), "--length-scale", str(velocidad)],
                   input=texto, text=True, check=True, capture_output=True)
    return salida
