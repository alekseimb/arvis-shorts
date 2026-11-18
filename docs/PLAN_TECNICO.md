# Plan técnico · Integración Open-Higgsfield + producción diaria (1 largo + 2 Shorts)

Principio: **ampliar lo que ya funciona, no duplicarlo.** La tarea «ARVIS Shorts», el motor v4, los escenarios de Make 8260243/8260190 y el almacén 238309 siguen siendo las piezas centrales.

## Arquitectura propuesta

```
Tarea programada Claude (ARVIS Shorts, ya existe)  ──►  motor v4 (Blender/Piper/FFmpeg)
        │                                                  │   ▲
        │                                                  │   └─ arvis_av (este repo):
        │                                                  │        · guardia_coste  (0 € por defecto)
        │                                                  │        · higgsfield_client (API Open-Higgsfield, opcional)
        │                                                  │        · generador_local (FFmpeg) · qc · registro
        ▼                                                  ▼
 Hoja videos / PANEL ARVIS / Notion          MP4 → URL temporal (rama media) → Make 8260243 → YouTube
                                                               └─ resultado → almacén 238309 → verificación con 8260190
```

## Mapa de agentes (sin duplicar)

| Rol pedido | Quién lo hace hoy | Cambio |
|---|---|---|
| 1 Director audiovisual | E0 Head of Content (tarea ARVIS Shorts) | Añadir planificación del vídeo largo |
| 2 Investigador | Agente 3 + Agente 5 (E1 Trend Researcher) | — |
| 3 Guionista | E2/E3 del texto v6 | Plantilla de guion largo (8–12 min, capítulos) |
| 4 Director creativo | Storyboard del motor v4 | Campo `prompt_visual` por escena |
| 5 Generador audiovisual | **Nuevo:** `arvis_av` (Open-Higgsfield si hay proveedor autorizado; si no, FFmpeg/Blender local) | Este repo |
| 6 Narrador | Piper davefx_doc | — |
| 7 Editor | motor v4 (FFmpeg) | Montaje 16:9 largo |
| 8 Control de calidad | QC 21 + puntuación ≥85 | `arvis_av.qc` añade perfil `largo`, silencios, congelados, SRT |
| 9 SEO | Agente 4 | — |
| 10 Publicador | Make 8260243 | Campo `containsSyntheticMedia` + miniatura (`thumbnails.set` vía 8260190) |
| 11 Analista | Supervisor + revisión semanal | — |

## Fases

| Fase | Contenido | Estado |
|---|---|---|
| 1 | Auditoría, Open-Higgsfield instalado y probado, guardia de coste, registro de herramientas gratuitas, QC técnico, registro de producción, CI ligera | **Hecho 18/11/2026** |
| 2 | Generador de imágenes gratuito local (SD-Turbo en CPU) como «proveedor local»; medir tiempo real por imagen. Requiere confirmar licencia del modelo para canal monetizado. | Pendiente de decisión |
| 3a | Short completo 100 % local con `arvis_av.productor_short` (Piper davefx + Pillow + FFmpeg + música propia) → QC | **Hecho 18/11/2026** · SH-TEST-001, 33,5 s, QC 11/11, 49 s de render, 0 € |
| 3b | Subida **en privado** con Make 8260243 → verificación por API 8260190 | **Bloqueada:** falta URL pública del MP4. El puente es la rama `media` y esta rutina solo puede hacer push a su rama de trabajo. Necesita permiso explícito para usar `media` |
| 4 | Vídeo largo 16:9 de prueba (8–12 min, capítulos, subtítulos, miniatura) → subida privada | Pendiente |
| 5 | Cambiar CONFIG_YOUTUBE a 1 largo + 2 Shorts y activar público | **Solo con autorización explícita de Aleksei** |

## Decisiones que necesita Aleksei
1. ¿Sustituir «3 Shorts/día» por «1 largo + 2 Shorts/día»? (hoy hay 3 Shorts autorizados).
2. ¿Copiar el motor v4 del Proyecto ARVIS a este repo para versionarlo?
3. ¿Probar SD-Turbo local (gratis, lento en CPU) como generador de imágenes?
4. ¿Hacer `containsSyntheticMedia` configurable en el escenario 8260243?
5. Para autonomía sin Claude: ¿hay un PC/servidor siempre encendido (o VM gratuita) donde ejecutar el motor? Si no, la producción sigue dependiendo de las tareas programadas de Claude (que sí corren sin tener Claude abierto).

## Límites a 0 €
- Ningún proveedor de Open-Higgsfield es gratuito de forma sostenida → desactivados (`config/proveedores_open_higgsfield.json`).
- Vídeo generativo local requiere GPU (≥12 GB VRAM): no viable aquí.
- GitHub Actions solo valida (tests, JSON, secretos); nunca renderiza.
