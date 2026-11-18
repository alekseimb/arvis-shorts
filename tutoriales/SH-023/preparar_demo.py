"""Crea la carpeta de demostración con archivos de PRUEBA (contenido aleatorio fijo, no son archivos reales de nadie).
Copias exactas: cancion - copia.mp3, factura_luz (1).pdf, movil/IMG_4471 (2).jpg y vacaciones.jpg (= IMG_4471.jpg)."""
import random
from pathlib import Path

rnd = random.Random(2026)
d = Path("Descargas_demo")
(d / "movil").mkdir(parents=True, exist_ok=True)


def bloque(n):
    return rnd.randbytes(n)


foto, cancion, factura = bloque(3_400_000), bloque(5_100_000), bloque(400_000)
archivos = {
    "IMG_4471.jpg": foto, "vacaciones.jpg": foto, "movil/IMG_4471 (2).jpg": foto,
    "cancion.mp3": cancion, "cancion - copia.mp3": cancion,
    "factura_luz.pdf": factura, "factura_luz (1).pdf": factura,
    "presentacion.pptx": bloque(6_200_000), "notas.txt": "Comprar pilas\nLlamar al taller\n".encode(),
}
for nombre, datos in archivos.items():
    (d / nombre).write_bytes(datos)
print("Carpeta de prueba lista:", len(archivos), "archivos")
