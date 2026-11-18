"""Control de calidad técnico previo a publicar (ffprobe/ffmpeg, sin servicios externos)."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

PERFILES = {
    "short": {"w": 1080, "h": 1920, "min_s": 30, "max_s": 60},
    "largo": {"w": 1920, "h": 1080, "min_s": 480, "max_s": 720},
}


def _probe(f: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams",
                          "-show_format", str(f)], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def _detect(f: Path, filtro: str, audio: bool) -> str:
    sel = ["-af", filtro, "-vn"] if audio else ["-vf", filtro, "-an"]
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(f), *sel, "-f", "null", "-"],
                       capture_output=True, text=True)
    return r.stderr


def srt_sincronizado(srt: Path, duracion: float) -> tuple[bool, str]:
    t = re.findall(r"(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)", srt.read_text(encoding="utf-8"))
    if not t:
        return False, "SRT vacío"
    seg = lambda h, m, s, ms: int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    prev = 0.0
    for c in t:
        a, b = seg(*c[:4]), seg(*c[4:])
        if b <= a or a < prev - 0.01:
            return False, f"cue desordenado en {a:.2f}s"
        prev = b
    return (prev <= duracion + 0.5), f"último cue {prev:.2f}s / vídeo {duracion:.2f}s"


def revisar(f: Path, perfil: str = "short", srt: Path | None = None) -> dict:
    p = PERFILES[perfil]
    res: dict[str, tuple[bool, str]] = {}
    res["existe"] = (f.exists() and f.stat().st_size > 0, str(f))
    if not res["existe"][0]:
        return {"ok": False, "checks": res}
    try:
        info = _probe(f)
    except subprocess.CalledProcessError as e:
        res["reproducible"] = (False, e.stderr[:200])
        return {"ok": False, "checks": res}
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    dur = float(info["format"].get("duration", 0))
    res["reproducible"] = (v is not None, v["codec_name"] if v else "sin vídeo")
    res["resolucion"] = (bool(v) and (v["width"], v["height"]) == (p["w"], p["h"]),
                         f"{v and v['width']}x{v and v['height']}")
    res["duracion"] = (p["min_s"] <= dur <= p["max_s"], f"{dur:.1f}s")
    res["audio"] = (a is not None, a["codec_name"] if a else "sin audio")
    if a:
        vol = re.search(r"mean_volume: (-?[\d.]+) dB", _detect(f, "volumedetect", True))
        mv = float(vol.group(1)) if vol else -99
        res["volumen"] = (-30 <= mv <= -8, f"{mv} dB")
        sil = re.findall(r"silence_duration: ([\d.]+)", _detect(f, "silencedetect=n=-45dB:d=1.5", True))
        res["sin_silencios"] = (not sil, f"{len(sil)} silencios > 1.5 s")
    neg = re.findall(r"black_duration:([\d.]+)", _detect(f, "blackdetect=d=1:pix_th=0.05", False))
    res["sin_negro"] = (not neg, f"{len(neg)} tramos negros")
    frz = re.findall(r"freeze_duration: ([\d.]+)", _detect(f, "freezedetect=n=0.003:d=4", False))
    res["sin_congelados"] = (not frz, f"{len(frz)} tramos congelados > 4 s")
    if srt:
        res["subtitulos"] = srt_sincronizado(srt, dur)
    return {"ok": all(ok for ok, _ in res.values()), "checks": res, "duracion_s": dur}
