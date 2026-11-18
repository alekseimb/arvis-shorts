"""Pruebas del estudio (sin red, sin credenciales, sin Mac): ComfyUI y YouTube simulados."""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from arvis_estudio import calidad, comfy, estilos, imagenes  # noqa: E402
from arvis_estudio.cola import Cola, TransicionInvalida  # noqa: E402
from arvis_estudio.youtube import OAuth, YouTube, YouTubeError  # noqa: E402
from tests.simuladores import ComfySim, YouTubeSim  # noqa: E402


# ------------------------------------------------------------------ ComfyUI
# Valores del subgrafo de la plantilla oficial de ComfyUI «image_z_image_turbo.json»
# (Comfy-Org/workflow_templates, leída el 18/11/2026).
OFICIAL = {"CLIPLoader": ["qwen_3_4b.safetensors", "lumina2", "default"], "VAELoader": ["ae.safetensors"],
           "UNETLoader": ["z_image_turbo_bf16.safetensors", "default"], "EmptySD3LatentImage": [1024, 1024, 1],
           "ModelSamplingAuraFlow": [3], "KSampler": [0, "randomize", 8, 1, "res_multistep", "simple", 1]}


def test_grafo_igual_que_plantilla_oficial():
    tipos_oficiales = OFICIAL
    g = comfy.grafo_zimage("un faro en la niebla", 1536, 864, 42)
    tipos = {v["class_type"]: v["inputs"] for v in g.values()}
    for t in ("UNETLoader", "CLIPLoader", "VAELoader", "ModelSamplingAuraFlow", "CLIPTextEncode", "ConditioningZeroOut",
              "EmptySD3LatentImage", "KSampler", "VAEDecode"):
        assert t in tipos, t
    assert [tipos["CLIPLoader"]["clip_name"], tipos["CLIPLoader"]["type"]] == tipos_oficiales["CLIPLoader"][:2]
    assert tipos["VAELoader"]["vae_name"] == tipos_oficiales["VAELoader"][0]
    assert tipos["UNETLoader"]["unet_name"] == tipos_oficiales["UNETLoader"][0]
    k = tipos_oficiales["KSampler"]
    ks = tipos["KSampler"]
    assert (ks["steps"], ks["cfg"], ks["sampler_name"], ks["scheduler"]) == (k[2], k[3], k[4], k[5])
    assert tipos["ModelSamplingAuraFlow"]["shift"] == tipos_oficiales["ModelSamplingAuraFlow"][0]


def test_comfy_solo_local():
    with pytest.raises(comfy.ComfyError):
        comfy.Comfy("http://192.168.1.20:8188")


def test_lote_reintenta_imagen_negra_e_idempotente(tmp_path):
    sim = ComfySim(fallos={"e2": 1}, siempre_falla=("e3",))
    try:
        cf = comfy.Comfy(sim.url)
        assert cf.disponible()
        ped = [{"id": "LG-T_e%d" % i, "prompt": "escena %d" % i, "ancho": 256, "alto": 144, "semilla": 100 + i} for i in (1, 2, 3)]
        r = comfy.generar_lote(cf, ped, tmp_path, reintentos=2, espera=0.01, registro=lambda *a: None)
        assert r["ok"] == ["LG-T_e1", "LG-T_e2"]
        assert r["fallidos"][0]["id"] == "LG-T_e3" and "negra" in r["fallidos"][0]["error"]
        man = json.loads((tmp_path / "manifiesto.json").read_text())
        assert man["imagenes"]["LG-T_e2"]["intento"] == 2 and man["imagenes"]["LG-T_e2"]["semilla"] == 102 + 7919
        assert man["licencia"] == "Apache-2.0"
        n = len(sim.grafos)
        r2 = comfy.generar_lote(cf, ped[:2], tmp_path, registro=lambda *a: None)
        assert r2["ok"] == ["LG-T_e1", "LG-T_e2"] and len(sim.grafos) == n     # nada se regenera
    finally:
        sim.cerrar()


