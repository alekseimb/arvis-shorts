"""Escenarios dibujados por ARVIS (SVG propio): cocina, lavadero, baño, salón, dormitorio, despensa y estudio.

Se dibujan a 1242×2208 (un 15 % más que el fotograma) para que la cámara virtual pueda acercarse y desplazarse.
Zonas: la encimera / el suelo quedan por debajo de y≈0,60 del fotograma, donde se apoyan los objetos.
Paletas variadas por escenario (evita que todos los vídeos parezcan iguales); semilla = variación de color.
"""
import random

from . import activos

BW, BH = 1242, 2208           # fondo
OX, OY = 81, 144              # margen respecto al fotograma de 1080×1920


def _y(fr):
    """Fracción del fotograma (0–1) → coordenada y del fondo."""
    return OY + fr * 1920


def _svg(cuerpo, defs=""):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d"><defs>%s'
            '<radialGradient id="vig" cx="0.5" cy="0.42" r="0.75"><stop offset="0.55" stop-color="#000" stop-opacity="0"/>'
            '<stop offset="1" stop-color="#000" stop-opacity="0.55"/></radialGradient>'
            '<linearGradient id="arriba" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#050913" stop-opacity="0.85"/>'
            '<stop offset="1" stop-color="#050913" stop-opacity="0"/></linearGradient>'
            '<linearGradient id="abajo" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#050913" stop-opacity="0"/>'
            '<stop offset="1" stop-color="#050913" stop-opacity="0.8"/></linearGradient>'
            '</defs>%s'
            '<rect width="%d" height="%d" fill="url(#vig)"/>'
            '<rect width="%d" height="560" fill="url(#arriba)"/>'
            '<rect y="%d" width="%d" height="%d" fill="url(#abajo)"/></svg>'
            % (BW, BH, BW, BH, defs, cuerpo, BW, BH, BW, int(_y(0.62)), BW, int(BH - _y(0.62))))


