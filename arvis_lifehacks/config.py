"""Constantes de LIFEHACKS AI (formato, identidad visual, franjas)."""
import os

W, H = 1080, 1920
FPS = 30
SR = 48000
SERIE = "lifehacks"
MARCA = "LIFEHACKS AI"
LEMA = "Pequeñas soluciones inteligentes"
FRANJAS = ["12:00", "17:00", "21:00"]          # decisión de Aleksei del 18/11/2026
ZONA = "Europe/Madrid"
MARGEN_MIN = 90                                 # minutos mínimos entre el fin del montaje y la franja
MAX_MB_MAKE = 4.6                               # Make Free admite 5 MB por archivo
CATEGORIA_YT = "28"                             # Ciencia y tecnología
DURACION = (25.0, 50.0)                         # duración ideal pedida por Aleksei
VOZ = "sharvard_m"                              # decisión de Aleksei del 18/11/2026 (muestra 2)
CREDITO_VOZ = {
    "sharvard_m": "Voz: modelo Piper es_ES «sharvard» (corpus Sharvard, Universidad de Edimburgo, CC BY 3.0).",
    "davefx_natural": "", "davefx_tuto": "", "davefx": "",
}
CACHE = os.path.expanduser(os.environ.get("ARVIS_EXP_CACHE", "~/.cache/arvis_expedientes"))

# Identidad visual (coherente entre vídeos): azul noche + cian eléctrico + lima
C = {
    "bg0": (8, 12, 24), "bg1": (14, 24, 46), "panel": (18, 24, 38), "barra": (30, 38, 56),
    "cian": (0, 224, 255), "lima": (176, 255, 46), "texto": (238, 243, 250), "gris": (148, 160, 182),
    "aviso": (255, 200, 40), "rojo": (255, 92, 92), "negro": (0, 0, 0),
}
# Zonas seguras de Shorts (botones de YouTube a la derecha y abajo)
CABECERA_Y = 96
VENTANA = (44, 262, 1036, 1168)                 # x0, y0, x1, y1 de la ventana de captura
SUBS_Y = 1262                                   # centro de los subtítulos
LIMITE_Y = 1450                                 # nada importante por debajo