def test_preparar_guion_crea_escenarios_compatibles_con_motor(tmp_path):
    sim = ComfySim()
    try:
        comfy.TAMANOS["16:9"] = (256, 144)        # pequeño para la prueba
        S = {"id": "LG-T", "formato": "16:9", "pilar": "curiosidades", "title": "t",
             "scenes": [{"say": "uno", "visual": {"type": "image", "prompt": "un volcán al amanecer", "move": "push_in", "fx": ["dust"]}},
                        {"say": "dos", "visual": {"type": "document", "title": "x", "lines": ["a"]}},
                        {"say": "tres", "visual": {"type": "image", "prompt": "un mapa antiguo", "move": "pan_left"}, "sintetico_realista": False}]}
        Sm, inf = imagenes.preparar(S, tmp_path, comfy.Comfy(sim.url), ["cur_epico", "cur_macro"], registro=lambda *a: None)
        assert inf["imagenes"] == 2 and not inf["fallidas"] and inf["variante"] in ("cur_historico", "cur_cosmos")
        v = Sm["scenes"][0]["visual"]
        assert v["type"] == "plate" and v["plate"] == "LG-T_img01" and v["move"] == "push_in" and v["fx"] == ["dust"] and v["denoise"] == 0
        assert any(o["type"] == "label" for o in Sm["scenes"][0]["overlays"])
        assert not Sm["scenes"][2].get("overlays")      # no realista → sin rótulo obligatorio
        assert Sm["scenes"][1]["visual"]["type"] == "document"
        assert Sm["containsSyntheticMedia"] is True
        # mismo criterio de lectura que comp.Plate del motor v4
        d = cv2.imread(str(tmp_path / "plates" / "LG-T_img01_depth.png"), cv2.IMREAD_UNCHANGED)
        assert d.dtype == np.uint16 and d.min() > 0
        dn = d.astype(np.float32) / 65535.0
        near, far = np.percentile(dn, 2), np.percentile(dn, 98)
        disp = 1.0 / np.maximum(dn, 1e-3)
        dispn = np.clip((disp - 1 / far) / max(1e-6, 1 / near - 1 / far), 0, 1)
        assert np.isfinite(dispn).all() and dispn.max() > 0.5
        meta = json.loads((tmp_path / "plates" / "LG-T_img01.json").read_text())
        assert meta["origen"]["licencia"] == "Apache-2.0" and meta["origen"]["profundidad"] in ("aproximada", "depth-anything-v2-small")
    finally:
        comfy.TAMANOS["16:9"] = (1536, 864)
        sim.cerrar()


def test_variantes_rotan():
    usadas = []
    for _ in range(8):
        v = estilos.elegir_variante("actualidad", usadas)
        usadas.append(v["id"])
    assert len(set(usadas[:4])) == 4 and usadas[4] == usadas[0]
    assert estilos.semilla("LG-001", 0) != estilos.semilla("LG-002", 0)


# ------------------------------------------------------------------ cola
def test_cola_estados_con_prueba(tmp_path):
    c = Cola(tmp_path / "e.db")
    g = tmp_path / "g.json"
    g.write_text("{}")
    assert c.alta("SH-100", "short", "actualidad", "T", str(g), estado="guionizado")
    assert not c.alta("SH-100", "short", "actualidad", "T", str(g))          # sin duplicados
    c.mover("SH-100", "generando")
    with pytest.raises(TransicionInvalida):
        c.mover("SH-100", "editando")                                        # falta la prueba
    c.mover("SH-100", "editando", {"imagenes_ok": True})
    with pytest.raises(TransicionInvalida):
        c.mover("SH-100", "validando", {"mp4": str(tmp_path / "no.mp4"), "informe": "x"})   # MP4 inexistente
    mp4 = tmp_path / "a.mp4"
    mp4.write_bytes(b"x")
    c.mover("SH-100", "validando", {"mp4": str(mp4), "informe": "r.json"})
    with pytest.raises(TransicionInvalida):
        c.mover("SH-100", "publicado", {"confirmacion_api": {"privacyStatus": "public"}})   # salto no permitido
    c.mover("SH-100", "aprobado", {"puntuacion": 88.5, "evaluacion": "calidad.json"})
    c.mover("SH-100", "subido", {"video_id": "abc", "privacidad_real": "private"})
    with pytest.raises(TransicionInvalida):
        c.mover("SH-100", "publicado", {"confirmacion_api": {"privacyStatus": "private"}})  # YouTube no dice public
    c.mover("SH-100", "publicado", {"confirmacion_api": {"privacyStatus": "public"}})
    ev = [e["a_estado"] for e in c.eventos("SH-100")]
    assert ev == ["investigado", "guionizado", "generando", "editando", "validando", "aprobado", "subido", "publicado"]


