"""Motor audiovisual de ARVIS VIDA: guion JSON → vídeo vertical 1080×1920 a 30 fps con voz, música, efectos y subtítulos.

Cada escena: escenario (fondo con desenfoque de profundidad) + elementos animados (aparatos propios, iconos Fluent,
textos, cifras que cuentan, barras, sellos ✓/✗, flechas y partículas) + cámara virtual (empuje, alejar, paneo y
golpes de zoom en palabras clave) + transición de entrada (barrido con desenfoque, zoom, destello, subida).
Los momentos visuales se anclan a PALABRAS de la narración («en»: "agua") para que la imagen vaya con lo que se dice.
"""
import json
import math
import os
import re
import subprocess
import time
import unicodedata

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from arvis_lifehacks import voz as voz_mod
from . import activos, fondos, props, sonido, texto

W, H, FPS = 1080, 1920, 30
TRANS = 0.26                 # duración de las transiciones (s)
CHIPS = {"problema": ("EL PROBLEMA", "aviso"), "resultado": ("RESULTADO", "lima"), "cta": ("GUÁRDALO", "cian"),
         "error": ("ERROR HABITUAL", "rojo"), "gancho": ("", "lima")}


# ----------------------------------------------------------------------------- curvas
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def suave(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_out_back(x, s=1.7):
    x = clamp(x) - 1
    return 1 + x * x * ((s + 1) * x + s)


def ease_out_cubic(x):
    return 1 - (1 - clamp(x)) ** 3


def muelle(u, k=9.0, w=15.0):
    """0 → 1 con rebote (entrada «pop»)."""
    if u <= 0:
        return 0.0
    return 1 - math.exp(-k * u) * math.cos(w * u)


def rebote(x):
    x = clamp(x)
    n, d = 7.5625, 2.75
    if x < 1 / d:
        return n * x * x
    if x < 2 / d:
        x -= 1.5 / d
        return n * x * x + 0.75
    if x < 2.5 / d:
        x -= 2.25 / d
        return n * x * x + 0.9375
    x -= 2.625 / d
    return n * x * x + 0.984375


def _norm(w):
    w = unicodedata.normalize("NFKD", w.lower())
    return re.sub(r"[^a-z0-9ñ%]", "", "".join(c for c in w if not unicodedata.combining(c)))


# ----------------------------------------------------------------------------- escena / tiempos
class Linea:
    """Tiempos de una escena: voz y palabras en segundos absolutos."""

    def __init__(self, idx, t0, voz, palabras, dur):
        self.idx, self.t0, self.voz, self.palabras, self.dur = idx, t0, voz, palabras, dur

    @property
    def t1(self):
        return self.t0 + self.dur

    def tiempo(self, ancla, defecto=0.0):
        """ancla: número (s desde el inicio de la escena) o palabra/prefijo de la narración («agua», «gasta#2» = 2.ª vez)."""
        if ancla is None:
            return self.t0 + defecto
        if isinstance(ancla, (int, float)):
            return self.t0 + float(ancla)
        s = str(ancla)
        n = 1
        if "#" in s:
            s, k = s.split("#", 1)
            n = int(k or 1)
        clave = _norm(s)
        vistos = 0
        for p in self.palabras:
            if _norm(p["w"]).startswith(clave) and clave:
                vistos += 1
                if vistos == n:
                    return p["t0"]
        return self.t0 + defecto


# ----------------------------------------------------------------------------- elementos
class Elemento:
    def __init__(self, spec, linea, motor, orden):
        self.s = spec
        self.m = motor
        self.linea = linea
        self.tipo = spec.get("tipo") or ("activo" if spec.get("activo") else "texto")
        self.t_in = linea.tiempo(spec.get("en", spec.get("t")), 0.08 + 0.18 * orden)
        if spec.get("en") is not None and isinstance(spec.get("en"), str) and spec.get("antes"):
            self.t_in -= float(spec["antes"])
        self.t_out = linea.tiempo(spec["sale_en"], 99) if spec.get("sale_en") is not None else None
        self.x, self.y = spec.get("x", 0.5) * W, spec.get("y", 0.45) * H
        self.tam = spec.get("tam", 0.3)
        self.entrada = spec.get("entrada", "pop")
        self.anim = spec.get("anim", "flotar")
        self.semilla = (hash(json.dumps(spec, sort_keys=True, ensure_ascii=False)) & 0xFFFF) + orden
        self.mov = []
        for k in spec.get("mover", []):
            self.mov.append({"t": linea.tiempo(k.get("en", k.get("t")), 0.5), "dur": k.get("dur", 0.6),
                             "x": k.get("a", [None, None])[0], "y": k.get("a", [None, None])[1], "tam": k.get("tam")})
        self.capas_anim = {}
        self._cache = {}
        self.preparar()

    # --- preparación de sprites
    def preparar(self):
        zmax = 1.25
        if self.tipo == "activo":
            nombre = self.s["activo"]
            ancho = int(min(1300, self.tam * W * zmax * max([1.0] + [k["tam"] / self.tam for k in self.mov if k.get("tam")])))
            if nombre in props.PROPS:
                p = props.crear(nombre, self.s.get("estado"))
                self.prop = p
                esc = ancho / p["w"]
                self.capas = []
                for c in p["capas"]:
                    img = activos.svg_a_png(c["svg"], ancho, int(round(p["h"] * esc)))
                    self.capas.append({"id": c["id"], "img": img, "pivote": tuple(v * esc for v in c.get("pivote", (p["w"] / 2, p["h"] / 2))),
                                       "revelar": tuple(v * esc for v in c["revelar"]) if c.get("revelar") else None})
                for cid, a in (self.s.get("capas") or {}).items():
                    a = dict(a)
                    a["t"] = self.linea.tiempo(a.get("en", a.get("t")), 0.0)
                    if "de" in a and isinstance(a["de"], str) and "angulos" in p:
                        a["de"] = p["angulos"].get(a["de"], 0)
                    if "a" in a and isinstance(a["a"], str) and "angulos" in p:
                        a["a"] = p["angulos"].get(a["a"], 0)
                    self.capas_anim[cid] = a
                self.base_px = ancho
                self.aspecto = p["h"] / p["w"]
            else:
                img = activos.icono(nombre, ancho)
                self.capas = [{"id": "base", "img": img, "pivote": (img.width / 2, img.height / 2), "revelar": None}]
                self.base_px = ancho
                self.aspecto = img.height / img.width
        elif self.tipo == "texto":
            lineas = str(self.s.get("texto", "")).split("\n")
            tam_px = int(self.s.get("px", 84))
            tam_px = texto.ajustar_tam([l for l in lineas], tam_px, W - 140, "Oswald.ttf", 700)
            sprites = [texto.linea_sprite(l, tam_px, self.s.get("resaltar", []), self.s.get("color", "blanco"),
                                          self.s.get("color_resaltado", "lima")) for l in lineas]
            if self.s.get("fondo") == "pastilla":
                sprites = [texto.pastilla(l, int(tam_px * 0.62), self.s.get("color_fondo", "lima"), self.s.get("color", "noche"))
                           for l in lineas]
            self.capas = [{"id": "base", "img": _apilar(sprites), "pivote": None, "revelar": None}]
            self.base_px = self.capas[0]["img"].width
            self.aspecto = self.capas[0]["img"].height / self.capas[0]["img"].width
            self.tam = self.base_px / W
        elif self.tipo == "sello":
            nombre = {"check": "check", "cruz": "cruz", "prohibido": "prohibido"}.get(self.s.get("simbolo", "check"), "check")
            img = activos.icono(nombre, int(self.tam * W * 1.6))
            self.capas = [{"id": "base", "img": img, "pivote": None, "revelar": None}]
            self.base_px = img.width
            self.aspecto = 1.0
            self.entrada = "estampar"
            self.anim = "ninguna"
        elif self.tipo == "particulas":
            clase = self.s.get("clase", "brillos")
            icon = {"monedas": "moneda", "gotas": "gota", "nieve": "copo", "brillos": "brillos", "rayos": "rayo", "billetes": "billete_alas",
                    "corazones": "corazon", "hojas": "hoja", "hielo": "hielo", "fuego": "fuego"}.get(clase)
            self.sprite_p = activos.icono(icon, int(W * self.s.get("tam", 0.09) * 1.3)) if icon else None
            self.blob = _blob(120)
        # contador, barra y flecha se dibujan en cada fotograma

    # --- estado en el instante t
    def visible(self, t):
        if t < self.t_in - 0.001:
            return False
        if self.t_out is not None and t > self.t_out + 0.3:
            return False
        return True

    def transformar(self, t):
        u = t - self.t_in
        x, y, esc, rot, alfa = self.x, self.y, 1.0, 0.0, 1.0
        tam = self.tam
        # trayectorias
        for k in self.mov:
            p = ease_in_out(clamp((t - k["t"]) / max(0.05, k["dur"])))
            if p > 0:
                if k["x"] is not None:
                    x = x + (k["x"] * W - x) * p
                if k["y"] is not None:
                    y = y + (k["y"] * H - y) * p
                if k["tam"]:
                    tam = tam + (k["tam"] - tam) * p
        e = self.entrada
        if e == "pop":
            esc *= muelle(u)
            alfa = clamp(u / 0.06)
        elif e == "caer":
            y -= (1 - rebote(u / 0.6)) * 0.35 * H
            alfa = clamp(u / 0.05)
        elif e == "subir":
            y += (1 - ease_out_back(u / 0.45)) * 0.30 * H
            alfa = clamp(u / 0.08)
        elif e in ("izq", "der"):
            x += (-1 if e == "izq" else 1) * (1 - ease_out_back(u / 0.45)) * 0.85 * W
        elif e == "zoom":
            esc *= 1.6 - 0.6 * ease_out_cubic(u / 0.35)
            alfa = clamp(u / 0.2)
        elif e == "fade":
            alfa = clamp(u / 0.3)
        elif e == "estampar":
            k = clamp(u / 0.18)
            esc *= 2.3 - 1.3 * ease_out_cubic(k)
            rot = -14 * (1 - k)
            alfa = clamp(u / 0.06)
        if self.t_out is not None and t > self.t_out:
            k = clamp((t - self.t_out) / 0.25)
            esc *= 1 - suave(k)
            alfa *= 1 - k
        a = self.anim
        if u > 0.3:
            v = u - 0.3
            if a == "flotar":
                y += math.sin(2 * math.pi * v / 1.9 + self.semilla) * 0.008 * H
                rot += math.sin(2 * math.pi * v / 2.7 + self.semilla) * 2.0
            elif a == "latir":
                esc *= 1 + 0.05 * math.sin(2 * math.pi * v * 1.7)
            elif a == "balancear":
                rot += math.sin(2 * math.pi * v / 1.1) * 8
            elif a == "vibrar":
                x += math.sin(v * 95) * 5
                y += math.cos(v * 77) * 3
            elif a == "girar":
                rot += v * float(self.s.get("vel", 120))
            elif a == "respirar":
                esc *= 1 + 0.02 * math.sin(2 * math.pi * v / 2.0)
        return x, y, tam, esc, rot, alfa

    def _componer(self, t):
        """Imagen RGBA del activo (con capas animadas) a su tamaño máximo."""
        anim = self.capas_anim
        if not anim:
            if "estatico" not in self._cache:
                im = self.capas[0]["img"].copy()
                for c in self.capas[1:]:
                    im.alpha_composite(c["img"])
                self._cache["estatico"] = im
            return self._cache["estatico"]
        im = None
        for c in self.capas:
            a = anim.get(c["id"])
            capa = c["img"]
            if a:
                capa = self._capa_animada(c, a, t)
            if capa is None:
                continue
            im = capa.copy() if im is None else im
            if im is not capa:
                im.alpha_composite(capa)
        return im

    def _capa_animada(self, c, a, t):
        img = c["img"]
        u = t - a["t"]
        p = ease_in_out(clamp(u / max(0.05, a.get("dur", 0.8))))
        if "girar" in a:
            ang = -float(a["girar"]) * max(0.0, t - a["t"]) if t >= a["t"] else 0.0
            return img.rotate(ang, resample=Image.BILINEAR, center=c["pivote"])
        if c["id"] == "aguja" or ("de" in a and isinstance(a.get("de"), (int, float)) and c.get("pivote") and a.get("tipo") == "angulo"):
            ang = float(a.get("de", 0)) + (float(a.get("a", 0)) - float(a.get("de", 0))) * p
            return img.rotate(-ang, resample=Image.BILINEAR, center=c["pivote"])
        if c.get("revelar"):
            top, bot = c["revelar"]
            nivel = float(a.get("de", 0.5)) + (float(a.get("a", 0.5)) - float(a.get("de", 0.5))) * p
            corte = int(top + (1 - clamp(nivel)) * (bot - top))
            out = img.copy()
            ImageDraw.Draw(out).rectangle([0, 0, out.width, corte], fill=(0, 0, 0, 0))
            return out
        if "mover" in a or ("de" in a and isinstance(a.get("de"), list)):
            de, hasta = a.get("de", [0, 0]), a.get("a", [0, 0])
            esc = self.base_px / self.prop["w"]
            dx = (de[0] + (hasta[0] - de[0]) * p) * esc
            dy = (de[1] + (hasta[1] - de[1]) * p) * esc
            out = Image.new("RGBA", img.size, (0, 0, 0, 0))
            out.paste(img, (int(dx), int(dy)), img)
            return out
        if "pulso" in a or "de" in a:
            if "pulso" in a:
                op = 0.55 + 0.45 * math.sin(2 * math.pi * max(0.0, u) * float(a.get("pulso", 1.5))) if u >= 0 else float(a.get("antes", 0.0))
            else:
                op = float(a.get("de", 1)) + (float(a.get("a", 1)) - float(a.get("de", 1))) * p
            op = clamp(op)
            if op <= 0.01:
                return None
            out = img.copy()
            out.putalpha(out.getchannel("A").point(lambda v: int(v * op)))
            return out
        return img

    # --- dibujo en pantalla
    def dibujar(self, lienzo, t, cam):
        if not self.visible(t):
            return
        if self.tipo == "particulas":
            return self._particulas(lienzo, t, cam)
        if self.tipo == "flecha":
            return self._flecha(lienzo, t, cam)
        if self.tipo in ("contador", "barra"):
            spr = self._sprite_dinamico(t)
            x, y, tam, esc, rot, alfa = self.transformar(t)
            return _pegar(lienzo, spr, cam, x, y, spr.width * esc, rot, alfa)
        x, y, tam, esc, rot, alfa = self.transformar(t)
        if esc <= 0.02 or alfa <= 0.01:
            return
        im = self._componer(t)
        ancho = tam * W * esc * (im.width / self.base_px)
        _pegar(lienzo, im, cam, x, y, ancho, rot, alfa)

    def _sprite_dinamico(self, t):
        u = t - self.t_in
        if self.tipo == "contador":
            de, a = float(self.s.get("desde", 0)), float(self.s.get("hasta", 100))
            v = de + (a - de) * ease_out_cubic(u / float(self.s.get("dur", 1.2)))
            dec = int(self.s.get("decimales", 0))
            txt = self.s.get("formato", "{v}").replace("{v}", ("%." + str(dec) + "f") % v if dec else str(int(round(v))))
            k = (txt, int(self.s.get("px", 220)))
            if k not in self._cache:
                self._cache[k] = texto.cifra_sprite(txt, k[1], self.s.get("color", "aviso"))
            return self._cache[k]
        # barra
        ancho = int(self.s.get("ancho", 0.78) * W)
        alto = int(self.s.get("alto", 92))
        de, a = float(self.s.get("de", 0)), float(self.s.get("valor", 0.5))
        v = de + (a - de) * ease_out_cubic(u / float(self.s.get("dur", 1.0)))
        im = Image.new("RGBA", (ancho + 20, alto + 90), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        etq = self.s.get("etiqueta", "")
        f = texto.fuente("Inter.ttf", 44, 900)
        if etq:
            d.text((10, 0), etq, font=f, fill=texto.C["blanco"], stroke_width=6, stroke_fill=(0, 0, 0))
        y0 = 70 if etq else 10
        d.rounded_rectangle([10, y0, 10 + ancho, y0 + alto], alto // 2, fill=(20, 26, 40, 235), outline=(255, 255, 255, 200), width=4)
        col = texto.color(self.s.get("color", "rojo"))
        d.rounded_rectangle([16, y0 + 6, 16 + max(alto - 12, (ancho - 12) * clamp(v)), y0 + alto - 6], (alto - 12) // 2, fill=col)
        pct = self.s.get("texto_valor") or ("%d %%" % round(v * 100))
        fp = texto.fuente("Inter.ttf", int(alto * 0.55), 900)
        tw = d.textlength(pct, font=fp)
        d.text((10 + ancho - tw - 26, y0 + alto * 0.18), pct, font=fp, fill=texto.C["blanco"], stroke_width=5, stroke_fill=(0, 0, 0))
        return im

    def _particulas(self, lienzo, t, cam):
        s = self.s
        clase = s.get("clase", "brillos")
        x0, y0 = s.get("x", 0.5) * W, s.get("y", 0.5) * H
        aw, ah = s.get("ancho", 0.5) * W, s.get("alto", 0.3) * H
        t_ini = self.t_in
        t_fin = self.linea.tiempo(s["hasta"], 99) if s.get("hasta") is not None else self.linea.t1 + 0.3
        n = int(s.get("densidad", 14))
        vida = float(s.get("vida", 1.6))
        rng = np.random.default_rng(self.semilla)
        params = rng.random((n * 8, 5))
        periodo = vida / n
        for i in range(n * 8):
            ts = t_ini + i * periodo
            if ts > t_fin or ts > t:
                break
            u = (t - ts) / vida
            if u >= 1:
                continue
            r = params[i]
            if clase in ("vapor", "calor"):
                px = x0 + (r[0] - 0.5) * aw + math.sin(u * 6 + r[1] * 6) * 18
                py = y0 - u * ah
                rad = (40 + 90 * u) * (0.7 + 0.6 * r[2])
                op = (1 - u) * min(1, u * 5) * (0.55 if clase == "vapor" else 0.4)
                img = self.blob if clase == "vapor" else _tintar(self.blob, (255, 120, 60))
                _pegar(lienzo, img, cam, px, py, rad * 2, 0, op)
            elif clase == "burbujas":
                px = x0 + (r[0] - 0.5) * aw + math.sin(u * 8 + r[1] * 9) * 20
                py = y0 + ah / 2 - u * ah
                rad = 16 + 30 * r[2]
                _pegar(lienzo, _burbuja(), cam, px, py, rad * 2, 0, (1 - u ** 3) * min(1, u * 6))
            elif clase in ("monedas", "gotas", "nieve", "billetes", "hojas", "hielo", "corazones", "fuego", "rayos"):
                cae = clase in ("monedas", "gotas", "nieve", "hielo", "hojas")
                px = x0 + (r[0] - 0.5) * aw + (math.sin(u * 5 + r[1] * 7) * 30 if clase in ("nieve", "hojas") else 0)
                py = (y0 - ah / 2 + u * ah) if cae else (y0 + ah / 2 - u * ah)
                rot = (r[2] - 0.5) * 60 + (u * 200 * (r[3] - 0.5) if clase in ("monedas", "billetes", "hojas") else 0)
                esc = 0.6 + 0.6 * r[4]
                ancho = self.sprite_p.width / 1.3 * esc
                if clase == "monedas":
                    ancho *= abs(math.cos(u * 9 + r[1] * 5)) * 0.7 + 0.3
                _pegar(lienzo, self.sprite_p, cam, px, py, ancho, rot, min(1, (1 - u) * 4) * min(1, u * 8))
            else:  # brillos / chispas
                px = x0 + (r[0] - 0.5) * aw
                py = y0 + (r[1] - 0.5) * ah
                k = math.sin(math.pi * u)
                spr = self.sprite_p if self.sprite_p is not None else self.blob
                _pegar(lienzo, spr, cam, px, py, W * s.get("tam", 0.09) * (0.5 + 0.7 * r[2]) * k, u * 90, k)

    def _flecha(self, lienzo, t, cam):
        s = self.s
        u = clamp((t - self.t_in) / float(s.get("dur", 0.45)))
        (ax, ay), (bx, by) = s["de"], s["a"]
        ax, ay, bx, by = ax * W, ay * H, bx * W, by * H
        curva = float(s.get("curva", 0.25))
        mx, my = (ax + bx) / 2 - (by - ay) * curva, (ay + by) / 2 + (bx - ax) * curva
        pts = []
        for i in range(int(40 * u) + 1):
            k = i / 40
            px = (1 - k) ** 2 * ax + 2 * (1 - k) * k * mx + k * k * bx
            py = (1 - k) ** 2 * ay + 2 * (1 - k) * k * my + k * k * by
            pts.append(cam.a_pantalla(px, py))
        if len(pts) < 2:
            return
        d = ImageDraw.Draw(lienzo)
        col = texto.color(s.get("color", "lima"))
        d.line(pts, fill=(0, 0, 0), width=30, joint="curve")
        d.line(pts, fill=col, width=18, joint="curve")
        if u >= 0.98:
            (x1, y1), (x2, y2) = pts[-3], pts[-1]
            ang = math.atan2(y2 - y1, x2 - x1)
            L = 52
            p1 = (x2 + L * 0.35 * math.cos(ang), y2 + L * 0.35 * math.sin(ang))
            p2 = (x2 - L * math.cos(ang - 0.55), y2 - L * math.sin(ang - 0.55))
            p3 = (x2 - L * math.cos(ang + 0.55), y2 - L * math.sin(ang + 0.55))
            d.polygon([p1, p2, p3], fill=col, outline=(0, 0, 0))


def ease_in_out(x):
    x = clamp(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


_BLOB = {}


def _blob(r):
    if r not in _BLOB:
        im = Image.new("RGBA", (r * 2, r * 2), (255, 255, 255, 0))
        a = Image.new("L", (r * 2, r * 2), 0)
        ImageDraw.Draw(a).ellipse([r * 0.35, r * 0.35, r * 1.65, r * 1.65], fill=255)
        im.putalpha(a.filter(ImageFilter.GaussianBlur(r * 0.3)))
        _BLOB[r] = im
    return _BLOB[r]


_TINT = {}


def _tintar(im, col):
    k = (id(im), col)
    if k not in _TINT:
        t = Image.new("RGBA", im.size, col + (0,))
        t.putalpha(im.getchannel("A"))
        _TINT[k] = t
    return _TINT[k]


_BURB = []


def _burbuja():
    if not _BURB:
        r = 64
        im = Image.new("RGBA", (r * 2, r * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.ellipse([4, 4, r * 2 - 4, r * 2 - 4], fill=(200, 235, 255, 60), outline=(255, 255, 255, 230), width=6)
        d.ellipse([r * 0.5, r * 0.45, r * 0.85, r * 0.75], fill=(255, 255, 255, 220))
        _BURB.append(im)
    return _BURB[0]


def _apilar(sprites, sep=-6):
    w = max(s.width for s in sprites)
    h = sum(s.height for s in sprites) + sep * (len(sprites) - 1)
    im = Image.new("RGBA", (w, max(1, h)), (0, 0, 0, 0))
    y = 0
    for s in sprites:
        im.alpha_composite(s, ((w - s.width) // 2, y))
        y += s.height + sep
    return im


def _pegar(lienzo, im, cam, x, y, ancho, rot, alfa):
    """Pega im (RGBA) centrado en el punto del mundo (x, y) con el ancho dado, aplicando la cámara."""
    if ancho < 2 or alfa <= 0.01:
        return
    sx, sy = cam.a_pantalla(x, y)
    ancho *= cam.z
    alto = ancho * im.height / im.width
    if ancho > 3 * W or sx + ancho / 2 < 0 or sx - ancho / 2 > W or sy + alto / 2 < 0 or sy - alto / 2 > H:
        return
    spr = im.resize((max(1, int(ancho)), max(1, int(alto))), Image.BILINEAR)
    if abs(rot) > 0.3:
        spr = spr.rotate(rot, resample=Image.BILINEAR, expand=True)
    if alfa < 0.995:
        spr = spr.copy()
        spr.putalpha(spr.getchannel("A").point(lambda v: int(v * alfa)))
    lienzo.paste(spr, (int(sx - spr.width / 2), int(sy - spr.height / 2)), spr)


# ----------------------------------------------------------------------------- cámara
class Camara:
    def __init__(self, cx=W / 2, cy=H / 2, z=1.0):
        self.cx, self.cy, self.z = cx, cy, z

    def a_pantalla(self, x, y):
        return (x - self.cx) * self.z + W / 2, (y - self.cy) * self.z + H / 2

    def limitar(self):
        self.z = max(1.0, self.z)
        lx = (W / 2) / self.z
        ly = (H / 2) / self.z
        self.cx = clamp(self.cx, lx - fondos.OX, W + fondos.OX - lx)
        self.cy = clamp(self.cy, ly - fondos.OY, H + fondos.OY - ly)
        return self


# ----------------------------------------------------------------------------- motor
class Motor:
    def __init__(self, guion, salida, voz=None):
        self.g = guion
        self.out = salida
        os.makedirs(salida, exist_ok=True)
        self.voz_preset = voz or guion.get("voice", "sharvard_m")
        self.escenas = guion["escenas"]
        self.n_pasos = sum(1 for e in self.escenas if e["beat"] == "tutorial")
        self.eventos_sfx = []
        self.eventos_visuales = []

    # --- 1. voz y línea de tiempo
    def preparar_audio(self, ritmo_global=1.0):
        partes, lineas, t = [], [], 0.0
        for i, e in enumerate(self.escenas):
            ritmo = float(e.get("ritmo", 0.93 if e["beat"] == "gancho" else 1.0)) * ritmo_global
            audio, pal = voz_mod.sintetizar(e["say"], self.voz_preset, ritmo)
            lead = 0.04 if i == 0 else 0.10
            pausa = 0.95 if i == len(self.escenas) - 1 else float(e.get("pausa", 0.20))
            dur = lead + len(audio) / sonido.SR + pausa
            dur = max(dur, float(e.get("min_dur", 1.6)))
            pal = [{"w": p["w"], "t0": round(t + lead + p["t0"], 3), "t1": round(t + lead + p["t1"], 3)} for p in pal]
            lineas.append(Linea(i, t, audio, pal, dur))
            partes.append((t + lead, audio))
            e["_t0"], e["_t1"], e["_voz"] = round(t, 3), round(t + dur, 3), round(len(audio) / sonido.SR, 3)
            t += dur
        self.dur = t
        voz = np.zeros(int(t * sonido.SR) + sonido.SR)
        for a, au in partes:
            k = int(a * sonido.SR)
            voz[k:k + len(au)] += au
        self.voz = voz[: int(t * sonido.SR)]
        self.lineas = lineas
        self.palabras = [p for l in lineas for p in l.palabras]
        self.subs = texto.bloques(self.palabras)
        return t

    # --- 2. recursos de cada escena
    def preparar_escenas(self):
        semilla = int(self.g.get("variante", 0))
        self.fondos, self.elems, self.titulos = [], [], []
        cache_f = {}
        for i, (e, l) in enumerate(zip(self.escenas, self.lineas)):
            nombre = e.get("fondo", "estudio")
            k = (nombre, semilla + e.get("variante_fondo", 0))
            if k not in cache_f:
                img = fondos.fondo(nombre, k[1])
                img = img.filter(ImageFilter.GaussianBlur(float(e.get("desenfoque", 3.0))))
                cache_f[k] = np.asarray(img)
            self.fondos.append(cache_f[k])
            els = [Elemento(s, l, self, j) for j, s in enumerate(e.get("elementos", []))]
            self.elems.append(els)
            for el in els:
                self.eventos_visuales.append(round(el.t_in, 2))
                if el.tipo == "sello":
                    self.eventos_sfx.append((el.t_in + 0.08, "exito" if el.s.get("simbolo", "check") == "check" else "error"))
                elif el.tipo == "contador":
                    for k2 in range(8):
                        self.eventos_sfx.append((el.t_in + k2 * float(el.s.get("dur", 1.2)) / 9, "tic"))
                elif el.tipo == "particulas":
                    tipo = {"monedas": "monedas", "burbujas": "burbujas", "gotas": "salpicadura"}.get(el.s.get("clase"))
                    if tipo:
                        self.eventos_sfx.append((el.t_in, tipo))
            pops = [el for el in els if el.tipo in ("activo", "texto", "contador", "barra") and el.entrada in ("pop", "caer", "zoom", "subir", "izq", "der")]
            ult = -9
            n = 0
            for el in sorted(pops, key=lambda x: x.t_in):
                if el.t_in - ult >= 0.3 and n < 3:
                    self.eventos_sfx.append((max(0.0, el.t_in), "pop" if el.entrada != "caer" else "golpe"))
                    ult = el.t_in
                    n += 1
            for tipo, ancla in e.get("sfx", []):
                self.eventos_sfx.append((l.tiempo(ancla, 0.0), tipo))
            if i > 0 and e.get("transicion", "barrido") != "corte":
                self.eventos_sfx.append((max(0.0, l.t0 - 0.16), "whoosh"))
                self.eventos_visuales.append(round(l.t0, 2))
            # título
            tit = e.get("titulo")
            sprites = []
            if tit:
                lineas_t = tit.split("\n")
                tam = 128 if e["beat"] == "gancho" else 96
                tam = texto.ajustar_tam(lineas_t, tam, W - 120)
                sprites = [texto.linea_sprite(x, tam, e.get("resaltar", []), "blanco", e.get("color_resaltado", "lima")) for x in lineas_t]
            self.titulos.append(sprites)
            for g in e.get("golpes", []):
                self.eventos_visuales.append(round(l.tiempo(g, 0), 2))

    # --- 3. cámara de cada escena
    def camara(self, i, t):
        e, l = self.escenas[i], self.lineas[i]
        u = clamp((t - l.t0) / max(0.5, l.dur))
        fx, fy = e.get("foco", [0.5, 0.48])
        cx, cy = fx * W, fy * H
        tipo = e.get("camara", "empuje")
        z = 1.0
        if tipo == "empuje":
            z = 1.0 + 0.08 * suave(u)
        elif tipo == "alejar":
            z = 1.10 - 0.09 * suave(u)
        elif tipo in ("izq", "der"):
            z = 1.07
            cx += (-1 if tipo == "izq" else 1) * (suave(u) - 0.5) * 70
        elif tipo in ("subir", "bajar"):
            z = 1.07
            cy += (-1 if tipo == "subir" else 1) * (suave(u) - 0.5) * 110
        else:
            z = 1.04 + 0.01 * math.sin(t * 1.3)
            cx += math.sin(t * 0.7) * 8
        for g in e.get("golpes", []):
            tg = l.tiempo(g, -9)
            v = t - tg
            if 0 <= v < 0.6:
                z *= 1 + 0.07 * math.sin(math.pi * clamp(v / 0.12) / 2) * math.exp(-v * 4)
        for el in self.elems[i]:
            if el.tipo == "sello" and el.s.get("simbolo") in ("cruz", "prohibido"):
                v = t - el.t_in - 0.12
                if 0 <= v < 0.35:
                    cx += math.sin(v * 80) * 10 * (1 - v / 0.35)
        return Camara(cx, cy, z).limitar()

    # --- 4. dibujo de una escena
    def escena(self, i, t):
        cam = self.camara(i, t)
        bg = self.fondos[i]
        x0 = cam.cx - (W / 2) / cam.z + fondos.OX
        y0 = cam.cy - (H / 2) / cam.z + fondos.OY
        M = np.float32([[cam.z, 0, -x0 * cam.z], [0, cam.z, -y0 * cam.z]])
        arr = cv2.warpAffine(bg, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        lienzo = Image.fromarray(arr)
        for el in self.elems[i]:
            el.dibujar(lienzo, t, cam)
        self._titulo(lienzo, i, t)
        return lienzo

    def _titulo(self, lienzo, i, t):
        sprites = self.titulos[i]
        if not sprites:
            return
        e, l = self.escenas[i], self.lineas[i]
        y = int(e.get("titulo_y", 0.150) * H)
        t_in = l.tiempo(e.get("titulo_en"), 0.0)
        for k, s in enumerate(sprites):
            u = t - t_in - k * 0.10
            if u < 0:
                y += s.height - 8
                continue
            if e["beat"] == "gancho":
                esc = muelle(u, 10, 16)
                dy = 0
            else:
                esc = 1.0
                dy = (1 - ease_out_back(u / 0.35)) * -40
            a = clamp(u / 0.08)
            w = max(1, int(s.width * esc))
            h = max(1, int(s.height * esc))
            spr = s.resize((w, h), Image.BILINEAR) if (w, h) != s.size else s
            if a < 1:
                spr = spr.copy()
                spr.putalpha(spr.getchannel("A").point(lambda v: int(v * a)))
            lienzo.paste(spr, (int(W / 2 - w / 2), int(y + (s.height - h) / 2 + dy)), spr)
            y += s.height - 8

    # --- 5. fotograma completo
    def indice(self, t):
        for i, l in enumerate(self.lineas):
            if t < l.t1:
                return i
        return len(self.lineas) - 1

    def fotograma(self, t):
        i = self.indice(t)
        l = self.lineas[i]
        img = None
        # transición de entrada de la escena i (o de salida hacia la i+1)
        for j in (i, i + 1):
            if 0 < j < len(self.lineas):
                tc = self.lineas[j].t0
                tipo = self.escenas[j].get("transicion", "barrido")
                if tipo != "corte" and abs(t - tc) < TRANS / 2:
                    k = (t - (tc - TRANS / 2)) / TRANS
                    a = np.asarray(self.escena(j - 1, t))
                    b = np.asarray(self.escena(j, t))
                    img = Image.fromarray(transicion(tipo, a, b, k))
                    i = j if t >= tc else j - 1
                    break
        if img is None:
            img = self.escena(i, t)
        self._capa_fija(img, i, t)
        return img

    def _capa_fija(self, img, i, t):
        e, l = self.escenas[i], self.lineas[i]
        n = self.g.get("numero")
        chip = "LIFEHACKS · Nº %03d" % int(n) if n is not None else "LIFEHACKS"
        etq, col = CHIPS.get(e["beat"], ("", "lima"))
        if e["beat"] == "tutorial":
            etq, col = "PASO %d/%d" % (e.get("paso", 1), self.n_pasos), "lima"
        if e.get("chip"):
            etq = e["chip"]
        k = clamp((t - l.t0) / 0.25)
        texto.cabecera(img, chip, etq, k, t / self.dur, col)
        for b in self.subs:
            if b["t0"] - 0.05 <= t < b["t1"] + 0.12:
                texto.subtitulo(img, b, t)
                break

    # --- 6. render
    def render(self, nombre, ritmo_global=1.0, stills=True):
        t_ini = time.time()
        self.preparar_audio(ritmo_global)
        self.preparar_escenas()
        n = int(math.ceil(self.dur * FPS))
        hq = os.path.join(self.out, nombre + "_hq.mp4")
        mudo = os.path.join(self.out, "_video.mp4")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
               "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-tune", "animation", "-pix_fmt", "yuv420p", mudo]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        sdir = os.path.join(self.out, "stills")
        os.makedirs(sdir, exist_ok=True)
        marcas = {}
        if stills:
            marcas[int(0.5 * FPS)] = "00_gancho_0.5s.jpg"
            for i, l in enumerate(self.lineas):
                marcas[int((l.t0 + l.dur * 0.6) * FPS)] = "%02d_%s_%.1fs.jpg" % (i + 1, self.escenas[i]["beat"], l.t0 + l.dur * 0.6)
        self.stills = []
        for f in range(n):
            t = f / FPS
            img = self.fotograma(t)
            p.stdin.write(img.tobytes())
            if f in marcas:
                img.save(os.path.join(sdir, marcas[f]), quality=88)
                self.stills.append(marcas[f])
        p.stdin.close()
        p.wait()
        # audio
        efectos = sorted((max(0.0, t), tipo) for t, tipo in self.eventos_sfx if t < self.dur)
        mezcla = sonido.mezclar(self.voz, self.dur, efectos, int(self.g.get("musica", {}).get("semilla", 0)),
                                float(self.g.get("musica", {}).get("nivel_db", -19.0)))
        wav = os.path.join(self.out, "_mezcla.wav")
        _escribir_wav(wav, mezcla)
        from arvis_lifehacks.montaje import normalizar
        wavn = os.path.join(self.out, "_mezcla_norm.wav")
        normalizar(wav, wavn, -14.0, -2.0)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mudo, "-i", wavn, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", hq], check=True)
        mk = os.path.join(self.out, nombre + ".mp4")
        comprimir_make(mudo, mk, self.dur, wavn)
        self._srt(os.path.join(self.out, nombre + ".srt"))
        for x in (mudo, wav):
            try:
                os.remove(x)
            except OSError:
                pass
        self.efectos = efectos
        return {"hq": hq, "make": mk, "wav": wavn, "duracion": round(self.dur, 2), "fotogramas": n, "palabras": len(self.palabras),
                "segundos_render": round(time.time() - t_ini, 1), "efectos": len(efectos)}

    def _srt(self, ruta):
        def ts(x):
            ms = int(round(x * 1000))
            return "%02d:%02d:%02d,%03d" % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)
        with open(ruta, "w", encoding="utf-8") as f:
            for k, b in enumerate(self.subs, 1):
                f.write("%d\n%s --> %s\n%s\n\n" % (k, ts(b["t0"]), ts(b["t1"]), " ".join(p["w"] for p in b["palabras"])))


def transicion(tipo, a, b, k):
    k = clamp(k)
    if tipo == "barrido":
        e = ease_in_out(k)
        off = int(e * W)
        out = np.empty_like(a)
        out[:, : W - off] = a[:, off:]
        out[:, W - off:] = b[:, : off]
        borr = int(10 + 70 * math.sin(math.pi * k))
        return cv2.blur(out, (borr, 1))
    if tipo == "subir":
        e = ease_in_out(k)
        off = int(e * H)
        out = np.empty_like(a)
        out[: H - off] = a[off:]
        out[H - off:] = b[: off]
        borr = int(10 + 70 * math.sin(math.pi * k))
        return cv2.blur(out, (1, borr))
    if tipo == "zoom":
        za = 1 + 0.5 * k
        zb = 1.25 - 0.25 * k
        A = cv2.warpAffine(a, np.float32([[za, 0, W / 2 * (1 - za)], [0, za, H / 2 * (1 - za)]]), (W, H), borderMode=cv2.BORDER_REPLICATE)
        B = cv2.warpAffine(b, np.float32([[zb, 0, W / 2 * (1 - zb)], [0, zb, H / 2 * (1 - zb)]]), (W, H), borderMode=cv2.BORDER_REPLICATE)
        m = suave((k - 0.25) / 0.5)
        return (A * (1 - m) + B * m).astype(np.uint8)
    if tipo == "destello":
        m = 1.0 if k >= 0.5 else 0.0
        mezcla = a * (1 - m) + b * m
        blanco = math.exp(-((k - 0.5) ** 2) / 0.02)
        return np.clip(mezcla * (1 - blanco) + 255 * blanco, 0, 255).astype(np.uint8)
    m = suave(k)
    return (a * (1 - m) + b * m).astype(np.uint8)


def _escribir_wav(ruta, estereo):
    import wave
    x = np.clip(estereo, -1, 1)
    datos = (x * 32767).astype("<i2").tobytes()
    with wave.open(ruta, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sonido.SR)
        w.writeframes(datos)


def comprimir_make(src, dst, dur, audio_wav, max_mb=4.6):
    """Versión para Make Free (≤ 4,6 MB) en dos pasadas de x264; si se pasa, baja la tasa y repite."""
    audio_k = 96
    objetivo = (max_mb * 8 * 1024 * 0.94) / dur - audio_k
    log = os.path.join(os.path.dirname(dst), "_x264")
    for _ in range(5):
        vk = int(max(250, objetivo))
        x264 = ["-c:v", "libx264", "-preset", "slow", "-b:v", "%dk" % vk, "-maxrate", "%dk" % int(vk * 1.5),
                "-bufsize", "%dk" % int(vk * 2), "-pix_fmt", "yuv420p", "-tune", "animation"]
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src] + x264 + ["-pass", "1", "-passlogfile", log, "-an", "-f", "mp4", "/dev/null"], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-i", audio_wav, "-map", "0:v:0", "-map", "1:a:0"] + x264 +
                       ["-pass", "2", "-passlogfile", log, "-c:a", "aac", "-b:a", "%dk" % audio_k, "-shortest", "-movflags", "+faststart", dst], check=True)
        if os.path.getsize(dst) <= max_mb * 1024 * 1024:
            break
        objetivo *= 0.88
    for f in os.listdir(os.path.dirname(dst)):
        if f.startswith("_x264"):
            os.remove(os.path.join(os.path.dirname(dst), f))
    return dst
