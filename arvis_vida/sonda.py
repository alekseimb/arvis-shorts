"""QC FASE 1 · sonda geométrica local (ARVIS 3.1, 22/11/2026).

Detecta, sin mirar imágenes, los defectos de composición que antes solo encontraba la revisión visual de Claude
(y que obligaban a 3 montajes y a leer 30–60 fotogramas por Short):
  · solape_subtitulos  elemento que pisa los subtítulos
  · tapado_por_rotulo  elemento debajo del rótulo grande de la escena
  · invade_cabecera    elemento sobre el chip «LIFEHACKS · Nº» / barra de progreso
  · cortado            elemento cortado por el borde del vídeo (ya terminada su entrada)
  · solape_elementos   dos objetos que se tapan entre sí (aviso: puede ser intencionado)
  · flecha_sobre_texto flecha que cruza un rótulo de texto
  · mitad_vacia        mitad izquierda o derecha sin ningún objeto ≥ 2 s
  · escena_vacia       zona central sin objetos ≥ 1 s
Muestrea la composición real del motor cada 0,25 s (las mismas funciones que pintan el vídeo; registra las cajas de
cada sprite por su canal alfa), guarda solo los fotogramas sospechosos y 2–3 hojas de contactos (un fotograma cada 1,5 s).

FASE 2 (Claude): revisa SOLO la lista «revisar» = fotogramas representativos del motor + hojas de contactos +
sospechosos. La sonda no aprueba nada: avisa. La nota final sigue saliendo de arvis_estudio.calidad (≥ 85).

Uso:
  python3 -m arvis_vida.sonda guiones_vida/SH-0NN/guion.json --out out/SH-0NN   # ANTES de montar (~20–30 s, sin vídeo)
  (producir.py la ejecuta sola después de cada montaje y deja out/SH-0NN/SH-0NN_sonda.json)
"""
import argparse
import json
import math
import os
import sys

from PIL import Image, ImageDraw

from . import motor as M
from . import texto

PASO = 0.25
DECORATIVOS = {"particulas"}
SUPERPUESTOS = {"sello", "flecha"}          # se ponen encima a propósito (✓/✗, flechas)
ZONA_Y = (205, texto.SUBS_Y - 10)            # zona de contenido: bajo la cabecera y sobre los subtítulos
CABECERA = (30, 80, M.W - 30, 196)
GRAVES = ("solape_subtitulos", "tapado_por_rotulo", "cortado", "escena_vacia", "flecha_sobre_texto")
MAX_SOSPECHOSOS = 8


def _area(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def _inter(a, b):
    return _area((max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])))


def _union(cajas):
    cajas = [c for c in cajas if c]
    if not cajas:
        return None
    return (min(c[0] for c in cajas), min(c[1] for c in cajas), max(c[2] for c in cajas), max(c[3] for c in cajas))


def _nombre(el):
    s = el.s
    n = s.get("activo") or s.get("texto") or s.get("simbolo") or s.get("clase") or el.tipo
    return ("%s:%s" % (el.tipo, n)).replace("\n", " ")[:40]


