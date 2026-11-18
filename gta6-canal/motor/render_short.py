# -*- coding: utf-8 -*-
"""Versión SHORTS (vertical 1080x1920) de los 10 vídeos, con la voz a x1,25.

Uso:
    python3 render_short.py            # los 10
    python3 render_short.py 03 07      # solo esos
    python3 render_short.py --preview 01

Reutiliza el motor horizontal (render.py) pero rehace cada diseño para
pantalla vertical y respeta las zonas que tapa la interfaz de Shorts
(arriba ~200 px, abajo ~420 px y la columna de botones de la derecha).
"""
import json, math, os, re, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(__file__))
import render as R
from render import (fuente, ease, texto_ancho, envolver, sombra, brillo, texto_img, degradado_texto, caja,
                    Elem, chip, PALETAS, WHITE, INK, REGIONES, CONTORNO, VIDEOS, CANAL, FPS, SR)

VEL = 1.25
W, H = 1080, 1920
R.W, R.H = W, H               # el fondo procedural usa estas dimensiones
R.Fondo.HOR = 1180            # horizonte más bajo en vertical
X0, ANCHO = 70, 940           # columna útil de contenido
SUB_Y = 1350                  # subtítulos (por encima de la interfaz de Shorts)
SALIDA = os.path.join(R.RAIZ, "salida-shorts")


# ------------------------------------------------------------------ piezas
def titular(texto, pal, tam=96, maxw=ANCHO):
    f = fuente("anton", tam)
    lineas = envolver(f, texto, maxw)
    while len(lineas) > 2 and tam > 60:
        tam -= 6; f = fuente("anton", tam); lineas = envolver(f, texto, maxw)
    t = texto_img("\n".join(lineas), f, WHITE, interlinea=0.95)
    img = Image.new("RGBA", (t.width + 10, t.height + 26), (0, 0, 0, 0))
    img.alpha_composite(t, (0, 0))
    ImageDraw.Draw(img).rectangle((2, t.height + 8, 150, t.height + 18), fill=pal["acc"] + (255,))
    return img


def tarjeta(pal, activa, principal, secundaria=None, num=None, ancho=ANCHO):
    """Fila con texto que se ajusta en varias líneas. `secundaria` va encima, más pequeña."""
    x = 116 if num is not None else 36
    fp = fuente("interb", 44); fs = fuente("inter", 34)
    lp = envolver(fp, principal, ancho - x - 36)
    ls = envolver(fs, secundaria, ancho - x - 36) if secundaria else []
    alto = 34 + len(ls) * 44 + len(lp) * 56 + 26
    alto = max(alto, 110)
    img = caja(ancho, alto, r=24, fill=(20, 12, 40, 230) if activa else (12, 8, 24, 190),
               borde=pal["acc"] + (255,) if activa else (255, 255, 255, 45), ancho=4 if activa else 2)
    d = ImageDraw.Draw(img)
    if num is not None:
        cy = alto // 2
        d.ellipse((26, cy - 32, 90, cy + 32), fill=(pal["acc"] if activa else (70, 60, 100)) + (255,))
        fn = fuente("interx", 34); s = str(num)
        d.text((58 - texto_ancho(fn, s) / 2, cy - 22), s, font=fn, fill=INK if activa else WHITE)
    y = 30 if (ls or len(lp) > 1) else (alto - 56) // 2 + 2
    for l in ls:
        d.text((x, y), l, font=fs, fill=(190, 182, 210)); y += 44
    for l in lp:
        col = (pal["acc"] if (secundaria and activa) else WHITE) if activa else (225, 218, 240)
        d.text((x, y), l, font=fp, fill=col); y += 56
    return img


