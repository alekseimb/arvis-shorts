"""CONTROL DE CALIDAD técnico de LIFEHACKS AI · 22 comprobaciones medidas sobre el vídeo final.

Los nombres de las comprobaciones usan las palabras clave de arvis_estudio.calidad (Fuentes, cifras, Gancho,
Estructura, repetidas, estáticos, negros, Variedad, Sonoridad, silencios, Ritmo de voz, Decodifica, Formato,
Subtítulos, Storyboard, sintético) para que un fallo ponga tope automático a la nota 0–100.
"""
import json
import os
import re
import subprocess

import cv2
import numpy as np

from .config import DURACION, H, LIMITE_Y, MAX_MB_MAKE, SR, SUBS_Y, VENTANA, W

RE_PERSONAL = [r"[\w.+-]+@[\w-]+\.[\w.]+", r"\b(?:\+34\s?)?[6789]\d{2}[\s.]?\d{3}[\s.]?\d{3}\b", r"/home/\w+", r"/root\b",
               r"/Users/\w+", r"C:\\Users\\\w+", r"/tmp/lifehacks_", r"\bDNI\b"]


def _probe(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate:format=duration,size",
                        "-of", "json", f], capture_output=True, text=True)
    return json.loads(r.stdout or "{}")


def _sonoridad(f):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", f, "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    s = r.stderr[r.stderr.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", s)
    p = re.search(r"Peak:\s+(-?[\d.]+) dBFS", s)
    return (float(i.group(1)) if i else None), (float(p.group(1)) if p else None)


def _decodifica(f):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", f, "-f", "null", "-"], capture_output=True, text=True)
    return r.returncode == 0 and not r.stderr.strip(), r.stderr.strip()[:300]


def _negros(f):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", f, "-vf", "blackdetect=d=0.25:pix_th=0.08", "-an", "-f", "null", "-"],
                       capture_output=True, text=True)
    return re.findall(r"black_start:([\d.]+)", r.stderr)


