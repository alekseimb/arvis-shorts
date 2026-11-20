"""Aparatos y objetos de la casa dibujados por ARVIS (SVG propio, sin licencias de terceros).

Cada prop devuelve capas SVG con el mismo viewBox; el motor las rasteriza una vez y anima algunas:
  «girar» (tambor de la lavadora, aguja del selector), «mover» (tapa de la olla, clavija), «revelar» (columna del termómetro),
  «brillo» (zona de la placa, luz del microondas: opacidad animada).
Uso en el guion: {"activo": "lavadora", "estado": {"pantalla": "40°"}, "capas": {"tambor": {"girar": 140}}}
"""

GRAD = """<linearGradient id="{id}" x1="0" y1="0" x2="{x2}" y2="{y2}">{stops}</linearGradient>"""


def _grad(id_, colores, vertical=True):
    stops = "".join('<stop offset="%s" stop-color="%s"/>' % (o, c) for o, c in colores)
    return GRAD.format(id=id_, x2=0 if vertical else 1, y2=1 if vertical else 0, stops=stops)


def _svg(w, h, cuerpo, defs=""):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d"><defs>%s</defs>%s</svg>'
            % (w, h, w, h, defs, cuerpo))


def _sombra(cx, cy, rx, ry, op=0.28):
    return ('<defs><radialGradient id="sh"><stop offset="0" stop-color="#000" stop-opacity="%s"/>'
            '<stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient></defs>'
            '<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="url(#sh)"/>' % (op, cx, cy, rx, ry))


def _texto(x, y, txt, tam, color="#0b1220", peso=800, anchor="middle"):
    txt = str(txt).replace("&", "&amp;").replace("<", "").replace(">", "")
    return ('<text x="%s" y="%s" font-family="Inter, DejaVu Sans, sans-serif" font-size="%s" font-weight="%s" fill="%s" '
            'text-anchor="%s" dominant-baseline="central">%s</text>' % (x, y, tam, peso, color, anchor, txt))


