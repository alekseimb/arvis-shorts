"""Arreglos del motor pedidos por el QC visual de SH-033 (25/11/2026)."""
import re

from arvis_vida import activos, fondos, motor, props, texto


def _ws(frase):
    return [{"w": w, "t0": i * 0.3, "t1": i * 0.3 + 0.25} for i, w in enumerate(frase.split())]


def _bloques(frase):
    return [" ".join(x["w"] for x in b["palabras"]) for b in texto.bloques(_ws(frase))]


def test_subtitulos_no_parten_rangos_unidades_ni_nombres():
    b = _bloques("La Comunidad de Madrid recomienda poner el termostato de la calefacción entre 18 y 20 grados.")
    assert "La Comunidad de Madrid" in b
    assert any("18 y 20 grados." in x for x in b)
    b = _bloques("Recuerda: casa de 18 a 20, y calentador de 55 a 60.")
    assert "18 a 20," in b and "55 a 60." in b
    b = _bloques("Y con un buen aislamiento se puede ahorrar hasta un 40 % en calefacción.")
    assert any("40 %" in x for x in b)
    # no se pierde ni se repite ninguna palabra y los bloques siguen siendo cortos
    for f in ("Entonces la OCU recomienda sacudir el filtro cada semana. Atrapa restos, y hasta monedas, para que no lleguen a la bomba.",
              "El calentador de agua también tiene el suyo: entre 55 y 60 grados."):
        b = texto.bloques(_ws(f))
        assert [w["w"] for k in b for w in k["palabras"]] == f.split()
        assert all(len(" ".join(w["w"] for w in k["palabras"])) <= 26 for k in b)


def test_icono_guardar_es_un_disquete_y_hucha_es_un_prop_con_moneda():
    assert activos.CATALOGO["guardar"][0] == "Floppy disk"
    assert activos.existe("guardar")
    assert "hucha" in props.PROPS and activos.existe("hucha")
    p = props.crear("hucha")
    assert [c["id"] for c in p["capas"]] == ["base", "moneda", "frente"]
    img = activos.svg_a_png(p["capas"][1]["svg"], 220, 190)
    assert img.getbbox() is not None   # la moneda se dibuja


def test_titulo_del_gancho_legible_en_el_primer_fotograma():
    esc, dy, a = motor.escala_titulo("gancho", 0.0, primera=True)
    assert esc >= 0.88 and a == 1.0 and dy == 0
    esc, _, a = motor.escala_titulo("gancho", 0.0)   # ganchos que no abren el vídeo: entrada «pop» como antes
    assert esc == 0.0 and a == 0.0
    assert motor.escala_titulo("tutorial", 1.0)[0] == 1.0


def test_tiradores_del_dormitorio_fuera_de_la_zona_del_titulo():
    svg = fondos.dormitorio(("#e9e4f5", "#b9a7d9", "#f29b38", "#8a6f5a"))
    ys = [int(y) for y in re.findall(r'<rect x="\d+" y="(\d+)" width="16" height="140"', svg)]
    assert len(ys) == 3 and min(ys) >= fondos._y(0.30)
