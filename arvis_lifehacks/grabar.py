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
