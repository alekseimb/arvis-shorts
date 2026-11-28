"""Bandera (prop propio) y duración pedida por Aleksei en un tema (SH-039, 28/11/2026)."""
from arvis_vida import activos, props
from arvis_vida.qc import duracion_objetivo


def test_banderas_de_los_nueve_paises():
    for p in ("es", "us", "fr", "de", "gb", "it", "ru", "ua", "cn"):
        d = props.crear("bandera", {"pais": p})
        assert d["capas"][0]["svg"].startswith("<svg")
        assert "bandera" in d["clave"]
    assert activos.existe("bandera")


def test_duracion_por_defecto_y_pedida():
    assert duracion_objetivo({}) == (20.0, 35.0)
    assert duracion_objetivo({"duracion_objetivo": [45, 60]}) == (20.0, 35.0)          # sin tema de Aleksei no vale
    assert duracion_objetivo({"tema": "T-004", "duracion_objetivo": [45, 60]}) == (45.0, 60.0)
    assert duracion_objetivo({"tema": "T-004", "duracion_objetivo": [5, 90]}) == (15.0, 60.0)
