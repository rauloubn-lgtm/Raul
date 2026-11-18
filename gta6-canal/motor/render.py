# -*- coding: utf-8 -*-
"""Motor de vídeo: guion -> voz -> gráficos animados -> música -> montaje MP4.

Uso:
    python3 render.py               # renderiza los 10 vídeos
    python3 render.py 03 07         # solo esos
    python3 render.py --preview 01  # primeros 12 s, para revisar rápido

Necesita: ffmpeg, pillow, numpy, scipy, piper-tts y la voz es_ES-davefx-medium
(ruta en la variable VOZ_ONNX o en ../voces/). Todo el arte es procedural y
original: no se usa ningún material de Rockstar.
"""
import json, math, os, re, subprocess, sys, wave, random
from functools import lru_cache
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy.signal import resample_poly

sys.path.insert(0, os.path.dirname(__file__))
from guiones import VIDEOS, CANAL, PRONUNCIACION

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FUENTES = os.path.join(RAIZ, "fuentes")
SALIDA = os.path.join(RAIZ, "salida")
VOZ = os.environ.get("VOZ_ONNX", os.path.join(RAIZ, "voces", "es_ES-davefx-medium.onnx"))

W, H, FPS, SR = 1920, 1080, 30, 44100

# ------------------------------------------------------------------ estilo
PALETAS = {
    "sunset": dict(sky=[(18, 6, 38), (74, 14, 92), (196, 38, 110), (255, 122, 72)], sun=((255, 214, 90), (255, 64, 129)),
                   grid=(255, 64, 160), acc=(255, 92, 168), acc2=(255, 196, 80), key=0),
    "teal":   dict(sky=[(4, 10, 28), (8, 34, 70), (10, 92, 120), (40, 200, 190)], sun=((190, 255, 245), (40, 170, 220)),
                   grid=(40, 230, 220), acc=(48, 232, 214), acc2=(255, 92, 168), key=3),
    "gold":   dict(sky=[(20, 8, 20), (88, 24, 40), (214, 84, 46), (255, 190, 90)], sun=((255, 240, 160), (255, 120, 40)),
                   grid=(255, 160, 60), acc=(255, 184, 60), acc2=(48, 232, 214), key=5),
    "violet": dict(sky=[(8, 4, 26), (40, 14, 90), (110, 40, 190), (230, 90, 210)], sun=((255, 200, 255), (150, 80, 255)),
                   grid=(170, 110, 255), acc=(186, 128, 255), acc2=(255, 196, 80), key=2),
}
WHITE = (255, 255, 255)
INK = (14, 10, 24)


@lru_cache(None)
def fuente(nombre, tam):
    f = {"anton": "anton-latin-400-normal.woff", "inter": "inter-latin-500-normal.woff",
         "interb": "inter-latin-700-normal.woff", "interx": "inter-latin-900-normal.woff"}[nombre]
    return ImageFont.truetype(os.path.join(FUENTES, f), tam)


def ease(p):
    p = max(0.0, min(1.0, p))
    return 1 - (1 - p) ** 3


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def texto_ancho(f, s):
    return f.getbbox(s)[2] if s else 0


def envolver(f, s, maxw):
    lineas, cur = [], ""
    for w in s.split():
        prueba = (cur + " " + w).strip()
        if texto_ancho(f, prueba) <= maxw or not cur:
            cur = prueba
        else:
            lineas.append(cur); cur = w
    if cur:
        lineas.append(cur)
    return lineas


