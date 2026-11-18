"""Publicación: franjas (12:00, 17:00, 21:00 Madrid), metadatos y parámetros para el circuito de subida de ARVIS.

La subida en sí la hace el agente con lo que ya existe: rama `media` de alekseimb/arvis-shorts → Make 8260243
(guardia antiduplicados, OAuth «ARVIS YouTube») → almacén 238309 → comprobación con Make 8260190.
Aquí solo se calcula la franja libre y se construyen título, descripción, etiquetas y categoría.

Uso:
  python3 -m arvis_lifehacks.publicar franja --ocupadas "19/11/2026 12:00,19/11/2026 17:00" [--ahora "19/11/2026 10:00"]
  python3 -m arvis_lifehacks.publicar metadatos out/SH-0NN_guion.json --franja "19/11/2026 21:00"
"""
import argparse
import datetime as dt
import json
import re
from zoneinfo import ZoneInfo

from .config import CATEGORIA_YT, CREDITO_VOZ, FRANJAS, MARGEN_MIN, VOZ, ZONA

TZ = ZoneInfo(ZONA)


def _parse(s):
    return dt.datetime.strptime(s.strip(), "%d/%m/%Y %H:%M").replace(tzinfo=TZ)


def siguiente_franja(ocupadas=(), ahora=None, margen=MARGEN_MIN, franjas=FRANJAS, dias=14):
    ahora = ahora or dt.datetime.now(TZ)
    ocup = {_parse(o) for o in ocupadas if o}
    for d in range(dias):
        dia = (ahora + dt.timedelta(days=d)).date()
        for h in franjas:
            hh, mm = map(int, h.split(":"))
            f = dt.datetime(dia.year, dia.month, dia.day, hh, mm, tzinfo=TZ)
            if f - ahora >= dt.timedelta(minutes=margen) and f not in ocup:
                return f
    return None


def a_utc(f):
    return f.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def limpiar(s):
    """YouTube no admite < ni > en título ni descripción."""
    return s.replace("<", "‹").replace(">", "›")


def descripcion(g, codigo=None):
    partes = [g["description"].strip(), ""]
    if codigo and not re.search(r"[<>]", codigo) and len(codigo) <= 2600:
        partes += ["Código completo (%s):" % g.get("requisito", "Python 3.11 o posterior, gratis en python.org"), codigo.strip(), ""]
    if g.get("como_usar"):
        partes += ["Cómo usarlo: " + g["como_usar"].strip(), ""]
    if g.get("sources"):
        partes += ["Fuentes:"] + ["• " + u for u in g["sources"]] + [""]
    partes += ["LIFEHACKS AI · Nº %03d · Pequeñas soluciones inteligentes para problemas de todos los días." % int(g.get("numero", 1)),
               "Grabación de pantalla real de la demostración. Narración con voz sintética. Música creada por el canal."]
    credito = CREDITO_VOZ.get(g.get("voice", VOZ), "")
    if credito:
        partes.append(credito)
    partes.append("")
    partes += [" ".join(g.get("hashtags", ["#Shorts"]))]
    return limpiar("\n".join(partes))[:4900]


def metadatos(g, franja=None, codigo=None):
    titulo = limpiar(g["title"])[:100]
    m = {"title": titulo, "description": descripcion(g, codigo), "tags": g.get("tags", [])[:15], "categoryId": g.get("categoryId", CATEGORIA_YT),
         "privacyStatus": "private", "publishAt": a_utc(franja) if franja else "", "key": g["id"]}
    return m


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="orden")
    a1 = sp.add_parser("franja")
    a1.add_argument("--ocupadas", default="")
    a1.add_argument("--ahora", default=None)
    a1.add_argument("--margen", type=int, default=MARGEN_MIN)
    a2 = sp.add_parser("metadatos")
    a2.add_argument("guion")
    a2.add_argument("--franja", default=None)
    a2.add_argument("--codigo", default=None)
    a = ap.parse_args()
    if a.orden == "franja":
        f = siguiente_franja([x for x in a.ocupadas.split(",") if x.strip()], _parse(a.ahora) if a.ahora else None, a.margen)
        print(json.dumps({"franja": f.strftime("%d/%m/%Y %H:%M") if f else None, "publishAt": a_utc(f) if f else None}))
    else:
        g = json.load(open(a.guion, encoding="utf-8"))
        codigo = open(a.codigo, encoding="utf-8").read() if a.codigo else None
        print(json.dumps(metadatos(g, _parse(a.franja) if a.franja else None, codigo), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
