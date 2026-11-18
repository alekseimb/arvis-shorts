# Auditoría · Departamento YouTube de ARVIS + Open-Higgsfield
**Fecha:** 18/11/2026 · **Rutina:** «Arvis Yotube» · **Coste de esta fase:** 0 €

Todo lo que aparece aquí se ha comprobado con las herramientas conectadas (Make, GitHub, Notion, Google Sheets) o ejecutando el software. Lo que no se pudo comprobar se indica.

## 1. ARVIS actual (lo que ya funciona — no se ha tocado)

| Pieza | Estado comprobado |
|---|---|
| Canal | Maestro · @el_maestro_777 · `UC01n95p_Zd8vaWHl9HV-vxQ` (almacén Make 238309, clave `canal`) |
| Producción | Tarea programada de Claude «ARVIS Shorts» (`trig_01KbUGichiCwXW57Re1A56jt`, 00:47/06:47/12:47) con motor v4 (Blender bpy + Piper davefx_doc + FFmpeg, QC 21 + puntuación ≥85). 3 Shorts/día autorizados el 14/11/2026. |
| Supervisión | «ARVIS Supervisor» (`trig_01PqvdddTA64eUdUxYqz1pgi`) y revisión semanal (`trig_019fj9UFyLYizCx5KbzY6DFY`). |
| Make (eu1, equipo 3393416) | `8260243` Subir Short (on-demand, antiduplicados por clave, privado por defecto, `publishAt`) · `8260190` consultas API YouTube · almacén `238309` (75 registros, 23 KB de 1 MB). Sin webhooks ni planificación en Make. Conexión YouTube `12504455`. |
| Publicados | SH-001…SH-022 subidos; 18 confirmados públicos por la API el 16/11 (5.497 vistas de canal, 7 suscriptores). |
| Datos | Hoja «videos» (SHORTS, TEMAS, CONFIG_YOUTUBE, CALIDAD, METRICAS…), PANEL ARVIS (TAREAS, REGISTRO), Notion ARVIS (Proyectos, Agentes, Automatizaciones, Decisiones). |
| GitHub `alekseimb/arvis-shorts` | Solo rama `media` (puente temporal de URL pública para que Make descargue el MP4; se vacía tras subir). **El código del motor no está versionado en GitHub**: vive en el Proyecto ARVIS de Claude y en blobs del Command Center. |

### Hallazgos
1. **El motor no está en Git.** Riesgo de pérdida (ya ocurrió el 30/10: «se habían perdido los MP4 y el motor»). Recomendación: versionar `motor_v4` en este repo (necesita que Aleksei lo suba o autorice copiarlo desde el Proyecto; esta rutina no tiene acceso a los ficheros del Proyecto).
2. **`containsSyntheticMedia: false` fijo** en el escenario 8260243. Hoy los Shorts usan voz sintética + gráficos (YouTube no exige la etiqueta para animaciones/gráficos claramente no realistas). Si se añaden imágenes o clips generados por IA fotorrealistas, **debe pasar a `true`**. Propuesta: convertirlo en un campo de entrada del escenario. No modificado (escenario en producción).
3. **Autonomía real:** la producción depende de *tareas programadas de Claude* que se ejecutan en la nube (no hace falta tener Claude abierto), pero el render ocurre en contenedores efímeros de esas sesiones. No existe un «motor local» siempre encendido. Make solo sube/consulta bajo demanda.
4. **Conflicto con el nuevo objetivo:** CONFIG_YOUTUBE fija 3 Shorts/día. La misión pide 1 largo + 2 Shorts. Cambiarlo es decisión de Aleksei → no se ha tocado.
5. Agentes de YouTube en Notion: Agente 3 (Investigación), Agente 4 (Producción), Agente 5 (Noticias) + roles E0–E7 del texto v6. Ver mapa en `PLAN_TECNICO.md`.

## 2. Open-Higgsfield (TechBeme/open-higgsfield @ `7d06c70`, 16/11/2026)

| Aspecto | Resultado |
|---|---|
| Qué es | Estudio web Next.js 16 / React 19 / TypeScript para **generar imagen y vídeo a través de proveedores externos** (BYOK). No incluye modelos propios ni ejecución local de modelos. |
| Licencia | MIT ✅ (uso comercial permitido) |
| Proveedores | Google AI Studio, Google Vertex AI, Vercel AI Gateway, ToAPIs, Magnific, Runware. Catálogo: **346 entradas de imagen + 322 de vídeo** (comprobado vía `/api/catalog`). |
| API interna | `/api/health`, `/api/ready`, `/api/providers`, `/api/catalog`, `/api/models`, `/api/image-models`, `POST /api/generate-image`, `POST /api/generate`, `/api/tasks/{id}`, `/api/download/{id}`, `/api/events/{id}` (SSE). Multipart con `model_id` = `<proveedor>__<modelo>`. |
| Ejecución local | `npm ci` + `next dev` en 127.0.0.1:3000, perfil `single-process`, almacenamiento `local`. **Probado y funcionando** (health/ready OK, almacén de tareas disponible). |
| Seguridad | Credenciales solo en servidor, cifradas con `PROVIDER_CONFIG_ENCRYPTION_KEY`; sin login (solo loopback); interruptor `GENERATION_ENABLED`; un único intento por envío de pago (no reintenta cobros). La build avisa de una vulnerabilidad conocida en Next.js 16.4.3 → actualizar antes de exponerlo fuera de loopback (aquí solo escucha en 127.0.0.1). |
| Dependencias | Node 22.23.4+, ~700 MB de `node_modules`. Opcional: PostgreSQL/Neon, Vercel Blob/S3. |
| **Generación gratuita** | **Ninguna verificada.** Todos los proveedores cobran por imagen/vídeo o solo dan créditos de prueba únicos. Prueba real: `POST /api/generate-image` con Gemini 2.5 Flash Image → `ERR_GEMINI_API_KEY_NOT_CONFIGURED`; `/api/image-models` y `/api/models` → 0 modelos utilizables. |

**Conclusión honesta:** Open-Higgsfield es software libre, pero **no da generación gratis**. Queda integrado como *pasarela opcional* con todos los proveedores desactivados por la guardia de coste. Con 0 € la generación visual real sigue siendo local (FFmpeg/Blender, y opcionalmente Stable Diffusion Turbo en CPU — Fase 2).

## 3. Prueba real de esta fase
- Open-Higgsfield instalado y arrancado en local → `ready: true`.
- Intento de generación → bloqueado por la guardia antes de llegar a ningún proveedor (y la propia API lo rechaza por falta de clave). **0 € gastados.**
- Motor local FFmpeg: imagen 1080×1920 + clip animado de 4 s en 2 s de CPU; QC técnico detecta correctamente que no vale como Short (4 s, sin audio). Anotado en `produccion/registro.jsonl`.
- No se ha subido nada a YouTube ni modificado Make, la hoja ni las tareas existentes.
