"""Productor de Shorts 9:16 100 % local y gratuito.

guion JSON → voz (Piper) → escenas (Pillow) → animación (FFmpeg zoompan) →
subtítulos (SRT + quemados con libass) → música propia sintetizada → mezcla
normalizada → miniatura → QC técnico → registro de producción.

Si en el futuro se autoriza un proveedor de Open-Higgsfield, `fondo_generado`
de cada escena puede apuntar a una imagen descargada con higgsfield_client y
se usará como fondo; sin autorización todo sale de este módulo.
"""
from __future__ import annotations

import json
import math
import subprocess
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import narrador, qc, registro

W, H, FPS = 1080, 1920, 30
F_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
F_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
PALETAS = [((11, 29, 58), (31, 111, 235)), ((40, 12, 60), (190, 60, 140)), ((8, 40, 40), (20, 160, 130)),
           ((50, 20, 10), (230, 110, 40)), ((15, 20, 50), (90, 80, 220)), ((5, 45, 20), (40, 180, 90))]
ACENTO, VERDE, ROJO = (255, 214, 10), (37, 211, 102), (235, 64, 52)
PAUSA = 0.25  # s entre escenas


def _f(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"{cmd[0]} falló: {r.stderr[-800:]}")


# ---------------------------------------------------------------- dibujo
def _degradado(c0, c1) -> Image.Image:
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(c0, c1)))
    # brillo difuso para dar profundidad
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse((W * 0.1, H * 0.25, W * 0.9, H * 0.7), fill=70)
    return Image.composite(Image.new("RGB", (W, H), (255, 255, 255)), img, glow.filter(ImageFilter.GaussianBlur(160)))


def _texto_ajustado(d, texto, fuente, ancho):
    lineas, actual = [], ""
    for p in texto.split():
        prueba = f"{actual} {p}".strip()
        if d.textlength(prueba, font=fuente) <= ancho:
            actual = prueba
        else:
            lineas.append(actual); actual = p
    return lineas + [actual]


def _titular(d, texto, y=150):
    for tam in (92, 82, 72, 64):  # máx. 2 líneas para no invadir el móvil (y0=450)
        f = _f(F_BOLD, tam)
        lineas = _texto_ajustado(d, texto, f, W - 120)
        if len(lineas) <= 2:
            break
    for i, l in enumerate(lineas):
        tw = d.textlength(l, font=f)
        d.text(((W - tw) / 2, y + i * (tam + 18)), l, font=f, fill=ACENTO, stroke_width=6, stroke_fill=(0, 0, 0))


def _movil(d, x0=230, y0=450, w=620, h=940):
    d.rounded_rectangle((x0 - 18, y0 - 18, x0 + w + 18, y0 + h + 18), 70, fill=(20, 20, 24))
    d.rounded_rectangle((x0, y0, x0 + w, y0 + h), 54, fill=(245, 247, 250))
    d.rounded_rectangle((x0 + w / 2 - 70, y0 + 14, x0 + w / 2 + 70, y0 + 46), 16, fill=(20, 20, 24))
    d.rectangle((x0, y0 + 60, x0 + w, y0 + 150), fill=(0, 128, 105))
    return x0, y0, w, h


def _mano(d, x, y):
    d.ellipse((x - 46, y - 46, x + 46, y + 46), outline=ACENTO, width=10)
    d.ellipse((x - 16, y - 16, x + 16, y + 16), fill=ACENTO)


