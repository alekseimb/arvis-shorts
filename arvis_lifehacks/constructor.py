"""AI TUTORIAL BUILDER · construye y prueba las herramientas de cada tutorial antes de grabar nada.

Reglas (encargo de Aleksei del 18/11/2026):
- Python, HTML, CSS y JavaScript con herramientas locales y gratuitas; sin API de pago.
- Código funcional y probado: las pruebas tienen que pasar y la demostración se graba de una ejecución real.
- Nada peligroso: revisión estática + ejecución en una carpeta temporal aislada, sin red y con tiempo límite.
  Las herramientas nunca tocan archivos del usuario; por defecto ni borran ni mueven nada (solo con un permiso
  declarado en el guion y siempre dentro de la carpeta de demostración).
"""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

PATRONES_PY = {
    "borrar": [r"\bos\.remove\(", r"\bos\.unlink\(", r"\.unlink\(", r"shutil\.rmtree", r"\bos\.rmdir\(", r"\.rmdir\("],
    "mover": [r"shutil\.move", r"\bos\.rename\(", r"\.rename\(", r"\bos\.replace\("],
    "red": [r"\bimport\s+socket", r"\brequests\b", r"\burllib\b", r"http\.client", r"\bhttpx\b", r"\baiohttp\b", r"\bsmtplib\b", r"\bftplib\b"],
    "procesos": [r"\bsubprocess\b", r"\bos\.system\(", r"\bos\.popen\(", r"\bpty\b", r"\bos\.exec"],
    "dinamico": [r"(?<![\w.])eval\(", r"(?<![\w.])exec\(", r"__import__\(", r"(?<![\w.])compile\("],
    "escribir": [r"open\([^)]*['\"][wax]\+?b?['\"]", r"\.write_text\(", r"\.write_bytes\(", r"shutil\.copy"],
    "sistema": [r"\bwinreg\b", r"\bctypes\b", r"\bsudo\b", r"chmod\s+777", r"\bkeyboard\b", r"\bpynput\b"],
}
PATRONES_WEB = {
    "red": [r"\bfetch\(", r"XMLHttpRequest", r"WebSocket", r"sendBeacon", r"<script[^>]+src=['\"]https?:", r"<link[^>]+href=['\"]https?:", r"@import\s+url\(['\"]?https?:"],
    "dinamico": [r"(?<![\w.])eval\(", r"new\s+Function\("],
    "sistema": [r"document\.cookie"],
}


def revisar(carpeta, permisos=()):
    """Revisión estática. Devuelve (ok, [hallazgos])."""
    hallazgos = []
    for raiz, _, archivos in os.walk(carpeta):
        for a in archivos:
            ruta = os.path.join(raiz, a)
            # las pruebas y el preparador de la demo no son la herramienta que se enseña (se ejecutan aislados igualmente)
            if a.startswith(("test_", "prueba_", "preparar_")) or a == "guion.json" or "__pycache__" in ruta:
                continue
            if a.endswith(".py"):
                pat = PATRONES_PY
            elif a.endswith((".html", ".js", ".css")):
                pat = PATRONES_WEB
            else:
                continue
            txt = open(ruta, encoding="utf-8", errors="replace").read()
            for clase, lista in pat.items():
                if clase in permisos:
                    continue
                for p in lista:
                    for m in re.finditer(p, txt):
                        linea = txt[: m.start()].count("\n") + 1
                        hallazgos.append("%s:%d · %s (%s)" % (a, linea, clase, m.group(0)[:40]))
    return (not hallazgos), hallazgos


def entorno_aislado(carpeta):
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": carpeta, "LANG": "es_ES.UTF-8", "LC_ALL": "C.UTF-8",
           "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1",
           # sin red: cualquier intento de conexión falla en el acto
           "HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9", "http_proxy": "http://127.0.0.1:9",
           "https_proxy": "http://127.0.0.1:9", "NO_PROXY": "", "no_proxy": ""}
    return env


def preparar_sandbox(origen, clave="tuto"):
    """Copia la herramienta a /tmp/lh/<clave>/demo (ruta neutra: no muestra nombres de usuario en pantalla)."""
    base = os.path.join(tempfile.gettempdir(), "lh", clave)
    if os.path.isdir(base):
        shutil.rmtree(base)          # solo la carpeta temporal propia de esta demostración
    dst = os.path.join(base, "demo")
    shutil.copytree(origen, dst, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "guion.json"))
    return dst


