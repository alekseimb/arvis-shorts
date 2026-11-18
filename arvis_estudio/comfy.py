"""Cliente de ComfyUI (solo local, 127.0.0.1) y generación por lotes con reintentos.

Modelo principal: Z-Image-Turbo bf16 (Apache-2.0), con su codificador Qwen3-4B (Apache-2.0) y el
autoencoder de FLUX.1-schnell (Apache-2.0). Grafo copiado de la plantilla oficial de ComfyUI
«image_z_image_turbo» (8 pasos, cfg 1, res_multistep/simple, ModelSamplingAuraFlow 3).
En Apple Silicon no se usan pesos fp8 (MPS no los admite).
"""
import hashlib
import io
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import numpy as np
from PIL import Image

from .config import escribir_json

MODELOS = {
    "zimage_turbo": {
        "nombre": "Z-Image-Turbo (Tongyi-MAI) bf16",
        "licencia": "Apache-2.0",
        "archivos": {
            "diffusion_models/z_image_turbo_bf16.safetensors": "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/diffusion_models/z_image_turbo_bf16.safetensors",
            "text_encoders/qwen_3_4b.safetensors": "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors",
            "vae/ae.safetensors": "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors",
        },
        "pasos": 8, "cfg": 1.0, "shift": 3.0, "sampler": "res_multistep", "scheduler": "simple",
    },
}

# tamaños nativos (múltiplos de 16, ~1,3 MP)
TAMANOS = {"9:16": (864, 1536), "16:9": (1536, 864), "1:1": (1152, 1152)}


class ComfyError(Exception):
    pass


class Comfy:
    def __init__(self, url="http://127.0.0.1:8188", timeout=900):
        p = urllib.parse.urlparse(url)
        if p.hostname not in ("127.0.0.1", "localhost", "::1"):
            raise ComfyError("ComfyUI solo se usa en local (127.0.0.1), nunca expuesto a la red")
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.client_id = "arvis-" + uuid.uuid4().hex[:8]

    def _req(self, metodo, ruta, cuerpo=None, crudo=False, t=30):
        data = json.dumps(cuerpo).encode() if cuerpo is not None else None
        req = urllib.request.Request(self.url + ruta, data=data, method=metodo,
                                     headers={"Content-Type": "application/json"} if data else {})
        try:
            with urllib.request.urlopen(req, timeout=t) as r:
                b = r.read()
        except urllib.error.HTTPError as e:
            raise ComfyError("HTTP %s en %s: %s" % (e.code, ruta, e.read()[:400].decode("utf-8", "replace")))
        except (urllib.error.URLError, OSError) as e:
            raise ComfyError("ComfyUI no responde en %s (%s)" % (self.url, e))
        return b if crudo else (json.loads(b) if b else {})

    def disponible(self):
        try:
            self._req("GET", "/system_stats", t=5)
            return True
        except ComfyError:
            return False

    def estado(self):
        return self._req("GET", "/system_stats", t=5)

    def enviar(self, grafo):
        r = self._req("POST", "/prompt", {"prompt": grafo, "client_id": self.client_id})
        if r.get("error") or r.get("node_errors"):
            raise ComfyError("grafo rechazado: %s %s" % (r.get("error"), json.dumps(r.get("node_errors"))[:400]))
        return r["prompt_id"]

    def esperar(self, prompt_id, timeout=None):
        fin = time.time() + (timeout or self.timeout)
        while time.time() < fin:
            h = self._req("GET", "/history/" + prompt_id)
            if prompt_id in h:
                item = h[prompt_id]
                st = item.get("status", {})
                if st.get("status_str") == "error":
                    msgs = [m for m in st.get("messages", []) if m and m[0] == "execution_error"]
                    raise ComfyError("error de ejecución: %s" % (json.dumps(msgs)[:500] or "sin detalle"))
                if st.get("completed") or item.get("outputs"):
                    return item.get("outputs", {})
            time.sleep(1.0)
        raise ComfyError("tiempo agotado esperando %s" % prompt_id)

    def descargar(self, info):
        q = urllib.parse.urlencode({"filename": info["filename"], "subfolder": info.get("subfolder", ""), "type": info.get("type", "output")})
        return self._req("GET", "/view?" + q, crudo=True, t=60)

    def liberar(self):
        try:
            self._req("POST", "/free", {"unload_models": False, "free_memory": True})
        except ComfyError:
            pass


