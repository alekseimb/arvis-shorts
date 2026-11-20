"""Pruebas rápidas de ARVIS VIDA (sin render completo: validación, activos, fotogramas, retención)."""
import copy
import json
import os

import numpy as np
import pytest

from arvis_vida import activos, guion, props

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = json.load(open(os.path.join(RAIZ, "guiones_vida", "SH-027", "guion.json"), encoding="utf-8"))


def test_guion_modelo_valido():
    r = guion.validar(G)
    assert r["ok"], r


def test_gancho_sin_pregunta_se_rechaza():
    g = copy.deepcopy(G)
    g["escenas"][0]["say"] = "Tu lavadora gasta mucho."
    assert any("pregunta" in e for e in guion.validar(g)["errores"])


def test_cifra_sin_fuente_se_rechaza():
    g = copy.deepcopy(G)
    g["escenas"][1]["say"] = "El 97 por ciento se va en calentar el agua."
    assert any("cifras" in e for e in guion.validar(g)["errores"])


def test_mezcla_peligrosa_se_rechaza_y_la_advertencia_no():
    g = copy.deepcopy(G)
    g["escenas"][2]["say"] = "Mezcla lejía con vinagre para limpiar."
    assert any("no permitido" in e for e in guion.validar(g)["errores"])
    g["escenas"][2]["say"] = "Nunca mezcles lejía con vinagre."
    assert not any("no permitido" in e for e in guion.validar(g)["errores"])


def test_titulo_repetido_se_rechaza():
    assert any("publicado" in e for e in guion.validar(G, [G["title"]])["errores"])


def test_sin_fuente_oficial_se_rechaza():
    g = copy.deepcopy(G)
    g["sources"] = ["https://blog-cualquiera.example.com/truco"]
    assert any("fuente" in e for e in guion.validar(g)["errores"])


def test_props_tienen_capas():
    for n in props.PROPS:
        p = props.crear(n)
        assert p["capas"] and p["capas"][0]["id"] == "base"


@pytest.mark.skipif(not os.path.isdir(activos.FLUENT), reason="sin caché de Fluent Emoji")
def test_catalogo_completo():
    assert [k for k in activos.CATALOGO if not activos.ruta_fluent(k)] == []


@pytest.mark.skipif(not os.path.isdir(activos.FLUENT), reason="sin caché de Fluent Emoji")
def test_fotograma_del_gancho_no_esta_vacio(tmp_path):
    from arvis_vida.motor import Motor
    g = copy.deepcopy(G)
    g["escenas"] = g["escenas"][:2]
    m = Motor(g, str(tmp_path))
    m.preparar_audio()
    m.preparar_escenas()
    a = np.asarray(m.fotograma(0.0)).astype(float)
    b = np.asarray(m.fotograma(0.5)).astype(float)
    assert a.shape == (1920, 1080, 3)
    assert a.mean() > 40                       # no es una pantalla negra
    assert np.abs(a - b).mean() > 1.0          # hay movimiento en el primer medio segundo
    assert any(el.t_in <= 0.3 for el in m.elems[0])
