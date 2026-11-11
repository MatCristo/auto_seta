"""
numeros.py - Detecção do minigame "Clique nos números em ordem".

Como é o minigame: um mostrador verde grande com várias bolinhas espalhadas.
Cada bolinha tem contorno verde, fundo escuro e um número branco no meio; por
fora corre um arco cinza que é o tempo até ela sumir.

Como a detecção funciona:
  1. Separa os pixels brancos (números) e verdes (contornos) da região.
  2. Agrupa os brancos em blocos. Um bloco só vale como número se tiver um
     círculo verde em volta e fundo escuro entre ele e o círculo; isso descarta
     o texto do título, o contador "0/8" e as caixas verdes do minigame de setas.
  3. Reconhece o dígito comparando o bloco com modelos dos números 1-9
     desenhados com fontes negrito do Windows. Se existir a pasta "digitos/"
     ao lado do programa com arquivos 1.png, 2.png..., eles são usados também
     (dá pra montar com os recortes que o teste salva em "debug_digitos/").
"""

import os
from collections import deque

import numpy as np
from PIL import Image, ImageDraw, ImageFont

WHITE_MIN = 150      # número: canal mais fraco acima disso...
WHITE_SAT = 45       # ...e pouca cor
GREEN_DIFF = 12      # contorno: G maior que R e B por pelo menos isso (é um verde
                     # apagado, tipo (24, 63, 49), no print de exemplo)
GREEN_MIN = 45
DARK_MAX = 90        # fundo da bolinha: canal mais forte abaixo disso
RING_MIN = 0.55      # fração do círculo que precisa ser verde
DARK_FRAC = 0.6      # fração do interior que precisa ser escuro
MIN_SCORE = 0.45     # semelhança mínima com o modelo do dígito

TPL = 24             # tamanho dos modelos (TPL x TPL)
FONTS = ["seguisb.ttf", "segoeuib.ttf", "arialbd.ttf", "verdanab.ttf",
         "calibrib.ttf", "tahomabd.ttf", "bahnschrift.ttf"]


