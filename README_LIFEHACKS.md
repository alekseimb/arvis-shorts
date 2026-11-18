# LIFEHACKS AI · rama `lifehacks`

Unidad de ARVIS que crea, prueba, monta y publica **3 YouTube Shorts diarios de tutoriales prácticos**
(«Pequeñas soluciones inteligentes para problemas de todos los días»). Coste: 0 €. Decisiones de Aleksei (18/11/2026):
3 al día a las 12:00, 17:00 y 21:00 (las series de misterio quedan en pausa), publicación automática desde el primero
si la nota de calidad es ≥ 85, voz `sharvard_m` (Piper es_ES, CC BY 3.0, crédito en la descripción); 20:20: empezar suave, con temas cotidianos y gancho en pregunta.

| Agente | Módulo | Qué hace |
|---|---|---|
| LIFEHACKS RESEARCHER | `arvis_lifehacks/ideas.py` | Rúbrica 1–100 (utilidad 25 · interés 20 · demostrable 20 · retención 15 · originalidad 10 · conversación 10), evidencias obligatorias, antiduplicados, 3 mejores con categorías variadas |
| AI TUTORIAL BUILDER | `arvis_lifehacks/constructor.py` | Revisión estática de seguridad, carpeta aislada `/tmp/lh/<ID>/demo` sin red, pruebas pytest, ejecución real de la demo |
| SHORTS VIDEO CREATOR | `grabar.py` · `montaje.py` · `voz.py` · `musica.py` | Grabación real: Chrome con su interfaz en un escritorio virtual (Xvfb + teclas reales XTest + x11grab, eventos calibrados), páginas con Playwright, editor y terminal con la salida real; animación de atajos; voz Piper; música propia; subtítulos palabra a palabra; 1080×1920 30 fps; versión ≤ 4,6 MB para Make |
| CONTROL DE CALIDAD | `qc.py` + `arvis_estudio/calidad.py` | 24 comprobaciones medidas (incluida «gancho en pregunta») + nota 0–100 con evidencias (umbral 85, topes automáticos) |
| Publicación | `publicar.py` + `tools/publish_media.sh` | Franja libre (≥ 90 min), título, descripción con código y fuentes, etiquetas; subida por Make 8260243 |
| SHORTS PERFORMANCE ANALYST | `analista.py` | Índices por categoría, gancho, duración y franja; multiplicadores para el Researcher (pasos ≤ 0,1, ≥ 3 vídeos); franjas solo con ≥ 10 vídeos |

```bash
pip install --break-system-packages -q piper-tts python-xlib playwright pytest scipy opencv-python-headless pillow numpy
python3 -m arvis_lifehacks.recursos                     # voz y fuentes (GitHub)
python3 -m arvis_lifehacks.producir tutoriales/SH-023/guion.json --out out/SH-023
python3 -m arvis_estudio.calidad out/SH-023/SH-023.json out/SH-023/SH-023_evaluacion.json --stills out/SH-023/stills
python3 -m arvis_lifehacks.publicar franja --ocupadas "19/11/2026 12:00"
python3 -m pytest -q tests/test_lifehacks.py
```
Modelos: `tutoriales/SH-024` (truco de navegador, captura «escritorio» con verificación) y `tutoriales/SH-023` (herramienta Python con pruebas). Panel: `panel/lifehacks_panel.html` (artefacto «ARVIS · LIFEHACKS AI»). Cada tutorial vive en `tutoriales/SH-0NN/`: la herramienta, sus pruebas (`test_*.py`), `preparar_demo.py` (archivos de prueba) y `guion.json`.
Reglas completas: Proyecto ARVIS › `agentes/lifehacks_ai.md`.