def pruebas(carpeta, timeout=180):
    """Ejecuta las pruebas de la herramienta (pytest) dentro de la carpeta aislada."""
    tests = [a for a in os.listdir(carpeta) if a.startswith(("test_", "prueba_")) and a.endswith(".py")]
    if not tests:
        return {"ok": False, "log": "La herramienta no trae pruebas (test_*.py)", "tests": 0}
    t0 = time.time()
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"] + tests, cwd=carpeta,
                       env=entorno_aislado(carpeta), capture_output=True, text=True, timeout=timeout)
    log = (r.stdout + r.stderr)[-4000:]
    m = re.search(r"(\d+) passed", log)
    fallos = re.search(r"(\d+) failed", log)
    return {"ok": r.returncode == 0 and bool(m) and not fallos, "log": log, "tests": int(m.group(1)) if m else 0,
            "segundos": round(time.time() - t0, 1)}


def sesion_terminal(comandos, carpeta, timeout=60, prompt="~/demo $"):
    """Ejecuta de verdad cada comando y apunta cada línea de salida con su instante.

    comandos: [{"cmd": "python3 duplicados.py Descargas_demo"}] (sin shell; el programa tiene que estar en la carpeta
    o ser python3). Devuelve {"eventos": [{t, tipo: cmd|out|err, texto}], "codigos": [...], "ok": bool}.
    """
    eventos, codigos, t_base = [], [], time.time()
    env = entorno_aislado(carpeta)
    for c in comandos:
        args = shlex.split(c["cmd"])
        if args[0] not in ("python3", "python") and not os.path.exists(os.path.join(carpeta, args[0])):
            raise ValueError("Comando no permitido en la demostración: %s" % c["cmd"])
        if args[0] in ("python3", "python"):
            args[0] = sys.executable
        eventos.append({"t": round(time.time() - t_base, 3), "tipo": "cmd", "texto": c["cmd"], "prompt": c.get("prompt", prompt)})
        p = subprocess.Popen(args, cwd=carpeta, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        limite = time.time() + timeout
        for linea in p.stdout:
            eventos.append({"t": round(time.time() - t_base, 3), "tipo": "out", "texto": linea.rstrip("\n")})
            if time.time() > limite:
                p.kill()
                break
        codigos.append(p.wait(timeout=10))
        time.sleep(0.05)
    return {"eventos": eventos, "codigos": codigos, "ok": all(c == 0 for c in codigos)}


def construir(guion, base_tutorial, salida):
    """Paso completo del AI TUTORIAL BUILDER para un guion. Escribe salida/herramienta.json con la evidencia."""
    h = guion["herramienta"]
    origen = os.path.join(base_tutorial, h.get("carpeta", "."))
    permisos = h.get("permisos", [])
    ok_rev, hallazgos = revisar(origen, permisos)
    trabajo = preparar_sandbox(origen, guion.get("id", "tuto"))
    # carpeta de demostración (archivos de prueba creados por la propia herramienta de preparación)
    prep = None
    if h.get("preparar_demo"):
        prep = subprocess.run([sys.executable, h["preparar_demo"]], cwd=trabajo, env=entorno_aislado(trabajo),
                              capture_output=True, text=True, timeout=120)
    res_pruebas = pruebas(trabajo)
    sesiones = {}
    for cap in guion.get("capturas", []):
        if cap["tipo"] == "terminal":
            sesiones[cap["id"]] = sesion_terminal(cap["comandos"], trabajo, prompt=cap.get("prompt", "~/demo $"))
    informe = {
        "revision_ok": ok_rev, "hallazgos": hallazgos, "permisos": permisos,
        "preparar_demo": None if prep is None else {"codigo": prep.returncode, "log": (prep.stdout + prep.stderr)[-1500:]},
        "pruebas": res_pruebas, "sesiones": sesiones, "carpeta_trabajo": trabajo,
        "ok": ok_rev and res_pruebas["ok"] and (prep is None or prep.returncode == 0) and all(s["ok"] for s in sesiones.values()),
    }
    os.makedirs(salida, exist_ok=True)
    json.dump(informe, open(os.path.join(salida, "herramienta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return informe