def fila_hora(pal, activa, izq, der, ancho=ANCHO):
    fi = fuente("interb", 40); fd = fuente("interx", 40)
    if texto_ancho(fi, izq) + texto_ancho(fd, der) + 110 > ancho:
        return tarjeta(pal, activa, der, secundaria=izq, ancho=ancho)
    img = caja(ancho, 96, r=22, fill=(20, 12, 40, 230) if activa else (12, 8, 24, 190),
               borde=pal["acc"] + (255,) if activa else (255, 255, 255, 45), ancho=4 if activa else 2)
    d = ImageDraw.Draw(img)
    d.text((34, 24), izq, font=fi, fill=WHITE if activa else (225, 218, 240))
    d.text((ancho - 34 - texto_ancho(fd, der), 24), der, font=fd, fill=pal["acc"] if activa else pal["acc2"])
    return img


def stat_img(s, pal):
    tam = 280
    while texto_ancho(fuente("anton", tam), s) > ANCHO - 40:
        tam -= 10
    im = degradado_texto(s, fuente("anton", tam), WHITE, pal["acc"])
    g, pad = brillo(im, pal["acc"], 28, 0.7)
    return g


_stat = {}


def stat_cache(s, pal):
    k = (s, pal["acc"])
    if k not in _stat: _stat[k] = stat_img(s, pal)
    return _stat[k]


def bloque_texto(texto, f, color, maxw=ANCHO, align="center"):
    lineas = []
    for parr in texto.split("\n"):
        lineas += envolver(f, parr, maxw)
    return texto_img("\n".join(lineas), f, color, align=align)


def lista_filas(filas_img, y0, fr, off, t0, t1, sep=18):
    """Coloca filas (activa, inactiva) y calcula cuándo aparece/ilumina cada una."""
    out = []; y = y0
    tframe = lambda k: fr[k]["t0"] - 0.08 if k < len(fr) else t1
    for k, (a, b) in enumerate(filas_img):
        ti = max(tframe(off + k) if off + k >= 0 else t0 + 0.3, t0 + 0.2)
        tf = tframe(off + k + 1) if k < len(filas_img) - 1 else t1
        out.append((a, b, X0, y, ti, tf)); y += a.height + sep
    return out, y


def dibujar_filas(lienzo, t, filas):
    for (a, b, x, yy, ti, tf) in filas:
        if t < ti: continue
        im = a if t < tf else b
        p = (t - ti) / 0.4
        if p < 1:
            ee = ease(p); im2 = im.copy()
            im2.putalpha(im.split()[3].point(lambda v, ee=ee: int(v * ee)))
            lienzo.alpha_composite(im2, (int(x - 60 * (1 - ee)), int(yy)))
        else:
            lienzo.alpha_composite(im, (x, yy))


def capa_mapa(pal, hl):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    sx = lambda pts: [((x - 500) * 1.18 + 145, (y - 270) * 1.0 + 600) for x, y in pts]
    d.rounded_rectangle((X0, 570, X0 + ANCHO, 1320), 30, fill=(10, 6, 20, 205), outline=(255, 255, 255, 50), width=2)
    d.polygon(sx(CONTORNO), fill=(30, 20, 60, 120), outline=(255, 255, 255, 90))
    for i, (nom, pts, _) in enumerate(REGIONES):
        c = pal["acc"] if i == hl else (110, 96, 150)
        d.polygon(sx(pts), fill=c + (235 if i == hl else 120,), outline=(255, 255, 255, 200 if i == hl else 70))
    for i, (nom, pts, _) in enumerate(REGIONES):
        P = sx(pts); cx = sum(p[0] for p in P) / len(P); cy = sum(p[1] for p in P) / len(P)
        f = fuente("interx", 24 if i != hl else 30)
        d.text((cx - texto_ancho(f, nom) / 2, cy - 12), nom, font=f, fill=INK if i == hl else (235, 230, 250))
    f = fuente("inter", 26); n = "Esquema orientativo, no es el mapa oficial"
    d.text((W / 2 - texto_ancho(f, n) / 2, 1278), n, font=f, fill=(200, 190, 220))
    return img


