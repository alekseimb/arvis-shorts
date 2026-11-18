"""Control de espacio y limpieza de temporales.

Solo se borran INTERMEDIOS (imágenes de trabajo, escenarios, audio, vídeo sin comprimir, fotogramas de revisión)
de vídeos ya PUBLICADOS y CONFIRMADOS por YouTube, pasados «intermedios_dias». El MP4 final, la miniatura,
el guion y los informes no se borran nunca de forma automática.
"""
import shutil
import time
from pathlib import Path

INTERMEDIOS = ("imagenes", "plates", "stills", "*_mix.wav", "*_mix_norm.wav", "*_video.mkv", "*.2pass*")


def libre_gb(ruta):
    ruta = Path(ruta)
    while not ruta.exists():
        ruta = ruta.parent
    return shutil.disk_usage(ruta).free / 1e9


def hay_espacio(ruta, minimo_gb):
    return libre_gb(ruta) >= minimo_gb


def limpiar(cola, carpeta_trabajo, dias=7, simular=False):
    """Devuelve la lista de rutas borradas (o que se borrarían con simular=True) y el espacio liberado."""
    limite = time.time() - dias * 86400
    borrado, liberado = [], 0
    pubs = {p["clave"]: p for p in cola.publicaciones() if p.get("confirmado")}
    for t in cola.lista(["publicado"]):
        p = pubs.get(t["clave"])
        if not p or (p["confirmado"] or time.time()) > limite:
            continue
        base = Path(carpeta_trabajo) / t["clave"]
        if not base.exists():
            continue
        for patron in INTERMEDIOS:
            for x in base.glob(patron):
                tam = _tam(x)
                if not simular:
                    shutil.rmtree(x) if x.is_dir() else x.unlink()
                borrado.append(str(x))
                liberado += tam
    return {"borrado": borrado, "liberado_gb": round(liberado / 1e9, 2), "simulado": simular}


def _tam(p):
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
