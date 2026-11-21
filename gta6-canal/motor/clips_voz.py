# -*- coding: utf-8 -*-
"""Shorts con el gameplay del usuario de fondo + voz en off (x1,25) con datos de GTA 6.

Uso:
    python3 clips_voz.py RUTA_VIDEO.mp4 [V1 V2 V3]
"""
import os, subprocess, sys, wave
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import render as R
import render_short as S
from render import fuente, PALETAS, CANAL, SR
from clips_usuario import bloque, marco

W, H, FPS = 1080, 1920, 30
VEL = 1.25
SALIDA = os.path.join(R.RAIZ, "salida-clips")

SHORTS = [
    {"id": "V1", "slug": "curiosidades-mapa", "tema": "05", "paleta": "sunset",
     "rangos": [(24.5, 46.5), (53.0, 58.5)],
     "gancho": ("GTA 6", "CURIOSIDADES DEL MAPA"),
     "titulo": "GTA 6: curiosidades del MAPA de Leonida que quizá no sabías #Shorts",
     "tags": ["gta 6 mapa", "leonida", "vice city", "gta 6 curiosidades", "gta 6 regiones", "gta 6 shorts", "gta 6 datos"],
     "say": ["Esto es Vice City, y solo es una parte del mapa de GTA 6.",
             "El juego pasa en Leonida, la versión de Florida de Rockstar, y tiene seis regiones.",
             "Vice City es la única gran ciudad, y está inspirada en Miami.",
             "Al sur están los cayos, Leonida Keys, donde empieza la historia.",
             "Y además hay pantanos, pueblos costeros y hasta un parque nacional con montañas.",
             "Rockstar no ha dado el tamaño oficial, pero se calcula entre una vez y media y el doble que GTA cinco.",
             "¿Qué zona has explorado ya? Te leo en comentarios."]},
    {"id": "V2", "slug": "guardar-coches", "tema": "15", "paleta": "violet",
     "rangos": [(0.0, 24.5)],
     "gancho": ("GTA 6", "NO PIERDAS TUS COCHES"),
     "titulo": "GTA 6: cómo GUARDAR tus coches para que no desaparezcan #Shorts",
     "tags": ["gta 6 coches", "gta 6 guardar coches", "gta 6 garaje", "gta 6 pay n spray", "gta 6 supercoches", "gta 6 shorts", "gta 6 trucos"],
     "say": ["¿Te has encontrado un supercoche como este? Que no se te escape.",
             "En GTA 6, si aparcas un coche en una plaza o en un garaje, solo se guarda de forma temporal.",
             "Para que sea tuyo para siempre, tienes que registrarlo en un Pay 'N' Spray.",
             "Cuanto peor es el coche, más barato sale registrarlo.",
             "Y una vez registrado, puedes pedirlo desde el móvil estés donde estés.",
             "Hay casi una docena de garajes, pero no se desbloquean hasta salir de Key Lento.",
             "Sígueme para más trucos de GTA 6."]},
    {"id": "V3", "slug": "no-pierdas-dinero", "tema": "16", "paleta": "gold",
     "rangos": [(44.0, 58.0), (64.5, 75.3)],
     "gancho": ("GTA 6", "TODO IBA BIEN…"), "chip": "NO PIERDAS TU DINERO",
     "titulo": "GTA 6: los accidentes salen CAROS (no pierdas tu dinero) #Shorts",
     "tags": ["gta 6 dinero", "gta 6 fails", "gta 6 choque", "gta 6 consejos", "gta 6 guardar partida", "gta 6 shorts", "gta 6 banco"],
     "say": ["Todo iba bien… hasta que no.",
             "Ojo, porque en GTA 6 los accidentes salen caros.",
             "Si mueres o te detienen, pierdes todo el efectivo que llevas encima.",
             "Al principio, guárdalo en el escondite bajo el suelo del dormitorio de Jason.",
             "Tras una o dos horas consigues cuenta en la app del banco. Pero cuidado: lo que metas en ahorros no se puede sacar.",
             "Y el juego solo guarda al terminar una misión, así que guarda a mano antes de hacer locuras.",
             "¿Tú conduces mejor? Te leo."]},
]


def leer_wav(ruta):
    with wave.open(ruta) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        return a.reshape(-1, w.getnchannels()).mean(axis=1)


