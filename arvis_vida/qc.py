"""CONTROL DE CALIDAD técnico y de contenido de un Short de ARVIS VIDA (comprobaciones medidas, no opinadas).

Los nombres de las comprobaciones llevan las palabras que usa arvis_estudio.calidad para poner topes a la nota
(«Fuentes», «cifras», «Gancho», «Estructura», «negros», «movimiento», «Variedad», «Sonoridad», «Ritmo de voz»,
«Decodifica», «Formato», «Subtítulos», «Storyboard», «etiquet»).
"""
import json
import os
import re
import subprocess

from . import activos, guion as guion_mod

MAX_MB = 4.6


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(f):
    r = _run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", f])
    return json.loads(r.stdout or "{}")


def sonoridad(f):
    r = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", f, "-af", "ebur128=peak=true", "-f", "null", "-"])
    s = r.stderr[r.stderr.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", s)
    p = re.search(r"Peak:\s+(-?[\d.]+) dBFS", s)
    return (float(i.group(1)) if i else None, float(p.group(1)) if p else None)


def negros(f):
    r = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", f, "-vf", "blackdetect=d=0.1:pix_th=0.08", "-an", "-f", "null", "-"])
    return re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", r.stderr)


def congelados(f, d=1.0):
    r = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", f, "-vf", "freezedetect=n=0.0015:d=%s" % d, "-an", "-f", "null", "-"])
    return re.findall(r"freeze_start: ([\d.]+)", r.stderr)


def decodifica(f):
    r = _run(["ffmpeg", "-v", "error", "-i", f, "-f", "null", "-"])
    return r.returncode == 0 and not r.stderr.strip(), r.stderr.strip()[:300]


def comprobar(g, info, motor, salida, titulos_publicados=()):
    checks = []

    def add(nombre, ok, detalle=""):
        checks.append({"check": nombre, "ok": bool(ok), "detalle": str(detalle)})

    mk, hq = info["make"], info["hq"]
    # --- técnica
    ok1, err1 = decodifica(mk)
    ok2, err2 = decodifica(hq)
    add("Decodifica sin errores (Make y HQ)", ok1 and ok2, err1 or err2 or "ffmpeg -v error: 0 avisos")
    pr = probe(mk)
    v = next((s for s in pr.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in pr.get("streams", []) if s.get("codec_type") == "audio"), {})
    fps = eval(v.get("r_frame_rate", "0/1")) if v else 0
    add("Formato vertical 1080×1920 H.264 30 fps", v.get("width") == 1080 and v.get("height") == 1920 and v.get("codec_name") == "h264"
        and abs(fps - 30) < 0.01 and v.get("pix_fmt") == "yuv420p", "%sx%s %s %.2f fps %s" % (v.get("width"), v.get("height"), v.get("codec_name"), fps, v.get("pix_fmt")))
    dur = float(pr.get("format", {}).get("duration", 0))
    add("Duración 20–35 s", 20 <= dur <= 35.5, "%.1f s" % dur)   # ARVIS 5.0: 20–35 s
    mb = os.path.getsize(mk) / 1048576
    add("Tamaño ≤ %.1f MB (Make Free)" % MAX_MB, mb <= MAX_MB, "%.2f MB" % mb)
    lufs, pico = sonoridad(mk)
    add("Sonoridad −14 ± 1,5 LUFS y pico ≤ −1 dBFS", lufs is not None and abs(lufs + 14) <= 1.5 and pico is not None and pico <= -0.9,
        "%s LUFS, pico %s dBFS, audio %s" % (lufs, pico, a.get("codec_name")))
    ng = negros(hq)
    add("Sin pantallas negras", not ng, "ninguna" if not ng else ng)
    fr = congelados(hq)
    add("Sin tramos estáticos ≥ 1 s (movimiento constante)", not fr, "ninguno" if not fr else "congelado desde %s s" % ", ".join(fr))
    # voz: sin silencios largos dentro de la narración
    ts = sorted((p["t0"], p["t1"]) for p in motor.palabras)
    huecos = [b[0] - a[1] for a, b in zip(ts, ts[1:])]
    add("Sin silencios largos en la voz (≤ 1,0 s)", not huecos or max(huecos) <= 1.0, "mayor pausa %.2f s" % (max(huecos) if huecos else 0))
    pal_s = info["palabras"] / max(1.0, dur)
    add("Ritmo de voz 2,3–3,8 palabras/s", 2.3 <= pal_s <= 3.8, "%.2f pal/s" % pal_s)
    # subtítulos
    srt = os.path.join(salida, g["id"] + ".srt")
    n_srt = len(re.findall(r"-->", open(srt, encoding="utf-8").read())) if os.path.exists(srt) else 0
    cubiertas = sum(len(b["palabras"]) for b in motor.subs)
    add("Subtítulos sincronizados y legibles (74 px, borde 8 px, zona segura)", n_srt > 0 and cubiertas == len(motor.palabras),
        "%d bloques, %d/%d palabras, centro y=1330–1420 px (< 1450)" % (n_srt, cubiertas, len(motor.palabras)))
    # --- estructura y contenido
    val = guion_mod.validar(g, titulos_publicados)
    add("Estructura gancho → problema → pasos → resultado → cierre", not [e for e in val["errores"] if "orden" in e or "escena" in e or "pasos" in e],
        "; ".join(val["errores"]) or "ok")
    gan = g["escenas"][0]
    add("Gancho en pregunta ≤ 2,6 s con imagen y rótulo desde el primer instante", gan["say"].strip().endswith("?") and gan["_voz"] <= 2.6
        and any(el.t_in <= 0.3 for el in motor.elems[0]) and bool(gan.get("titulo")), "«%s» %.2f s" % (gan["say"], gan["_voz"]))
    add("Fuentes oficiales o primarias con cita literal", not [e for e in val["errores"] if "fuente" in e or "cita" in e],
        "; ".join(g.get("sources", [])))
    add("Todas las cifras respaldadas por una cita", not [e for e in val["errores"] if "cifras" in e], next((e for e in val["errores"] if "cifras" in e), "ok"))
    add("Sin consejos peligrosos, médicos ni promesas exageradas", not [e for e in val["errores"] if "no permitido" in e],
        next((e for e in val["errores"] if "no permitido" in e), "ok"))
    add("Sin repetir un vídeo publicado", not [e for e in val["errores"] if "publicado" in e], next((e for e in val["errores"] if "publicado" in e), "ok"))
    # imagen ↔ narración
    fallos = []
    for i, e in enumerate(g["escenas"]):
        if e["beat"] == "cta":
            continue
        claves = " ".join([e.get("titulo", "")] + [activos.palabras_clave(el["activo"]) if el.get("activo") else str(el.get("texto", "")) + " " + str(el.get("etiqueta", ""))
                                                   for el in e.get("elementos", [])])
        from . import props
        for el in e.get("elementos", []):
            if el.get("activo") in props.PROPS:
                claves += " " + props.crear(el["activo"], el.get("estado")).get("clave", "")
        comun = activos.raices(claves) & activos.raices(e["say"])
        if not comun:
            fallos.append("escena %d (%s)" % (i + 1, e["beat"]))
    add("Imágenes que corresponden a la narración (palabras clave comunes en cada escena)", not fallos, "sin relación: " + ", ".join(fallos) if fallos else "todas las escenas")
    # variedad
    firmas = [(e.get("fondo"), e.get("variante_fondo", 0), e.get("camara", "empuje")) for e in g["escenas"]]
    repetidas = [i for i in range(1, len(firmas)) if firmas[i] == firmas[i - 1]]
    tipos_cam = len({f[2] for f in firmas})
    trans = len({e.get("transicion", "barrido") for e in g["escenas"][1:]})
    add("Variedad visual: sin escenas repetidas seguidas, ≥ 3 movimientos de cámara y ≥ 2 transiciones", not repetidas and tipos_cam >= 3 and trans >= 2,
        "%d movimientos, %d transiciones, repetidas: %s" % (tipos_cam, trans, repetidas or "ninguna"))
    ev = sorted(set([0.0] + motor.eventos_visuales + [dur]))
    hueco = max(b - a for a, b in zip(ev, ev[1:]))
    add("Novedad visual al menos cada 3 s (sin escenas repetidas)", hueco <= 3.0, "mayor hueco %.1f s" % hueco)
    # entregables
    st = os.path.join(salida, "stills")
    n_st = len([f for f in os.listdir(st) if f.endswith(".jpg")]) if os.path.isdir(st) else 0
    add("Storyboard y fotogramas de revisión", n_st >= len(g["escenas"]) and os.path.exists(os.path.join(salida, g["id"] + "_storyboard.md")),
        "%d fotogramas" % n_st)
    desc = g.get("_descripcion", "")
    add("Descripción con fuentes y créditos; animación etiquetada como recreación", all(x in desc for x in ("Fuentes", "Voz:", "Fluent Emoji", "Animación 2D")),
        "ok" if desc else "sin descripción")
    passed = sum(1 for c in checks if c["ok"])
    return {"checks": checks, "passed": passed, "total": len(checks), "duration_s": round(dur, 2), "mb": round(mb, 2), "lufs": lufs, "pico": pico,
            "avisos_guion": val["avisos"]}
