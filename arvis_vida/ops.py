"""ARVIS 3.1 · operación eficiente de la tarea programada «ARVIS LIFEHACKS» (22/11/2026).

Hace con Python, sin gastar razonamiento de Claude, todo lo mecánico de cada ejecución: qué modos tocan, qué Shorts
hay que comprobar, la franja libre, el siguiente SH y Nº, si hay que investigar, si las fuentes en caché siguen
valiendo, la preparación del entorno (sin reinstalar ni repetir pruebas si el motor no cambió) y el cálculo de
métricas. Solo biblioteca estándar: `plan`, `anotar` y `guardar` funcionan sin instalar nada (modo SUPERVISIÓN).

ESTADO PERSISTENTE: estado/lh_estado.json en la rama `vida` (se recupera tras cualquier reinicio porque vive en git).
El repositorio es PÚBLICO: el estado nunca lleva IDs de hojas, claves, correos ni datos personales. Las hojas de
Google siguen siendo la fuente de verdad: si no coinciden con el estado, mandan las hojas y se corrige el estado.

  python3 -m arvis_vida.ops plan [--ahora "dd/mm/aaaa HH:MM"]      # qué hacer en esta ejecución (JSON corto)
  python3 -m arvis_vida.ops entorno                               # MODO C: dependencias, recursos, Fluent, pruebas si cambió el motor
  python3 -m arvis_vida.ops anotar '{"shorts": {"SH-033": {"fase": "9. Programado"}}}'   # fusiona en el estado
  python3 -m arvis_vida.ops ejecucion "A+C" OK "resumen de una línea"                    # cierra la ejecución
  python3 -m arvis_vida.ops error "paso" "mensaje corto"                                 # guarda el error (sin logs)
  python3 -m arvis_vida.ops metricas registro.json                # MODO B: filas METRICAS + SHORTS K:O + analista
  python3 -m arvis_vida.ops titulos titulos.json                  # títulos ya usados (sin leer SHORTS › F)
  python3 -m arvis_vida.ops guardar "mensaje"                     # commit + push del estado si cambió

ARVIS LIFEHACKS 5.0 (26/11/2026, «yo elijo el tema»): con reglas.modo = "dirigido" la tarea ya no elige temas ni investiga
por su cuenta. Solo sube los Shorts que Aleksei aprobó («6. Pendiente de subida») y produce los temas que él le encargó.
  python3 -m arvis_vida.ops tema "texto del tema" [--encargar] [--publicar]   # registra el tema (T-0NN) y da SH, Nº y parecidos
  python3 -m arvis_vida.ops aprobar SH-0NN "Aleksei en el chat dd/mm HH:MM"   # su «sí»: pasa a 6. Pendiente de subida
  python3 -m arvis_vida.ops franja                                # primera franja libre y publishAt (subida desde el chat)
"""
import argparse
import datetime as dt
import difflib
import hashlib
import json
import os
import subprocess
import sys
import time

try:
    from zoneinfo import ZoneInfo
    MADRID = ZoneInfo("Europe/Madrid")
except Exception:  # pragma: no cover
    MADRID = None

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTA = os.environ.get("ARVIS_ESTADO") or os.path.join(RAIZ, "estado", "lh_estado.json")
ARBOL_MOTOR = ["arvis_vida", "arvis_lifehacks", "arvis_estudio/calidad.py", "tests/test_vida.py", "tests/test_ops.py",
               "tests/test_sonda.py", "tests/test_v5.py", "requirements-vida.txt"]
FASES_OCUPAN = ("6.", "7.", "8.", "9.", "10.")
CAT_VIDA_DESDE = 27          # SH-024…026 eran de informática: no cuentan para aprender categorías

REGLAS = {"franjas": ["12:00", "17:00", "21:00"], "margen_min": 90, "max_horas_cola": 30, "umbral": 85,
          "min_elegidas": 3, "ideas_por_investigacion": 4, "validez_fuentes_dias": 14, "max_montajes": 3,
          "max_reescrituras_qc": 2, "max_videos_metricas": 50,
          "modo": "dirigido", "duracion": [20, 35]}   # ARVIS 5.0: «dirigido» = solo temas de Aleksei; «autonomo» = como el 3.1

