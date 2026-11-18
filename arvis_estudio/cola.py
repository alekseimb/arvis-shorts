"""Cola de producción persistente (SQLite) con estados verificados, historial y recuperación tras reinicios.

Estados (el sistema sabe siempre en cuál está cada vídeo):
  investigado → guionizado → generando → editando → validando → aprobado → subido → publicado
  corregir (no llega a la nota: vuelve al agente responsable) · espera_manual · error · descartado
Ningún paso se marca hecho sin su prueba (evidencia): archivo existente, informe, nota, respuesta de YouTube.
Nada se borra: un vídeo retirado pasa a «descartado».
"""
import json
import os
import sqlite3
import time
from contextlib import contextmanager

ESTADOS = ["investigado", "guionizado", "generando", "editando", "validando", "aprobado", "subido", "publicado",
           "corregir", "espera_manual", "error", "descartado"]

TRANSICIONES = {
    "investigado": {"guionizado", "descartado"},
    "guionizado": {"generando", "descartado", "error"},
    "generando": {"editando", "error", "guionizado", "descartado"},
    "editando": {"validando", "error", "generando", "descartado"},
    "validando": {"aprobado", "corregir", "error", "descartado"},
    "corregir": {"guionizado", "generando", "editando", "descartado"},
    "aprobado": {"subido", "espera_manual", "descartado"},
    "espera_manual": {"subido", "aprobado", "descartado"},
    "subido": {"publicado", "error", "subido"},
    "publicado": set(),
    "error": {"guionizado", "generando", "editando", "validando", "aprobado", "subido", "descartado"},
    "descartado": set(),
}

# prueba obligatoria para entrar en cada estado
EVIDENCIA = {
    "guionizado": ("guion",),
    "editando": ("imagenes_ok",),
    "validando": ("mp4", "informe"),
    "aprobado": ("puntuacion", "evaluacion"),
    "corregir": ("motivos",),
    "subido": ("video_id", "privacidad_real"),
    "publicado": ("confirmacion_api",),
    "error": ("error",),
    "descartado": ("motivo",),
}

TRANSITORIOS = ("generando", "editando", "validando")

ESQUEMA = """
CREATE TABLE IF NOT EXISTS trabajos(
  clave TEXT PRIMARY KEY, tipo TEXT NOT NULL, pilar TEXT, titulo TEXT, estado TEXT NOT NULL,
  prioridad INTEGER DEFAULT 5, intentos INTEGER DEFAULT 0, reediciones INTEGER DEFAULT 0,
  guion TEXT, carpeta TEXT, mp4 TEXT, sha256 TEXT, puntuacion REAL,
  video_id TEXT, privacidad_pedida TEXT, privacidad_real TEXT, publicar_en TEXT, subida_url TEXT,
  bloqueo TEXT, bloqueo_hasta REAL, error TEXT, datos TEXT DEFAULT '{}',
  creado REAL, actualizado REAL);
CREATE TABLE IF NOT EXISTS eventos(id INTEGER PRIMARY KEY AUTOINCREMENT, clave TEXT, momento REAL,
  de_estado TEXT, a_estado TEXT, detalle TEXT);
CREATE TABLE IF NOT EXISTS publicaciones(video_id TEXT PRIMARY KEY, clave TEXT, sha256 TEXT, subido REAL,
  privacidad_pedida TEXT, privacidad_real TEXT, estado_subida TEXT, confirmado REAL, url TEXT, notas TEXT);
CREATE TABLE IF NOT EXISTS firmas(clave TEXT PRIMARY KEY, pilar TEXT, variante TEXT, firma TEXT, momento REAL);
CREATE INDEX IF NOT EXISTS ix_estado ON trabajos(estado);
CREATE INDEX IF NOT EXISTS ix_pub_sha ON publicaciones(sha256);
"""


class TransicionInvalida(Exception):
    pass


