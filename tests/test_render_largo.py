"""Prueba del parche v4.2 (vídeo largo 16:9) con un motor SIMULADO que reproduce las interfaces del motor v4
(render.Scene/_final/scene_overlays/composite, comp, gfx, audio, voice, qc._probe). Comprueba el código nuevo
(formato, capítulos, memoria acotada, subtítulos, codificación, miniatura, QC largo). La prueba con el motor real
se hace en el Mac (fase 7)."""
import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import cv2
import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parents[1]

STUBS = {
    "__init__.py": "",
    "comp.py": '''
import math
import numpy as np
WW, WH = 720, 1280
_VIG = None
def ease_io(t):
    t = min(1.0, max(0.0, t)); return 0.5 - 0.5 * math.cos(math.pi * t)
class Noise2D:
    def __init__(self, seed=0, w=WW, h=WH):
        self.w, self.h = w, h
class Grain:
    def __init__(self, seed=3):
        self.shape = (WH, WW)
''',
    "gfx.py": '''
from PIL import Image, ImageDraw, ImageFont
W, H = 1080, 1920
AMBER = (255, 184, 64)
def F(name, size, weight=None):
    return ImageFont.load_default(size)
def rgba(w, h):
    return Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
def text_size(font, txt):
    b = font.getbbox(txt); return b[2] - b[0], b[3] - b[1], b
def shadow_text(img, xy, txt, font, fill=(255, 255, 255, 255), shadow=10, sop=200, stroke=0, stroke_fill=(0, 0, 0, 255), anchor="la"):
    ImageDraw.Draw(img).text(xy, txt, font=font, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=stroke_fill); return img
def caption_groups(words, max_words=3, max_chars=20):
    groups, cur = [], []
    for i, w in enumerate(words):
        cur.append(i)
        if len(cur) >= max_words or w["w"][-1] in ".,?!":
            groups.append(cur); cur = []
    if cur: groups.append(cur)
    return groups
def caption_img(words_t, hi, kw):
    im = rgba(600, 120); ImageDraw.Draw(im).text((20, 20), " ".join(words_t).upper(), font=F("x", 60), fill=(255, 255, 255, 255)); return im
def lower_third(l1, l2=None, chars=None):
    im = rgba(700, 170); ImageDraw.Draw(im).rectangle([0, 10, 690, 150], fill=(8, 8, 10, 160))
    ImageDraw.Draw(im).text((30, 30), l1, font=F("x", 46), fill=(255, 255, 255, 255)); return im
def big_title(text, sub=None):
    im = rgba(W, 200); ImageDraw.Draw(im).text((W // 2, 20), text, font=F("x", 80), fill=(255, 255, 255, 255), anchor="ma"); return im
''',
    "audio.py": '''
import numpy as np
SR = 48000
SFX_LEVEL = {}
def reverb(x, **k): return x
def sfx(k, d, seed=0): return np.zeros((int(d * SR), 2))
def place(buf, x, at, level, pan=0.0, fade=0.1): pass
def music(total, beats, seed=4):
    t = np.arange(int(total * SR)) / SR; m = 0.05 * np.sin(2 * np.pi * 110 * t); return np.stack([m, m], 1)
def duck(m, v, db): return m
''',
    "voice.py": '''
import numpy as np
SR = 48000
def synth(text, preset):
    ws = text.split(); d = 0.36 * len(ws) + 0.1
    t = np.arange(int(d * SR)) / SR; au = 0.3 * np.sin(2 * np.pi * 220 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t))
    return au, [{"w": w, "t0": 0.05 + 0.36 * i, "t1": 0.05 + 0.36 * i + 0.3} for i, w in enumerate(ws)]
''',
    "qc.py": '''
import json, subprocess
def _probe(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", p], capture_output=True, text=True)
    return json.loads(r.stdout)
''',
    "render.py": '''
import hashlib, json, math, os, subprocess, wave
import cv2
import numpy as np
from . import comp as C
from . import gfx as G
FPS = 24
OUT_W, OUT_H = 1080, 1920
LEAD, TRANS, GAP, TAIL = 0.28, 0.42, 0.30, 1.9
PREPARADAS = []
class Scene:
    def __init__(self, spec, idx, plates_dir, script):
        self.s, self.idx, self.v, self.plates_dir = spec, idx, spec.get("visual", {}), plates_dir
        self.img = None
    def prepare(self):
        PREPARADAS.append(self.idx)
        if self.v.get("type") == "plate":
            im = cv2.imread(os.path.join(self.plates_dir, self.v["plate"] + ".png"))[:, :, ::-1].astype(np.float32) / 255
        else:
            im = np.full((400, 300, 3), 0.6, np.float32)
        self.img = cv2.resize(im, (int(C.WW * 1.15), int(C.WH * 1.15)))
    def base(self, lt, dur):
        assert self.img is not None, "escena %d sin preparar" % self.idx
        u = min(1, lt / max(dur, 0.01)); z = 1 + 0.1 * u
        h, w = self.img.shape[:2]; cw, ch = int(C.WW * 1.15 / z), int(C.WH * 1.15 / z)
        x0, y0 = (w - cw) // 2, (h - ch) // 2
        return cv2.resize(self.img[y0:y0 + ch, x0:x0 + cw], (C.WW, C.WH))
def scene_overlays(scene, lt, dur):
    res = []
    for ov in scene.s.get("overlays", []):
        if lt < ov.get("at", 0) or lt > ov.get("until", dur + 1): continue
        if ov["type"] == "lower_third": res.append((G.lower_third(ov["l1"], ov.get("l2")), 50, ov.get("y", 250), 1.0))
        elif ov["type"] == "title": res.append((G.big_title(ov["text"]), 0, ov.get("y", 560), 1.0))
        elif ov["type"] == "label": res.append((G.rgba(200, 50), OUT_W - 250, 250, 1.0))
    return res
def composite(dst, im, x, y, alpha=1.0):
    a = np.asarray(im, np.uint8); h, w = a.shape[:2]
    x0, y0 = max(0, x), max(0, y); x1, y1 = min(OUT_W, x + w), min(OUT_H, y + h)
    if x1 <= x0 or y1 <= y0: return
    src = a[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.float32); al = src[..., 3:4] / 255.0 * alpha
    dst[y0:y1, x0:x1] = (dst[y0:y1, x0:x1] * (1 - al) + src[..., :3] * al).astype(np.uint8)
def _final(objs, scenes, S, cur, tt, grain, f, total):
    s = scenes[cur]; lt = tt - s["v0"]; img = objs[cur].base(lt, s["v1"] - s["v0"])
    if cur > 0 and lt < TRANS:
        p = scenes[cur - 1]; prev = objs[cur - 1].base(tt - p["v0"], p["v1"] - p["v0"]); a = C.ease_io(lt / TRANS); img = prev * (1 - a) + img * a
    assert img.shape == (C.WH, C.WW, 3)
    return np.clip(img, 0, 1)
def _write_wav(path, x):
    x = np.clip(x, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000); w.writeframes((x * 32767).astype("<i2").tobytes())
def _loudnorm(src, dst, I=-14.0, TP=-1.5, LRA=9):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-af", "loudnorm=I=-14:TP=-1.5:LRA=9", "-ar", "48000", dst], check=True)
    return {"input_i": -20.0, "output_i": -14.2, "output_tp": -1.6}
def _write_srt(path, words, groups):
    open(path, "w").write("\\n".join(" ".join(words[i]["w"] for i in g) for g in groups))
def storyboard(S, scenes, words):
    return [{"escena": k + 1, "plano": sc.get("shot", "x"), "camara": sc.get("visual", {}).get("move", "push_in"), "iluminacion": "x",
             "ambiente": "x", "relacion": "x", "duracion_s": scenes[k]["v1"] - scenes[k]["v0"], "narracion": sc["say"]} for k, sc in enumerate(S["scenes"])]
def storyboard_md(S, sb): return "storyboard"
def render_plates(S, plates_dir): pass
def _sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
''',
}


