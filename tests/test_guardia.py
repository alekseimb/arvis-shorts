import json
import unittest
from pathlib import Path

from arvis_av import guardia_coste, registro
from arvis_av.qc import srt_sincronizado


class Guardia(unittest.TestCase):
    def test_config_real_bloquea_todo(self):
        cfg = guardia_coste.cargar_config()
        self.assertEqual(cfg["presupuesto_eur"], 0)
        for prov, p in cfg["proveedores"].items():
            self.assertFalse(p["habilitado"], prov)
            with self.assertRaises(guardia_coste.GastoNoAutorizado):
                guardia_coste.comprobar(f"{prov}__cualquier-modelo", cfg)

    def test_habilitado_sin_autorizacion_bloquea(self):
        cfg = {"presupuesto_eur": 0, "proveedores": {"x": {"habilitado": True, "coste_estimado_eur": 0,
                                                           "modelos_permitidos": ["x__m"]}}}
        with self.assertRaises(guardia_coste.GastoNoAutorizado):
            guardia_coste.comprobar("x__m", cfg)

    def test_coste_distinto_de_cero_bloquea(self):
        cfg = {"presupuesto_eur": 0, "proveedores": {"x": {"habilitado": True, "coste_estimado_eur": 0.04,
               "modelos_permitidos": ["x__m"], "autorizado_por": "a", "fecha_autorizacion": "b"}}}
        with self.assertRaises(guardia_coste.GastoNoAutorizado):
            guardia_coste.comprobar("x__m", cfg)

    def test_gratis_y_autorizado_pasa(self):
        cfg = {"presupuesto_eur": 0, "proveedores": {"x": {"habilitado": True, "coste_estimado_eur": 0,
               "modelos_permitidos": ["x__m"], "autorizado_por": "a", "fecha_autorizacion": "b"}}}
        guardia_coste.comprobar("x__m", cfg)


class Registro(unittest.TestCase):
    def test_no_publicado_sin_confirmacion(self):
        with self.assertRaises(ValueError):
            registro.anotar("T", "publicado")


class Srt(unittest.TestCase):
    def test_srt(self):
        p = Path(__file__).with_name("_t.srt")
        p.write_text("1\n00:00:00,000 --> 00:00:02,000\nHola\n\n2\n00:00:02,100 --> 00:00:04,000\nAdiós\n")
        try:
            self.assertTrue(srt_sincronizado(p, 4.0)[0])
            self.assertFalse(srt_sincronizado(p, 2.0)[0])
        finally:
            p.unlink()


if __name__ == "__main__":
    unittest.main()