def dibujar_escena(e: dict, i: int, salida: Path) -> Path:
    img = _degradado(*PALETAS[i % len(PALETAS)])
    d = ImageDraw.Draw(img)
    _titular(d, e["titular"])
    v = e.get("visual")
    if v == "alerta":
        x0, y0, w, h = _movil(d)
        d.text((x0 + 40, y0 + 85), "Mensajes", font=_f(F_BOLD, 44), fill="white")
        d.rounded_rectangle((x0 + 40, y0 + 220, x0 + w - 40, y0 + 420), 28, fill=(225, 245, 230))
        d.text((x0 + 70, y0 + 245), "Tu código de WhatsApp:", font=_f(F_REG, 36), fill=(30, 30, 30))
        d.text((x0 + 70, y0 + 310), "482-913", font=_f(F_BOLD, 76), fill=(30, 30, 30))
        d.ellipse((W / 2 - 150, y0 + 520, W / 2 + 150, y0 + 820), fill=ROJO)
        d.text((W / 2, y0 + 670), "!", font=_f(F_BOLD, 230), fill="white", anchor="mm")
    elif v == "menu":
        x0, y0, w, h = _movil(d)
        d.text((x0 + 40, y0 + 85), "Ajustes" if i < 2 else "Cuenta", font=_f(F_BOLD, 44), fill="white")
        for k, item in enumerate(e["menu"]):
            y = y0 + 190 + k * 150
            sel = k == e.get("resaltar")
            if sel:
                d.rounded_rectangle((x0 + 20, y - 10, x0 + w - 20, y + 120), 24, fill=(210, 245, 225), outline=VERDE, width=6)
            d.ellipse((x0 + 45, y + 25, x0 + 105, y + 85), fill=VERDE if sel else (190, 195, 200))
            for j, l in enumerate(_texto_ajustado(d, item, _f(F_BOLD if sel else F_REG, 38), w - 260)[:2]):
                d.text((x0 + 130, y + 22 + j * 44), l, font=_f(F_BOLD if sel else F_REG, 38), fill=(25, 25, 25))
        _mano(d, x0 + w - 90, y0 + 190 + e.get("resaltar", 0) * 150 + 55)
    elif v == "pin":
        x0, y0, w, h = _movil(d)
        d.text((x0 + 40, y0 + 85), "Verificación en dos pasos", font=_f(F_BOLD, 36), fill="white")
        d.text((W / 2, y0 + 260), "Crea un PIN de 6 dígitos", font=_f(F_BOLD, 40), fill=(25, 25, 25), anchor="mm")
        for k in range(6):
            cx = x0 + (w - (5 * 88 + 74)) / 2 + k * 88
            d.rounded_rectangle((cx, y0 + 340, cx + 74, y0 + 440), 14, outline=(0, 128, 105), width=5)
            d.ellipse((cx + 22, y0 + 375, cx + 52, y0 + 405), fill=(25, 25, 25))
        d.rounded_rectangle((x0 + 100, y0 + 760, x0 + w - 140, y0 + 860), 50, fill=VERDE)
        d.text((W / 2 - 20, y0 + 810), "Activar", font=_f(F_BOLD, 46), fill="white", anchor="mm")
        _mano(d, x0 + w - 80, y0 + 810)
    elif v == "correo":
        x0, y0, w, h = _movil(d)
        d.text((x0 + 40, y0 + 85), "Correo de recuperación", font=_f(F_BOLD, 38), fill="white")
        d.text((W / 2, y0 + 260), "Añade tu correo", font=_f(F_BOLD, 42), fill=(25, 25, 25), anchor="mm")
        d.line((x0 + 60, y0 + 420, x0 + w - 60, y0 + 420), fill=(0, 128, 105), width=6)
        d.text((x0 + 70, y0 + 350), "tu@correo.com", font=_f(F_REG, 42), fill=(130, 130, 130))
        d.rectangle((W / 2 - 140, y0 + 520, W / 2 + 140, y0 + 700), outline=(0, 128, 105), width=10)
        d.line((W / 2 - 140, y0 + 520, W / 2, y0 + 620, W / 2 + 140, y0 + 520), fill=(0, 128, 105), width=10)
        d.rounded_rectangle((x0 + 120, y0 + 760, x0 + w - 120, y0 + 860), 50, fill=VERDE)
        d.text((W / 2, y0 + 810), "Siguiente", font=_f(F_BOLD, 46), fill="white", anchor="mm")
    elif v == "ok":
        cy = 950
        d.ellipse((W / 2 - 300, cy - 300, W / 2 + 300, cy + 300), fill=VERDE)
        d.line((W / 2 - 150, cy, W / 2 - 40, cy + 120, W / 2 + 170, cy - 130), fill="white", width=60, joint="curve")
        d.text((W / 2, cy + 420), "Sin PIN, nadie entra", font=_f(F_BOLD, 64), fill="white", anchor="mm",
               stroke_width=4, stroke_fill=(0, 0, 0))
    d.text((W - 40, H - 40), "ARVIS", font=_f(F_BOLD, 34), fill=(255, 255, 255), anchor="rd")
    img.save(salida)
    return salida


