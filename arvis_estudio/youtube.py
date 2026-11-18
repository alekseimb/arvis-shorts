"""Subida directa a YouTube desde el Mac (YouTube Data API v3, OAuth del propio canal).

Lo que comprueba antes y después de subir:
  * canal correcto (channels.list mine=true contra «canal_id_esperado»),
  * duplicados (mismo SHA-256 ya subido → no se vuelve a subir),
  * subida reanudable por trozos (308 + Range), reanudación tras corte y reintentos con espera,
  * finalización (videos.list: uploadStatus y processingStatus),
  * privacidad pedida frente a la real (se registra siempre).
LÍMITE DE GOOGLE: un proyecto de API no auditado solo puede subir en privado y esos vídeos quedan
bloqueados como privados para siempre. Mientras «integracion_youtube_auditada» sea False, este módulo
solo sube en privado y lo deja escrito; no intenta esquivarlo.
Credenciales: en el Llavero de macOS (servicio «arvis-youtube»), nunca en archivos del repositorio.
"""
import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://www.googleapis.com"
TOKEN_URL = "https://oauth2.googleapis.com/token"
TROZO = 8 * 1024 * 1024          # múltiplo de 256 KiB, como pide la API
REINTENTABLES = (500, 502, 503, 504)


class YouTubeError(Exception):
    def __init__(self, msg, codigo=None, reintentable=False):
        super().__init__(msg)
        self.codigo = codigo
        self.reintentable = reintentable


def llavero(campo, servicio="arvis-youtube"):
    """Lee un secreto del Llavero de macOS (security find-generic-password)."""
    r = subprocess.run(["security", "find-generic-password", "-s", servicio, "-a", campo, "-w"], capture_output=True, text=True)
    if r.returncode != 0:
        raise YouTubeError("falta «%s» en el Llavero (servicio %s)" % (campo, servicio))
    return r.stdout.strip()


class OAuth:
    def __init__(self, client_id=None, client_secret=None, refresh_token=None, token_url=TOKEN_URL):
        self.client_id = client_id or llavero("client_id")
        self.client_secret = client_secret or llavero("client_secret")
        self.refresh_token = refresh_token or llavero("refresh_token")
        self.token_url = token_url
        self._tok, self._exp = None, 0

    def token(self, forzar=False):
        if self._tok and not forzar and time.time() < self._exp - 60:
            return self._tok
        body = urllib.parse.urlencode({"client_id": self.client_id, "client_secret": self.client_secret,
                                       "refresh_token": self.refresh_token, "grant_type": "refresh_token"}).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(self.token_url, data=body), timeout=30) as r:
                d = json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise YouTubeError("no se pudo renovar el acceso: %s %s" % (e.code, e.read()[:200]), e.code)
        self._tok, self._exp = d["access_token"], time.time() + int(d.get("expires_in", 3600))
        return self._tok


