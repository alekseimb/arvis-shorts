"""Guardia de coste: ningún proveedor de pago se usa sin autorización explícita.

Regla económica de ARVIS: presupuesto adicional 0 €. La lista de proveedores
permitidos vive en config/proveedores_open_higgsfield.json y por defecto está
vacía. Para permitir uno hace falta `autorizado_por` + `fecha_autorizacion`
(frase literal de Aleksei), y aun así solo si `coste_estimado_eur` es 0.
"""
from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = RAIZ / "config" / "proveedores_open_higgsfield.json"


class GastoNoAutorizado(PermissionError):
    """Se intentó usar un proveedor/modelo que puede costar dinero."""


def cargar_config(ruta: Path = CONFIG) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


def proveedor_de(model_id: str) -> str:
    # Los IDs del catálogo de Open-Higgsfield son "<proveedor>__<modelo>".
    if "__" not in model_id:
        raise ValueError(f"model_id sin proveedor: {model_id!r}")
    return model_id.split("__", 1)[0]


def comprobar(model_id: str, config: dict | None = None) -> None:
    """Lanza GastoNoAutorizado salvo que el proveedor esté permitido y sea gratis."""
    cfg = config or cargar_config()
    if cfg.get("presupuesto_eur", 0) != 0 and not cfg.get("presupuesto_autorizado_por"):
        raise GastoNoAutorizado("Presupuesto distinto de 0 € sin autorización registrada")
    prov = proveedor_de(model_id)
    p = cfg.get("proveedores", {}).get(prov)
    if p is None:
        raise GastoNoAutorizado(f"Proveedor desconocido: {prov}")
    if not p.get("habilitado", False):
        raise GastoNoAutorizado(f"Proveedor {prov} desactivado por defecto ({p.get('motivo', 'de pago')})")
    if not (p.get("autorizado_por") and p.get("fecha_autorizacion")):
        raise GastoNoAutorizado(f"Proveedor {prov} sin autorización explícita registrada")
    permitidos = p.get("modelos_permitidos", [])
    if model_id not in permitidos:
        raise GastoNoAutorizado(f"Modelo {model_id} no está en la lista de modelos gratuitos de {prov}")
    if p.get("coste_estimado_eur", None) != 0:
        raise GastoNoAutorizado(f"Proveedor {prov} con coste estimado distinto de 0 €")