def test_cola_recupera_y_reintenta(tmp_path):
    c = Cola(tmp_path / "e.db")
    for k, p in (("A", 5), ("B", 1)):
        c.alta(k, "largo", "x", k, "g", p, estado="guionizado")
    assert c.siguiente()["clave"] == "B"                     # prioridad
    assert c.reservar("B", "mac", minutos=-1)                # bloqueo ya caducado (simula apagón)
    assert [f["clave"] for f in c.recuperar()] == ["B"]
    assert c.get("B")["bloqueo"] is None
    assert c.reservar("B", "mac", 60) and not c.reservar("B", "otro", 60)
    assert c.siguiente()["clave"] == "A"
    assert c.siguiente(saltar={"A"}) is None
    assert not c.fallo("A", "generando", "ComfyUI no responde", 3)
    assert not c.fallo("A", "generando", "ComfyUI no responde", 3)
    assert c.fallo("A", "generando", "ComfyUI no responde", 3) and c.get("A")["estado"] == "error"


# ------------------------------------------------------------------ YouTube
def _yt(sim):
    o = OAuth("cid", "secreto", "refresh", token_url=sim.url + "/token")
    return YouTube(o, base=sim.url, espera_base=0.01, registro=lambda *a: None)


def _video(tmp_path, mb=2.3):
    p = tmp_path / "v.mp4"
    p.write_bytes(os.urandom(int(mb * 1024 * 1024)))
    return p


def test_subida_reanudable_con_cortes_y_sin_duplicados(tmp_path, monkeypatch):
    import arvis_estudio.youtube as Y
    monkeypatch.setattr(Y, "TROZO", 512 * 1024)
    sim = YouTubeSim(cortes=(2, 3))
    try:
        c = Cola(tmp_path / "e.db")
        c.alta("LG-T", "largo", "x", "t", "g", estado="guionizado")
        yt = _yt(sim)
        assert yt.canal()["id"] == "UCtest"
        v = _video(tmp_path)
        r = yt.subir(str(v), {"title": "Prueba", "description": "d"}, "public", c, "LG-T", auditada=False)
        assert r["privacidad_pedida"] == "private" and r["privacidad_real"] == "private" and "auditar" in r["nota"]
        assert sim.videos[r["video_id"]]["sha"] == hashlib.sha256(v.read_bytes()).hexdigest()   # llegó entero
        assert sim.videos[r["video_id"]]["meta"]["status"]["privacyStatus"] == "private"
        r2 = yt.subir(str(v), {"title": "Prueba"}, "public", c, "LG-T", auditada=False)
        assert r2["duplicado"] and r2["video_id"] == r["video_id"] and len(sim.videos) == 1
        e = yt.esperar_procesado(r["video_id"], timeout=5, cada=0.01)
        assert e["uploadStatus"] == "processed" and e["privacyStatus"] == "private"
        with pytest.raises(YouTubeError):
            yt.cambiar_estado(r["video_id"], "public", auditada=False)                         # no se esquiva la auditoría
    finally:
        sim.cerrar()


def test_subida_se_reanuda_tras_apagado(tmp_path, monkeypatch):
    import arvis_estudio.youtube as Y
    monkeypatch.setattr(Y, "TROZO", 256 * 1024)
    sim = YouTubeSim()
    try:
        c = Cola(tmp_path / "e.db")
        c.alta("SH-T", "short", "x", "t", "g", estado="guionizado")
        yt = _yt(sim)
        v = _video(tmp_path, 1.0)
        reales = yt._http
        cuenta = {"n": 0}

        def corta(metodo, url, *a, **k):
            if "/sesion/" in url and metodo == "PUT" and not k.get("cabeceras", a[1] if len(a) > 1 else {}).get("Content-Range", "").startswith("bytes */"):
                cuenta["n"] += 1
                if cuenta["n"] == 3:
                    raise KeyboardInterrupt("apagón")
            return reales(metodo, url, *a, **k)
        yt._http = corta
        with pytest.raises(KeyboardInterrupt):
            yt.subir(str(v), {"title": "Corte"}, "private", c, "SH-T", auditada=True)
        assert c.get("SH-T")["subida_url"]                       # la sesión quedó guardada
        recibido = len(next(iter(sim.sesiones.values()))["datos"])
        assert 0 < recibido < v.stat().st_size
        yt._http = reales
        r = yt.subir(str(v), {"title": "Corte"}, "private", c, "SH-T", auditada=True)
        assert len(sim.sesiones) == 1                            # misma sesión, no una subida nueva
        assert sim.videos[r["video_id"]]["sha"] == hashlib.sha256(v.read_bytes()).hexdigest()
        assert c.get("SH-T")["subida_url"] is None
    finally:
        sim.cerrar()


