"""SHORTS VIDEO CREATOR · montaje vertical 1080×1920 de cada tutorial.

Estructura obligatoria: GANCHO (0–2 s) → PROBLEMA (hasta ~8 s) → TUTORIAL (pasos) → RESULTADO → CTA.
Lo que se ve es real: el código que se escribe es el archivo probado, la terminal muestra la salida real de la
ejecución (con sus tiempos, acelerados si hace falta) y la web es una grabación de Chrome. Encima: cabecera de
marca, barra de progreso, chip de paso, cursor y clics, zoom al detalle, subtítulos grandes palabra a palabra,
música propia y efectos.
"""
import json
import math
import os
import re
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import grabar, musica, recursos, voz
from .config import C, CABECERA_Y, FPS, H, MARCA, SR, SUBS_Y, VENTANA, W

VX0, VY0, VX1, VY1 = VENTANA
BARRA_T = 56
CW, CH = VX1 - VX0, VY1 - VY0 - BARRA_T          # área de contenido 992×850
_FUENTES = {}


def fuente(nombre, tam, peso=None):
    k = (nombre, tam, peso)
    if k not in _FUENTES:
        f = ImageFont.truetype(recursos.fuente(nombre), tam)
        if peso:
            try:
                ejes = f.get_variation_axes()
                vals = []
                for e in ejes:
                    n = e.get("name", b"")
                    n = n.decode() if isinstance(n, bytes) else str(n)
                    if "eight" in n or n.lower().startswith("wght"):
                        vals.append(peso)
                    elif "ptical" in n or n.lower().startswith("opsz"):
                        vals.append(max(e["minimum"], min(e["maximum"], tam)))
                    else:
                        vals.append(e.get("default", e["minimum"]))
                f.set_variation_by_axes(vals)
            except Exception:
                pass
        _FUENTES[k] = f
    return _FUENTES[k]


def _suave(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


# ----------------------------------------------------------------------------- fondo y marco
def _fondo():
    y = np.linspace(0, 1, H)[:, None, None]
    a, b = np.array(C["bg0"], float), np.array(C["bg1"], float)
    img = (a * (1 - y) + b * y) * np.ones((1, W + 80, 1))
    img = img.astype(np.uint8)
    for x in range(0, W + 80, 60):
        img[:, x, :] = np.minimum(255, img[:, x, :].astype(int) + 10)
    for yy in range(0, H, 60):
        img[yy, :, :] = np.minimum(255, img[yy, :, :].astype(int) + 10)
    # halo cian arriba a la derecha
    yy, xx = np.mgrid[0:H, 0:W + 80]
    halo = np.exp(-(((xx - 900) / 520.0) ** 2 + ((yy - 420) / 520.0) ** 2))[:, :, None]
    img = np.clip(img + halo * np.array([0, 40, 55]), 0, 255).astype(np.uint8)
    return img


def _mascara_redondeada(w, h, r):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], r, fill=255)
    return m


# ----------------------------------------------------------------------------- contenidos
PY_KW = r"\b(import|from|for|in|if|else|elif|def|return|with|as|while|not|and|or|True|False|None|class|try|except|lambda)\b"


def _colorear_py(linea):
    """Devuelve [(texto, color)] para una línea de Python (resaltado sencillo y determinista)."""
    tokens = []
    patron = re.compile(r"(#.*$)|([fF]?\"[^\"]*\"|[fF]?'[^']*')|" + PY_KW + r"|(\b\d+(?:\.\d+)?(?:e\d+)?\b)|([A-Za-z_]\w*)(?=\()")
    pos = 0
    for m in patron.finditer(linea):
        if m.start() > pos:
            tokens.append((linea[pos:m.start()], (226, 232, 242)))
        if m.group(1):
            col = (112, 128, 156)
        elif m.group(2):
            col = (255, 204, 120)
        elif m.group(3):
            col = (255, 121, 198)
        elif m.group(4):
            col = (190, 150, 255)
        else:
            col = C["cian"]
        tokens.append((m.group(0), col))
        pos = m.end()
    if pos < len(linea):
        tokens.append((linea[pos:], (226, 232, 242)))
    return tokens


