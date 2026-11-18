"""Pruebas de duplicados.py (AI TUTORIAL BUILDER): encuentra copias aunque cambie el nombre, mira subcarpetas,
suma bien el espacio y NO borra ni modifica nada."""
import os
import runpy
import sys
from pathlib import Path


def _correr(carpeta, capsys):
    sys.argv = ["duplicados.py", str(carpeta)]
    runpy.run_path(str(Path(__file__).with_name("duplicados.py")), run_name="__main__")
    return capsys.readouterr().out


def _foto(ruta, contenido):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(contenido)


def test_detecta_copias_con_otro_nombre_y_en_subcarpetas(tmp_path, capsys):
    a = os.urandom(2000)
    _foto(tmp_path / "playa.jpg", a)
    _foto(tmp_path / "IMG_1.jpg", a)                 # mismo contenido, otro nombre
    _foto(tmp_path / "sub" / "playa (1).jpg", a)     # en una subcarpeta
    _foto(tmp_path / "otra.jpg", os.urandom(2000))   # distinta
    out = _correr(tmp_path, capsys)
    assert out.count("REPETIDO:") == 2
    assert "otra.jpg" not in out
    assert "Puedes liberar 0.0 MB" in out             # 4.000 bytes = 0,004 MB


def test_suma_el_espacio_de_las_copias(tmp_path, capsys):
    b = os.urandom(1_572_864)               # 1,5 MB (en MB de 1.048.576 bytes, como Windows)
    _foto(tmp_path / "video.mp4", b)
    _foto(tmp_path / "video - copia.mp4", b)
    _foto(tmp_path / "video (2).mp4", b)
    out = _correr(tmp_path, capsys)
    assert "Puedes liberar 3.0 MB" in out


def test_carpeta_sin_repetidos(tmp_path, capsys):
    _foto(tmp_path / "a.txt", b"uno")
    _foto(tmp_path / "b.txt", b"dos")
    out = _correr(tmp_path, capsys)
    assert "REPETIDO" not in out and "Puedes liberar 0.0 MB" in out


def test_no_borra_ni_cambia_nada(tmp_path, capsys):
    c = os.urandom(5000)
    for n in ("x.bin", "y.bin", "z/x.bin"):
        _foto(tmp_path / n, c)
    antes = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    _correr(tmp_path, capsys)
    despues = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert antes == despues
