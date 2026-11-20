# ENJOYESP — canal de GTA 6 listo para el lanzamiento

10 vídeos terminados (guion, voz, gráficos, animación, música y montaje) para el lanzamiento de GTA 6 el **jueves 19 de noviembre de 2026**. Cada carpeta de `salida/` trae todo lo necesario para subirlo:

| Archivo | Para qué |
|---|---|
| `video.mp4` | Vídeo final 1920×1080, 30 fps, audio normalizado a -14 LUFS |
| `miniatura.png` | Miniatura 1280×720 |
| `subtitulos.srt` | Subtítulos en español para YouTube |
| `publicacion.md` | Título, descripción con capítulos, etiquetas y ajustes de Studio |

## Qué va a buscar la gente (investigación, 17/11/2026)

Datos de vidIQ (búsquedas mensuales estimadas en YouTube y crecimiento del último mes):

- **Precarga y descarga**: «gta 6 preload» 373 k (+2 362 %), «gta 6 download» 282 k (+8 061 %)
- **Hora de lanzamiento / Nueva Zelanda**: «cuando sale gta 6», «como jugar gta 6 antes», «cuenta de nueva zelanda ps5 gta 6»
- **Clips / ganar dinero como creador**: «gta 6 clipping» 392 k (+1 633 %, competencia baja: 29), «como ganar dinero con gta 6» (+91 %)
- **PC**: «gta 6 pc» 380 k (+302 %), «cuando sale gta 6 para pc» (+85 %)
- **Ediciones y precio**: «gta 6 ultimate edition» 267 k (+319 %), «comprar gta 6 barato»
- **Mapa**: «gta 6 map» 668 k (+244 %)
- **Comparativa**: «gta 5 vs gta 6» 297 k (+316 %)
- **Gameplay**: «gta 6 gameplay» 5 M (+408 %)

## Calendario de subida recomendado

La búsqueda de horarios y precarga llega a su máximo **antes** del lanzamiento, así que conviene publicar esos dos el miércoles:

| Cuándo | Vídeo |
|---|---|
| Mié 18 · 10:00 | 01 · A qué hora sale (Nueva Zelanda desbloquea a las 12:00 hora de España) |
| Mié 18 · 10:00 | 02 · Precarga y tamaño |
| Mié 18 · 18:00 | 03 · Qué edición comprar (el bonus de reserva acaba el 19–20) |
| Jue 19 · 00:00 | 10 · Todo lo que sabemos (resumen para quien empieza ya) |
| Jue 19 · 00:00 | 08 · Primera hora: ajustes y consejos |
| Jue 19 · 10:00 | 05 · El mapa explicado |
| Jue 19 · 14:00 | 06 · GTA 5 vs GTA 6 |
| Jue 19 · 18:00 | 07 · Jason y Lucía |
| Jue 19 · 20:00 | 04 · GTA 6 en PC |
| Jue 19 · 22:00 | 09 · Ganar dinero con clips |

Si solo quieres publicar el jueves, súbelos todos y prográmalos con YouTube Studio en ese orden.

## Datos y avisos

- Datos comprobados el 17/11/2026 en fuentes públicas: Forbes, Newsweek, PureXbox, Windows Central, GamingBolt, GamesRadar, Tom's Guide y guías de precarga y ediciones. Lo que Rockstar no ha confirmado (PC en 2027, truco de Nueva Zelanda, tamaño del mapa, fecha límite del bonus) se presenta como rumor o estimación.
- **Todo el material visual y la música son originales**: se generan por código en `motor/render.py`. No hay ni una imagen, tráiler o logo de Rockstar. La descripción incluye el aviso de canal de fans no oficial.
- La narración es voz sintética (Piper, voz `es_ES-davefx-medium`, licencia libre). Al subir, marca **«Contenido alterado o sintético: Sí»**.
- Tipografías Anton e Inter (licencia OFL).

## Volver a generar o cambiar algo

```bash
pip install piper-tts pillow numpy scipy   # y ffmpeg
# voz: es_ES-davefx-medium.onnx + .onnx.json en gta6-canal/voces/
python3 motor/render.py            # los 10
python3 motor/render.py 03         # solo uno
python3 motor/render.py --preview 03   # 12 s de prueba
```

- Textos, frases de la voz y etiquetas: `motor/guiones.py`
- Nombre del canal: variable `CANAL` en `motor/guiones.py`
- Pronunciación de nombres en inglés: lista `PRONUNCIACION`

## Versión Shorts (vertical, voz x1,25)

En `salida-shorts/` están los mismos 10 vídeos en 1080×1920, con la narración a velocidad x1,25 y el diseño rehecho para vertical (respeta las zonas que tapa la interfaz de Shorts). Todos duran menos de 100 s. Cada carpeta trae `short.mp4`, `portada.png`, `subtitulos.srt` y `publicacion.md` (título con #Shorts).

```bash
python3 motor/render_short.py        # los 10
python3 motor/render_short.py 05     # solo uno
```

La velocidad está en `VEL` dentro de `motor/render_short.py`.

## Lote 2 — después del lanzamiento (Shorts 11–25)

Guiones en `motor/guiones_post.py`, datos comprobados el 20/11/2026: notas (Metacritic/OpenCritic), duración, comparativa de Digital Foundry, guías de lanzamiento (coches, dinero, policía, guardado), estado del online y del PC, primeros easter eggs. Lo que viene de una sola fuente o de jugadores se dice como tal.

```bash
python3 motor/render_short.py 11 12 13   # o sin números para todos
```
