"""Uso: python3 -m arvis_av.cli <comando>

  estado        Salud de Open-Higgsfield, proveedores y modelos utilizables.
  probar        Intenta una generación de prueba (la guardia la bloquea si no es gratis).
  local DIR     Genera imagen + clip 9:16 con FFmpeg y pasa QC técnico.
  qc FICHERO [short|largo] [SRT]
  payload GUION.json URL  Payload para Make 8260243 (SIEMPRE privado; no ejecuta nada).
  short GUION.json [DIR]  Produce un Short completo en local (Piper + Pillow + FFmpeg) y pasa QC.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import generador_local, guardia_coste, qc, registro
from .higgsfield_client import OpenHiggsfield


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "estado"
    if cmd == "estado":
        oh = OpenHiggsfield()
        print(json.dumps({**oh.salud(), **oh.estado_proveedores(), "utilizables": oh.modelos_utilizables()},
                         ensure_ascii=False, indent=1))
    elif cmd == "probar":
        modelo = argv[1] if len(argv) > 1 else "google-ai-studio__gemini-2.5-flash-image"
        try:
            r = OpenHiggsfield().generar("imagen", modelo, "Prueba ARVIS")
        except guardia_coste.GastoNoAutorizado as e:
            r = {"bloqueado_por_guardia": str(e)}
        print(json.dumps(r, ensure_ascii=False))
    elif cmd == "local":
        d = Path(argv[1] if len(argv) > 1 else "salida"); d.mkdir(parents=True, exist_ok=True)
        img = generador_local.imagen("ARVIS · prueba local", d / "prueba.png")
        clip = generador_local.clip_desde_imagen(img, d / "prueba.mp4", segundos=4)
        rq = qc.revisar(clip, "short")
        registro.anotar("PRUEBA-LOCAL", "prueba", motor="ffmpeg", fichero=clip.name,
                        qc={k: v[0] for k, v in rq["checks"].items()})
        print(json.dumps(rq, ensure_ascii=False, indent=1))
    elif cmd == "short":
        from . import productor_short
        r = productor_short.producir(Path(argv[1]), Path(argv[2] if len(argv) > 2 else "salida"))
        print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if r["qc"]["ok"] else 1
    elif cmd == "payload":
        g = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        print(json.dumps({"fileUrl": argv[2], "title": g["titulo"][:100], "description": g["descripcion"][:5000],
                          "tags": g.get("etiquetas", []), "privacyStatus": "private", "categoryId": "27",
                          "key": g["pieza"]}, ensure_ascii=False, indent=1))
    elif cmd == "qc":
        r = qc.revisar(Path(argv[1]), argv[2] if len(argv) > 2 else "short",
                       Path(argv[3]) if len(argv) > 3 else None)
        print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if r["ok"] else 1
    else:
        print(__doc__); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
