"""Autorización OAuth de YouTube en el Mac (una sola vez). Guarda las credenciales en el Llavero de macOS.

Antes (Aleksei, en Google Cloud con la cuenta del canal): proyecto «ARVIS Estudio» → activar «YouTube Data API v3» →
pantalla de consentimiento «Externo» y estado de publicación «En producción» (en «Prueba» el permiso caduca a los 7 días) →
credencial «ID de cliente OAuth» de tipo «App de escritorio» → descargar el JSON.

Uso:  python3 -m arvis_estudio.autorizar ~/Downloads/client_secret_XXXX.json
Abre el navegador, pides permiso con la cuenta del canal y el script guarda client_id, client_secret y refresh_token
en el Llavero (servicio «arvis-youtube»). Nada se escribe en archivos ni sale del Mac. Después borra el JSON descargado.
Permisos pedidos: youtube.upload (subir y miniaturas) y youtube.readonly (comprobar canal y estado de los vídeos).
"""
import base64
import hashlib
import http.server
import json
import os
import secrets
import subprocess
import sys
import urllib.parse
import urllib.request
import webbrowser

SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"


def guardar(campo, valor, servicio="arvis-youtube"):
    subprocess.run(["security", "add-generic-password", "-U", "-s", servicio, "-a", campo, "-w", valor], check=True, capture_output=True)


def main():
    cfg = json.load(open(os.path.expanduser(sys.argv[1])))
    c = cfg.get("installed") or cfg.get("web")
    cid, csec = c["client_id"], c["client_secret"]
    verif = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    reto = base64.urlsafe_b64encode(hashlib.sha256(verif.encode()).digest()).rstrip(b"=").decode()
    estado = secrets.token_urlsafe(16)
    recibido = {}

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            recibido.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<h2>ARVIS: permiso recibido. Puedes cerrar esta pestaña.</h2>".encode())

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    redir = "http://127.0.0.1:%d" % srv.server_address[1]
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": cid, "redirect_uri": redir, "response_type": "code", "scope": SCOPES, "access_type": "offline",
        "prompt": "consent", "state": estado, "code_challenge": reto, "code_challenge_method": "S256"})
    print("Se abre el navegador. Entra con la cuenta del canal (vagary.escala@gmail.com) y acepta.")
    webbrowser.open(url)
    while "code" not in recibido and "error" not in recibido:
        srv.handle_request()
    if recibido.get("state") != estado or "code" not in recibido:
        sys.exit("Autorización cancelada o no válida: %s" % recibido.get("error", "estado incorrecto"))
    body = urllib.parse.urlencode({"code": recibido["code"], "client_id": cid, "client_secret": csec, "redirect_uri": redir,
                                   "grant_type": "authorization_code", "code_verifier": verif}).encode()
    with urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=body), timeout=30) as r:
        tok = json.loads(r.read())
    if "refresh_token" not in tok:
        sys.exit("Google no devolvió refresh_token. Revisa que la app sea de escritorio y vuelve a intentarlo.")
    guardar("client_id", cid)
    guardar("client_secret", csec)
    guardar("refresh_token", tok["refresh_token"])
    print("Guardado en el Llavero (servicio arvis-youtube). Comprueba con: python3 -m arvis_estudio.servicio comprobar")
    print("Ya puedes borrar el archivo JSON descargado.")


if __name__ == "__main__":
    main()
