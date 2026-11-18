# Registro de cambios

## 2026-11-18 · Fase 1 (rutina «Arvis Yotube»)
- Añadido: submódulo Open-Higgsfield @7d06c70, paquete `arvis_av` (guardia de coste, cliente API, generador local FFmpeg, QC técnico, registro), configuración de proveedores (todos desactivados), registro de herramientas gratuitas, tests, CI de validación.
- No modificado: escenarios de Make, almacén 238309, hojas, Notion (salvo una línea en PANEL ARVIS › REGISTRO), tareas programadas, rama `media`.
- Copia de seguridad: no hacía falta (no se ha modificado nada existente; todo es aditivo en una rama nueva).

## 2026-11-18 · Fase 3a (rutina «Arvis Yotube», 2.ª ejecución)
- Incorporado el trabajo de la Fase 1 (rama `claude/cool-sagan-fqcwd3`) sin cambios.
- Añadido: `arvis_av/narrador.py` (Piper + voz davefx desde GitHub Releases), `arvis_av/productor_short.py` (Short 9:16 completo y local), comandos `short` y `payload` en el CLI, guion `guiones/SH-TEST-001.json`, `tests/test_productor.py`.
- Producido en local SH-TEST-001 (tutorial: verificación en dos pasos de WhatsApp). QC técnico 11/11 correcto. El vídeo **no** se ha subido a GitHub ni a YouTube.
- No modificado: Make (solo se leyó el escenario 8260243), almacén 238309, hojas, Notion, tareas programadas, rama `media`.
