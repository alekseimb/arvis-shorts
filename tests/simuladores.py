"""Simuladores locales para las pruebas: ComfyUI y la API de YouTube (subida reanudable). Sin red ni credenciales reales."""
import hashlib
import io
import json
import threading
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
from PIL import Image


def _servir(handler_cls):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    return srv, "http://127.0.0.1:%d" % srv.server_address[1]


# ------------------------------------------------------------------ ComfyUI
class ComfySim:
    """fallos: dict id_prefijo → nº de veces que devuelve una imagen negra antes de funcionar."""

    def __init__(self, fallos=None, siempre_falla=()):
        self.fallos = dict(fallos or {})
        self.siempre = set(siempre_falla)
        self.historial, self.grafos = {}, []
        sim = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _json(self, code, d):
                b = json.dumps(d).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def do_GET(self):
                if self.path == "/system_stats":
                    return self._json(200, {"system": {"os": "posix"}, "devices": [{"name": "mps", "type": "mps"}]})
                if self.path.startswith("/history/"):
                    pid = self.path.split("/")[-1]
                    return self._json(200, {pid: sim.historial[pid]} if pid in sim.historial else {})
                if self.path.startswith("/view?"):
                    q = urllib.parse.parse_qs(self.path[6:])
                    b = sim.imagenes[q["filename"][0]]
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Length", str(len(b)))
                    self.end_headers()
                    return self.wfile.write(b)
                self._json(404, {})

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                d = json.loads(self.rfile.read(n) or b"{}")
                if self.path == "/free":
                    return self._json(200, {})
                if self.path == "/prompt":
                    g = d["prompt"]
                    sim.grafos.append(g)
                    lat = next(v for v in g.values() if v["class_type"] == "EmptySD3LatentImage")["inputs"]
                    save = next(v for v in g.values() if v["class_type"] == "SaveImage")["inputs"]
                    seed = next(v for v in g.values() if v["class_type"] == "KSampler")["inputs"]["seed"]
                    pref = save["filename_prefix"]
                    pid = uuid.uuid4().hex
                    negra = any(pref.endswith(k) for k in sim.siempre)
                    for k in list(sim.fallos):
                        if pref.endswith(k) and sim.fallos[k] > 0:
                            sim.fallos[k] -= 1
                            negra = True
                    w, h = lat["width"], lat["height"]
                    rng = np.random.RandomState(seed % (2 ** 32))
                    if negra:
                        arr = np.zeros((h, w, 3), np.uint8)
                    else:
                        yy = np.linspace(0, 1, h)[:, None, None]
                        arr = np.clip((yy * 180 + rng.rand(h, w, 3) * 60), 0, 255).astype(np.uint8)
                    buf = io.BytesIO()
                    Image.fromarray(arr).save(buf, "PNG")
                    fn = "%s_00001_.png" % pref
                    sim.imagenes[fn] = buf.getvalue()
                    sim.historial[pid] = {"status": {"status_str": "success", "completed": True},
                                          "outputs": {"10": {"images": [{"filename": fn, "subfolder": "", "type": "output"}]}}}
                    return self._json(200, {"prompt_id": pid, "number": 1, "node_errors": {}})
                self._json(404, {})

        self.imagenes = {}
        self.srv, self.url = _servir(H)

    def cerrar(self):
        self.srv.shutdown()


