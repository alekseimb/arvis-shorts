"""Registro persistente de producción (JSON Lines en produccion/registro.jsonl).

Solo texto y metadatos: nunca vídeos. Coste siempre 0 € salvo autorización.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REGISTRO = Path(__file__).resolve().parent.parent / "produccion" / "registro.jsonl"
ESTADOS = {"pendiente", "guion", "generando", "renderizado", "qc_ok", "qc_fallo",
           "subido_privado", "programado", "publicado", "error", "prueba"}


def anotar(pieza: str, estado: str, coste_eur: float = 0.0, **datos) -> dict:
    if estado not in ESTADOS:
        raise ValueError(estado)
    if estado == "publicado" and not datos.get("youtube_id_confirmado"):
        raise ValueError("No se marca publicado sin confirmación de la API de YouTube")
    fila = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "pieza": pieza,
            "estado": estado, "coste_eur": coste_eur, **datos}
    REGISTRO.parent.mkdir(exist_ok=True)
    with REGISTRO.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
    return fila


def leer() -> list[dict]:
    if not REGISTRO.exists():
        return []
    return [json.loads(l) for l in REGISTRO.read_text(encoding="utf-8").splitlines() if l.strip()]
