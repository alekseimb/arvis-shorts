"""Avisos del estudio: notificación de macOS + registro. Opcional: webhook de Make solo para errores y publicaciones
(cada aviso gasta operaciones del plan Free; por defecto está apagado)."""
import json
import subprocess
import time
import urllib.request

from .config import LOGS


def registrar(nivel, texto, datos=None):
    LOGS.mkdir(parents=True, exist_ok=True)
    linea = {"momento": time.strftime("%Y-%m-%dT%H:%M:%S"), "nivel": nivel, "texto": texto, "datos": datos or {}}
    with open(LOGS / ("estudio_%s.jsonl" % time.strftime("%Y-%m")), "a", encoding="utf-8") as f:
        f.write(json.dumps(linea, ensure_ascii=False) + "\n")
    print("[%s] %s" % (nivel, texto), flush=True)


def notificar(titulo, texto, nivel="info", webhook=None, datos=None):
    registrar(nivel, "%s · %s" % (titulo, texto), datos)
    try:
        t = texto.replace('"', "'")[:200]
        subprocess.run(["osascript", "-e", 'display notification "%s" with title "ARVIS · %s"' % (t, titulo.replace('"', "'"))],
                       capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        pass
    if webhook and nivel in ("error", "publicado"):
        try:
            body = json.dumps({"titulo": titulo, "texto": texto, "nivel": nivel, "datos": datos or {}}).encode()
            urllib.request.urlopen(urllib.request.Request(webhook, data=body, headers={"Content-Type": "application/json"}), timeout=15)
        except OSError as e:
            registrar("aviso", "webhook de Make no respondió: %s" % e)
