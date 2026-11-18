"""Servicio del estudio (lo lanza launchd cada 5 minutos; no necesita Claude abierto).

Cada «tick»:
  1. bloqueo de proceso (si ya hay un tick trabajando, este solo escribe el latido y sale),
  2. latido + comprobación de disco y de ComfyUI,
  3. recuperación de trabajos cortados (reinicio, apagado, falta de batería),
  4. órdenes nuevas desde el repositorio (git pull),
  5. un paso del trabajo más avanzado de la cola (acabar antes que empezar).
Si el Mac está apagado no pasa nada: no hay latido y el Supervisor lo muestra como «Mac sin conexión».

Uso:
  python3 -m arvis_estudio.servicio tick
  python3 -m arvis_estudio.servicio estado
  python3 -m arvis_estudio.servicio comprobar
  python3 -m arvis_estudio.servicio encolar guiones/LG-001.json --tipo largo --pilar curiosidades
  python3 -m arvis_estudio.servicio vincular LG-001 <video_id>        (tras una subida manual)
  python3 -m arvis_estudio.servicio subir-prueba ruta.mp4 "Título"     (siempre privado)
  python3 -m arvis_estudio.servicio limpiar [--simular]
"""
import argparse
import fcntl
import glob
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import avisos, calidad, comfy, disco, imagenes
from . import config as K
from .cola import Cola, TransicionInvalida
from .repo import Repo, RepoError

QUIEN = "mac-" + (os.uname().nodename if hasattr(os, "uname") else "local")


# ------------------------------------------------------------------ latido
def estado_actual(cola, aj, trabajando=None):
    return {"momento": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "equipo": QUIEN, "version": "1.0.0",
            "motor_imagen": aj.get("motor_imagen", "ninguno"),
            "comfyui": aj.get("motor_imagen") == "comfyui" and comfy.Comfy(aj["comfy_url"]).disponible(), "disco_libre_gb": round(disco.libre_gb(K.ESTUDIO), 1),
            "trabajando_en": trabajando, "cola": cola.resumen(),
            "integracion_youtube_auditada": aj["integracion_youtube_auditada"]}


def latido(cola, aj, trabajando=None, repo=None):
    e = estado_actual(cola, aj, trabajando)
    K.escribir_json(K.ESTADO, e)
    if repo and repo.disponible():
        try:
            ultimo = K.ESTUDIO / ".latido_repo"
            if not ultimo.exists() or time.time() - ultimo.stat().st_mtime > 1800 or trabajando:
                repo.latido(e)
                ultimo.touch()
        except RepoError as ex:
            avisos.registrar("aviso", str(ex))
    return e


class Latidor(threading.Thread):
    """Mantiene el latido cada minuto mientras un paso largo (montaje de 40 min) está en marcha."""
    def __init__(self, cola, aj, clave):
        super().__init__(daemon=True)
        self.cola, self.aj, self.clave, self.parar = cola, aj, clave, threading.Event()

    def run(self):
        while not self.parar.wait(60):
            try:
                K.escribir_json(K.ESTADO, estado_actual(self.cola, self.aj, self.clave))
            except Exception:
                pass


# ------------------------------------------------------------------ órdenes
def importar_ordenes(cola, repo):
    nuevas = 0
    for o in repo.ordenes():
        t = cola.get(o["clave"])
        guion = str(repo.ruta_de(o["guion"]))
        if not os.path.exists(guion):
            continue
        if not t:
            if cola.alta(o["clave"], o["tipo"], o.get("pilar"), o.get("titulo"), guion, o.get("prioridad", 5), estado="guionizado"):
                nuevas += 1
        elif t["estado"] == "corregir" and o.get("version", 1) > json.loads(t["datos"] or "{}").get("version", 1):
            cola.mover(o["clave"], "guionizado", {"guion": guion}, datos=json.dumps({"version": o.get("version", 1)}))
    return nuevas


# ------------------------------------------------------------------ pasos
def carpeta_de(clave):
    p = K.TRABAJO / clave
    p.mkdir(parents=True, exist_ok=True)
    return p