def render(src, s):
    pal = PALETAS[s["paleta"]]
    carpeta = os.path.join(SALIDA, f"{s['id']}-{s['slug']}"); os.makedirs(carpeta, exist_ok=True)
    cache = os.path.join(R.RAIZ, ".cache", f"clip-{s['id']}"); os.makedirs(cache, exist_ok=True)

    # voz y línea de tiempo
    t = 0.35; frases = []; pistas = []
    for j, linea in enumerate(s["say"]):
        f = os.path.join(cache, f"l{j:02d}.npy"); meta = f + ".txt"
        if os.path.exists(f) and open(meta).read() == linea:
            a = np.load(f)
        else:
            a = R.sintetizar(linea, VEL); np.save(f, a); open(meta, "w").write(linea)
        frases.append(dict(texto=linea, t0=t, t1=t + len(a) / SR)); pistas.append((t, a))
        t += len(a) / SR + 0.22
    dur_voz = t + 0.5
    dur_clip = sum(b - a for a, b in s["rangos"])
    dur = min(dur_clip, dur_voz + 2.0)
    if dur_voz > dur_clip:
        print(f"  AVISO {s['id']}: la voz ({dur_voz:.1f}s) supera al vídeo ({dur_clip:.1f}s)")

    # audio: juego bajo + voz
    juego = []
    for (a, b) in s["rangos"]:
        tmp = os.path.join(cache, f"juego_{a}.wav")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(a), "-t", str(b - a), "-i", src,
                        "-ac", "1", "-ar", str(SR), tmp], check=True)
        juego.append(leer_wav(tmp))
    g = np.concatenate(juego)[:int(dur * SR)]
    n = len(g)
    v = np.zeros(n, np.float32)
    for (t0, a) in pistas:
        i = int(t0 * SR)
        if i < n: v[i:i + len(a[:n - i])] += a[:n - i]
    env = np.convolve(np.abs(v), np.ones(2205) / 2205, mode="same")
    duck = 1 - 0.6 * np.clip(env * 15, 0, 1)
    duck = np.convolve(duck, np.ones(4410) / 4410, mode="same")
    g = g / (np.abs(g).max() + 1e-6)
    mix = v * 0.95 + g * 0.30 * duck
    fade = np.minimum(1, np.minimum(np.arange(n) / (0.3 * SR), (n - np.arange(n)) / (0.6 * SR)))
    mix = mix * fade; mix = mix / (np.abs(mix).max() + 1e-6) * 0.89
    audio = os.path.join(cache, "mezcla.wav")
    with wave.open(audio, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())

    # vídeo
    out = os.path.join(carpeta, "short.mp4")
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-i", audio, "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                            "-shortest", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    mk = marco(pal)
    gancho = bloque(*s["gancho"], pal)
    tema = S.chip(s.get("chip", s["gancho"][1]), pal, 34)
    subs = [x for f in frases for x in R.trozos_subtitulo(f, 5)]
    vf = "crop=608:1080:656:0,scale=1080:1920:flags=lanczos,unsharp=5:5:0.6,fps=30"
    nf = int(dur * FPS); fi = 0; si = 0; portada = None
    for (a, b) in s["rangos"]:
        dec = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-ss", str(a), "-t", str(b - a), "-i", src,
                                "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        while fi < nf:
            raw = dec.stdout.read(W * H * 3)
            if len(raw) < W * H * 3: break
            tt = fi / FPS
            img = Image.frombuffer("RGB", (W, H), raw).convert("RGBA")
            img.alpha_composite(mk)
            fin_gancho = frases[0]["t1"] + 0.4
            if tt < fin_gancho:
                p = R.ease(tt / 0.22); sc = 0.82 + 0.18 * p
                bb = gancho if p >= 1 else gancho.resize((max(1, int(gancho.width * sc)), max(1, int(gancho.height * sc))))
                img.alpha_composite(bb, ((W - bb.width) // 2, int(430 + (gancho.height - bb.height) / 2)))
            else:
                img.alpha_composite(tema, ((W - tema.width) // 2, 300))
            while si < len(subs) - 1 and tt >= subs[si]["t1"]: si += 1
            sb = subs[si]
            if sb["t0"] - 0.05 <= tt < sb["t1"] + 0.2:
                act = sum(1 for x in sb["tw"] if x <= tt) - 1
                im = S.sub_cache(tuple(sb["palabras"]), act, pal["acc"])
                img.alpha_composite(im, ((W - im.width) // 2, S.SUB_Y))
            if portada is None and tt >= 1.0:
                portada = img.copy()
            enc.stdin.write(img.convert("RGB").tobytes()); fi += 1
        dec.stdout.close(); dec.wait()
    enc.stdin.close(); enc.wait()
    portada.convert("RGB").save(os.path.join(carpeta, "portada.png"), optimize=True)

    srt = []; k = 1
    for f in frases:
        for x in R.trozos_subtitulo(f, 8):
            srt += [str(k), f"{R.ts(x['t0'])} --> {R.ts(x['t1'])}", " ".join(x["palabras"]), ""]; k += 1
    open(os.path.join(carpeta, "subtitulos.srt"), "w", encoding="utf-8").write("\n".join(srt))
    md = f"""# Short {s['id']} — listo para subir

**Archivo:** `short.mp4` (1080×1920, {fi / FPS:.0f} s) · tu gameplay de fondo + voz en off a x1,25 · **Portada:** `portada.png` · **Subtítulos:** `subtitulos.srt`

## Título
{s['titulo']}

## Descripción
```
{" ".join(s['say'][:2])}

🔔 Suscríbete a {CANAL} para más datos y trucos de GTA 6.
Gameplay propio. Canal de fans no oficial, sin relación con Rockstar Games ni Take-Two.

#GTA6 #GTAVI #ViceCity #Shorts
```

## Etiquetas
```
{", ".join(s['tags'])}
```

## Al subir
- «Contenido alterado o sintético»: **Sí** (la narración es voz sintética).
"""
    open(os.path.join(carpeta, "publicacion.md"), "w", encoding="utf-8").write(md)
    print(f"OK {out} ({fi / FPS:.1f}s, voz {dur_voz:.1f}s, vídeo {dur_clip:.1f}s)", flush=True)


if __name__ == "__main__":
    src = sys.argv[1]; ids = sys.argv[2:]
    for s in SHORTS:
        if not ids or s["id"] in ids:
            render(src, s)
