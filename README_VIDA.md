# ARVIS VIDA · rama `vida` · motor de Shorts de lifehacks de la vida real (ARVIS 3.0, 20/11/2026)

Sustituye, para la línea «de la vida» (orden de Aleksei del 19/11/2026), al motor de grabación de pantalla (`arvis_lifehacks`,
que se conserva) y al motor 3D con Blender que nunca llegó a existir. **No depende de Blender, ComfyUI ni GPU**: Python + Pillow +
numpy + OpenCV + FFmpeg en 2 CPU y 7 GB. Un Short de 22–40 s se monta en ~2 min.

| Agente | Módulo | Qué hace |
|---|---|---|
| Investigador de ideas | (agente con búsqueda web) + `arvis_lifehacks/ideas.py` | Problemas cotidianos con solución en fuentes oficiales; rúbrica 1–100 con evidencias; antiduplicados; `demo: "2d"` |
| Guionista | `arvis_vida/guion.py` | Guion JSON: gancho en pregunta → problema → 2-3 pasos → resultado → cierre. Rechaza: sin fuente oficial, cifras sin cita, consejos peligrosos o médicos, títulos repetidos, activos que no existen |
| Motor audiovisual | `arvis_vida/motor.py`, `fondos.py`, `props.py`, `activos.py`, `texto.py` | Escenarios y aparatos dibujados por ARVIS (SVG propio) + iconos Fluent Emoji (MIT); entradas con muelle, trayectorias, capas animadas (tambor que gira, aguja del selector, termómetro, tapa, luz), partículas (vapor, calor, burbujas, monedas, gotas, brillos…), cifras, barras, sellos ✓/✗, flechas |
| Editor | `motor.py` + `sonido.py` + `producir.py` | Cámara virtual (empuje, alejar, paneos, golpes de zoom en palabras), transiciones (barrido con desenfoque, zoom, destello, subida), subtítulos palabra a palabra, voz Piper `sharvard_m`, música y efectos propios con ducking, −14 LUFS, H.264 1080×1920 30 fps, versión ≤ 4,6 MB para Make |
| Control de calidad | `arvis_vida/qc.py` + `retencion.py` + `arvis_estudio/calidad.py` | 22 comprobaciones medidas (decodifica, formato, duración 20–45 s, sonoridad, negros, tramos congelados, silencios, ritmo, subtítulos, estructura, gancho, fuentes, cifras, seguridad, duplicados, imagen↔narración, variedad, novedad visual cada ≤ 3 s, entregables, descripción); retención automática 0–100 (≥ 70); nota 0–100 con evidencias (≥ 85) |
| Publicador | `producir.py` (metadatos) + `tools/publish_media.sh` + Make 8260243 / 8260190 | Rama `media` → Make (guardia antiduplicados) → privado + publishAt en la franja → comprobación con la API |
| Analista | `arvis_lifehacks/analista.py` | Métricas reales (Make 8260190; retención con ARVIS_ANALITICA cuando esté) → pesos del investigador |

Las anclas `"en": "palabra"` sincronizan cada aparición con la narración: la imagen va con lo que se dice.
Si un activo o una escena falla, el guion se rechaza ANTES de montar (no se sube nada a medias); la investigación y los guiones siguen.

```bash
pip install --break-system-packages -q -r requirements-vida.txt
python3 -m arvis_vida.guion guiones_vida/SH-027/guion.json                      # validar
python3 -m arvis_vida.producir guiones_vida/SH-027/guion.json --out out/SH-027 --publicados titulos.json
python3 -m arvis_estudio.calidad out/SH-027/SH-027.json out/SH-027/SH-027_evaluacion.json --stills out/SH-027/stills
python3 -m pytest -q tests/test_vida.py
```

Recursos y licencias (coste 0 €): voz Piper es_ES sharvard (CC BY 3.0, crédito en la descripción) · iconos Fluent Emoji de
Microsoft (MIT, crédito en la descripción) · fuentes Google Fonts (OFL) · escenarios, aparatos, música y efectos creados por ARVIS.
Pexels, Pixabay y Wikimedia no son accesibles desde el entorno de las tareas (comprobado el 19 y el 20/11/2026); Hugging Face
tampoco: no hay IA de imagen gratuita utilizable. Si algún día lo hay, entra como módulo opcional, nunca como dependencia.

**ARVIS 3.1 (22/11/2026) · operación eficiente:** `python3 -m arvis_vida.ops plan` decide qué toca en cada ejecución con el
estado persistente `estado/lh_estado.json`; `arvis_vida.sonda` es el QC fase 1 (geométrico, sin mirar imágenes) y deja la
lista corta de fotogramas para la revisión visual. Detalle: `docs_vida/OPERACION_3_1.md`.

Modelo de guion: `guiones_vida/SH-027/guion.json` (lavadora, Comunidad de Madrid). Reglas: Proyecto ARVIS › `agentes/lifehacks_ai.md` (v2.0).
