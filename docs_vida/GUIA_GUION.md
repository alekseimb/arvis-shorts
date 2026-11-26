# Guía del guion de ARVIS VIDA (para el GUIONISTA: sesión de creación en el chat o tarea programada)

## ARVIS LIFEHACKS 5.0 (26/11/2026) — manda sobre lo de abajo
- **El tema lo elige Aleksei.** Nunca se escribe un guion sobre un tema que él no haya pedido (`ops tema` lo registra como T-0NN; pon `"tema": "T-0NN"` en el guion).
- **Duración 20–35 s** (ideal 24–32). El QC falla por encima de 35,5 s.
- **Estructura**: gancho inmediato (pregunta ≤ 9 palabras) → problema → explicación sencilla (en `problema` o en el 1.er paso) → demostración visual (`tutorial` × 2–3) → resultado o recompensa → cierre breve (`cta`). Se entiende sin contexto previo.
- **Enfoque** (`"enfoque"` en el guion; nunca el mismo que el vídeo anterior): curiosidad · sorpresa · error común · comparación · antes y después · demostración · problema y solución · consejo práctico.
- **Identidad visual única («volumen 3D suave»)**: los aparatos de ARVIS ya salen con luces, brillo y sombras como los iconos Fluent, y el escenario va desenfocado detrás. Para que se vea profesional:
  - Un **objeto protagonista grande** por escena: `tam` ≥ 0,42 (ideal 0,50–0,65), centrado en x ≈ 0,5 y **apoyado**: su base en la encimera o el suelo (y ≈ 0,46–0,56 según su altura). El validador avisa si es más pequeño.
  - Iconos secundarios pequeños (`tam` ≤ 0,18) **a los lados del protagonista**, sin taparlo ni taparse (la sonda lo mide).
  - **Nunca una escena solo con textos** (pantalla vacía): siempre un objeto, una cifra que cuenta o una barra.
  - Las partículas que salen de un aparato se colocan con `"ancla": "grifo"` (van a la boca del caño aunque cambie el tamaño o la posición del grifo).
  - `grifo` es ahora un **lavabo con grifo monomando**: capa `palanca` ({"tipo": "angulo", "de": 0, "a": 25, "en": "cierra", "dur": 0.6} = cerrar) y, con `"estado": {"agua": true}`, capa `chorro` ({"de": 1, "a": 0, "en": "cierra"} = se corta el agua).

Modelo completo y probado: `guiones_vida/SH-027/guion.json` (QC 22/22, retención 94, CALIDAD 86,8). Cópialo y cámbialo.

## Campos de primer nivel
`id` (SH-0NN) · `numero` (Nº de la serie lifehacks) · `idea` (IDEA-0NN) · `categoria` (cocina · limpieza · ahorro · organizacion · ropa · reparaciones · cotidiano · errores) ·
`gancho_tecnica` · `variante` (0–2: cambia la paleta de los escenarios; alterna entre vídeos) · `voice` (la de CONFIG_YOUTUBE › Voz; opciones «más divertidas» en arvis_lifehacks/voz.py › PRESETS, pendientes de que Aleksei elija; «voz» en una escena = otra voz para esa escena, p. ej. un dúo; usa también «¡…!» y alguna interjección como «¡Ojo!» para dar vida a la voz) · `musica` ({"semilla": 0–2, "nivel_db": -19}) ·
`title` (≤ 100 caracteres, en pregunta, concreto, sin engañar) · `description` · `hashtags` · `tags` · `categoryId` ("26") ·
`sources` (URLs oficiales o primarias, ver `guion.DOMINIOS_FIABLES`) · `hechos` ([{dato, cita LITERAL, url, leido: dd/mm/aaaa}]).
**Cada cifra que se diga o se escriba en pantalla tiene que aparecer en alguna `cita`** (si no, el guion se rechaza).

## Escenas (en este orden)
1. `gancho` — pregunta de ≤ 9 palabras (≤ 2,5 s) que termina en «?»; `titulo` grande; el objeto principal ya en pantalla (`"en": -0.14`) y `"titulo_en": -0.12`.
2. `problema` — el dato que sorprende (si hay cifra, en un `texto` grande o una `barra`) antes de los 3 s.
3. `tutorial` × 2 o 3 — `"paso": 1, 2…`; un gesto por paso; `titulo` corto con la palabra clave en `resaltar`.
4. `resultado` — qué se consigue (sin prometer euros que la fuente no da).
5. `cta` — «Guárdalo… y sígueme: un truco de casa cada día.» (≤ 4,6 s de voz).
Duración total 20–35 s (ideal 24–32; ARVIS 5.0). 2,6–3,6 palabras/s.

