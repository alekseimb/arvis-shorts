"""SHORTS PERFORMANCE ANALYST · aprende de los resultados reales de cada LIFEHACKS.

Entrada: lista de vídeos con sus métricas reales (Make 8260190 y, si está instalado, ARVIS_ANALITICA):
  {id, titulo, categoria, gancho_tecnica, duracion, franja ("12:00"…), horas, vistas, me_gusta, comentarios,
   compartidos?, suscriptores?, pct_visto?, retencion_3s?, visto_vs_deslizado?, duracion_media?}
Salida: rendimiento por categoría, técnica de gancho, duración y franja; multiplicadores de categoría para el
LIFEHACKS RESEARCHER (0,75–1,25, solo con ≥ 3 vídeos por grupo); duración recomendada; y propuestas de franja
(solo con ≥ 10 vídeos por franja y diferencia > 25 %; nunca cambia el número de vídeos al día).
Nunca repite vídeos: solo reutiliza aprendizajes. Nunca saca conclusiones de un solo vídeo.

Uso: python3 -m arvis_lifehacks.analista metricas.json [--anterior pesos.json] > pesos_nuevos.json
"""
import argparse
import json
import statistics


def _rend(v):
    """Rendimiento relativo: vistas por hora (las primeras 48 h), corregido por retención si existe."""
    h = max(1.0, min(float(v.get("horas") or 1), 48.0))
    base = float(v.get("vistas") or 0) / h
    if v.get("visto_vs_deslizado") is not None:
        base *= 0.5 + float(v["visto_vs_deslizado"]) / 100
    if v.get("pct_visto") is not None:
        base *= 0.5 + min(1.5, float(v["pct_visto"]) / 100)
    inter = (float(v.get("me_gusta") or 0) + 3 * float(v.get("comentarios") or 0) + 4 * float(v.get("compartidos") or 0)
             + 10 * float(v.get("suscriptores") or 0)) / max(1.0, float(v.get("vistas") or 1))
    return base * (1 + min(0.5, inter * 5))


def _grupos(vs, clave):
    g = {}
    for v in vs:
        g.setdefault(v.get(clave) or "¿?", []).append(v["_r"])
    return g


def analizar(videos, anterior=None):
    vs = [dict(v) for v in videos if v.get("vistas") is not None]
    for v in vs:
        v["_r"] = _rend(v)
        d = float(v.get("duracion") or 0)
        v["_tramo"] = "≤30 s" if d <= 30 else ("30–40 s" if d <= 40 else "40–50 s")
    out = {"videos_analizados": len(vs), "nota": "", "categorias": {}, "ganchos": {}, "duracion": {}, "franjas": {},
           "multiplicador_categoria": dict((anterior or {}).get("multiplicador_categoria", {})),
           "duracion_recomendada": (anterior or {}).get("duracion_recomendada", [30, 45]), "propuestas_franja": [], "mejores": []}
    if len(vs) < 3:
        out["nota"] = "Menos de 3 vídeos con métricas: sin cambios de estrategia (nunca por un solo vídeo)."
        return out
    med = statistics.median(v["_r"] for v in vs) or 1e-6
    for nombre, clave in (("categorias", "categoria"), ("ganchos", "gancho_tecnica"), ("duracion", "_tramo"), ("franjas", "franja")):
        for k, lista in _grupos(vs, clave).items():
            out[nombre][k] = {"videos": len(lista), "indice": round(statistics.mean(lista) / med, 2)}
    for cat, d in out["categorias"].items():
        if d["videos"] >= 3:
            prev = out["multiplicador_categoria"].get(cat, 1.0)
            objetivo = max(0.75, min(1.25, d["indice"]))
            out["multiplicador_categoria"][cat] = round(prev + max(-0.1, min(0.1, objetivo - prev)), 2)   # pasos ≤ 0,1
    tramos = [(k, d) for k, d in out["duracion"].items() if d["videos"] >= 3]
    if tramos:
        mejor = max(tramos, key=lambda x: x[1]["indice"])[0]
        out["duracion_recomendada"] = {"≤30 s": [25, 30], "30–40 s": [30, 40], "40–50 s": [40, 50]}[mejor]
    fr = {k: d for k, d in out["franjas"].items() if d["videos"] >= 10}
    if len(fr) >= 2:
        peor = min(fr, key=lambda k: fr[k]["indice"])
        mejor = max(fr, key=lambda k: fr[k]["indice"])
        if fr[mejor]["indice"] > fr[peor]["indice"] * 1.25:
            out["propuestas_franja"].append("Mover la franja de las %s una hora hacia la de las %s (índice %.2f frente a %.2f, ≥ 10 vídeos cada una)"
                                            % (peor, mejor, fr[peor]["indice"], fr[mejor]["indice"]))
    out["mejores"] = [{"id": v["id"], "titulo": v.get("titulo"), "indice": round(v["_r"] / med, 2)} for v in sorted(vs, key=lambda v: -v["_r"])[:5]]
    out["nota"] = "Índice 1,00 = mediana del canal (vistas por hora en las primeras 48 h, corregidas por retención e interacción si hay datos)."
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("metricas")
    ap.add_argument("--anterior", default=None)
    a = ap.parse_args()
    vids = json.load(open(a.metricas, encoding="utf-8"))
    ant = json.load(open(a.anterior, encoding="utf-8")) if a.anterior else None
    print(json.dumps(analizar(vids, ant), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
