"""Pruebas de LIFEHACKS AI (sin red ni vídeo): rúbrica de ideas, franjas, analista, revisión de seguridad y subtítulos."""
import datetime as dt
import os
import tempfile
from zoneinfo import ZoneInfo

from arvis_lifehacks import analista, constructor, ideas, publicar
from arvis_lifehacks.montaje import bloques_subtitulos

TZ = ZoneInfo("Europe/Madrid")


def _idea(titulo, cat="python", demo="terminal", n=8, seg=40):
    crit = ["utilidad", "interes", "demostrable", "retencion", "originalidad", "conversacion"]
    return {"titulo": titulo, "categoria": cat, "demo": demo, "segundos_estimados": seg,
            "notas": {c: n for c in crit}, "evidencias": {c: "evidencia suficiente %s" % c for c in crit}}


def test_puntuacion_y_topes():
    r = ideas.puntuar(_idea("Ordena tus descargas por tipo con Python"))
    assert r["puntuacion"] == 80.0 and not r["duplicada"]
    no_grabable = ideas.puntuar(_idea("Truco del registro de Windows", demo="no_grabable"))
    assert no_grabable["desglose"]["demostrable"] == 6.0          # tope 3/10 de 20
    sin_evid = _idea("Algo sin pruebas")
    sin_evid["evidencias"]["interes"] = "corta"
    assert ideas.puntuar(sin_evid)["desglose"]["interes"] == 0.0


def test_no_repite_lo_publicado_y_reparte_categorias():
    pub = ["Encuentra archivos repetidos en tu ordenador con Python (gratis)"]
    lista = [_idea("Encuentra archivos repetidos en tu ordenador con Python", n=10),
             _idea("Genera contraseñas seguras con Python", n=9),
             _idea("Renombra cien fotos de golpe con Python", n=8.5),
             _idea("Convierte un PDF a texto en local", cat="pdf", n=8)]
    sel = ideas.seleccionar(lista, pub, n=3)
    titulos = [e["titulo"] for e in sel["elegidas"]]
    assert "Encuentra archivos repetidos en tu ordenador con Python" not in titulos
    assert len(titulos) == 3 and "Convierte un PDF a texto en local" in titulos


def test_franjas_con_margen_y_ocupadas():
    ahora = dt.datetime(2026, 11, 18, 20, 15, tzinfo=TZ)
    f = publicar.siguiente_franja([], ahora)
    assert f.strftime("%d/%m/%Y %H:%M") == "19/11/2026 12:00"          # 21:00 queda a 45 min (< 90)
    f2 = publicar.siguiente_franja(["19/11/2026 12:00"], ahora)
    assert f2.strftime("%H:%M") == "17:00"
    assert publicar.a_utc(f) == "2026-11-19T11:00:00.000Z"


def test_descripcion_sin_angulos():
    g = {"description": "Usa a < b y c > d", "title": "x", "numero": 1, "sources": ["https://a.b"], "hashtags": ["#Shorts"]}
    d = publicar.descripcion(g, codigo="print(1)")
    assert "<" not in d and ">" not in d and "voz sintética" in d


def test_analista_no_cambia_con_pocos_videos():
    out = analista.analizar([{"id": "SH-1", "vistas": 100, "horas": 10, "categoria": "python"}])
    assert "Menos de 3" in out["nota"] and out["multiplicador_categoria"] == {}


def test_analista_pasos_pequenos():
    vids = [{"id": "A%d" % i, "vistas": 1000, "horas": 24, "categoria": "python", "franja": "12:00", "duracion": 35} for i in range(3)]
    vids += [{"id": "B%d" % i, "vistas": 100, "horas": 24, "categoria": "web", "franja": "17:00", "duracion": 45} for i in range(3)]
    out = analista.analizar(vids)
    assert out["multiplicador_categoria"]["python"] == 1.1 and out["multiplicador_categoria"]["web"] == 0.9
    assert out["propuestas_franja"] == []          # menos de 10 vídeos por franja


def test_revision_de_seguridad():
    d = tempfile.mkdtemp()
    open(os.path.join(d, "malo.py"), "w").write("import shutil\nshutil.rmtree('/')\nimport requests\n")
    open(os.path.join(d, "bueno.py"), "w").write("import hashlib\nprint(hashlib.sha256(b'x').hexdigest())\n")
    open(os.path.join(d, "test_x.py"), "w").write("import os\nos.remove('nada')\n")       # las pruebas no cuentan
    ok, hallazgos = constructor.revisar(d)
    assert not ok and any("borrar" in h for h in hallazgos) and any("red" in h for h in hallazgos)
    assert not any("test_x" in h for h in hallazgos)
    ok2, _ = constructor.revisar(d, permisos=["borrar", "red"])
    assert ok2


def test_subtitulos_por_frases():
    ws, t = [], 0.0
    for w in "Fotos descargadas dos veces, copias con otro nombre... Y buscarlas a mano es un rollo.".split():
        ws.append({"w": w, "t0": t, "t1": t + 0.3})
        t += 0.3
    bl = [" ".join(x["w"] for x in b["palabras"]) for b in bloques_subtitulos(ws)]
    assert bl[0] == "Fotos descargadas dos veces," and all(len(b.split()) <= 5 for b in bl)
    assert sum(len(b.split()) for b in bl) == len(ws)


def test_escritorio_cuenta_como_grabable():
    """Chrome real con su interfaz (captura «escritorio») es una demostración de verdad: no se topa a 3."""
    base = {"titulo": "Atajo de prueba", "categoria": "navegador", "segundos_estimados": 35,
            "notas": {k: 9 for k in ideas.PESOS},
            "evidencias": {k: "evidencia suficiente de prueba" for k in ideas.PESOS}}
    esc = ideas.puntuar(dict(base, demo="escritorio"))
    nog = ideas.puntuar(dict(base, demo="no_grabable"))
    assert esc["desglose"]["demostrable"] == 18.0
    assert nog["desglose"]["demostrable"] == 6.0