class _Grabadora:
    """Envuelve motor._pegar y Elemento.dibujar para anotar la caja visible de cada elemento pintado."""

    def __init__(self):
        self.actual = None
        self.items = []
        self._pegar0 = M._pegar
        self._dibujar0 = M.Elemento.dibujar

    def __enter__(self):
        grab = self

        def pegar(lienzo, im, cam, x, y, ancho, rot, alfa):
            el = grab.actual
            if el is not None and ancho >= 2 and alfa > 0.01:
                bb = im.getchannel("A").getbbox() if im.mode == "RGBA" else (0, 0, im.width, im.height)
                if bb:
                    sx, sy = cam.a_pantalla(x, y)
                    w = ancho * cam.z
                    h = w * im.height / im.width
                    fx, fy = w / im.width, h / im.height
                    x0, y0 = sx - w / 2 + bb[0] * fx, sy - h / 2 + bb[1] * fy
                    x1, y1 = sx - w / 2 + bb[2] * fx, sy - h / 2 + bb[3] * fy
                    if abs(rot) > 0.3:
                        cx, cy, r = sx, sy, math.radians(-rot)
                        pts = [((px - cx) * math.cos(r) - (py - cy) * math.sin(r) + cx, (px - cx) * math.sin(r) + (py - cy) * math.cos(r) + cy)
                               for px, py in ((x0, y0), (x1, y0), (x0, y1), (x1, y1))]
                        x0, y0 = min(p[0] for p in pts), min(p[1] for p in pts)
                        x1, y1 = max(p[0] for p in pts), max(p[1] for p in pts)
                    grab.items.append({"el": el, "caja": (x0, y0, x1, y1), "alfa": alfa})
            return grab._pegar0(lienzo, im, cam, x, y, ancho, rot, alfa)

        def dibujar(el, lienzo, t, cam):
            grab.actual = el
            try:
                r = grab._dibujar0(el, lienzo, t, cam)
                if el.tipo == "flecha" and el.visible(t):
                    s = el.s
                    u = M.clamp((t - el.t_in) / float(s.get("dur", 0.45)))
                    if u > 0.05:
                        (ax, ay), (bx, by) = s["de"], s["a"]
                        ax, ay, bx, by = ax * M.W, ay * M.H, bx * M.W, by * M.H
                        cur = float(s.get("curva", 0.25))
                        mx, my = (ax + bx) / 2 - (by - ay) * cur, (ay + by) / 2 + (bx - ax) * cur
                        pts = []
                        for i in range(int(20 * u) + 1):
                            k = i / 20
                            pts.append(cam.a_pantalla((1 - k) ** 2 * ax + 2 * (1 - k) * k * mx + k * k * bx,
                                                      (1 - k) ** 2 * ay + 2 * (1 - k) * k * my + k * k * by))
                        grab.items.append({"el": el, "caja": (min(p[0] for p in pts) - 15, min(p[1] for p in pts) - 15,
                                                               max(p[0] for p in pts) + 15, max(p[1] for p in pts) + 15),
                                           "alfa": 1.0, "puntos": pts})
                return r
            finally:
                grab.actual = None

        M._pegar = pegar
        M.Elemento.dibujar = dibujar
        return self

    def __exit__(self, *a):
        M._pegar = self._pegar0
        M.Elemento.dibujar = self._dibujar0


def _caja_subtitulos(m, t):
    for b in m.subs:
        if b["t0"] - 0.05 <= t < b["t1"] + 0.12:
            d = ImageDraw.Draw(Image.new("RGB", (8, 8)))
            f = texto.fuente("Inter.ttf", 74, 900)
            anchos = [d.textlength(w["w"], font=f) for w in b["palabras"]]
            esp = d.textlength(" ", font=f)
            lineas, cur, ac = [], [], 0
            for i, a in enumerate(anchos):
                if cur and ac + esp + a > M.W - 170:
                    lineas.append(ac)
                    cur, ac = [], 0
                cur.append(i)
                ac += (esp if len(cur) > 1 else 0) + a
            lineas.append(ac)
            ancho = max(lineas)
            bb = d.textbbox((0, texto.SUBS_Y), "ÁÉgjpqy", font=f, stroke_width=8)
            return ((M.W - ancho) / 2 - 8, bb[1], (M.W + ancho) / 2 + 8, bb[3] + 90 * (len(lineas) - 1))
    return None


def _caja_rotulo(m, i, t):
    sprites = m.titulos[i]
    if not sprites:
        return None
    e, l = m.escenas[i], m.lineas[i]
    y = int(e.get("titulo_y", 0.150) * M.H)
    t_in = l.tiempo(e.get("titulo_en"), 0.0)
    cajas = []
    for k, s in enumerate(sprites):
        if t - t_in - k * 0.10 >= 0.12:
            bb = s.getchannel("A").getbbox() or (0, 0, s.width, s.height)
            x0 = M.W / 2 - s.width / 2
            cajas.append((x0 + bb[0], y + bb[1], x0 + bb[2], y + bb[3]))
        y += s.height - 8
    return _union(cajas)


