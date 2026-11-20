"""Producción completa de un Short de ARVIS VIDA con corrección automática.

  guion → validación (GUIONISTA) → voz + render (MOTOR) → QC medido (CONTROL DE CALIDAD) → retención automática
  → si algo falla y tiene arreglo automático, se corrige y se vuelve a montar (máx. 2 veces) → informe + plantilla de evaluación.

Uso:  python3 -m arvis_vida.producir guiones_vida/SH-0NN/guion.json --out out/SH-0NN [--publicados titulos.json]
Salida: SH-0NN.mp4 (≤ 4,6 MB, para Make), SH-0NN_hq.mp4, SH-0NN.srt, stills/, SH-0NN_storyboard.md, SH-0NN.json (informe con
        las comprobaciones, apto para arvis_estudio.calidad), SH-0NN_evaluacion.json (plantilla), metadatos.json (para la subida).
Código de salida: 0 = vídeo montado y QC completo; 1 = montado con fallos de QC; 2 = guion rechazado (no se monta nada).
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import time

from arvis_lifehacks.config import CREDITO_VOZ
from arvis_lifehacks.publicar import a_utc, limpiar  # noqa: F401  (a_utc lo usa el publicador)
from . import __version__, activos, guion as guion_mod, qc, retencion
from .motor import Motor

DESCRIPCION_PIE = ("Animación 2D creada por el canal (recreación explicativa, no es una grabación real). Narración con voz sintética. "
                   "Música y efectos creados por el canal.")


def descripcion(g):
    partes = [g["description"].strip(), ""]
    if g.get("sources"):
        partes += ["Fuentes (consultadas el %s):" % g.get("hechos", [{}])[0].get("leido", "")] + ["• " + u for u in g["sources"]] + [""]
    num = "LIFEHACKS · Nº %03d" % int(g["numero"]) if g.get("numero") is not None else "LIFEHACKS"
    partes += [num + " · Trucos de la vida real para casa, cocina, ahorro y ropa.", DESCRIPCION_PIE,
               CREDITO_VOZ.get(g.get("voice", "sharvard_m"), ""), activos.CREDITO_ICONOS, "", " ".join(g.get("hashtags", ["#Shorts"]))]
    return limpiar("\n".join(p for p in partes if p is not None))[:4900]


def metadatos(g, publish_at=""):
    return {"title": limpiar(g["title"])[:100], "description": g["_descripcion"], "tags": g.get("tags", [])[:15],
            "categoryId": g.get("categoryId", "26"), "privacyStatus": "private", "publishAt": publish_at, "key": g["id"]}


def storyboard(g, ruta):
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("# Storyboard %s · %s\n\n" % (g["id"], g["title"]))
        for i, e in enumerate(g["escenas"], 1):
            f.write("%d. **%s** %.1f–%.1f s · %s · cámara %s · transición %s\n   - Voz: %s\n   - Elementos: %s\n" % (
                i, e["beat"].upper() + (" %d" % e["paso"] if e.get("paso") else ""), e["_t0"], e["_t1"], e.get("fondo"), e.get("camara", "empuje"),
                e.get("transicion", "barrido") if i > 1 else "—", e["say"],
                ", ".join(el.get("activo") or el.get("tipo") for el in e.get("elementos", []))))
            if e.get("titulo"):
                f.write("   - Rótulo: %s\n" % e["titulo"].replace("\n", " / "))


ARREGLOS = {
    "Duración": lambda p: p.update(ritmo=p["ritmo"] * 0.93),
    "Gancho": lambda p: p.update(ritmo_gancho=p["ritmo_gancho"] * 0.9),
    "movimiento": lambda p: p.update(sin_fija=True),
    "Ritmo de voz": lambda p: p.update(ritmo=p["ritmo"] * (0.94 if p.get("rapido") else 1.06)),
}


def producir(ruta, out, publicados=()):
    t_ini = time.time()
    g = json.load(open(ruta, encoding="utf-8"))
    val = guion_mod.validar(g, publicados)
    if not val["ok"]:
        print(json.dumps({"ok": False, "motivo": "guion", **val}, ensure_ascii=False, indent=1))
        return 2
    activos.preparar_fluent()
    os.makedirs(out, exist_ok=True)
    g["_descripcion"] = descripcion(g)
    params = {"ritmo": 1.0, "ritmo_gancho": float(g["escenas"][0].get("ritmo", 0.93)), "sin_fija": False}
    intentos = []
    for intento in range(1, 4):
        if os.path.isdir(os.path.join(out, "stills")):
            shutil.rmtree(os.path.join(out, "stills"))
        g["escenas"][0]["ritmo"] = params["ritmo_gancho"]
        if params["sin_fija"]:
            for e in g["escenas"]:
                if e.get("camara") == "fija":
                    e["camara"] = "empuje"
        m = Motor(g, out)
        info = m.render(g["id"], params["ritmo"])
        storyboard(g, os.path.join(out, g["id"] + "_storyboard.md"))
        rep = qc.comprobar(g, info, m, out, publicados)
        ret = retencion.puntuar(g, info, m)
        rep["checks"].append({"check": "Gancho y retención automática ≥ 70/100", "ok": ret["total"] >= 70, "detalle": "%d/100 %s" % (ret["total"], ret["desglose"])})
        rep["passed"] = sum(1 for c in rep["checks"] if c["ok"])
        rep["total"] = len(rep["checks"])
        fallos = [c["check"] for c in rep["checks"] if not c["ok"]]
        intentos.append({"intento": intento, "qc": "%d/%d" % (rep["passed"], rep["total"]), "fallos": fallos, "params": dict(params)})
        arreglables = [k for k in ARREGLOS if any(k in f for f in fallos)]
        if not fallos or not arreglables or intento == 3:
            break
        params["rapido"] = info["palabras"] / max(1, info["duracion"]) > 3.8
        for k in arreglables:
            ARREGLOS[k](params)
    sha = hashlib.sha256(open(info["make"], "rb").read()).hexdigest()
    rep.update({"id": g["id"], "serie": "lifehacks", "formato": "lifehacks-vida", "numero": g.get("numero"), "categoria": g.get("categoria"),
                "title": g["title"], "gancho_tecnica": g.get("gancho_tecnica"), "palabras": info["palabras"],
                "pal_s": round(info["palabras"] / max(1, info["duracion"]), 2), "retencion": ret,
                "escenas": [{"beat": e["beat"], "t0": e["_t0"], "t1": e["_t1"], "fondo": e.get("fondo"), "camara": e.get("camara", "empuje"),
                             "transicion": e.get("transicion", "barrido"), "say": e["say"],
                             "elementos": [el.get("activo") or el.get("tipo") for el in e.get("elementos", [])]} for e in g["escenas"]],
                "sha256": sha, "archivo_make": os.path.basename(info["make"]), "archivo_hq": os.path.basename(info["hq"]),
                "descripcion": g["_descripcion"], "tags": g.get("tags", []), "categoryId": g.get("categoryId", "26"),
                "intentos": intentos, "segundos_produccion": round(time.time() - t_ini, 1), "segundos_render": info["segundos_render"],
                "motor": "arvis_vida %s" % __version__, "stills": m.stills, "containsSyntheticMedia": False,
                "firma": {"variante": g.get("variante"), "pasos": ["%s|%s|%s" % (e.get("fondo"), e.get("camara", "empuje"), e.get("transicion", "barrido"))
                                                                  for e in g["escenas"]]}})
    json.dump(rep, open(os.path.join(out, g["id"] + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(metadatos(g), open(os.path.join(out, "metadatos.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    from arvis_estudio.calidad import plantilla_evaluacion
    ev = plantilla_evaluacion()
    ev["titulo"] = g["title"]
    json.dump(ev, open(os.path.join(out, g["id"] + "_evaluacion.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    fallos = [c["check"] + ": " + c["detalle"] for c in rep["checks"] if not c["ok"]]
    print(json.dumps({"ok": not fallos, "qc": "%d/%d" % (rep["passed"], rep["total"]), "fallos": fallos, "retencion": ret["total"],
                      "duracion": rep["duration_s"], "mb": rep["mb"], "lufs": rep["lufs"], "segundos": rep["segundos_produccion"],
                      "intentos": len(intentos), "avisos_guion": rep["avisos_guion"]}, ensure_ascii=False, indent=1))
    return 0 if not fallos else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("guion")
    ap.add_argument("--out", required=True)
    ap.add_argument("--publicados", default=None)
    a = ap.parse_args()
    pub = json.load(open(a.publicados, encoding="utf-8")) if a.publicados else []
    sys.exit(producir(a.guion, a.out, pub))


if __name__ == "__main__":
    main()
