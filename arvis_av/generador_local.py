"""Alternativa local y gratuita cuando no hay modelo generativo gratuito: FFmpeg.

No imita una IA generativa: crea fondos, tarjetas de texto y clips animados
(zoom/paneo tipo Ken Burns) a partir de colores, degradados o imágenes propias.
Sirve como recurso visual de relleno y como prueba real del motor de render.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

FUENTE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FORMATOS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}


def _esc(t: str) -> str:
    return t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace("%", "\\%")


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def imagen(texto: str, salida: Path, formato: str = "9:16",
           c0: str = "0x0b1d3a", c1: str = "0x1f6feb") -> Path:
    w, h = FORMATOS[formato]
    vf = (f"drawtext=fontfile={FUENTE}:text='{_esc(texto)}':fontcolor=white:fontsize={w // 14}:"
          f"x=(w-text_w)/2:y=(h-text_h)/2:box=1:boxcolor=black@0.35:boxborderw=30")
    _run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
          "-i", f"gradients=s={w}x{h}:c0={c0}:c1={c1}:x0=0:y0=0:x1={w}:y1={h}:d=1",
          "-vf", vf, "-frames:v", "1", "-update", "1", str(salida)])
    return salida


def clip_desde_imagen(img: Path, salida: Path, segundos: float = 4, formato: str = "9:16",
                      fps: int = 30) -> Path:
    """Anima una imagen con zoom suave (image-to-video local)."""
    w, h = FORMATOS[formato]
    n = int(segundos * fps)
    vf = (f"scale={w * 2}:{h * 2},zoompan=z='min(zoom+0.0012,1.25)':d={n}:"
          f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps},format=yuv420p")
    _run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(img), "-vf", vf,
          "-t", str(segundos), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(salida)])
    return salida