def paso_generar(cola, t, aj):
    if t["estado"] == "guionizado":
        cola.mover(t["clave"], "generando")
    S = json.load(open(t["guion"], encoding="utf-8"))
    cf = comfy.Comfy(aj["comfy_url"])
    necesita = any(sc.get("visual", {}).get("type") == "image" for sc in S["scenes"])
    if necesita and aj.get("motor_imagen", "ninguno") != "comfyui":
        raise RuntimeError("este equipo no genera imágenes (motor_imagen = %s): el guion debe usar escenarios del motor "
                           "(plate, document, slate, board, map, timeline) en lugar de visual.type «image»" % aj.get("motor_imagen"))
    if necesita and not cf.disponible():
        raise RuntimeError("ComfyUI no responde en %s" % aj["comfy_url"])
    usadas = [f["variante"] for f in cola.firmas_recientes(S.get("pilar"))]
    Sm, inf = imagenes.preparar(S, carpeta_de(t["clave"]), cf if necesita else None, usadas, print)
    if Sm is None:
        raise RuntimeError("imágenes fallidas: %s" % json.dumps(inf["fallidas"], ensure_ascii=False)[:300])
    K.escribir_json(carpeta_de(t["clave"]) / "guion_motor.json", Sm)
    cola.guardar_firma(t["clave"], S.get("pilar"), Sm.get("variante"), calidad.firma(Sm))
    cola.mover(t["clave"], "editando", {"imagenes_ok": True})


