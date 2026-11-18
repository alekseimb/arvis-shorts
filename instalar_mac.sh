#!/bin/bash
# ARVIS · Instalación del estudio audiovisual en el MacBook Pro M1 Max (64 GB) · v1.0 (18/11/2026)
#
#   bash instalar_mac.sh --comprobar      solo comprueba (no cambia nada)
#   bash instalar_mac.sh                  instala lo que falte (pregunta antes de cada descarga grande)
#   bash instalar_mac.sh --activar        además carga los servicios de launchd (solo tras la prueba de la fase 7)
#
# No usa sudo ni pide la contraseña del Mac. No borra nada: si un archivo existe y es distinto, guarda copia .bak.
# Modelos: solo Z-Image-Turbo bf16 + Qwen3-4B + autoencoder FLUX (Apache-2.0, ~19,3 GiB). Sin modelos de vídeo.
set -euo pipefail

ARVIS="$HOME/ARVIS"
CODIGO="$(cd "$(dirname "$0")" && pwd)"
MODO="instalar"; SI=0; ACTIVAR=0
for a in "$@"; do
  case "$a" in --comprobar) MODO="comprobar";; --si) SI=1;; --activar) ACTIVAR=1;; esac
done
export PATH="/opt/homebrew/bin:$PATH"
ok()  { printf "  ✓ %s\n" "$1"; }
mal() { printf "  ✗ %s\n" "$1"; }
paso(){ printf "\n== %s ==\n" "$1"; }
preguntar() { [ "$SI" = 1 ] && return 0; read -r -p "  $1 [s/N] " r; [[ "$r" =~ ^[sS]$ ]]; }

paso "1. Equipo"
[ "$(sysctl -n hw.optional.arm64 2>/dev/null || echo 0)" = 1 ] && ok "Apple Silicon" || { mal "no es Apple Silicon: ComfyUI con Metal no es viable"; exit 1; }
MAC_MAJOR=$(sw_vers -productVersion | cut -d. -f1)
[ "$MAC_MAJOR" -ge 14 ] && ok "macOS $(sw_vers -productVersion)" || mal "macOS $(sw_vers -productVersion): hace falta 14 o posterior (bf16 en MPS)"
MEM=$(( $(sysctl -n hw.memsize) / 1073741824 ))
[ "$MEM" -ge 32 ] && ok "memoria $MEM GB" || mal "memoria $MEM GB (recomendado ≥ 32)"
LIBRE=$(df -g "$HOME" | awk 'NR==2{print $4}')
[ "$LIBRE" -ge 60 ] && ok "disco libre $LIBRE GB" || mal "disco libre $LIBRE GB (hacen falta ≥ 60 GB)"

paso "2. Herramientas"
xcode-select -p >/dev/null 2>&1 && ok "herramientas de Xcode" || { mal "faltan las herramientas de Xcode: ejecuta  xcode-select --install  y vuelve a lanzar este script"; [ "$MODO" = comprobar ] || exit 1; }
command -v brew >/dev/null && ok "Homebrew" || { mal "falta Homebrew (https://brew.sh). Su instalador pide tu contraseña: hazlo tú y vuelve a lanzar este script"; [ "$MODO" = comprobar ] || exit 1; }
for f in python@3.12 ffmpeg git; do
  if brew list --versions "$f" >/dev/null 2>&1; then ok "$f"; elif [ "$MODO" = instalar ]; then brew install "$f"; else mal "falta $f"; fi
done
PY312="$(brew --prefix python@3.12 2>/dev/null)/bin/python3.12"
[ "$MODO" = comprobar ] && { echo; echo "(modo comprobar: no se ha cambiado nada)"; exit 0; }

