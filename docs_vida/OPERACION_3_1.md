# ARVIS 3.1 · operación eficiente de LIFEHACKS (22/11/2026)

Objetivo: las mismas 3 ejecuciones diarias (01:47, 08:47, 14:47), el mismo objetivo de 3 Shorts al día y la misma
protección (QC 22/22 + nota ≥ 85), con mucho menos contexto por ejecución. Python hace lo mecánico; Claude decide lo
creativo y revisa la calidad. Las hojas de Google siguen siendo la fuente de verdad.

## Modos (los decide `python3 -m arvis_vida.ops plan`)
| Modo | Cuándo | Qué hace | Qué NO hace |
|---|---|---|---|
| A · Supervisión | siempre | lee 3 rangos pequeños (SHORTS A y U de las filas de LIFEHACKS, CONFIG A1:B45); solo si hay franjas vencidas, 1 consulta a Make con la llamada exacta que da el plan; Make y almacén solo a las 01:47 o tras un error | no lee SHORTS A:U, IDEAS_LH, OPERACIONES ni documentos; no investiga, no monta, no prueba el motor, no prepara recursos |
| B · Métricas | 01:47, una vez al día | 1 consulta (metricas-lh) → `ops metricas` calcula filas de METRICAS, SHORTS K:O (con null = no tocar) y el analista | no analiza vídeos uno a uno; no cambia pesos con < 3 vídeos por categoría |
| C · Producción | si hay franja libre (≥ 90 min, ≤ 30 h) | 1 Short como máximo: entorno idempotente, idea con fuentes en caché (≤ 14 días), guion, sonda sin vídeo, montaje, QC visual en subagente, publicación | no investiga si hay ≥ 3 ideas «Elegida»; no relee fuentes válidas; no repite pytest si el motor no cambió |

## Estado persistente
`estado/lh_estado.json` (en git, rama `vida`; público: sin IDs de hojas ni datos personales): Shorts (fila, ID de
YouTube, franja, fase, categoría, idea, Nº, nota, intentos), ideas (fila, estado, puntuación, fuentes, fecha de lectura,
citas literales), última medición por vídeo, pesos del analista, revisión de Make, huella del motor probada, errores
(resumidos, últimos 10), últimas 9 ejecuciones, filas de SALUD y CONFIG, títulos ya usados. `ops anotar` fusiona cambios,
`ops guardar` hace commit y push solo si hay algo nuevo. Si el estado y las hojas no coinciden, mandan las hojas.

## QC en dos fases
1. **Sonda** (`arvis_vida.sonda`, local, sin mirar imágenes): recorre la composición real cada 0,25 s y detecta objetos
   bajo los subtítulos o el rótulo, cortados por el borde, sobre la cabecera, que se tapan entre sí, flechas sobre textos y
   mitades o escenas vacías. Se usa antes de montar (`--sin-imagenes`, ~10 s) y después de cada montaje (`producir.py`, sobre la
   misma toma de voz). Guarda solo los fotogramas sospechosos (`stills/zz_s…`) y 2–3 hojas de contactos (`stills/zz_hoja_N.jpg`,
   un fotograma cada 1,5 s).
2. **Revisión visual** (Claude, en un subagente): solo la lista `revisar` de `<SH>_sonda.json` (representativos del motor +
   hojas + sospechosos, ≤ 20 imágenes) → evaluación con evidencias → `arvis_estudio.calidad` (≥ 85). La sonda avisa; nunca aprueba.
   Probada con los 6 guiones de la vida: encontró defectos reales que se habían publicado (SH-031 «ÚSALA BIEN» bajo los
   subtítulos hacia 8 s; SH-030 portátil bajo el rótulo hacia 16 s; SH-028 barra sobre los subtítulos hacia 4,5 s).

## Presupuesto interno (topes de operaciones, no de tokens)
Claude no permite fijar un límite real de tokens. `ops plan` da topes contables por modo (llamadas, consultas a Make,
montajes, sondas, imágenes, lecturas web). Al llegar a uno: parar lo no esencial, guardar estado, nunca dejar una subida a
medias, anotar lo pendiente y seguir en la siguiente ejecución.

## Pruebas
`tests/test_ops.py` (plan, franjas, caché de fuentes, métricas, UTC) y `tests/test_sonda.py` (detecta el defecto real de
SH-031). `ops entorno` solo las ejecuta si cambia la huella del motor (`git ls-files -s` de arvis_vida, arvis_lifehacks,
calidad.py, pruebas y requisitos).
