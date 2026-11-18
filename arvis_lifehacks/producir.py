"""Producción completa de un LIFEHACKS: herramienta probada → grabaciones reales → voz → montaje → QC → informe.

Uso:  python3 -m arvis_lifehacks.producir tutoriales/SH-0NN/guion.json --out out/SH-0NN
Salida en --out: SH-0NN.mp4 (≤ 4,6 MB, para Make), SH-0NN_hq.mp4, SH-0NN.srt, SH-0NN_portada.jpg, stills/,
SH-0NN.json (informe con las 22 comprobaciones, apto para arvis_estudio.calidad), SH-0NN_storyboard.md,
SH-0NN_evaluacion.json (plantilla para que Control de calidad la rellene con evidencias), herramienta.json.
Código de salida: 0 = vídeo montado (mirar el QC); 2 = la herramienta no pasa revisión o pruebas (no se graba nada).
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import time

from . import constructor, grabar, publicar, qc
from .montaje import Montaje


def storyboard(g, ruta):
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("# Storyboard %s · %s\n\n" % (g["id"], g["title"]))
        for i, e in enumerate(g["escenas"], 1):
            v = e["visual"]
            f.write("%d. **%s** %.1f–%.1f s · %s%s\n   - Voz: %s\n" % (
                i, e["beat"].upper(), e["_t0"], e["_t1"], v["tipo"],
                (" · paso %s" % e["paso"]) if e.get("paso") else "", e["say"]))
            if e.get("rotulo"):
                f.write("   - Rótulo: %s\n" % e["rotulo"].replace("\n", " / "))
            if e.get("titulo_paso"):
                f.write("   - Paso en pantalla: %s\n" % e["titulo_paso"])


def producir(ruta_guion, out):
    t_ini = time.time()
    g = json.load(open(ruta_guion, encoding="utf-8"))
    base = os.path.dirname(os.path.abspath(ruta_guion))
    os.makedirs(out, exist_ok=True)
    if os.path.isdir(os.path.join(out, "stills")):
        shutil.rmtree(os.path.join(out, "stills"))
    h = constructor.construir(g, base, out)
    if not h["ok"]:
        print(json.dumps({"ok": False, "motivo": "herramienta", "revision": h["hallazgos"], "pruebas": h["pruebas"]["log"][-800:],
                          "sesiones_ok": {k: s["ok"] for k, s in h["sesiones"].items()}}, ensure_ascii=False, indent=1))
        return 2
    capturas = {}
    for c in g.get("capturas", []):
        if c["tipo"] == "web":
            capturas[c["id"]] = grabar.capturar_web(c, h["carpeta_trabajo"], out)
        elif c["tipo"] == "escritorio":
            capturas[c["id"]] = grabar.capturar_escritorio(c, h["carpeta_trabajo"], out)
    if h.get("tipo") == "truco":
        verifs = [v for c in capturas.values() for v in c.get("verificaciones", [])]
        h["pruebas"] = {"ok": bool(verifs) and all(v["ok"] for v in verifs), "tests": len(verifs),
                        "log": json.dumps(verifs, ensure_ascii=False)}
        h["ok"] = h["revision_ok"] and h["pruebas"]["ok"]
        json.dump(h, open(os.path.join(out, "herramienta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if not h["ok"]:
            print(json.dumps({"ok": False, "motivo": "el truco no se pudo verificar en la grabación", "verificaciones": verifs}, ensure_ascii=False))
            return 2
    m = Montaje(g, h, capturas, base, out)
    info = m.render(g["id"])
    codigo = None
    if g.get("codigo_en_descripcion"):
        codigo = open(os.path.join(h["carpeta_trabajo"], g["codigo_en_descripcion"]), encoding="utf-8").read()
    g["_descripcion"] = publicar.descripcion(g, codigo)
    sb = os.path.join(out, g["id"] + "_storyboard.md")
    storyboard(g, sb)
    rep = qc.comprobar(info["make"], info["hq"], g, h, capturas, info, m.voz, m.subs, g["escenas"], sb)
    # portada: fotograma del resultado
    k = next((i for i, e in enumerate(g["escenas"]) if e["beat"] == "resultado"), 0)
    if k in m.miniaturas:
        m.miniaturas[k].save(os.path.join(out, g["id"] + "_portada.jpg"), quality=90)
    sha = hashlib.sha256(open(info["make"], "rb").read()).hexdigest()
    rep.update({
        "id": g["id"], "serie": "lifehacks", "numero": g.get("numero"), "categoria": g.get("categoria"),
        "gancho_tecnica": g.get("gancho_tecnica"), "palabras": info["palabras"],
        "pal_s": round(info["palabras"] / max(1, info["duracion"]), 2),
        "escenas": [{"beat": e["beat"], "t0": round(e["_t0"], 2), "t1": round(e["_t1"], 2), "tipo": e["visual"]["tipo"], "say": e["say"]} for e in g["escenas"]],
        "sha256": sha, "archivo_make": os.path.basename(info["make"]), "archivo_hq": os.path.basename(info["hq"]),
        "descripcion": g["_descripcion"], "tags": g.get("tags", []), "categoryId": g.get("categoryId", "28"),
        "pruebas_herramienta": h["pruebas"]["tests"], "segundos_produccion": round(time.time() - t_ini, 1),
        "motor": "arvis_lifehacks 1.0",
    })
    json.dump(rep, open(os.path.join(out, g["id"] + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    from arvis_estudio.calidad import plantilla_evaluacion
    ev = plantilla_evaluacion()
    ev["titulo"] = g["title"]
    json.dump(ev, open(os.path.join(out, g["id"] + "_evaluacion.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"ok": True, "qc": "%d/%d" % (rep["passed"], rep["total"]), "fallos": [c["check"] + ": " + c["detalle"] for c in rep["checks"] if not c["ok"]],
                      "duracion": rep["duration_s"], "mb": rep["mb"], "lufs": rep["lufs"], "segundos": rep["segundos_produccion"]},
                     ensure_ascii=False, indent=1))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("guion")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    sys.exit(producir(a.guion, a.out))


if __name__ == "__main__":
    main()