mkdir -p "$ARVIS"/{estudio/logs,estudio_codigo}
paso "3. Código del estudio → $ARVIS/estudio_codigo"
for d in arvis_estudio launchd; do mkdir -p "$ARVIS/estudio_codigo/$d"; done
for f in "$CODIGO"/arvis_estudio/*.py; do
  dst="$ARVIS/estudio_codigo/arvis_estudio/$(basename "$f")"
  if [ -f "$dst" ] && ! cmp -s "$f" "$dst"; then cp "$dst" "$dst.bak.$(date +%Y%m%d%H%M)"; fi
  cp "$f" "$dst"
done
ok "arvis_estudio copiado"

paso "4. ComfyUI (versión estable)"
if [ ! -d "$ARVIS/ComfyUI/.git" ]; then git clone -q https://github.com/comfyanonymous/ComfyUI "$ARVIS/ComfyUI"; fi
git -C "$ARVIS/ComfyUI" fetch -q --tags
ETQ=$(git -C "$ARVIS/ComfyUI" describe --tags "$(git -C "$ARVIS/ComfyUI" rev-list --tags --max-count=1)")
git -C "$ARVIS/ComfyUI" checkout -q "$ETQ"
ok "ComfyUI $ETQ"
if [ ! -x "$ARVIS/venv-comfy/bin/python" ]; then "$PY312" -m venv "$ARVIS/venv-comfy"; fi
"$ARVIS/venv-comfy/bin/pip" install -q --upgrade pip
"$ARVIS/venv-comfy/bin/pip" install -q torch torchvision torchaudio
"$ARVIS/venv-comfy/bin/pip" install -q -r "$ARVIS/ComfyUI/requirements.txt"
"$ARVIS/venv-comfy/bin/pip" install -q opencv-python-headless "transformers>=4.45" pillow numpy
"$ARVIS/venv-comfy/bin/python" -c "import torch; assert torch.backends.mps.is_available(), 'MPS no disponible'; print('  ✓ PyTorch', torch.__version__, 'con MPS (Metal)')"

paso "5. Modelo de imagen (Z-Image-Turbo, Apache-2.0)"
M="$ARVIS/ComfyUI/models"
descargar() {  # $1 carpeta  $2 archivo
  local dir="$1" fn="$2" dst="$M/$1/$2"
  local api="https://huggingface.co/api/models/Comfy-Org/z_image_turbo/tree/main/split_files/$dir"
  local info; info=$(curl -fsSL "$api")
  local size sha
  size=$(printf '%s' "$info" | "$ARVIS/venv-comfy/bin/python" -c "import sys,json;print(next(x for x in json.load(sys.stdin) if x['path'].endswith('/$fn'))['lfs']['size'])")
  sha=$(printf '%s' "$info" | "$ARVIS/venv-comfy/bin/python" -c "import sys,json;print(next(x for x in json.load(sys.stdin) if x['path'].endswith('/$fn'))['lfs']['oid'])")
  mkdir -p "$M/$dir"
  if [ -f "$dst" ] && [ "$(stat -f%z "$dst")" = "$size" ]; then ok "$fn ya está ($((size/1048576)) MB)"; return; fi
  local libre; libre=$(df -k "$M" | awk 'NR==2{print $4*1024}')
  if [ "$libre" -lt $((size + 30*1073741824)) ]; then mal "no hay espacio para $fn ($((size/1073741824)) GB + 30 GB de margen)"; exit 1; fi
  preguntar "¿Descargar $fn ($((size/1048576)) MB, licencia Apache-2.0, origen Comfy-Org/z_image_turbo)?" || { mal "$fn no descargado"; return; }
  curl -fL -C - --retry 5 -o "$dst.part" "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/$dir/$fn"
  local got; got=$(shasum -a 256 "$dst.part" | cut -d' ' -f1)
  if [ "$got" != "$sha" ]; then mal "$fn: la huella no coincide (descarga dañada); se deja como .part"; exit 1; fi
  mv "$dst.part" "$dst"; ok "$fn verificado (sha256 $sha)"
}
descargar diffusion_models z_image_turbo_bf16.safetensors
descargar text_encoders qwen_3_4b.safetensors
descargar vae ae.safetensors

paso "6. Motor v4 + parche v4.2"
if [ -f "$ARVIS/motor/arvis_expedientes/render.py" ]; then
  ok "motor v4 presente"
  for f in "$CODIGO"/arvis_expedientes/*.py; do
    dst="$ARVIS/motor/arvis_expedientes/$(basename "$f")"
    if [ -f "$dst" ] && ! cmp -s "$f" "$dst"; then cp "$dst" "$dst.bak.$(date +%Y%m%d%H%M)"; fi
    cp "$f" "$dst"
  done
  ok "parche v4.2 aplicado (formato, render_largo, qc_largo, miniatura)"
  if [ ! -x "$ARVIS/venv-motor/bin/python" ]; then
    "$PY312" -m venv "$ARVIS/venv-motor"
    if ! "$ARVIS/venv-motor/bin/pip" install -q -r "$ARVIS/motor/requirements.txt"; then
      mal "bpy no se instala con Python 3.12; se prueba con 3.11"
      rm -rf "$ARVIS/venv-motor"; brew install python@3.11
      "$(brew --prefix python@3.11)/bin/python3.11" -m venv "$ARVIS/venv-motor"
      "$ARVIS/venv-motor/bin/pip" install -q -r "$ARVIS/motor/requirements.txt"
    fi
  fi
  ok "entorno del motor listo"
else
  mal "falta el motor v4 en $ARVIS/motor (ARVIS lo copia desde el almacén del Command Center cuando el Mac esté conectado)"
fi

paso "7. Servicios de launchd"
mkdir -p "$HOME/Library/LaunchAgents"
for p in "$CODIGO"/launchd/*.plist; do
  dst="$HOME/Library/LaunchAgents/$(basename "$p")"
  sed "s#__HOME__#$HOME#g" "$p" > "$dst"
  plutil -lint "$dst" >/dev/null && ok "$(basename "$p") preparado"
  if [ "$ACTIVAR" = 1 ]; then
    launchctl bootout "gui/$(id -u)/$(basename "$p" .plist)" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$dst" && ok "$(basename "$p" .plist) activo"
  fi
done
[ "$ACTIVAR" = 1 ] || echo "  (servicios preparados pero NO activos: se activan con --activar tras la prueba de la fase 7)"

paso "8. Para producir de noche"
echo "  Ajustes del Sistema › Batería › Opciones › «Evitar el reposo automático con el adaptador de corriente"
echo "  cuando la pantalla esté apagada» = activado. Deja el Mac enchufado y con la tapa abierta (o con monitor externo)."
echo
echo "Hecho. Comprueba con:  PYTHONPATH=$ARVIS/estudio_codigo $ARVIS/venv-comfy/bin/python -m arvis_estudio.servicio comprobar"
