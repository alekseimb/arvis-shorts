"""Recursos visuales con licencia clara y sin claves.

1. Iconos Fluent Emoji de Microsoft (licencia MIT): ~1.600 objetos cotidianos en SVG (limón, esponja, camiseta,
   bombilla, moneda…). Se descargan una vez desde GitHub (la red disponible en las tareas de ARVIS) con un
   clon parcial que trae solo los SVG en color, y se rasterizan con rsvg-convert al tamaño exacto (nítidos a cualquier escala).
2. Aparatos y escenarios dibujados por ARVIS (arvis_vida.props / arvis_vida.fondos): SVG propio.

Pexels, Pixabay y Wikimedia no son accesibles desde el entorno de las tareas (comprobado el 19 y el 20/11/2026):
el motor no depende de ellos. Si algún día lo son (y hay clave gratuita de Aleksei), se pueden añadir como módulo opcional.
"""
import hashlib
import io
import os
import re
import subprocess
import unicodedata

from PIL import Image

CACHE = os.path.expanduser(os.environ.get("ARVIS_VIDA_CACHE", "~/.cache/arvis_vida"))
FLUENT = os.path.join(CACHE, "fluent")
FLUENT_REPO = "https://github.com/microsoft/fluentui-emoji.git"
CREDITO_ICONOS = "Iconos: Fluent Emoji © Microsoft Corporation (licencia MIT)."

