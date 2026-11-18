# ARVIS · Departamento audiovisual de YouTube

Código y documentación del departamento de YouTube de ARVIS. **Sin vídeos** (los medios pesados nunca se guardan aquí; la rama `media` es solo un puente temporal para Make).

- `arvis_av/` — integración de Open-Higgsfield con guardia de coste 0 €, generador local FFmpeg, QC técnico y registro de producción.
- `config/` — proveedores (todos los de pago desactivados) y registro de herramientas/modelos gratuitos.
- `docs/` — auditoría, plan técnico, guía de Open-Higgsfield y registro de cambios.
- `integrations/open-higgsfield/` — submódulo fijado (MIT).
- `produccion/registro.jsonl` — registro persistente de producción (solo metadatos).

```bash
python3 -m unittest discover -s tests
python3 -m arvis_av.cli estado        # requiere Open-Higgsfield en 127.0.0.1:3000
python3 -m arvis_av.cli local salida/ # prueba del motor local
```