def miniatura(m: dict, salida: Path) -> Path:
    img = _degradado((10, 20, 50), (0, 128, 105)).resize((1280, 720))
    d = ImageDraw.Draw(img)
    f = _f(F_BOLD, 110)
    for k, l in enumerate(_texto_ajustado(d, m["titular"], f, 760)):
        d.text((60, 140 + k * 130), l, font=f, fill=ACENTO, stroke_width=7, stroke_fill=(0, 0, 0))
    d.text((60, 560), m["sub"], font=_f(F_BOLD, 64), fill="white", stroke_width=4, stroke_fill=(0, 0, 0))
    d.ellipse((900, 200, 1220, 520), fill=VERDE)
    d.line((980, 360, 1040, 430, 1150, 290), fill="white", width=40, joint="curve")
    img.save(salida)
    return salida


# ---------------------------------------------------------------- tiempos y subtítulos
def _ts(s: float, sep=",") -> str:
    h, r = divmod(s, 3600); m, r = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(r):02d}{sep}{int(round((r % 1) * 1000)) % 1000:03d}"


def trocear(texto: str, t0: float, dur: float, max_pal: int = 5) -> list[tuple[float, float, str]]:
    """Reparte la frase en bloques de ≤max_pal palabras, con tiempos proporcionales a los caracteres."""
    pal = texto.split()
    bloques = [" ".join(pal[k:k + max_pal]) for k in range(0, len(pal), max_pal)]
    total = sum(len(b) for b in bloques)
    out, t = [], t0
    for b in bloques:
        d = dur * len(b) / total
        out.append((t, t + d, b)); t += d
    return out


def escribir_srt(cues, f: Path) -> Path:
    f.write_text("\n".join(f"{k}\n{_ts(a)} --> {_ts(b)}\n{t}\n" for k, (a, b, t) in enumerate(cues, 1)), encoding="utf-8")
    return f


def escribir_ass(cues, f: Path) -> Path:
    cab = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n[V4+ Styles]\n"
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
           "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
           "Style: C,DejaVu Sans,74,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,7,3,2,70,70,150,1\n\n"
           "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    ev = [f"Dialogue: 0,{_ts(a, '.')[1:-1]},{_ts(b, '.')[1:-1]},C,,0,0,0,,{{\\fad(60,40)}}{t.upper()}" for a, b, t in cues]
    f.write_text(cab + "\n".join(ev) + "\n", encoding="utf-8")
    return f


# ---------------------------------------------------------------- render
def _clip(img: Path, dur: float, i: int, salida: Path) -> Path:
    n = math.ceil(dur * FPS)
    z = f"min(1+0.10*on/{n},1.10)" if i % 2 == 0 else f"max(1.10-0.10*on/{n},1.0)"
    vf = (f"scale={W * 2}:{H * 2},zoompan=z='{z}':d={n}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS},"
          f"fade=t=in:st=0:d=0.15,fade=t=out:st={dur - 0.15:.3f}:d=0.15,format=yuv420p")
    _run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(img), "-vf", vf, "-t", f"{dur:.3f}",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(FPS), str(salida)])
    return salida