def test_auditada_permite_programar_y_miniatura(tmp_path):
    sim = YouTubeSim(auditada=True)
    try:
        yt = _yt(sim)
        v = _video(tmp_path, 0.5)
        r = yt.subir(str(v), {"title": "Prog"}, "public", None, None, publicar_en="2026-12-01T17:00:00Z", sintetico=True, auditada=True)
        st = sim.videos[r["video_id"]]["meta"]["status"]
        assert st["privacyStatus"] == "private" and st["publishAt"] == "2026-12-01T17:00:00Z" and st["containsSyntheticMedia"] is True
        img = tmp_path / "m.jpg"
        cv2.imwrite(str(img), np.full((720, 1280, 3), 120, np.uint8))
        assert yt.miniatura(r["video_id"], str(img)) and sim.videos[r["video_id"]]["miniatura"] > 0
    finally:
        sim.cerrar()


# ------------------------------------------------------------------ calidad
def _informe(ok=True, fallos=()):
    checks = [{"check": n, "ok": n not in fallos, "valor": "x"} for n in
              ("Formato 1920×1080 H.264 + AAC, 24 fps", "Sonoridad −14 LUFS ±1,5 y pico ≤ −1 dBTP", "Gancho: primera frase ≤ 15 palabras y antes de 5 s",
               "Sin imágenes repetidas (diferencia ≥ 0,035; cada imagen ≤ 2 veces)", "Fuentes: ≥ 3 https, cada hecho con fuente y tipo (hecho/opinión/hipótesis)",
               "Subtítulos: todas las palabras, ≤ 3 por bloque")]
    p = sum(c["ok"] for c in checks)
    return {"checks": checks, "passed": p, "total": len(checks), "duration_s": 600.0, "title": "El volcán que cambió el clima",
            "containsSyntheticMedia": True}


def _eval(nota=9, motivo="se ve exactamente lo que se narra en este segundo", seg=12.0, foto="f1.jpg"):
    return {"criterios": {k: {"nota": nota, "evidencias": [{"segundo": seg, "motivo": motivo, "fotograma": foto}]} for k in calidad.PESOS},
            "debilidades": ["la escena del minuto 4 dura demasiado", "el cierre repite una idea del inicio"],
            "veracidad_ok": True, "etica_ok": True, "sintetico_realista": True}


def test_calidad_aprueba_solo_con_evidencia(tmp_path):
    (tmp_path / "f1.jpg").write_bytes(b"x")
    r = calidad.evaluar(_informe(), _eval(9), "largo", 85, stills_dir=str(tmp_path))
    assert r["total"] == 90.0 and r["aprobado"]
    r = calidad.evaluar(_informe(), _eval(9, seg=900.0), "largo", 85, stills_dir=str(tmp_path))   # segundo fuera del vídeo
    assert r["total"] == 0 and not r["aprobado"] and r["puertas"]
    r = calidad.evaluar(_informe(), _eval(9, motivo="bien"), "largo", 85, stills_dir=str(tmp_path))  # motivo vacío
    assert not r["aprobado"]
    r = calidad.evaluar(_informe(), _eval(9, foto="no_existe.jpg"), "largo", 85, stills_dir=str(tmp_path))
    assert r["desglose"]["visual"] == 0                       # sin fotograma revisado, lo visual no puntúa