def sombra(img, radio=18, opac=170, off=(0, 8)):
    """Devuelve img con sombra suave debajo (lienzo ampliado)."""
    pad = radio * 3
    base = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    a = img.split()[3].point(lambda v: v * opac // 255)
    sh = Image.new("RGBA", img.size, (0, 0, 0, 255)); sh.putalpha(a)
    base.alpha_composite(sh, (pad + off[0], pad + off[1]))
    base = base.filter(ImageFilter.GaussianBlur(radio))
    base.alpha_composite(img, (pad, pad))
    return base, pad


def brillo(img, color, radio=22, fuerza=1.0):
    pad = radio * 3
    base = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    a = img.split()[3].point(lambda v: min(255, int(v * fuerza)))
    g = Image.new("RGBA", img.size, color + (255,)); g.putalpha(a)
    base.alpha_composite(g, (pad, pad))
    base = base.filter(ImageFilter.GaussianBlur(radio))
    base.alpha_composite(img, (pad, pad))
    return base, pad


def texto_img(s, f, color=WHITE, stroke=0, stroke_color=INK, interlinea=1.0, align="left"):
    lineas = s.split("\n")
    asc, desc = f.getmetrics()
    lh = int((asc + desc) * interlinea)
    ws = [texto_ancho(f, l) + stroke * 2 for l in lineas]
    img = Image.new("RGBA", (max(ws) + 4, lh * len(lineas) + stroke * 2 + 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, l in enumerate(lineas):
        x = {"left": 0, "center": (img.width - ws[i]) // 2}[align]
        d.text((x + stroke, i * lh + stroke), l, font=f, fill=color, stroke_width=stroke, stroke_fill=stroke_color)
    return img


def degradado_texto(s, f, c1, c2, stroke=0):
    m = texto_img(s, f, WHITE, stroke=stroke, stroke_color=WHITE)
    g = np.zeros((m.height, m.width, 4), np.uint8)
    t = np.linspace(0, 1, m.height)[:, None]
    for k in range(3):
        g[..., k] = (c1[k] + (c2[k] - c1[k]) * t).astype(np.uint8)
    g[..., 3] = np.array(m.split()[3])
    return Image.fromarray(g, "RGBA")


def caja(w, h, r=26, fill=(12, 8, 24, 190), borde=None, ancho=3):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), r, fill=fill, outline=borde, width=ancho if borde else 0)
    return img


# ------------------------------------------------------------------ fondo
class Fondo:
    HOR = 690

    def __init__(self, pal, semilla):
        self.p = pal
        rnd = random.Random(semilla)
        self.cielo = self._cielo()
        self.skyline = self._skyline(rnd)
        self.palmeras = self._palmeras(rnd)
        self.suelo = [self._suelo(i / 30) for i in range(30)]
        self.vineta = self._vineta()
        self.estrellas = [(rnd.randrange(W), rnd.randrange(self.HOR - 120), rnd.random() * 6.28, rnd.choice([1, 1, 2])) for _ in range(90)]

    def _cielo(self):
        c = self.p["sky"]
        y = np.linspace(0, 1, self.HOR)[:, None]
        cols = np.array(c, float)
        stops = np.linspace(0, 1, len(c))
        arr = np.zeros((H, W, 3), float)
        for k in range(3):
            arr[:self.HOR, :, k] = np.interp(y, stops, cols[:, k])
        arr[self.HOR:] = np.array(c[0]) * 0.6
        img = Image.fromarray(arr.clip(0, 255).astype(np.uint8)).convert("RGBA")
        # sol con franjas
        R = 250; cx, cy = W // 2, self.HOR - 60
        sol = np.zeros((2 * R, 2 * R, 4), np.uint8)
        yy, xx = np.mgrid[0:2 * R, 0:2 * R]
        dentro = (xx - R) ** 2 + (yy - R) ** 2 <= R * R
        t = (yy / (2 * R))[..., None]
        top, bot = np.array(self.p["sun"][0]), np.array(self.p["sun"][1])
        sol[..., :3] = (top + (bot - top) * t).astype(np.uint8)
        franjas = np.ones_like(dentro)
        for i in range(7):
            y0 = int(R * 1.05 + i * i * 4.2 + i * 14); hgt = 3 + i * 2
            franjas[y0:y0 + hgt] = False
        sol[..., 3] = (dentro & franjas) * 255
        s = Image.fromarray(sol, "RGBA")
        glow = Image.new("RGBA", (2 * R + 400, 2 * R + 400), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse((150, 150, 2 * R + 250, 2 * R + 250), fill=self.p["sun"][1] + (150,))
        glow = glow.filter(ImageFilter.GaussianBlur(90))
        img.alpha_composite(glow, (cx - R - 200, cy - R - 200))
        img.alpha_composite(s, (cx - R, cy - R))
        return img

    def _skyline(self, rnd):
        ancho = W + 900
        img = Image.new("RGBA", (ancho, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        base = tuple(int(v * 0.45) for v in self.p["sky"][1])
        x = 0
        while x < ancho:
            w = rnd.randint(50, 140); h = rnd.choice([rnd.randint(60, 200), rnd.randint(160, 330)])
            col = lerp(base, (6, 4, 14), rnd.random() * 0.5)
            d.rectangle((x, self.HOR - h, x + w, self.HOR), fill=col + (255,))
            if rnd.random() < 0.25:  # antena
                d.rectangle((x + w // 2 - 2, self.HOR - h - 40, x + w // 2 + 2, self.HOR - h), fill=col + (255,))
            for wy in range(self.HOR - h + 14, self.HOR - 10, 18):
                for wx in range(x + 8, x + w - 10, 16):
                    if rnd.random() < 0.28:
                        c = rnd.choice([self.p["acc2"], (255, 236, 190), self.p["acc"]])
                        d.rectangle((wx, wy, wx + 6, wy + 8), fill=c + (170,))
            x += w + rnd.randint(-10, 18)
        return img

    def _palmera(self, d, x, base_y, alto, rnd, col):
        # tronco curvo
        curva = rnd.uniform(-90, 90)
        pts = []
        for i in range(30):
            t = i / 29
            pts.append((x + curva * t * t, base_y - alto * t))
        for i in range(29):
            w = int(26 - 14 * i / 29)
            d.line([pts[i], pts[i + 1]], fill=col, width=w)
        tx, ty = pts[-1]
        for k in range(9):
            ang = -math.pi / 2 + (k - 4) * 0.42 + rnd.uniform(-0.1, 0.1)
            L = rnd.uniform(170, 250)
            hoja = []
            for i in range(18):
                t = i / 17
                hx = tx + math.cos(ang) * L * t
                hy = ty + math.sin(ang) * L * t + (L * 0.55) * t * t
                hoja.append((hx, hy))
            for i in range(17):
                d.line([hoja[i], hoja[i + 1]], fill=col, width=int(16 * (1 - i / 17)) + 2)
                if i % 2 == 0 and i > 2:
                    px, py = hoja[i]
                    d.line([(px, py), (px + math.cos(ang + 1.3) * 30, py + 34)], fill=col, width=4)
                    d.line([(px, py), (px + math.cos(ang - 1.3) * 30, py + 34)], fill=col, width=4)
        d.ellipse((tx - 16, ty - 10, tx + 16, ty + 18), fill=col)

    def _palmeras(self, rnd):
        ancho = W + 1400
        img = Image.new("RGBA", (ancho, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        col = (6, 3, 12, 255)
        x = 60
        while x < ancho:
            self._palmera(d, x, H + 20, rnd.randint(520, 760), rnd, col)
            x += rnd.randint(620, 980)
        return img

    def _suelo(self, fase):
        h = H - self.HOR
        img = Image.new("RGBA", (W, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        g = self.p["grid"]
        for k in range(-30, 31):
            x0 = W / 2 + k * 70; x1 = W / 2 + k * 70 * 14
            d.line([(x0, 0), (x1, h * 14)], fill=g + (150,), width=2)
        for i in range(40):
            z = (i + fase)
            y = h * (1.0 / (1 + 0.0) ) * (1 - 1 / (1 + z * 0.12))
            y = h * (z * 0.12) ** 1.6 / 6
            if 0 < y < h:
                a = int(60 + 140 * min(1, y / h * 2))
                d.line([(0, y), (W, y)], fill=g + (a,), width=2 if y > 40 else 1)
        img = Image.alpha_composite(img.filter(ImageFilter.GaussianBlur(3)), img)
        return img

    def _vineta(self):
        yy, xx = np.mgrid[0:H, 0:W]
        dx = (xx - W / 2) / (W / 2); dy = (yy - H / 2) / (H / 2)
        r = np.sqrt(dx * dx * 0.8 + dy * dy)
        a = np.clip((r - 0.55) * 200, 0, 190) + 70  # oscurece todo un poco para leer
        arr = np.zeros((H, W, 4), np.uint8); arr[..., :3] = (6, 3, 14); arr[..., 3] = np.clip(a, 0, 230)
        return Image.fromarray(arr, "RGBA")

    def frame(self, t):
        img = self.cielo.copy()
        d = ImageDraw.Draw(img)
        for (x, y, ph, s) in self.estrellas:
            b = int(120 + 120 * math.sin(t * 2 + ph))
            d.rectangle((x, y, x + s, y + s), fill=(255, 255, 255, max(0, b)))
        ox = int(t * 9) % 900
        img.alpha_composite(self.skyline.crop((ox, 0, ox + W, H)))
        img.alpha_composite(self.suelo[int(t * FPS) % 30], (0, self.HOR))
        ox2 = int(t * 26) % 1400
        img.alpha_composite(self.palmeras.crop((ox2, 0, ox2 + W, H)))
        img.alpha_composite(self.vineta)
        return img


# ------------------------------------------------------------------ voz
_voz = None


def voz():
    global _voz
    if _voz is None:
        from piper import PiperVoice
        _voz = PiperVoice.load(VOZ)
    return _voz


def pronunciar(s):
    for a, b in PRONUNCIACION:
        s = re.sub(r"(?<![\wÁÉÍÓÚáéíóúñ])" + re.escape(a) + r"(?![\wÁÉÍÓÚáéíóúñ])", b, s)
    s = s.replace("…", ",").replace("«", "").replace("»", "")
    return s


def sintetizar(texto, vel=1.0):
    from piper import SynthesisConfig
    v = voz()
    cfg = SynthesisConfig(length_scale=0.9 / vel, noise_scale=0.6, noise_w_scale=0.8)
    trozos = [c.audio_int16_array for c in v.synthesize(pronunciar(texto), syn_config=cfg)]
    a = np.concatenate(trozos).astype(np.float32) / 32768.0
    sr = v.config.sample_rate
    a = resample_poly(a, SR, sr).astype(np.float32)
    # recorta silencios de los extremos
    nz = np.where(np.abs(a) > 0.01)[0]
    if len(nz):
        a = a[max(0, nz[0] - 800): nz[-1] + 2000]
    return a


# ------------------------------------------------------------------ música original procedural
def musica(dur, key, semilla):
    rnd = np.random.default_rng(semilla)
    n = int(dur * SR)
    t = np.arange(n) / SR
    bpm = 96; beat = 60 / bpm; bar = beat * 4
    base = 220 * 2 ** ((key - 12) / 12)  # La grave transpuesto
    prog = [[0, 3, 7], [-4, 0, 3], [-9, -5, -2], [-2, 2, 5]]  # i - VI - III - VII (menor)
    out = np.zeros(n, np.float32)
    nb = int(dur / bar) + 1
    env_len = int(bar * SR)
    att = np.minimum(1, np.arange(env_len) / (0.4 * SR)); rel = np.minimum(1, (env_len - np.arange(env_len)) / (0.5 * SR))
    env = (att * rel).astype(np.float32)
    for b in range(nb):
        s0 = int(b * bar * SR)
        if s0 >= n: break
        L = min(env_len, n - s0); tt = np.arange(L) / SR
        acorde = prog[b % 4]
        pad = np.zeros(L, np.float32)
        for semi in acorde:
            f = base * 2 ** (semi / 12)
            for det in (-0.12, 0.0, 0.12):
                ff = f * 2 ** (det / 12)
                pad += (2 * ((tt * ff) % 1) - 1) * 0.05
        out[s0:s0 + L] += pad * env[:L]
        # bajo en corcheas
        fb = base / 2 * 2 ** (acorde[0] / 12)
        for k in range(8):
            q0 = s0 + int(k * beat / 2 * SR); ql = int(beat / 2 * SR * 0.9)
            if q0 + ql >= n: break
            tq = np.arange(ql) / SR
            out[q0:q0 + ql] += (np.sign(np.sin(2 * np.pi * fb * tq)) * 0.06 * np.exp(-tq * 6)).astype(np.float32)
        # arpegio brillante
        for k in range(16):
            q0 = s0 + int(k * beat / 4 * SR); ql = int(beat / 4 * SR)
            if q0 + ql >= n: break
            semi = acorde[k % 3] + 12 * (1 + (k // 3) % 2)
            fa = base * 2 ** (semi / 12)
            tq = np.arange(ql) / SR
            out[q0:q0 + ql] += (np.sin(2 * np.pi * fa * tq) * 0.035 * np.exp(-tq * 14)).astype(np.float32)
    # filtro paso bajo suave
    from scipy.signal import lfilter
    out = lfilter([0.18], [1, -0.82], out).astype(np.float32)
    # bombo y hi-hat
    for k in range(int(dur / beat) + 1):
        q0 = int(k * beat * SR); ql = int(0.25 * SR)
        if q0 + ql >= n: break
        tq = np.arange(ql) / SR
        out[q0:q0 + ql] += (np.sin(2 * np.pi * (50 + 90 * np.exp(-tq * 30)) * tq) * np.exp(-tq * 12) * 0.32).astype(np.float32)
        h0 = q0 + int(beat / 2 * SR); hl = int(0.05 * SR)
        if h0 + hl < n:
            out[h0:h0 + hl] += (rnd.standard_normal(hl) * np.exp(-np.arange(hl) / SR * 80) * 0.03).astype(np.float32)
    fade = np.minimum(1, np.minimum(t / 2.0, (dur - t) / 3.0)).astype(np.float32)
    return out * fade


def whoosh(semilla):
    rnd = np.random.default_rng(semilla)
    L = int(0.55 * SR); tt = np.arange(L) / SR
    ruido = rnd.standard_normal(L).astype(np.float32)
    from scipy.signal import lfilter
    a = np.zeros(L, np.float32); prev = 0.0
    coef = 0.75 + 0.22 * np.sin(np.pi * tt / tt[-1])
    for i in range(L):  # filtro con barrido
        prev = prev * coef[i] + ruido[i] * (1 - coef[i]); a[i] = prev
    env = np.sin(np.pi * tt / tt[-1]) ** 2
    return (a * env * 1.6).astype(np.float32)


# ------------------------------------------------------------------ línea de tiempo
def construir_linea(video, cache_dir, vel=1.0, fin_extra=6.0, pad_ini=0.75):
    os.makedirs(cache_dir, exist_ok=True)
    escenas = []
    t = 0.0
    voz_total = []
    for i, e in enumerate(video["escenas"]):
        ini = t
        t += pad_ini if i == 0 else 0.45 / vel
        frases = []
        for j, s in enumerate(e["say"]):
            f = os.path.join(cache_dir, f"s{i:02d}_{j:02d}.npy")
            meta = os.path.join(cache_dir, f"s{i:02d}_{j:02d}.txt")
            if os.path.exists(f) and open(meta).read() == s:
                a = np.load(f)
            else:
                a = sintetizar(s, vel); np.save(f, a); open(meta, "w").write(s)
            frases.append(dict(texto=s, t0=t, t1=t + len(a) / SR))
            voz_total.append((t, a))
            t += len(a) / SR + 0.32 / vel
        t += 0.35 / vel
        if e["type"] == "outro":
            t += fin_extra  # margen para pantalla final de YouTube
        escenas.append(dict(e, t0=ini, t1=t, frases=frases))
    dur = t + 0.3
    return escenas, voz_total, dur


def mezclar_audio(escenas, voz_total, dur, pal, semilla, ruta):
    n = int(dur * SR) + SR
    v = np.zeros(n, np.float32)
    for (t0, a) in voz_total:
        i = int(t0 * SR)
        if i >= n: continue
        seg = a[:n - i]; v[i:i + len(seg)] += seg
    m = musica(dur + 1, pal["key"], semilla)[:n]
    m = np.pad(m, (0, n - len(m)))
    # ducking: baja la música cuando habla la voz
    envv = np.convolve(np.abs(v), np.ones(4410) / 4410, mode="same")
    duck = 1 - 0.55 * np.clip(envv * 12, 0, 1)
    duck = np.convolve(duck, np.ones(8820) / 8820, mode="same")
    mix = v * 0.95 + m * 0.42 * duck
    for i, e in enumerate(escenas):
        if i == 0: continue
        w = whoosh(semilla + i); s0 = int(max(0, e["t0"] - 0.15) * SR)
        mix[s0:s0 + len(w)] += w[:max(0, n - s0)] * 0.10
    mix = mix[:int(dur * SR)]
    mix = mix / max(1e-6, np.abs(mix).max()) * 0.89
    pcm = (mix * 32767).astype(np.int16)
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())


# ------------------------------------------------------------------ capas de escena
class Elem:
    def __init__(self, img, x, y, t_in, dy=36, dur=0.5, pulso=False):
        self.img, self.x, self.y, self.t_in, self.dy, self.dur, self.pulso = img, x, y, t_in, dy, dur, pulso
        self.alpha = np.array(img.split()[3], np.float32)

    def dibujar(self, lienzo, t):
        if t < self.t_in: return
        p = (t - self.t_in) / self.dur
        if p >= 1:
            lienzo.alpha_composite(self.img, (int(self.x), int(self.y)))
            return
        e = ease(p)
        im = self.img.copy()
        im.putalpha(Image.fromarray((self.alpha * e).astype(np.uint8)))
        lienzo.alpha_composite(im, (int(self.x), int(self.y + self.dy * (1 - e))))


def chip(texto, pal, tam=34):
    f = fuente("interx", tam)
    tw = texto_ancho(f, texto)
    img = caja(tw + 56, tam + 34, r=(tam + 34) // 2, fill=pal["acc"] + (255,))
    ImageDraw.Draw(img).text((28, 13), texto, font=f, fill=INK)
    return img


def cabecera(texto, pal):
    f = fuente("anton", 92)
    t = texto_img(texto, f, WHITE)
    img = Image.new("RGBA", (t.width + 10, t.height + 26), (0, 0, 0, 0))
    img.alpha_composite(t, (0, 0))
    ImageDraw.Draw(img).rectangle((2, t.height + 8, 170, t.height + 18), fill=pal["acc"] + (255,))
    return img


def fila(texto, pal, ancho, num=None, activa=False, derecha=None, tam=46):
    alto = 108
    borde = pal["acc"] + (255,) if activa else (255, 255, 255, 40)
    fill = (20, 12, 40, 225) if activa else (12, 8, 24, 175)
    img = caja(ancho, alto, r=22, fill=fill, borde=borde, ancho=4 if activa else 2)
    d = ImageDraw.Draw(img)
    x = 34
    if num is not None:
        d.ellipse((26, 22, 90, 86), fill=(pal["acc"] if activa else (70, 60, 100)) + (255,))
        fn = fuente("interx", 34); s = str(num)
        d.text((58 - texto_ancho(fn, s) / 2, 32), s, font=fn, fill=INK if activa else WHITE)
        x = 116
    f = fuente("interb", tam)
    col = WHITE if activa else (220, 214, 235)
    maxw = ancho - x - 40 - (texto_ancho(fuente("interx", tam), derecha) + 60 if derecha else 0)
    while texto_ancho(f, texto) > maxw and tam > 30:
        tam -= 2; f = fuente("interb", tam)
    d.text((x, (alto - tam * 1.2) / 2), texto, font=f, fill=col)
    if derecha:
        fd = fuente("interx", tam)
        d.text((ancho - 40 - texto_ancho(fd, derecha), (alto - tam * 1.2) / 2), derecha, font=fd,
               fill=(pal["acc"] if activa else pal["acc2"]))
    return img


REGIONES = [  # nombre, polígono (esquema libre, no oficial), color tono, descripción
    ("VICE CITY", [(1010, 640), (1110, 600), (1160, 700), (1120, 820), (1030, 800)], "La gran ciudad · Miami"),
    ("LEONIDA KEYS", [(860, 900), (940, 880), (1060, 905), (1120, 935), (980, 950), (880, 940)], "Cayos, islas y puentes"),
    ("GRASSRIVERS", [(860, 640), (1010, 640), (1030, 800), (920, 860), (850, 760)], "Pantanos · Everglades"),
    ("PORT GELLHORN", [(520, 300), (700, 280), (720, 380), (560, 420), (500, 370)], "Costa venida a menos"),
    ("AMBROSIA", [(700, 280), (900, 280), (930, 470), (800, 520), (720, 380)], "Industria y campo"),
    ("MOUNT KALAGA", [(900, 280), (1060, 300), (1080, 450), (930, 470)], "Bosque y montaña"),
]
CONTORNO = [(500, 300), (700, 270), (1060, 290), (1090, 450), (1120, 560), (1170, 700), (1120, 830), (1050, 900), (930, 870), (850, 760), (830, 600), (800, 520), (560, 420), (500, 370)]


def capa_mapa(pal, hl):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    sx = lambda pts: [((x - 500) * 1.2 + 170, (y - 270) * 1.0 + 265) for x, y in pts]
    d.rounded_rectangle((120, 235, 1040, 965), 30, fill=(10, 6, 20, 200), outline=(255, 255, 255, 50), width=2)
    d.polygon(sx(CONTORNO), fill=(30, 20, 60, 120), outline=(255, 255, 255, 90))
    for i, (nom, pts, _) in enumerate(REGIONES):
        c = pal["acc"] if i == hl else (110, 96, 150)
        d.polygon(sx(pts), fill=c + (235 if i == hl else 120,), outline=(255, 255, 255, 200 if i == hl else 70))
    for i, (nom, pts, _) in enumerate(REGIONES):
        P = sx(pts); cx = sum(p[0] for p in P) / len(P); cy = sum(p[1] for p in P) / len(P)
        f = fuente("interx", 26 if i != hl else 32)
        tw = texto_ancho(f, nom)
        d.text((cx - tw / 2, cy - 12), nom, font=f, fill=INK if i == hl else (235, 230, 250), stroke_width=0)
    return img


def construir_escena(e, pal, idx_video):
    """Devuelve (elementos, dinamico) para la escena."""
    els = []
    t0 = e["t0"]; fr = e["frases"]
    tipo = e["type"]
    tframe = lambda k: fr[k]["t0"] - 0.1 if k < len(fr) else e["t1"]
    din = None
    if tipo == "title":
        c = chip(e["kicker"], pal)
        els.append(Elem(c, (W - c.width) / 2, 230, t0 + 0.15))
        tt = degradado_texto(e["title"].upper(), fuente("anton", 168), WHITE, pal["acc2"])
        tt = texto_centrado_multilinea(e["title"].upper(), fuente("anton", 168), pal)
        g, pad = brillo(tt, pal["acc"], 28, 0.8)
        els.append(Elem(g, (W - g.width) / 2, 330 - pad, t0 + 0.35, dy=60, dur=0.7))
        s = texto_img(e["sub"], fuente("interb", 46), (235, 228, 255))
        sh, pad = sombra(s, 10)
        els.append(Elem(sh, (W - sh.width) / 2, 330 + tt.height + 30 - pad, t0 + 0.9))
    elif tipo == "stat":
        cab = chip("DATO CLAVE", pal)
        els.append(Elem(cab, (W - cab.width) / 2, 220, t0 + 0.1))
        f = fuente("interb", 50); tw = texto_ancho(f, e["label"])
        lab = caja(tw + 80, 96, r=48, fill=(12, 8, 24, 215), borde=pal["acc"] + (255,), ancho=3)
        ImageDraw.Draw(lab).text((40, 18), e["label"], font=f, fill=WHITE)
        els.append(Elem(lab, (W - lab.width) / 2, 770, t0 + 0.8))
        m = re.match(r"^(\d+)(.*)$", e["big"])
        big_final = e["big"]

        def din(lienzo, t, e=e, m=m):
            if t < t0 + 0.3: return
            p = ease((t - t0 - 0.3) / 1.1)
            s = big_final
            if m and int(m.group(1)) > 9 and p < 1:
                s = str(int(int(m.group(1)) * p)) + m.group(2)
            im = stat_img(s, pal)
            a = int(255 * min(1, (t - t0 - 0.3) / 0.3))
            if a < 255:
                im2 = im.copy(); im2.putalpha(im.split()[3].point(lambda v: v * a // 255)); im = im2
            lienzo.alpha_composite(im, (int((W - stat_img(big_final, pal).width) / 2), 215))
    elif tipo in ("bullets", "compare", "clock"):
        cab = cabecera(e["head"], pal)
        els.append(Elem(cab, 150, 120, t0 + 0.1, dy=0))
        items = e.get("items") or e.get("rows")
        off = len(fr) - len(items)
        y = 290 if tipo == "bullets" else (345 if tipo == "compare" else 300)
        if tipo == "compare":
            for k, col in enumerate(e["cols"]):
                c = chip(col, pal if k == 1 else dict(pal, acc=(200, 190, 230)), 30)
                els.append(Elem(c, 150 + 40 + (0 if k == 0 else 820), 270, t0 + 0.2))
        filas = []
        for k, it in enumerate(items):
            if tipo == "bullets":
                a = fila(it, pal, W - 300, num=k + 1, activa=True); b = fila(it, pal, W - 300, num=k + 1, activa=False)
            elif tipo == "compare":
                txt = f"{it[0]}"
                a = fila_compare(it, pal, True); b = fila_compare(it, pal, False)
            else:
                a = fila(it[0], pal, W - 300, activa=True, derecha=it[1]); b = fila(it[0], pal, W - 300, activa=False, derecha=it[1])
            ti = tframe(off + k) if off + k >= 0 else t0 + 0.3
            ti = max(ti, t0 + 0.25)
            tf = tframe(off + k + 1) if k < len(items) - 1 else e["t1"]
            filas.append((a, b, 150, y, ti, tf))
            y += 116
        estado = {}

        def din(lienzo, t, filas=filas):
            for (a, b, x, yy, ti, tf) in filas:
                if t < ti: continue
                im = a if t < tf else b
                p = (t - ti) / 0.45
                if p < 1:
                    ee = ease(p); im2 = im.copy()
                    im2.putalpha(im.split()[3].point(lambda v, ee=ee: int(v * ee)))
                    lienzo.alpha_composite(im2, (int(x - 60 * (1 - ee)), int(yy)))
                else:
                    lienzo.alpha_composite(im, (x, yy))
    elif tipo == "warn":
        bw, bh = 1320, 460
        bx, by = (W - bw) // 2, 300
        box = caja(bw, bh, r=30, fill=(14, 8, 26, 225), borde=pal["acc2"] + (255,), ancho=5)
        d = ImageDraw.Draw(box)
        # icono de aviso
        d.polygon([(110, 70), (190, 210), (30, 210)], fill=pal["acc2"] + (255,))
        d.text((99, 98), "!", font=fuente("interx", 84), fill=INK)
        d.text((250, 60), e["head"], font=fuente("anton", 84), fill=WHITE)
        yy = 200
        for linea in e["text"].split("\n"):
            for l in envolver(fuente("interb", 44), linea, bw - 300):
                d.text((250, yy), l, font=fuente("interb", 44), fill=(230, 224, 248)); yy += 60
        sh, pad = sombra(box, 24)
        els.append(Elem(sh, bx - pad, by - pad, t0 + 0.15, dy=50, dur=0.6))

        def din(lienzo, t):  # franja de peligro animada
            if t < t0 + 0.4: return
            stripe = Image.new("RGBA", (bw, 26), (0, 0, 0, 0)); ds = ImageDraw.Draw(stripe)
            o = int((t * 80) % 60)
            for x in range(-60, bw + 60, 60):
                ds.polygon([(x + o, 26), (x + o + 30, 0), (x + o + 60, 0), (x + o + 30, 26)], fill=pal["acc2"] + (255,))
            lienzo.alpha_composite(stripe, (bx, by + bh + 20))
            lienzo.alpha_composite(stripe, (bx, by - 46))
    elif tipo == "map":
        cab = cabecera(e["head"], pal)
        els.append(Elem(cab, 150, 110, t0 + 0.1, dy=0))
        mp = capa_mapa(pal, e["highlight"])
        els.append(Elem(mp, 0, 0, t0 + 0.05, dy=0, dur=0.3))
        nom, _, desc = REGIONES[e["highlight"]]
        card = caja(620, 250, r=26, fill=(14, 8, 26, 220), borde=pal["acc"] + (255,), ancho=4)
        d = ImageDraw.Draw(card)
        d.text((40, 30), f"REGIÓN {e['highlight'] + 1}/6", font=fuente("interx", 28), fill=pal["acc"])
        d.text((40, 76), nom, font=fuente("anton", 72), fill=WHITE)
        d.text((40, 180), desc, font=fuente("interb", 34), fill=(225, 218, 245))
        els.append(Elem(card, 1120, 440, t0 + 0.35))
        nota = texto_img("Esquema orientativo, no es el mapa oficial", fuente("inter", 26), (200, 190, 220))
        els.append(Elem(nota, 1120, 710, t0 + 0.6))
    elif tipo == "outro":
        lg = texto_img(CANAL, fuente("anton", 120), WHITE)
        g, pad = brillo(lg, pal["acc"], 26, 0.9)
        els.append(Elem(g, 150 - pad, 230 - pad, t0 + 0.1))
        sub = texto_img("Nos vemos en Leonida", fuente("interb", 50), (235, 228, 255))
        els.append(Elem(sub, 156, 400, t0 + 0.4))
        # huecos para pantalla final de YouTube (vídeos sugeridos)
        for k in range(2):
            ph = caja(560, 315, r=18, fill=(255, 255, 255, 18), borde=(255, 255, 255, 70), ancho=2)
            els.append(Elem(ph, 1210, 200 + k * 350, t0 + 0.6 + k * 0.15))

        def din(lienzo, t):
            if t < t0 + 0.6: return
            s = 1 + 0.04 * math.sin((t - t0) * 5)
            b = boton_sub(pal)
            bw, bh = int(b.width * s), int(b.height * s)
            b = b.resize((bw, bh), Image.LANCZOS)
            a = ease((t - t0 - 0.6) / 0.5)
            if a < 1:
                b.putalpha(b.split()[3].point(lambda v: int(v * a)))
            lienzo.alpha_composite(b, (int(156 + (560 - bw) / 2), int(560 + (150 - bh) / 2)))
    return els, din


@lru_cache(None)
def _boton(acc):
    b = caja(560, 150, r=75, fill=(230, 30, 50, 255))
    d = ImageDraw.Draw(b)
    d.text((150, 38), "SUSCRÍBETE", font=fuente("interx", 56), fill=WHITE)
    # campana
    d.ellipse((60, 40, 120, 104), fill=WHITE); d.rectangle((56, 86, 124, 100), fill=WHITE)
    d.ellipse((80, 100, 100, 118), fill=WHITE)
    return b


def boton_sub(pal):
    return _boton(pal["acc"])


_stat_cache = {}


def stat_img(s, pal):
    k = (s, pal["acc"])
    if k not in _stat_cache:
        im = degradado_texto(s, fuente("anton", 300), WHITE, pal["acc"])
        g, pad = brillo(im, pal["acc"], 30, 0.7)
        _stat_cache[k] = g
    return _stat_cache[k]


def texto_centrado_multilinea(s, f, pal):
    lineas = s.split("\n")
    imgs = [degradado_texto(l, f, WHITE, pal["acc2"] if i else (255, 236, 250)) for i, l in enumerate(lineas)]
    asc, desc = f.getmetrics(); lh = int((asc + desc) * 0.98)
    wmax = max(i.width for i in imgs)
    out = Image.new("RGBA", (wmax, lh * len(imgs) + 20), (0, 0, 0, 0))
    for i, im in enumerate(imgs):
        out.alpha_composite(im, ((wmax - im.width) // 2, i * lh))
    return out


def fila_compare(it, pal, activa):
    ancho = W - 300; alto = 108
    img = caja(ancho, alto, r=22, fill=(20, 12, 40, 225) if activa else (12, 8, 24, 175),
               borde=pal["acc"] + (255,) if activa else (255, 255, 255, 40), ancho=4 if activa else 2)
    d = ImageDraw.Draw(img)
    f = fuente("interb", 42)
    d.text((40, 30), it[0], font=f, fill=(190, 182, 210))
    d.polygon([(770, 38), (800, 54), (770, 70)], fill=pal["acc"]); d.rectangle((740, 50, 772, 58), fill=pal["acc"])
    fr = fuente("interx", 42)
    tam = 42
    while texto_ancho(fr, it[1]) > ancho - 900 and tam > 28:
        tam -= 2; fr = fuente("interx", tam)
    d.text((860, 30), it[1], font=fr, fill=WHITE if activa else (230, 224, 248))
    return img


# ------------------------------------------------------------------ subtítulos
def trozos_subtitulo(frase, max_pal=9):
    pal = frase["texto"].split()
    grupos = []; cur = []
    for w in pal:
        cur.append(w)
        if len(cur) >= max_pal or (w[-1] in ".,:;?!" and len(cur) >= 4):
            grupos.append(cur); cur = []
    if cur:
        if grupos and len(cur) <= 2: grupos[-1] += cur
        else: grupos.append(cur)
    total = sum(len(w) + 1 for w in pal)
    t = frase["t0"]; dur = frase["t1"] - frase["t0"]
    out = []
    for g in grupos:
        n = sum(len(w) + 1 for w in g)
        d = dur * n / total
        tiempos = []; tt = t
        for w in g:
            tiempos.append(tt); tt += d * (len(w) + 1) / n
        out.append(dict(palabras=g, t0=t, t1=t + d, tw=tiempos))
        t += d
    return out


@lru_cache(maxsize=64)
def sub_img(palabras, activa, acc):
    f = fuente("interx", 50)
    esp = texto_ancho(f, " ")
    ws = [texto_ancho(f, w) for w in palabras]
    tw = sum(ws) + esp * (len(ws) - 1)
    img = caja(tw + 64, 84, r=18, fill=(8, 5, 16, 200))
    d = ImageDraw.Draw(img)
    x = 32
    for i, w in enumerate(palabras):
        col = acc if i == activa else (WHITE if i < activa else (205, 200, 220))
        d.text((x, 14), w, font=f, fill=col, stroke_width=2, stroke_fill=INK)
        x += ws[i] + esp
    return img


# ------------------------------------------------------------------ marco fijo
def capa_marco(pal, video):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = fuente("anton", 40)
    d.rounded_rectangle((48, 40, 60 + texto_ancho(f, CANAL) + 40, 104), 14, fill=(10, 6, 20, 200))
    d.rectangle((48, 40, 58, 104), fill=pal["acc"])
    d.text((76, 44), CANAL, font=f, fill=WHITE)
    tag = "GTA VI · 19.11"
    ft = fuente("interx", 28)
    tw = texto_ancho(ft, tag)
    d.rounded_rectangle((W - 80 - tw, 48, W - 48, 98), 25, outline=pal["acc2"], width=3, fill=(10, 6, 20, 160))
    d.text((W - 64 - tw, 57), tag, font=ft, fill=pal["acc2"])
    return img


def wipe(lienzo, t, t0, pal):
    p = (t - t0 + 0.2) / 0.5
    if not (0 <= p <= 1): return
    d = ImageDraw.Draw(lienzo)
    x = -600 + (W + 1200) * ease(p)
    for k, c in enumerate([pal["acc"], pal["acc2"]]):
        xo = x - k * 140
        d.polygon([(xo, 0), (xo + 260, 0), (xo + 60, H), (xo - 200, H)], fill=c + (255,))


# ------------------------------------------------------------------ render
def render_video(video, preview=False):
    pal = PALETAS[video["paleta"]]
    sem = int(video["id"]) * 7919
    carpeta = os.path.join(SALIDA, f"{video['id']}-{video['slug']}")
    os.makedirs(carpeta, exist_ok=True)
    cache = os.path.join(RAIZ, ".cache", video["id"])
    escenas, voz_total, dur = construir_linea(video, cache)
    if preview: dur = min(dur, 12)
    audio = os.path.join(cache, "mezcla.wav")
    mezclar_audio(escenas, voz_total, dur, pal, sem, audio)

    fondo = Fondo(pal, sem)
    marco = capa_marco(pal, video)
    construidas = [construir_escena(e, pal, video["id"]) for e in escenas]
    subs = [s for e in escenas for f in e["frases"] for s in trozos_subtitulo(f)]

    out = os.path.join(carpeta, "video.mp4" if not preview else "preview.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", audio, "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p", "-tune", "animation",
           "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-shortest", "-movflags", "+faststart", out]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    nf = int(dur * FPS)
    si = 0
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
        if s and s["t0"] - 0.05 <= t < s["t1"] + 0.25:
            act = sum(1 for x in s["tw"] if x <= t) - 1
            sb = sub_img(tuple(s["palabras"]), act, pal["acc"])
            img.alpha_composite(sb, ((W - sb.width) // 2, H - 128))
        for e in escenas[1:]:
            wipe(img, t, e["t0"], pal)
        # barra de progreso
        ImageDraw.Draw(img).rectangle((0, H - 6, int(W * t / dur), H), fill=pal["acc"])
        ff.stdin.write(img.convert("RGB").tobytes())
        if fi % 300 == 0:
            print(f"  [{video['id']}] {fi}/{nf} frames", flush=True)
    ff.stdin.close(); ff.wait()
    if not preview:
        escribir_srt(escenas, os.path.join(carpeta, "subtitulos.srt"))
        escribir_meta(video, escenas, dur, os.path.join(carpeta, "publicacion.md"))
        miniatura(video, os.path.join(carpeta, "miniatura.png"))
        json.dump(dict(id=video["id"], duracion=round(dur, 2)), open(os.path.join(carpeta, "info.json"), "w"))
    return out, dur


def ts(t, srt=True):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    if srt:
        return f"{h:02d}:{m:02d}:{int(s):02d},{int((s % 1) * 1000):03d}"
    return f"{m}:{int(s):02d}"


def escribir_srt(escenas, ruta):
    n = 1; lines = []
    for e in escenas:
        for f in e["frases"]:
            for s in trozos_subtitulo(f, 12):
                lines += [str(n), f"{ts(s['t0'])} --> {ts(s['t1'])}", " ".join(s["palabras"]), ""]; n += 1
    open(ruta, "w", encoding="utf-8").write("\n".join(lines))


def escribir_meta(video, escenas, dur, ruta):
    caps = []
    for i, e in enumerate(escenas):
        nombre = {"title": "Intro", "outro": "Despedida"}.get(e["type"]) or e.get("head") or e.get("label") or e.get("big")
        if e["type"] == "map": nombre = "Mapa: " + e["head"].title()
        if e["type"] == "stat": nombre = e["label"]
        nombre = nombre.capitalize() if nombre.isupper() else nombre
        caps.append(f"{ts(0 if i == 0 else e['t0'], False)} {nombre}")
    hashtags = "#GTA6 #GTAVI #Leonida"
    desc = f"""{video['titulo']}

{resumen(video)}

⏱️ CAPÍTULOS
""" + "\n".join(caps) + f"""

🔔 Suscríbete a {CANAL}: guías, noticias y secretos de GTA 6 desde el día 1.

Datos verificados el 17/11/2026 con fuentes públicas. Lo no confirmado por Rockstar se indica como rumor o estimación.
Canal de fans no oficial, sin relación con Rockstar Games ni Take-Two. Grand Theft Auto es marca de Take-Two Interactive.
Música y gráficos originales del canal.

{hashtags}"""
    md = f"""# Vídeo {video['id']} — listo para subir

**Archivo:** `video.mp4` ({int(dur // 60)}:{int(dur % 60):02d}) · **Miniatura:** `miniatura.png` · **Subtítulos:** `subtitulos.srt` (español)

## Título
{video['titulo']}

## Descripción
```
{desc}
```

## Etiquetas
```
{", ".join(video['tags'])}
```

## Ajustes en YouTube Studio
- Idioma del vídeo: Español · Categoría: Videojuegos · Juego: Grand Theft Auto VI
- Subir `subtitulos.srt` en Subtítulos → Español
- Pantalla final: los últimos ~6 s tienen dos huecos a la derecha para vídeos sugeridos y el botón de suscripción a la izquierda
- «Contenido alterado o sintético»: **Sí** (la narración es voz sintética)
"""
    open(ruta, "w", encoding="utf-8").write(md)


def resumen(video):
    primera = video["escenas"][0]["say"]
    return " ".join(primera)


def miniatura(video, ruta):
    pal = PALETAS[video["paleta"]]
    f = Fondo(pal, int(video["id"]) * 7919)
    img = f.frame(3.0)
    # oscurece la izquierda para el texto
    grad = np.zeros((H, W, 4), np.uint8); grad[..., :3] = (8, 4, 16)
    grad[..., 3] = np.clip(np.linspace(235, 40, W), 0, 255).astype(np.uint8)[None, :]
    img.alpha_composite(Image.fromarray(grad, "RGBA"))
    l1, l2 = video["mini"]
    fa = fuente("anton", 230)
    t1 = texto_img(l1, fa, WHITE, stroke=10, stroke_color=INK)
    while max(texto_ancho(fa, l1), texto_ancho(fa, l2)) > W - 240:
        fa = fuente("anton", fa.size - 10)
    t1 = texto_img(l1, fa, WHITE, stroke=10, stroke_color=INK)
    t2 = degradado_texto(l2, fa, pal["acc2"], pal["acc"], stroke=0)
    t2s = texto_img(l2, fa, INK, stroke=10, stroke_color=INK)
    c = chip(video["mini_tag"], pal, 60)
    img.alpha_composite(c, (90, 120))
    g1, p1 = sombra(t1, 20, 220)
    img.alpha_composite(g1, (90 - p1, 250 - p1))
    y2 = 250 + t1.height - 20
    img.alpha_composite(t2s, (90, y2)); img.alpha_composite(t2, (100, y2 + 10))
    fb = fuente("anton", 90); bw = texto_ancho(fb, "GTA VI") + 70
    badge = caja(bw, 150, r=24, fill=pal["acc"] + (255,))
    ImageDraw.Draw(badge).text((35, 8), "GTA VI", font=fb, fill=INK)
    b, pb = sombra(badge, 16)
    img.alpha_composite(b, (W - bw - 90 - pb, 90 - pb))
    img.convert("RGB").resize((1280, 720), Image.LANCZOS).save(ruta, optimize=True)


if __name__ == "__main__":
    args = sys.argv[1:]
    preview = "--preview" in args
    ids = [a for a in args if not a.startswith("--")]
    for v in VIDEOS:
        if ids and v["id"] not in ids: continue
        print(f"Renderizando {v['id']} – {v['titulo']}", flush=True)
        out, dur = render_video(v, preview)
        print(f"  OK {out} ({dur:.1f}s)", flush=True)