# Alias en español → carpeta de Fluent Emoji, con palabras clave para comprobar que la imagen corresponde a lo que se dice
CATALOGO = {
    # cocina y alimentos
    "limon": ("Lemon", "limón limones ácido cítrico"), "lima": ("Lime", "lima cítrico"),
    "sarten": ("Cooking", "sartén freír cocinar huevo"), "olla_comida": ("Pot of food", "olla guiso cocinar comida"),
    "paella": ("Shallow pan of food", "paellera sartén comida"), "tetera": ("Teapot", "tetera té agua hervir"),
    "taza": ("Hot beverage", "taza café caliente bebida"), "sal": ("Salt", "sal salero"), "huevo": ("Egg", "huevo huevos"),
    "pan": ("Bread", "pan barra tostada"), "baguette": ("Baguette bread", "pan barra"), "queso": ("Cheese wedge", "queso"),
    "leche": ("Glass of milk", "leche vaso"), "lechuga": ("Leafy green", "lechuga verdura hojas"), "tomate": ("Tomato", "tomate"),
    "patata": ("Potato", "patata patatas"), "cebolla": ("Onion", "cebolla"), "ajo": ("Garlic", "ajo ajos"),
    "zanahoria": ("Carrot", "zanahoria"), "platano": ("Banana", "plátano plátanos fruta"), "manzana": ("Red apple", "manzana fruta"),
    "fresa": ("Strawberry", "fresa fresas fruta"), "aguacate": ("Avocado", "aguacate"), "pepino": ("Cucumber", "pepino"),
    "arroz": ("Cooked rice", "arroz"), "carne": ("Cut of meat", "carne filete"), "pollo": ("Poultry leg", "pollo muslo carne"),
    "pimiento": ("Bell pepper", "pimiento"), "hierbas": ("Herb", "hierbas perejil"), "miel": ("Honey pot", "miel"),
    "frasco": ("Jar", "bote frasco tarro conserva"), "lata": ("Canned food", "lata conserva"), "cuchara": ("Spoon", "cuchara"),
    "cuchillo": ("Kitchen knife", "cuchillo cortar"), "cubiertos": ("Fork and knife", "cubiertos tenedor cuchillo comer"),
    "plato": ("Fork and knife with plate", "plato comida comer"), "bol": ("Bowl with spoon", "bol cuenco tazón"),
    "vaso": ("Tumbler glass", "vaso agua"), "fiambrera": ("Takeout box", "táper fiambrera sobras comida"),
    "hielo": ("Ice", "hielo frío congelar"), "cubito": ("Ice", "hielo cubitos"),
    # limpieza y casa
    "jabon": ("Soap", "jabón lavar limpiar"), "esponja": ("Sponge", "esponja fregar limpiar"), "cubo": ("Bucket", "cubo fregar agua"),
    "escoba": ("Broom", "escoba barrer limpiar"), "burbujas": ("Bubbles", "burbujas espuma jabón"), "brillos": ("Sparkles", "brillo limpio reluciente"),
    "gota": ("Droplet", "gota agua"), "gotas": ("Sweat droplets", "gotas agua salpicar"), "ducha": ("Shower", "ducha agua"),
    "banera": ("Bathtub", "bañera baño"), "vater": ("Toilet", "váter inodoro baño"), "papel": ("Roll of paper", "papel rollo"),
    "desatascador": ("Plunger", "desatascador atasco"), "espejo": ("Mirror", "espejo"), "botella_crema": ("Lotion bottle", "bote botella producto"),
    "guantes": ("Gloves", "guantes"), "papelera": ("Wastebasket", "papelera basura"), "cesta": ("Basket", "cesta colada ropa"),
    "ventana": ("Window", "ventana ventilar aire"), "puerta": ("Door", "puerta"), "casa": ("House", "casa hogar"),
    "sofa": ("Couch and lamp", "sofá salón lámpara"), "cama": ("Bed", "cama dormitorio"), "silla": ("Chair", "silla"),
    "planta": ("Potted plant", "planta maceta"), "vela": ("Candle", "vela"), "llave": ("Key", "llave"),
    "aviso_quimico": ("Warning", "peligro aviso cuidado nunca"), "calavera": ("Skull and crossbones", "tóxico peligro veneno"),
    "tubo_ensayo": ("Test tube", "químico mezcla producto"),
    # ropa y organización
    "camiseta": ("T-shirt", "camiseta ropa prenda"), "calcetines": ("Socks", "calcetines ropa"), "vaqueros": ("Jeans", "vaqueros pantalón ropa"),
    "vestido": ("Dress", "vestido ropa prenda"), "abrigo": ("Coat", "abrigo ropa"), "camisa_deporte": ("Running shirt", "camiseta deporte ropa"),
    "hilo": ("Thread", "hilo coser"), "ovillo": ("Yarn", "lana ovillo jersey"), "imperdible": ("Safety pin", "imperdible"),
    "tijeras": ("Scissors", "tijeras cortar"), "percha": ("Hook", "percha gancho colgar"), "etiqueta": ("Label", "etiqueta"),
    "caja": ("Package", "caja guardar ordenar"), "archivador": ("Card file box", "caja ordenar organizar"), "bolso": ("Handbag", "bolso"),
    "zapato": ("Mans shoe", "zapato calzado"), "bota": ("Hiking boot", "bota calzado"), "cajon": ("File cabinet", "cajón ordenar"),
    "calendario": ("Spiral calendar", "calendario fecha"), "portapapeles": ("Clipboard", "lista apuntar"),
    # ahorro y energía
    "bombilla": ("Light bulb", "bombilla luz idea energía"), "enchufe_cable": ("Electric plug", "enchufe cable electricidad luz"),
    "rayo": ("High voltage", "electricidad energía luz consumo"), "bateria": ("Battery", "batería"), "bateria_baja": ("Low battery", "batería baja"),
    "moneda": ("Coin", "moneda dinero euros ahorro"), "saco_dinero": ("Money bag", "dinero ahorro euros"),
    "billete_alas": ("Money with wings", "dinero gasto pierdes euros factura"), "billete": ("Euro banknote", "euros dinero billete"),
    "tarjeta": ("Credit card", "tarjeta pago"), "recibo": ("Receipt", "factura recibo ticket"), "cerdo": ("Pig", "cerdo"),
    "grafico_baja": ("Chart decreasing", "baja menos reduce gasto"), "grafico_sube": ("Chart increasing", "sube más aumenta"),
    "carrito": ("Shopping cart", "compra supermercado carro"), "bolsas": ("Shopping bags", "compra bolsas"),
    "termometro_emoji": ("Thermometer", "temperatura grados"), "copo": ("Snowflake", "frío nieve congelar"), "fuego": ("Fire", "fuego calor caliente"),
    "sol": ("Sun", "sol calor luz"), "nube": ("Cloud", "nube"), "viento": ("Wind face", "aire viento"), "hoja": ("Leaf fluttering in wind", "eco ecológico hoja"),
    "trebol": ("Four leaf clover", "suerte"), "reloj": ("Alarm clock", "reloj tiempo minutos"), "temporizador": ("Timer clock", "tiempo minutos temporizador"),
    "cronometro": ("Stopwatch", "tiempo segundos rápido"), "reloj_arena": ("Hourglass not done", "tiempo esperar"),
    # reparaciones
    "martillo": ("Hammer", "martillo"), "llave_inglesa": ("Wrench", "llave inglesa reparar"), "destornillador": ("Screwdriver", "destornillador tornillo"),
    "caja_herramientas": ("Toolbox", "herramientas reparar"), "tuerca": ("Nut and bolt", "tornillo tuerca"), "iman": ("Magnet", "imán"),
    "cinta": ("Adhesive bandage", "tirita cinta"), "linterna": ("Flashlight", "linterna luz"), "escalera": ("Ladder", "escalera"),
    # reacciones y símbolos
    "pensando": ("Thinking face", "piensa duda pregunta"), "sorpresa": ("Exploding head", "sorpresa increíble alucinante"),
    "asombro": ("Astonished face", "sorpresa qué"), "monoculo": ("Face with monocle", "fíjate mira detalle"),
    "estrellas_ojos": ("Star-struck", "genial increíble"), "gafas_sol": ("Smiling face with sunglasses", "fácil genial"),
    "asco": ("Nauseated face", "asco olor mal"), "sudor": ("Grinning face with sweat", "uf problema"), "llorando": ("Loudly crying face", "error mal"),
    "pulgar": ("Thumbs up", "bien perfecto vale"), "pulgar_abajo": ("Thumbs down", "mal error no"), "ok": ("Ok hand", "perfecto"),
    "aplausos": ("Clapping hands", "bien hecho"), "musculo": ("Flexed biceps", "fuerza"), "senalar": ("Backhand index pointing right", "mira esto"),
    "senalar_abajo": ("Backhand index pointing down", "abajo aquí"), "check": ("Check mark button", "bien correcto sí hazlo"),
    "cruz": ("Cross mark", "mal error no nunca"), "prohibido": ("Prohibited", "nunca prohibido no"), "aviso": ("Warning", "cuidado atención aviso"),
    "lupa": ("Magnifying glass tilted right", "mira busca fíjate"), "pregunta": ("Red question mark", "pregunta qué"),
    "exclamacion": ("Red exclamation mark", "atención importante"), "cien": ("Hundred points", "perfecto"), "estrella": ("Glowing star", "mejor brillante"),
    "corazon": ("Red heart", "gusta"), "guardar": ("Floppy disk", "guárdalo guardar"), "bocadillo": ("Speech balloon", "comenta dime"),
    "colision": ("Collision", "golpe choque"), "chispa": ("High voltage", "chispa electricidad"), "ojos": ("Eyes", "mira fíjate"),
}