def musica(dur: float, salida: Path) -> Path:
    """Pad ambiental propio (acordes Am–F–C–G con sinusoides): sin derechos de terceros."""
    acordes = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (130.81, 164.81, 196.0), (196.0, 246.94, 293.66)]
    seg = 4.0
    partes = []
    for k, ac in enumerate(acordes):
        ventana = f"between(mod(t,{seg * 4}),{k * seg},{(k + 1) * seg})"
        partes.append("+".join(f"sin(2*PI*{fr}*t)" for fr in ac) + f")*{ventana}")
    expr = "(" + "+(".join(partes)
    expr = f"0.08*({expr})*(0.75+0.25*sin(2*PI*0.25*t))"
    _run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"aevalsrc='{expr}':s=44100:d={dur:.2f}",
          "-af", f"lowpass=f=1200,aecho=0.8:0.7:120:0.3,afade=t=in:d=1,afade=t=out:st={dur - 1.5:.2f}:d=1.5",
          "-ac", "2", str(salida)])
    return salida


def producir(guion_path: Path, salida_dir: Path) -> dict:
    t_ini = time.time()
    g = json.loads(guion_path.read_text(encoding="utf-8"))
    pieza = g["pieza"]
    d = salida_dir / pieza
    d.mkdir(parents=True, exist_ok=True)
    registro.anotar(pieza, "guion", titulo=g["titulo"], linea=g.get("linea"))
    registro.anotar(pieza, "generando", motor="local: piper+pillow+ffmpeg")

    cues, clips, wavs, t = [], [], [], 0.0
    for i, e in enumerate(g["escenas"]):
        wav = narrador.sintetizar(e["voz"], d / f"voz_{i:02d}.wav")
        dv = narrador.duracion(wav)
        dur = dv + PAUSA
        cues += trocear(e["voz"], t + 0.02, dv - 0.04)
        img = dibujar_escena(e, i, d / f"escena_{i:02d}.png")
        clips.append(_clip(img, dur, i, d / f"clip_{i:02d}.mp4"))
        wavs.append((wav, dur)); t += dur
    total = t

    # audio de narración con pausas exactas
    voz = d / "voz.wav"
    ins, filt = [], []
    for k, (w, dur) in enumerate(wavs):
        ins += ["-i", str(w)]
        filt.append(f"[{k}:a]aresample=44100,apad,atrim=0:{dur:.3f}[a{k}]")
    filt.append("".join(f"[a{k}]" for k in range(len(wavs))) + f"concat=n={len(wavs)}:v=0:a=1[v]")
    _run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", ";".join(filt), "-map", "[v]", "-ac", "2", str(voz)])
    mus = musica(total, d / "musica.wav")

    lista = d / "clips.txt"
    lista.write_text("".join(f"file '{c.name}'\n" for c in clips))
    srt = escribir_srt(cues, d / f"{pieza}.srt")
    ass = escribir_ass(cues, d / f"{pieza}.ass")
    final = d / f"{pieza}.mp4"
    _run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lista), "-i", str(voz), "-i", str(mus),
          "-filter_complex",
          f"[0:v]ass={ass}[v];[2:a]volume=0.35[m];[1:a][m]amix=inputs=2:duration=first:normalize=0,"
          f"loudnorm=I=-14:TP=-1.5:LRA=11[a]",
          "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-movflags", "+faststart", "-t", f"{total:.3f}", str(final)])
    mini = miniatura(g["miniatura"], d / f"{pieza}_miniatura.jpg")
    registro.anotar(pieza, "renderizado", fichero=final.name, duracion_s=round(total, 2))

    rq = qc.revisar(final, "short", srt)
    # gancho: la primera frase de voz debe empezar antes de 2 s
    rq["checks"]["gancho_2s"] = (cues[0][0] < 2.0, f"primera palabra a {cues[0][0]:.2f}s")
    rq["ok"] = all(ok for ok, _ in rq["checks"].values())
    registro.anotar(pieza, "qc_ok" if rq["ok"] else "qc_fallo",
                    qc={k: v[0] for k, v in rq["checks"].items()},
                    tiempo_produccion_s=round(time.time() - t_ini, 1))
    return {"pieza": pieza, "video": str(final), "srt": str(srt), "miniatura": str(mini), "qc": rq,
            "tiempo_s": round(time.time() - t_ini, 1)}