# ----------------------------------------------------------------------------- lavadora
def lavadora(pantalla="40°", ropa=("#ff5d73", "#3fa7ff", "#ffd23f", "#7bd389"), agua=True, eco=False):
    W, H = 400, 500
    d = (_grad("cuerpo", [(0, "#ffffff"), (0.55, "#eef1f6"), (1, "#cfd6e2")]) + _grad("panel", [(0, "#e6eaf1"), (1, "#c9d1de")])
         + _grad("aro", [(0, "#f7f9fc"), (0.5, "#a9b3c4"), (1, "#eef2f7")]) + _grad("agua", [(0, "#8fd3ff"), (1, "#2d7fd8")])
         + '<radialGradient id="int" cx="0.5" cy="0.45" r="0.6"><stop offset="0" stop-color="#3a4558"/><stop offset="1" stop-color="#151b26"/></radialGradient>')
    base = _sombra(200, 488, 190, 14) + (
        '<rect x="14" y="10" width="372" height="470" rx="34" fill="url(#cuerpo)" stroke="#b9c2d0" stroke-width="3"/>'
        '<rect x="14" y="10" width="372" height="96" rx="34" fill="url(#panel)"/><rect x="14" y="70" width="372" height="36" fill="url(#panel)"/>'
        '<line x1="20" y1="106" x2="380" y2="106" stroke="#aeb7c6" stroke-width="3"/>'
        '<rect x="44" y="34" width="70" height="44" rx="10" fill="#f9fbff" stroke="#9aa6b8" stroke-width="2"/>'
        '<rect x="44" y="34" width="70" height="20" rx="10" fill="#ffffff" opacity="0.6"/>'
        '<rect x="168" y="36" width="104" height="44" rx="10" fill="#0f2233"/>'
        + _texto(220, 58, pantalla, 30, "#4ff0ff", 800)
        + '<circle cx="320" cy="57" r="14" fill="%s"/>' % ("#7be86a" if eco else "#d4dae4")
        + ('' if not eco else _texto(320, 57, "ECO", 9, "#0b3a12", 900))
        + '<circle cx="356" cy="57" r="10" fill="#d4dae4"/>'
        '<circle cx="200" cy="300" r="146" fill="url(#aro)" stroke="#9aa5b6" stroke-width="3"/>'
        '<circle cx="200" cy="300" r="122" fill="url(#int)"/>'
        '<rect x="150" y="452" width="100" height="10" rx="5" fill="#c1c9d6"/>')
    if agua:
        base += ('<clipPath id="cv"><circle cx="200" cy="300" r="118"/></clipPath>'
                 '<rect x="70" y="330" width="260" height="110" fill="url(#agua)" opacity="0.75" clip-path="url(#cv)"/>')
    prendas = ""
    formas = [(150, 260, 52, 30, 20), (250, 270, 46, 34, -30), (200, 350, 58, 30, 10), (140, 340, 34, 26, 50), (262, 345, 38, 24, -60)]
    for i, (x, y, rx, ry, rot) in enumerate(formas):
        c = ropa[i % len(ropa)]
        prendas += ('<g transform="rotate(%d %d %d)"><ellipse cx="%d" cy="%d" rx="%d" ry="%d" fill="%s"/>'
                    '<ellipse cx="%d" cy="%d" rx="%d" ry="%d" fill="#fff" opacity="0.18"/></g>'
                    % (rot, x, y, x, y, rx, ry, c, x - rx * 0.3, y - ry * 0.35, rx * 0.45, ry * 0.3))
    agujeros = "".join('<circle cx="%d" cy="%d" r="4" fill="#0e131c" opacity="0.5"/>' % (200 + 104 * __import__("math").cos(a / 6.0),
                                                                                         300 + 104 * __import__("math").sin(a / 6.0)) for a in range(0, 38, 3))
    tambor = ('<clipPath id="ct"><circle cx="200" cy="300" r="118"/></clipPath><g clip-path="url(#ct)">' + agujeros + prendas + '</g>')
    cristal = ('<path d="M120 230 A110 110 0 0 1 250 190" stroke="#ffffff" stroke-width="14" fill="none" opacity="0.35" stroke-linecap="round"/>'
               '<circle cx="200" cy="300" r="122" fill="none" stroke="#0e131c" stroke-width="6"/>'
               '<rect x="330" y="270" width="18" height="60" rx="9" fill="#aab4c4"/>')
    return {"w": W, "h": H, "capas": [
        {"id": "base", "svg": _svg(W, H, base, d)},
        {"id": "tambor", "svg": _svg(W, H, tambor, d), "pivote": (200, 300)},
        {"id": "cristal", "svg": _svg(W, H, cristal, d)},
    ], "clave": "lavadora colada lavar ropa electrodoméstico"}


# ----------------------------------------------------------------------------- nevera
def nevera(pantalla="5°C", pantalla2="-18°C"):
    W, H = 300, 600
    d = _grad("cn", [(0, "#ffffff"), (0.6, "#eef1f6"), (1, "#cdd4df")], vertical=False)
    base = _sombra(150, 590, 150, 12) + (
        '<rect x="12" y="8" width="276" height="574" rx="26" fill="url(#cn)" stroke="#b5bfcd" stroke-width="3"/>'
        '<line x1="14" y1="392" x2="286" y2="392" stroke="#aeb7c6" stroke-width="4"/>'
        '<rect x="234" y="70" width="16" height="130" rx="8" fill="#aeb8c8"/>'
        '<rect x="234" y="420" width="16" height="90" rx="8" fill="#aeb8c8"/>'
        '<rect x="42" y="56" width="120" height="54" rx="12" fill="#0f2233"/>' + _texto(102, 83, pantalla, 30, "#4ff0ff", 800)
        + '<rect x="42" y="414" width="120" height="44" rx="10" fill="#0f2233"/>' + _texto(102, 436, pantalla2, 24, "#9fd8ff", 800)
        + '<path d="M30 30 L30 360" stroke="#ffffff" stroke-width="8" opacity="0.5" stroke-linecap="round"/>')
    return {"w": W, "h": H, "capas": [{"id": "base", "svg": _svg(W, H, base, d)}], "clave": "nevera frigorífico congelador frío"}


