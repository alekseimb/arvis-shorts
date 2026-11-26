"""GUIONISTA · validación del guion antes de gastar tiempo en el render.

Estructura obligatoria (ARVIS 3.0): gancho (pregunta, ≤ 2,5 s) → problema → 2-3 pasos («tutorial») → resultado → cta.
Cada escena: «say» (narración), «fondo», «elementos» (activos que EXISTEN), anclas «en» que aparecen en la narración.
Contenido: fuentes oficiales o primarias, cada cifra de la narración respaldada por una cita, nada peligroso ni médico.
Uso: python3 -m arvis_vida.guion guion.json   → JSON con errores (bloquean) y avisos.
"""
import argparse
import json
import re
import sys
import unicodedata

from . import activos, fondos, props

ORDEN = ["gancho", "problema", "tutorial", "resultado", "cta"]
DOMINIOS_FIABLES = ("support.google.com/youtube", "blog.youtube",   # fuente primaria de las reglas y métricas de YouTube
                    "nih.gov",   # PubMed / PMC (Biblioteca Nacional de Medicina de EE. UU.): estudios revisados por pares
                    ".gob.es", "comunidad.madrid", "aesan.gob.es", "idae.es", "ocu.org", "consumo.gob.es", "sanidad.gob.es", "boe.es",
                    "europa.eu", "who.int", "juntadeandalucia.es", "gencat.cat", "euskadi.eus", "gva.es", "xunta.gal", "jcyl.es",
                    "madrid.es", "bcn.cat", "cnmc.es", "miteco.gob.es", "mapa.gob.es", "efsa.europa.eu", "fao.org", "csic.es",
                    "ree.es", "omie.es", "dgt.es", "bde.es", "cnmv.es", "carm.es", "navarra.es", "aragon.es", "castillalamancha.es",
                    "larioja.org", "asturias.es", "cantabria.es", "caib.es", "gobiernodecanarias.org", "juntaex.es")
# Frases que nunca pueden aparecer como consejo (se permiten solo como advertencia «nunca…» y con fuente)
PELIGROSOS = [
    (r"lej[ií]a.{0,40}(amon[ií]aco|vinagre|salfum[aá]n|[aá]cido|alcohol)|(amon[ií]aco|vinagre|salfum[aá]n).{0,40}lej[ií]a", "mezcla de productos de limpieza"),
    (r"\b(cura|curar|sana|adelgaza|desintoxica|detox|quema grasa|previene el c[aá]ncer)\b", "afirmación de salud"),
    (r"\b(garantizad[oa]|100 ?% seguro|milagro|nunca falla)\b", "promesa exagerada"),
    (r"\b(gas|butano|enchufe|cable).{0,30}(abre|manipula|empalma|pela)\b", "manipulación peligrosa"),
]
NEGACION = r"\b(nunca|jam[aá]s|no mezcles|no lo hagas|peligro|t[oó]xico)\b"


def _norm(w):
    w = unicodedata.normalize("NFKD", str(w).lower())
    return re.sub(r"[^a-z0-9ñ%]", "", "".join(c for c in w if not unicodedata.combining(c)))


def numeros(texto):
    return set(re.findall(r"\d+(?:[.,]\d+)?", texto))


TAM_PROTAGONISTA = 0.42   # ARVIS 5.0: ancho mínimo (fracción del fotograma) del objeto principal de cada escena