def _muestrear(m, guardar_cada=1.5):
    """Recorre el vídeo cada PASO s. Devuelve las muestras y los fotogramas para las hojas de contactos."""
    muestras, hojas = [], []
    n = int(m.dur / PASO)
    with _Grabadora() as gr:
        for k in range(n + 1):
            t = min(m.dur - 0.02, k * PASO + 0.01)
            gr.items = []
            img = m.fotograma(t)
            i = m.indice(t)
            en_transicion = any(abs(t - m.lineas[j].t0) < M.TRANS / 2 + 0.02 for j in range(1, len(m.lineas)))
            muestras.append({"t": round(t, 2), "i": i, "trans": en_transicion, "items": list(gr.items),
                             "subs": _caja_subtitulos(m, t), "rotulo": _caja_rotulo(m, i, t)})
            if abs((t / guardar_cada) - round(t / guardar_cada)) < 0.09:
                hojas.append((t, img.resize((270, 480), Image.BILINEAR)))
    return muestras, hojas


def _defectos(m, muestras):
    eventos = []   # (tipo, clave, t, gravedad 0-1, detalle, idx_muestra)
    for idx, mu in enumerate(muestras):
        if mu["trans"]:
            continue
        t, i = mu["t"], mu["i"]
        l = m.lineas[i]
        items = [it for it in mu["items"] if it["el"].tipo not in DECORATIVOS and it["alfa"] > 0.6 and it["el"] in m.elems[i]]
        for it in items:
            el, c = it["el"], it["caja"]
            a = max(1.0, _area(c))
            nom = _nombre(el)
            entrando = t - el.t_in < 0.55
            saliendo = el.t_out is not None and t > el.t_out
            if mu["subs"] and el.tipo not in SUPERPUESTOS:
                x = _inter(c, mu["subs"])
                if x > max(0.03 * a, 1500):
                    eventos.append(("solape_subtitulos", nom, t, min(1, x / a * 3), "%d %% del objeto bajo los subtítulos" % round(100 * x / a), idx))
                elif x > 0 or (c[3] > mu["subs"][1] - 12 and c[1] < mu["subs"][3] and c[2] > mu["subs"][0] and c[0] < mu["subs"][2]):
                    eventos.append(("roza_subtitulos", nom, t, 0.3, "a menos de 12 px de los subtítulos", idx))
            if mu["rotulo"] and el.tipo not in SUPERPUESTOS:
                x = _inter(c, mu["rotulo"])
                if x > 0.06 * a:
                    eventos.append(("tapado_por_rotulo", nom, t, min(1, x / a * 2), "%d %% del objeto bajo el rótulo" % round(100 * x / a), idx))
            x = _inter(c, CABECERA)
            if x > 0.08 * a:
                eventos.append(("invade_cabecera", nom, t, min(1, x / a * 2), "%d %% sobre la cabecera" % round(100 * x / a), idx))
            if not entrando and not saliendo and el.tipo != "flecha":
                dentro = _inter(c, (0, 0, M.W, M.H)) / a
                if dentro < 0.97:
                    eventos.append(("cortado", nom, t, min(1, (1 - dentro) * 4), "%d %% fuera del encuadre" % round(100 * (1 - dentro)), idx))
        # pares
        for p in range(len(items)):
            for q in range(p + 1, len(items)):
                A, B = items[p], items[q]
                ta, tb = A["el"].tipo, B["el"].tipo
                if "flecha" in (ta, tb):
                    txt = B if ta == "flecha" else A
                    if txt["el"].tipo == "texto":
                        x = _inter(A["caja"], B["caja"])
                        if x > 0.15 * _area(txt["caja"]):
                            eventos.append(("flecha_sobre_texto", _nombre(txt["el"]), t, min(1, x / max(1, _area(txt["caja"]))),
                                            "la flecha cruza el texto", idx))
                    continue
                if ta in SUPERPUESTOS or tb in SUPERPUESTOS:
                    continue
                x = _inter(A["caja"], B["caja"])
                peq = max(1.0, min(_area(A["caja"]), _area(B["caja"])))
                gra = max(1.0, _area(A["caja"]), _area(B["caja"]))
                detalle_dentro = x >= 0.9 * peq and peq < 0.25 * gra
                if x > 0.30 * peq and not detalle_dentro and t - max(A["el"].t_in, B["el"].t_in) > 0.5:
                    eventos.append(("solape_elementos", "%s + %s" % (_nombre(A["el"]), _nombre(B["el"])), t, min(1, x / peq),
                                    "se tapan un %d %%" % round(100 * x / peq), idx))
        # vacíos (tras el primer medio segundo de la escena)
        if t - l.t0 > 0.5:
            izq = der = False
            for it in mu["items"]:
                if it["el"].tipo in DECORATIVOS or it["el"] not in m.elems[i]:
                    continue
                c = it["caja"]
                izq |= _inter(c, (0, ZONA_Y[0], M.W / 2, ZONA_Y[1])) >= 5000
                der |= _inter(c, (M.W / 2, ZONA_Y[0], M.W, ZONA_Y[1])) >= 5000
            if not izq and not der:
                eventos.append(("escena_vacia", "escena %d" % (i + 1), t, 1.0, "sin objetos en la zona central", idx))
            elif not izq or not der:
                eventos.append(("mitad_vacia", "escena %d %s" % (i + 1, "izquierda" if not izq else "derecha"), t, 0.6,
                                "mitad %s sin objetos" % ("izquierda" if not izq else "derecha"), idx))
    # agrupar en tramos continuos
    grupos = {}
    for tipo, clave, t, grav, det, idx in eventos:
        g = grupos.get((tipo, clave))
        if g and t - g["t1"] <= PASO * 1.5:
            g["t1"] = t
            g["n"] += 1
            if grav > g["grav"]:
                g.update(grav=grav, detalle=det, idx=idx, t_peor=t)
        else:
            if g:
                grupos.setdefault("_cerrados", []).append(g)
            grupos[(tipo, clave)] = {"tipo": tipo, "que": clave, "t0": t, "t1": t, "n": 1, "grav": grav, "detalle": det, "idx": idx, "t_peor": t}
    lista = grupos.pop("_cerrados", []) + list(grupos.values())
    salida = []
    for g in lista:
        dur = g["t1"] - g["t0"] + PASO
        if g["tipo"] == "mitad_vacia" and dur < 2.0:
            continue
        if g["tipo"] == "escena_vacia" and dur < 1.0:
            continue
        if g["tipo"] in ("solape_elementos", "invade_cabecera", "roza_subtitulos") and dur < 0.5:
            continue
        g["dur"] = round(dur, 2)
        g["nivel"] = "grave" if g["tipo"] in GRAVES else "aviso"
        salida.append(g)
    salida.sort(key=lambda g: (g["nivel"] != "grave", -g["grav"] * g["dur"]))
    return salida


