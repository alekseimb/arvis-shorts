"""Tipografía: títulos cinéticos, cifras, pastillas, cabecera de marca y subtítulos palabra a palabra.

Fuentes de google/fonts (SIL OFL 1.1) descargadas por arvis_lifehacks.recursos.
"""
import re

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from arvis_lifehacks import recursos

W, H = 1080, 1920
C = {"noche": (8, 12, 24), "cian": (0, 224, 255), "lima": (176, 255, 46), "blanco": (246, 248, 252), "aviso": (255, 200, 40),
     "rojo": (255, 84, 84), "verde": (64, 214, 120), "negro": (0, 0, 0), "gris": (160, 170, 190)}
_F = {}


def fuente(nombre, tam, peso=None):
    k = (nombre, int(tam), peso)
    if k not in _F:
        f = ImageFont.truetype(recursos.fuente(nombre), int(tam))
        if peso:
            try:
                vals = []
                for e in f.get_variation_axes():
                    n = e.get("name", b"")
                    n = n.decode() if isinstance(n, bytes) else str(n)
                    if "eight" in n or n.lower().startswith("wght"):
                        vals.append(max(e["minimum"], min(e["maximum"], peso)))
                    elif "ptical" in n or n.lower().startswith("opsz"):
                        vals.append(max(e["minimum"], min(e["maximum"], tam)))
                    else:
                        vals.append(e.get("default", e["minimum"]))
                f.set_variation_by_axes(vals)
            except Exception:
                pass
        _F[k] = f
    return _F[k]


def color(c):
    if isinstance(c, (list, tuple)):
        return tuple(c)
    return C.get(c, C["blanco"])


def _norm(w):
    return re.sub(r"[^\wáéíóúüñ%€]", "", w.lower())


