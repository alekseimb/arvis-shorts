"""Rutas y ajustes del estudio. Los ajustes viven en ~/ARVIS/estudio/ajustes.json (sin secretos)."""
import json
import os
from pathlib import Path

BASE = Path(os.environ.get("ARVIS_HOME", "~/ARVIS")).expanduser()
ESTUDIO = BASE / "estudio"
TRABAJO = ESTUDIO / "trabajo"      # una carpeta por vídeo (imágenes, escenarios, audio, render)
LISTOS = ESTUDIO / "listos"        # vídeos aprobados (MP4, miniatura, metadatos)
LOGS = ESTUDIO / "logs"
DB = ESTUDIO / "estudio.db"
AJUSTES = ESTUDIO / "ajustes.json"
ESTADO = ESTUDIO / "estado.json"   # latido y resumen para el Supervisor
MOTOR = BASE / "motor"             # motor v4 (arvis_expedientes) + parche v4.2
COMFY_DIR = BASE / "ComfyUI"

DEFECTO = {
    "comfy_url": "http://127.0.0.1:8188",
    "modelo_imagen": "zimage_turbo",
    "umbral_calidad": 85,
    "reediciones_max": 2,
    "disco_min_gb": 25,
    "intermedios_dias": 7,            # se borran solo intermedios de vídeos ya publicados y confirmados
    "reintentos_paso": 2,
    # YouTube: hasta que Google apruebe la auditoría del proyecto, toda subida por API queda privada
    # y NO se puede hacer pública. Estos dos ajustes solo los cambia Aleksei.
    "integracion_youtube_auditada": False,
    "publicacion_publica_autorizada": False,
    "canal_id_esperado": "",
    "subida_largo": "manual",         # manual | api   (decisión D3 del 18/11/2026)
    "subida_short": "make",           # make | api | manual  (transición hasta la auditoría)
    "hoja_videos_id": "10jcTixYo7toV-AyFyOKasHGY8zm-RbRT3Oqm77MsVWA",
    "hoja_pestana_cola": "COLA_MAC",
    "repo_ordenes": "",               # clon local del repositorio con guiones y revisiones (git pull)
    "make_webhook_avisos": "",        # opcional: solo errores y publicaciones (cada aviso gasta operaciones)
    "python_motor": str(Path("~/ARVIS/venv-motor/bin/python").expanduser()),   # entorno del motor v4 (bpy, piper)
    "max_largos_dia": 1,
    "max_shorts_dia": 2,
}


def ajustes():
    a = dict(DEFECTO)
    if AJUSTES.exists():
        a.update(json.loads(AJUSTES.read_text(encoding="utf-8")))
    return a


def guardar_ajustes(cambios):
    a = ajustes()
    a.update(cambios)
    ESTUDIO.mkdir(parents=True, exist_ok=True)
    escribir_json(AJUSTES, a)
    return a


def preparar_carpetas():
    for d in (ESTUDIO, TRABAJO, LISTOS, LOGS):
        d.mkdir(parents=True, exist_ok=True)


def escribir_json(ruta, datos):
    """Escritura atómica: nunca deja un JSON a medias si se corta la luz."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(ruta.suffix + ".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, ruta)