class YouTube:
    def __init__(self, oauth, base=API, espera_base=2.0, registro=print):
        self.oauth, self.base, self.espera_base, self.log = oauth, base.rstrip("/"), espera_base, registro

    # ------------------------------------------------------------ HTTP
    def _http(self, metodo, url, datos=None, cabeceras=None, t=120):
        cab = {"Authorization": "Bearer " + self.oauth.token()}
        cab.update(cabeceras or {})
        req = urllib.request.Request(url, data=datos, method=metodo, headers=cab)
        try:
            with urllib.request.urlopen(req, timeout=t) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            raise YouTubeError("red: %s" % e, reintentable=True)

    def _json(self, metodo, ruta, cuerpo=None, query=None):
        url = self.base + ruta + ("?" + urllib.parse.urlencode(query) if query else "")
        for intento in range(4):
            datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
            st, _, b = self._http(metodo, url, datos, {"Content-Type": "application/json"} if datos else None)
            if st == 401 and intento == 0:
                self.oauth.token(forzar=True)
                continue
            if st in REINTENTABLES:
                time.sleep(self.espera_base * 2 ** intento)
                continue
            if st >= 400:
                raise YouTubeError("%s %s → %s %s" % (metodo, ruta, st, b[:300].decode("utf-8", "replace")), st)
            return json.loads(b) if b else {}
        raise YouTubeError("%s %s: sin respuesta válida tras reintentos" % (metodo, ruta), reintentable=True)

    # ------------------------------------------------------------ comprobaciones
    def canal(self):
        d = self._json("GET", "/youtube/v3/channels", query={"part": "id,snippet,status", "mine": "true"})
        it = d.get("items") or []
        if not it:
            raise YouTubeError("la cuenta autorizada no tiene canal")
        c = it[0]
        return {"id": c["id"], "titulo": c["snippet"]["title"], "estado": c.get("status", {})}

    def estado_video(self, video_id):
        d = self._json("GET", "/youtube/v3/videos", query={"part": "status,processingDetails,snippet", "id": video_id})
        it = d.get("items") or []
        if not it:
            return None
        s = it[0].get("status", {})
        p = it[0].get("processingDetails", {})
        return {"privacyStatus": s.get("privacyStatus"), "uploadStatus": s.get("uploadStatus"), "publishAt": s.get("publishAt"),
                "failureReason": s.get("failureReason"), "rejectionReason": s.get("rejectionReason"),
                "containsSyntheticMedia": s.get("containsSyntheticMedia"), "processingStatus": p.get("processingStatus"),
                "titulo": it[0]["snippet"]["title"]}

    def esperar_procesado(self, video_id, timeout=1800, cada=20):
        fin = time.time() + timeout
        while time.time() < fin:
            e = self.estado_video(video_id)
            if e and e["uploadStatus"] in ("processed", "failed", "rejected", "deleted"):
                return e
            time.sleep(cada)
        return self.estado_video(video_id)

    # ------------------------------------------------------------ subida reanudable
    def subir(self, ruta_mp4, meta, privacidad, cola=None, clave=None, publicar_en=None, sintetico=False, auditada=False):
        """meta: {"title","description","tags","categoryId"}. Devuelve dict con video_id y privacidad real."""
        sha = _sha_archivo(ruta_mp4)
        if cola:
            prev = cola.publicacion_por_sha(sha)
            if prev:
                self.log("[youtube] duplicado: %s ya subido como %s; no se vuelve a subir" % (clave, prev["video_id"]))
                return {"video_id": prev["video_id"], "duplicado": True, "privacidad_pedida": prev["privacidad_pedida"],
                        "privacidad_real": prev["privacidad_real"], "sha256": sha}
        pedida = privacidad if auditada else "private"
        nota = "" if auditada else "proyecto de API sin auditar: YouTube solo permite privado y no se podrá hacer público"
        estado = {"privacyStatus": pedida, "selfDeclaredMadeForKids": False, "containsSyntheticMedia": bool(sintetico)}
        if publicar_en and auditada:
            estado.update({"privacyStatus": "private", "publishAt": publicar_en})
            pedida = "private→public " + publicar_en
        cuerpo = {"snippet": {"title": meta["title"][:100], "description": meta.get("description", "")[:4900],
                              "tags": meta.get("tags", [])[:30], "categoryId": str(meta.get("categoryId", "27")),
                              "defaultLanguage": "es", "defaultAudioLanguage": "es"}, "status": estado}
        total = os.path.getsize(ruta_mp4)
        sesion = (cola.get(clave) or {}).get("subida_url") if cola and clave else None
        if not sesion:
            sesion = self._abrir_sesion(cuerpo, total)
            if cola and clave:
                cola.anotar(clave, subida_url=sesion, privacidad_pedida=pedida, sha256=sha)
        recurso = self._enviar(ruta_mp4, sesion, total, cuerpo, cola, clave)
        vid = recurso["id"]
        real = recurso.get("status", {}).get("privacyStatus")
        if cola:
            cola.registrar_publicacion(vid, clave, sha, pedida, real, recurso.get("status", {}).get("uploadStatus"),
                                       "https://youtu.be/" + vid, nota)
            if clave:
                cola.anotar(clave, subida_url=None)
        self.log("[youtube] %s subido: %s (pedido %s, YouTube dice %s)" % (clave, vid, pedida, real))
        return {"video_id": vid, "duplicado": False, "privacidad_pedida": pedida, "privacidad_real": real, "sha256": sha, "nota": nota}

    def _abrir_sesion(self, cuerpo, total):
        url = self.base + "/upload/youtube/v3/videos?" + urllib.parse.urlencode({"uploadType": "resumable", "part": "snippet,status"})
        for intento in range(4):
            st, cab, b = self._http("POST", url, json.dumps(cuerpo).encode(),
                                    {"Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Type": "video/mp4",
                                     "X-Upload-Content-Length": str(total)})
            if st == 200 and _cab(cab, "Location"):
                return _cab(cab, "Location")
            if st == 401 and intento == 0:
                self.oauth.token(forzar=True)
                continue
            if st in REINTENTABLES:
                time.sleep(self.espera_base * 2 ** intento)
                continue
            raise YouTubeError("no se pudo abrir la subida: %s %s" % (st, b[:300].decode("utf-8", "replace")), st)
        raise YouTubeError("no se pudo abrir la subida tras reintentos", reintentable=True)

    def _consultar(self, sesion, total):
        """Pregunta a YouTube cuánto ha recibido. Devuelve (siguiente_byte, recurso_si_terminó)."""
        st, cab, b = self._http("PUT", sesion, b"", {"Content-Range": "bytes */%d" % total, "Content-Length": "0"})
        if st in (200, 201):
            return total, json.loads(b)
        if st == 308:
            rg = _cab(cab, "Range")
            return (int(rg.split("-")[1]) + 1 if rg else 0), None
        if st in (404, 410):
            return None, None                       # la sesión caducó
        raise YouTubeError("consulta de subida: %s" % st, st, st in REINTENTABLES)

    def _enviar(self, ruta, sesion, total, cuerpo, cola, clave):
        pos, fallos = 0, 0
        if cola and clave:
            pos, rec = self._consultar(sesion, total)
            if rec:
                return rec
            if pos is None:
                sesion = self._abrir_sesion(cuerpo, total)
                cola.anotar(clave, subida_url=sesion)
                pos = 0
        with open(ruta, "rb") as f:
            while True:
                f.seek(pos)
                trozo = f.read(TROZO)
                fin = pos + len(trozo) - 1
                try:
                    st, cab, b = self._http("PUT", sesion, trozo, {"Content-Type": "video/mp4", "Content-Length": str(len(trozo)),
                                                                   "Content-Range": "bytes %d-%d/%d" % (pos, fin, total)}, t=600)
                except YouTubeError:
                    st, cab, b = None, {}, b""
                if st in (200, 201):
                    return json.loads(b)
                if st == 308:
                    rg = _cab(cab, "Range")
                    pos = int(rg.split("-")[1]) + 1 if rg else 0
                    fallos = 0
                    continue
                if st in (400, 403) or (st and 400 <= st < 500 and st not in (404, 408, 410, 429)):
                    raise YouTubeError("subida rechazada: %s %s" % (st, b[:300].decode("utf-8", "replace")), st)
                fallos += 1
                if fallos > 6:
                    raise YouTubeError("subida interrumpida demasiadas veces", st, True)
                time.sleep(self.espera_base * 2 ** min(fallos, 5))
                pos, rec = self._consultar(sesion, total)
                if rec:
                    return rec
                if pos is None:
                    sesion = self._abrir_sesion(cuerpo, total)
                    if cola and clave:
                        cola.anotar(clave, subida_url=sesion)
                    pos = 0

    # ------------------------------------------------------------ después de subir
    def miniatura(self, video_id, ruta_img):
        datos = open(ruta_img, "rb").read()
        if len(datos) > 2 * 1024 * 1024:
            raise YouTubeError("la miniatura supera 2 MB")
        tipo = "image/png" if ruta_img.lower().endswith(".png") else "image/jpeg"
        url = self.base + "/upload/youtube/v3/thumbnails/set?" + urllib.parse.urlencode({"videoId": video_id})
        st, _, b = self._http("POST", url, datos, {"Content-Type": tipo})
        if st >= 400:
            raise YouTubeError("miniatura: %s %s (¿canal verificado por teléfono?)" % (st, b[:200].decode("utf-8", "replace")), st)
        return True

    def cambiar_estado(self, video_id, privacidad, publicar_en=None, sintetico=None, auditada=False):
        if privacidad != "private" and not auditada:
            raise YouTubeError("bloqueado: el proyecto de API no está auditado; un vídeo subido por API no puede hacerse público")
        st = {"privacyStatus": privacidad}
        if publicar_en:
            st.update({"privacyStatus": "private", "publishAt": publicar_en})
        if sintetico is not None:
            st["containsSyntheticMedia"] = bool(sintetico)
        return self._json("PUT", "/youtube/v3/videos", {"id": video_id, "status": st}, {"part": "status"})


def _cab(cab, nombre):
    for k, v in cab.items():
        if k.lower() == nombre.lower():
            return v
    return None


def _sha_archivo(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()