def test_calidad_topes_y_reparto(tmp_path):
    (tmp_path / "f1.jpg").write_bytes(b"x")
    rep = _informe(fallos=("Sonoridad −14 LUFS ±1,5 y pico ≤ −1 dBTP",))
    r = calidad.evaluar(rep, _eval(10), "largo", 85, stills_dir=str(tmp_path))
    assert r["desglose"]["narracion_sonido"] == 9.0 and "narracion_sonido" in r["topes_aplicados"]
    assert not r["aprobado"] and any("QC técnico" in p for p in r["puertas"])
    agentes = [d["agente"] for d in r["devolver_a"]]
    assert any("Narrador" in a for a in agentes)
    S1 = {"variante": "cur_epico", "scenes": [{"visual": {"type": "plate", "move": m}} for m in ("push_in", "pan_left", "drift", "tilt_up")]}
    f = calidad.firma(S1)
    r = calidad.evaluar(_informe(), _eval(10), "largo", 85, f, [{"clave": "LG-1", "firma": f}], stills_dir=str(tmp_path))
    assert r["desglose"]["visual"] == 14.0 and r["desglose"]["originalidad"] == 9.0 and r["parecido_max"] == 1.0
    r = calidad.evaluar(_informe(), _eval(10), "largo", 85, titulos_recientes=["El volcán que cambió el clima!"], stills_dir=str(tmp_path))
    assert r["desglose"]["originalidad"] == 6.0


# ------------------------------------------------------------------ servicio (orquestación de principio a fin, sin motor)
def _git(*a, cwd=None):
    subprocess.run(["git"] + list(a), cwd=cwd, check=True, capture_output=True)