class VistaCodigo:
    """Editor sencillo (no imita ningún programa comercial) que escribe el archivo real carácter a carácter."""

    def __init__(self, ruta, nombre):
        self.lineas = open(ruta, encoding="utf-8").read().rstrip("\n").split("\n")
        self.nombre = nombre
        self.total = sum(len(l) + 1 for l in self.lineas)
        self.f = fuente("JetBrainsMono.ttf", 31, 500)
        self.fn = fuente("JetBrainsMono.ttf", 25, 400)
        self._cache = {}

    def imagen(self, n_chars, resaltar=(), t=0.0):
        k = (n_chars, tuple(resaltar), int(t * 2) % 2)
        if k in self._cache:
            return self._cache[k]
        img = Image.new("RGB", (CW, CH), (17, 21, 33))
        d = ImageDraw.Draw(img)
        lh = 46
        visibles = (CH - 24) // lh
        resto, filas = n_chars, []
        for i, l in enumerate(self.lineas):
            if resto <= 0:
                break
            filas.append((i, l[:resto]))
            resto -= len(l) + 1
        actual = filas[-1][0] if filas else 0
        primera = max(0, actual - visibles + 2)
        for i, txt in filas[primera:]:
            y = 16 + (i - primera) * lh
            if i + 1 in resaltar:
                d.rectangle([0, y - 4, CW, y + lh - 6], fill=(28, 52, 64))
                d.rectangle([0, y - 4, 6, y + lh - 6], fill=C["lima"])
            d.text((18, y + 4), "%2d" % (i + 1), font=self.fn, fill=(82, 94, 120))
            x = 82
            for frag, col in _colorear_py(txt):
                d.text((x, y), frag, font=self.f, fill=col)
                x += d.textlength(frag, font=self.f)
            if i == actual and k[2] == 0 and n_chars < self.total:
                d.rectangle([x + 2, y + 2, x + 16, y + 36], fill=C["cian"])
        self._cache[k] = img
        return img


class VistaTerminal:
    """Terminal que reproduce la sesión REAL (comandos y salida con sus tiempos medidos)."""

    def __init__(self, sesion, tecleo=20.0):
        self.f = fuente("JetBrainsMono.ttf", 30, 500)
        self.fb = fuente("JetBrainsMono.ttf", 30, 800)
        self.guion = []          # [(t_virtual, tipo, texto, prompt)]
        t, t_prev_real = 0.4, None
        for e in sesion["eventos"]:
            if e["tipo"] == "cmd":
                self.guion.append((t, "cmd", e["texto"], e.get("prompt", "~/demo $")))
                t += len(e["texto"]) / tecleo + 0.35
                t_prev_real = e["t"]
            else:
                dt = e["t"] - (t_prev_real or e["t"])
                t += min(0.32, max(0.07, dt))
                t_prev_real = e["t"]
                self.guion.append((t, "out", e["texto"], None))
        self.fin_salida = t + 0.05
        self.total = t + 0.5
        self.tecleo = tecleo
        self.prompt = next((e.get("prompt", "~/demo $") for e in sesion["eventos"] if e["tipo"] == "cmd"), "~/demo $")
        self._cache = {}

    def estado(self, tv):
        lineas = []
        for t0, tipo, txt, prompt in self.guion:
            if t0 > tv:
                break
            if tipo == "cmd":
                n = int((tv - t0) * self.tecleo)
                lineas.append(("cmd", txt[: max(0, n)], prompt, n < len(txt)))
            else:
                lineas.append(("out", txt, None, False))
        return lineas

    def imagen(self, tv, foco=None, t=0.0):
        est = self.estado(tv)
        k = (tuple((a, b) for a, b, _, _ in est), foco, int(t * 2) % 2)
        if k in self._cache:
            return self._cache[k]
        img = Image.new("RGB", (CW, CH), (10, 13, 20))
        d = ImageDraw.Draw(img)
        lh = 45
        # partir líneas largas
        filas = []
        for tipo, txt, prompt, escribiendo in est:
            pre = (prompt + " ") if tipo == "cmd" else ""
            completo = pre + txt
            ancho = 52
            partes = [completo[i:i + ancho] for i in range(0, max(1, len(completo)), ancho)] or [""]
            for j, p in enumerate(partes):
                filas.append((tipo, p, len(pre) if j == 0 and tipo == "cmd" else 0, escribiendo and j == len(partes) - 1, txt))
        if tv >= self.fin_salida and not (est and est[-1][0] == "cmd" and est[-1][3]):
            filas.append(("prompt", self.prompt + " ", 0, True, ""))
        visibles = (CH - 30) // lh
        filas = filas[-visibles:]
        foco_y = None
        for i, (tipo, txt, npre, cursor, orig) in enumerate(filas):
            y = 18 + i * lh
            if foco and foco.lower() in orig.lower() and tipo == "out":
                d.rounded_rectangle([8, y - 6, CW - 8, y + lh - 4], 10, fill=(34, 60, 22), outline=C["lima"], width=3)
                foco_y = y
            if tipo in ("cmd", "prompt"):
                d.text((22, y), txt[:npre] if tipo == "cmd" else txt, font=self.fb, fill=C["cian"])
                x = 22 + d.textlength(txt[:npre], font=self.fb) if tipo == "cmd" else 22 + d.textlength(txt, font=self.fb)
                if tipo == "cmd":
                    d.text((x, y), txt[npre:], font=self.f, fill=C["texto"])
                    x += d.textlength(txt[npre:], font=self.f)
                if cursor and k[2] == 0:
                    d.rectangle([x + 2, y + 3, x + 18, y + 34], fill=C["texto"])
            else:
                col = C["texto"]
                if re.match(r"\s*(DUPLICADO|AVISO|REPETID)", txt, re.I):
                    col = C["aviso"]
                if re.search(r"(liberar|total|resultado|listo|hecho)", orig, re.I):
                    col = C["lima"]
                d.text((22, y), txt, font=self.fb if col == C["lima"] else self.f, fill=col)
        self._cache[k] = (img, foco_y)
        return img, foco_y