# Presupuesto interno por ejecución (no es un límite de tokens: Claude no permite imponerlo. Son topes de operaciones
# contables que la tarea respeta; al llegar a uno: parar lo no esencial, guardar estado, nada a medias, anotar pendiente).
PRESUPUESTO = {
    "A": {"llamadas_herramientas": 14, "consultas_make": 1, "listados_almacen": 1, "imagenes": 0, "web": 0},
    "B": {"llamadas_herramientas": 8, "consultas_make": 1, "listados_almacen": 1, "imagenes": 0, "web": 0},
    "C": {"llamadas_herramientas": 60, "consultas_make": 2, "listados_almacen": 1, "montajes": 3, "sondas": 4,
          "imagenes_revision": 20, "web_busquedas": 4, "web_lecturas": 4, "reescrituras_qc": 2},
}


# ----------------------------------------------------------------------------- utilidades
def ahora_madrid(txt=None):
    if txt:
        return dt.datetime.strptime(txt, "%d/%m/%Y %H:%M")
    n = dt.datetime.now(MADRID) if MADRID else dt.datetime.utcnow() + dt.timedelta(hours=1)
    return n.replace(tzinfo=None, second=0, microsecond=0)


def fmt(d):
    return d.strftime("%d/%m/%Y %H:%M")


def leer_fecha(txt):
    txt = (txt or "").strip()
    for f in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime(txt, f)
        except ValueError:
            pass
    return None


def utc_iso(local):
    """Franja de Madrid → ISO UTC con «.000Z» (formato que espera Make 8260243)."""
    if MADRID:
        u = local.replace(tzinfo=MADRID).astimezone(dt.timezone.utc)
    else:  # pragma: no cover
        u = local - dt.timedelta(hours=1)
    return u.strftime("%Y-%m-%dT%H:%M:00.000Z")


def cargar(ruta=RUTA):
    if not os.path.exists(ruta):
        return {"version": 1, "shorts": {}, "ideas": {}, "ejecuciones": [], "errores": [], "pendiente": [], "reglas": dict(REGLAS)}
    return json.load(open(ruta, encoding="utf-8"))


