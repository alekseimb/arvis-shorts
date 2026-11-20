"""LIFEHACKS RESEARCHER · puntuación 1–100 de cada idea y selección automática de las 3 mejores del día.

La investigación (problemas reales, herramientas gratuitas nuevas, tendencias de búsqueda) la hace el agente con
búsqueda web; este módulo aplica la rúbrica de forma reproducible, evita repetir lo publicado y reparte categorías.

Rúbrica (pesos ajustables por SHORTS PERFORMANCE ANALYST, ver analista.py):
  utilidad 25 · interés del público 20 · facilidad para demostrarlo 20 · retención 15 · originalidad 10 · conversación 10
Cada criterio se puntúa 0–10 CON una evidencia de ≥ 12 caracteres; sin evidencia, vale 0.
Topes: si no se puede grabar de verdad en el entorno de ARVIS («no_grabable»), «demostrable» ≤ 3; si necesita más de
60 s, «retención» ≤ 4. Ideas casi iguales a un vídeo publicado (≥ 0,62 de parecido) quedan fuera.

Uso: python3 -m arvis_lifehacks.ideas ideas.json --publicados titulos.json [--pesos pesos.json] [--n 3] [--minimo 60]
"""
import argparse
import difflib
import json
import re
import unicodedata

PESOS = {"utilidad": 25, "interes": 20, "demostrable": 20, "retencion": 15, "originalidad": 10, "conversacion": 10}
DEMOS_GRABABLES = {"escritorio", "terminal", "web", "mixta", "2d"}  # 2d = animación de ARVIS VIDA (20/11/2026)


def _norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", s).strip()


def parecido(a, b):
    a, b = _norm(a), _norm(b)
    base = difflib.SequenceMatcher(None, a, b).ratio()
    pa, pb = set(a.split()) - {"como", "con", "tu", "tus", "en", "de", "la", "el", "los", "las", "un", "una", "y", "que", "para", "sin"}, set(b.split())
    jac = len(pa & pb) / max(1, len(pa | pb))
    return round(max(base, jac * 1.1), 3)


def puntuar(idea, pesos=None, publicados=(), mult_categoria=None):
    pesos = pesos or PESOS
    notas, evid = idea.get("notas", {}), idea.get("evidencias", {})
    desglose, avisos = {}, []
    for k, w in pesos.items():
        n = notas.get(k)
        e = str(evid.get(k, "")).strip()
        if not isinstance(n, (int, float)) or len(e) < 12:
            desglose[k] = 0.0
            avisos.append("%s sin evidencia" % k)
            continue
        n = max(0.0, min(10.0, float(n)))
        if k == "demostrable" and idea.get("demo") not in DEMOS_GRABABLES:
            n = min(n, 3.0)
            avisos.append("no se puede grabar de verdad aquí")
        if k == "retencion" and idea.get("segundos_estimados", 40) > 60:
            n = min(n, 4.0)
            avisos.append("necesita más de 60 s")
        desglose[k] = round(w * n / 10.0, 1)
    total = sum(desglose.values())
    m = (mult_categoria or {}).get(idea.get("categoria"), 1.0)
    total = round(max(1.0, min(100.0, total * m)), 1)
    sim, con = 0.0, None
    for t in publicados:
        s = parecido(idea["titulo"], t)
        if s > sim:
            sim, con = s, t
    duplicada = sim >= 0.62
    if duplicada:
        avisos.append("casi igual a «%s» (%.2f)" % (con, sim))
    return {"titulo": idea["titulo"], "categoria": idea.get("categoria"), "puntuacion": total, "desglose": desglose,
            "multiplicador": m, "parecido_max": sim, "duplicada": duplicada, "avisos": avisos}


def seleccionar(ideas, publicados=(), pesos=None, mult_categoria=None, n=3, minimo=60):
    res = []
    for i in ideas:
        r = puntuar(i, pesos, publicados, mult_categoria)
        r["idea"] = i
        res.append(r)
    res.sort(key=lambda r: -r["puntuacion"])
    elegidas, cats = [], set()
    for r in res:  # 1.ª pasada: una por categoría
        if len(elegidas) == n:
            break
        if not r["duplicada"] and r["puntuacion"] >= minimo and r["categoria"] not in cats \
                and all(parecido(r["titulo"], e["titulo"]) < 0.62 for e in elegidas):
            elegidas.append(r)
            cats.add(r["categoria"])
    for r in res:  # 2.ª pasada: si faltan, se repite categoría (nunca por debajo del mínimo)
        if len(elegidas) == n:
            break
        if r not in elegidas and not r["duplicada"] and r["puntuacion"] >= minimo \
                and all(parecido(r["titulo"], e["titulo"]) < 0.62 for e in elegidas):
            elegidas.append(r)
    return {"ranking": res, "elegidas": elegidas, "faltan": n - len(elegidas)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ideas")
    ap.add_argument("--publicados", default=None)
    ap.add_argument("--pesos", default=None)
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--minimo", type=float, default=60)
    a = ap.parse_args()
    ideas = json.load(open(a.ideas, encoding="utf-8"))
    pub = json.load(open(a.publicados, encoding="utf-8")) if a.publicados else []
    cfg = json.load(open(a.pesos, encoding="utf-8")) if a.pesos else {}
    out = seleccionar(ideas, pub, cfg.get("pesos"), cfg.get("multiplicador_categoria"), a.n, a.minimo)
    salida = {"elegidas": out["elegidas"], "faltan": out["faltan"],
              "ranking": [{k: v for k, v in r.items() if k != "idea"} for r in out["ranking"]]}
    print(json.dumps(salida, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