def _ajustar(img, w, h):
    iw, ih = img.size
    s = min(w / iw, h / ih)
    nw, nh = int(iw * s), int(ih * s)
    lienzo = Image.new("RGB", (w, h), (12, 14, 20))
    lienzo.paste(img.resize((nw, nh), Image.LANCZOS), ((w - nw) // 2, (h - nh) // 2))
    return lienzo, s, ((w - nw) // 2, (h - nh) // 2)


def _zoom(img, z, cx, cy):
    """Recorta alrededor de (cx, cy) con aumento z (1 = sin zoom) y devuelve el tamaño original."""
    if z <= 1.001:
        return img
    w, h = img.size
    cw, ch = w / z, h / z
    x0 = min(max(0, cx - cw / 2), w - cw)
    y0 = min(max(0, cy - ch / 2), h - ch)
    arr = np.asarray(img)[int(y0):int(y0 + ch), int(x0):int(x0 + cw)]
    return Image.fromarray(cv2.resize(arr, (w, h), interpolation=cv2.INTER_CUBIC))


# ----------------------------------------------------------------------------- subtítulos
def bloques_subtitulos(palabras, max_pal=4, max_chars=28):
    bloques, actual = [], []
    for p in palabras:
        texto = " ".join(x["w"] for x in actual + [p])
        if actual and (len(actual) >= max_pal or len(texto) > max_chars or re.search(r"[.!?…:]$", actual[-1]["w"])
                       or actual[-1]["w"].endswith(",")):
            bloques.append(actual)
            actual = []
        actual.append(p)
    if actual:
        bloques.append(actual)
    # sin palabras sueltas al final de una frase («cada / día.»): se unen al bloque anterior si cabe
    i = 1
    while i < len(bloques):
        b = bloques[i]
        prev = bloques[i - 1]
        if len(b) == 1 and len(prev) <= 4 and not re.search(r"[.!?…:,]$", prev[-1]["w"]) \
                and len(" ".join(x["w"] for x in prev + b)) <= 32:
            prev.extend(bloques.pop(i))
            continue
        i += 1
    return [{"t0": b[0]["t0"], "t1": b[-1]["t1"], "palabras": b} for b in bloques]


def dibujar_subtitulo(lienzo, bloque, t):
    d = ImageDraw.Draw(lienzo)
    f = fuente("Inter.ttf", 70, 850)
    ws = bloque["palabras"]
    textos = [w["w"] for w in ws]
    anchos = [d.textlength(x, font=f) for x in textos]
    esp = d.textlength(" ", font=f)
    # una o dos líneas
    lineas, cur, ancho_cur = [], [], 0
    for i, a in enumerate(anchos):
        if cur and ancho_cur + esp + a > W - 150:
            lineas.append(cur)
            cur, ancho_cur = [], 0
        cur.append(i)
        ancho_cur += (esp if len(cur) > 1 else 0) + a
    lineas.append(cur)
    y = SUBS_Y - 22          # anclado arriba: con 2 líneas baja, nunca tapa el rótulo del paso (y ≤ 1416)
    for ln in lineas:
        tot = sum(anchos[i] for i in ln) + esp * (len(ln) - 1)
        x = (W - tot) / 2
        for i in ln:
            activa = ws[i]["t0"] <= t < ws[i]["t1"] + 0.05
            col = C["lima"] if activa else C["texto"]
            d.text((x, y), textos[i], font=f, fill=col, stroke_width=7, stroke_fill=(0, 0, 0))
            x += anchos[i] + esp
        y += 88


# ----------------------------------------------------------------------------- montaje
class Montaje:
    def __init__(self, guion, herramienta, capturas_web, carpeta_tutorial, salida):
        self.g = guion
        self.h = herramienta
        self.web = capturas_web
        self.dir = carpeta_tutorial
        self.out = salida
        self.fondo = _fondo()
        self.mask = _mascara_redondeada(VX1 - VX0, VY1 - VY0, 28)
        self.vistas = {}
        self.efectos = []
        self.registro = {"escenas": []}

    # --- voz y tiempos
    def preparar_audio(self):
        from .config import VOZ
        preset = self.g.get("voice", VOZ)
        t, piezas, palabras = 0.0, [], []
        for i, e in enumerate(self.g["escenas"]):
            a, ws = voz.sintetizar(e["say"], preset, e.get("ritmo_voz", 0.93 if e["beat"] == "gancho" else 1.0))
            pre = 0.04 if i == 0 else 0.12
            post = {"gancho": 0.06, "cta": 0.9}.get(e["beat"], 0.18)
            dur = pre + len(a) / SR + post
            dur = max(dur, e.get("min_s", 0))
            e["_t0"], e["_t1"] = t, t + dur
            e["_palabras"] = [{"w": w["w"], "t0": round(t + pre + w["t0"], 3), "t1": round(t + pre + w["t1"], 3)} for w in ws]
            seg = np.zeros(int(dur * SR))
            ini = int(pre * SR)
            seg[ini:ini + len(a)] = a[: len(seg) - ini]
            piezas.append(seg)
            palabras += e["_palabras"]
            t += dur
        self.dur = t
        self.voz = np.concatenate(piezas)
        self.palabras = palabras
        self.subs = []
        for e in self.g["escenas"]:
            self.subs += bloques_subtitulos(e["_palabras"])
        return t

    # --- vistas
    def _vista(self, v):
        if v["tipo"] == "codigo":
            k = ("codigo", v["archivo"])
            if k not in self.vistas:
                self.vistas[k] = VistaCodigo(os.path.join(self.h["carpeta_trabajo"], v["archivo"]), v["archivo"])
            return self.vistas[k]
        if v["tipo"] in ("terminal", "resultado"):
            k = ("terminal", v["clip"])
            if k not in self.vistas:
                self.vistas[k] = VistaTerminal(self.h["sesiones"][v["clip"]])
            return self.vistas[k]
        return None

    def contenido(self, e, t):
        """Imagen CW×CH del contenido de la ventana para la escena e en el instante t, y su título."""
        v = e["visual"]
        u = (t - e["_t0"]) / max(0.01, e["_t1"] - e["_t0"])
        a, b = v.get("progreso", [0, 1])
        p = a + (b - a) * _suave(min(1.0, u * v.get("ritmo", 1.15)))
        foco_xy = None
        if v["tipo"] == "codigo":
            vc = self._vista(v)
            img = vc.imagen(int(vc.total * p), v.get("resaltar", ()), t)
            titulo = v["archivo"]
            if b > a and p < b:
                self._tecleo(t)
        elif v["tipo"] in ("terminal", "resultado"):
            vt = self._vista(v)
            img, fy = vt.imagen(vt.total * p, v.get("foco_linea"), t)
            titulo = v.get("titulo", "Terminal")
            if fy is not None:
                foco_xy = (0, fy + 20)
        elif v["tipo"] == "teclas":
            img = self._teclas(v, t - e["_t0"], e["_t1"] - e["_t0"])
            titulo = v.get("titulo", "El atajo")
        elif v["tipo"] in ("web", "escritorio"):
            info = self.web[v["clip"]]
            desde, hasta = self.tramo(v)
            tt = desde + (hasta - desde) * min(1.0, u)
            ruta = grabar.frame_en(info, tt)
            fr = Image.open(ruta).convert("RGB")
            esc_c = fr.width / float(info.get("viewport", [self.web_vw(v["clip"])])[0])
            rx, ry = 0, 0
            if v.get("recorte"):   # recorte de edición sobre la grabación real (px CSS: x, y, w, h)
                rx, ry, rw, rh = [int(c * esc_c) for c in v["recorte"]]
                fr = fr.crop((rx, ry, rx + rw, ry + rh))
            img, s, (ox, oy) = _ajustar(fr, CW, CH)
            titulo = v.get("titulo", "Navegador")
            for ev in info["eventos"]:
                te, tipo, caja = ev[0], ev[1], ev[2]
                if caja and tipo in ("clic", "escribir") and desde - 0.6 <= te <= hasta:
                    cx = ox + ((caja[0] + caja[2] / 2) * esc_c - rx) * s
                    cy = oy + ((caja[1] + caja[3] / 2) * esc_c - ry) * s
                    dt = tt - te
                    if -0.7 <= dt <= 0.9:
                        dd = ImageDraw.Draw(img)
                        if dt >= 0 and tipo == "clic":
                            r = 18 + 70 * dt
                            dd.ellipse([cx - r, cy - r, cx + r, cy + r], outline=C["lima"], width=5)
                        dd.polygon([(cx, cy), (cx + 30, cy + 36), (cx + 13, cy + 34), (cx + 4, cy + 52)], fill=(255, 255, 255), outline=(0, 0, 0))
                        foco_xy = (cx, cy)
            for ev in info["eventos"]:
                if ev[1] == "teclas" and ev[3] and 0 <= tt - ev[0] <= 1.4 and desde - 0.2 <= ev[0] <= hasta:
                    img = self._chips(img, ev[3], tt - ev[0])
            if v.get("foco") is not None:      # punto de la ventana hacia el que se acerca la cámara (px del área de contenido)
                foco_xy = tuple(v["foco"])
        elif v["tipo"] == "cta":
            img = self._tarjeta_cta(t - e["_t0"])
            titulo = MARCA
        else:
            raise ValueError("Visual desconocido: %s" % v["tipo"])
        z = v.get("zoom", 1.0)
        zt = 1.0
        if z > 1 and foco_xy:
            zt = 1 + (z - 1) * _suave((t - e["_t0"]) / 0.7)
        # deriva lenta de cámara en todos los planos (nunca un plano clavado)
        zt *= 1.0 + 0.045 * u
        if v["tipo"] != "cta":
            fx, fy_ = foco_xy if foco_xy else (CW / 2, CH * 0.35)
            img = _zoom(img, zt, fx, fy_)
        if v.get("destacado"):
            img = self._destacado(img, v["destacado"], t - e["_t0"] - v["destacado"].get("desde", 0.0))
        return img, titulo

    def _chips(self, img, rotulo, dt):
        """Teclas pulsadas de verdad en la grabación (se dibujan en el instante en que se pulsaron)."""
        img = img.copy()
        d = ImageDraw.Draw(img, "RGBA")
        k = _suave(dt / 0.15) * (1 - _suave((dt - 1.1) / 0.3))
        f = fuente("Inter.ttf", 50, 800)
        partes = [x.strip() for x in rotulo.split("+")]
        anchos = [d.textlength(p_, font=f) + 56 for p_ in partes]
        total = sum(anchos) + 52 * (len(partes) - 1)
        x = (CW - total) / 2
        y = CH - 170
        for i, (p_, w) in enumerate(zip(partes, anchos)):
            d.rounded_rectangle([x, y + 8, x + w, y + 104], 18, fill=(0, 0, 0, int(120 * k)))
            d.rounded_rectangle([x, y, x + w, y + 96], 18, fill=(250, 250, 252, int(245 * k)), outline=C["cian"] + (int(255 * k),), width=4)
            d.text((x + 28, y + 16), p_, font=f, fill=(20, 24, 36, int(255 * k)))
            x += w
            if i < len(partes) - 1:
                d.text((x + 12, y + 14), "+", font=f, fill=C["lima"] + (int(255 * k),))
                x += 52
        return img

    def _teclas(self, v, dt, dur):
        """Animación explicativa del atajo: las teclas aparecen y se hunden una a una (no imita ninguna pantalla)."""
        img = Image.new("RGB", (CW, CH), (14, 20, 34))
        d = ImageDraw.Draw(img)
        teclas = v["teclas"]
        f = fuente("Inter.ttf", 66, 800)
        anchos = [max(170, d.textlength(t_, font=f) + 80) for t_ in teclas]
        total = sum(anchos) + 70 * (len(teclas) - 1)
        x = (CW - total) / 2
        y = 300
        for i, (t_, w) in enumerate(zip(teclas, anchos)):
            ti = 0.25 + i * 0.45
            k = _suave((dt - ti) / 0.2)
            hundida = 10 if dt >= ti + 0.25 else 0
            if k > 0:
                d.rounded_rectangle([x, y + 22, x + w, y + 182], 26, fill=(4, 6, 12))
                d.rounded_rectangle([x, y + hundida, x + w, y + 160 + hundida], 26, fill=(236, 240, 247), outline=C["cian"], width=5)
                tw = d.textlength(t_, font=f)
                d.text((x + (w - tw) / 2, y + 38 + hundida), t_, font=f, fill=(16, 20, 32))
            x += w
            if i < len(teclas) - 1 and dt >= ti + 0.2:
                d.text((x + 16, y + 40), "+", font=f, fill=C["lima"])
            x += 70
        if v.get("nota") and dt > 0.25 + len(teclas) * 0.45:
            fn = fuente("Inter.ttf", 42, 700)
            wn = d.textlength(v["nota"], font=fn)
            d.text(((CW - wn) / 2, 560), v["nota"], font=fn, fill=C["gris"])
        if v.get("encima"):
            fe = fuente("Inter.ttf", 44, 800)
            we = d.textlength(v["encima"], font=fe)
            d.text(((CW - we) / 2, 170), v["encima"], font=fe, fill=C["cian"])
        return img

    def _destacado(self, img, dz, dt):
        """Cifra o frase clave del resultado, sacada de la salida real (la comprueba el QC de cifras)."""
        img = img.copy()
        k = _suave(dt / 0.3)
        if k <= 0:
            return img
        d = ImageDraw.Draw(img, "RGBA")
        f1 = fuente("BebasNeue.ttf", int(dz.get("tam", 170) * (0.8 + 0.2 * k)))
        f2 = fuente("Inter.ttf", 40, 800)
        w1 = d.textlength(dz["texto"], font=f1)
        w2 = d.textlength(dz.get("sub", ""), font=f2)
        bw = max(w1, w2) + 90
        y0 = CH - 330
        d.rounded_rectangle([(CW - bw) / 2, y0, (CW + bw) / 2, y0 + 270], 30, fill=(10, 16, 28, int(235 * k)), outline=C["lima"] + (int(255 * k),), width=4)
        d.text(((CW - w1) / 2, y0 + 18), dz["texto"], font=f1, fill=C["lima"] + (int(255 * k),))
        d.text(((CW - w2) / 2, y0 + 200), dz.get("sub", ""), font=f2, fill=C["texto"] + (int(255 * k),))
        return img

    def tramo(self, v):
        """Tramo de la grabación de una escena: absoluto (desde/hasta) o relativo a un evento real
        ({"evento": n, "antes": s, "despues": s}) o el final ({"final": s})."""
        info = self.web[v["clip"]]
        if "evento" in v:
            te = info["eventos"][v["evento"]][0]
            return max(0.0, te - v.get("antes", 1.0)), min(info["duracion"], te + v.get("despues", 1.0))
        if "final" in v:
            return max(0.0, info["duracion"] - v["final"]), info["duracion"]
        return v.get("desde", 0.0), v.get("hasta", info["duracion"])

    def web_vw(self, clip):
        cap = next(c for c in self.g["capturas"] if c["id"] == clip)
        return cap.get("viewport", [496, 425])[0]

    def _tecleo(self, t):
        if not self.efectos or t - self.efectos[-1][0] > 0.11:
            self.efectos.append((t, "tecla"))

    def _tarjeta_cta(self, dt):
        img = Image.new("RGB", (CW, CH), (14, 20, 34))
        d = ImageDraw.Draw(img)
        s = 0.85 + 0.15 * _suave(dt / 0.35)
        rebote = 14 * math.sin(dt * 5.0)
        # icono de guardar (marcador) que late
        cx, cy, r = CW // 2, int(250 * s + rebote), int(110 * s * (1 + 0.04 * math.sin(dt * 7)))
        d.polygon([(cx - r * 0.7, cy - r), (cx + r * 0.7, cy - r), (cx + r * 0.7, cy + r), (cx, cy + r * 0.45), (cx - r * 0.7, cy + r)], fill=C["lima"])
        f1 = fuente("BebasNeue.ttf", int(150 * s))
        f2 = fuente("Inter.ttf", 44, 700)
        for txt, f, y, col in [("GUÁRDALO", f1, 420, C["texto"]), (self.g.get("cta_linea", "para cuando lo necesites"), f2, 590, C["gris"]),
                               ("SÍGUEME: UN TRUCO ÚTIL CADA DÍA", fuente("Inter.ttf", 42, 800), 700, C["cian"])]:
            w = d.textlength(txt, font=f)
            d.text(((CW - w) / 2, y), txt, font=f, fill=col)
        # flecha que invita a seguir el canal
        ay = 790 + 10 * math.sin(dt * 6)
        d.polygon([(CW / 2 - 34, ay), (CW / 2 + 34, ay), (CW / 2, ay + 40)], fill=C["cian"])
        return img

    # --- cabecera, chips, gancho
    def _cabecera(self, lienzo, t, e):
        d = ImageDraw.Draw(lienzo)
        f = fuente("Inter.ttf", 34, 800)
        n = self.g.get("numero")  # None = reserva sin número (se numera al programarlo)
        chip = "%s · Nº %03d" % (MARCA, int(n)) if n is not None else MARCA
        w = d.textlength(chip, font=f)
        d.rounded_rectangle([VX0, CABECERA_Y, VX0 + w + 56, CABECERA_Y + 60], 30, fill=(16, 30, 46), outline=C["cian"], width=3)
        d.ellipse([VX0 + 20, CABECERA_Y + 23, VX0 + 34, CABECERA_Y + 37], fill=C["lima"])
        d.text((VX0 + 44, CABECERA_Y + 11), chip, font=f, fill=C["texto"])
        etiqueta = {"gancho": "", "problema": "EL PROBLEMA", "resultado": "RESULTADO", "cta": ""}.get(e["beat"])
        if e["beat"] == "tutorial":
            etiqueta = "PASO %d/%d" % (e.get("paso", 1), self.n_pasos)
        if etiqueta:
            fe = fuente("Inter.ttf", 34, 900)
            we = d.textlength(etiqueta, font=fe)
            k = _suave((t - e["_t0"]) / 0.25)
            x1 = VX1
            col = C["lima"] if e["beat"] in ("tutorial", "resultado") else C["aviso"]
            d.rounded_rectangle([x1 - we - 48, CABECERA_Y, x1, CABECERA_Y + 60], 30, fill=col)
            d.text((x1 - we - 24, CABECERA_Y + 10 + (1 - k) * 12), etiqueta, font=fe, fill=(8, 12, 24))
        # barra de progreso (retención)
        y = CABECERA_Y + 86
        d.rounded_rectangle([VX0, y, VX1, y + 10], 5, fill=(36, 44, 66))
        d.rounded_rectangle([VX0, y, VX0 + (VX1 - VX0) * min(1, t / self.dur), y + 10], 5, fill=C["cian"])
        # título del paso, si lo hay
        if e.get("titulo_paso"):
            ft = fuente("Inter.ttf", 40, 800)
            d.text((VX0 + 4, VY1 + 18), e["titulo_paso"], font=ft, fill=C["cian"])

    def _ventana(self, lienzo, img, titulo, t, e, entrada):
        panel = Image.new("RGB", (VX1 - VX0, VY1 - VY0), C["barra"])
        d = ImageDraw.Draw(panel)
        for i, col in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
            d.ellipse([22 + i * 34, 19, 40 + i * 34, 37], fill=col)
        ft = fuente("Inter.ttf", 28, 600)
        wt = d.textlength(titulo, font=ft)
        d.text(((VX1 - VX0 - wt) / 2, 12), titulo, font=ft, fill=C["gris"])
        panel.paste(img, (0, BARRA_T))
        # entrada de escena: deslizamiento + escala corta
        if entrada < 1:
            k = _suave(entrada)
            esc = 0.94 + 0.06 * k
            pw, ph = int(panel.width * esc), int(panel.height * esc)
            panel_s = panel.resize((pw, ph), Image.BILINEAR)
            mask = self.mask.resize((pw, ph))
            dx = int((1 - k) * 140)
            lienzo.paste(panel_s, (VX0 + (VX1 - VX0 - pw) // 2 + dx, VY0 + (VY1 - VY0 - ph) // 2), mask)
        else:
            lienzo.paste(panel, (VX0, VY0), self.mask)
        ImageDraw.Draw(lienzo).rounded_rectangle([VX0 - 2, VY0 - 2, VX1 + 2, VY1 + 2], 30, outline=(60, 76, 108), width=2)

    def _gancho(self, lienzo, t, e):
        if not e.get("rotulo"):
            return
        k = _suave((t - e["_t0"]) / 0.22)
        f = fuente("BebasNeue.ttf", int(118 * (0.86 + 0.14 * k)))
        d = ImageDraw.Draw(lienzo, "RGBA")
        lineas = e["rotulo"].split("\n")
        alto = len(lineas) * 116
        y0 = 560 - alto // 2
        d.rounded_rectangle([VX0 + 30, y0 - 34, VX1 - 30, y0 + alto + 20], 26, fill=(6, 10, 20, int(225 * k)))
        for i, ln in enumerate(lineas):
            w = d.textlength(ln, font=f)
            col = C["lima"] if i == len(lineas) - 1 else C["texto"]
            d.text(((W - w) / 2, y0 + i * 116), ln, font=f, fill=col + (int(255 * k),))

    def fotograma(self, t):
        x0 = int((t * 6) % 60)
        lienzo = Image.fromarray(self.fondo[:, x0:x0 + W])
        e = next((x for x in self.g["escenas"] if x["_t0"] <= t < x["_t1"]), self.g["escenas"][-1])
        img, titulo = self.contenido(e, t)
        entrada = (t - e["_t0"]) / 0.22 if e is not self.g["escenas"][0] else 1.0
        self._ventana(lienzo, img, titulo, t, e, entrada)
        self._cabecera(lienzo, t, e)
        if e["beat"] == "gancho":
            self._gancho(lienzo, t, e)
        b = next((x for x in self.subs if x["t0"] - 0.02 <= t < x["t1"] + 0.12), None)
        if b:
            dibujar_subtitulo(lienzo, b, t)
        return lienzo

    def render(self, nombre):
        self.n_pasos = max([e.get("paso", 0) for e in self.g["escenas"]] + [1])
        dur = self.preparar_audio()
        # efectos en los cortes, pasos y resultado
        for i, e in enumerate(self.g["escenas"]):
            if i > 0:
                self.efectos.append((e["_t0"], "whoosh"))
            if e["beat"] == "tutorial":
                self.efectos.append((e["_t0"] + 0.05, "pop"))
            if e["beat"] == "resultado":
                self.efectos.append((e["_t0"] + 0.25, "ding"))
            elif e["visual"].get("destacado", {}).get("desde"):
                self.efectos.append((e["_t0"] + e["visual"]["destacado"]["desde"], "pop"))
            if e["visual"]["tipo"] in ("web", "escritorio"):
                info = self.web[e["visual"]["clip"]]
                desde, hasta = self.tramo(e["visual"])
                for ev in info["eventos"]:
                    te, tipo = ev[0], ev[1]
                    if tipo in ("clic", "teclas") and desde <= te <= hasta:
                        self.efectos.append((e["_t0"] + (te - desde) / max(0.01, hasta - desde) * (e["_t1"] - e["_t0"]), "clic"))
            if e["visual"]["tipo"] == "teclas":
                for i in range(len(e["visual"]["teclas"])):
                    self.efectos.append((e["_t0"] + 0.5 + i * 0.45, "clic"))
        os.makedirs(self.out, exist_ok=True)
        hq = os.path.join(self.out, nombre + "_hq.mp4")
        video_mudo = os.path.join(self.out, "_video.mp4")
        n = int(math.ceil(dur * FPS))
        proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
                                 "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
                                 video_mudo], stdin=subprocess.PIPE)
        self.miniaturas = {}
        for i in range(n):
            t = i / FPS
            fr = self.fotograma(t)
            proc.stdin.write(fr.tobytes())
            for k, e in enumerate(self.g["escenas"]):
                medio = (e["_t0"] + e["_t1"]) / 2
                if abs(t - medio) < 0.5 / FPS and k not in self.miniaturas:
                    self.miniaturas[k] = fr.copy()
        proc.stdin.close()
        proc.wait()
        # audio: voz + música propia + efectos, normalizado a −14 LUFS
        mezcla = musica.mezclar(self.voz, dur, sorted(self.efectos), semilla=int(self.g.get("music_seed", 3)))
        wav = os.path.join(self.out, "_mezcla.wav")
        import wave
        with wave.open(wav, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(SR)
            wf.writeframes((np.clip(mezcla, -1, 1) * 32767).astype("<i2").tobytes())
        norm = os.path.join(self.out, "_mezcla_norm.wav")
        normalizar(wav, norm)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video_mudo, "-i", norm, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                        "-shortest", "-movflags", "+faststart", hq], check=True)
        mk = os.path.join(self.out, nombre + ".mp4")
        comprimir_make(video_mudo, mk, dur, audio_wav=norm)
        # subtítulos SRT (para la descripción y revisión)
        with open(os.path.join(self.out, nombre + ".srt"), "w", encoding="utf-8") as f:
            for i, b in enumerate(self.subs, 1):
                f.write("%d\n%s --> %s\n%s\n\n" % (i, _srt(b["t0"]), _srt(b["t1"]), " ".join(w["w"] for w in b["palabras"])))
        os.makedirs(os.path.join(self.out, "stills"), exist_ok=True)
        for k, img in self.miniaturas.items():
            img.save(os.path.join(self.out, "stills", "escena_%02d.jpg" % (k + 1)), quality=88)
        for x in ("_video.mp4", "_mezcla.wav", "_mezcla_norm.wav"):
            try:
                os.remove(os.path.join(self.out, x))
            except OSError:
                pass
        return {"hq": hq, "make": mk, "duracion": round(dur, 2), "palabras": len(self.palabras), "efectos": len(self.efectos)}


def _srt(t):
    ms = int(round(t * 1000))
    return "%02d:%02d:%02d,%03d" % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)


def normalizar(src, dst, objetivo=-14.0, pico=-2.5):
    """loudnorm en dos pasadas (EBU R128) → −14 LUFS integrados, pico real ≤ −2 dBTP (margen para el AAC)."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", src, "-af", "loudnorm=I=%s:TP=%s:LRA=11:print_format=json" % (objetivo, pico),
                        "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    if m:
        j = json.loads(m.group(0))
        filtro = ("loudnorm=I=%s:TP=%s:LRA=11:measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:offset=%s:linear=true"
                  % (objetivo, pico, j["input_i"], j["input_tp"], j["input_lra"], j["input_thresh"], j["target_offset"]))
    else:
        filtro = "loudnorm=I=%s:TP=%s:LRA=11" % (objetivo, pico)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-af", filtro, "-ar", str(SR), dst], check=True)


def comprimir_make(src, dst, dur, max_mb=None, audio_wav=None):
    """Versión para Make Free (≤ 4,6 MB) en dos pasadas de x264; si se pasa, baja la tasa y repite.
    El audio se codifica UNA sola vez desde la mezcla WAV (un AAC sobre otro AAC dispara los picos)."""
    from .config import MAX_MB_MAKE
    max_mb = max_mb or MAX_MB_MAKE
    audio_k = 96
    objetivo = (max_mb * 8 * 1024 * 0.94) / dur - audio_k
    entradas = ["-i", src] + (["-i", audio_wav, "-map", "0:v:0", "-map", "1:a:0"] if audio_wav else [])
    for _ in range(4):
        vk = int(max(250, objetivo))
        x264 = ["-c:v", "libx264", "-preset", "slow", "-b:v", "%dk" % vk, "-maxrate", "%dk" % int(vk * 1.6),
                "-bufsize", "%dk" % int(vk * 2), "-pix_fmt", "yuv420p", "-tune", "stillimage"]
        log = os.path.join(os.path.dirname(dst), "_x264")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src] + x264 + ["-pass", "1", "-passlogfile", log, "-an", "-f", "mp4", "/dev/null"], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + entradas + x264 + ["-pass", "2", "-passlogfile", log,
                        "-c:a", "aac", "-b:a", "%dk" % audio_k, "-shortest", "-movflags", "+faststart", dst], check=True)
        if os.path.getsize(dst) <= max_mb * 1024 * 1024:
            break
        objetivo *= 0.88
    for f in os.listdir(os.path.dirname(dst)):
        if f.startswith("_x264"):
            os.remove(os.path.join(os.path.dirname(dst), f))
    # los clics y teclas pueden hacer que el AAC pase de −1 dBFS: se mide y se rehace solo el audio desde la mezcla WAV
    ganancia = 0.0
    for _ in range(3):
        pico = _pico(dst)
        if not audio_wav or pico is None or pico <= -1.2:
            break
        ganancia += -1.5 - pico
        tmp = dst + ".tmp.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", dst, "-i", audio_wav, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                        "-af", "volume=%.2fdB" % ganancia, "-c:a", "aac", "-b:a", "%dk" % audio_k, "-shortest", "-movflags", "+faststart", tmp],
                       check=True)
        os.replace(tmp, dst)
    return dst


def _pico(f):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", f, "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"Peak:\s+(-?[\d.]+) dBFS", r.stderr[r.stderr.rfind("Summary:"):])
    return float(m.group(1)) if m else None