def guardar_local(est, ruta=RUTA):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    est["actualizado"] = fmt(ahora_madrid())
    tmp = ruta + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(est, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write("\n")
    os.replace(tmp, ruta)


def fusionar(a, b):
    for k, v in b.items():
        if v is None:
            a.pop(k, None)
        elif isinstance(v, dict) and isinstance(a.get(k), dict):
            fusionar(a[k], v)
        else:
            a[k] = v
    return a


def num(sh):
    return int(str(sh).split("-")[1])


def reglas(est):
    r = dict(REGLAS)
    r.update(est.get("reglas") or {})
    return r


# ----------------------------------------------------------------------------- plan
def franjas_ocupadas(est):
    occ = set()
    for sh, s in est.get("shorts", {}).items():
        if s.get("franja") and str(s.get("fase", "")).startswith(FASES_OCUPAN) and not s.get("retirado"):
            occ.add(s["franja"])
    return occ


def franja_libre(est, ahora):
    r = reglas(est)
    occ = franjas_ocupadas(est)
    for dias in range(0, 3):
        d = (ahora + dt.timedelta(days=dias)).date()
        for hm in r["franjas"]:
            hh, mm = map(int, hm.split(":"))
            f = dt.datetime(d.year, d.month, d.day, hh, mm)
            if f < ahora + dt.timedelta(minutes=r["margen_min"]):
                continue
            if fmt(f) in occ:
                continue
            if f > ahora + dt.timedelta(hours=r["max_horas_cola"]):
                return None, "cola llena: la primera franja libre está a más de %d h" % r["max_horas_cola"]
            return f, ""
    return None, "sin franja libre en 3 días"


def llamada_estado(ids, clave="estados-lh"):
    return {"url": "/v3/videos", "method": "GET", "key": clave,
            "qs": [{"key": "part", "value": "status"}, {"key": "id", "value": ",".join(ids)}]}


def llamada_metricas(ids):
    return {"url": "/v3/videos", "method": "GET", "key": "metricas-lh",
            "qs": [{"key": "part", "value": "statistics,snippet,contentDetails,status"}, {"key": "id", "value": ",".join(ids)}]}


def plan(est, ahora):
    r = reglas(est)
    shorts = est.get("shorts", {})
    hoy = ahora.strftime("%d/%m/%Y")
    out = {"hora": fmt(ahora), "ejecucion": "01:47" if ahora.hour < 5 else ("08:47" if ahora.hour < 12 else "14:47"), "modos": ["A"]}

    # ---- MODO A · supervisión
    vencidos = []
    for sh, s in sorted(shorts.items()):
        f = leer_fecha(s.get("franja"))
        if str(s.get("fase", "")).startswith("9.") and s.get("yt") and f and f <= ahora and not s.get("retirado"):
            vencidos.append(sh)
    colgados = [sh for sh, s in shorts.items() if str(s.get("fase", "")).startswith("7.")]
    filas = [s["fila"] for s in shorts.values() if s.get("fila")]
    f0, f1 = (min(filas), max(filas) + 4) if filas else (25, 60)
    mk = est.get("make", {})
    ult_mk = leer_fecha(mk.get("ultima_revision"))
    revisar_make = out["ejecucion"] == "01:47" or mk.get("estado") not in (None, "OK") or not ult_mk or (ahora - ult_mk) > dt.timedelta(hours=20)
    out["A"] = {
        "lecturas_hojas": ["SHORTS!A%d:A%d" % (f0, f1), "SHORTS!U%d:U%d" % (f0, f1),
                           "CONFIG_YOUTUBE!A1:B45 (solo etiquetas y valores; nunca la columna C)"],
        "comprobar_publico": [{"sh": sh, "yt": shorts[sh]["yt"], "franja": shorts[sh]["franja"], "fila": shorts[sh].get("fila")} for sh in vencidos],
        "llamada_make": llamada_estado([shorts[sh]["yt"] for sh in vencidos]) if vencidos else None,
        "subidas_colgadas": colgados,
        "revisar_make": revisar_make,
        "como_revisar_make": "scenarios_list teamId 3393416 + data-stores_get 238309 (sin blueprints)" if revisar_make else "",
        "nota": "Sin vencidos ni colgados: NO consultes Make ni el almacén." if not vencidos and not colgados else "",
    }
    # ---- MODO B · métricas (01:47, una vez al día)
    met = est.get("metricas", {})
    if out["ejecucion"] == "01:47" and not str(met.get("fecha", "")).startswith(hoy):
        pub = [s["yt"] for sh, s in sorted(shorts.items(), key=lambda x: num(x[0]))
               if s.get("yt") and (str(s.get("fase", "")).startswith("10.") or sh in vencidos) and not s.get("retirado")]
        pub = pub[-r["max_videos_metricas"]:]
        out["modos"].append("B")
        out["B"] = {"videos": len(pub), "llamada_make": llamada_metricas(pub) if pub else None,
                    "despues": "guarda el «data» de metricas-lh en /tmp/metricas-lh.json y ejecuta: python3 -m arvis_vida.ops metricas /tmp/metricas-lh.json"}

    # ---- MODO C · ARVIS 5.0 dirigido (solo temas de Aleksei y Shorts que él aprobó)
    if r.get("modo") == "dirigido":
        out["C"] = plan_dirigido(est, ahora, r)
        if out["C"].get("producir"):
            out["modos"].append("C")
        out["presupuesto"] = {m: PRESUPUESTO[m] for m in out["modos"]}
        out["errores_abiertos"] = [e for e in est.get("errores", []) if not e.get("resuelto")][-3:]
        out["pendiente"] = est.get("pendiente", [])[-5:]
        return out

    # ---- MODO C · producción (modo «autonomo», ARVIS 3.1)
    rev = [sh for sh, s in shorts.items() if str(s.get("fase", "")).startswith("4.") and int(s.get("intentos", 1)) < 2 and not s.get("descartado")]
    franja, motivo = franja_libre(est, ahora)
    c = {"producir": bool(franja), "motivo": motivo}
    if franja:
        recientes = [shorts[sh].get("categoria") for sh in sorted(shorts, key=num, reverse=True)
                     if num(sh) >= CAT_VIDA_DESDE and shorts[sh].get("categoria") and str(shorts[sh].get("fase", "")).startswith(FASES_OCUPAN)][:2]
        elegidas = sorted([(k, v) for k, v in est.get("ideas", {}).items() if v.get("estado") == "Elegida" and not v.get("sh")],
                          key=lambda kv: -float(kv[1].get("puntuacion", 0)))
        alternativas = [kv for kv in elegidas if kv[1].get("categoria") not in recientes] or elegidas
        idea = None
        if rev:
            sh = sorted(rev, key=num)[0]
            idea_id = shorts[sh].get("idea")
            idea = (idea_id, est.get("ideas", {}).get(idea_id, {}))
            c.update(reintento=sh, siguiente_sh=sh, numero=shorts[sh].get("numero"),
                     debilidades=shorts[sh].get("debilidades", ""))
        else:
            ult = max([num(sh) for sh in shorts] + [num(est.get("ultimo_sh", "SH-000"))])
            c.update(siguiente_sh="SH-%03d" % (ult + 1), numero=int(est.get("ultimo_numero", 0)) + 1)
            idea = alternativas[0] if alternativas else None
        c["franja"] = fmt(franja)
        c["publishAt"] = utc_iso(franja)
        c["categorias_recientes"] = recientes
        if idea and idea[0]:
            leido = leer_fecha(idea[1].get("leido"))
            urls = [u for u in idea[1].get("fuentes", []) if str(u).startswith("http")]
            valida = bool(leido and (ahora - leido).days <= r["validez_fuentes_dias"] and idea[1].get("citas") and urls)
            c["idea"] = {"id": idea[0], "fila": idea[1].get("fila"), "categoria": idea[1].get("categoria"), "titulo": idea[1].get("titulo"),
                         "fuentes": idea[1].get("fuentes", []), "leido": idea[1].get("leido"),
                         "fuente_valida": valida,
                         "web": "NO hace falta: citas en caché (estado › ideas) leídas hace ≤ %d días" % r["validez_fuentes_dias"] if valida
                         else "relee UNA vez la fuente (agente web-fetch) y guarda URL, fecha y citas con «ops anotar»"}
        else:
            c["idea"] = None
        c["investigar"] = len(elegidas) < r["min_elegidas"] or not idea
        if c["investigar"]:
            c["investigar_n"] = r["ideas_por_investigacion"]
        c["entorno"] = "python3 -m arvis_vida.ops entorno"
        out["modos"].append("C")
    out["C"] = c
    out["presupuesto"] = {m: PRESUPUESTO[m] for m in out["modos"]}
    out["errores_abiertos"] = [e for e in est.get("errores", []) if not e.get("resuelto")][-3:]
    out["pendiente"] = est.get("pendiente", [])[-5:]
    return out


# ----------------------------------------------------------------------------- ARVIS 5.0 · temas de Aleksei
def siguiente(est):
    shorts = est.get("shorts", {})
    ult = max([num(sh) for sh in shorts] + [num(est.get("ultimo_sh", "SH-000"))])
    return "SH-%03d" % (ult + 1), int(est.get("ultimo_numero", 0)) + 1


def plan_dirigido(est, ahora, r):
    shorts = est.get("shorts", {})
    esperan = sorted(sh for sh, s in shorts.items() if str(s.get("fase", "")).startswith("5.") and s.get("tema") and not s.get("aprobado"))
    c = {"producir": False, "modo": "dirigido", "investigar": False,
         "esperan_tu_si": esperan, "regla": "Nunca elijas ni investigues temas por tu cuenta; nunca uses ideas «Elegida» de ARVIS."}
    aprobados = sorted((sh for sh, s in shorts.items() if str(s.get("fase", "")).startswith("6.") and s.get("aprobado")
                        and not s.get("yt") and not s.get("retirado")), key=num)
    encargados = sorted((k for k, t in est.get("temas", {}).items() if t.get("estado") == "Encargado a la tarea"), key=lambda k: k)
    rev = sorted((sh for sh, s in shorts.items() if str(s.get("fase", "")).startswith("4.") and s.get("tema")
                  and int(s.get("intentos", 1)) < 2 and not s.get("descartado")), key=num)
    franja, motivo = franja_libre(est, ahora)
    if aprobados:
        sh = aprobados[0]
        s = shorts[sh]
        if not franja:
            c["motivo"] = "%s aprobado, pero %s" % (sh, motivo)
            return c
        c.update(producir=True, tipo="subir_aprobado", sh=sh, numero=s.get("numero"), tema=s.get("tema"),
                 guion="guiones_vida/%s/guion.json" % sh, huella_contenido_aprobada=s.get("huella_contenido"),
                 huella_motor_aprobado=s.get("huella_motor"),
                 mismo_motor=bool(s.get("huella_motor")) and s.get("huella_motor") == huella_motor(),
                 franja=fmt(franja), publishAt=utc_iso(franja),
                 pasos="Monta el guion aprobado SIN cambiarlo (C5), QC 22/22 y sonda sin graves; si mismo_motor y la "
                       "huella_contenido del informe coincide, es el vídeo que vio Aleksei: súbelo (C7). Si no coincide o cambió "
                       "el motor: no subas, déjalo en «5. Vídeo aprobado» y pide su sí de nuevo.")
        return c
    if encargados or rev:
        if not franja and not (encargados and not est["temas"][encargados[0]].get("publicar")):
            c["motivo"] = motivo
            return c
        if rev:
            sh = rev[0]
            c.update(producir=True, tipo="reintento_tema", siguiente_sh=sh, numero=shorts[sh].get("numero"),
                     tema=shorts[sh].get("tema"), debilidades=shorts[sh].get("debilidades", ""))
        else:
            k = encargados[0]
            sh, n = siguiente(est)
            c.update(producir=True, tipo="producir_tema", tema=k, texto=est["temas"][k].get("texto"), siguiente_sh=sh, numero=n,
                     investigar_tema=True)
        t = est.get("temas", {}).get(c["tema"], {})
        c["publicar_sin_preguntar"] = bool(t.get("publicar"))
        if franja:
            c.update(franja=fmt(franja), publishAt=utc_iso(franja))
        c["al_terminar"] = ("nota ≥ 85 → sube a la franja (Aleksei ya lo autorizó)" if c["publicar_sin_preguntar"] else
                            "nota ≥ 85 → NO subas: SHORTS «Vídeo listo (pendiente de subir)» + Fase «5. Vídeo aprobado» + Notas «ESPERA TU SÍ», "
                            "ops anotar (fase 5, tema, sha256, huella_motor) y aviso push «Short listo: ¿lo subo?»")
        c["entorno"] = "python3 -m arvis_vida.ops entorno"
        return c
    c["motivo"] = "sin temas de Aleksei ni Shorts aprobados: no se produce nada"
    return c


def tema(est, texto, encargar=False, publicar=False, ahora=None):
    """Registra un tema que eligió Aleksei. Devuelve su ID, el SH y Nº que tocan y los temas o títulos parecidos."""
    ahora = ahora or ahora_madrid()
    temas = est.setdefault("temas", {})
    k = "T-%03d" % (max([int(x[2:]) for x in temas] + [0]) + 1)
    sh, n = siguiente(est)
    usados = [(x, t.get("texto", "")) for x, t in temas.items()] + [(sh2, s.get("titulo", "")) for sh2, s in est.get("shorts", {}).items()]
    parecidos = sorted(((round(difflib.SequenceMatcher(None, texto.lower(), u.lower()).ratio(), 2), x, u) for x, u in usados if u),
                       reverse=True)[:3]
    temas[k] = {"texto": texto[:200], "fecha": fmt(ahora), "origen": "Aleksei",
                "estado": "Encargado a la tarea" if encargar else "En producción (chat)", "publicar": bool(publicar)}
    recientes = [est["shorts"][x].get("categoria") for x in sorted(est.get("shorts", {}), key=num, reverse=True)
                 if est["shorts"][x].get("categoria")][:3]
    return {"ok": True, "tema": k, "siguiente_sh": sh, "numero": n, "parecidos": [p for p in parecidos if p[0] >= 0.45],
            "categorias_recientes": recientes, "publicar_sin_preguntar": bool(publicar)}


def aprobar(est, sh, quien, ahora=None):
    s = est.get("shorts", {}).get(sh)
    if not s:
        return {"ok": False, "error": "%s no está en el estado" % sh}
    if s.get("yt"):
        return {"ok": False, "error": "%s ya está subido (%s)" % (sh, s["yt"])}
    s.update(aprobado=True, aprobado_por=quien[:120], fase="6. Pendiente de subida")
    f, motivo = franja_libre(est, ahora or ahora_madrid())
    return {"ok": True, "sh": sh, "fase": s["fase"], "franja": fmt(f) if f else None, "publishAt": utc_iso(f) if f else None,
            "motivo": motivo, "mismo_motor": s.get("huella_motor") == huella_motor()}


# ----------------------------------------------------------------------------- entorno (solo MODO C)
def huella_motor():
    try:
        r = subprocess.run(["git", "-C", RAIZ, "ls-files", "-s", "--"] + ARBOL_MOTOR, capture_output=True, text=True, timeout=30)
        return hashlib.sha1(r.stdout.encode()).hexdigest()[:16]
    except Exception:
        return "?"


def entorno(est):
    t0 = time.time()
    res = {"ok": True}
    try:
        import piper  # noqa: F401
        res["pip"] = "ya instalado"
    except Exception:
        log = "/tmp/arvis_pip.log"
        r = subprocess.run([sys.executable, "-m", "pip", "install", "--break-system-packages", "-q", "-r",
                            os.path.join(RAIZ, "requirements-vida.txt")], capture_output=True, text=True)
        open(log, "w").write(r.stdout + r.stderr)
        res["pip"] = "instalado" if r.returncode == 0 else "ERROR (ver %s)" % log
        res["ok"] &= r.returncode == 0
    try:
        sys.path.insert(0, RAIZ)
        from arvis_lifehacks import recursos
        recursos.preparar()
        from arvis_vida import activos
        activos.preparar_fluent()
        res["recursos"] = "ok (voz, fuentes, Fluent en caché)"
    except Exception as ex:
        res["recursos"] = "ERROR: %s" % str(ex)[:160]
        res["ok"] = False
    h = huella_motor()
    m = est.setdefault("motor", {})
    if res["ok"] and m.get("huella_probada") == h and m.get("pytest", "").startswith("OK"):
        res["pytest"] = "omitido: el motor no ha cambiado desde la prueba del %s (%s)" % (m.get("fecha"), m.get("pytest"))
    elif res["ok"]:
        pruebas = [os.path.join(RAIZ, "tests", x) for x in ("test_vida.py", "test_ops.py", "test_sonda.py", "test_v5.py") if os.path.exists(os.path.join(RAIZ, "tests", x))]
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x"] + pruebas, capture_output=True, text=True, cwd=RAIZ)
        ultima = (r.stdout.strip().splitlines() or ["?"])[-1]
        res["pytest"] = ("OK " if r.returncode == 0 else "FALLO ") + ultima
        if r.returncode == 0:
            m.update(huella_probada=h, pytest="OK " + ultima, fecha=fmt(ahora_madrid()))
        else:
            res["ok"] = False
            res["pytest_resumen"] = [x for x in r.stdout.splitlines() if x.startswith(("FAILED", "ERROR", "E "))][:6]
    res["segundos"] = round(time.time() - t0, 1)
    return res


# ----------------------------------------------------------------------------- MODO B · métricas
def metricas(est, data, ahora):
    ids = [x for x in str(data.get("ids", "")).split(",") if x]
    cols = {k: str(data.get(k, "")).split(",") for k in ("viewsList", "likesList", "commentsList", "pubList", "durList", "privList")}
    por_yt = {s.get("yt"): sh for sh, s in est.get("shorts", {}).items() if s.get("yt")}
    hoy = ahora.strftime("%d/%m/%Y")
    filas_met, ko, videos, sin_mapa = [], {}, [], []
    previo = est.get("metricas", {}).get("videos", {})
    for k, yt in enumerate(ids):
        sh = por_yt.get(yt)
        if not sh:
            sin_mapa.append(yt)
            continue

        def col(n):
            v = cols[n][k] if k < len(cols[n]) else ""
            return v.strip()
        vistas, megusta, coment = int(col("viewsList") or 0), int(col("likesList") or 0), int(col("commentsList") or 0)
        pub = col("pubList")
        try:
            p = dt.datetime.strptime(pub, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
            horas = (dt.datetime.now(dt.timezone.utc) - p).total_seconds() / 3600 if not MADRID else \
                ((ahora.replace(tzinfo=MADRID).astimezone(dt.timezone.utc)) - p).total_seconds() / 3600
        except ValueError:
            horas = None
        dur = col("durList").replace("PT", "").replace("S", "")
        s = est["shorts"][sh]
        nota = "%s, clave metricas-lh (tarea programada) · publishedAt %s%s · %s vistas/h · %s s%s" % (
            fmt(ahora), pub, " (franja %s)" % s["franja"][-5:] if s.get("franja") else "",
            ("%.1f" % (vistas / max(1.0, horas))).replace(".", ",") if horas else "?", dur,
            " · VIDA, %s" % s.get("categoria") if num(sh) >= CAT_VIDA_DESDE else " · informática")
        if sh in previo:
            nota += " · +%d vistas desde %s" % (vistas - int(previo[sh].get("vistas", 0)), est.get("metricas", {}).get("fecha", "?"))
        filas_met.append([sh, hoy, ("%.1f" % horas).replace(".", ",") if horas is not None else "", str(vistas), "", "", "", "",
                          str(megusta), str(coment), "", "API YouTube (Data v3, Make 8260190)", nota])
        if s.get("fila"):
            ko[s["fila"]] = [str(vistas), None, str(megusta), None, hoy]
        if num(sh) >= CAT_VIDA_DESDE:
            videos.append({"id": sh, "titulo": s.get("titulo", ""), "categoria": s.get("categoria"), "gancho_tecnica": s.get("gancho_tecnica"),
                           "duracion": float(dur or 0), "franja": (s.get("franja") or "")[-5:], "horas": horas, "vistas": vistas,
                           "me_gusta": megusta, "comentarios": coment})
        previo_n = previo.get(sh, {})
        previo_n.update(vistas=vistas, me_gusta=megusta, comentarios=coment, horas=round(horas or 0, 1))
        previo[sh] = previo_n
    sys.path.insert(0, RAIZ)
    from arvis_lifehacks import analista
    ant = est.get("pesos_cache") or {}
    an = analista.analizar(videos, ant)
    cambia = an.get("multiplicador_categoria", {}) != (ant.get("multiplicador_categoria") or {})
    filas_ko = None
    if ko:
        r0, r1 = min(ko), max(ko)
        filas_ko = {"rango": "SHORTS!K%d:O%d" % (r0, r1), "valores": [ko.get(r, [None] * 5) for r in range(r0, r1 + 1)],
                    "nota": "null = no tocar esa celda (L y N quedan como estén)"}
    est["metricas"] = {"fecha": fmt(ahora), "videos": previo}
    return {"filas_METRICAS": filas_met, "SHORTS_K_O": filas_ko, "sin_mapa": sin_mapa,
            "analista": {"videos_vida": len(videos), "categorias": an.get("categorias"), "nota": an.get("nota"),
                         "cambia_pesos": cambia, "multiplicador_categoria": an.get("multiplicador_categoria"),
                         "duracion_recomendada": an.get("duracion_recomendada"), "propuestas_franja": an.get("propuestas_franja")},
            "siguiente": ("añade filas_METRICAS (append, una llamada) y escribe SHORTS_K_O (update, una llamada)" +
                          ("; actualiza CONFIG «LIFEHACKS · pesos del Researcher» y una fila en APRENDIZAJE" if cambia else "; pesos sin cambios: no escribas CONFIG ni APRENDIZAJE"))}


# ----------------------------------------------------------------------------- git
def titulos(est):
    """Títulos ya usados (para --publicados del guionista y del motor), sin leer la columna F de SHORTS."""
    t = list(est.get("titulos_publicados", []))
    for sh, s in sorted(est.get("shorts", {}).items()):
        if s.get("titulo") and s["titulo"] not in t and str(s.get("fase", "")).startswith(FASES_OCUPAN):
            t.append(s["titulo"])
    return t


def guardar_git(mensaje):
    rel = os.path.relpath(RUTA, RAIZ)
    st = subprocess.run(["git", "-C", RAIZ, "status", "--porcelain", "--", rel], capture_output=True, text=True).stdout.strip()
    if st:
        subprocess.run(["git", "-C", RAIZ, "add", "--", rel], check=True)
        c = subprocess.run(["git", "-C", RAIZ, "commit", "-q", "-m", mensaje, "--", rel], capture_output=True, text=True)
        if c.returncode != 0:
            return {"ok": False, "error": (c.stderr or c.stdout)[-300:]}
    subprocess.run(["git", "-C", RAIZ, "fetch", "-q", "origin", "vida"], capture_output=True, text=True)
    pend = subprocess.run(["git", "-C", RAIZ, "rev-list", "--count", "origin/vida..HEAD"], capture_output=True, text=True).stdout.strip()
    if pend in ("", "0"):
        return {"ok": True, "commit": None, "nota": "nada que subir"}
    for intento in range(2):
        p = subprocess.run(["git", "-C", RAIZ, "push", "-q", "origin", "HEAD:vida"], capture_output=True, text=True)
        if p.returncode == 0:
            h = subprocess.run(["git", "-C", RAIZ, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
            return {"ok": True, "commit": h}
        subprocess.run(["git", "-C", RAIZ, "pull", "-q", "--rebase", "origin", "vida"], capture_output=True, text=True)
    return {"ok": False, "error": p.stderr[-300:]}


# ----------------------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--ahora", default=None)
    sub.add_parser("entorno")
    p = sub.add_parser("anotar")
    p.add_argument("json")
    p = sub.add_parser("ejecucion")
    p.add_argument("modos")
    p.add_argument("resultado")
    p.add_argument("resumen")
    p = sub.add_parser("error")
    p.add_argument("paso")
    p.add_argument("mensaje")
    p = sub.add_parser("metricas")
    p.add_argument("registro")
    p.add_argument("--ahora", default=None)
    p = sub.add_parser("titulos")
    p.add_argument("salida", nargs="?", default="titulos.json")
    p = sub.add_parser("tema")
    p.add_argument("texto")
    p.add_argument("--encargar", action="store_true", help="lo produce la tarea programada en su próxima ejecución")
    p.add_argument("--publicar", action="store_true", help="Aleksei ya autorizó subirlo si llega a 85")
    p = sub.add_parser("aprobar")
    p.add_argument("sh")
    p.add_argument("quien")
    sub.add_parser("franja")
    p = sub.add_parser("guardar")
    p.add_argument("mensaje", nargs="?", default="ARVIS 3.1: estado de LIFEHACKS")
    a = ap.parse_args(argv)
    est = cargar()
    if a.cmd == "plan":
        out = plan(est, ahora_madrid(a.ahora))
    elif a.cmd == "entorno":
        out = entorno(est)
        guardar_local(est)
    elif a.cmd == "anotar":
        fusionar(est, json.loads(a.json))
        guardar_local(est)
        out = {"ok": True}
    elif a.cmd == "ejecucion":
        est.setdefault("ejecuciones", []).append({"fecha": fmt(ahora_madrid()), "modos": a.modos, "resultado": a.resultado, "resumen": a.resumen[:300]})
        est["ejecuciones"] = est["ejecuciones"][-9:]
        guardar_local(est)
        out = {"ok": True}
    elif a.cmd == "error":
        est.setdefault("errores", []).append({"fecha": fmt(ahora_madrid()), "paso": a.paso, "error": a.mensaje[:240], "resuelto": False})
        est["errores"] = est["errores"][-10:]
        guardar_local(est)
        out = {"ok": True}
    elif a.cmd == "metricas":
        data = json.load(open(a.registro, encoding="utf-8"))
        data = data.get("data", data)
        out = metricas(est, data, ahora_madrid(a.ahora))
        guardar_local(est)
    elif a.cmd == "titulos":
        t = titulos(est)
        json.dump(t, open(a.salida, "w", encoding="utf-8"), ensure_ascii=False)
        out = {"ok": True, "titulos": len(t), "archivo": a.salida}
    elif a.cmd == "tema":
        out = tema(est, a.texto, a.encargar, a.publicar)
        guardar_local(est)
    elif a.cmd == "aprobar":
        out = aprobar(est, a.sh, a.quien)
        if out.get("ok"):
            guardar_local(est)
    elif a.cmd == "franja":
        f, motivo = franja_libre(est, ahora_madrid())
        out = {"franja": fmt(f) if f else None, "publishAt": utc_iso(f) if f else None, "motivo": motivo}
    elif a.cmd == "guardar":
        out = guardar_git(a.mensaje)
    # salida compacta (cada carácter impreso entra en el contexto de Claude)
    print("{\n" + ",\n".join(" %s: %s" % (json.dumps(k, ensure_ascii=False), json.dumps(v, ensure_ascii=False, separators=(",", ":")))
                             for k, v in out.items()) + "\n}")
    return 0 if out.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(main())