def _hojas(hojas, carpeta, por_hoja=12):
    rutas = []
    for h in range(0, len(hojas), por_hoja):
        lote = hojas[h:h + por_hoja]
        lienzo = Image.new("RGB", (4 * 270 + 5 * 6, 3 * 480 + 4 * 6), (20, 20, 20))
        d = ImageDraw.Draw(lienzo)
        f = texto.fuente("Inter.ttf", 30, 800)
        for k, (t, im) in enumerate(lote):
            x, y = 6 + (k % 4) * 276, 6 + (k // 4) * 486
            lienzo.paste(im, (x, y))
            d.rectangle([x, y, x + 92, y + 40], fill=(0, 0, 0))
            d.text((x + 6, y + 4), "%.1f s" % t, font=f, fill=(255, 255, 0))
        ruta = os.path.join(carpeta, "zz_hoja_%d.jpg" % (h // por_hoja + 1))
        lienzo.save(ruta, quality=82)
        rutas.append(os.path.basename(ruta))
    return rutas


def analizar(m, out, guardar=True):
    """m: Motor ya preparado (preparar_audio + preparar_escenas, o tras render). Escribe <id>_sonda.json en out."""
    muestras, hojas = _muestrear(m)
    defectos = _defectos(m, muestras)
    carpeta = os.path.join(out, "stills")
    os.makedirs(carpeta, exist_ok=True)
    sospechosos = []
    if guardar:
        usados = set()
        for g in defectos[:MAX_SOSPECHOSOS]:
            if g["idx"] in usados:
                g["fotograma"] = next(s for s in sospechosos if s.startswith("zz_s%03d" % g["idx"]))
                continue
            nombre = "zz_s%03d_%s_%.2fs.jpg" % (g["idx"], g["tipo"], g["t_peor"])
            with _Grabadora() as gr:          # el fotograma es función del tiempo: se vuelve a pintar (no se guardan 150 imágenes)
                img = m.fotograma(muestras[g["idx"]]["t"])
                items = list(gr.items)
            d = ImageDraw.Draw(img)
            for it in items:
                if _nombre(it["el"]) in g["que"]:
                    d.rectangle(it["caja"], outline=(255, 0, 255), width=6)
            img.save(os.path.join(carpeta, nombre), quality=86)
            g["fotograma"] = nombre
            usados.add(g["idx"])
            sospechosos.append(nombre)
        rutas_hojas = _hojas(hojas, carpeta)
    else:
        rutas_hojas = []
    representativos = sorted(f for f in os.listdir(carpeta) if f.endswith(".jpg") and not f.startswith("zz_"))
    graves = [g for g in defectos if g["nivel"] == "grave"]
    res = {"version": 1, "paso_s": PASO, "muestras": len(muestras), "defectos": [
        {k: (round(v, 2) if isinstance(v, float) else v) for k, v in g.items() if k not in ("idx",)} for g in defectos],
        "graves": len(graves), "avisos": len(defectos) - len(graves),
        "revisar": representativos + rutas_hojas + sospechosos, "hojas": rutas_hojas, "sospechosos": sospechosos,
        "resumen": ["%s · %s · %.1f–%.1f s · %s" % (g["tipo"], g["que"], g["t0"], g["t1"] + PASO, g["detalle"]) for g in defectos[:12]]}
    gid = m.g.get("id", "SH")
    json.dump(res, open(os.path.join(out, gid + "_sonda.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return res


def compacto(res):
    """Resumen para imprimir en la tarea (pocas líneas, sin listas largas)."""
    return {"graves": res["graves"], "avisos": res["avisos"], "defectos": res["resumen"][:8], "revisar": len(res["revisar"]),
            "hojas": res["hojas"], "sospechosos": res["sospechosos"]}


def main():
    ap = argparse.ArgumentParser(description="QC fase 1: sonda geométrica (sin montar el vídeo)")
    ap.add_argument("guion")
    ap.add_argument("--out", required=True)
    ap.add_argument("--sin-imagenes", action="store_true", help="solo el informe, sin guardar fotogramas")
    a = ap.parse_args()
    from . import activos, guion as guion_mod
    g = json.load(open(a.guion, encoding="utf-8"))
    val = guion_mod.validar(g, [])
    if not val["ok"]:
        print(json.dumps({"ok": False, "motivo": "guion", "errores": val["errores"][:8]}, ensure_ascii=False))
        sys.exit(2)
    activos.preparar_fluent()
    m = M.Motor(g, a.out)
    m.preparar_audio(1.0)
    m.preparar_escenas()
    res = analizar(m, a.out, guardar=not a.sin_imagenes)
    print(json.dumps(compacto(res), ensure_ascii=False, indent=1))
    sys.exit(0 if res["graves"] == 0 else 1)


if __name__ == "__main__":
    main()
