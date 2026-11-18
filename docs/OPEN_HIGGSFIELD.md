# Open-Higgsfield en ARVIS · uso local

Submódulo fijado en `integrations/open-higgsfield` (commit `7d06c70`). Se ejecuta **solo en 127.0.0.1**.

```bash
git submodule update --init
cd integrations/open-higgsfield && npm ci
cp .env.example .env.local   # NO se sube a Git
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"  # → PROVIDER_CONFIG_ENCRYPTION_KEY
NEXT_TELEMETRY_DISABLED=1 npm run dev     # http://127.0.0.1:3000
cd ../.. && python3 -m arvis_av.cli estado
```

- No añadas claves de proveedor sin autorización: aunque las añadas, `arvis_av` no enviará nada mientras el proveedor esté `habilitado: false` en `config/proveedores_open_higgsfield.json`.
- Para autorizar un proveedor gratuito: `habilitado: true`, `coste_estimado_eur: 0`, `modelos_permitidos: [...]`, `autorizado_por` (frase literal) y `fecha_autorizacion`.
- Nota de seguridad: la build avisa de una vulnerabilidad conocida en Next.js 16.4.3. Mientras escuche solo en loopback el riesgo es bajo; actualizar antes de exponerlo.
