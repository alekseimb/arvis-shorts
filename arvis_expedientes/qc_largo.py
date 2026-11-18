"""Parche v4.2 · control de calidad automático del vídeo largo (16:9). Misma forma que qc.run del motor v4."""
import os
import re
import subprocess

import numpy as np

from .qc import _probe


def run(S, final, wav, words, groups, scenes, keyframes, sb, loud, capitulos, miniatura, dur_min=480, dur_max=720):
    checks = []

    def add(name, ok, value):
        checks.append({"check": name, "ok": bool(ok), "valor": value})

    pr = _probe(final)
    v = [s for s in pr["streams"] if s["codec_type"] == "video"][0]
    a = [s for s in pr["streams"] if s["codec_type"] == "audio"]
    fps = eval(v.get("r_frame_rate", "0/1"))
    add("Formato 1920×1080 H.264 + AAC, 24 fps", v["width"] == 1920 and v["height"] == 1080 and v["codec_name"] == "h264" and a
        and a[0]["codec_name"] == "aac" and abs(fps - 24) < 0.01,
        "%sx%s %s %s %.2f fps" % (v["width"], v["height"], v["codec_name"], a[0]["codec_name"] if a else "sin audio", fps))
    dur = float(pr["format"]["duration"])
    add("Duración 8–12 min", dur_min <= dur <= dur_max, "%.1f min" % (dur / 60))
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", final, "-f", "null", "-"], capture_output=True, text=True)
    add("Decodifica sin errores", r.returncode == 0 and not r.stderr.strip(), (r.stderr.strip()[:120] or "sin errores"))
    add("Sonoridad −14 LUFS ±1,5 y pico ≤ −1 dBTP", abs(loud["output_i"] + 14) <= 1.5 and loud["output_tp"] <= -1.0,
        "%.1f LUFS · %.1f dBTP" % (loud["output_i"], loud["output_tp"]))
    vt = sum(s["a1"] - s["a0"] for s in scenes)
    wps = len(words) / max(vt, 0.1)
    add("Ritmo de voz 2,0–3,2 palabras/s", 2.0 <= wps <= 3.2, "%.2f pal/s" % wps)
    first = S["scenes"][0]["say"]
    m = re.match(r"(.+?[.!?…])(\s|$)", first)
    fs = (m.group(1) if m else first).split()
    t_end = words[len(fs) - 1]["t1"] if len(words) >= len(fs) else 99
    add("Gancho: primera frase ≤ 15 palabras y antes de 5 s", t_end <= 5.0 and len(fs) <= 15, "%d palabras, termina a %.1f s" % (len(fs), t_end))
    ok_cap = len(capitulos) >= 3 and capitulos[0][0] == 0 and all(b[0] - a_[0] >= 10 for a_, b in zip(capitulos, capitulos[1:]))
    add("Capítulos: ≥ 3, el primero en 0:00 y ≥ 10 s entre ellos", ok_cap, "%d capítulos" % len(capitulos))
    durs = [s["v1"] - s["v0"] for s in scenes]
    add("Escenas: 2–14 s y plano medio ≤ 8 s", min(durs) >= 2.0 and max(durs) <= 14.0 and np.mean(durs) <= 8.0,
        "%d escenas · %.1f–%.1f s · media %.1f s" % (len(durs), min(durs), max(durs), np.mean(durs)))
    mids = [np.asarray(keyframes[k][1 if len(keyframes[k]) > 1 else 0], np.float32) / 255 for k in sorted(keyframes)]
    mind, pair = 9.0, None
    for i in range(len(mids)):
        for j in range(i + 1, min(len(mids), i + 12)):        # compara con las 11 escenas siguientes
            d = float(np.mean(np.abs(mids[i] - mids[j])))
            if d < mind:
                mind, pair = d, (i + 1, j + 1)
    usos = {}
    for sc in S["scenes"]:
        p = sc.get("visual", {}).get("plate")
        if p:
            usos[p] = usos.get(p, 0) + 1
    rep = [p for p, n in usos.items() if n > 2]
    add("Sin imágenes repetidas (diferencia ≥ 0,035; cada imagen ≤ 2 veces)", mind >= 0.035 and not rep,
        "mínima %.3f entre escenas %s%s" % (mind, pair, " · repetidas: %s" % rep if rep else ""))
    statics = [k + 1 for k in sorted(keyframes) if len(keyframes[k]) >= 2 and
               float(np.mean(np.abs(np.asarray(keyframes[k][0], np.float32) - np.asarray(keyframes[k][-1], np.float32)))) / 255 < 0.006]
    add("Todas las escenas con movimiento", not statics, "estáticas: %s" % (statics or "ninguna"))
    tipos = set(sc.get("visual", {}).get("type") for sc in S["scenes"])
    movs = set(sc.get("visual", {}).get("move", "push_in") for sc in S["scenes"])
    add("Variedad visual (≥ 2 tipos, ≥ 5 movimientos, imágenes distintas ≥ 60 % de escenas)",
        len(tipos) >= 2 and len(movs) >= 5 and len(usos) >= 0.6 * len(S["scenes"]),
        "%d tipos · %d movimientos · %d imágenes / %d escenas" % (len(tipos), len(movs), len(usos), len(S["scenes"])))
    covered = sum(len(g) for g in groups)
    longest = max(len(g) for g in groups) if groups else 0
    add("Subtítulos: todas las palabras, ≤ 3 por bloque", covered == len(words) and longest <= 3, "%d/%d · hasta %d" % (covered, len(words), longest))
    gaps = [words[i + 1]["t0"] - words[i]["t1"] for i in range(len(words) - 1)]
    add("Sin silencios largos (≤ 1,6 s entre palabras)", (max(gaps) if gaps else 0) <= 1.6, "máximo %.2f s" % (max(gaps) if gaps else 0))
    dark = [k + 1 for k in sorted(keyframes) if np.mean(keyframes[k][1 if len(keyframes[k]) > 1 else 0]) / 255 < 0.03]
    add("Sin fotogramas negros a mitad de escena", not dark, "negras: %s" % (dark or "ninguna"))
    src = S.get("sources", [])
    facts = S.get("facts", [])
    bad_f = [f for f in facts if not isinstance(f.get("source"), list) or not f["source"] or any(i >= len(src) for i in f["source"])]
    tipos_ok = all(f.get("tipo") in ("hecho", "opinion", "opinión", "hipotesis", "hipótesis") for f in facts)
    add("Fuentes: ≥ 3 https, cada hecho con fuente y tipo (hecho/opinión/hipótesis)",
        len(src) >= 3 and all(u.startswith("https://") for u in src) and facts and not bad_f and tipos_ok,
        "%d fuentes · %d hechos · %d sin fuente%s" % (len(src), len(facts), len(bad_f), "" if tipos_ok else " · falta tipo"))
    digits = [i + 1 for i, sc in enumerate(S["scenes"]) if re.search(r"\d", sc["say"])]
    add("Narración sin cifras escritas (se leen en palabras)", not digits, "escenas con cifras: %s" % (digits or "ninguna"))
    t = S["title"]
    add("Título ≤ 100 caracteres, sin < >", len(t) <= 100 and "<" not in t and ">" not in t, "%d caracteres" % len(t))
    need = ("plano", "camara", "iluminacion", "ambiente", "relacion")
    incomplete = [r_["escena"] for r_ in sb if any(not r_.get(k) for k in need)]
    add("Storyboard completo (plano, cámara, luz, ambiente y relación)", not incomplete, "incompletas: %s" % (incomplete or "ninguna"))
    unlabeled = [i + 1 for i, sc in enumerate(S["scenes"]) if sc.get("visual", {}).get("type") == "plate"
                 and not any(o["type"] == "label" for o in sc.get("overlays", []))]
    add("Imágenes sintéticas etiquetadas en pantalla", not unlabeled, "sin etiqueta: %s" % (unlabeled or "ninguna"))
    ok_m = bool(miniatura) and os.path.exists(miniatura) and os.path.getsize(miniatura) <= 2_000_000
    add("Miniatura 1280×720 ≤ 2 MB", ok_m, "%s" % (round(os.path.getsize(miniatura) / 1e6, 2) if ok_m else "falta"))
    passed = sum(c["ok"] for c in checks)
    return {"ok": passed == len(checks), "passed": passed, "total": len(checks), "checks": checks,
            "failed": [c["check"] + " (" + str(c["valor"]) + ")" for c in checks if not c["ok"]]}