@pytest.fixture()
def motor(tmp_path):
    pkg = tmp_path / "motor" / "arvis_expedientes"
    pkg.mkdir(parents=True)
    for n, c in STUBS.items():
        (pkg / n).write_text(textwrap.dedent(c))
    for n in ("formato.py", "render_largo.py", "qc_largo.py", "miniatura.py"):
        shutil.copy(RAIZ / "arvis_expedientes" / n, pkg / n)
    return tmp_path / "motor"


def _guion(tmp_path):
    plates = tmp_path / "plates"
    plates.mkdir()
    rng = np.random.RandomState(1)
    for i in range(3):
        img = np.clip(rng.rand(828, 1472, 3) * 80 + np.linspace(40, 200, 1472)[None, :, None] * (i + 1) / 3, 0, 255).astype(np.uint8)
        cv2.imwrite(str(plates / ("LG-T_img%02d.png" % (i + 1))), img)
    frase = "esta es una frase de prueba con bastantes palabras para el ritmo"
    S = {"id": "LG-T", "formato": "16:9", "title": "Prueba del vídeo largo", "description": "Descripción.", "thumbnail_text": "El volcán que heló Europa",
         "thumbnail_keywords": ["VOLCÁN"], "serie_tag": "ARCHIVO", "cover_scene": 0, "containsSyntheticMedia": True,
         "sources": ["https://a.org/1", "https://b.org/2", "https://c.org/3"], "facts": [{"claim": "x", "source": [0], "tipo": "hecho"}],
         "scenes": [
             {"say": "Un volcán cambió el clima.", "capitulo": "El volcán", "visual": {"type": "plate", "plate": "LG-T_img01", "move": "push_in"},
              "overlays": [{"type": "label", "text": "IMAGEN GENERADA CON IA"}]},
             {"say": frase, "visual": {"type": "plate", "plate": "LG-T_img02", "move": "pan_left"}, "overlays": [{"type": "label"}, {"type": "title", "text": "1816"}]},
             {"say": frase, "capitulo": "Las consecuencias", "visual": {"type": "document", "title": "Diario", "lines": ["a"]}},
             {"say": frase + " final.", "capitulo": "Qué aprendimos", "visual": {"type": "plate", "plate": "LG-T_img03", "move": "drift"},
              "overlays": [{"type": "label"}]},
         ]}
    p = tmp_path / "guion_motor.json"
    p.write_text(json.dumps(S, ensure_ascii=False))
    return p, plates


