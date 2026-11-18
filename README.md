# ARVIS · Estudio audiovisual local (rama `estudio`)

Fábrica del departamento de YouTube de ARVIS en el **MacBook Pro M1 Max (64 GB)**. Coste adicional: 0 €.
No sustituye al motor v4 (`arvis_expedientes`): lo usa como corazón del montaje.

| Parte | Qué hace |
|---|---|
| `arvis_estudio/comfy.py` | ComfyUI local (127.0.0.1): Z-Image-Turbo bf16 (Apache-2.0), lotes, reintentos, imágenes vacías rechazadas, manifiesto |
| `arvis_estudio/estilos.py` | Estilo por pilar (actualidad, curiosidades, tutoriales, expedientes): consistencia dentro del vídeo, variedad entre vídeos |
| `arvis_estudio/imagenes.py` | Imagen → «escenario» del motor con mapa de profundidad (Depth-Anything-V2-Small, Apache-2.0) para la cámara 2.5D |
| `arvis_expedientes/` (parche v4.2) | `formato.py` 16:9 · `render_largo.py` vídeo largo 8–12 min con capítulos · `qc_largo.py` 20 comprobaciones · `miniatura.py` |
| `arvis_estudio/calidad.py` | Nota 0–100 (guion 20 · gancho 20 · visual 20 · narración 15 · originalidad 15 · edición 10), umbral 85, evidencias obligatorias, topes automáticos |
| `arvis_estudio/cola.py` | Cola SQLite: investigado → guionizado → generando → editando → validando → aprobado → subido → publicado (con prueba en cada paso) |
| `arvis_estudio/youtube.py` | Subida reanudable, duplicados por SHA-256, verificación, registro de privacidad. Sin auditoría de Google: solo privado |
| `arvis_estudio/servicio.py` | Lo lanza launchd cada 5 min: latido, recuperación, órdenes, un paso de la cola |
| `arvis_estudio/repo.py` | Puente con la nube por git: `ordenes/`, `guiones/`, `revision/` (fotogramas para Control de calidad). Nunca vídeos ni claves |
| `launchd/` · `instalar_mac.sh` | Servicios de macOS y la instalación (sin sudo; descargas verificadas con su huella) |

Pruebas: `python3 -m pytest -q tests/` (ComfyUI y YouTube simulados; el montaje largo con un motor simulado de mismas interfaces).
La prueba con el motor real y ComfyUI real se hace en el Mac (fase 7). Documentación: Proyecto ARVIS › `agentes/estudio_audiovisual_mac.md`.
