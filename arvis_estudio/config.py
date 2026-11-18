"""Rutas y ajustes del estudio. Los ajustes viven en <ARVIS_HOME>/estudio/ajustes.json (sin secretos).

Equipo actual (auditado el 18/11/2026): MacBook Pro 13" 2019 Intel Core i5 (4 núcleos, 1,4 GHz), 8 GB, Iris Plus 645,
disco interno con 5,6 GB libres → el estudio vive en el volumen externo: ARVIS_HOME=/Volumes/DADES/arvis.
En este equipo NO se generan imágenes (motor_imagen = "ninguno"): el motor v4 monta con sus escenarios procedurales.
"""
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
    # Generación de imágenes: "ninguno" (MacBook Pro Intel 2019: en pausa por hardware) | "comfyui" (solo en un
    # Mac Apple Silicon cuyo hardware se haya comprobado antes; decisión de Aleksei del 18/11/2026).
    "motor_imagen": "ninguno",
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
    "python_motor": str(BASE / "venv-motor" / "bin" / "python"),   # entorno del motor v4 (bpy, piper)
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


def base_disponible():
    """Si el estudio vive en un volumen externo (/Volumes/<disco>/...), ese disco tiene que estar montado.
    Sin esta comprobación, con el disco desconectado se crearía una carpeta falsa en el disco interno (casi lleno)."""
    partes = BASE.parts
    if len(partes) > 2 and partes[1] == "Volumes":
        return os.path.ismount(os.path.join("/", "Volumes", partes[2])) and BASE.exists()
    return True


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
