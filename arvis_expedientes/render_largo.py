"""Parche v4.2 · vídeo largo 16:9 (8–12 min) con el motor v4.

Reutiliza del motor: voz Piper (voice), música y efectos (audio), cámara 2.5D con profundidad, niebla, partículas,
luz, gradación, grano y transiciones (comp + render.Scene/_final), rótulos y subtítulos dinámicos (gfx),
sonoridad −14 LUFS (render._loudnorm), storyboard y SRT. Añade: formato 16:9, capítulos, miniatura,
memoria acotada (solo 2–3 escenas cargadas a la vez) y codificación de calidad (sin el límite de 4,7 MB de Make).

python3 -m arvis_expedientes.render_largo guion_motor.json --out out/ --plates plates/ [--stills auto] [--fast]
Tipos de visual admitidos en 16:9: plate (imágenes de ComfyUI o escenarios Blender), document, slate, board.
Escena con "capitulo": "Título" → empieza capítulo (rótulo en pantalla y marca de tiempo en la descripción).
"""
import argparse
import json
import os
import subprocess
import time

import cv2
import numpy as np
from PIL import Image

from . import audio as A
from . import comp as C
from . import formato
from . import gfx as G
from . import miniatura, qc_largo
from . import render as R
from . import voice

PERMITIDOS = {"plate", "document", "slate", "board"}
TAM_TARJETA = {"document": (900, 1180), "slate": (900, 640), "board": (1080, 1500)}
PAUSA_CAPITULO = 0.6


def log(*a):
    print("[largo]", *a, flush=True)


def normalizar(S):
    errores = []
    for k, sc in enumerate(S["scenes"]):
        v = sc.setdefault("visual", {})
        t = v.get("type", "plate")
        if t not in PERMITIDOS:
            errores.append("escena %d: el tipo «%s» aún no está disponible en 16:9" % (k + 1, t))
        if any(o.get("type") == "pin" for o in sc.get("overlays", [])):
            errores.append("escena %d: el rótulo «pin» es solo de mapas (9:16)" % (k + 1))
        if t in TAM_TARJETA and "scale" not in v:
            w, h = TAM_TARJETA[t]
            v["scale"] = round(min(0.9, 0.86 * C.WH * w / h / C.WW), 3)
        if sc.get("capitulo"):
            sc.setdefault("overlays", []).append({"type": "lower_third", "l1": sc["capitulo"].upper(), "l2": "CAPÍTULO %d" % (sum(
                1 for x in S["scenes"][:k + 1] if x.get("capitulo"))), "at": 0.35, "until": 4.2, "y": 60})
    for p in S.get("plates", []):
        p.setdefault("res", [1472, 828])
    if errores:
        raise ValueError("; ".join(errores))
    return S


def centrar(items):
    """Los rótulos del motor están pensados para 1080 de ancho: en 16:9 se centran."""
    out = []
    for (im, x, y, a) in items:
        if x == 0 and im.width == G.W:
            x = (R.OUT_W - im.width) // 2
        out.append((im, x, y, a))
    return out