# ----------------------------------------------------------------------------- microondas
def microondas(pantalla="1:30"):
    W, H = 500, 320
    d = (_grad("cm", [(0, "#f6f8fb"), (1, "#c9d1dd")]) + '<radialGradient id="luz" cx="0.5" cy="0.6" r="0.7"><stop offset="0" stop-color="#ffe9a3"/>'
         '<stop offset="1" stop-color="#e0a93a" stop-opacity="0.85"/></radialGradient>')
    base = _sombra(250, 310, 240, 12) + (
        '<rect x="10" y="10" width="480" height="290" rx="26" fill="url(#cm)" stroke="#b3bdcb" stroke-width="3"/>'
        '<rect x="34" y="36" width="322" height="238" rx="18" fill="#1d2532"/>'
        '<rect x="380" y="40" width="88" height="40" rx="8" fill="#0f2233"/>' + _texto(424, 60, pantalla, 24, "#4ff0ff", 800)
        + "".join('<circle cx="%d" cy="%d" r="11" fill="#d7dde6" stroke="#aeb7c6"/>' % (398 + 26 * (i % 3), 112 + 30 * (i // 3)) for i in range(9))
        + '<rect x="384" y="214" width="80" height="34" rx="10" fill="#7be86a"/>')
    luz = '<rect x="46" y="48" width="298" height="214" rx="12" fill="url(#luz)" opacity="0.9"/>'
    cristal = ('<rect x="34" y="36" width="322" height="238" rx="18" fill="none" stroke="#0b0f16" stroke-width="6"/>'
               '<path d="M60 70 L150 70" stroke="#fff" stroke-width="10" opacity="0.25" stroke-linecap="round"/>')
    return {"w": W, "h": H, "capas": [{"id": "base", "svg": _svg(W, H, base, d)}, {"id": "luz", "svg": _svg(W, H, luz, d)},
                                      {"id": "cristal", "svg": _svg(W, H, cristal, d)}], "clave": "microondas calentar comida sobras"}


# ----------------------------------------------------------------------------- horno
def horno():
    W, H = 440, 420
    d = (_grad("ch", [(0, "#4b5566"), (1, "#222a36")]) + '<radialGradient id="fh" cx="0.5" cy="0.5" r="0.7"><stop offset="0" stop-color="#ffb347"/>'
         '<stop offset="1" stop-color="#c2410c" stop-opacity="0.9"/></radialGradient>')
    base = _sombra(220, 410, 210, 12) + (
        '<rect x="10" y="10" width="420" height="390" rx="24" fill="url(#ch)" stroke="#121821" stroke-width="3"/>'
        + "".join('<circle cx="%d" cy="50" r="18" fill="#c9d1dd" stroke="#8b96a8" stroke-width="3"/>'
                  '<line x1="%d" y1="50" x2="%d" y2="36" stroke="#4b5566" stroke-width="5" stroke-linecap="round"/>' % (70 + 75 * i, 70 + 75 * i, 70 + 75 * i) for i in range(5))
        + '<rect x="60" y="104" width="320" height="22" rx="11" fill="#c9d1dd"/>'
        '<rect x="44" y="146" width="352" height="226" rx="20" fill="#0d1118"/>')
    luz = '<rect x="58" y="160" width="324" height="198" rx="14" fill="url(#fh)" opacity="0.85"/>'
    cristal = '<path d="M76 186 L190 186" stroke="#fff" stroke-width="10" opacity="0.2" stroke-linecap="round"/>'
    return {"w": W, "h": H, "capas": [{"id": "base", "svg": _svg(W, H, base, d)}, {"id": "luz", "svg": _svg(W, H, luz, d)},
                                      {"id": "cristal", "svg": _svg(W, H, cristal, d)}], "clave": "horno hornear calor cocinar"}


# ----------------------------------------------------------------------------- placa vitrocerámica
def placa(zonas=2):
    W, H = 560, 340
    d = _grad("cp", [(0, "#2a3140"), (1, "#0b0e14")])
    base = _sombra(280, 330, 270, 12) + '<path d="M70 20 L490 20 L550 310 L10 310 Z" fill="url(#cp)" stroke="#000" stroke-width="3"/>'
    centros = [(190, 170, 95, 50), (380, 170, 95, 50)] if zonas == 2 else [(170, 110, 70, 34), (390, 110, 70, 34), (160, 230, 90, 44), (400, 230, 90, 44)]
    for cx, cy, rx, ry in centros:
        base += '<ellipse cx="%d" cy="%d" rx="%d" ry="%d" fill="none" stroke="#6b7486" stroke-width="4"/>' % (cx, cy, rx, ry)
    base += '<path d="M90 40 L250 40" stroke="#fff" stroke-width="8" opacity="0.12" stroke-linecap="round"/>'
    defs = d + ('<radialGradient id="rojo"><stop offset="0" stop-color="#ff6a3d"/><stop offset="0.7" stop-color="#e2341d" stop-opacity="0.85"/>'
                '<stop offset="1" stop-color="#e2341d" stop-opacity="0"/></radialGradient>')
    capas = [{"id": "base", "svg": _svg(W, H, base, defs)}]
    for i, (cx, cy, rx, ry) in enumerate(centros):
        capas.append({"id": "zona%d" % (i + 1), "svg": _svg(W, H, '<ellipse cx="%d" cy="%d" rx="%d" ry="%d" fill="url(#rojo)"/>' % (cx, cy, rx * 0.95, ry * 0.95), defs)})
    return {"w": W, "h": H, "capas": capas, "clave": "placa vitrocerámica fuego cocinar calor residual"}


# ----------------------------------------------------------------------------- olla con tapa
def olla(color="#c7cfdb"):
    W, H = 420, 400
    d = (_grad("co", [(0, "#f2f5f9"), (0.5, color), (1, "#7f8a9c")], vertical=False) + _grad("ct", [(0, "#eef2f7"), (1, "#9aa6b8")]))
    base = _sombra(210, 390, 200, 12) + (
        '<rect x="18" y="200" width="60" height="24" rx="12" fill="#3b4250"/><rect x="342" y="200" width="60" height="24" rx="12" fill="#3b4250"/>'
        '<path d="M62 170 L358 170 L340 370 Q336 384 320 384 L100 384 Q84 384 80 370 Z" fill="url(#co)" stroke="#6b7486" stroke-width="3"/>'
        '<ellipse cx="210" cy="170" rx="150" ry="22" fill="#5d6778"/>')
    tapa = ('<ellipse cx="210" cy="166" rx="160" ry="26" fill="url(#ct)" stroke="#6b7486" stroke-width="3"/>'
            '<path d="M60 162 Q210 100 360 162" fill="url(#ct)" stroke="#6b7486" stroke-width="3"/>'
            '<rect x="186" y="106" width="48" height="22" rx="11" fill="#3b4250"/>')
    return {"w": W, "h": H, "capas": [{"id": "base", "svg": _svg(W, H, base, d)}, {"id": "tapa", "svg": _svg(W, H, tapa, d)}],
            "clave": "olla cacerola tapa cocinar hervir"}


# ----------------------------------------------------------------------------- termómetro
def termometro(color="#ff4d4d", marcas=("90", "60", "40", "30", "20")):
    W, H = 160, 520
    d = _grad("tv", [(0, "#ffffff"), (1, "#dfe5ee")], vertical=False)
    base = ('<rect x="50" y="20" width="60" height="400" rx="30" fill="url(#tv)" stroke="#9aa5b6" stroke-width="4"/>'
            '<circle cx="80" cy="450" r="56" fill="url(#tv)" stroke="#9aa5b6" stroke-width="4"/>'
            '<rect x="68" y="40" width="24" height="380" rx="12" fill="#e9edf3"/>')
    for i in range(len(marcas)):
        y = 60 + i * 80
        base += '<line x1="112" y1="%d" x2="130" y2="%d" stroke="#5b6475" stroke-width="4"/>' % (y, y)
    columna = '<rect x="68" y="40" width="24" height="410" rx="12" fill="%s"/><circle cx="80" cy="450" r="42" fill="%s"/>' % (color, color)
    brillo = '<rect x="58" y="40" width="8" height="360" rx="4" fill="#fff" opacity="0.7"/>'
    return {"w": W, "h": H, "capas": [{"id": "base", "svg": _svg(W, H, base, d)},
                                      {"id": "columna", "svg": _svg(W, H, columna, d), "revelar": (40, 450)},
                                      {"id": "brillo", "svg": _svg(W, H, brillo, d)}], "clave": "termómetro temperatura grados calor frío"}


# ----------------------------------------------------------------------------- selector (rueda de programas)
def dial(etiquetas=("90°", "60°", "40°", "30°", "ECO"), color="#00c2e0"):
    W, H = 420, 420
    d = (_grad("dc", [(0, "#ffffff"), (1, "#c9d1dd")]) + '<radialGradient id="dk" cx="0.4" cy="0.35" r="0.8"><stop offset="0" stop-color="#ffffff"/>'
         '<stop offset="1" stop-color="#aab4c4"/></radialGradient>')
    base = _sombra(210, 405, 170, 12) + '<circle cx="210" cy="210" r="196" fill="url(#dc)" stroke="#9aa5b6" stroke-width="4"/>'
    n = len(etiquetas)
    import math
    for i, e in enumerate(etiquetas):
        ang = math.radians(-135 + 270 * i / max(1, n - 1))
        x, y = 210 + 160 * math.sin(ang), 210 - 160 * math.cos(ang)
        col = "#16a34a" if "ECO" in e.upper() else "#2b3445"
        base += _texto(x, y, e, 30 if len(e) <= 3 else 26, col, 900)
    base += '<circle cx="210" cy="210" r="104" fill="url(#dk)" stroke="#8d98aa" stroke-width="4"/>'
    aguja = ('<rect x="200" y="112" width="20" height="74" rx="10" fill="%s"/><circle cx="210" cy="210" r="22" fill="#e8edf4" stroke="#8d98aa" stroke-width="3"/>' % color)
    return {"w": W, "h": H, "capas": [{"id": "base", "svg": _svg(W, H, base, d)}, {"id": "aguja", "svg": _svg(W, H, aguja, d), "pivote": (210, 210)}],
            "clave": "programa selector rueda temperatura eco",
            "angulos": {e: -135 + 270 * i / max(1, n - 1) for i, e in enumerate(etiquetas)}}


# ----------------------------------------------------------------------------- grifo
def grifo():
    W, H = 360, 340
    d = _grad("cg", [(0, "#f5f7fa"), (0.5, "#aeb8c8"), (1, "#eef2f7")], vertical=False)
    base = ('<rect x="40" y="250" width="280" height="40" rx="16" fill="#cfd6e1"/>'
            '<rect x="150" y="120" width="60" height="140" rx="18" fill="url(#cg)" stroke="#7f8a9c" stroke-width="3"/>'
            '<path d="M180 130 Q180 60 260 60 L300 60 Q320 60 320 80 L320 100 L290 100 L290 92 Q290 88 284 88 L262 88 Q212 88 212 130 Z" fill="url(#cg)" stroke="#7f8a9c" stroke-width="3"/>'
            '<rect x="120" y="96" width="120" height="26" rx="13" fill="#9aa5b6"/>')
    return {"w": W, "h": H, "capas": [{"id": "base", "svg": _svg(W, H, base, d)}], "clave": "grifo agua lavar", "boca": (305, 104)}


# ----------------------------------------------------------------------------- enchufe de pared
def enchufe():
    W, H = 300, 300
    base = ('<rect x="20" y="20" width="260" height="260" rx="40" fill="#f4f6fa" stroke="#b9c2d0" stroke-width="4"/>'
            '<circle cx="150" cy="150" r="86" fill="#e3e8ef" stroke="#c3cbd8" stroke-width="3"/>'
            '<circle cx="118" cy="150" r="12" fill="#2b3445"/><circle cx="182" cy="150" r="12" fill="#2b3445"/>')
    clavija = ('<rect x="104" y="96" width="92" height="108" rx="26" fill="#2f3a4c"/><rect x="132" y="204" width="36" height="90" rx="12" fill="#2f3a4c"/>'
               '<rect x="116" y="108" width="20" height="60" rx="10" fill="#ffffff" opacity="0.12"/>')
    return {"w": W, "h": H, "capas": [{"id": "base", "svg": _svg(W, H, base)}, {"id": "clavija", "svg": _svg(W, H, clavija)}],
            "clave": "enchufe desenchufar consumo fantasma cable"}


PROPS = {"lavadora": lavadora, "nevera": nevera, "microondas": microondas, "horno": horno, "placa": placa, "olla": olla,
         "termometro": termometro, "dial": dial, "grifo": grifo, "enchufe": enchufe}


def crear(nombre, estado=None):
    return PROPS[nombre](**(estado or {}))
