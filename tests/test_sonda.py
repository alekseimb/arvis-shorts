"""Pruebas de la sonda (QC fase 1, ARVIS 3.1) con guiones reales. Necesitan la voz Piper y Fluent (ops entorno)."""
import json
import os

import pytest

piper = pytest.importorskip("piper")

from arvis_vida import activos, sonda  # noqa: E402
from arvis_vida.motor import Motor     # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _sondear(sh, tmp_path):
    activos.preparar_fluent()
    g = json.load(open(os.path.join(RAIZ, "guiones_vida", sh, "guion.json"), encoding="utf-8"))
    m = Motor(g, str(tmp_path))
    m.preparar_audio(1.0)
    m.preparar_escenas()
    return sonda.analizar(m, str(tmp_path))


def test_detecta_rotulo_bajo_los_subtitulos_en_sh031(tmp_path):
    # Defecto real que se publicó: la pastilla «ÚSALA BIEN» queda debajo de los subtítulos hacia el segundo 8,3
    r = _sondear("SH-031", tmp_path)
    graves = [d for d in r["defectos"] if d["tipo"] == "solape_subtitulos"]
    assert graves and 7.5 <= graves[0]["t0"] <= 9.0
    assert graves[0]["fotograma"] in os.listdir(tmp_path / "stills")
    assert r["hojas"] and all((tmp_path / "stills" / h).exists() for h in r["hojas"])


def test_sh028_sin_defectos_estructurales(tmp_path):
    # La voz Piper cambia unas centésimas entre síntesis: los roces breves (p. ej. la barra «ENERGÍA AHORRADA» sobre
    # los subtítulos hacia 4,5 s) aparecen o no según la toma. Por eso producir.py sondea la MISMA toma que se monta.
    r = _sondear("SH-028", tmp_path)
    assert not [x for x in r["defectos"] if x["tipo"] in ("cortado", "escena_vacia")]
    assert len(r["revisar"]) <= 20
