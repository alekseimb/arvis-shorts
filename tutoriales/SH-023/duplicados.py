import hashlib, sys
from pathlib import Path

carpeta = Path(sys.argv[1])
vistos, total = {}, 0

for f in sorted(carpeta.rglob("*")):
    if not f.is_file():
        continue
    with open(f, "rb") as d:
        h = hashlib.file_digest(d, "sha256")
    huella = h.hexdigest()
    if huella in vistos:
        total += f.stat().st_size
        print("REPETIDO:", f.name,
              "=", vistos[huella].name)
    else:
        vistos[huella] = f

print(f"Puedes liberar {total/2**20:.1f} MB")
