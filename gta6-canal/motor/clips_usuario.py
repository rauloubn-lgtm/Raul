# -*- coding: utf-8 -*-
"""Shorts verticales a partir de una grabación de gameplay del usuario.

Uso:
    python3 clips_usuario.py RUTA_VIDEO.mp4

Recorta el 16:9 a 9:16 centrado, mantiene el audio original y añade textos
animados (gancho, comentarios y llamada final) con la marca del canal.
"""
import os, subprocess, sys, json
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(__file__))
import render as R
from render import fuente, texto_ancho, envolver, texto_img, sombra, caja, chip, ease, PALETAS, INK, WHITE, CANAL

W, H, FPS = 1080, 1920, 30
SALIDA = os.path.join(R.RAIZ, "salida-clips")

SHORTS = [
    {"id": "C1", "slug": "vice-city-atardecer", "ini": 24.5, "fin": 46.5, "paleta": "sunset",
     "titulo": "Vice City al ATARDECER en GTA 6 es otro nivel #Shorts",
     "tags": ["gta 6", "vice city", "gta 6 gameplay", "gta 6 atardecer", "gta 6 graficos", "gta 6 shorts", "gta vi"],
     "textos": [(0.0, 4.6, "GTA 6", "VICE CITY AL ATARDECER"),
                (5.0, 10.5, None, "MIRA ESTE CIELO"),
                (11.0, 16.5, None, "Y ESTO ES UN VIDEOJUEGO"),
                (17.0, 22.0, "COMENTA", "¿DÍA O NOCHE?")],
     "golpes": [1.6]},
    {"id": "C2", "slug": "supercoche-tunel", "ini": 0.0, "fin": 24.5, "paleta": "violet",
     "titulo": "Supercoche 2 de 9 en GTA 6: el túnel de Vice City #Shorts",
     "tags": ["gta 6", "gta 6 supercoches", "gta 6 coches", "gta 6 gameplay", "gta 6 tunel", "gta 6 shorts", "gta vi"],
     "textos": [(0.0, 5.5, "GTA 6", "SUPERCOCHE 2 DE 9"),
                (6.5, 12.5, None, "ENTRANDO AL TÚNEL…"),
                (13.0, 18.5, None, "ESCUCHA ESE MOTOR"),
                (19.0, 24.5, "COMENTA", "¿TU SUPERCOCHE FAVORITO?")],
     "golpes": [7.4]},
    {"id": "C3", "slug": "todo-iba-bien", "ini": 44.0, "fin": 75.3, "paleta": "gold",
     "titulo": "GTA 6: todo iba bien… hasta que 😅 #Shorts",
     "tags": ["gta 6", "gta 6 fails", "gta 6 choque", "gta 6 funny moments", "gta 6 gameplay", "gta 6 shorts", "gta vi"],
     "textos": [(0.0, 3.8, "GTA 6", "TODO IBA BIEN…"),
                (3.9, 8.0, None, "HASTA QUE…"),
                (9.0, 15.0, None, "SEGUIMOS COMO SI NADA"),
                (21.5, 26.8, None, "SEGUNDO INTENTO…"),
                (27.0, 29.2, None, "OTRA VEZ NO"),
                (29.2, 31.3, "COMENTA", "¿TÚ CONDUCES MEJOR?")],
     "golpes": [4.0, 27.1]},
]