def tiempo(s):
    s = int(round(s))
    return "%d:%02d:%02d" % (s // 3600, s % 3600 // 60, s % 60) if s >= 3600 else "%d:%02d" % (s // 60, s % 60)


def descripcion(S, capitulos):
    lines = [S.get("description", "").strip(), ""]
    if capitulos:
        lines.append("Capítulos:")
        lines += ["%s %s" % (tiempo(t), n) for t, n in capitulos]
        lines.append("")
    if S.get("sources"):
        lines.append("Fuentes:")
        lines += ["• " + u for u in S["sources"]]
        lines.append("")
    lines.append("Imágenes generadas por ordenador con IA (no son fotografías reales) salvo que se indique. Narración con voz sintética.")
    if S.get("hashtags"):
        lines += ["", " ".join(S["hashtags"][:3])]
    return "\n".join(lines).strip()[:4900]


def build(script_path, outdir, plates_dir, stills="auto", fast=False):
    t_start = time.time()
    S = json.load(open(script_path, encoding="utf-8"))
    lay = formato.aplicar("16:9")
    S = normalizar(S)
    sid = S["id"]
    os.makedirs(outdir, exist_ok=True)
    preset = S.get("voice", "davefx_doc")
    preset = "davefx_doc" if preset == "davefx" else preset
    # 1) voz por escena
    scenes, all_words, vbus_parts, t = [], [], [], 0.15
    for i, sc in enumerate(S["scenes"]):
        if i > 0 and sc.get("capitulo"):
            t += PAUSA_CAPITULO
        au, words = voice.synth(sc["say"], preset)
        d = len(au) / voice.SR
        for w in words:
            w["t0"] += t
            w["t1"] += t
            w["scene"] = i
        all_words += words
        vbus_parts.append((t, au))
        end = t + d + (R.GAP if i < len(S["scenes"]) - 1 else R.TAIL)
        scenes.append({"i": i, "a0": t, "a1": t + d, "end": end})
        t = end
    total = t
    log("voz: %.1f s (%.1f min), %d palabras, %d escenas" % (total, total / 60, len(all_words), len(scenes)))
    for k, s in enumerate(scenes):
        s["v0"] = 0.0 if k == 0 else s["a0"] - R.LEAD
        s["v1"] = scenes[k + 1]["a0"] - R.LEAD + R.TRANS if k + 1 < len(scenes) else total
    capitulos = [(round(scenes[k]["v0"]), sc["capitulo"]) for k, sc in enumerate(S["scenes"]) if sc.get("capitulo")]
    if capitulos and capitulos[0][0] != 0:
        capitulos.insert(0, (0, S.get("capitulo_inicial", "Introducción")))
    elif capitulos:
        capitulos[0] = (0, capitulos[0][1])
    # 2) audio (misma mezcla que el motor v4)
    n = int(total * A.SR) + A.SR
    vbus = np.zeros((n, 2))
    for st, au in vbus_parts:
        i0 = int(st * A.SR)
        vbus[i0:i0 + len(au)] += np.stack([au, au], 1)
    vbus = A.reverb(vbus, wet=0.07, dur=0.9, seed=2)
    sfx = np.zeros((n, 2))
    beats = {"hits": []}
    for k, sc in enumerate(S["scenes"]):
        s = scenes[k]
        dur = s["v1"] - s["v0"]
        if sc.get("beat") == "giro" and "giro" not in beats:
            beats["giro"] = s["a0"] - 0.05
        if sc.get("beat") in ("investigacion", "investigación") and "tension" not in beats:
            beats["tension"] = s["a0"]
        for ev in sc.get("sfx", []):
            ev = {"k": ev} if isinstance(ev, str) else ev
            at = s["v0"] + ev.get("at", 0.0)
            d = ev.get("dur", dur + 0.6 if ev["k"] in ("wind", "rain", "sea", "storm_sea", "room", "fire", "radio", "clock", "creak", "chalk",
                                                      "typewriter", "footsteps_snow", "paper") else 3.0)
            if ev["k"] == "impact":
                beats["hits"].append(at)
                continue
            x = A.sfx(ev["k"], d, seed=k * 13 + len(ev["k"]))
            A.place(sfx, x, at, A.SFX_LEVEL.get(ev["k"], 0.25) * ev.get("gain", 1.0), ev.get("pan", 0.0), fade=0.25 if d > 1 else 0.01)
    mus = A.music(total + 1, beats, seed=S.get("music_seed", 4))
    mus = mus[:n] if len(mus) >= n else np.pad(mus, ((0, n - len(mus)), (0, 0)))
    mus = A.duck(mus, vbus, -8.5)
    mix = (vbus + mus * S.get("music_gain", 0.5) + sfx * 0.9)[: int(total * A.SR)]
    mix = mix / (np.max(np.abs(mix)) or 1) * 0.9
    wav = os.path.join(outdir, sid + "_mix.wav")
    R._write_wav(wav, mix)
    wav_n = os.path.join(outdir, sid + "_mix_norm.wav")
    loud = R._loudnorm(wav, wav_n)
    log("audio listo (%.1f → %.1f LUFS)" % (loud["input_i"], loud["output_i"]))
    # 3) vídeo
    R.render_plates(S, plates_dir)
    objs = [R.Scene(sc, k, plates_dir, S) for k, sc in enumerate(S["scenes"])]
    listos = set()

    def asegurar(k):
        if k not in listos:
            objs[k].prepare()
            listos.add(k)
        for j in [j for j in listos if j < k - 1]:          # memoria acotada: libera escenas ya pasadas
            objs[j] = R.Scene(S["scenes"][j], j, plates_dir, S)
            listos.discard(j)

    grain = C.Grain()
    groups = G.caption_groups(all_words)
    kw = tuple(S.get("keywords", []))
    nframes = int(total * R.FPS)
    if stills == "auto":
        paso = max(1, len(scenes) // 60)
        stills_t = [round((s["v0"] + s["v1"]) / 2, 2) for s in scenes[::paso]]
    else:
        stills_t = [float(x) for x in str(stills or "").split(",") if x.strip()]
    still_frames = {int(x * R.FPS): x for x in stills_t}
    tmp_video = os.path.join(outdir, sid + "_video.mkv")
    if os.environ.get("ARVIS_ENCODER") == "videotoolbox":
        venc = ["-c:v", "h264_videotoolbox", "-b:v", "14M", "-allow_sw", "1"]
    else:
        venc = ["-c:v", "libx264", "-preset", "veryfast" if fast else "medium", "-crf", "18"]
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (R.OUT_W, R.OUT_H),
                           "-r", str(R.FPS), "-i", "-"] + venc + ["-pix_fmt", "yuv420p", tmp_video], stdin=subprocess.PIPE)
    keyframes = {}
    t_vid = time.time()
    cap_y = lay["subtitulos_y"]
    try:
        for f in range(nframes):
            tt = f / R.FPS
            cur = max(k for k, s in enumerate(scenes) if s["v0"] <= tt + 1e-6)
            s = scenes[cur]
            asegurar(cur)
            if cur > 0:
                asegurar(cur - 1)
            img = R._final(objs, scenes, S, cur, tt, grain, f, total)
            out = cv2.resize(img, (R.OUT_W, R.OUT_H), interpolation=cv2.INTER_CUBIC)
            out = np.clip(out * 255 + np.random.RandomState(f).rand(R.OUT_H, R.OUT_W, 1).astype(np.float32) * 1.2 - 0.6, 0, 255).astype(np.uint8)
            lt = tt - s["v0"]
            if cur > 0 and lt < R.TRANS:
                p_ = scenes[cur - 1]
                fade_prev = 1.0 - C.ease_io(lt / R.TRANS)
                for (im, x, y, a) in centrar(R.scene_overlays(objs[cur - 1], tt - p_["v0"], p_["v1"] - p_["v0"])):
                    R.composite(out, im, x, y, a * fade_prev)
            for (im, x, y, a) in centrar(R.scene_overlays(objs[cur], lt, s["v1"] - s["v0"])):
                R.composite(out, im, x, y, a * (C.ease_io(lt / R.TRANS) if cur > 0 and lt < R.TRANS else 1.0))
            for g in groups:
                w0 = all_words[g[0]]["t0"] - 0.06
                w1 = all_words[g[-1]]["t1"] + 0.12
                if w0 <= tt <= w1:
                    hi = 0
                    for j, wi in enumerate(g):
                        if all_words[wi]["t0"] - 0.03 <= tt:
                            hi = j
                    cap = G.caption_img(tuple(all_words[wi]["w"] for wi in g), hi, kw)
                    pop = 1.0 + 0.06 * max(0.0, 1 - (tt - w0) / 0.12)
                    if pop != 1.0:
                        cap = cap.resize((int(cap.width * pop), int(cap.height * pop)), Image.BILINEAR)
                    R.composite(out, cap, int(R.OUT_W / 2 - 40 - cap.width / 2), int(cap_y - cap.height / 2), 1.0)
                    break
            ff.stdin.write(out.tobytes())
            mid = int((s["v0"] + (s["v1"] - s["v0"]) * 0.55) * R.FPS)
            if f == mid or f == int((s["v0"] + 0.1) * R.FPS) + int(R.TRANS * R.FPS) + 1 or f == int(s["v1"] * R.FPS) - 2:
                keyframes.setdefault(cur, []).append(cv2.resize(out, lay["miniatura_kf"], interpolation=cv2.INTER_AREA))
            if f in still_frames:
                Image.fromarray(out).save(os.path.join(outdir, "%s_still_%06.1f.png" % (sid, still_frames[f])))
            if f % 480 == 0:
                el = time.time() - t_vid
                log("fotograma %d/%d (%.0f s, %.3f s/f, quedan ~%.0f min)" % (f, nframes, el, el / max(1, f), el / max(1, f) * (nframes - f) / 60))
    finally:
        ff.stdin.close()
        ff.wait()
    log("vídeo montado en %.1f min" % ((time.time() - t_vid) / 60))
    final = os.path.join(outdir, sid + ".mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp_video, "-i", wav_n, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", "-shortest", final], check=True)
    R._write_srt(os.path.join(outdir, sid + ".srt"), all_words, groups)
    mini = miniatura.crear(S, plates_dir, os.path.join(outdir, sid + "_miniatura.jpg"))
    sb = R.storyboard(S, scenes, all_words)
    json.dump(sb, open(os.path.join(outdir, sid + "_storyboard.json"), "w"), ensure_ascii=False, indent=1)
    open(os.path.join(outdir, sid + "_storyboard.md"), "w").write(R.storyboard_md(S, sb))
    rep = qc_largo.run(S, final, wav_n, all_words, groups, scenes, keyframes, sb, loud, capitulos, mini)
    rep.update({"id": sid, "formato": "16:9", "title": S["title"], "description": descripcion(S, capitulos), "tags": S.get("tags", []),
                "duration_s": round(total, 2), "words": len(all_words), "render_s": round(time.time() - t_start, 1), "mp4": final, "mp4_hq": final,
                "thumbnail": mini, "chapters": capitulos, "containsSyntheticMedia": bool(S.get("containsSyntheticMedia")),
                "sha256": R._sha(final), "size_mb": round(os.path.getsize(final) / 1e6, 1)})
    json.dump(rep, open(os.path.join(outdir, sid + ".json"), "w"), ensure_ascii=False, indent=1)
    for p in (tmp_video, wav):
        try:
            os.remove(p)
        except OSError:
            pass
    log("QC %s · %d/%d · %.1f min · %.1f MB" % ("OK" if rep["ok"] else "FALLA", rep["passed"], rep["total"], total / 60, rep["size_mb"]))
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--out", default="out")
    ap.add_argument("--plates", default=None)
    ap.add_argument("--stills", default="auto")
    ap.add_argument("--fast", action="store_true")
    a = ap.parse_args()
    rep = build(a.script, a.out, a.plates or os.path.join(a.out, "plates"), a.stills, a.fast)
    print(json.dumps({k: rep[k] for k in ("ok", "passed", "total", "duration_s", "size_mb", "failed")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