## Escena
`beat` · `say` (narración; las cifras en dígitos) · `fondo` (cocina · lavadero · bano · salon · dormitorio · despensa · estudio) · `variante_fondo` (0–2) ·
`camara` (empuje · alejar · izq · der · subir · bajar · fija) · `foco` [x, y] · `golpes` [palabras: zoom rápido] ·
`transicion` (barrido · zoom · destello · subir · fundido · corte; no la uses igual dos veces seguidas) · `titulo` ("LÍNEA 1\nLÍNEA 2") · `resaltar` [palabras] ·
`titulo_y` (0.125 por defecto en el gancho, 0.150 el resto) · `chip` (para cambiar el rótulo de arriba a la derecha) · `sfx` [[tipo, palabra]] (whoosh, pop, ding, monedas, burbujas, error, exito, tic, salpicadura, sube, golpe).
Regla de variedad (QC): ≥ 3 movimientos de cámara y ≥ 2 transiciones distintas; nunca dos escenas seguidas con el mismo fondo + variante + cámara.

## Elementos (coordenadas en fracción del fotograma 1080×1920)
Zonas: cabecera 0–0,10 · título 0,12–0,28 · **objetos 0,30–0,64** · subtítulos 0,69–0,74 (no pongas nada ahí) · por debajo de 0,76 solo decorado (la interfaz de YouTube lo tapa).
Por la derecha, entre y = 0,50 y 0,90, están los botones de YouTube: deja x ≤ 0,86.
Todos admiten: `x`, `y`, `tam` (ancho en fracción de 1080), `en` (palabra de la narración o segundos desde el inicio de la escena; «agua#2» = 2.ª vez),
`sale_en`, `entrada` (pop · caer · subir · izq · der · zoom · fade), `anim` (flotar · latir · balancear · vibrar · girar · respirar · ninguna),
`mover` [{"a": [x, y], "tam": t, "en": palabra, "dur": 0.5}].
- `{"activo": "<nombre>"}` — aparato propio o icono:
  - Aparatos (con capas animables en `capas`): `lavadora` (capa `tambor`: {"girar": grados/s}; `estado`: pantalla, eco) · `nevera` (estado: pantalla, pantalla2) ·
    `microondas` (capa `luz`: {"de": 0, "a": 1, "en": …} o {"pulso": 1.5}) · `horno` (capa `luz`) · `placa` (capas `zona1`, `zona2`: {"de": 1, "a": 0.2, "en", "dur"}) ·
    `olla` (capa `tapa`: {"de": [0, -90], "a": [0, 0], "en": "tapa"} (no más de −100: se recorta)) · `termometro` (capa `columna`: {"de": 0.2, "a": 0.9, "en", "dur"}) ·
    `dial` (estado: etiquetas; capa `aguja`: {"de": "90°", "a": "ECO", "en", "dur"}) · `grifo` (lavabo con grifo; capas `palanca` y `chorro`, ver arriba) · `enchufe` (capa `clavija`: {"de": [0, 0], "a": [0, 160]}) · `hucha` (cerdito con ranura; capa `moneda`: {"de": [0, -20], "a": [0, 50], "en": …} para que la moneda entre; para el ahorro, mejor que `cerdo`).
  - Iconos Fluent Emoji (MIT): alias del `CATALOGO` de `arvis_vida/activos.py` (limon, jabon, esponja, cubo, escoba, burbujas, brillos, gota, camiseta, calcetines,
    vaqueros, bombilla, moneda, saco_dinero (lleva «$»: evítalo), billete_alas, recibo, copo, fuego, hielo, reloj, check, cruz, pensando, sorpresa, guardar…) o el nombre de carpeta
    en inglés de Fluent («Frying pan»). Comprueba con `python3 -c "from arvis_vida import activos; print(activos.existe('X'))"`.
- `{"tipo": "texto", "texto": "80–85 %", "px": 210, "color": "aviso"}` — cifras y rótulos grandes (`fondo: "pastilla"`, `color_fondo` para etiquetas).
- `{"tipo": "contador", "desde": 0, "hasta": 60, "formato": "{v} %", "px": 220}` — cifra que cuenta (suena «tic»).
- `{"tipo": "barra", "etiqueta": "…", "valor": 0.85, "texto_valor": "80–85 %", "color": "rojo", "ancho": 0.8}`.
- `{"tipo": "sello", "simbolo": "check" | "cruz" | "prohibido"}` — sello con golpe y sonido (éxito / error).
- `{"tipo": "particulas", "clase": "vapor | calor | burbujas | monedas | gotas | nieve | brillos | billetes | hojas | hielo | fuego | rayos", "ancho", "alto", "densidad", "vida", "hasta"}`.
- `{"tipo": "flecha", "de": [x, y], "a": [x, y], "curva": 0.25, "color": "lima"}`.
Cada escena necesita al menos una novedad visual cada ≤ 3 s (ancla elementos a palabras repartidas por la frase).
Imagen = narración: en cada escena, al menos un objeto o rótulo tiene que nombrar lo que se dice (el QC lo comprueba por palabras clave).

## Antes de montar
`python3 -m arvis_vida.guion guiones_vida/SH-0NN/guion.json --publicados titulos.json` → sin errores. Después `python3 -m arvis_vida.producir …`.
Mira SIEMPRE los fotogramas de `stills/` (Read) antes de evaluar: textos que se tapan, objetos cortados o fuera de zona → corrige posiciones y vuelve a montar.
Subtítulos (desde el 25/11/2026): el motor ya no parte «18 y 20 grados», «40 %» ni «Comunidad de Madrid»; «guardar» es un disquete; el título del gancho se ve entero en el primer fotograma.
