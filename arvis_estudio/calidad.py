"""Evaluador de calidad 0–100 (rúbrica del 18/11/2026) · umbral 85.

  Guion 20 · Gancho y retención 20 · Calidad visual 20 · Narración y sonido 15 · Originalidad y valor 15 · Edición y acabado 10

Cómo evita las notas inventadas:
  1. Cada criterio necesita evidencias concretas (segundo del vídeo dentro de su duración + motivo de ≥ 12 caracteres)
     y, para lo visual, el fotograma revisado (archivo que existe). Sin evidencia válida, el criterio vale 0.
  2. Las mediciones automáticas del motor ponen TOPES: aunque el evaluador ponga 10, si el sonido no cumple
     −14 LUFS, «Narración y sonido» no pasa de 9/15, etc. El tope gana siempre.
  3. Puertas que no se compensan con puntos: veracidad, ética, contenido sintético declarado, QC técnico.
  4. Anti-plantilla: se compara la «firma» visual con los últimos vídeos del mismo pilar; si se parece demasiado,
     Calidad visual y Originalidad tienen tope.
Si no llega a 85, cada criterio flojo se devuelve a su agente con el arreglo concreto.

Uso:  python3 -m arvis_estudio.calidad informe_motor.json evaluacion.json [--firmas firmas.json] [--titulos titulos.json]
"""
import argparse
import difflib
import json
import os

PESOS = {"guion": 20, "gancho_retencion": 20, "visual": 20, "narracion_sonido": 15, "originalidad": 15, "edicion": 10}
NOMBRES = {"guion": "Calidad del guion", "gancho_retencion": "Gancho y retención", "visual": "Calidad visual",
           "narracion_sonido": "Narración y sonido", "originalidad": "Originalidad y valor aportado", "edicion": "Edición y acabado"}
RESPONSABLE = {"guion": "E3 Guionista", "gancho_retencion": "E3 Guionista (con E2 ganchos)", "visual": "E4 Director creativo + E9 Generador de imágenes",
               "narracion_sonido": "E10 Narrador (+ E5 música y efectos)", "originalidad": "E0 Director audiovisual + E1 Investigación",
               "edicion": "E5 Editor"}
ARREGLO = {
    "guion": "Reescribir los tramos señalados: un hecho comprobado por frase, sin relleno, distinguiendo hecho, opinión e hipótesis.",
    "gancho_retencion": "Gancho más concreto en la primera frase y una revelación nueva antes de cada punto donde cae el interés.",
    "visual": "Sustituir las escenas señaladas por imágenes que muestren exactamente lo que se dice; cambiar plano o movimiento donde se repite.",
    "narracion_sonido": "Frases más cortas y pausas marcadas; ajustar música (≥ 12 dB bajo la voz) y efectos solo en los cambios.",
    "originalidad": "Aportar el dato o ángulo que no está en otros vídeos; si el tema ya se hizo, cambiar el enfoque o descartarlo.",
    "edicion": "Corregir los fallos técnicos del QC (subtítulos, cortes, negros, sincronía) y volver a montar.",
}
MIN_MOTIVO = 12


def _peso_tope(nombre, frac):
    return round(PESOS[nombre] * frac, 1)


def topes_automaticos(rep, tipo):
    """rep: informe del motor (checks, passed, total, duration_s…). Devuelve {criterio: (tope, motivo)}."""
    t = {}
    fallos = {c["check"]: c for c in rep.get("checks", []) if not c.get("ok")}

    def fallo(*palabras):
        return [k for k in fallos if any(p.lower() in k.lower() for p in palabras)]

    def poner(crit, frac, motivo):
        tope = _peso_tope(crit, frac)
        if crit not in t or tope < t[crit][0]:
            t[crit] = (tope, motivo)

    for k in fallo("Fuentes"):
        poner("guion", 0.4, k)
    for k in fallo("cifras"):
        poner("guion", 0.75, k)
    for k in fallo("Gancho"):
        poner("gancho_retencion", 0.6, k)
    for k in fallo("Capítulos", "Estructura"):
        poner("gancho_retencion", 0.7, k)
    for k in fallo("repetidas"):
        poner("visual", 0.5, k)
    for k in fallo("estáticos", "movimiento"):
        poner("visual", 0.6, k)
    for k in fallo("negros"):
        poner("visual", 0.3, k)
    for k in fallo("Variedad"):
        poner("visual", 0.7, k)
    for k in fallo("Sonoridad"):
        poner("narracion_sonido", 0.6, k)
    for k in fallo("silencios", "Ritmo de voz"):
        poner("narracion_sonido", 0.7, k)
    for k in fallo("Decodifica", "Formato"):
        poner("edicion", 0.0, k)
        poner("narracion_sonido", 0.0, k)
    for k in fallo("Subtítulos"):
        poner("edicion", 0.5, k)
    for k in fallo("Storyboard", "Miniatura"):
        poner("edicion", 0.7, k)
    for k in fallo("etiquet", "sintético"):
        poner("edicion", 0.5, k)
    return t


def firma(guion):
    """Firma de plantilla: secuencia de (tipo, movimiento, transición, gradación) + variante de estilo."""
    pasos = []
    for sc in guion.get("scenes", []):
        v = sc.get("visual", {})
        pasos.append("%s|%s|%s|%s" % (v.get("type"), v.get("move", ""), sc.get("transition", "fade"), v.get("grade", "")))
    return {"variante": guion.get("variante"), "pasos": pasos}