class Cola:
    def __init__(self, ruta):
        self.ruta = str(ruta)
        os.makedirs(os.path.dirname(self.ruta) or ".", exist_ok=True)
        with self._c() as c:
            c.executescript(ESQUEMA)

    @contextmanager
    def _c(self):
        c = sqlite3.connect(self.ruta, timeout=30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        try:
            yield c
            c.commit()
        finally:
            c.close()

    # ------------------------------------------------------------ alta y consulta
    def alta(self, clave, tipo, pilar, titulo, guion=None, prioridad=5, estado="investigado", datos=None):
        if tipo not in ("largo", "short"):
            raise ValueError("tipo debe ser largo o short")
        ahora = time.time()
        with self._c() as c:
            if c.execute("SELECT 1 FROM trabajos WHERE clave=?", (clave,)).fetchone():
                return False                       # nunca se duplica una clave
            c.execute("INSERT INTO trabajos(clave,tipo,pilar,titulo,estado,prioridad,guion,datos,creado,actualizado) VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (clave, tipo, pilar, titulo, "investigado", prioridad, None, json.dumps(datos or {}), ahora, ahora))
            c.execute("INSERT INTO eventos(clave,momento,de_estado,a_estado,detalle) VALUES(?,?,?,?,?)", (clave, ahora, None, "investigado", "alta"))
        if estado == "guionizado":
            self.mover(clave, "guionizado", {"guion": guion})
        return True

    def get(self, clave):
        with self._c() as c:
            r = c.execute("SELECT * FROM trabajos WHERE clave=?", (clave,)).fetchone()
        return dict(r) if r else None

    def lista(self, estados=None):
        with self._c() as c:
            if estados:
                q = "SELECT * FROM trabajos WHERE estado IN (%s) ORDER BY prioridad, creado" % ",".join("?" * len(estados))
                return [dict(r) for r in c.execute(q, list(estados))]
            return [dict(r) for r in c.execute("SELECT * FROM trabajos ORDER BY creado")]

    def eventos(self, clave):
        with self._c() as c:
            return [dict(r) for r in c.execute("SELECT * FROM eventos WHERE clave=? ORDER BY id", (clave,))]

    # ------------------------------------------------------------ estados
    def mover(self, clave, a, evidencia=None, **campos):
        evidencia = evidencia or {}
        if a not in ESTADOS:
            raise TransicionInvalida("estado desconocido: %s" % a)
        t = self.get(clave)
        if not t:
            raise TransicionInvalida("no existe %s" % clave)
        if a not in TRANSICIONES[t["estado"]]:
            raise TransicionInvalida("%s: %s → %s no permitido" % (clave, t["estado"], a))
        faltan = [k for k in EVIDENCIA.get(a, ()) if evidencia.get(k) in (None, "", [], {})]
        if faltan:
            raise TransicionInvalida("%s → %s sin prueba: falta %s" % (clave, a, ", ".join(faltan)))
        if a == "validando" and not os.path.exists(evidencia["mp4"]):
            raise TransicionInvalida("%s → validando: el MP4 no existe" % clave)
        if a == "publicado" and evidencia["confirmacion_api"].get("privacyStatus") != "public":
            raise TransicionInvalida("%s → publicado: YouTube no dice public" % clave)
        mapa = {"guion": "guion", "mp4": "mp4", "puntuacion": "puntuacion", "video_id": "video_id",
                "privacidad_real": "privacidad_real", "error": "error"}
        sets = {mapa[k]: v for k, v in evidencia.items() if k in mapa}
        sets.update(campos)
        if a == "corregir":
            sets["reediciones"] = (t["reediciones"] or 0) + 1
        if a in ("generando", "editando", "validando", "subido"):
            sets.setdefault("error", None)
        sets.update({"estado": a, "actualizado": time.time(), "bloqueo": None, "bloqueo_hasta": None})
        with self._c() as c:
            c.execute("UPDATE trabajos SET %s WHERE clave=?" % ",".join("%s=?" % k for k in sets), list(sets.values()) + [clave])
            c.execute("INSERT INTO eventos(clave,momento,de_estado,a_estado,detalle) VALUES(?,?,?,?,?)",
                      (clave, time.time(), t["estado"], a, json.dumps({k: v for k, v in evidencia.items() if k != "confirmacion_api"}, ensure_ascii=False)[:2000]))
        return self.get(clave)

    def anotar(self, clave, **campos):
        campos["actualizado"] = time.time()
        with self._c() as c:
            c.execute("UPDATE trabajos SET %s WHERE clave=?" % ",".join("%s=?" % k for k in campos), list(campos.values()) + [clave])

    def fallo(self, clave, paso, mensaje, max_intentos=3):
        """Cuenta un intento fallido; a partir de max_intentos pasa a «error» (y lo avisa el servicio)."""
        t = self.get(clave)
        n = (t["intentos"] or 0) + 1
        self.anotar(clave, intentos=n, error="%s: %s" % (paso, mensaje[:500]), bloqueo=None, bloqueo_hasta=None)
        with self._c() as c:
            c.execute("INSERT INTO eventos(clave,momento,de_estado,a_estado,detalle) VALUES(?,?,?,?,?)",
                      (clave, time.time(), t["estado"], t["estado"], "fallo %d en %s: %s" % (n, paso, mensaje[:300])))
        if n >= max_intentos and t["estado"] != "error":
            self.mover(clave, "error", {"error": "%s: %s" % (paso, mensaje[:300])})
            return True
        return False

    # ------------------------------------------------------------ bloqueo y recuperación
    def reservar(self, clave, quien, minutos=180):
        ahora = time.time()
        with self._c() as c:
            r = c.execute("UPDATE trabajos SET bloqueo=?, bloqueo_hasta=? WHERE clave=? AND (bloqueo IS NULL OR bloqueo_hasta < ?)",
                          (quien, ahora + minutos * 60, clave, ahora))
            return r.rowcount == 1

    def liberar(self, clave):
        self.anotar(clave, bloqueo=None, bloqueo_hasta=None)

    def recuperar(self):
        """Tras un reinicio o un corte: libera bloqueos caducados. El trabajo sigue en su estado y
        se reanuda desde el último paso guardado (las imágenes y el audio ya hechos se reutilizan)."""
        ahora = time.time()
        with self._c() as c:
            filas = [dict(r) for r in c.execute("SELECT clave, estado FROM trabajos WHERE bloqueo IS NOT NULL AND bloqueo_hasta < ?", (ahora,))]
            for f in filas:
                c.execute("UPDATE trabajos SET bloqueo=NULL, bloqueo_hasta=NULL WHERE clave=?", (f["clave"],))
                c.execute("INSERT INTO eventos(clave,momento,de_estado,a_estado,detalle) VALUES(?,?,?,?,?)",
                          (f["clave"], ahora, f["estado"], f["estado"], "recuperado tras corte: se reanuda desde el último paso guardado"))
        return filas

    def siguiente(self, saltar=()):
        """Próximo trabajo con algo que hacer en el Mac, sin bloqueo: primero lo más avanzado (acabar antes que empezar).
        «corregir» y «espera_manual» no están: los resuelven los agentes de la nube o Aleksei."""
        orden = ["subido", "aprobado", "validando", "editando", "generando", "guionizado"]
        ahora = time.time()
        for est in orden:
            for t in self.lista([est]):
                if t["clave"] in saltar:
                    continue
                if not t["bloqueo"] or (t["bloqueo_hasta"] or 0) < ahora:
                    return t
        return None

    # ------------------------------------------------------------ publicaciones y duplicados
    def publicacion_por_sha(self, sha):
        with self._c() as c:
            r = c.execute("SELECT * FROM publicaciones WHERE sha256=?", (sha,)).fetchone()
        return dict(r) if r else None

    def registrar_publicacion(self, video_id, clave, sha, pedida, real, estado_subida, url, notas=""):
        with self._c() as c:
            c.execute("INSERT OR REPLACE INTO publicaciones(video_id,clave,sha256,subido,privacidad_pedida,privacidad_real,estado_subida,confirmado,url,notas) "
                      "VALUES(?,?,?,?,?,?,?,?,?,?)", (video_id, clave, sha, time.time(), pedida, real, estado_subida, None, url, notas))

    def confirmar_publicacion(self, video_id, real, estado_subida):
        with self._c() as c:
            c.execute("UPDATE publicaciones SET privacidad_real=?, estado_subida=?, confirmado=? WHERE video_id=?", (real, estado_subida, time.time(), video_id))

    def publicaciones(self):
        with self._c() as c:
            return [dict(r) for r in c.execute("SELECT * FROM publicaciones ORDER BY subido")]

    # ------------------------------------------------------------ firmas visuales (anti-plantilla)
    def guardar_firma(self, clave, pilar, variante, firma):
        with self._c() as c:
            c.execute("INSERT OR REPLACE INTO firmas VALUES(?,?,?,?,?)", (clave, pilar, variante, json.dumps(firma), time.time()))

    def firmas_recientes(self, pilar=None, n=20):
        with self._c() as c:
            q = "SELECT * FROM firmas %s ORDER BY momento DESC LIMIT ?" % ("WHERE pilar=?" if pilar else "")
            filas = c.execute(q, ((pilar, n) if pilar else (n,))).fetchall()
        return [dict(r, firma=json.loads(r["firma"])) for r in filas]

    def resumen(self):
        cuenta = {e: 0 for e in ESTADOS}
        for t in self.lista():
            cuenta[t["estado"]] += 1
        return cuenta