# --------------------------------------------------------------------------
# Modelos dos dígitos
# --------------------------------------------------------------------------
def _normalize(gray):
    """Recorta o conteúdo e encaixa num quadrado TPL x TPL mantendo a proporção."""
    ys, xs = np.nonzero(gray > 0.35)
    if len(xs) == 0:
        return None
    crop = gray[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = crop.shape
    s = (TPL - 2) / max(h, w)
    nh, nw = max(1, round(h * s)), max(1, round(w * s))
    im = Image.fromarray((crop * 255).astype(np.uint8)).resize(
        (nw, nh), Image.BILINEAR)
    out = np.zeros((TPL, TPL), np.float32)
    y0, x0 = (TPL - nh) // 2, (TPL - nw) // 2
    out[y0:y0 + nh, x0:x0 + nw] = np.asarray(im, np.float32) / 255
    out -= out.mean()
    n = np.linalg.norm(out)
    return out / n if n else None


def _font_templates():
    fonts_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    tpls = []
    for name in FONTS:
        path = os.path.join(fonts_dir, name)
        if not os.path.exists(path):
            continue
        font = ImageFont.truetype(path, 64)
        for d in range(1, 10):
            im = Image.new("L", (100, 100), 0)
            ImageDraw.Draw(im).text((18, 5), str(d), fill=255, font=font)
            t = _normalize(np.asarray(im, np.float32) / 255)
            if t is not None:
                tpls.append((d, t))
    return tpls


def _user_templates(folder):
    tpls = []
    if not os.path.isdir(folder):
        return tpls
    for fn in os.listdir(folder):
        stem = os.path.splitext(fn)[0]
        if not fn.lower().endswith(".png") or not stem[:1].isdigit():
            continue
        d = int(stem[0])
        if d == 0:
            continue
        im = Image.open(os.path.join(folder, fn)).convert("L")
        t = _normalize(np.asarray(im, np.float32) / 255)
        if t is not None:
            tpls.append((d, t))
    return tpls


_TEMPLATES = None


def load_templates(user_folder=None):
    global _TEMPLATES
    _TEMPLATES = _font_templates()
    if user_folder:
        _TEMPLATES += _user_templates(user_folder)
    return len(_TEMPLATES)


def classify(gray):
    """gray: recorte do número em 0..1. Retorna (dígito, semelhança)."""
    if _TEMPLATES is None:
        load_templates()
    v = _normalize(gray)
    if v is None:
        return None, 0.0
    best_d, best_s = None, -1.0
    for d, t in _TEMPLATES:
        s = float((v * t).sum())
        if s > best_s:
            best_d, best_s = d, s
    return best_d, best_s


# --------------------------------------------------------------------------
# Componentes conexos (sem scipy, pra manter o .exe pequeno)
# --------------------------------------------------------------------------
def _components(mask):
    h, w = mask.shape
    seen = np.zeros_like(mask, bool)
    comps = []
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        seen[y0, x0] = True
        q = deque([(y0, x0)])
        pts = []
        while q:
            y, x = q.popleft()
            pts.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
        comps.append(np.array(pts))
    return comps


def _ring_samples(cy, cx, r, n):
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return (np.round(cy + r * np.sin(a)).astype(int),
            np.round(cx + r * np.cos(a)).astype(int))


# --------------------------------------------------------------------------
# Detecção
# --------------------------------------------------------------------------
def detect(img, crops=None):
    """
    img: BGRA (mss) ou BGR, numpy. Retorna lista de bolinhas, ordenada pelo
    número: [{"digito", "x", "y", "raio", "score"}], com x/y relativos à região.
    Se `crops` for uma lista, adiciona nela (dígito, recorte em 0..1) de cada uma.
    """
    b = img[:, :, 0].astype(np.int16)
    g = img[:, :, 1].astype(np.int16)
    r = img[:, :, 2].astype(np.int16)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    H, W = mn.shape

    white = (mn >= WHITE_MIN) & ((mx - mn) <= WHITE_SAT)
    green = ((g - np.maximum(r, b)) >= GREEN_DIFF) & (g >= GREEN_MIN)
    # engrossa o verde em 1 px pra amostragem do círculo não escapar da linha
    gd = green.copy()
    gd[1:, :] |= green[:-1, :]
    gd[:-1, :] |= green[1:, :]
    gd[:, 1:] |= green[:, :-1]
    gd[:, :-1] |= green[:, 1:]
    dark = mx <= DARK_MAX

    found = []
    for pts in _components(white):
        ys, xs = pts[:, 0], pts[:, 1]
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        h, w = y1 - y0 + 1, x1 - x0 + 1
        if h < 4 or h > 80 or w > h * 1.2 or len(pts) < 6:
            continue
        cy, cx = (y0 + y1) / 2, (x0 + x1) / 2

        # procura o círculo verde em volta
        best_r, best_f = 0, 0.0
        for rad in np.arange(1.4 * h, 3.6 * h + 1, 0.5):
            sy, sx = _ring_samples(cy, cx, rad, 48)
            ok = (sy >= 0) & (sy < H) & (sx >= 0) & (sx < W)
            if ok.mean() < 0.9:
                continue
            f = gd[sy[ok], sx[ok]].mean()
            if f > best_f:
                best_r, best_f = rad, f
        if best_f < RING_MIN:
            continue

        # entre o número e o contorno o fundo é escuro
        samples = []
        for rad in np.linspace(0.9 * h, best_r * 0.8, 3):
            if rad <= 0.9 * h - 1e-6 and best_r * 0.8 < 0.9 * h:
                break
            sy, sx = _ring_samples(cy, cx, rad, 32)
            ok = (sy >= 0) & (sy < H) & (sx >= 0) & (sx < W)
            samples.append(dark[sy[ok], sx[ok]])
        if not samples or np.concatenate(samples).mean() < DARK_FRAC:
            continue

        pad = 1
        crop = mn[max(0, y0 - pad):y1 + 1 + pad, max(0, x0 - pad):x1 + 1 + pad]
        gray = np.clip((crop.astype(np.float32) - 60) / 170, 0, 1)
        digit, score = classify(gray)
        if digit is None or score < MIN_SCORE:
            continue
        if crops is not None:
            crops.append((digit, gray))
        found.append({"digito": digit, "x": int(round(cx)), "y": int(round(cy)),
                      "raio": float(best_r), "score": score})

    found.sort(key=lambda c: (c["digito"], -c["score"]))
    return found
