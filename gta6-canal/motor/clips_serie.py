# -*- coding: utf-8 -*-
"""Serie de Shorts con el gameplay del usuario en orden continuo (parte 1/5, 2/5…).

Cada Short usa un tramo seguido del vídeo; el siguiente empieza donde acabó
el anterior. Voz en off (x1,25) con noticias, curiosidades y trucos de GTA 6.

Uso:
    python3 clips_serie.py PARTE1.mp4 PARTE2.mp4 [S1 S2 …]
"""
import json, os, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(__file__))
import render as R
import render_short as S
from render import fuente, texto_ancho, envolver, caja, PALETAS, CANAL, SR, WHITE, INK
from clips_usuario import bloque, marco

W, H, FPS = 1080, 1920, 30
VEL = 1.25
SALIDA = os.path.join(R.RAIZ, "salida-serie")
TOTAL = 5

# tramos: (vídeo, inicio, fin) — 0 = parte1, 1 = parte2
SERIE = [
    {"id": "S1", "slug": "atracos-cayo-lento", "paleta": "sunset", "tramos": [(0, 0.0, 25.5)],
     "gancho": ("PARTE 1", "PUEDES ATRACAR CASI TODO"), "chip": "ATRACOS EN GTA 6",
     "avisos": [(2, "AVISO DEL JUEGO", "24/7 (Cayo Lento) ha cerrado sus puertas debido a un atraco o altercado cercano.")],
     "titulo": "En GTA 6 puedes atracar casi CUALQUIER tienda… pero ojo (Parte 1) #Shorts",
     "tags": ["gta 6 atracos", "gta 6 robar tienda", "gta 6 cayo lento", "gta 6 gameplay", "gta 6 curiosidades", "gta 6 shorts"],
     "say": ["En GTA 6 casi cualquier tienda se puede atracar. Pero ojo con este detalle.",
             "Estamos en Cayo Lento, en los cayos del sur de Leonida, donde empieza la historia de Jason.",
             "Fíjate en el aviso: el juego te dice que una tienda ha cerrado sus puertas por un atraco cercano.",
             "O sea, cada atraco deja huella en el mundo.",
             "Y antes de entrar, piensa la huida: en cuanto empiezas un atraco, la policía no tarda en llegar.",
             "En la parte dos, entramos. Sígueme para no perdértela."]},
    {"id": "S2", "slug": "3790-millones", "paleta": "gold", "tramos": [(0, 25.5, 51.0)],
     "gancho": ("PARTE 2", "3.790 MILLONES EN UN DÍA"), "chip": "NOTICIA: RÉCORD DE VENTAS",
     "avisos": [],
     "titulo": "GTA 6 hizo 3.790 MILLONES en un día: récord histórico (Parte 2) #Shorts",
     "tags": ["gta 6 ventas", "gta 6 record", "gta 6 noticias", "gta 6 take two", "gta 6 millones", "gta 6 shorts"],
     "say": ["Mientras Jason se lleva cien dólares de esta caja, GTA 6 ha hecho tres mil setecientos noventa millones en un día.",
             "Lo ha anunciado Take-Two: es el mayor estreno de la historia del entretenimiento. Más que cualquier película.",
             "Antes de salir ya había vendido treinta y dos millones y medio de copias.",
             "GTA cinco hizo unos ochocientos millones en su primer día. Casi cinco veces menos.",
             "Y todo eso sin modo online, que todavía ni siquiera tiene fecha.",
             "¿Tú lo compraste el primer día?"]},
    {"id": "S3", "slug": "escapar-policia", "paleta": "violet", "tramos": [(0, 51.0, 70.49), (1, 0.0, 6.0)],
     "gancho": ("PARTE 3", "LO DIFÍCIL ES ESCAPAR"), "chip": "CÓMO PERDER A LA POLICÍA",
     "avisos": [],
     "titulo": "GTA 6: atracar es fácil, lo difícil es ESCAPAR (Parte 3) #Shorts",
     "tags": ["gta 6 policia", "gta 6 perder policia", "gta 6 estrellas", "gta 6 trucos", "gta 6 atracos", "gta 6 shorts"],
     "say": ["Atracar es fácil. Lo difícil es escapar.",
             "En GTA 6 la policía no persigue un punto del mapa: busca tu descripción.",
             "Así que cambia de ropa, de gorra o de gafas, y cambia de coche donde no te vean.",
             "Guarda el arma: nadie se fía de alguien con una pistola en la mano.",
             "Si te han fichado el coche, pásate por un Pay 'N' Spray.",
             "Y aunque escapes, la zona donde te vieron sigue vigilada un rato.",
             "En la parte cuatro, Jason vuelve a por más."]},
    {"id": "S4", "slug": "donde-guardar-dinero", "paleta": "teal", "tramos": [(1, 6.0, 31.5)],
     "gancho": ("PARTE 4", "¿DÓNDE GUARDAS EL BOTÍN?"), "chip": "NO PIERDAS TU DINERO",
     "avisos": [(1, "BRIAN", "Te ha hecho un Buck de 1200 $")],
     "titulo": "GTA 6: ¿dónde guardas el dinero que robas? CUIDADO (Parte 4) #Shorts",
     "tags": ["gta 6 dinero", "gta 6 buckme", "gta 6 banco", "gta 6 consejos", "gta 6 atracos", "gta 6 shorts"],
     "say": ["¿Dónde guardas el dinero que robas en GTA 6? Cuidado.",
             "Mira la notificación: Brian le acaba de hacer un Buck de mil doscientos dólares. Es la app del banco.",
             "Si mueres o te detienen, pierdes todo el efectivo que llevas encima.",
             "La cuenta llega tras una o dos horas de juego. Antes, el dinero se esconde bajo el suelo de casa.",
             "Y ojo: lo que metas en ahorros no se puede sacar.",
             "Lleva unos cientos encima para imprevistos, y el resto, a salvo. Última parte, en el canal."]},
    {"id": "S5", "slug": "no-pierdas-el-coche", "paleta": "sunset", "tramos": [(1, 31.5, 56.9)],
     "gancho": ("PARTE 5", "NO PIERDAS ESTE COCHE"), "chip": "CÓMO GUARDAR TUS COCHES",
     "avisos": [],
     "titulo": "GTA 6: si no haces esto, PERDERÁS tu coche (Parte 5, final) #Shorts",
     "tags": ["gta 6 coches", "gta 6 guardar coches", "gta 6 pay n spray", "gta 6 garaje", "gta 6 trucos", "gta 6 shorts"],
     "say": ["Si no haces esto, vas a perder tu coche en GTA 6.",
             "Si lo aparcas en una plaza o en un garaje, solo se guarda de forma temporal.",
             "Para quedártelo, regístralo en un Pay 'N' Spray. Cuanto peor es el coche, más barato.",
             "Y una vez registrado, lo pides desde el móvil estés donde estés.",
             "Hay casi una docena de garajes, pero se desbloquean al salir de Cayo Lento.",
             "Fin de la serie. ¿Qué atracamos en la próxima? Te leo en comentarios."]},
]