# Palabras vacías para el contraste imagen ↔ narración
VACIAS = set("""a al algo ante así con como cómo cuando de del desde el ella en entre es esa ese eso esta este esto estos
fue ha hay la las le lo los más me mi mis muy no nos o para pero por que qué se si sí sin sobre son su sus también te tu tus
un una uno unos y ya yo""".split())


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s).lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9ñ ]+", " ", s)


def raices(texto):
    """Raíces de 5 letras de las palabras con contenido (para comparar imagen y narración sin lematizador)."""
    return {w[:5] for w in _norm(texto).split() if w not in VACIAS and len(w) >= 3}


def preparar_fluent():
    """Clon parcial (solo SVG en color) de Fluent Emoji. Idempotente."""
    if os.path.isdir(os.path.join(FLUENT, "assets", "Lemon")):
        return FLUENT
    os.makedirs(CACHE, exist_ok=True)
    subprocess.run(["git", "clone", "-q", "--depth", "1", "--filter=blob:none", "--sparse", FLUENT_REPO, FLUENT], check=True, timeout=600)
    subprocess.run(["git", "-C", FLUENT, "sparse-checkout", "set", "--no-cone", "/assets/*/Color/*.svg",
                    "/assets/*/Default/Color/*.svg", "/LICENSE"], check=True, timeout=900)
    return FLUENT


