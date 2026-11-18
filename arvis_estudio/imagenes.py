"""De guion con escenas «image» a guion listo para el motor v4.

Para cada escena {"visual": {"type": "image", "prompt": "...", "move": ..., "fx": [...]}}:
  1. genera la imagen con ComfyUI (lote, reintentos, manifiesto),
  2. estima su profundidad (Depth-Anything-V2-Small, Apache-2.0; si no está, profundidad aproximada),
  3. la guarda como «escenario» del motor (<id>.png, <id>_depth.png 16 bits, <id>.json),
  4. reescribe la escena como {"type": "plate", "plate": <id>} para que el motor la anime en 2.5D
     (zoom, travelling, inclinación, paralaje por profundidad, niebla, partículas, luz).
El motor v4 no se modifica: usa su propia cámara 2.5D sobre estas imágenes.
"""
import copy
import json
from pathlib import Path

import cv2
import numpy as np

from . import comfy as CF
from . import estilos

_DEPTH = None


def profundidad(img_rgb):
    """Devuelve profundidad 0..1 (0 = cerca, 1 = lejos) y el método usado."""
    global _DEPTH
    try:
        if _DEPTH is None:
            import torch
            from transformers import pipeline
            dev = "mps" if torch.backends.mps.is_available() else "cpu"
            _DEPTH = pipeline("depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf", device=dev)
        from PIL import Image
        out = _DEPTH(Image.fromarray(img_rgb))
        inv = np.asarray(out["predicted_depth"].squeeze().cpu().numpy(), np.float32)   # mayor = más cerca
        inv = cv2.resize(inv, (img_rgb.shape[1], img_rgb.shape[0]), interpolation=cv2.INTER_CUBIC)
        lo, hi = np.percentile(inv, 1), np.percentile(inv, 99)
        n = np.clip((inv - lo) / max(1e-6, hi - lo), 0, 1)
        return 1.0 - n, "depth-anything-v2-small"
    except Exception:
        return profundidad_aproximada(img_rgb), "aproximada"


def profundidad_aproximada(img_rgb):
    """Sin modelo: arriba lejos, abajo cerca, y lo nítido/contrastado algo más cerca. Suave para no romper la imagen."""
    h, w = img_rgb.shape[:2]
    y = np.linspace(0, 1, h, dtype=np.float32)[:, None] * np.ones((1, w), np.float32)
    g = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    det = cv2.GaussianBlur(np.abs(cv2.Laplacian(g, cv2.CV_32F)), (0, 0), max(h, w) / 40)
    det = det / (det.max() + 1e-6)
    d = 0.75 * (1 - y) + 0.25 * (1 - det)
    return cv2.GaussianBlur(d, (0, 0), max(h, w) / 60)


def guardar_escenario(png_path, carpeta_escenarios, pid, origen):
    """Escribe <pid>.png, <pid>_depth.png (16 bits, 0 cerca … 65535 lejos) y <pid>.json como los de Blender."""
    carpeta = Path(carpeta_escenarios)
    carpeta.mkdir(parents=True, exist_ok=True)
    bgr = cv2.imread(str(png_path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("no se puede leer %s" % png_path)
    d, metodo = profundidad(bgr[:, :, ::-1].copy())
    d = np.clip(d, 0.03, 1.0)                     # el motor usa 1/d: nunca 0
    cv2.imwrite(str(carpeta / (pid + ".png")), bgr)
    cv2.imwrite(str(carpeta / (pid + "_depth.png")), (d * 65535).astype(np.uint16))
    meta = {"id": pid, "res": [bgr.shape[1], bgr.shape[0]], "poi": {}, "origen": dict(origen, profundidad=metodo)}
    (carpeta / (pid + ".json")).write_text(json.dumps(meta, ensure_ascii=False))
    return meta


def preparar(guion, carpeta_trabajo, comfy=None, historial_variantes=(), registro=print):
    """guion: dict con id, formato ("9:16"|"16:9"), pilar y escenas. Devuelve (guion_motor, informe)."""
    S = copy.deepcopy(guion)
    fmt = S.get("formato", "9:16")
    ancho, alto = CF.TAMANOS[fmt]
    pilar = S.get("pilar", "curiosidades")
    var = estilos.elegir_variante(pilar, list(historial_variantes)) if not S.get("variante") else \
        next(v for v in estilos.PILARES[pilar]["variantes"] if v["id"] == S["variante"])
    S["variante"] = var["id"]
    carpeta = Path(carpeta_trabajo)
    pedidos, escenas_img = [], []
    for k, sc in enumerate(S["scenes"]):
        v = sc.get("visual", {})
        if v.get("type") != "image":
            continue
        pid = "%s_img%02d" % (S["id"], k + 1)
        pedidos.append({"id": pid, "prompt": estilos.prompt(pilar, var, v["prompt"], fmt), "ancho": ancho, "alto": alto,
                        "semilla": v.get("seed", estilos.semilla(S["id"], k))})
        escenas_img.append((k, pid))
    informe = {"variante": var["id"], "imagenes": len(pedidos), "fallidas": [], "profundidad": {}}
    if pedidos:
        if comfy is None:
            raise RuntimeError("hay escenas de imagen y ComfyUI no está disponible")
        res = CF.generar_lote(comfy, pedidos, carpeta / "imagenes", registro=registro)
        informe["fallidas"] = res["fallidos"]
        if res["fallidos"]:
            return None, informe                 # no se monta un vídeo con huecos
    man = json.loads((carpeta / "imagenes" / "manifiesto.json").read_text()) if pedidos else {"imagenes": {}}
    for k, pid in escenas_img:
        sc = S["scenes"][k]
        v = sc["visual"]
        meta = guardar_escenario(carpeta / "imagenes" / (pid + ".png"), carpeta / "plates", pid,
                                 {"tipo": "comfyui", "modelo": man.get("modelo"), "licencia": man.get("licencia"),
                                  "semilla": man["imagenes"][pid]["semilla"], "variante": var["id"]})
        informe["profundidad"][pid] = meta["origen"]["profundidad"]
        nuevo = {kk: vv for kk, vv in v.items() if kk not in ("type", "prompt", "seed")}
        nuevo.update({"type": "plate", "plate": pid, "denoise": 0, "grade": v.get("grade", var["grade"])})
        sc["visual"] = nuevo
        if sc.get("sintetico_realista", True) and not any(o.get("type") == "label" for o in sc.get("overlays", [])):
            sc.setdefault("overlays", []).append({"type": "label", "text": "IMAGEN GENERADA CON IA", "at": 0.0})
    S["containsSyntheticMedia"] = any(sc.get("sintetico_realista", True) for k, _ in escenas_img for sc in [S["scenes"][k]]) \
        or S.get("containsSyntheticMedia", False)
    return S, informe