def tamano(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                                   "stream=width,height", "-of", "csv=p=0", path]).decode().strip()
    w, h = map(int, out.split(","))
    return w, h


def leer_wav(ruta):
    with wave.open(ruta) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        return a.reshape(-1, w.getnchannels()).mean(axis=1)


def tarjeta_aviso(titulo, texto, pal):
    ft = fuente("interx", 30); fx = fuente("interb", 40)
    lineas = envolver(fx, texto, 760)
    alto = 40 + 44 + len(lineas) * 54 + 30
    img = caja(840, alto, r=24, fill=(14, 10, 26, 235), borde=pal["acc"] + (255,), ancho=4)
    d = ImageDraw.Draw(img)
    d.text((40, 30), titulo, font=ft, fill=pal["acc"])
    y = 30 + 50
    for l in lineas:
        d.text((40, y), l, font=fx, fill=WHITE); y += 54
    return img


def chip_parte(n, pal):
    t = f"PARTE {n}/{TOTAL}"; f = fuente("interx", 30); w = texto_ancho(f, t)
    img = caja(w + 44, 56, r=28, fill=(10, 6, 20, 200), borde=pal["acc2"] + (255,), ancho=3)
    ImageDraw.Draw(img).text((22, 10), t, font=f, fill=pal["acc2"])
    return img