def grafo_zimage(prompt, ancho, alto, semilla, modelo="zimage_turbo", prefijo="arvis"):
    m = MODELOS[modelo]
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "z_image_turbo_bf16.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "lumina2", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        "4": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": m["shift"]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "6": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["5", 0]}},
        "7": {"class_type": "EmptySD3LatentImage", "inputs": {"width": int(ancho), "height": int(alto), "batch_size": 1}},
        "8": {"class_type": "KSampler", "inputs": {"model": ["4", 0], "seed": int(semilla) % (2 ** 63), "steps": m["pasos"], "cfg": m["cfg"],
                                                    "sampler_name": m["sampler"], "scheduler": m["scheduler"], "positive": ["5", 0],
                                                    "negative": ["6", 0], "latent_image": ["7", 0], "denoise": 1.0}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "SaveImage", "inputs": {"images": ["9", 0], "filename_prefix": prefijo}},
    }


def validar_imagen(png_bytes, ancho, alto):
    """Rechaza imágenes vacías: negras (NaN en MPS), planas o de tamaño distinto al pedido."""
    im = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    if im.size != (ancho, alto):
        return False, "tamaño %sx%s (pedido %sx%s)" % (im.size[0], im.size[1], ancho, alto)
    a = np.asarray(im.resize((64, 64)), np.float32) / 255.0
    lum = a @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    media, desv = float(lum.mean()), float(lum.std())
    if media < 0.02:
        return False, "imagen negra (media %.3f)" % media
    if desv < 0.02:
        return False, "imagen plana (desviación %.3f)" % desv
    return True, "media %.2f · desviación %.2f" % (media, desv)


def generar_lote(comfy, pedidos, carpeta, modelo="zimage_turbo", reintentos=2, espera=5.0, registro=print):
    """pedidos: [{"id", "prompt", "ancho", "alto", "semilla"}]. Idempotente: lo ya generado y válido no se repite.

    Organización: <carpeta>/<id>.png + <carpeta>/manifiesto.json (prompt, semilla, modelo, licencia, sha256, segundos).
    """
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    man_p = carpeta / "manifiesto.json"
    man = json.loads(man_p.read_text()) if man_p.exists() else {"modelo": modelo, "licencia": MODELOS[modelo]["licencia"], "imagenes": {}}
    ok, fallidos = [], []
    for p in pedidos:
        destino = carpeta / (p["id"] + ".png")
        previo = man["imagenes"].get(p["id"])
        if destino.exists() and previo and previo.get("sha256") == _sha(destino.read_bytes()) and previo.get("prompt") == p["prompt"]:
            ok.append(p["id"])
            continue
        semilla, ultimo = int(p["semilla"]), ""
        for intento in range(reintentos + 1):
            t0 = time.time()
            try:
                pid = comfy.enviar(grafo_zimage(p["prompt"], p["ancho"], p["alto"], semilla, modelo, prefijo="arvis_" + p["id"]))
                salidas = comfy.esperar(pid)
                imgs = [i for nodo in salidas.values() for i in nodo.get("images", [])]
                if not imgs:
                    raise ComfyError("sin imagen en la salida")
                datos = comfy.descargar(imgs[0])
                valida, motivo = validar_imagen(datos, p["ancho"], p["alto"])
                if not valida:
                    raise ComfyError(motivo)
                destino.write_bytes(datos)
                man["imagenes"][p["id"]] = {"prompt": p["prompt"], "semilla": semilla, "ancho": p["ancho"], "alto": p["alto"],
                                            "sha256": _sha(datos), "segundos": round(time.time() - t0, 1), "intento": intento + 1,
                                            "control": motivo}
                escribir_json(man_p, man)
                ok.append(p["id"])
                registro("[comfy] %s ok en %.0f s" % (p["id"], time.time() - t0))
                break
            except ComfyError as e:
                ultimo = str(e)
                registro("[comfy] %s intento %d falló: %s" % (p["id"], intento + 1, ultimo))
                semilla += 7919          # otra semilla: evita repetir una imagen defectuosa
                if intento < reintentos:
                    time.sleep(espera * (intento + 1))
        else:
            fallidos.append({"id": p["id"], "error": ultimo})
    man["ultima_ejecucion"] = {"ok": len(ok), "fallidos": fallidos, "momento": time.strftime("%Y-%m-%dT%H:%M:%S")}
    escribir_json(man_p, man)
    return {"ok": ok, "fallidos": fallidos, "manifiesto": str(man_p)}


def _sha(b):
    return hashlib.sha256(b).hexdigest()
