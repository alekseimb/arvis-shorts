"""Evaluador de calidad 0–100 · umbral 85.

  LIFEHACKS (rúbrica «5.0», 26/11/2026): Gancho 20 · Retención 20 · Calidad visual 20 · Originalidad 15 · Utilidad 10 · Claridad 10 · Viralidad 5
  Resto (rúbrica «2026-11-18»):

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

# --- ARVIS LIFEHACKS 5.0 (26/11/2026, orden de Aleksei): rúbrica propia de los Shorts de la vida.
RUBRICA_50 = {
    "pesos": {"gancho": 20, "retencion": 20, "visual": 20, "originalidad": 15, "utilidad": 10, "claridad": 10, "viralidad": 5},
    "nombres": {"gancho": "Gancho", "retencion": "Retención", "visual": "Calidad visual", "originalidad": "Originalidad",
                "utilidad": "Utilidad", "claridad": "Claridad", "viralidad": "Potencial de viralidad"},
    "responsable": {"gancho": "Guionista", "retencion": "Guionista + Editor", "visual": "Director visual (motor ARVIS VIDA)",
                    "originalidad": "Director creativo + Investigador", "utilidad": "Investigador", "claridad": "Guionista + Editor (voz y subtítulos)",
                    "viralidad": "Director creativo"},
    "arreglo": {
        "gancho": "Primera frase con la cifra o la sorpresa citada, en pregunta de ≤ 9 palabras, y el objeto protagonista en pantalla desde el segundo 0.",
        "retencion": "Un cambio visual o un dato nuevo cada 2–3 s; quitar frases de relleno; cada paso con su objeto en grande.",
        "visual": "Objeto protagonista grande y apoyado en su sitio, todo en el mismo estilo con volumen, sin pantallas vacías ni elementos que se tapen.",
        "originalidad": "Cambiar el enfoque (error común, comparación, antes/después) o el dato poco conocido; no repetir la plantilla del último vídeo.",
        "utilidad": "Que el consejo se pueda aplicar hoy, con el paso exacto y la fuente oficial citada; sin cifras sin cita.",
        "claridad": "Frases cortas, una idea por escena, subtítulos legibles y voz a ritmo natural; se entiende sin contexto previo.",
        "viralidad": "Remate que invite a guardar o comentar, título concreto y dato que apetezca compartir.",
    },
    "topes": [  # (palabras en el nombre de la comprobación que falla, criterio, fracción máxima)
        (("Fuentes",), "utilidad", 0.4), (("cifras",), "utilidad", 0.75), (("Gancho",), "gancho", 0.6),
        (("Capítulos", "Estructura"), "retencion", 0.7), (("repetidas",), "visual", 0.5), (("estáticos", "movimiento"), "visual", 0.6),
        (("estáticos", "movimiento"), "retencion", 0.8), (("negros",), "visual", 0.3), (("Variedad",), "visual", 0.7),
        (("Sonoridad",), "claridad", 0.6), (("silencios", "Ritmo de voz"), "retencion", 0.7), (("silencios", "Ritmo de voz"), "claridad", 0.8),
        (("Decodifica", "Formato"), "visual", 0.0), (("Decodifica", "Formato"), "claridad", 0.0), (("Subtítulos",), "claridad", 0.5),
        (("Storyboard", "Miniatura"), "visual", 0.85), (("etiquet", "sintético"), "viralidad", 0.5),
    ],
    "plantilla": {"visual": 0.7, "originalidad": 0.6},
    "tema_repetido": "originalidad",
}
RUBRICA_181 = {"pesos": PESOS, "nombres": NOMBRES, "responsable": RESPONSABLE, "arreglo": ARREGLO, "topes": None,
               "plantilla": {"visual": 0.7, "originalidad": 0.6}, "tema_repetido": "originalidad"}
RUBRICAS = {"5.0": RUBRICA_50, "2026-11-18": RUBRICA_181}


def _peso_tope(nombre, frac, pesos=None):
    return round((pesos or PESOS)[nombre] * frac, 1)


def topes_automaticos(rep, tipo, rubrica=None):
    """rep: informe del motor (checks, passed, total, duration_s…). Devuelve {criterio: (tope, motivo)}."""
    t = {}
    fallos = {c["check"]: c for c in rep.get("checks", []) if not c.get("ok")}
    if rubrica and rubrica.get("topes"):
        for palabras, crit, frac in rubrica["topes"]:
            for k in [k for k in fallos if any(p.lower() in k.lower() for p in palabras)]:
                tope = _peso_tope(crit, frac, rubrica["pesos"])
                if crit not in t or tope < t[crit][0]:
                    t[crit] = (tope, k)
        return t

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


def evaluar(rep, ev, tipo="short", umbral=85, firma_actual=None, firmas_recientes=(), titulos_recientes=(), stills_dir=None,
            rubrica=None):
    R = RUBRICAS[rubrica or ev.get("rubrica") or "2026-11-18"]
    PESOS, NOMBRES, RESPONSABLE, ARREGLO = R["pesos"], R["nombres"], R["responsable"], R["arreglo"]
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
    topes = topes_automaticos(rep, tipo, R if R.get("topes") else None)
    sim_max, sim_con = 0.0, None
    if firma_actual:
        for f in firmas_recientes:
            s = parecido(firma_actual, f["firma"])
            if s > sim_max:
                sim_max, sim_con = s, f.get("clave")
        if sim_max >= 0.75:
            for crit, frac in R["plantilla"].items():
                topes[crit] = min(topes.get(crit, (99, "")), (_peso_tope(crit, frac, PESOS), "plantilla repetida (%.0f %% igual a %s)" % (sim_max * 100, sim_con)))
    tit = ev.get("titulo") or rep.get("title") or ""
    for t in titulos_recientes:
        if tit and difflib.SequenceMatcher(None, tit.lower(), t.lower()).ratio() >= 0.8:
            c = R["tema_repetido"]
            topes[c] = min(topes.get(c, (99, "")), (_peso_tope(c, 0.4, PESOS), "tema casi igual a «%s»" % t))
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
            "rubrica": rubrica or ev.get("rubrica") or "2026-11-18",
            "desglose": desglose, "topes_aplicados": aplicados, "evidencias_validas": evidencias, "puertas": puertas,
            "devolver_a": devolver, "debilidades": ev.get("debilidades", []), "parecido_max": sim_max,
            "medidas": {"duracion_s": dur, "qc": "%s/%s" % (rep.get("passed"), rep.get("total"))}}


def plantilla_evaluacion(rubrica=None):
    pesos = RUBRICAS[rubrica]["pesos"] if rubrica else PESOS
    ev = {"titulo": "", "criterios": {k: {"nota": None, "evidencias": [{"segundo": 0.0, "motivo": "", "fotograma": ""}]} for k in pesos},
          "debilidades": [], "veracidad_ok": False, "etica_ok": False, "sintetico_realista": False}
    if rubrica:
        ev["rubrica"] = rubrica
        ev["pesos"] = dict(pesos)
    return ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("informe")
    ap.add_argument("evaluacion")
    ap.add_argument("--tipo", default="short")
    ap.add_argument("--umbral", type=float, default=85)
    ap.add_argument("--stills", default=None)
    ap.add_argument("--rubrica", default=None, help="5.0 (LIFEHACKS) o 2026-11-18; por defecto, la que diga la evaluación")
    a = ap.parse_args()
    rep = json.load(open(a.informe, encoding="utf-8"))
    ev = json.load(open(a.evaluacion, encoding="utf-8"))
    out = evaluar(rep, ev, a.tipo, a.umbral, stills_dir=a.stills, rubrica=a.rubrica)
    dst = a.informe.replace(".json", "_calidad.json")
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: out[k] for k in ("total", "decision", "rubrica", "desglose", "puertas")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
