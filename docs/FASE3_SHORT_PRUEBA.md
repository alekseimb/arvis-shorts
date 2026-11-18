# Fase 3a · Short de prueba producido en local (18/11/2026)

**Pieza:** SH-TEST-001 · SHORT 2 (tutorial) · «Protege tu WhatsApp en 20 segundos (verificación en dos pasos)»
**Coste:** 0 € · **Tiempo de producción:** 49 s en 4 CPU · **Motor:** Piper (voz davefx, CC0) + Pillow + FFmpeg 6.1

| Comprobación de QC | Resultado |
|---|---|
| Archivo existe y se reproduce | ✅ H.264 + AAC |
| Resolución / formato | ✅ 1080×1920, 30 fps, yuv420p, faststart |
| Duración (30–60 s) | ✅ 33,5 s |
| Audio / volumen | ✅ −17,8 dB medio (normalizado a −14 LUFS) |
| Silencios > 1,5 s | ✅ ninguno |
| Tramos negros / congelados > 4 s | ✅ ninguno |
| Subtítulos sincronizados (SRT) | ✅ último cue 33,2 s / vídeo 33,5 s |
| Gancho en < 2 s | ✅ la voz arranca a 0,02 s |
| Marcas de agua ajenas | ✅ ninguna (solo «ARVIS») |
| Revisión visual de fotogramas | ✅ tras 2 correcciones (subtítulos sobre el móvil, puntero tapando texto, casillas del PIN fuera de pantalla, titular tapado) |

Pendiente de revisión humana: la ruta exacta de menús de WhatsApp no se pudo contrastar en la web oficial (faq.whatsapp.com está bloqueada por el proxy).

## Qué es real y qué no
- **Real:** voz, escenas, montaje, subtítulos, música y miniatura generados en local y comprobados con ffprobe/ffmpeg.
- **Open-Higgsfield no ha generado nada:** no hay ningún proveedor gratuito (ver `AUDITORIA_2026-11-18.md`). La guardia de coste lo bloquea.
- **No subido a YouTube.** El escenario 8260243 descarga el MP4 de `fileUrl` (HTTP público). El único puente existente es la rama `media`; esta rutina no tiene permiso para hacer push ahí.

## Para hacer la subida en privado (cuando Aleksei lo autorice)
```bash
python3.13 -m arvis_av.cli short guiones/SH-TEST-001.json /ruta/salida
# subir el MP4 a la rama media (puente temporal) y obtener la URL raw
python3 -m arvis_av.cli payload guiones/SH-TEST-001.json <URL_RAW>   # privacyStatus=private, key=SH-TEST-001
# → ejecutar el escenario Make 8260243 con ese payload → verificar con 8260190 (videos?part=status&id=…) → vaciar media
```
Antes de subirlo: `containsSyntheticMedia` está fijo en `false` en el escenario. Para este vídeo (voz sintética + gráficos claramente no realistas) es aceptable según las normas de YouTube; si se usan imágenes realistas generadas por IA tiene que pasar a `true`.