# ------------------------------------------------------------------ escenas
def construir_escena(e, pal):
    els = []; din = None
    t0 = e["t0"]; fr = e["frases"]; tipo = e["type"]
    if tipo == "title":
        c = chip(e["kicker"], pal, 36)
        els.append(Elem(c, (W - c.width) / 2, 330, t0 + 0.1))
        f = fuente("anton", 170)
        lineas = e["title"].upper().split("\n")
        while max(texto_ancho(f, l) for l in lineas) > ANCHO:
            f = fuente("anton", f.size - 8)
        tt = R.texto_centrado_multilinea(e["title"].upper(), f, pal)
        g, pad = brillo(tt, pal["acc"], 28, 0.8)
        els.append(Elem(g, (W - g.width) / 2, 450 - pad, t0 + 0.25, dy=60, dur=0.6))
        s = bloque_texto(e["sub"], fuente("interb", 50), (240, 234, 255))
        sh, pad = sombra(s, 10)
        els.append(Elem(sh, (W - sh.width) / 2, 450 + tt.height + 40 - pad, t0 + 0.7))
    elif tipo == "stat":
        cab = chip("DATO CLAVE", pal, 36)
        els.append(Elem(cab, (W - cab.width) / 2, 360, t0 + 0.1))
        f = fuente("interb", 48)
        lineas = envolver(f, e["label"], ANCHO - 100)
        lab = caja(max(texto_ancho(f, l) for l in lineas) + 90, 40 + 62 * len(lineas), r=40,
                   fill=(12, 8, 24, 220), borde=pal["acc"] + (255,), ancho=3)
        d = ImageDraw.Draw(lab)
        for k, l in enumerate(lineas):
            d.text(((lab.width - texto_ancho(f, l)) / 2, 18 + 62 * k), l, font=f, fill=WHITE)
        els.append(Elem(lab, (W - lab.width) / 2, 900, t0 + 0.7))
        m = re.match(r"^(\d+)(.*)$", e["big"]); final = e["big"]

        def din(lienzo, t):
            if t < t0 + 0.25: return
            p = ease((t - t0 - 0.25) / 0.9); s = final
            if m and int(m.group(1)) > 9 and p < 1:
                s = str(int(int(m.group(1)) * p)) + m.group(2)
            im = stat_cache(s, pal)
            a = int(255 * min(1, (t - t0 - 0.25) / 0.25))
            if a < 255:
                im = im.copy(); im.putalpha(im.split()[3].point(lambda v: v * a // 255))
            ref = stat_cache(final, pal)
            lienzo.alpha_composite(im, (int((W - ref.width) / 2), int(700 - ref.height / 2)))
    elif tipo in ("bullets", "compare", "clock"):
        cab = titular(e["head"], pal)
        els.append(Elem(cab, X0, 260, t0 + 0.1, dy=0))
        y0 = 260 + cab.height + 34
        items = e.get("items") or e.get("rows")
        if tipo == "compare":
            c1 = chip(e["cols"][0], dict(pal, acc=(200, 190, 230)), 30); c2 = chip(e["cols"][1], pal, 30)
            leyenda = Image.new("RGBA", (c1.width + c2.width + 90, c1.height), (0, 0, 0, 0))
            leyenda.alpha_composite(c1, (0, 0)); leyenda.alpha_composite(c2, (c1.width + 90, 0))
            dl = ImageDraw.Draw(leyenda); cx = c1.width + 30; cy = c1.height // 2
            dl.polygon([(cx + 10, cy - 14), (cx + 34, cy), (cx + 10, cy + 14)], fill=pal["acc"])
            els.append(Elem(leyenda, X0, y0, t0 + 0.15)); y0 += leyenda.height + 22
        imgs = []
        for k, it in enumerate(items):
            if tipo == "bullets":
                imgs.append((tarjeta(pal, True, it, num=k + 1), tarjeta(pal, False, it, num=k + 1)))
            elif tipo == "compare":
                imgs.append((tarjeta(pal, True, it[1], secundaria=f"{e['cols'][0]}: {it[0]}"),
                             tarjeta(pal, False, it[1], secundaria=f"{e['cols'][0]}: {it[0]}")))
            else:
                imgs.append((fila_hora(pal, True, it[0], it[1]), fila_hora(pal, False, it[0], it[1])))
        sep = 18
        total = sum(a.height for a, _ in imgs) + sep * (len(imgs) - 1)
        if y0 + total > SUB_Y - 30:  # si no cabe, compacta
            sep = 10
        filas, _ = lista_filas(imgs, y0, fr, len(fr) - len(items), t0, e["t1"], sep)
        din = lambda lienzo, t, filas=filas: dibujar_filas(lienzo, t, filas)
    elif tipo == "warn":
        fh = fuente("anton", 84); ft = fuente("interb", 46)
        lh = envolver(fh, e["head"], ANCHO - 80)
        lt = []
        for parr in e["text"].split("\n"): lt += envolver(ft, parr, ANCHO - 80)
        hh = int(sum(fh.getmetrics()) * 0.92)
        bh = 200 + len(lh) * hh + 24 + len(lt) * 62 + 40
        box = caja(ANCHO, bh, r=30, fill=(14, 8, 26, 230), borde=pal["acc2"] + (255,), ancho=5)
        d = ImageDraw.Draw(box)
        d.polygon([(120, 40), (190, 160), (50, 160)], fill=pal["acc2"] + (255,))
        d.text((108, 62), "!", font=fuente("interx", 76), fill=INK)
        y = 190
        for l in lh: d.text((40, y), l, font=fh, fill=WHITE); y += hh
        y += 24
        for l in lt: d.text((40, y), l, font=ft, fill=(232, 226, 250)); y += 62
        by = int(max(300, (SUB_Y - 60 - bh) / 2 + 150))
        sh, pad = sombra(box, 24)
        els.append(Elem(sh, X0 - pad, by - pad, t0 + 0.1, dy=50, dur=0.5))

        def din(lienzo, t):
            if t < t0 + 0.35: return
            stripe = Image.new("RGBA", (ANCHO, 26), (0, 0, 0, 0)); ds = ImageDraw.Draw(stripe)
            o = int((t * 80) % 60)
            for x in range(-60, ANCHO + 60, 60):
                ds.polygon([(x + o, 26), (x + o + 30, 0), (x + o + 60, 0), (x + o + 30, 26)], fill=pal["acc2"] + (255,))
            lienzo.alpha_composite(stripe, (X0, by - 46)); lienzo.alpha_composite(stripe, (X0, by + bh + 20))
    elif tipo == "map":
        hl = e["highlight"]; nom, _, desc = REGIONES[hl]
        c = chip(f"REGIÓN {hl + 1}/6", pal, 30)
        els.append(Elem(c, X0, 250, t0 + 0.05, dy=0))
        cab = titular(nom, pal, 100)
        els.append(Elem(cab, X0, 310, t0 + 0.1, dy=0))
        ds = texto_img(desc, fuente("interb", 44), (235, 228, 255))
        els.append(Elem(ds, X0, 310 + cab.height + 4, t0 + 0.3))
        els.append(Elem(capa_mapa(pal, hl), 0, 0, t0 + 0.05, dy=0, dur=0.3))
    elif tipo == "outro":
        lg = texto_img(CANAL, fuente("anton", 130), WHITE)
        g, pad = brillo(lg, pal["acc"], 26, 0.9)
        els.append(Elem(g, (W - g.width) / 2, 450 - pad, t0 + 0.1))
        sub = texto_img("Nos vemos en Leonida", fuente("interb", 54), (235, 228, 255))
        els.append(Elem(sub, (W - sub.width) / 2, 640, t0 + 0.35))

        def din(lienzo, t):
            if t < t0 + 0.5: return
            s = 1 + 0.05 * math.sin((t - t0) * 5)
            b = R.boton_sub(pal)
            bw, bh = int(b.width * s), int(b.height * s)
            b = b.resize((bw, bh), Image.LANCZOS)
            a = ease((t - t0 - 0.5) / 0.4)
            if a < 1: b.putalpha(b.split()[3].point(lambda v: int(v * a)))
            lienzo.alpha_composite(b, (int((W - bw) / 2), int(820 + (150 - bh) / 2)))
    return els, din


# ------------------------------------------------------------------ subtítulos y marco
def sub_img(palabras, activa, acc):
    tam = 58; f = fuente("interx", tam)
    while texto_ancho(f, " ".join(palabras)) > 860 and tam > 40:
        tam -= 4; f = fuente("interx", tam)
    esp = texto_ancho(f, " "); ws = [texto_ancho(f, w) for w in palabras]
    tw = sum(ws) + esp * (len(ws) - 1)
    img = caja(tw + 60, tam + 44, r=20, fill=(8, 5, 16, 215))
    d = ImageDraw.Draw(img); x = 30
    for i, w in enumerate(palabras):
        col = acc if i == activa else (WHITE if i < activa else (205, 200, 220))
        d.text((x, 16), w, font=f, fill=col, stroke_width=3, stroke_fill=INK); x += ws[i] + esp
    return img


_subc = {}


def sub_cache(palabras, activa, acc):
    k = (palabras, activa)
    if k not in _subc:
        if len(_subc) > 80: _subc.clear()
        _subc[k] = sub_img(palabras, activa, acc)
    return _subc[k]


def capa_marco(pal):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img); f = fuente("anton", 40)
    w = texto_ancho(f, CANAL)
    d.rounded_rectangle((X0, 150, X0 + w + 50, 214), 14, fill=(10, 6, 20, 200))
    d.rectangle((X0, 150, X0 + 10, 214), fill=pal["acc"])
    d.text((X0 + 28, 154), CANAL, font=f, fill=WHITE)
    tag = "GTA VI · 19.11"; ft = fuente("interx", 28); tw = texto_ancho(ft, tag)
    d.rounded_rectangle((W - X0 - tw - 34, 157, W - X0, 207), 25, outline=pal["acc2"], width=3, fill=(10, 6, 20, 160))
    d.text((W - X0 - tw - 17, 166), tag, font=ft, fill=pal["acc2"])
    return img


def wipe(lienzo, t, t0, pal):
    p = (t - t0 + 0.18) / 0.42
    if not (0 <= p <= 1): return
    d = ImageDraw.Draw(lienzo); x = -700 + (W + 1400) * ease(p)
    for k, c in enumerate([pal["acc"], pal["acc2"]]):
        xo = x - k * 140
        d.polygon([(xo, 0), (xo + 300, 0), (xo + 20, H), (xo - 280, H)], fill=c + (255,))


# ------------------------------------------------------------------ render
def render_short(video, preview=False):
    pal = PALETAS[video["paleta"]]
    sem = int(video["id"]) * 7919
    carpeta = os.path.join(SALIDA, f"{video['id']}-{video['slug']}")
    os.makedirs(carpeta, exist_ok=True)
    cache = os.path.join(R.RAIZ, ".cache", f"short-{video['id']}")
    escenas, voz_total, dur = R.construir_linea(video, cache, vel=VEL, fin_extra=0.6, pad_ini=0.25)
    if preview: dur = min(dur, 12)
    audio = os.path.join(cache, "mezcla.wav")
    R.mezclar_audio(escenas, voz_total, dur, pal, sem, audio)

    fondo = R.Fondo(pal, sem)
    marco = capa_marco(pal)
    construidas = [construir_escena(e, pal) for e in escenas]
    subs = [s for e in escenas for f in e["frases"] for s in R.trozos_subtitulo(f, 5)]

    out = os.path.join(carpeta, "short.mp4" if not preview else "preview.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", audio, "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p", "-tune", "animation",
           "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-shortest", "-movflags", "+faststart", out]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    nf = int(dur * FPS); si = 0
    for fi in range(nf):
        t = fi / FPS
        img = fondo.frame(t)
        for (e, (els, din)) in zip(escenas, construidas):
            if e["t0"] - 0.05 <= t < e["t1"]:
                for el in els: el.dibujar(img, t)
                if din: din(img, t)
        img.alpha_composite(marco)
        while si < len(subs) - 1 and t >= subs[si]["t1"]: si += 1
        s = subs[si] if subs else None
        if s and s["t0"] - 0.05 <= t < s["t1"] + 0.2:
            act = sum(1 for x in s["tw"] if x <= t) - 1
            sb = sub_cache(tuple(s["palabras"]), act, pal["acc"])
            img.alpha_composite(sb, ((W - sb.width) // 2, SUB_Y))
        for e in escenas[1:]:
            wipe(img, t, e["t0"], pal)
        ff.stdin.write(img.convert("RGB").tobytes())
        if fi % 300 == 0: print(f"  [short {video['id']}] {fi}/{nf}", flush=True)
    ff.stdin.close(); ff.wait()
    if not preview:
        escribir_srt(escenas, os.path.join(carpeta, "subtitulos.srt"))
        escribir_meta(video, dur, os.path.join(carpeta, "publicacion.md"))
        portada(video, fondo, construidas[0], escenas[0], marco, os.path.join(carpeta, "portada.png"))
        json.dump(dict(id=video["id"], duracion=round(dur, 2)), open(os.path.join(carpeta, "info.json"), "w"))
    return out, dur


def escribir_srt(escenas, ruta):
    n = 1; lines = []
    for e in escenas:
        for f in e["frases"]:
            for s in R.trozos_subtitulo(f, 8):
                lines += [str(n), f"{R.ts(s['t0'])} --> {R.ts(s['t1'])}", " ".join(s["palabras"]), ""]; n += 1
    open(ruta, "w", encoding="utf-8").write("\n".join(lines))


def titulo_short(video):
    t = video["titulo"]
    t = re.sub(r"\s*\(.*?\)\s*", " ", t).strip()
    if len(t) > 85: t = t.split(":")[0].strip()
    return f"{t} #Shorts"


def escribir_meta(video, dur, ruta):
    desc = f"""{" ".join(video['escenas'][0]['say'])}

🔔 Suscríbete a {CANAL}: guías, noticias y secretos de GTA 6 desde el día 1.

Datos verificados el 17/11/2026. Lo no confirmado por Rockstar se indica como rumor o estimación.
Canal de fans no oficial, sin relación con Rockstar Games ni Take-Two. Música y gráficos originales.

#GTA6 #GTAVI #Shorts"""
    md = f"""# Short {video['id']} — listo para subir

**Archivo:** `short.mp4` (1080×1920, {int(dur)} s, voz a x1,25) · **Portada:** `portada.png` · **Subtítulos:** `subtitulos.srt`

## Título
{titulo_short(video)}

## Descripción
```
{desc}
```

## Etiquetas
```
{", ".join(video['tags'] + ["gta 6 shorts"])}
```

## Al subir
- Súbelo como vídeo normal: al ser vertical y de menos de 3 minutos, YouTube lo publica como Short.
- Portada: en la app de YouTube, «Editar portada» y elige el primer fotograma (el título); `portada.png` sirve para TikTok/Reels.
- «Contenido alterado o sintético»: **Sí** (voz sintética).
"""
    open(ruta, "w", encoding="utf-8").write(md)


def portada(video, fondo, cons, esc, marco, ruta):
    t = esc["t0"] + 1.6
    img = fondo.frame(t)
    els, din = cons
    for el in els: el.dibujar(img, t)
    if din: din(img, t)
    img.alpha_composite(marco)
    img.convert("RGB").save(ruta, optimize=True)


if __name__ == "__main__":
    args = sys.argv[1:]
    preview = "--preview" in args
    ids = [a for a in args if not a.startswith("--")]
    for v in VIDEOS:
        if ids and v["id"] not in ids: continue
        print(f"Short {v['id']} – {v['titulo']}", flush=True)
        out, dur = render_short(v, preview)
        print(f"  OK {out} ({dur:.1f}s)", flush=True)