def render(fuentes, s, n):
    pal = PALETAS[s["paleta"]]
    carpeta = os.path.join(SALIDA, f"{s['id']}-{s['slug']}"); os.makedirs(carpeta, exist_ok=True)
    cache = os.path.join(R.RAIZ, ".cache", f"serie-{s['id']}"); os.makedirs(cache, exist_ok=True)

    t = 0.35; frases = []; pistas = []
    for j, linea in enumerate(s["say"]):
        f = os.path.join(cache, f"l{j:02d}.npy"); meta = f + ".txt"
        if os.path.exists(f) and open(meta).read() == linea:
            a = np.load(f)
        else:
            a = R.sintetizar(linea, VEL); np.save(f, a); open(meta, "w").write(linea)
        frases.append(dict(texto=linea, t0=t, t1=t + len(a) / SR)); pistas.append((t, a))
        t += len(a) / SR + 0.22
    dur_voz = t
    dur = sum(b - a for _, a, b in s["tramos"])   # se usa el tramo entero para mantener la continuidad
    if dur_voz > dur:
        print(f"  AVISO {s['id']}: la voz ({dur_voz:.1f}s) supera el tramo ({dur:.1f}s)")

    juego = []
    for k, (i, a, b) in enumerate(s["tramos"]):
        tmp = os.path.join(cache, f"juego_{k}.wav")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(a), "-t", str(b - a), "-i", fuentes[i],
                        "-ac", "1", "-ar", str(SR), tmp], check=True)
        juego.append(leer_wav(tmp))
    g = np.concatenate(juego); n_s = int(dur * SR); g = np.pad(g, (0, max(0, n_s - len(g))))[:n_s]
    v = np.zeros(n_s, np.float32)
    for (t0, a) in pistas:
        i = int(t0 * SR)
        if i < n_s: v[i:i + len(a[:n_s - i])] += a[:n_s - i]
    env = np.convolve(np.abs(v), np.ones(2205) / 2205, mode="same")
    duck = 1 - 0.65 * np.clip(env * 15, 0, 1)
    duck = np.convolve(duck, np.ones(4410) / 4410, mode="same")
    g = g / (np.abs(g).max() + 1e-6)
    mix = v * 0.95 + g * 0.32 * duck
    mix = mix / (np.abs(mix).max() + 1e-6) * 0.89   # sin fundidos: el corte casa con la parte siguiente
    audio = os.path.join(cache, "mezcla.wav")
    with wave.open(audio, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())

    out = os.path.join(carpeta, "short.mp4")
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-i", audio, "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                            "-shortest", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    mk = marco(pal); mk.alpha_composite(chip_parte(n, pal), (W - 70 - chip_parte(n, pal).width, 154))
    gancho = bloque(*s["gancho"], pal)
    tema = S.chip(s["chip"], pal, 34)
    avisos = [(frases[k]["t0"] - 0.2, frases[k]["t1"] + 1.5, tarjeta_aviso(ti, tx, pal)) for (k, ti, tx) in s["avisos"]]
    subs = [x for f in frases for x in R.trozos_subtitulo(f, 5)]
    nf = int(round(dur * FPS)); fi = 0; si = 0; portada = None
    for (i, a, b) in s["tramos"]:
        sw, sh = tamano(fuentes[i])
        cw = int(round(sh * 9 / 16)) // 2 * 2
        vf = f"crop={cw}:{sh}:{(sw - cw) // 2}:0,scale=1080:1920:flags=lanczos,unsharp=5:5:0.7,fps=30"
        dec = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-ss", str(a), "-t", str(b - a), "-i", fuentes[i],
                                "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL)
        ult = None
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
            for (a0, b0, card) in avisos:
                if a0 <= tt < b0:
                    p = R.ease((tt - a0) / 0.3)
                    img.alpha_composite(card, (int((W - card.width) / 2 + 80 * (1 - p)), 420))
            while si < len(subs) - 1 and tt >= subs[si]["t1"]: si += 1
            sb = subs[si]
            if sb["t0"] - 0.05 <= tt < sb["t1"] + 0.2:
                act = sum(1 for x in sb["tw"] if x <= tt) - 1
                im = S.sub_cache(tuple(sb["palabras"]), act, pal["acc"])
                img.alpha_composite(im, ((W - im.width) // 2, S.SUB_Y))
            if portada is None and tt >= 1.0:
                portada = img.copy()
            enc.stdin.write(img.convert("RGB").tobytes()); fi += 1; ult = img
        dec.stdout.close(); dec.wait()
    while fi < nf and ult is not None:  # por si un tramo trae algún fotograma menos
        enc.stdin.write(ult.convert("RGB").tobytes()); fi += 1
    enc.stdin.close(); enc.wait()
    portada.convert("RGB").save(os.path.join(carpeta, "portada.png"), optimize=True)

    srt = []; k = 1
    for f in frases:
        for x in R.trozos_subtitulo(f, 8):
            srt += [str(k), f"{R.ts(x['t0'])} --> {R.ts(x['t1'])}", " ".join(x["palabras"]), ""]; k += 1
    open(os.path.join(carpeta, "subtitulos.srt"), "w", encoding="utf-8").write("\n".join(srt))
    sig = f"Parte {n + 1} en el canal 👉" if n < TOTAL else "Serie completa en el canal."
    md = f"""# Short {s['id']} · Parte {n}/{TOTAL} — listo para subir

**Archivo:** `short.mp4` (1080×1920, {fi / FPS:.1f} s) · gameplay en orden + voz en off a x1,25 · **Portada:** `portada.png` · **Subtítulos:** `subtitulos.srt`

## Título
{s['titulo']}

## Descripción
```
{s['say'][0]}

Serie: atraco en Cayo Lento — parte {n} de {TOTAL}. {sig}
🔔 Suscríbete a {CANAL} para más GTA 6 cada día.
Gameplay propio. Canal de fans no oficial, sin relación con Rockstar Games ni Take-Two.

#GTA6 #GTAVI #Shorts
```

## Etiquetas
```
{", ".join(s['tags'])}
```

## Al subir
- Publica en orden (parte 1 → 5) para que el gameplay siga la secuencia.
- «Contenido alterado o sintético»: **Sí** (voz sintética).
"""
    open(os.path.join(carpeta, "publicacion.md"), "w", encoding="utf-8").write(md)
    print(f"OK {s['id']} {out} ({fi / FPS:.2f}s, voz {dur_voz:.1f}s)", flush=True)


if __name__ == "__main__":
    fuentes = sys.argv[1:3]; ids = sys.argv[3:]
    for n, s in enumerate(SERIE, 1):
        if not ids or s["id"] in ids:
            render(fuentes, s, n)