def paso_montar(cola, t, aj):
    c = carpeta_de(t["clave"])
    Sm = json.load(open(c / "guion_motor.json", encoding="utf-8"))
    out = c / "render"
    py = aj["python_motor"] if os.path.exists(aj["python_motor"]) else sys.executable
    if t["tipo"] == "largo":
        cmd = [py, "-m", "arvis_expedientes.render_largo", str(c / "guion_motor.json"), "--out", str(out), "--plates", str(c / "plates"), "--stills", "auto"]
    else:
        cmd = [py, "-m", "arvis_expedientes.render_serie", str(c / "guion_motor.json"), "--out", str(out), "--plates", str(c / "plates"),
               "--stills", ",".join(str(x) for x in range(1, 58, 5))]
    log = open(K.LOGS / ("montaje_%s.log" % t["clave"]), "a")
    r = subprocess.run(cmd, cwd=str(K.MOTOR), stdout=log, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        raise RuntimeError("el motor terminó con código %d (ver logs/montaje_%s.log)" % (r.returncode, t["clave"]))
    sid = Sm["id"]
    rep_p = out / (sid + ".json")
    rep = json.load(open(rep_p, encoding="utf-8"))
    mp4 = rep.get("mp4_hq") or rep.get("mp4")       # Shorts: se sube la versión de calidad, no la de 4,7 MB
    if not rep.get("ok"):
        avisos.registrar("aviso", "%s: QC del motor %s/%s: %s" % (t["clave"], rep.get("passed"), rep.get("total"), "; ".join(rep.get("failed", []))[:300]))
    cola.mover(t["clave"], "validando", {"mp4": mp4, "informe": str(rep_p)})


def paso_validar(cola, t, aj, repo):
    c = carpeta_de(t["clave"])
    Sm = json.load(open(c / "guion_motor.json", encoding="utf-8"))
    rep_p = c / "render" / (Sm["id"] + ".json")
    rep = json.load(open(rep_p, encoding="utf-8"))
    if not repo or not repo.disponible():
        raise RuntimeError("sin repositorio de revisión: Control de calidad no puede ver los fotogramas")
    ev = repo.evaluacion(t["clave"])
    if not ev:
        stills = sorted(glob.glob(str(c / "render" / "*_still_*.png")))
        archivos = {"informe.json": str(rep_p), "guion_motor.json": str(c / "guion_motor.json")}
        for s in stills:
            jpg = Path(s).with_suffix(".jpg")
            if not jpg.exists():
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", s, "-vf", "scale=-2:720", "-q:v", "4", str(jpg)], check=True)
            archivos[jpg.name] = str(jpg)
        repo.publicar_revision(t["clave"], archivos)
        cola.anotar(t["clave"], error="esperando evaluación de E6 (Control de calidad)")
        return "esperando"
    recientes = [f for f in cola.firmas_recientes(Sm.get("pilar")) if f["clave"] != t["clave"]]
    titulos = [x["titulo"] for x in cola.lista(["publicado", "subido", "espera_manual"]) if x["titulo"] and x["clave"] != t["clave"]]
    res = calidad.evaluar(rep, ev, t["tipo"], aj["umbral_calidad"], calidad.firma(Sm), recientes, titulos,
                          stills_dir=str(repo.ruta_de("revision/" + t["clave"])))
    K.escribir_json(c / "calidad.json", res)
    if res["aprobado"]:
        cola.mover(t["clave"], "aprobado", {"puntuacion": res["total"], "evaluacion": "calidad.json"})
        avisos.notificar("Aprobado", "%s · %.1f/100" % (t["clave"], res["total"]))
    elif (t["reediciones"] or 0) >= aj["reediciones_max"]:
        cola.mover(t["clave"], "corregir", {"motivos": res["devolver_a"] or res["puertas"]}, puntuacion=res["total"])
        cola.mover(t["clave"], "descartado", {"motivo": "no llega a %s tras %d reediciones (%.1f)" % (aj["umbral_calidad"], aj["reediciones_max"], res["total"])})
        avisos.notificar("Descartado", "%s no llega a la nota (%.1f). No se publica." % (t["clave"], res["total"]), "aviso")
    else:
        cola.mover(t["clave"], "corregir", {"motivos": res["devolver_a"] or res["puertas"]}, puntuacion=res["total"])
        avisos.notificar("A corregir", "%s %.1f/100 → %s" % (t["clave"], res["total"], ", ".join(d["agente"] for d in res["devolver_a"])[:150]), "aviso")


def preparar_listo(t, rep, Sm):
    """Carpeta «listos/<clave>» con todo lo necesario para subir a mano o por API."""
    d = K.LISTOS / t["clave"]
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy2(t["mp4"], d / (t["clave"] + ".mp4"))
    for k in ("thumbnail", "cover"):
        if rep.get(k) and os.path.exists(rep[k]):
            shutil.copy2(rep[k], d / ("miniatura" + Path(rep[k]).suffix))
            break
    meta = {"title": rep.get("title"), "description": rep.get("description"), "tags": rep.get("tags", []),
            "categoryId": Sm.get("categoryId", "27"), "containsSyntheticMedia": bool(Sm.get("containsSyntheticMedia")),
            "formato": Sm.get("formato", "9:16"), "duracion_s": rep.get("duration_s")}
    K.escribir_json(d / "metadatos.json", meta)
    (d / "descripcion.txt").write_text((meta["title"] or "") + "\n\n" + (meta["description"] or ""), encoding="utf-8")
    return d, meta


def paso_publicar(cola, t, aj):
    c = carpeta_de(t["clave"])
    Sm = json.load(open(c / "guion_motor.json", encoding="utf-8"))
    rep = json.load(open(c / "render" / (Sm["id"] + ".json"), encoding="utf-8"))
    d, meta = preparar_listo(t, rep, Sm)
    modo = aj["subida_largo"] if t["tipo"] == "largo" else aj["subida_short"]
    if modo != "api" or not aj["integracion_youtube_auditada"]:
        motivo = "subida manual (decisión D3)" if modo == "manual" else \
            "la API de YouTube no está auditada: subir por API dejaría el vídeo privado para siempre" if modo == "api" else \
            "modo «%s»: este Mac no transporta vídeos por Make" % modo
        cola.mover(t["clave"], "espera_manual", {}, error=motivo)
        avisos.notificar("Listo para subir", "%s en %s · %s" % (t["clave"], d, motivo), "aviso")
        return
    from .youtube import OAuth, YouTube
    yt = YouTube(OAuth(), registro=print)
    canal = yt.canal()
    if aj["canal_id_esperado"] and canal["id"] != aj["canal_id_esperado"]:
        raise RuntimeError("canal incorrecto: %s (%s)" % (canal["titulo"], canal["id"]))
    priv = "public" if aj["publicacion_publica_autorizada"] else "private"
    r = yt.subir(str(d / (t["clave"] + ".mp4")), meta, priv, cola, t["clave"], t["publicar_en"], meta["containsSyntheticMedia"], auditada=True)
    cola.mover(t["clave"], "subido", {"video_id": r["video_id"], "privacidad_real": r["privacidad_real"]}, privacidad_pedida=r["privacidad_pedida"])
    mini = next(iter(d.glob("miniatura.*")), None)
    if t["tipo"] == "largo" and mini:
        try:
            yt.miniatura(r["video_id"], str(mini))
        except Exception as e:
            avisos.registrar("aviso", "%s: miniatura no aplicada: %s" % (t["clave"], e))


def paso_confirmar(cola, t, aj):
    from .youtube import OAuth, YouTube
    yt = YouTube(OAuth())
    e = yt.estado_video(t["video_id"])
    if not e:
        raise RuntimeError("YouTube no encuentra %s" % t["video_id"])
    cola.confirmar_publicacion(t["video_id"], e["privacyStatus"], e["uploadStatus"])
    if e["uploadStatus"] in ("failed", "rejected", "deleted"):
        cola.mover(t["clave"], "error", {"error": "YouTube: %s %s" % (e["uploadStatus"], e.get("failureReason") or e.get("rejectionReason") or "")})
    elif e["privacyStatus"] == "public":
        cola.mover(t["clave"], "publicado", {"confirmacion_api": e})
        avisos.notificar("Publicado", "%s · https://youtu.be/%s" % (t["clave"], t["video_id"]), "publicado", aj["make_webhook_avisos"])
    else:
        cola.anotar(t["clave"], privacidad_real=e["privacyStatus"])


# ------------------------------------------------------------------ tick
def tick():
    K.preparar_carpetas()
    aj = K.ajustes()
    cola = Cola(K.DB)
    repo = Repo(aj["repo_ordenes"]) if aj["repo_ordenes"] else None
    lock = open(K.ESTUDIO / ".tick.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return {"ocupado": True}
    try:
        latido(cola, aj, None, repo)
        for f in cola.recuperar():
            avisos.registrar("info", "recuperado %s (%s) tras corte" % (f["clave"], f["estado"]))
        if not disco.hay_espacio(K.ESTUDIO, aj["disco_min_gb"]):
            avisos.notificar("Sin espacio", "quedan %.1f GB; producción en pausa" % disco.libre_gb(K.ESTUDIO), "error", aj["make_webhook_avisos"])
            return {"pausa": "disco"}
        if repo and repo.disponible():
            try:
                repo.actualizar()
                n = importar_ordenes(cola, repo)
                if n:
                    avisos.registrar("info", "%d órdenes nuevas" % n)
            except RepoError as e:
                avisos.registrar("aviso", "repositorio: %s" % e)
        saltar = set()
        for x in cola.lista(["validando"]):
            if (x["error"] or "").startswith("esperando evaluación") and not (repo and repo.disponible() and repo.evaluacion(x["clave"])):
                saltar.add(x["clave"])
        for x in cola.lista(["subido"]):
            if time.time() - (x["actualizado"] or 0) < 1800:
                saltar.add(x["clave"])
        t = cola.siguiente(saltar)
        if not t:
            return {"nada": True, "en_espera": sorted(saltar)}
        if not cola.reservar(t["clave"], QUIEN, 240):
            return {"reservado": t["clave"]}
        lat = Latidor(cola, aj, t["clave"])
        lat.start()
        try:
            est = t["estado"]
            if est in ("guionizado", "generando"):
                paso_generar(cola, t, aj)
            elif est == "editando":
                paso_montar(cola, t, aj)
            elif est == "validando":
                paso_validar(cola, t, aj, repo)
            elif est == "aprobado":
                paso_publicar(cola, t, aj)
            elif est == "subido":
                paso_confirmar(cola, t, aj)
            return {"paso": est, "clave": t["clave"]}
        except (Exception, TransicionInvalida) as e:
            a_error = cola.fallo(t["clave"], t["estado"], str(e), aj["reintentos_paso"] + 1)
            avisos.notificar("Error" if a_error else "Reintento", "%s en %s: %s" % (t["clave"], t["estado"], str(e)[:160]),
                             "error" if a_error else "aviso", aj["make_webhook_avisos"] if a_error else None)
            return {"error": str(e), "clave": t["clave"]}
        finally:
            lat.parar.set()
            if cola.get(t["clave"])["bloqueo"]:
                cola.liberar(t["clave"])
            K.escribir_json(K.ESTADO, estado_actual(cola, aj, None))      # el latido refleja el resultado del paso
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)


def comprobar():
    aj = K.ajustes()
    res = {"motor_imagen": aj.get("motor_imagen", "ninguno")}
    if res["motor_imagen"] == "comfyui":
        cf = comfy.Comfy(aj["comfy_url"])
        res["comfyui"] = cf.estado().get("devices", [{}])[0].get("type") if cf.disponible() else "no responde"
    else:
        res["comfyui"] = "en pausa (este equipo no genera imágenes)"
    res["disco_libre_gb"] = round(disco.libre_gb(K.BASE), 1)
    res["motor_v4"] = (K.MOTOR / "arvis_expedientes" / "render.py").exists()
    res["parche_v42"] = (K.MOTOR / "arvis_expedientes" / "render_largo.py").exists()
    res["ffmpeg"] = shutil.which("ffmpeg") is not None
    res["repo_ordenes"] = bool(aj["repo_ordenes"]) and Repo(aj["repo_ordenes"]).disponible()
    try:
        from .youtube import OAuth, YouTube
        c = YouTube(OAuth()).canal()
        res["youtube_canal"] = "%s (%s)" % (c["titulo"], c["id"])
        res["canal_correcto"] = (not aj["canal_id_esperado"]) or c["id"] == aj["canal_id_esperado"]
    except Exception as e:
        res["youtube_canal"] = "sin conectar: %s" % str(e)[:120]
    res["integracion_youtube_auditada"] = aj["integracion_youtube_auditada"]
    return res


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("tick")
    sub.add_parser("estado")
    sub.add_parser("comprobar")
    e = sub.add_parser("encolar")
    e.add_argument("guion")
    e.add_argument("--tipo", required=True, choices=["largo", "short"])
    e.add_argument("--pilar", default="curiosidades")
    e.add_argument("--prioridad", type=int, default=5)
    v = sub.add_parser("vincular")
    v.add_argument("clave")
    v.add_argument("video_id")
    s = sub.add_parser("subir-prueba")
    s.add_argument("mp4")
    s.add_argument("titulo")
    lm = sub.add_parser("limpiar")
    lm.add_argument("--simular", action="store_true")
    a = ap.parse_args()
    if not K.base_disponible():
        # disco externo desconectado: no se crea nada ni se toca la cola; launchd lo reintentará
        print(json.dumps({"pausa": "volumen", "base": str(K.BASE)}, ensure_ascii=False))
        sys.exit(0 if a.cmd == "tick" else 2)
    K.preparar_carpetas()
    cola = Cola(K.DB)
    if a.cmd == "tick":
        print(json.dumps(tick(), ensure_ascii=False))
    elif a.cmd == "estado":
        print(json.dumps({"resumen": cola.resumen(), "trabajos": [{k: t[k] for k in ("clave", "tipo", "estado", "puntuacion", "video_id", "error")} for t in cola.lista()]},
                         ensure_ascii=False, indent=1))
    elif a.cmd == "comprobar":
        print(json.dumps(comprobar(), ensure_ascii=False, indent=1))
    elif a.cmd == "encolar":
        S = json.load(open(a.guion, encoding="utf-8"))
        ok = cola.alta(S["id"], a.tipo, a.pilar, S.get("title"), os.path.abspath(a.guion), a.prioridad, estado="guionizado")
        print("encolado" if ok else "ya existía %s (no se duplica)" % S["id"])
    elif a.cmd == "vincular":
        from .youtube import OAuth, YouTube
        e = YouTube(OAuth()).estado_video(a.video_id)
        if not e:
            sys.exit("YouTube no encuentra %s" % a.video_id)
        t = cola.get(a.clave)
        cola.registrar_publicacion(a.video_id, a.clave, t.get("sha256"), "manual", e["privacyStatus"], e["uploadStatus"], "https://youtu.be/" + a.video_id, "subida manual")
        cola.mover(a.clave, "subido", {"video_id": a.video_id, "privacidad_real": e["privacyStatus"]})
        if e["privacyStatus"] == "public":
            cola.mover(a.clave, "publicado", {"confirmacion_api": e})
        print(json.dumps(e, ensure_ascii=False))
    elif a.cmd == "subir-prueba":
        from .youtube import OAuth, YouTube
        yt = YouTube(OAuth())
        print("canal:", yt.canal())
        r = yt.subir(a.mp4, {"title": a.titulo, "description": "Prueba privada de ARVIS. No publicar.", "tags": ["prueba"]}, "private", cola,
                     None, None, False, auditada=False)
        print(json.dumps(r, ensure_ascii=False))
        print(json.dumps(yt.esperar_procesado(r["video_id"], timeout=900), ensure_ascii=False))
    elif a.cmd == "limpiar":
        print(json.dumps(disco.limpiar(cola, K.TRABAJO, K.ajustes()["intermedios_dias"], a.simular), ensure_ascii=False))


if __name__ == "__main__":
    main()