def parecido(f1, f2):
    a = difflib.SequenceMatcher(None, f1["pasos"], f2["pasos"]).ratio()
    return round(0.8 * a + 0.2 * (1.0 if f1.get("variante") and f1.get("variante") == f2.get("variante") else 0.0), 3)


def evaluar(rep, ev, tipo="short", umbral=85, firma_actual=None, firmas_recientes=(), titulos_recientes=(), stills_dir=None):
    dur = float(rep.get("duration_s") or 0)
    crit = ev.get("criterios", {})
    desglose, faltan, evidencias = {}, [], {}
    for nombre, peso in PESOS.items():
        c = crit.get(nombre) or {}
        nota = c.get("nota")
        evs = c.get("evidencias") or []
        validas = []
        for e in evs:
            seg, mot = e.get("segundo"), str(e.get("motivo") or "").strip()
            if not isinstance(seg, (int, float)) or seg < 0 or (dur and seg > dur + 0.5) or len(mot) < MIN_MOTIVO:
                continue
            if nombre == "visual" and stills_dir:
                f = e.get("fotograma")
                if not f or not os.path.exists(os.path.join(stills_dir, f)):
                    continue
            validas.append(e)
        evidencias[nombre] = len(validas)
        if not isinstance(nota, (int, float)) or not validas:
            desglose[nombre] = 0.0
            faltan.append(NOMBRES[nombre] + " (sin evidencia válida)")
            continue
        desglose[nombre] = round(peso * max(0.0, min(10.0, float(nota))) / 10.0, 1)
    topes = topes_automaticos(rep, tipo)
    sim_max, sim_con = 0.0, None
    if firma_actual:
        for f in firmas_recientes:
            s = parecido(firma_actual, f["firma"])
            if s > sim_max:
                sim_max, sim_con = s, f.get("clave")
        if sim_max >= 0.75:
            topes["visual"] = min(topes.get("visual", (99, "")), (_peso_tope("visual", 0.7), "plantilla repetida (%.0f %% igual a %s)" % (sim_max * 100, sim_con)))
            topes["originalidad"] = min(topes.get("originalidad", (99, "")), (_peso_tope("originalidad", 0.6), "plantilla repetida"))
    tit = ev.get("titulo") or rep.get("title") or ""
    for t in titulos_recientes:
        if tit and difflib.SequenceMatcher(None, tit.lower(), t.lower()).ratio() >= 0.8:
            topes["originalidad"] = min(topes.get("originalidad", (99, "")), (_peso_tope("originalidad", 0.4), "tema casi igual a «%s»" % t))
            break
    aplicados = {}
    for k, (tope, motivo) in topes.items():
        if desglose.get(k, 0) > tope:
            aplicados[k] = {"antes": desglose[k], "tope": tope, "motivo": motivo}
            desglose[k] = tope
    total = round(sum(desglose.values()), 1)
    puertas = []
    if rep.get("passed") != rep.get("total"):
        puertas.append("QC técnico %s/%s" % (rep.get("passed"), rep.get("total")))
    if not ev.get("veracidad_ok"):
        puertas.append("veracidad sin confirmar (hechos, opiniones e hipótesis distinguidos)")
    if not ev.get("etica_ok"):
        puertas.append("ética y políticas de YouTube sin confirmar")
    if ev.get("sintetico_realista") and not rep.get("containsSyntheticMedia"):
        puertas.append("contenido sintético realista sin declarar")
    if len([d for d in ev.get("debilidades", []) if len(str(d).strip()) >= MIN_MOTIVO]) < 2:
        puertas.append("faltan al menos 2 debilidades concretas")
    if faltan:
        puertas.append("evaluación incompleta: " + "; ".join(faltan))
    aprobado = total >= umbral and not puertas
    devolver = []
    for k, peso in PESOS.items():
        if desglose[k] < 0.75 * peso:
            devolver.append({"criterio": NOMBRES[k], "puntos": desglose[k], "de": peso, "agente": RESPONSABLE[k], "arreglo": ARREGLO[k],
                             "tope": aplicados.get(k, {}).get("motivo")})
    return {"total": total, "umbral": umbral, "aprobado": aprobado, "decision": "Aprobado" if aprobado else "Corregir",
            "desglose": desglose, "topes_aplicados": aplicados, "evidencias_validas": evidencias, "puertas": puertas,
            "devolver_a": devolver, "debilidades": ev.get("debilidades", []), "parecido_max": sim_max,
            "medidas": {"duracion_s": dur, "qc": "%s/%s" % (rep.get("passed"), rep.get("total"))}}


def plantilla_evaluacion():
    return {"titulo": "", "criterios": {k: {"nota": None, "evidencias": [{"segundo": 0.0, "motivo": "", "fotograma": ""}]} for k in PESOS},
            "debilidades": [], "veracidad_ok": False, "etica_ok": False, "sintetico_realista": False}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("informe")
    ap.add_argument("evaluacion")
    ap.add_argument("--tipo", default="short")
    ap.add_argument("--umbral", type=float, default=85)
    ap.add_argument("--stills", default=None)
    a = ap.parse_args()
    rep = json.load(open(a.informe, encoding="utf-8"))
    ev = json.load(open(a.evaluacion, encoding="utf-8"))
    out = evaluar(rep, ev, a.tipo, a.umbral, stills_dir=a.stills)
    dst = a.informe.replace(".json", "_calidad.json")
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: out[k] for k in ("total", "decision", "puertas")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