def linea_sprite(texto, tam, resaltar=(), col="blanco", col_res="lima", fuente_n="Oswald.ttf", peso=700, borde=None, sombra=True):
    """Una línea de título (mayúsculas grandes) con palabras resaltadas, borde oscuro y sombra suave. RGBA recortado."""
    f = fuente(fuente_n, tam, peso)
    borde = borde if borde is not None else max(4, tam // 11)
    palabras = texto.split(" ")
    res = {_norm(r) for r in resaltar}
    d0 = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    esp = d0.textlength(" ", font=f)
    anchos = [d0.textlength(p, font=f) for p in palabras]
    ancho = int(sum(anchos) + esp * (len(palabras) - 1) + borde * 2 + 40)
    alto = int(tam * 1.45 + borde * 2 + 30)
    im = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x, y = 20 + borde, 12 + borde
    for p, a in zip(palabras, anchos):
        c = color(col_res) if _norm(p) in res else color(col)
        d.text((x, y), p, font=f, fill=c + (255,), stroke_width=borde, stroke_fill=(8, 10, 18, 255))
        x += a + esp
    if sombra:
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        sh.putalpha(im.getchannel("A").point(lambda v: int(v * 0.55)))
        sh = sh.filter(ImageFilter.GaussianBlur(10))
        base = Image.new("RGBA", (im.width, im.height + 12), (0, 0, 0, 0))
        base.alpha_composite(sh, (0, 12))
        base.alpha_composite(im, (0, 0))
        im = base
    bb = im.getbbox()
    return im.crop(bb) if bb else im


def ajustar_tam(lineas, tam, max_ancho=W - 120, fuente_n="Oswald.ttf", peso=700):
    d0 = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    while tam > 40:
        f = fuente(fuente_n, tam, peso)
        if all(d0.textlength(l, font=f) + tam * 0.25 <= max_ancho for l in lineas):
            return tam
        tam -= 4
    return tam


def pastilla(texto, tam=46, fondo="lima", col="noche", fuente_n="Inter.ttf", peso=900, pad=(30, 14), radio=None):
    f = fuente(fuente_n, tam, peso)
    d0 = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    bb = d0.textbbox((0, 0), texto, font=f)
    w, h = bb[2] - bb[0] + pad[0] * 2, bb[3] - bb[1] + pad[1] * 2
    im = Image.new("RGBA", (w + 16, h + 20), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([8, 12, w + 8, h + 12], radio or h // 2, fill=(0, 0, 0, 120))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([8, 6, w + 8, h + 6], radio or h // 2, fill=color(fondo) + (255,))
    d.text((8 + pad[0] - bb[0], 6 + pad[1] - bb[1]), texto, font=f, fill=color(col) + (255,))
    return im


def cifra_sprite(texto, tam, col="aviso"):
    return linea_sprite(texto, tam, (), col, col, "BebasNeue.ttf", None, borde=max(6, tam // 12))


# ----------------------------------------------------------------------------- cabecera
def cabecera(lienzo, chip, etiqueta, k_etq, progreso, col_etq="lima"):
    d = ImageDraw.Draw(lienzo)
    f = fuente("Inter.ttf", 32, 800)
    x0, y0 = 44, 92
    w = d.textlength(chip, font=f)
    d.rounded_rectangle([x0, y0, x0 + w + 58, y0 + 58], 29, fill=(10, 18, 34, 225), outline=C["cian"], width=3)
    d.ellipse([x0 + 20, y0 + 22, x0 + 34, y0 + 36], fill=C["lima"])
    d.text((x0 + 44, y0 + 10), chip, font=f, fill=C["blanco"])
    if etiqueta and k_etq > 0:
        fe = fuente("Inter.ttf", 32, 900)
        we = d.textlength(etiqueta, font=fe)
        x1 = W - 44
        dy = (1 - k_etq) * 14
        d.rounded_rectangle([x1 - we - 48, y0 + dy, x1, y0 + 58 + dy], 29, fill=color(col_etq))
        d.text((x1 - we - 24, y0 + 10 + dy), etiqueta, font=fe, fill=C["noche"])
    y = y0 + 80
    d.rounded_rectangle([x0, y, W - 44, y + 10], 5, fill=(30, 38, 58))
    d.rounded_rectangle([x0, y, x0 + (W - 88) * max(0.0, min(1.0, progreso)), y + 10], 5, fill=C["cian"])


# ----------------------------------------------------------------------------- subtítulos
SUBS_Y = 1330


_CONECT_NUM = {"y", "a", "o", "al", "-", "–", "x"}
_UNIDADES = {"%", "grados", "ºc", "°c", "º", "°", "euros", "€", "céntimos", "minutos", "min", "horas", "h", "segundos", "s",
             "días", "semanas", "meses", "años", "veces", "litros", "l", "ml", "kg", "g", "kilos", "gramos", "cm", "mm", "metros",
             "w", "kw", "kwh", "vatios"}
_ENLACE_NOMBRE = {"de", "del", "la", "las", "los", "y"}


def _limpia(w):
    return re.sub(r"[.!?…:,;«»\"()¿¡]", "", w)


def _num(w):
    return bool(re.search(r"\d", _limpia(w)))


def _cap(w):
    c = _limpia(w)
    return bool(c) and c[0].isupper()


def _cierra(w):
    return bool(re.search(r"[.!?…:,;]$", w))


def unidades(palabras):
    """Agrupa las palabras que no se deben separar en subtítulos: «18 y 20 grados», «40 %», «Comunidad de Madrid»."""
    ws = [p["w"] for p in palabras]
    out, i, n = [], 0, len(ws)
    while i < n:
        j = i + 1
        if _num(ws[i]) and not _cierra(ws[i]):
            # 18 y 20 · 55 a 60 · 3 x 2
            if j + 1 < n and _limpia(ws[j]).lower() in _CONECT_NUM and not _cierra(ws[j]) and _num(ws[j + 1]):
                j += 2
            # unidad detrás de la cifra (grados, %, euros…)
            if j < n and not _cierra(ws[j - 1]) and _limpia(ws[j]).lower() in _UNIDADES:
                j += 1
        elif _cap(ws[i]) and not _cierra(ws[i]):
            # Comunidad de Madrid · Banco de España · Castilla y León
            while j < n and not _cierra(ws[j - 1]):
                if _cap(ws[j]) and _limpia(ws[j - 1]).lower() not in _ENLACE_NOMBRE and j == i + 1 and i > 0:
                    j += 1
                    continue
                if (j + 1 < n and _limpia(ws[j]).lower() in _ENLACE_NOMBRE and not _cierra(ws[j]) and _cap(ws[j + 1])):
                    j += 2
                    continue
                break
        out.append(palabras[i:j])
        i = j
    return out


def bloques(palabras, max_pal=3, max_chars=22):
    """Bloques de subtítulos de ≤ 3 palabras sin partir cifras con su rango o unidad ni nombres propios compuestos."""
    out, cur = [], []
    for u in unidades(palabras):
        txt = " ".join(x["w"] for x in cur + u)
        if cur and (len(cur) + len(u) > max_pal or len(txt) > max_chars or _cierra(cur[-1]["w"])):
            out.append(cur)
            cur = []
        cur.extend(u)
    if cur:
        out.append(cur)
    i = 1
    while i < len(out):
        if len(out[i]) == 1 and len(out[i - 1]) <= 3 and not _cierra(out[i - 1][-1]["w"]) \
                and len(" ".join(x["w"] for x in out[i - 1] + out[i])) <= 26:
            out[i - 1].extend(out.pop(i))
            continue
        i += 1
    # una palabra corta suelta («La», «entre») se une al bloque siguiente si cabe en una línea
    i = 0
    while i < len(out) - 1:
        if len(out[i]) == 1 and len(_limpia(out[i][0]["w"])) <= 6 and not _cierra(out[i][0]["w"]) \
                and len(" ".join(x["w"] for x in out[i] + out[i + 1])) <= max_chars:
            suelta = out.pop(i)
            out[i] = suelta + out[i]
            continue
        i += 1
    return [{"t0": b[0]["t0"], "t1": b[-1]["t1"], "palabras": b} for b in out]


def subtitulo(lienzo, bloque, t):
    d = ImageDraw.Draw(lienzo)
    f = fuente("Inter.ttf", 74, 900)
    ws = bloque["palabras"]
    txt = [w["w"] for w in ws]
    anchos = [d.textlength(x, font=f) for x in txt]
    esp = d.textlength(" ", font=f)
    lineas, cur, ac = [], [], 0
    for i, a in enumerate(anchos):
        if cur and ac + esp + a > W - 170:
            lineas.append(cur)
            cur, ac = [], 0
        cur.append(i)
        ac += (esp if len(cur) > 1 else 0) + a
    lineas.append(cur)
    k = min(1.0, max(0.0, (t - bloque["t0"]) / 0.08))
    y = SUBS_Y + (1 - k) * 10
    for ln in lineas:
        tot = sum(anchos[i] for i in ln) + esp * (len(ln) - 1)
        x = (W - tot) / 2
        for i in ln:
            fin = ws[i + 1]["t0"] - 0.03 if i + 1 < len(ws) else ws[i]["t1"] + 0.06
            activa = ws[i]["t0"] - 0.03 <= t < fin
            d.text((x, y), txt[i], font=f, fill=C["lima"] if activa else C["blanco"], stroke_width=8, stroke_fill=(0, 0, 0))
            x += anchos[i] + esp
        y += 90
