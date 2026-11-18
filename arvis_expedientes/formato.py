"""Parche v4.2 · formato de salida del motor v4 (9:16 Shorts o 16:9 vídeo largo).

El motor v4 trabaja en vertical (720×1280 → 1080×1920). aplicar("16:9") cambia sus dimensiones globales
(comp.WW/WH, render.OUT_W/OUT_H, viñeta y ruido) para trabajar en 1280×720 → 1920×1080 sin tocar sus archivos.
Llamar ANTES de crear escenas, grano o ruido.
"""
from . import comp as C
from . import render as R

FORMATOS = {
    "9:16": {"out": (1080, 1920), "work": (720, 1280), "subtitulos_y": 1240, "cabecera_y": 118, "miniatura_kf": (108, 192)},
    "16:9": {"out": (1920, 1080), "work": (1280, 720), "subtitulos_y": 930, "cabecera_y": None, "miniatura_kf": (192, 108)},
}


def aplicar(fmt):
    if fmt not in FORMATOS:
        raise ValueError("formato desconocido: %s (9:16 o 16:9)" % fmt)
    f = FORMATOS[fmt]
    C.WW, C.WH = f["work"]
    C._VIG = None
    C.Noise2D.__init__.__defaults__ = (0, C.WW, C.WH)
    R.OUT_W, R.OUT_H = f["out"]
    return dict(f, formato=fmt)
