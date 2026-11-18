"""Grabaciones de pantalla reales con Chrome sin cabeza (Playwright: capturas continuas a ~10 fps, escala 2).

Solo se graban páginas locales (file:// o 127.0.0.1) hechas por ARVIS o del propio navegador: nada de webs de
terceros, logotipos ajenos ni marcas de agua. Cada acción (escribir, pulsar, desplazar) queda en una línea de
tiempo con la caja del elemento, para dibujar el cursor, el clic y el zoom del montaje.
"""
import json
import os
import time

from PIL import Image

CHROME = os.environ.get("ARVIS_CHROME", "/usr/bin/google-chrome")


def _permitida(url):
    return url.startswith(("file://", "http://127.0.0.1", "http://localhost", "about:"))


def capturar_web(cap, carpeta_trabajo, salida):
    """cap = {"id", "url" (relativa a la carpeta de trabajo o file://), "viewport": [w, h], "escala": 2,
              "acciones": [{"hacer": "esperar|escribir|pulsar|desplazar|ir", "sel": css, "texto": str, "ms": int, "y": px}]}
    Devuelve {"frames": [[t, ruta]], "eventos": [[t, tipo, caja]], "duracion": s, "url": url}."""
    from playwright.sync_api import sync_playwright
    url = cap["url"]
    if "://" not in url:
        url = "file://" + os.path.abspath(os.path.join(carpeta_trabajo, url))
    if not _permitida(url):
        raise ValueError("Solo se graban páginas locales: %s" % url)
    vw, vh = cap.get("viewport", [496, 425])
    esc = cap.get("escala", 2)
    d = os.path.join(salida, "cap_" + cap["id"])
    os.makedirs(d, exist_ok=True)
    frames, eventos = [], []
    with sync_playwright() as p:
        nav = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                                                              "--force-color-profile=srgb", "--lang=es-ES"],
                                  env={"LANGUAGE": "es", "LANG": "es_ES.UTF-8", "LC_ALL": "es_ES.UTF-8", "HOME": carpeta_trabajo,
                                       "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "TZ": "Europe/Madrid"})
        ctx = nav.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=esc, locale="es-ES")
        ctx.route("**/*", lambda r: r.continue_() if _permitida(r.request.url) or r.request.url.startswith("data:") else r.abort())
        pg = ctx.new_page()
        errores = []
        pg.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errores.append(str(e)))
        pg.goto(url)
        pg.wait_for_timeout(300)
        inicio = time.time()

        def reloj():
            return round(time.time() - inicio, 3)

        def foto():
            """Captura real de la pantalla del navegador (resolución completa, escala del dispositivo)."""
            ruta = os.path.join(d, "f%05d.png" % len(frames))
            pg.screenshot(path=ruta, type="png")
            frames.append([reloj(), ruta])

        def grabar_durante(ms, cada=90):
            fin = time.time() + ms / 1000.0
            while time.time() < fin:
                foto()
                resto = (fin - time.time()) * 1000
                if resto > 0:
                    pg.wait_for_timeout(min(cada, resto))

        def caja(sel):
            try:
                b = pg.locator(sel).first.bounding_box()
                return [b["x"], b["y"], b["width"], b["height"]] if b else None    # px CSS
            except Exception:
                return None

        foto()
        for a in cap.get("acciones", []):
            h = a["hacer"]
            if h == "esperar":
                grabar_durante(a.get("ms", 500))
            elif h == "escribir":
                eventos.append([reloj(), "escribir", caja(a["sel"])])
                pg.locator(a["sel"]).first.click()
                for ch in a["texto"]:
                    pg.keyboard.type(ch)
                    pg.wait_for_timeout(a.get("retardo", 45))
                    foto()
            elif h == "pulsar":
                eventos.append([reloj(), "clic", caja(a["sel"])])
                grabar_durante(250, 80)
                pg.locator(a["sel"]).first.click()
                pg.wait_for_load_state()
                foto()
            elif h == "desplazar":
                eventos.append([reloj(), "desplazar", None])
                pasos = max(1, int(abs(a.get("y", 300)) / 30))
                for _ in range(pasos):
                    pg.mouse.wheel(0, 30 if a.get("y", 300) > 0 else -30)
                    pg.wait_for_timeout(20)
                    foto()
            elif h == "ir":
                destino = a["url"] if "://" in a["url"] else "file://" + os.path.abspath(os.path.join(carpeta_trabajo, a["url"]))
                if not _permitida(destino):
                    raise ValueError("Solo se graban páginas locales: %s" % destino)
                eventos.append([reloj(), "ir", None])
                pg.goto(destino)
                foto()
            if a.get("despues_ms"):
                grabar_durante(a["despues_ms"])
        grabar_durante(cap.get("final_ms", 600))
        texto = pg.inner_text("body")[:5000]
        nav.close()
    info = {"frames": frames, "eventos": eventos, "duracion": frames[-1][0] if frames else 0, "url": url,
            "errores_consola": errores, "texto_visible": texto, "tamano": list(Image.open(frames[0][1]).size), "viewport": [vw, vh]}
    json.dump(info, open(os.path.join(d, "captura.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return info


def frame_en(info, t):
    """Fotograma de la captura en el instante t (s) (mantiene el último cambio, como una grabación real)."""
    fr = info["frames"]
    if not fr:
        return None
    ruta = fr[0][1]
    for ti, r in fr:
        if ti <= t:
            ruta = r
        else:
            break
    return ruta


# ----------------------------------------------------------------------------- escritorio (Chrome real con su interfaz)
def capturar_escritorio(cap, carpeta_trabajo, salida):
    """Graba la pantalla completa de un Chrome real (pestañas, barra de direcciones) en un escritorio virtual (Xvfb)
    con FFmpeg x11grab. Las teclas se pulsan como un usuario (XTest), así funcionan los atajos del propio navegador.

    cap = {"id", "tipo": "escritorio", "paginas": ["receta.html", …], "pantalla": [992, 850], "escala": 1.6,
           "acciones": [{"hacer": "esperar", "ms": 1200}, {"hacer": "teclas", "combo": "ctrl+shift+t", "rotulo": "Ctrl + Mayús + T"},
                        {"hacer": "marca", "nombre": "inicio"}],
           "verificar": [["inicio", "final"]]}   # pares de marcas cuya pantalla debe coincidir (el truco funcionó)
    """
    import shutil
    import signal
    import subprocess
    import tempfile

    import numpy as np
    from Xlib import X, XK, display as xdisplay
    from Xlib.ext import xtest

    W, H = cap.get("pantalla", [992, 850])
    esc = cap.get("escala", 1.6)
    d = os.path.join(salida, "cap_" + cap["id"])
    os.makedirs(d, exist_ok=True)
    num = 70 + (os.getpid() % 20)
    disp = ":%d" % num
    xv = subprocess.Popen(["Xvfb", disp, "-screen", "0", "%dx%dx24" % (W, H), "-nolisten", "tcp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        if os.path.exists("/tmp/.X11-unix/X%d" % num):
            break
        time.sleep(0.1)
    perfil = tempfile.mkdtemp(prefix="lh_chrome_")
    urls = []
    for p in cap["paginas"]:
        u = p if "://" in p else "file://" + os.path.abspath(os.path.join(carpeta_trabajo, p))
        if not _permitida(u):
            raise ValueError("Solo se graban páginas locales: %s" % u)
        urls.append(u)
    env = dict(os.environ, DISPLAY=disp, LANGUAGE="es", LANG="es_ES.UTF-8", LC_ALL="es_ES.UTF-8", TZ="Europe/Madrid", HOME=perfil)
    ch = subprocess.Popen([CHROME, "--no-sandbox", "--test-type", "--user-data-dir=" + perfil, "--no-first-run", "--no-default-browser-check",
                           "--disable-gpu", "--disable-sync", "--disable-background-networking", "--disable-component-update",
                           "--disable-features=Translate,MediaRouter,OptimizationHints,PrivacySandboxSettings4", "--password-store=basic",
                           "--hide-crash-restore-bubble", "--lang=es-ES", "--force-device-scale-factor=%s" % esc,
                           "--window-position=0,0", "--window-size=%d,%d" % (int(W / esc), int(H / esc))] + urls,
                          env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(cap.get("arranque_s", 4.0))
    try:   # el puntero, a una esquina (no tapa nada)
        _xd = xdisplay.Display(disp)
        xtest.fake_input(_xd, X.MotionNotify, x=W - 2, y=H - 2)
        _xd.sync()
    except Exception:
        pass
    video = os.path.join(d, "pantalla.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "x11grab", "-video_size", "%dx%d" % (W, H), "-framerate", "30",
                           "-i", disp, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "12", "-pix_fmt", "yuv444p", video],
                          stdin=subprocess.PIPE, env=env)
    inicio = time.time() + 0.25          # arranque aproximado de x11grab
    time.sleep(0.6)
    xd = xdisplay.Display(disp)
    eventos, marcas = [], {}

    def reloj():
        return round(time.time() - inicio, 3)

    def tecla(nombre, abajo):
        ks = XK.string_to_keysym({"ctrl": "Control_L", "shift": "Shift_L", "alt": "Alt_L"}.get(nombre, nombre))
        xtest.fake_input(xd, X.KeyPress if abajo else X.KeyRelease, xd.keysym_to_keycode(ks))
        xd.sync()

    def captura_ahora(nombre):
        ruta = os.path.join(d, "marca_%s.png" % nombre)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "x11grab", "-video_size", "%dx%d" % (W, H), "-i", disp,
                        "-frames:v", "1", ruta], env=env)
        marcas[nombre] = ruta

    for a in cap.get("acciones", []):
        h = a["hacer"]
        if h == "esperar":
            time.sleep(a.get("ms", 500) / 1000.0)
        elif h == "teclas":
            partes = a["combo"].lower().split("+")
            eventos.append([reloj(), "teclas", None, a.get("rotulo", a["combo"])])
            for k in partes:
                tecla(k, True)
                time.sleep(0.06)
            for k in reversed(partes):
                tecla(k, False)
                time.sleep(0.03)
        elif h == "marca":
            captura_ahora(a["nombre"])
    time.sleep(cap.get("final_ms", 800) / 1000.0)
    ff.stdin.write(b"q")
    ff.stdin.flush()
    ff.wait(timeout=30)
    for p in (ch, xv):
        try:
            p.send_signal(signal.SIGTERM)
            p.wait(timeout=10)
        except Exception:
            p.kill()
    shutil.rmtree(perfil, ignore_errors=True)
    # fotogramas a 15 fps para el montaje
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-vf", "fps=15", os.path.join(d, "f%05d.png")], check=True)
    fr = sorted(f for f in os.listdir(d) if f.startswith("f") and f.endswith(".png"))
    frames = [[round(i / 15.0, 3), os.path.join(d, f)] for i, f in enumerate(fr)]
    # La compilación «Chrome for Testing» del entorno muestra una barra propia bajo la barra de direcciones que el
    # Chrome normal del espectador no tiene: se recorta esa franja (edición, no se añade nada a la interfaz).
    banda = cap.get("quitar_banda", [138, 230] if (W == 992 and abs(esc - 1.6) < 0.01) else None)
    if banda:
        for _, ruta in frames:
            im = np.asarray(Image.open(ruta).convert("RGB"))
            Image.fromarray(np.concatenate([im[: banda[0]], im[banda[1]:]], axis=0)).save(ruta)
    # Calibración: x11grab arranca con retraso; se mide cuándo cambia de verdad la pantalla tras cada pulsación
    # y se corrige la hora de los eventos (así las teclas en pantalla coinciden con lo que se ve).
    if eventos and len(frames) > 2:
        grises = [np.asarray(Image.open(r).convert("L"), dtype=np.float32) for _, r in frames]
        retrasos = []
        for ev in eventos:
            for i in range(1, len(frames)):
                if frames[i][0] < ev[0]:
                    continue
                if frames[i][0] > ev[0] + 1.5:
                    break
                if float(np.mean(np.abs(grises[i] - grises[i - 1]))) > 1.0:
                    retrasos.append(frames[i][0] - ev[0])
                    break
        if retrasos:
            ajuste = max(0.0, sorted(retrasos)[len(retrasos) // 2] - 0.08)
            for ev in eventos:
                ev[0] = round(ev[0] + ajuste, 3)
            cap["_ajuste_s"] = round(ajuste, 3)
    verif = []
    for a_, b_ in cap.get("verificar", []):
        if a_ in marcas and b_ in marcas:
            A = np.asarray(Image.open(marcas[a_]).convert("L"), dtype=np.float32)
            B = np.asarray(Image.open(marcas[b_]).convert("L"), dtype=np.float32)
            dif = float(np.mean(np.abs(A - B)))
            verif.append({"antes": a_, "despues": b_, "diferencia": round(dif, 2), "ok": dif < 3.0})
        else:
            verif.append({"antes": a_, "despues": b_, "ok": False, "diferencia": None})
    info = {"frames": frames, "eventos": eventos, "duracion": frames[-1][0] if frames else 0, "url": urls[0],
            "errores_consola": [], "texto_visible": " ".join(cap["paginas"]) + " " + " ".join(urls),
            "tamano": [W, H - ((banda[1] - banda[0]) if banda else 0)], "viewport": [W, H], "banda_quitada": banda,
            "verificaciones": verif, "video": video, "ajuste_eventos_s": cap.get("_ajuste_s", 0.0)}
    json.dump(info, open(os.path.join(d, "captura.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return info