def bloque(kicker, texto, pal):
    f = fuente("anton", 128)
    lineas = envolver(f, texto, W - 140)
    while len(lineas) > 2 or max(texto_ancho(f, l) for l in lineas) > W - 140:
        f = fuente("anton", f.size - 8); lineas = envolver(f, texto, W - 140)
    t = texto_img("\n".join(lineas), f, WHITE, stroke=9, stroke_color=INK, interlinea=0.95, align="center")
    g, p = sombra(t, 18, 230)
    partes = []
    if kicker:
        partes.append(chip(kicker, pal, 40))
    partes.append(g)
    ancho = max(x.width for x in partes); alto = sum(x.height for x in partes) + 10
    img = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0)); y = 0
    for x in partes:
        img.alpha_composite(x, ((ancho - x.width) // 2, y)); y += x.height + (10 - p if x is not g else 0)
    return img


def marco(pal):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # degradado arriba para leer el texto
    a = np.zeros((H, W, 4), np.uint8); a[..., :3] = (6, 3, 14)
    perfil = np.clip(np.concatenate([np.linspace(170, 0, 760), np.zeros(H - 760)]), 0, 255)
    a[..., 3] = perfil.astype(np.uint8)[:, None]
    img.alpha_composite(Image.fromarray(a, "RGBA"))
    d = ImageDraw.Draw(img); f = fuente("anton", 40); w = texto_ancho(f, CANAL)
    d.rounded_rectangle((70, 150, 70 + w + 50, 214), 14, fill=(10, 6, 20, 200))
    d.rectangle((70, 150, 80, 214), fill=pal["acc"]); d.text((98, 154), CANAL, font=f, fill=WHITE)
    return img


def render(src, s):
    pal = PALETAS[s["paleta"]]
    carpeta = os.path.join(SALIDA, f"{s['id']}-{s['slug']}"); os.makedirs(carpeta, exist_ok=True)
    dur = s["fin"] - s["ini"]
    vf = "crop=608:1080:656:0,scale=1080:1920:flags=lanczos,unsharp=5:5:0.6,fps=30"
    dec = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-ss", str(s["ini"]), "-t", str(dur), "-i", src,
                            "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    out = os.path.join(carpeta, "short.mp4")
    af = f"afade=t=in:d=0.3,afade=t=out:st={dur - 0.6:.2f}:d=0.6,loudnorm=I=-14:TP=-1.5:LRA=11"
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-ss", str(s["ini"]), "-t", str(dur), "-i", src,
                            "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-af", af, "-shortest",
                            "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    mk = marco(pal)
    bloques = [(t0, t1, bloque(k, tx, pal)) for (t0, t1, k, tx) in s["textos"]]
    n = 0; portada = None
    while True:
        raw = dec.stdout.read(W * H * 3)
        if len(raw) < W * H * 3: break
        t = n / FPS
        img = Image.frombuffer("RGB", (W, H), raw).convert("RGBA")
        for g in s["golpes"]:  # golpe de zoom en los momentos fuertes
            if g <= t < g + 0.35:
                z = 1 + 0.10 * (1 - (t - g) / 0.35)
                cw, ch = int(W / z), int(H / z)
                img = img.crop(((W - cw) // 2, (H - ch) // 2, (W + cw) // 2, (H + ch) // 2)).resize((W, H))
        img.alpha_composite(mk)
        for (t0, t1, b) in bloques:
            if t0 <= t < t1:
                p = ease((t - t0) / 0.22); sc = 0.82 + 0.18 * p
                bb = b if p >= 1 else b.resize((max(1, int(b.width * sc)), max(1, int(b.height * sc))))
                if p < 1:
                    bb.putalpha(bb.split()[3].point(lambda v, p=p: int(v * min(1, p * 1.3))))
                img.alpha_composite(bb, ((W - bb.width) // 2, int(430 + (b.height - bb.height) / 2)))
        if portada is None and t >= 1.0:
            portada = img.copy()
        enc.stdin.write(img.convert("RGB").tobytes()); n += 1
    enc.stdin.close(); enc.wait(); dec.wait()
    portada.convert("RGB").save(os.path.join(carpeta, "portada.png"), optimize=True)
    md = f"""# Short {s['id']} — listo para subir

**Archivo:** `short.mp4` (1080×1920, {n / FPS:.0f} s, tu gameplay con su audio original) · **Portada:** `portada.png`

## Título
{s['titulo']}

## Descripción
```
GTA 6 en Vice City, jugado por mí. 🎮
🔔 Suscríbete a {CANAL} para más GTA 6 cada día.

Canal de fans no oficial, sin relación con Rockstar Games ni Take-Two.

#GTA6 #GTAVI #ViceCity #Shorts
```

## Etiquetas
```
{", ".join(s['tags'])}
```
"""
    open(os.path.join(carpeta, "publicacion.md"), "w", encoding="utf-8").write(md)
    print(f"OK {out} ({n / FPS:.1f}s)", flush=True)


if __name__ == "__main__":
    src = sys.argv[1]
    ids = sys.argv[2:]
    for s in SHORTS:
        if not ids or s["id"] in ids:
            render(src, s)
