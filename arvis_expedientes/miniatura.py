"""Parche v4.2 · miniatura 1280×720 del vídeo largo (≤ 2 MB, lo que admite YouTube).

Fondo: la imagen de la escena elegida («cover_scene»), recortada a 16:9. Texto corto y grande (≤ 5 palabras,
«thumbnail_text» del guion), palabra clave en ámbar, degradado para que se lea en el móvil. Sin logotipos ajenos.
"""
import os

import numpy as np
from PIL import Image, ImageDraw

from . import gfx as G

TW, TH = 1280, 720


def crear(S, plates_dir, destino):
    k = S.get("cover_scene", 0)
    v = S["scenes"][k].get("visual", {})
    src = os.path.join(plates_dir, (v.get("plate") or "") + ".png")
    if v.get("type") == "plate" and os.path.exists(src):
        im = Image.open(src).convert("RGB")
    else:
        im = Image.new("RGB", (TW, TH), (14, 14, 18))
    r = max(TW / im.width, TH / im.height)
    im = im.resize((int(im.width * r + 0.5), int(im.height * r + 0.5)), Image.LANCZOS)
    x0, y0 = (im.width - TW) // 2, (im.height - TH) // 2
    im = im.crop((x0, y0, x0 + TW, y0 + TH))
    a = np.asarray(im, np.float32) / 255.0
    xx = np.linspace(0, 1, TW, dtype=np.float32)[None, :, None]
    a = a * (0.38 + 0.62 * np.clip(xx * 1.6 - 0.15, 0, 1))          # oscurece la izquierda para el texto
    a = np.clip((a - 0.5) * 1.12 + 0.5, 0, 1)
    img = Image.fromarray((a * 255).astype(np.uint8)).convert("RGBA")
    texto = (S.get("thumbnail_text") or S.get("case_title") or S["title"]).upper().split()[:5]
    clave = set(w.upper() for w in S.get("thumbnail_keywords", []))
    f = G.F("Oswald.ttf", 112, 700)
    lineas, cur = [], []
    for w in texto:
        prueba = " ".join(cur + [w])
        if G.text_size(f, prueba)[0] > 700 and cur:
            lineas.append(cur)
            cur = [w]
        else:
            cur.append(w)
    lineas.append(cur)
    y = TH // 2 - len(lineas) * 64
    for ln in lineas:
        x = 60
        for w in ln:
            col = G.AMBER + (255,) if w in clave else (255, 255, 255, 255)
            G.shadow_text(img, (x, y), w, f, fill=col, shadow=12, sop=230, stroke=3, stroke_fill=(0, 0, 0, 255))
            x += G.text_size(f, w + " ")[0]
        y += 128
    if S.get("serie_tag"):
        d = ImageDraw.Draw(img)
        ft = G.F("Oswald.ttf", 34, 600)
        tw = G.text_size(ft, S["serie_tag"])[0]
        d.rounded_rectangle([56, 48, 56 + tw + 36, 100], radius=8, fill=(196, 30, 30, 235))
        d.text((74, 74), S["serie_tag"], font=ft, fill=(255, 255, 255, 255), anchor="lm")
    out = img.convert("RGB")
    calidad = 92
    while True:
        out.save(destino, "JPEG", quality=calidad, optimize=True)
        if os.path.getsize(destino) <= 1_900_000 or calidad <= 60:
            break
        calidad -= 8
    return destino
