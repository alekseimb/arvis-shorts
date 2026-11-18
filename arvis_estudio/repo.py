"""Puente con GitHub (sin vídeos): órdenes y guiones de la nube → Mac; revisiones (fotogramas + informe) y estado → nube.

Estructura del repositorio de órdenes:
  ordenes/<clave>.json        {"clave","tipo","pilar","titulo","guion":"guiones/<clave>.json","prioridad"}
  guiones/<clave>.json        guion del motor (escenas «image» con prompt)
  revision/<clave>/           el Mac deja informe.json, guion_motor.json y fotogramas (JPG pequeños) para Control de calidad
  revision/<clave>/evaluacion.json   la deja E6 (Control de calidad, en la nube) con notas y evidencias
Rama «estado»: un único commit que el Mac reescribe con estado/mac.json (latido), sin llenar el historial.
"""
import json
import subprocess
from pathlib import Path


class RepoError(Exception):
    pass


class Repo:
    def __init__(self, ruta):
        self.ruta = Path(ruta).expanduser()

    def _git(self, *args, check=True):
        r = subprocess.run(["git", "-C", str(self.ruta)] + list(args), capture_output=True, text=True, timeout=300)
        if check and r.returncode != 0:
            raise RepoError("git %s: %s" % (" ".join(args[:2]), (r.stderr or r.stdout).strip()[:300]))
        return r.stdout

    def disponible(self):
        return (self.ruta / ".git").exists()

    def actualizar(self):
        self._git("pull", "--ff-only", "-q")

    def ordenes(self):
        d = self.ruta / "ordenes"
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json"))] if d.exists() else []

    def leer(self, rel):
        p = self.ruta / rel
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def ruta_de(self, rel):
        return self.ruta / rel

    def publicar_revision(self, clave, archivos):
        """archivos: {nombre_destino: ruta_origen}. Solo archivos pequeños (nunca vídeo)."""
        dst = self.ruta / "revision" / clave
        dst.mkdir(parents=True, exist_ok=True)
        for nombre, origen in archivos.items():
            o = Path(origen)
            if o.suffix.lower() in (".mp4", ".mov", ".mkv", ".wav") or o.stat().st_size > 2_000_000:
                raise RepoError("no se suben vídeos ni archivos grandes al repositorio: %s" % o.name)
            (dst / nombre).write_bytes(o.read_bytes())
        self._git("add", str(dst))
        if self._git("status", "--porcelain", str(dst)).strip():
            self._git("commit", "-q", "-m", "revisión %s (fotogramas e informe para Control de calidad)" % clave)
            self._git("push", "-q")

    def evaluacion(self, clave):
        return self.leer("revision/%s/evaluacion.json" % clave)

    def latido(self, estado):
        """Reescribe el único commit de la rama «estado» con estado/mac.json."""
        wt = self.ruta.parent / (self.ruta.name + "_estado")
        if not wt.exists():
            self._git("fetch", "-q", "origin", check=False)
            existe = self._git("ls-remote", "--heads", "origin", "estado", check=False).strip()
            if existe:
                self._git("worktree", "add", "-q", str(wt), "estado")
            else:
                self._git("worktree", "add", "-q", "--detach", str(wt))
                subprocess.run(["git", "-C", str(wt), "checkout", "-q", "--orphan", "estado"], check=True)
                subprocess.run(["git", "-C", str(wt), "rm", "-rfq", "."], check=False)
        (wt / "estado").mkdir(exist_ok=True)
        (wt / "estado" / "mac.json").write_text(json.dumps(estado, ensure_ascii=False, indent=1))
        g = ["git", "-C", str(wt)]
        subprocess.run(g + ["add", "estado/mac.json"], check=True)
        tiene = subprocess.run(g + ["rev-parse", "--verify", "-q", "HEAD"], capture_output=True).returncode == 0
        subprocess.run(g + ["commit", "-q"] + (["--amend"] if tiene else []) + ["-m", "latido del Mac"], check=True, capture_output=True)
        r = subprocess.run(g + ["push", "-q", "-f", "origin", "estado"], capture_output=True, text=True)
        if r.returncode != 0:
            raise RepoError("no se pudo publicar el latido: %s" % r.stderr[:200])