def test_servicio_flujo_completo_sin_motor(tmp_path):
    env = dict(os.environ, ARVIS_HOME=str(tmp_path / "ARVIS"), PYTHONPATH=str(RAIZ), GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    remoto = tmp_path / "remoto.git"
    _git("init", "-q", "--bare", "-b", "main", str(remoto))
    nube = tmp_path / "nube"
    _git("clone", "-q", str(remoto), str(nube))
    (nube / "ordenes").mkdir()
    (nube / "guiones").mkdir()
    S = {"id": "SH-900", "formato": "9:16", "pilar": "tutoriales", "title": "Truco", "scenes": [{"say": "hola", "visual": {"type": "slate", "lines": ["a"]}}]}
    (nube / "guiones" / "SH-900.json").write_text(json.dumps(S))
    (nube / "ordenes" / "SH-900.json").write_text(json.dumps({"clave": "SH-900", "tipo": "short", "pilar": "tutoriales", "titulo": "Truco",
                                                              "guion": "guiones/SH-900.json"}))
    for a in (("add", "."), ("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "orden"), ("push", "-q", "origin", "main")):
        _git(*a, cwd=nube)
    mac = tmp_path / "mac_repo"
    _git("clone", "-q", str(remoto), str(mac))
    base = tmp_path / "ARVIS" / "estudio"
    base.mkdir(parents=True)
    (base / "ajustes.json").write_text(json.dumps({"repo_ordenes": str(mac), "comfy_url": "http://127.0.0.1:9", "disco_min_gb": 0.001}))

    def tick():
        r = subprocess.run([sys.executable, "-m", "arvis_estudio.servicio", "tick"], env=env, capture_output=True, text=True, cwd=str(RAIZ))
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout.strip().splitlines()[-1])

    def estado():
        r = subprocess.run([sys.executable, "-m", "arvis_estudio.servicio", "estado"], env=env, capture_output=True, text=True, cwd=str(RAIZ))
        return {t["clave"]: t for t in json.loads(r.stdout)["trabajos"]}

    r = tick()
    assert r["paso"] == "guionizado" and estado()["SH-900"]["estado"] == "editando"
    assert json.loads((base / "estado.json").read_text())["cola"]["editando"] == 1      # latido local
    lat = subprocess.run(["git", "-C", str(remoto), "show", "estado:estado/mac.json"], capture_output=True, text=True)
    assert lat.returncode == 0 and json.loads(lat.stdout)["trabajando_en"] in (None, "SH-900")   # latido en la rama «estado»
    for _ in range(3):                                     # sin motor: 3 fallos → «error», nunca «hecho»
        r = tick()
    assert estado()["SH-900"]["estado"] == "error" and "motor" in (estado()["SH-900"]["error"] or "") or "código" in (estado()["SH-900"]["error"] or "")
    # simulamos el resultado del motor y reanudamos desde «error» → «validando»
    sys.path.insert(0, str(RAIZ))
    os.environ["ARVIS_HOME"] = env["ARVIS_HOME"]
    trabajo = base / "trabajo" / "SH-900" / "render"
    trabajo.mkdir(parents=True)
    (trabajo / "SH-900_hq.mp4").write_bytes(b"0" * 1000)
    rep = _informe()
    rep.update({"id": "SH-900", "mp4_hq": str(trabajo / "SH-900_hq.mp4"), "title": "Truco", "description": "d", "duration_s": 40.0})
    (trabajo / "SH-900.json").write_text(json.dumps(rep))
    cv2.imwrite(str(trabajo / "SH-900_still_001.0.png"), np.full((1920, 1080, 3), 90, np.uint8))
    c = Cola(base / "estudio.db")
    c.mover("SH-900", "validando", {"mp4": str(trabajo / "SH-900_hq.mp4"), "informe": str(trabajo / "SH-900.json")})
    r = tick()
    assert estado()["SH-900"]["estado"] == "validando" and "esperando" in estado()["SH-900"]["error"]
    _git("pull", "-q", cwd=nube)
    assert (nube / "revision" / "SH-900" / "informe.json").exists() and (nube / "revision" / "SH-900" / "SH-900_still_001.0.jpg").exists()
    assert not list((nube / "revision" / "SH-900").glob("*.mp4"))            # nunca vídeo en el repositorio
    assert tick().get("nada")                                                   # sin evaluación: no se atasca
    ev = _eval(9, foto="SH-900_still_001.0.jpg", seg=1.0)
    (nube / "revision" / "SH-900" / "evaluacion.json").write_text(json.dumps(ev))
    for a in (("add", "."), ("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "evaluación"), ("push", "-q", "origin", "main")):
        _git(*a, cwd=nube)
    tick()
    assert estado()["SH-900"]["estado"] == "aprobado" and estado()["SH-900"]["puntuacion"] == 90.0
    tick()                                                                      # sin auditoría → espera manual
    t = estado()["SH-900"]
    assert t["estado"] == "espera_manual" and "Make" in t["error"]
    listo = base / "listos" / "SH-900"
    assert (listo / "SH-900.mp4").exists() and json.loads((listo / "metadatos.json").read_text())["title"] == "Truco"


# ------------------------------------------------------------------ MacBook Pro Intel 2019 (corrección del 18/11/2026)
def _servicio(env, *args):
    return subprocess.run([sys.executable, "-m", "arvis_estudio.servicio", *args], env=env, capture_output=True, text=True, cwd=str(RAIZ))


def test_sin_motor_de_imagen_no_se_genera_ni_se_simula(tmp_path):
    """En el Mac Intel (motor_imagen = ninguno) un guion con imágenes IA se detiene con un motivo claro; nunca se inventan."""
    env = dict(os.environ, ARVIS_HOME=str(tmp_path / "ARVIS"), PYTHONPATH=str(RAIZ))
    base = tmp_path / "ARVIS" / "estudio"
    base.mkdir(parents=True)
    (base / "ajustes.json").write_text(json.dumps({"comfy_url": "http://127.0.0.1:9", "disco_min_gb": 0.001}))
    g = tmp_path / "SH-901.json"
    g.write_text(json.dumps({"id": "SH-901", "formato": "9:16", "pilar": "curiosidades", "title": "Dato",
                             "scenes": [{"say": "hola", "visual": {"type": "image", "prompt": "un faro"}}]}))
    assert _servicio(env, "encolar", str(g), "--tipo", "short").returncode == 0
    r = json.loads(_servicio(env, "tick").stdout.strip().splitlines()[-1])
    assert "no genera imágenes" in r["error"]
    est = {t["clave"]: t for t in json.loads(_servicio(env, "estado").stdout)["trabajos"]}
    assert est["SH-901"]["estado"] == "generando"                     # no avanza a «editando»
    assert not list((base / "trabajo").rglob("*.png"))                  # ninguna imagen inventada
    c = json.loads(_servicio(env, "comprobar").stdout)
    assert c["motor_imagen"] == "ninguno" and "pausa" in c["comfyui"]


def test_disco_externo_desconectado_no_crea_nada():
    falso = "/Volumes/ARVIS_PRUEBA_NO_MONTADO"
    env = dict(os.environ, ARVIS_HOME=falso + "/arvis", PYTHONPATH=str(RAIZ))
    r = _servicio(env, "tick")
    assert r.returncode == 0 and json.loads(r.stdout.strip().splitlines()[-1])["pausa"] == "volumen"
    assert not os.path.exists(falso)
    assert _servicio(env, "estado").returncode == 2
