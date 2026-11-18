#!/usr/bin/env bash
# Puente de archivos para Make (copia de Proyecto ARVIS › motor_v4/tools/publish_media.sh).
#   tools/publish_media.sh out/SH-001.mp4 [out/SH-002.mp4 …]  → sube los MP4 a la rama "media" y escribe sus URLs raw
#   tools/publish_media.sh --clear                             → deja la rama "media" vacía (después de cada subida a YouTube)
set -euo pipefail
SLUG="${ARVIS_REPO:-alekseimb/arvis-shorts}"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE="$(git -C "$REPO_DIR" remote get-url origin)"
TMP="$(mktemp -d)"
git -C "$TMP" init -q -b media
git -C "$TMP" remote add origin "$REMOTE"
G=(git -C "$TMP" -c user.name="ARVIS" -c user.email="arvis@users.noreply.github.com")
if [ "${1:-}" = "--clear" ]; then
  "${G[@]}" commit -q --allow-empty -m "media: vaciada"
  "${G[@]}" push -q -f origin media
  echo "Rama media vaciada"
  exit 0
fi
for f in "$@"; do cp "$f" "$TMP/"; done
"${G[@]}" add -A
"${G[@]}" commit -q -m "media: $(date -u +%FT%TZ)"
"${G[@]}" push -q -f origin media
for f in "$@"; do echo "https://raw.githubusercontent.com/$SLUG/media/$(basename "$f")"; done
