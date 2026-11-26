"""Pruebas de ARVIS LIFEHACKS 5.0 (26/11/2026): rúbrica 5.0, estilo único con volumen, anclas, reglas del guion."""
import copy
import json
import os

from PIL import Image

from arvis_estudio import calidad
from arvis_vida import activos, guion, motor, props

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _rep(checks=()):
    return {"duration_s": 28.0, "passed": 22, "total": 22, "checks": list(checks)}


def _ev(nota=9.0):
    ev = calidad.plantilla_evaluacion("5.0")
    for k in ev["criterios"]:
        ev["criterios"][k] = {"nota": nota, "evidencias": [{"segundo": 3.0, "motivo": "se ve y se entiende bien", "fotograma": ""}]}
    ev.update(debilidades=["el cierre es algo largo", "el segundo paso va rápido"], veracidad_ok=True, etica_ok=True)
    return ev


def test_rubrica_50_suma_100_y_pesos_de_la_orden():
    p = calidad.RUBRICA_50["pesos"]
    assert sum(p.values()) == 100
    assert p == {"gancho": 20, "retencion": 20, "visual": 20, "originalidad": 15, "utilidad": 10, "claridad": 10, "viralidad": 5}


def test_rubrica_50_evalua_y_aplica_topes():
    r = calidad.evaluar(_rep(), _ev(9.0), rubrica="5.0")
    assert r["rubrica"] == "5.0" and r["total"] == 90.0 and r["aprobado"]
    r = calidad.evaluar(_rep([{"check": "Subtítulos legibles", "ok": False}]), _ev(9.0))   # la rúbrica viene en la evaluación
    assert r["desglose"]["claridad"] == 5.0 and r["total"] == 86.0
    r = calidad.evaluar(_rep(), _ev(8.0), rubrica="5.0")
    assert r["total"] == 80.0 and not r["aprobado"] and r["devolver_a"] == []      # 8/10 en todo: no llega a 85, sin inflar


def test_rubrica_antigua_sigue_igual():
    ev = calidad.plantilla_evaluacion()
    assert set(ev["criterios"]) == set(calidad.PESOS) and "rubrica" not in ev


def test_volumen_conserva_silueta_y_es_determinista():
    im = Image.new("RGBA", (120, 160), (0, 0, 0, 0))
    im.paste((200, 60, 60, 255), (20, 20, 100, 140))
    a, b = activos.volumen(im), activos.volumen(im)
    assert a.tobytes() == b.tobytes()
    assert a.getchannel("A").tobytes() == im.getchannel("A").tobytes()
    assert a.getpixel((24, 24))[0] > a.getpixel((96, 136))[0]        # luz arriba-izquierda, sombra abajo-derecha


def test_props_sin_contornos_marcados():
    svg = props.crear("hucha")["capas"][0]["svg"]
    assert 'stroke-opacity="0.18"' in svg
    assert 'fill="none" stroke="#d76a91"' in svg                     # los trazos sin relleno (la cola) no cambian


def test_grifo_es_lavabo_con_palanca_y_boca():
    p = props.crear("grifo", {"agua": True})
    assert [c["id"] for c in p["capas"]] == ["base", "palanca", "chorro"] and 0 < p["boca"][0] < 1


def test_ancla_coloca_las_gotas_en_la_boca_del_grifo():
    els = [{"activo": "grifo", "x": 0.5, "y": 0.5, "tam": 0.6}, {"tipo": "particulas", "clase": "gotas", "ancla": "grifo"}]
    g = motor._resolver_anclas(els)[1]
    p = props.crear("grifo")
    assert abs(g["x"] - (0.5 + (p["boca"][0] - 0.5) * 0.6)) < 1e-3 and g["y"] < 0.5


def test_guion_avisa_protagonista_pequeno_y_ancla_rota():
    g = json.load(open(os.path.join(RAIZ, "guiones_vida", "SH-035", "guion.json"), encoding="utf-8"))
    assert not any("protagonista" in a for a in guion.validar(g)["avisos"])          # SH-035 ya está hecho con las reglas 5.0
    g1 = copy.deepcopy(g)
    for el in g1["escenas"][0]["elementos"]:
        if el.get("activo"):
            el["tam"] = 0.3
    assert any("protagonista pequeño" in a for a in guion.validar(g1)["avisos"])
    g2 = copy.deepcopy(g)
    g2["escenas"][1]["elementos"].append({"tipo": "particulas", "clase": "gotas", "ancla": "grifo", "x": 0.5, "y": 0.5})
    assert any("ancla" in e for e in guion.validar(g2)["errores"])


def test_cifra_de_ejemplo_en_rotulo_no_necesita_cita_pero_en_la_voz_si():
    g = json.load(open(os.path.join(RAIZ, "guiones_vida", "SH-035", "guion.json"), encoding="utf-8"))
    g["escenas"][0]["elementos"].append({"tipo": "texto", "texto": "-50 %", "x": 0.5, "y": 0.4, "ejemplo": True})
    assert not any("cifras sin cita" in e for e in guion.validar(g)["errores"])
    g["escenas"][0]["elementos"][-1]["ejemplo"] = False
    assert any("cifras sin cita" in e for e in guion.validar(g)["errores"])
