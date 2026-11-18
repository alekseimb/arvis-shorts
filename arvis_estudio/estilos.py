"""Biblias de estilo por pilar: consistencia dentro de un vídeo y variedad entre vídeos.

Dentro de un vídeo todas las imágenes comparten estilo, paleta y familia de semillas.
Entre vídeos se rota la variante (óptica, luz, paleta) para no repetir la misma plantilla:
se elige la variante menos usada en los últimos vídeos del mismo pilar.
"""
import hashlib

PILARES = {
    "actualidad": {
        "base": "editorial documentary photograph, realistic, natural light, accurate details, no text, no logos, no watermark",
        "variantes": [
            {"id": "act_35mm_dia", "luz": "soft overcast daylight", "optica": "35mm lens, eye level", "paleta": "neutral muted colors", "grade": "warm"},
            {"id": "act_tele_noche", "luz": "night city lights, sodium and neon", "optica": "85mm telephoto, shallow depth of field", "paleta": "teal and amber", "grade": "night"},
            {"id": "act_aereo", "luz": "golden hour sunlight", "optica": "high aerial view, wide angle", "paleta": "warm earth tones", "grade": "warm"},
            {"id": "act_interior", "luz": "window light, quiet interior", "optica": "50mm, medium shot", "paleta": "desaturated cool tones", "grade": "none"},
        ],
    },
    "curiosidades": {
        "base": "cinematic film still, highly detailed, dramatic composition, realistic textures, no text, no logos, no watermark",
        "variantes": [
            {"id": "cur_epico", "luz": "volumetric light rays, atmospheric haze", "optica": "anamorphic wide shot", "paleta": "deep blues and gold", "grade": "night"},
            {"id": "cur_macro", "luz": "studio rim light, black background", "optica": "macro close-up", "paleta": "high contrast, vivid", "grade": "none"},
            {"id": "cur_historico", "luz": "candle and lantern light", "optica": "35mm period film look", "paleta": "sepia and ochre", "grade": "archive"},
            {"id": "cur_cosmos", "luz": "starlight and nebula glow", "optica": "ultra wide, deep space", "paleta": "violet, cyan and black", "grade": "night"},
        ],
    },
    "tutoriales": {
        # nunca capturas inventadas de apps reales: objetos y escenas cotidianas, ilustración limpia
        "base": "clean modern 3D illustration, soft studio lighting, minimal background, friendly, no text, no logos, no user interface, no watermark",
        "variantes": [
            {"id": "tut_pastel", "luz": "soft diffuse light", "optica": "isometric view", "paleta": "pastel mint and coral", "grade": "none"},
            {"id": "tut_mesa", "luz": "warm desk lamp light", "optica": "top-down flat lay", "paleta": "wood and white", "grade": "warm"},
            {"id": "tut_azul", "luz": "bright clean light", "optica": "3/4 product view", "paleta": "blue and white", "grade": "none"},
        ],
    },
    "expedientes": {
        "base": "dark cinematic recreation, realistic, moody, film grain, no text, no logos, no watermark",
        "variantes": [
            {"id": "exp_niebla", "luz": "moonlight through fog", "optica": "wide establishing shot", "paleta": "cold blue-grey", "grade": "night"},
            {"id": "exp_archivo", "luz": "single desk lamp", "optica": "close-up on old documents", "paleta": "sepia", "grade": "archive"},
        ],
    },
}


def elegir_variante(pilar, usadas_recientes):
    """usadas_recientes: ids de variante de los últimos vídeos del pilar (más reciente al final)."""
    vs = PILARES[pilar]["variantes"]
    cuenta = {v["id"]: 0 for v in vs}
    for k, vid in enumerate(usadas_recientes[-12:]):
        if vid in cuenta:
            cuenta[vid] += 1 + k / 100.0      # a igualdad, evita la más reciente
    return min(vs, key=lambda v: cuenta[v["id"]])


def prompt(pilar, variante, escena_prompt, formato="16:9"):
    b = PILARES[pilar]["base"]
    encuadre = "vertical composition, subject centered" if formato == "9:16" else "horizontal widescreen composition, rule of thirds"
    return "%s. %s, %s, %s, %s, %s." % (escena_prompt.strip().rstrip("."), variante["luz"], variante["optica"], variante["paleta"], encuadre, b)


def semilla(clave_video, k):
    """Familia de semillas estable por vídeo (consistencia) y distinta entre vídeos (variedad)."""
    base = int(hashlib.sha256(clave_video.encode()).hexdigest()[:12], 16)
    return (base + 7919 * k) % (2 ** 48)