def ruta_fluent(nombre):
    """nombre: alias del CATALOGO o nombre de carpeta de Fluent («Lemon»). Devuelve la ruta del SVG o None."""
    carpeta = CATALOGO.get(nombre, (nombre, ""))[0]
    base = os.path.join(FLUENT, "assets", carpeta)
    for sub in ("Color", os.path.join("Default", "Color")):
        d = os.path.join(base, sub)
        if os.path.isdir(d):
            svgs = sorted(f for f in os.listdir(d) if f.endswith(".svg"))
            if svgs:
                return os.path.join(d, svgs[0])
    return None


def palabras_clave(nombre):
    if nombre in CATALOGO:
        return CATALOGO[nombre][1] + " " + nombre.replace("_", " ")
    return nombre


def svg_a_png(svg, ancho, alto=None):
    """svg: ruta o texto SVG. Devuelve una Image RGBA (caché en disco por contenido y tamaño)."""
    datos = open(svg, "rb").read() if (isinstance(svg, str) and os.path.exists(svg)) else svg.encode("utf-8")
    h = hashlib.sha1(datos + ("%sx%s" % (ancho, alto)).encode()).hexdigest()[:20]
    dest = os.path.join(CACHE, "png", h + ".png")
    if not os.path.exists(dest):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        cmd = ["rsvg-convert", "-w", str(int(ancho))] + (["-h", str(int(alto))] if alto else []) + ["-f", "png", "-o", dest + ".part"]
        subprocess.run(cmd, input=datos, check=True, timeout=60)
        os.replace(dest + ".part", dest)
    return Image.open(dest).convert("RGBA")


def volumen(img, fuerza=1.0, radio=None):
    """Estilo único ARVIS 5.0: da volumen 3D suave (luz arriba-izquierda, brillo, oclusión en los bordes) a una capa RGBA
    dibujada en plano, para que los aparatos propios casen con los iconos Fluent (que ya tienen volumen).
    Mismo resultado para la misma imagen (determinista)."""
    import numpy as np
    from scipy import ndimage
    a = np.asarray(img.convert("RGBA")).astype(np.float32) / 255.0
    rgb, al = a[..., :3], a[..., 3]
    h, w = al.shape
    r = radio or max(3.0, min(h, w) * 0.045)
    alt = ndimage.gaussian_filter(al, r)
    lum = rgb @ np.array([0.3, 0.59, 0.11], np.float32)
    alt2 = ndimage.gaussian_filter(lum * al, r * 0.35)
    gy, gx = np.gradient(alt + alt2 * 0.3)
    sh = np.clip(-(gx * -0.55 + gy * -0.83) * r * 2.2 * fuerza, -0.55, 0.55)
    spec = np.clip(sh - 0.18, 0, None) * 1.4
    out = (rgb * (1 + np.minimum(sh, 0)[..., None] * 0.9) + (1 - rgb) * np.maximum(sh, 0)[..., None] * 0.55
           + spec[..., None] * 0.25 + np.linspace(0.06, -0.08, h, dtype=np.float32)[:, None, None] * fuerza)
    res = np.dstack([np.clip(out, 0, 1), al])
    return Image.fromarray((res * 255 + 0.5).astype(np.uint8), "RGBA")


def prop_a_png(svg, ancho, alto=None, fuerza=1.0):
    """Capa de un aparato dibujado por ARVIS, rasterizada y con volumen 3D suave (caché en disco)."""
    datos = svg.encode("utf-8")
    h = hashlib.sha1(datos + ("%sx%s v%s" % (ancho, alto, fuerza)).encode()).hexdigest()[:20]
    dest = os.path.join(CACHE, "png3d", h + ".png")
    if not os.path.exists(dest):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        volumen(svg_a_png(svg, ancho, alto), fuerza).save(dest + ".part.png")
        os.replace(dest + ".part.png", dest)
    return Image.open(dest).convert("RGBA")


def icono(nombre, ancho):
    r = ruta_fluent(nombre)
    if not r:
        raise KeyError("Icono no encontrado: %s" % nombre)
    return svg_a_png(r, ancho)


def existe(nombre):
    from . import props
    return nombre in props.PROPS or ruta_fluent(nombre) is not None