def validar(g, titulos_publicados=()):
    errores, avisos = [], []
    for k in ("id", "title", "description", "escenas", "sources", "hechos", "categoria"):
        if not g.get(k):
            errores.append("falta «%s»" % k)
    es = g.get("escenas", [])
    beats = [e.get("beat") for e in es]
    if not beats or beats[0] != "gancho":
        errores.append("la primera escena debe ser el gancho")
    if beats[-1:] != ["cta"]:
        errores.append("la última escena debe ser el cierre (cta)")
    if "problema" not in beats or "resultado" not in beats:
        errores.append("faltan escenas de problema o resultado")
    pasos = [e for e in es if e.get("beat") == "tutorial"]
    if len(pasos) < 2:
        errores.append("hacen falta al menos 2 pasos (escenas «tutorial»)")
    if [e.get("paso") for e in pasos] != list(range(1, len(pasos) + 1)):
        errores.append("los pasos deben numerarse 1, 2, 3…")
    idx = [ORDEN.index(b) if b in ORDEN else -1 for b in beats]
    if idx != sorted(idx) or -1 in idx:
        errores.append("orden de escenas incorrecto: %s" % beats)
    gancho = es[0].get("say", "") if es else ""
    if not gancho.strip().endswith("?"):
        errores.append("el gancho debe ser una pregunta")
    if len(gancho.split()) > 10:
        avisos.append("gancho de %d palabras (ideal ≤ 9 para no pasar de 2,5 s)" % len(gancho.split()))
    for i, e in enumerate(es):
        if not e.get("say", "").strip():
            errores.append("escena %d sin narración" % (i + 1))
        if e.get("fondo") and e["fondo"] not in fondos.ESCENARIOS:
            errores.append("escena %d: fondo desconocido «%s»" % (i + 1, e["fondo"]))
        palabras = [_norm(w) for w in e.get("say", "").split()]
        if not e.get("elementos"):
            errores.append("escena %d sin elementos visuales" % (i + 1))
        for el in e.get("elementos", []):
            if el.get("activo") and not activos.existe(el["activo"]):
                errores.append("escena %d: activo inexistente «%s»" % (i + 1, el["activo"]))
            for clave in ("en", "sale_en"):
                a = el.get(clave)
                if isinstance(a, str):
                    a0 = _norm(a.split("#")[0])
                    if not any(p.startswith(a0) for p in palabras):
                        avisos.append("escena %d: el ancla «%s» no está en la narración (se usará el inicio)" % (i + 1, a))
            for k, (x, y) in (("pos", (el.get("x", 0.5), el.get("y", 0.5))),):
                if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                    errores.append("escena %d: posición fuera del fotograma" % (i + 1))
                if el.get("tipo") not in ("particulas", "flecha") and 0.665 <= y <= 0.74:
                    avisos.append("escena %d: «%s» en la franja de subtítulos (y=%.2f)" % (i + 1, el.get("activo") or el.get("tipo"), y))
        # ARVIS 5.0 · identidad visual: el objeto protagonista se ve grande y nada queda vacío
        tams = [float(el.get("tam", 0.3)) for el in e.get("elementos", []) if el.get("activo")]
        if e.get("beat") != "cta" and not tams and not any(el.get("tipo") in ("contador", "barra") for el in e.get("elementos", [])):
            avisos.append("escena %d: sin objeto ni cifra grande (solo textos): pantalla vacía" % (i + 1))
        elif (e.get("beat") not in ("cta",) and tams and max(tams) < TAM_PROTAGONISTA
              and not any(el.get("tipo") in ("contador", "barra") for el in e.get("elementos", []))):   # la cifra grande también vale
            avisos.append("escena %d: objeto protagonista pequeño (tam %.2f < %.2f)" % (i + 1, max(tams), TAM_PROTAGONISTA))
        nombres = {el.get("activo") for el in e.get("elementos", [])}
        for el in e.get("elementos", []):
            a = el.get("ancla")
            n = a if isinstance(a, str) else (a or {}).get("activo")
            if a and n not in nombres:
                errores.append("escena %d: «ancla» a «%s», que no está en la escena" % (i + 1, n))
    # contenido
    fuentes = g.get("sources", [])
    if not any(any(d in u for d in DOMINIOS_FIABLES) for u in fuentes):
        errores.append("ninguna fuente oficial o primaria (dominios admitidos en guion.DOMINIOS_FIABLES)")
    for h in g.get("hechos", []):
        if not h.get("cita") or not h.get("url"):
            errores.append("hecho sin cita literal o sin URL: %s" % h.get("dato"))
    narracion = " ".join(e.get("say", "") for e in es)
    citas = " ".join(h.get("cita", "") + " " + h.get("dato", "") for h in g.get("hechos", []))
    # «"ejemplo": true» en un rótulo = cifra ilustrativa (p. ej. una etiqueta «-50 %» genérica), no un dato: no necesita cita,
    # pero esa cifra no puede decirse en la narración (ahí sí sería una afirmación)
    sin_fuente = sorted(n for n in numeros(narracion + " " + " ".join(str(el.get("texto", "")) for e in es for el in e.get("elementos", [])
                                                                      if not el.get("ejemplo")))
                        if n not in numeros(citas))
    if sin_fuente:
        errores.append("cifras sin cita que las respalde: %s" % ", ".join(sin_fuente))
    texto_total = (narracion + " " + g.get("title", "") + " " + g.get("description", "")).lower()
    for patron, motivo in PELIGROSOS:
        for m in re.finditer(patron, texto_total):
            frase = texto_total[max(0, m.start() - 60): m.end() + 60]
            if not re.search(NEGACION, frase):
                errores.append("contenido no permitido (%s): «%s»" % (motivo, m.group(0)))
    import difflib
    for t in titulos_publicados:
        if difflib.SequenceMatcher(None, _norm(g.get("title", "")), _norm(t)).ratio() >= 0.62:
            errores.append("título casi igual a uno publicado: «%s»" % t)
    return {"ok": not errores, "errores": errores, "avisos": avisos}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("guion")
    ap.add_argument("--publicados", default=None, help="JSON con la lista de títulos ya publicados")
    a = ap.parse_args()
    g = json.load(open(a.guion, encoding="utf-8"))
    pub = json.load(open(a.publicados, encoding="utf-8")) if a.publicados else []
    r = validar(g, pub)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    sys.exit(0 if r["ok"] else 2)


if __name__ == "__main__":
    main()
