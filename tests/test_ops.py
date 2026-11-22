"""Pruebas de arvis_vida.ops (ARVIS 3.1): plan, franjas, caché de fuentes, métricas. Solo biblioteca estándar."""
import copy
import datetime as dt

from arvis_vida import ops

BASE = {"version": 1, "ultimo_sh": "SH-032", "ultimo_numero": 8, "reglas": dict(ops.REGLAS),
        "shorts": {"SH-031": {"fila": 32, "yt": "ED2BlyhPMds", "franja": "21/11/2026 17:00", "fase": "10. Publicado", "categoria": "cocina", "linea": "vida"},
                   "SH-032": {"fila": 33, "yt": "kuePPJV7oa4", "franja": "22/11/2026 12:00", "fase": "9. Programado", "categoria": "limpieza", "linea": "vida"}},
        "ideas": {"IDEA-020": {"fila": 21, "estado": "Elegida", "categoria": "ahorro", "puntuacion": 76.5, "leido": "20/11/2026",
                               "fuentes": ["https://www.comunidad.madrid/x"], "citas": ["entre los 18 y 20 ºC"]},
                  "IDEA-025": {"fila": 26, "estado": "Elegida", "categoria": "cocina", "puntuacion": 77.0, "leido": "22/11/2026",
                               "fuentes": ["https://www.aesan.gob.es/y"], "citas": ["La fecha de caducidad…"]},
                  "IDEA-023": {"fila": 24, "estado": "Elegida", "categoria": "ropa", "puntuacion": 69.5, "leido": "20/11/2026",
                               "fuentes": ["https://www.ocu.org/z"], "citas": ["…"]}},
        "metricas": {"fecha": "22/11/2026 01:52", "videos": {}}, "make": {"estado": "OK", "ultima_revision": "22/11/2026 08:50"}}


def t(x):
    return dt.datetime.strptime(x, "%d/%m/%Y %H:%M")


def test_supervision_detecta_vencidos_y_llamada_correcta():
    p = ops.plan(copy.deepcopy(BASE), t("22/11/2026 14:47"))
    assert [c["sh"] for c in p["A"]["comprobar_publico"]] == ["SH-032"]
    ll = p["A"]["llamada_make"]
    assert ll["url"] == "/v3/videos" and ll["method"] == "GET" and ll["key"] == "estados-lh"   # nunca la URL completa (da 404)
    assert {"key": "id", "value": "kuePPJV7oa4"} in ll["qs"]
    assert "B" not in p["modos"]                       # las métricas solo a las 01:47


def test_sin_vencidos_no_consulta_make():
    e = copy.deepcopy(BASE)
    e["shorts"]["SH-032"]["fase"] = "10. Publicado"
    p = ops.plan(e, t("22/11/2026 14:47"))
    assert p["A"]["llamada_make"] is None and not p["A"]["comprobar_publico"]


def test_franja_libre_y_categoria_distinta():
    p = ops.plan(copy.deepcopy(BASE), t("22/11/2026 14:47"))
    c = p["C"]
    assert c["franja"] == "22/11/2026 17:00" and c["publishAt"] == "2026-11-22T16:00:00.000Z"
    assert c["siguiente_sh"] == "SH-033" and c["numero"] == 9
    assert c["idea"]["id"] == "IDEA-020"               # IDEA-025 es cocina (reciente): se salta aunque puntúe más
    assert c["idea"]["fuente_valida"] and not c["investigar"]


def test_margen_de_90_minutos_y_cola_llena():
    e = copy.deepcopy(BASE)
    p = ops.plan(e, t("22/11/2026 19:45"))             # 21:00 está a 75 min: no vale
    assert p["C"]["franja"] == "23/11/2026 12:00"
    for k, f in enumerate(["23/11/2026 12:00", "23/11/2026 17:00", "23/11/2026 21:00", "22/11/2026 17:00", "22/11/2026 21:00"]):
        e["shorts"]["SH-1%02d" % k] = {"franja": f, "fase": "9. Programado", "yt": "x%d" % k}
    p = ops.plan(e, t("22/11/2026 14:47"))
    assert not p["C"]["producir"] and "cola llena" in p["C"]["motivo"]


def test_fuente_caducada_pide_releer_una_vez():
    p = ops.plan(copy.deepcopy(BASE), t("10/12/2026 08:47"))
    assert p["C"]["idea"]["fuente_valida"] is False


def test_reintento_usa_el_mismo_sh():
    e = copy.deepcopy(BASE)
    e["shorts"]["SH-033"] = {"fila": 34, "fase": "4. Revisión", "intentos": 1, "idea": "IDEA-020", "numero": 9, "debilidades": "gancho sin cifra"}
    p = ops.plan(e, t("22/11/2026 14:47"))
    assert p["C"]["reintento"] == "SH-033" and p["C"]["siguiente_sh"] == "SH-033" and p["C"]["numero"] == 9


def test_metricas_alinea_listas_y_no_pisa_columnas():
    e = copy.deepcopy(BASE)
    data = {"ids": "ED2BlyhPMds,kuePPJV7oa4", "viewsList": "660,120", "likesList": "11,2", "commentsList": "0,1",
            "pubList": "2026-11-21T16:00:08Z,2026-11-22T11:00:05Z", "durList": "PT32S,PT36S", "privList": "public,public"}
    r = ops.metricas(e, data, t("23/11/2026 01:50"))
    assert len(r["filas_METRICAS"]) == 2 and all(len(f) == 13 for f in r["filas_METRICAS"])
    assert r["filas_METRICAS"][0][0] == "SH-031" and r["filas_METRICAS"][0][3] == "660"
    ko = r["SHORTS_K_O"]
    assert ko["rango"] == "SHORTS!K32:O33" and ko["valores"][0][1] is None and ko["valores"][0][3] is None
    assert r["analista"]["cambia_pesos"] is False      # menos de 3 vídeos por categoría: nunca cambia
    assert e["metricas"]["videos"]["SH-032"]["vistas"] == 120


def test_utc_en_invierno_y_verano():
    assert ops.utc_iso(t("22/11/2026 21:00")) == "2026-11-22T20:00:00.000Z"
    assert ops.utc_iso(t("01/07/2027 12:00")) == "2027-07-01T10:00:00.000Z"


def test_fusionar_y_borrar_claves():
    e = {"a": {"b": 1, "c": 2}}
    ops.fusionar(e, {"a": {"c": None, "d": 3}})
    assert e == {"a": {"b": 1, "d": 3}}
