import json
import tempfile
import unittest
from pathlib import Path

try:
    from arvis_av import productor_short as ps
except ImportError:  # CI ligera sin Pillow: se omite
    ps = None

from arvis_av.qc import srt_sincronizado

RAIZ = Path(__file__).resolve().parent.parent


@unittest.skipIf(ps is None, "Pillow no instalado")
class Subtitulos(unittest.TestCase):
    def test_trocear_cubre_la_frase_en_orden(self):
        cues = ps.trocear("uno dos tres cuatro cinco seis siete", 1.0, 3.5, max_pal=3)
        self.assertEqual(" ".join(t for _, _, t in cues), "uno dos tres cuatro cinco seis siete")
        self.assertAlmostEqual(cues[0][0], 1.0); self.assertAlmostEqual(cues[-1][1], 4.5)
        self.assertTrue(all(a < b for a, b, _ in cues))

    def test_srt_generado_es_valido(self):
        with tempfile.TemporaryDirectory() as d:
            srt = ps.escribir_srt(ps.trocear("hola mundo esto es ARVIS", 0, 2.0, 2), Path(d) / "x.srt")
            ok, _ = srt_sincronizado(srt, 2.0)
            self.assertTrue(ok)


class Guiones(unittest.TestCase):
    def test_guiones_tienen_campos_obligatorios(self):
        for g in (RAIZ / "guiones").glob("*.json"):
            d = json.loads(g.read_text(encoding="utf-8"))
            for k in ("pieza", "tipo", "titulo", "descripcion", "escenas", "fuentes"):
                self.assertIn(k, d, f"{g.name}: falta {k}")
            self.assertTrue(all(e.get("voz") and e.get("titular") for e in d["escenas"]), g.name)
            self.assertLessEqual(len(d["titulo"]), 100, "YouTube limita el título a 100 caracteres")


if __name__ == "__main__":
    unittest.main()
