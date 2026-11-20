"""Puntuación automática de RETENCIÓN (0–100) de un Short ya montado, con el porqué de cada punto.

No promete viralidad: mide lo que se sabe que hace que la gente siga mirando y lo compara después con los datos
reales (METRICAS / RETENCION) para recalibrar los pesos (analista).
  Gancho 25 · Ritmo 20 · Claridad visual 15 · Curiosidad e interés 15 · Duración y estructura 15 · Conversación 10
"""
import re

PESOS = {"gancho": 25, "ritmo": 20, "claridad": 15, "curiosidad": 15, "estructura": 15, "conversacion": 10}


def puntuar(g, info, motor):
    es = g["escenas"]
    n, notas = {}, {}
    # --- gancho (25)
    gan = es[0]
    voz_g = float(gan.get("_voz", 9))
    pal_g = len(gan["say"].split())
    p = 0
    p += 6 if gan["say"].strip().endswith("?") else 0
    p += 6 if voz_g <= 2.5 else (3 if voz_g <= 3.0 else 0)
    p += 4 if pal_g <= 9 else 2 if pal_g <= 11 else 0
    p += 3 if re.search(r"\b(tu|tus|te|ti|sabes|sabías|haces|usas)\b", gan["say"].lower()) else 0
    primeros = [el for el in motor.elems[0] if el.t_in <= 0.35]
    p += 3 if primeros else 0
    p += 3 if gan.get("titulo") else 0
    n["gancho"], notas["gancho"] = p, "pregunta=%s, %.2f s, %d palabras, %d elementos en 0,35 s" % (gan["say"].strip().endswith("?"), voz_g, pal_g, len(primeros))
    # --- ritmo (20)
    pal_s = info["palabras"] / max(1.0, info["duracion"])
    ev = sorted(set([0.0] + motor.eventos_visuales + [info["duracion"]]))
    huecos = [b - a for a, b in zip(ev, ev[1:])]
    max_hueco = max(huecos) if huecos else 99
    p = 0
    p += 8 if 2.6 <= pal_s <= 3.6 else 5 if 2.3 <= pal_s <= 3.8 else 1
    p += 8 if max_hueco <= 2.2 else 5 if max_hueco <= 3.0 else 1
    p += 4 if len(ev) / info["duracion"] >= 0.8 else 2
    n["ritmo"], notas["ritmo"] = p, "%.2f pal/s, mayor hueco sin novedad visual %.1f s, %d novedades" % (pal_s, max_hueco, len(ev))
    # --- claridad visual (15)
    max_simult = max(len(e.get("elementos", [])) for e in es)
    con_titulo = sum(1 for e in es if e.get("titulo") or any(el.get("tipo") == "texto" for el in e.get("elementos", [])))
    p = 0
    p += 5 if max_simult <= 6 else 2
    p += 5 if con_titulo >= len(es) - 1 else 3
    p += 5 if motor.subs else 0
    n["claridad"], notas["claridad"] = p, "máx. %d elementos por escena, %d/%d escenas con rótulo, subtítulos %s" % (max_simult, con_titulo, len(es), bool(motor.subs))
    # --- curiosidad (15)
    texto_gancho_problema = " ".join(e["say"] for e in es[:2])
    p = 0
    p += 6 if re.search(r"\d", texto_gancho_problema) else 2
    p += 4 if any(el.get("tipo") in ("contador", "barra") or re.search(r"\d", str(el.get("texto", ""))) for e in es[:3] for el in e.get("elementos", [])) else 0
    p += 5 if re.search(r"\b(error|nunca|de verdad|en realidad|casi nadie|truco|secreto|sabías)\b", texto_gancho_problema.lower()) else 2
    n["curiosidad"], notas["curiosidad"] = p, "dato con cifra en los primeros segundos: %s" % bool(re.search(r"\d", texto_gancho_problema))
    # --- estructura y duración (15)
    d = info["duracion"]
    p = 0
    p += 6 if 22 <= d <= 38 else 4 if 20 <= d <= 45 else 0
    problema_t = next((e["_t0"] for e in es if e["beat"] == "problema"), 9)
    p += 4 if problema_t <= 3.0 else 1
    cta = es[-1]
    p += 5 if cta.get("_voz", 9) <= 4.6 else 2
    n["estructura"], notas["estructura"] = p, "%.1f s, problema en %.1f s, cierre %.1f s" % (d, problema_t, cta.get("_voz", 0))
    # --- conversación (10)
    c = cta["say"].lower()
    p = 0
    p += 5 if re.search(r"guárda|guarda|comparte|comenta|dime|cuéntame", c) else 0
    p += 5 if re.search(r"sígueme|sigue|suscríbete|cada día", c) else 2
    n["conversacion"], notas["conversacion"] = p, "cierre: «%s»" % cta["say"]
    total = sum(n.values())
    return {"total": total, "desglose": n, "detalle": notas, "pesos": PESOS}
