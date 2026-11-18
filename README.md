# ARVIS · Estudio audiovisual local (rama `estudio`)

Fábrica del departamento de YouTube de ARVIS. Coste adicional: 0 €. No sustituye al motor v4 (`arvis_expedientes`): lo usa como corazón del montaje.

> **Corrección de hardware (18/11/2026).** El Mac conectado **no es un M1 Max**: es un **MacBook Pro 13" 2019 (dos puertos Thunderbolt 3), Intel Core i5 de 4 núcleos a 1,4 GHz, 8 GB, Intel Iris Plus 645, macOS Sequoia 15.7.5**, disco interno de 121 GB con 5,6 GB libres y volumen externo DADES (224 GB, 177 GB libres).
> En este equipo: **sin generación de imágenes** (`motor_imagen = "ninguno"`, ComfyUI y Z-Image no se instalan), estudio en `ARVIS_HOME=/Volumes/DADES/arvis` (si el disco no está montado, el servicio no hace nada), motor v4 con **bpy 4.5.16** (último con macOS Intel; el motor pide ≥ 5.0: compatibilidad pendiente de probar). `instalar_mac.sh` es **solo para un Mac Apple Silicon verificado** y se detiene en Intel.

| Parte | Qué hace |
|---|---|
| `arvis_estudio/comfy.py` | **En espera** (solo Apple Silicon verificado): ComfyUI local (127.0.0.1), Z-Image-Turbo bf16 (Apache-2.0), lotes, reintentos, imágenes vacías rechazadas, manifiesto |
| `arvis_estudio/estilos.py` | Estilo por pilar (actualidad, curiosidades, tutoriales, expedientes): consistencia dentro del vídeo, variedad entre vídeos |
| `arvis_estudio/imagenes.py` | Imagen → «escenario» del motor con mapa de profundidad (Depth-Anything-V2-Small, Apache-2.0) para la cámara 2.5D |
| `arvis_expedientes/` (parche v4.2) | `formato.py` 16:9 · `render_largo.py` vídeo largo 8–12 min con capítulos · `qc_largo.py` 20 comprobaciones · `miniatura.py` |
| `arvis_estudio/calidad.py` | Nota 0–100 (guion 20 · gancho 20 · visual 20 · narración 15 · originalidad 15 · edición 10), umbral 85, evidencias obligatorias, topes automáticos |
| `arvis_estudio/cola.py` | Cola SQLite: investigado → guionizado → generando → editando → validando → aprobado → subido → publicado (con prueba en cada paso) |
| `arvis_estudio/youtube.py` | Subida reanudable, duplicados por SHA-256, verificación, registro de privacidad. Sin auditoría de Google: solo privado |
| `arvis_estudio/servicio.py` | Lo lanza launchd cada 5 min: latido, recuperación, órdenes, un paso de la cola |
| `arvis_estudio/repo.py` | Puente con la nube por git: `ordenes/`, `guiones/`, `revision/` (fotogramas para Control de calidad). Nunca vídeos ni claves |
| `launchd/` · `instalar_mac.sh` | Servicios de macOS (sin activar; las rutas se adaptarán a `/Volumes/DADES/arvis` al activar) e instalación para Apple Silicon (no usar en el Mac Intel) |

Pruebas: `python3 -m pytest -q tests/` (ComfyUI y YouTube simulados; el montaje largo con un motor simulado de mismas interfaces).
Las pruebas reales (motor v4 con bpy 4.5.16, Piper, FFmpeg/VideoToolbox, tiempos) se hacen en el Mac antes de activar nada. Documentación: Proyecto ARVIS › `agentes/estudio_audiovisual_mac.md`.