def test_largo_16_9_completo(tmp_path, motor):
    p, plates = _guion(tmp_path)
    out = tmp_path / "out"
    r = subprocess.run([sys.executable, "-m", "arvis_expedientes.render_largo", str(p), "--out", str(out), "--plates", str(plates), "--fast"],
                       cwd=str(motor), capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-2000:]
    rep = json.load(open(out / "LG-T.json"))
    pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", rep["mp4"]], capture_output=True, text=True).stdout)
    v = [s for s in pr["streams"] if s["codec_type"] == "video"][0]
    assert (v["width"], v["height"]) == (1920, 1080) and any(s["codec_type"] == "audio" for s in pr["streams"])
    assert abs(float(pr["format"]["duration"]) - rep["duration_s"]) < 0.6
    assert rep["chapters"][0][0] == 0 and [c[1] for c in rep["chapters"]] == ["El volcán", "Las consecuencias", "Qué aprendimos"]
    assert "Capítulos:" in rep["description"] and "0:00 El volcán" in rep["description"] and "Fuentes:" in rep["description"]
    mini = cv2.imread(rep["thumbnail"])
    assert mini.shape[:2] == (720, 1280)
    assert rep["total"] == 20 and len(list(out.glob("LG-T_still_*.png"))) == 4
    fallos = " | ".join(rep["failed"])
    assert "Duración 8–12 min" in fallos                    # la prueba dura segundos: debe detectarlo
    assert "Formato 1920×1080" not in fallos and "Decodifica" not in fallos and "Miniatura" not in fallos
    assert "Imágenes sintéticas" not in fallos and "Subtítulos" not in fallos and "Fuentes" not in fallos
    assert "≥ 10 s entre ellos" in fallos and "estáticas: [3]" in fallos      # pieza de 20 s y tarjeta lisa: el QC lo detecta
    # el título centrado: la columna central del fotograma con el título tiene texto blanco
    assert not (out / "LG-T_video.mkv").exists() and not (out / "LG-T_mix.wav").exists()


def test_largo_rechaza_tipos_solo_verticales(tmp_path, motor):
    p, plates = _guion(tmp_path)
    S = json.loads(p.read_text())
    S["scenes"][1]["visual"] = {"type": "map", "lon": 1, "lat": 2}
    p.write_text(json.dumps(S))
    r = subprocess.run([sys.executable, "-m", "arvis_expedientes.render_largo", str(p), "--out", str(tmp_path / "o"), "--plates", str(plates)],
                       cwd=str(motor), capture_output=True, text=True, timeout=120)
    assert r.returncode != 0 and "aún no está disponible en 16:9" in r.stderr


def test_formato_cambia_dimensiones_del_motor(motor):
    code = ("from arvis_expedientes import formato, comp as C, render as R; l = formato.aplicar('16:9'); "
            "print(C.WW, C.WH, R.OUT_W, R.OUT_H, C.Noise2D().w, C.Noise2D().h, l['subtitulos_y'])")
    r = subprocess.run([sys.executable, "-c", code], cwd=str(motor), capture_output=True, text=True)
    assert r.stdout.split() == ["1280", "720", "1920", "1080", "1280", "720", "930"], r.stderr