def _azulejos(color, junta, w=120, h=60, desfase=True, y0=0, y1=BH):
    ids = "az%d%d" % (w, h)
    defs = ('<pattern id="%s" width="%d" height="%d" patternUnits="userSpaceOnUse">'
            '<rect width="%d" height="%d" fill="%s"/>'
            '<rect x="2" y="2" width="%d" height="%d" rx="6" fill="%s"/>'
            '<rect x="2" y="2" width="%d" height="10" rx="5" fill="#ffffff" opacity="0.18"/>'
            '%s</pattern>' % (ids, w, h * 2, w, h * 2, junta, w - 4, h - 4, color, w - 4,
                              ('<rect x="%d" y="%d" width="%d" height="%d" rx="6" fill="%s"/><rect x="%d" y="%d" width="%d" height="%d" rx="6" fill="%s"/>'
                               % (-w // 2 + 2, h + 2, w - 4, h - 4, color, w // 2 + 2, h + 2, w - 4, h - 4, color)) if desfase
                              else '<rect x="2" y="%d" width="%d" height="%d" rx="6" fill="%s"/>' % (h + 2, w - 4, h - 4, color)))
    return defs, '<rect y="%d" width="%d" height="%d" fill="url(#%s)"/>' % (y0, BW, y1 - y0, ids)


def _luz(cx, cy, r, color="#fff7e0", op=0.35):
    return ('<radialGradient id="luz%d" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="%s" stop-opacity="%s"/>'
            '<stop offset="1" stop-color="%s" stop-opacity="0"/></radialGradient>' % (cx, color, op, color),
            '<circle cx="%d" cy="%d" r="%d" fill="url(#luz%d)"/>' % (cx, cy, r, cx))


PALETAS = {
    "cocina": [("#f3e9dc", "#d9c8b4", "#2f6f73", "#e8d7c3", "#8a5a3c"), ("#e6f0ea", "#c4d6cb", "#3d5a80", "#f1e3d3", "#6b4f3a"),
               ("#fbeee6", "#e3cbbd", "#264653", "#e9d8c4", "#7a4b2a")],
    "lavadero": [("#dcecf5", "#b7cfdd", "#5aa9c9", "#c9d6e2"), ("#e7e4f3", "#c8c3dd", "#7b6cc4", "#d3d0e6"), ("#e0f1ec", "#bcd8cf", "#2a9d8f", "#cfe1db")],
    "bano": [("#d8f0f0", "#b2d6d6", "#ffffff", "#9fc9c9"), ("#efe6f6", "#d2c4e2", "#ffffff", "#b9a8cf")],
    "salon": [("#f2e8d5", "#c98f5f", "#7aa56b", "#a86f45"), ("#e4ecf4", "#9a7b5f", "#d1785a", "#7d5c42")],
    "dormitorio": [("#efe3ea", "#c9a9b8", "#8fb8de", "#a77e66"), ("#e8f0e3", "#b9c9a9", "#e6a57e", "#8c6b52")],
    "despensa": [("#f4ead7", "#cfb48c", "#b5835a"), ("#ece7df", "#bfb3a2", "#8c7055")],
    "estudio": [("#1b2a4a", "#0b1224", "#00e0ff"), ("#2a1b4a", "#110b24", "#b0ff2e"), ("#123a3a", "#071b1b", "#ffd23f")],
}


def cocina(p):
    pared, junta, armario, encimera, madera = p
    defs, azul = _azulejos(pared, junta, 110, 56)
    yc = _y(0.60)
    d2, luz = _luz(620, int(_y(0.30)), 700)
    cuerpo = (azul +
              # muebles altos
              '<rect x="0" y="0" width="%d" height="%d" fill="%s"/>' % (BW, int(_y(0.08)), armario) +
              "".join('<rect x="%d" y="10" width="300" height="%d" rx="14" fill="%s" stroke="#00000022" stroke-width="4"/>'
                      '<rect x="%d" y="%d" width="80" height="12" rx="6" fill="#ffffffaa"/>' % (x, int(_y(0.08)) - 30, armario, x + 110, int(_y(0.08)) - 70)
                      for x in (10, 320, 630, 940)) + luz +
              # encimera y muebles bajos
              '<rect x="0" y="%d" width="%d" height="46" fill="%s"/>' % (yc, BW, encimera) +
              '<rect x="0" y="%d" width="%d" height="12" fill="#ffffff" opacity="0.5"/>' % (yc, BW) +
              '<rect x="0" y="%d" width="%d" height="%d" fill="%s"/>' % (yc + 46, BW, BH - yc - 46, madera) +
              "".join('<rect x="%d" y="%d" width="296" height="%d" rx="12" fill="#ffffff10" stroke="#00000033" stroke-width="4"/>'
                      '<rect x="%d" y="%d" width="90" height="14" rx="7" fill="#e8e1d6"/>' % (x, yc + 70, BH - yc - 90, x + 103, yc + 110)
                      for x in (12, 322, 632, 942)))
    return _svg(cuerpo, defs + d2)


def lavadero(p):
    pared, junta, acento, suelo = p
    defs, azul = _azulejos(pared, junta, 150, 150, desfase=False, y1=int(_y(0.66)))
    ys = int(_y(0.66))
    d2, luz = _luz(900, int(_y(0.18)), 620, "#ffffff", 0.45)
    cuerpo = (azul + luz +
              '<rect x="760" y="%d" width="380" height="300" rx="20" fill="#ffffff" stroke="#00000022" stroke-width="6"/>' % int(_y(0.04)) +
              '<rect x="780" y="%d" width="340" height="260" rx="12" fill="#bfe6ff"/>' % (int(_y(0.04)) + 20) +
              '<line x1="950" y1="%d" x2="950" y2="%d" stroke="#ffffff" stroke-width="10"/>' % (int(_y(0.04)) + 20, int(_y(0.04)) + 280) +
              '<rect x="60" y="%d" width="520" height="22" rx="8" fill="%s"/>' % (int(_y(0.12)), acento) +
              '<rect x="90" y="%d" width="70" height="120" rx="16" fill="%s"/><rect x="180" y="%d" width="56" height="90" rx="14" fill="#ffffff"/>'
              '<rect x="256" y="%d" width="80" height="110" rx="18" fill="#ffd23f"/>' % (int(_y(0.12)) - 120, acento, int(_y(0.12)) - 90, int(_y(0.12)) - 110) +
              '<rect x="0" y="%d" width="%d" height="%d" fill="%s"/>' % (ys, BW, BH - ys, suelo) +
              "".join('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#00000018" stroke-width="5"/>' % (621 + (x - 621) * 0.3, ys, x, BH)
                      for x in range(-600, 1900, 250)) +
              '<rect x="0" y="%d" width="%d" height="14" fill="#00000022"/>' % (ys, BW))
    return _svg(cuerpo, defs + d2)


def bano(p):
    pared, junta, lavabo, acento = p
    defs, azul = _azulejos(pared, junta, 90, 90, desfase=False)
    yc = int(_y(0.60))
    cuerpo = (azul +
              '<rect x="300" y="%d" width="640" height="560" rx="40" fill="#ffffff" opacity="0.55" stroke="%s" stroke-width="12"/>' % (int(_y(0.04)), acento) +
              '<path d="M380 %d L520 %d" stroke="#ffffff" stroke-width="22" opacity="0.6" stroke-linecap="round"/>' % (int(_y(0.04)) + 120, int(_y(0.04)) + 60) +
              '<rect x="0" y="%d" width="%d" height="60" fill="%s"/>' % (yc, BW, lavabo) +
              '<rect x="0" y="%d" width="%d" height="%d" fill="%s"/>' % (yc + 60, BW, BH - yc - 60, acento))
    return _svg(cuerpo, defs)


def salon(p):
    pared, suelo, planta, mueble = p
    ys = int(_y(0.64))
    d2, luz = _luz(850, int(_y(0.2)), 800, "#fff2c6", 0.5)
    cuerpo = ('<rect width="%d" height="%d" fill="%s"/>' % (BW, BH, pared) + luz +
              '<rect x="640" y="%d" width="480" height="640" rx="18" fill="#cfe9ff" stroke="#ffffff" stroke-width="22"/>' % int(_y(0.02)) +
              '<line x1="880" y1="%d" x2="880" y2="%d" stroke="#ffffff" stroke-width="14"/>' % (int(_y(0.02)), int(_y(0.02)) + 640) +
              '<path d="M600 %d Q640 %d 610 %d L700 %d L690 %d Z" fill="#e9c46a" opacity="0.9"/>' % (int(_y(0.0)), int(_y(0.2)), int(_y(0.38)), int(_y(0.38)), int(_y(0.0))) +
              '<rect x="0" y="%d" width="%d" height="%d" fill="%s"/>' % (ys, BW, BH - ys, suelo) +
              "".join('<rect x="0" y="%d" width="%d" height="6" fill="#00000014"/>' % (y, BW) for y in range(ys + 60, BH, 90)) +
              '<rect x="60" y="%d" width="330" height="190" rx="20" fill="%s"/>' % (ys - 190, mueble) +
              '<ellipse cx="200" cy="%d" rx="80" ry="140" fill="%s"/>' % (ys - 330, planta) +
              '<rect x="160" y="%d" width="80" height="110" rx="12" fill="#c06c49"/>' % (ys - 300))
    return _svg(cuerpo, d2)


def dormitorio(p):
    pared, armario, acento, suelo = p
    ys = int(_y(0.66))
    cuerpo = ('<rect width="%d" height="%d" fill="%s"/>' % (BW, BH, pared) +
              '<rect x="40" y="%d" width="1160" height="%d" rx="20" fill="%s"/>' % (int(_y(0.0)), ys - int(_y(0.0)), armario) +
              "".join('<rect x="%d" y="%d" width="370" height="%d" rx="14" fill="#ffffff22" stroke="#00000022" stroke-width="5"/>'
                      '<rect x="%d" y="%d" width="16" height="140" rx="8" fill="%s"/>' % (x, int(_y(0.0)) + 20, ys - int(_y(0.0)) - 40, x + (330 if i % 2 == 0 else 24),
                                                                                       int(_y(0.36)), acento) for i, x in enumerate((60, 435, 810))) +
              '<rect x="0" y="%d" width="%d" height="%d" fill="%s"/>' % (ys, BW, BH - ys, suelo))
    return _svg(cuerpo)


def despensa(p):
    pared, balda, madera = p
    cuerpo = '<rect width="%d" height="%d" fill="%s"/>' % (BW, BH, pared)
    for y in (0.08, 0.30, 0.52):
        yy = int(_y(y))
        cuerpo += '<rect x="30" y="%d" width="1180" height="30" rx="8" fill="%s"/><rect x="30" y="%d" width="1180" height="8" fill="#ffffff55"/>' % (yy, madera, yy)
    cuerpo += '<rect x="0" y="%d" width="%d" height="%d" fill="%s"/>' % (int(_y(0.62)), BW, BH - int(_y(0.62)), balda)
    return _svg(cuerpo)


def estudio(p):
    a, b, acento = p
    cuerpo = ('<radialGradient id="eg" cx="0.5" cy="0.38" r="0.8"><stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/></radialGradient>' % (a, b))
    lineas = "".join('<line x1="%d" y1="0" x2="%d" y2="%d" stroke="%s" stroke-opacity="0.05" stroke-width="3"/>' % (x, x, BH, acento) for x in range(0, BW, 90))
    lineas += "".join('<line x1="0" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-opacity="0.05" stroke-width="3"/>' % (y, BW, y, acento) for y in range(0, BH, 90))
    suelo = '<ellipse cx="621" cy="%d" rx="560" ry="90" fill="%s" opacity="0.10"/>' % (int(_y(0.62)), acento)
    return _svg('<rect width="%d" height="%d" fill="url(#eg)"/>' % (BW, BH) + lineas + suelo, cuerpo)


ESCENARIOS = {"cocina": cocina, "lavadero": lavadero, "bano": bano, "salon": salon, "dormitorio": dormitorio,
              "despensa": despensa, "estudio": estudio}


def fondo(nombre, semilla=0):
    """Devuelve una Image RGB de 1242×2208 con el escenario."""
    if nombre not in ESCENARIOS:
        nombre = "estudio"
    pal = PALETAS[nombre][semilla % len(PALETAS[nombre])]
    return activos.svg_a_png(ESCENARIOS[nombre](pal), BW, BH).convert("RGB")


if __name__ == "__main__":
    from PIL import Image
    ims = [fondo(n, random.randint(0, 2)).resize((414, 736)) for n in ESCENARIOS]
    hoja = Image.new("RGB", (414 * len(ims), 736))
    for i, im in enumerate(ims):
        hoja.paste(im, (414 * i, 0))
    hoja.save("/tmp/vida_test/fondos.png")
