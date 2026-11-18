"""Cliente de la API interna de Open-Higgsfield (instancia local, 127.0.0.1).

Endpoints verificados el 18/11/2026 contra el commit 7d06c70 de TechBeme/open-higgsfield:
  GET  /api/health        -> {"status":"alive"}
  GET  /api/ready         -> configuración, almacén de tareas, perfil
  GET  /api/providers     -> proveedores y conexiones (sin secretos)
  GET  /api/catalog       -> catálogo completo (images / videos)
  GET  /api/models        -> modelos de vídeo utilizables (proveedor conectado + activado)
  GET  /api/image-models  -> modelos de imagen utilizables
  POST /api/generate-image (multipart: model_id, prompt, ...) -> task_id
  POST /api/generate       (multipart: model_id, prompt, ...) -> task_id (vídeo)
  GET  /api/tasks/{id}     -> estado de la tarea
  GET  /api/download/{id}  -> fichero generado

Toda generación pasa ANTES por guardia_coste.comprobar(): sin autorización no sale
ninguna petición hacia un proveedor.
"""
from __future__ import annotations

import json
import time
import urllib.request
import uuid
from pathlib import Path

from . import guardia_coste

BASE = "http://127.0.0.1:3000"


class OpenHiggsfield:
    def __init__(self, base: str = BASE, timeout: float = 90):
        self.base = base.rstrip("/")
        self.timeout = timeout

    # --- lectura ---------------------------------------------------------
    def _get(self, ruta: str) -> dict:
        with urllib.request.urlopen(self.base + ruta, timeout=self.timeout) as r:
            return json.loads(r.read().decode())

    def salud(self) -> dict:
        return {"health": self._get("/api/health"), "ready": self._get("/api/ready")}

    def estado_proveedores(self) -> dict:
        p = self._get("/api/providers")
        return {
            "proveedores": [x["id"] for x in p.get("providers", [])],
            "conexiones": len(p.get("connections", [])),
            "conectados": p.get("connectedProviderIds", []),
            "por_entorno": p.get("environmentProviderIds", []),
        }

    def modelos_utilizables(self) -> dict:
        return {
            "video": len(self._get("/api/models").get("models", [])),
            "imagen": len(self._get("/api/image-models").get("models", [])),
        }

    # --- generación (protegida) -----------------------------------------
    def _post_multipart(self, ruta: str, campos: dict) -> dict:
        limite = uuid.uuid4().hex
        cuerpo = b"".join(
            f"--{limite}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
            for k, v in campos.items()
        ) + f"--{limite}--\r\n".encode()
        req = urllib.request.Request(
            self.base + ruta, data=cuerpo, method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={limite}", "Origin": self.base},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:  # la API devuelve JSON también en errores
            return json.loads(e.read().decode() or "{}")

    def generar(self, tipo: str, model_id: str, prompt: str, **params) -> dict:
        guardia_coste.comprobar(model_id)  # lanza GastoNoAutorizado si puede costar dinero
        ruta = "/api/generate-image" if tipo == "imagen" else "/api/generate"
        return self._post_multipart(ruta, {"model_id": model_id, "prompt": prompt, **params})

    def esperar(self, task_id: str, max_s: int = 900) -> dict:
        fin = time.time() + max_s
        while time.time() < fin:
            t = self._get(f"/api/tasks/{task_id}")
            if t.get("status") in {"completed", "succeeded", "failed", "error", "cancelled"}:
                return t
            time.sleep(5)
        raise TimeoutError(task_id)

    def descargar(self, task_id: str, destino: Path) -> Path:
        with urllib.request.urlopen(f"{self.base}/api/download/{task_id}", timeout=self.timeout) as r:
            destino.write_bytes(r.read())
        return destino