# ------------------------------------------------------------------ YouTube
class YouTubeSim:
    """Simula token, channels.list, subida reanudable (308/Range), videos.list/update y thumbnails.set.
    cortes: lista de nº de PUT que fallan con 503 (1 = el primer PUT de datos)."""

    def __init__(self, cortes=(), auditada=False, canal_id="UCtest"):
        self.cortes = set(cortes)
        self.auditada = auditada
        self.canal_id = canal_id
        self.sesiones, self.videos, self.puts, self.tokens = {}, {}, 0, 0
        sim = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def _resp(self, code, d=None, cab=None):
                b = json.dumps(d).encode() if d is not None else b""
                self.send_response(code)
                for k, v in (cab or {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def _auth(self):
                return self.headers.get("Authorization", "").startswith("Bearer tok")

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(n)
                if self.path == "/token":
                    sim.tokens += 1
                    return self._resp(200, {"access_token": "tok%d" % sim.tokens, "expires_in": 3600})
                if not self._auth():
                    return self._resp(401, {"error": "auth"})
                if self.path.startswith("/upload/youtube/v3/videos"):
                    meta = json.loads(body)
                    sid = uuid.uuid4().hex
                    sim.sesiones[sid] = {"meta": meta, "total": int(self.headers["X-Upload-Content-Length"]), "datos": bytearray()}
                    return self._resp(200, {}, {"Location": sim.url + "/sesion/" + sid})
                if self.path.startswith("/upload/youtube/v3/thumbnails/set"):
                    vid = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)["videoId"][0]
                    sim.videos[vid]["miniatura"] = len(body)
                    return self._resp(200, {"items": [{"default": {"url": "x"}}]})
                self._resp(404, {})

            def do_PUT(self):
                n = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(n)
                if not self._auth():
                    return self._resp(401, {"error": "auth"})
                if self.path.startswith("/sesion/"):
                    sid = self.path.split("/")[-1]
                    s = sim.sesiones.get(sid)
                    if not s:
                        return self._resp(404, {"error": "sesión caducada"})
                    cr = self.headers.get("Content-Range", "")
                    if cr.startswith("bytes */"):
                        if len(s["datos"]) == s["total"] and s.get("video"):
                            return self._resp(201, sim.videos[s["video"]]["recurso"])
                        cab = {"Range": "bytes=0-%d" % (len(s["datos"]) - 1)} if s["datos"] else {}
                        return self._resp(308, None, cab)
                    sim.puts += 1
                    if sim.puts in sim.cortes:
                        return self._resp(503, {"error": "backend"})
                    ini = int(cr.split()[1].split("-")[0])
                    if ini != len(s["datos"]):
                        return self._resp(308, None, {"Range": "bytes=0-%d" % (len(s["datos"]) - 1)})
                    s["datos"] += body
                    if len(s["datos"]) < s["total"]:
                        return self._resp(308, None, {"Range": "bytes=0-%d" % (len(s["datos"]) - 1)})
                    vid = "vid" + sid[:8]
                    pedida = s["meta"]["status"]["privacyStatus"]
                    real = pedida if sim.auditada else "private"
                    rec = {"id": vid, "snippet": s["meta"]["snippet"], "status": {"privacyStatus": real, "uploadStatus": "uploaded"}}
                    sim.videos[vid] = {"recurso": rec, "sha": hashlib.sha256(bytes(s["datos"])).hexdigest(), "meta": s["meta"]}
                    s["video"] = vid
                    return self._resp(201, rec)
                if self.path.startswith("/youtube/v3/videos"):
                    d = json.loads(body)
                    v = sim.videos[d["id"]]
                    v["recurso"]["status"].update(d["status"])
                    return self._resp(200, v["recurso"])
                self._resp(404, {})

            def do_GET(self):
                if not self._auth():
                    return self._resp(401, {"error": "auth"})
                u = urllib.parse.urlparse(self.path)
                q = urllib.parse.parse_qs(u.query)
                if u.path == "/youtube/v3/channels":
                    return self._resp(200, {"items": [{"id": sim.canal_id, "snippet": {"title": "Canal de prueba"}, "status": {}}]})
                if u.path == "/youtube/v3/videos":
                    v = sim.videos.get(q["id"][0])
                    if not v:
                        return self._resp(200, {"items": []})
                    r = v["recurso"]
                    st = dict(r["status"], uploadStatus="processed")
                    return self._resp(200, {"items": [{"id": r["id"], "snippet": r["snippet"], "status": st,
                                                       "processingDetails": {"processingStatus": "succeeded"}}]})
                self._resp(404, {})

        self.srv, self.url = _servir(H)

    def cerrar(self):
        self.srv.shutdown()