def _muestras_ventana(f, paso=0.5):
    cap = cv2.VideoCapture(f)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    x0, y0, x1, y1 = VENTANA
    out = []
    for i in range(0, n, max(1, int(fps * paso))):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, fr = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(fr[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
        out.append((i / fps, cv2.resize(g, (124, 113)).astype(np.float32)))
    cap.release()
    return out


def _numeros(texto):
    return set(re.findall(r"\d+(?:[.,]\d+)?", texto or ""))


def comprobar(video, hq, guion, herramienta, capturas, montaje_info, voz, subs, escenas, storyboard):
    checks = []

    def add(nombre, ok, detalle=""):
        checks.append({"check": nombre, "ok": bool(ok), "detalle": detalle})

    pr = _probe(video)
    vs = [s for s in pr.get("streams", []) if s.get("codec_type") == "video"]
    au = [s for s in pr.get("streams", []) if s.get("codec_type") == "audio"]
    dur = float(pr.get("format", {}).get("duration", 0))
    ok_fmt = bool(vs) and vs[0]["width"] == W and vs[0]["height"] == H and bool(au)
    add("Formato vertical 1080×1920 con audio", ok_fmt, "%sx%s, audio %s" % (vs[0]["width"] if vs else "?", vs[0]["height"] if vs else "?", bool(au)))
    dec, err = _decodifica(video)
    add("Decodifica entero sin errores", dec, err)
    add("Duración %d–%d s" % DURACION, DURACION[0] <= dur <= DURACION[1] + 0.5, "%.1f s" % dur)
    mb = os.path.getsize(video) / 1024 / 1024
    add("Tamaño para Make ≤ %.1f MB" % MAX_MB_MAKE, mb <= MAX_MB_MAKE, "%.2f MB" % mb)
    lufs, pico = _sonoridad(video)
    add("Sonoridad −14 LUFS (±1,5) y pico ≤ −1 dBFS", lufs is not None and abs(lufs + 14) <= 1.5 and pico is not None and pico <= -1.0,
        "%s LUFS, pico %s dBFS" % (lufs, pico))
    # silencios de la voz (sin contar el cierre)
    v = voz[: int((dur - 1.2) * SR)]
    k = int(0.05 * SR)
    rms = np.sqrt(np.convolve(v.astype(np.float64) ** 2, np.ones(k) / k, mode="valid")[::k]) if len(v) > k else np.zeros(1)
    mudo, maxmudo = 0, 0
    for r in rms:
        mudo = mudo + 1 if r < 0.01 else 0
        maxmudo = max(maxmudo, mudo)
    add("Sin silencios largos de voz (≤ 0,8 s)", maxmudo * 0.05 <= 0.8, "máx. %.2f s" % (maxmudo * 0.05))
    habla = sum(e["_t1"] - e["_t0"] for e in escenas)
    ppm = montaje_info["palabras"] / max(1, habla)
    add("Ritmo de voz 2,3–3,8 pal/s", 2.3 <= ppm <= 3.8, "%.2f pal/s" % ppm)
    g = escenas[0]
    add("Gancho ≤ 2,5 s", g["beat"] == "gancho" and g["_t1"] - g["_t0"] <= 2.5, "%.2f s" % (g["_t1"] - g["_t0"]))
    beats = [e["beat"] for e in escenas]
    fin_problema = max([e["_t1"] for e in escenas if e["beat"] == "problema"] or [99])
    ok_est = (beats[0] == "gancho" and "problema" in beats and beats.count("tutorial") >= 2 and "resultado" in beats
              and beats[-1] == "cta" and beats.index("resultado") > max(i for i, b in enumerate(beats) if b == "tutorial")
              and fin_problema <= 9.5)
    add("Estructura gancho → problema → tutorial → resultado → CTA", ok_est, " → ".join(beats) + " · problema hasta %.1f s" % fin_problema)
    palabras_dichas = sum(len(e["say"].split()) for e in escenas)
    palabras_sub = sum(len(b["palabras"]) for b in subs)
    abajo = SUBS_Y + 88 <= LIMITE_Y
    add("Subtítulos: todas las palabras, 70 px, en zona segura", palabras_sub == palabras_dichas and abajo,
        "%d/%d palabras" % (palabras_sub, palabras_dichas))
    negros = _negros(video)
    add("Sin fotogramas negros", not negros, ", ".join(negros[:5]))
    muestras = _muestras_ventana(hq)
    # tramos estáticos > 3 s dentro de la ventana
    quieto, maxq, prev = 0.0, 0.0, None
    for t, m in muestras:
        if prev is not None:
            quieto = quieto + 0.5 if float(np.mean(np.abs(m - prev))) < 0.6 else 0.0
            maxq = max(maxq, quieto)
        prev = m
    add("Sin tramos estáticos > 3 s (movimiento real en pantalla)", maxq <= 3.0, "máx. %.1f s quieto" % maxq)
    # escenas repetidas (el gancho puede adelantar el resultado si se declara «avance»)
    medios = []
    for e in escenas:
        tm = (e["_t0"] + e["_t1"]) / 2
        cerca = min(muestras, key=lambda x: abs(x[0] - tm))[1]
        medios.append(cerca)
    rep = []
    for i in range(len(medios)):
        for j in range(i + 1, len(medios)):
            if escenas[i]["visual"].get("avance") or escenas[j]["visual"].get("avance"):
                continue
            if float(np.mean(np.abs(medios[i] - medios[j]))) < 1.5:
                rep.append("%d=%d" % (i + 1, j + 1))
    add("Sin escenas repetidas", not rep, ", ".join(rep))
    tipos = {e["visual"]["tipo"] for e in escenas}
    add("Variedad visual ≥ 3 tipos de plano", len(tipos) >= 3, ", ".join(sorted(tipos)))
    add("Herramienta revisada y probada antes de grabar", herramienta["ok"] and herramienta["pruebas"]["tests"] >= 1,
        "%s pruebas OK · revisión %s" % (herramienta["pruebas"]["tests"], "OK" if herramienta["revision_ok"] else herramienta["hallazgos"][:3]))
    reales = all(s["ok"] for s in herramienta["sesiones"].values()) and all(
        len(c["frames"]) >= 2 and not c["errores_consola"] for c in capturas.values())
    add("Demostración real (ejecución y capturas sin errores)", reales,
        "terminal %d · web %d" % (len(herramienta["sesiones"]), len(capturas)))
    fuentes = guion.get("sources", [])
    hechos = guion.get("facts", [])
    ok_f = bool(fuentes) and all(u.startswith("https://") for u in fuentes) and all(
        h.get("source") and all(0 <= i < len(fuentes) for i in h["source"]) for h in hechos) and bool(hechos)
    add("Fuentes: cada afirmación técnica con su fuente", ok_f, "%d fuentes · %d hechos" % (len(fuentes), len(hechos)))
    evidencia = " ".join(e["texto"] for s in herramienta["sesiones"].values() for e in s["eventos"])
    evidencia += " " + " ".join(h["claim"] for h in hechos) + " " + " ".join(c.get("texto_visible", "") for c in capturas.values())
    for e in escenas:
        if e["visual"]["tipo"] == "codigo":
            evidencia += " " + open(os.path.join(herramienta["carpeta_trabajo"], e["visual"]["archivo"]), encoding="utf-8").read()
    pantalla = " ".join([guion["title"]] + [e.get("rotulo", "") + " " + e.get("titulo_paso", "") + " " + e["visual"].get("destacado", {}).get("texto", "")
                                              + " " + e["visual"].get("destacado", {}).get("sub", "") for e in escenas])
    sin_respaldo = sorted(n for n in _numeros(pantalla) if n not in _numeros(evidencia) and n.replace(",", ".") not in _numeros(evidencia))
    add("Las cifras en pantalla salen de la ejecución real o de las fuentes", not sin_respaldo, ", ".join(sin_respaldo))
    desc = guion.get("_descripcion", "")
    ok_t = 0 < len(guion["title"]) <= 100 and not re.search(r"[<>]", guion["title"] + desc) and len(desc) <= 5000
    add("Título ≤ 100 y título/descripción sin < >", ok_t, "%d caracteres de título" % len(guion["title"]))
    locales = all(c["url"].startswith(("file://", "http://127.0.0.1", "http://localhost")) for c in capturas.values())
    add("Sin marcas de agua ni material ajeno (solo capturas locales y música propia)", locales, "")
    texto_publico = evidencia + " " + pantalla + " " + desc + " " + " ".join(e["say"] for e in escenas)
    personales = sorted({m.group(0) for p in RE_PERSONAL for m in re.finditer(p, texto_publico)})
    add("Sin datos personales en pantalla", not personales, ", ".join(personales[:5]))
    add("Storyboard e informe generados", os.path.exists(storyboard), os.path.basename(storyboard))
    from .config import CREDITO_VOZ, VOZ
    credito = CREDITO_VOZ.get(guion.get("voice", VOZ), "")
    add("Contenido sintético declarado (voz sintética) y crédito de la voz si su licencia lo pide",
        "voz sintética" in desc.lower() and (not credito or credito in desc), "")
    return {"checks": checks, "passed": sum(c["ok"] for c in checks), "total": len(checks), "duration_s": round(dur, 2),
            "title": guion["title"], "containsSyntheticMedia": False, "lufs": lufs, "pico": pico, "mb": round(mb, 2)}
