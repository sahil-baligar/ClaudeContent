"""Overlay kit: type, labels, header, cards, stamps, captions, year counter, route heads, icons.
Everything is drawn with Pillow/OpenCV from code, so it scales to any frame size and every style.
"""
import math, os
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from .geo import eback, eout

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fonts')
FONT_FILES = {'Oswald': 'Oswald.ttf', 'Playfair': 'Playfair-Bold.ttf', 'Fell': 'IMFell.ttf',
              'Roboto': 'Roboto-Bold.ttf', 'Caveat': 'Caveat-Variable.ttf'}
_FC = {}


def font(name, size, weight=None):
    key = (name, int(size), weight)
    if key not in _FC:
        f = ImageFont.truetype(os.path.join(FONT_DIR, FONT_FILES[name]), max(6, int(size)))
        if weight:
            try:
                f.set_variation_by_axes([weight])
            except Exception:
                pass
        _FC[key] = f
    return _FC[key]


_CAP = {}


def cap_ratio(name, weight=None):
    """cap height of the face as a fraction of its point size"""
    k = (name, weight)
    if k not in _CAP:
        f = font(name, 200, weight)
        bb = f.getbbox('H')
        _CAP[k] = (bb[3] - bb[1]) / 200.0
    return _CAP[k]


PHONE_CAP = 0.035     # minimum cap height for captions and headers on portrait frames (fraction of frame height)
LABEL_CAP = 0.035     # same target for map labels; a label shrinks only when it would not fit across the frame


def phone_size(name, size, H, W, cap=PHONE_CAP, weight=None):
    """point size raised so the cap height is at least cap * H on portrait frames (9:16, 4:5); landscape unchanged"""
    if H <= W:
        return size
    return max(size, cap * H / cap_ratio(name, weight))


def rgba(c, a=1.0):
    return tuple(int(v) for v in c[:3]) + (int(255 * max(0, min(1, a))),)


def spaced(d, xy, text, f, fill, sp=0.0, anchor='m', stroke=0, stroke_fill=None):
    """draw text with letter spacing; anchor m/l/r on the x axis, vertically centred"""
    widths = [d.textlength(ch, font=f) for ch in text]
    total = sum(widths) + sp * max(0, len(text) - 1)
    x, y = xy
    if anchor == 'm':
        x -= total / 2
    elif anchor == 'r':
        x -= total
    for ch, w in zip(text, widths):
        d.text((x, y), ch, font=f, fill=fill, anchor='lm', stroke_width=stroke, stroke_fill=stroke_fill)
        x += w + sp
    return total


def text_w(text, f, sp=0.0):
    d = ImageDraw.Draw(Image.new('RGBA', (4, 4)))
    return sum(d.textlength(ch, font=f) for ch in text) + sp * max(0, len(text) - 1)


def wrap(text, f, max_w):
    out, cur = [], ''
    for w in text.split():
        t = (cur + ' ' + w).strip()
        if cur and text_w(t, f) > max_w:
            out.append(cur); cur = w
        else:
            cur = t
    if cur:
        out.append(cur)
    return out


def shadowed(img, blur=10, off=(0, 8), op=150):
    a = img.split()[3]
    sh = Image.new('RGBA', img.size, (0, 0, 0, 0)); sh.putalpha(a.point(lambda v: v * op // 255))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    pad = blur * 3
    out = Image.new('RGBA', (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    out.alpha_composite(sh, (pad + off[0], pad + off[1]))
    out.alpha_composite(img, (pad, pad))
    return out


def paste(ov, spr, cx, cy, scale=1.0, alpha=1.0, rot=0.0):
    if spr is None or alpha <= 0.01 or scale <= 0.01:
        return
    s = spr
    if rot:
        s = s.rotate(rot, Image.BICUBIC, expand=True)
    if abs(scale - 1) > 0.003:
        s = s.resize((max(1, int(s.width * scale)), max(1, int(s.height * scale))), Image.BILINEAR)
    if alpha < 0.999:
        s = s.copy(); s.putalpha(s.split()[3].point(lambda v: int(v * alpha)))
    x, y = int(cx - s.width / 2), int(cy - s.height / 2)
    x0, y0 = max(0, x), max(0, y); x1, y1 = min(ov.width, x + s.width), min(ov.height, y + s.height)
    if x1 > x0 and y1 > y0:
        ov.alpha_composite(s.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))


# ---------------------------------------------------------------- motion helpers
def pop(t, t0, t1=1e9, dur=0.42, out=0.3):
    """overshoot-in / fade-out -> (scale, alpha)"""
    if t < t0 or t > t1 + out:
        return 0.0, 0.0
    k = eback((t - t0) / dur); a = min(1.0, (t - t0) / (dur * 0.5))
    if t > t1:
        fo = 1 - (t - t1) / out; return k * (0.92 + 0.08 * fo), a * fo
    return k, a


def slam(t, t0, t1=1e9, out=0.3):
    """stamp: big -> settle with a little wobble"""
    if t < t0 or t > t1 + out:
        return 0.0, 0.0
    x = (t - t0) / 0.16
    s = 1.9 - 0.9 * eout(x) if x < 1 else 1 + 0.025 * math.exp(-(x - 1) * 3) * math.sin((x - 1) * 12)
    a = min(1.0, x * 1.5)
    if t > t1:
        a *= 1 - (t - t1) / out
    return s, a


def fade(t, t0, t1, fin=0.35, fout=0.35):
    if t < t0 or t > t1 + fout:
        return 0.0
    return min(1.0, (t - t0) / fin) * (1.0 if t <= t1 else 1 - (t - t1) / fout)


# ---------------------------------------------------------------- map labels and icons
def icon(d, kind, x, y, s, col, halo):
    """city / capital / battle / port / camp / x markers, drawn at (x, y) with size s"""
    if kind in ('city', 'capital', 'dot'):
        r = s * 0.42
        d.ellipse([x - r - s * 0.18, y - r - s * 0.18, x + r + s * 0.18, y + r + s * 0.18], fill=halo)
        d.ellipse([x - r, y - r, x + r, y + r], fill=col)
        if kind == 'capital':
            r2 = r * 0.45; d.ellipse([x - r2, y - r2, x + r2, y + r2], fill=halo)
    elif kind == 'battle':   # crossed swords
        for sgn in (1, -1):
            a = (x - s * 0.7 * sgn, y - s * 0.7); b = (x + s * 0.7 * sgn, y + s * 0.7)
            d.line([a, b], fill=halo, width=int(s * 0.5)); d.line([a, b], fill=col, width=int(s * 0.24))
            gx, gy = x + s * 0.4 * sgn, y + s * 0.4          # cross-guard, perpendicular to the blade
            d.line([(gx - s * 0.26, gy + s * 0.26 * sgn), (gx + s * 0.26, gy - s * 0.26 * sgn)], fill=col, width=max(2, int(s * 0.2)))
    elif kind == 'x':
        for sgn in (1, -1):
            d.line([(x - s * 0.5, y - s * 0.5 * sgn), (x + s * 0.5, y + s * 0.5 * sgn)], fill=halo, width=int(s * 0.5))
            d.line([(x - s * 0.5, y - s * 0.5 * sgn), (x + s * 0.5, y + s * 0.5 * sgn)], fill=col, width=int(s * 0.26))
    elif kind == 'port':     # anchor
        w = max(2, int(s * 0.2))
        d.ellipse([x - s * 0.2, y - s * 0.75, x + s * 0.2, y - s * 0.35], outline=col, width=w)
        d.line([(x, y - s * 0.35), (x, y + s * 0.7)], fill=col, width=w)
        d.line([(x - s * 0.35, y - s * 0.1), (x + s * 0.35, y - s * 0.1)], fill=col, width=w)
        d.arc([x - s * 0.65, y - s * 0.1, x + s * 0.65, y + s * 0.75], 20, 160, fill=col, width=w)
    elif kind == 'camp':     # tent
        d.polygon([(x - s * 0.75, y + s * 0.5), (x, y - s * 0.7), (x + s * 0.75, y + s * 0.5)], fill=col, outline=halo)
        d.polygon([(x - s * 0.15, y + s * 0.5), (x, y), (x + s * 0.15, y + s * 0.5)], fill=halo)


def place_label(ov, st, S, pos, name, kind, a, side='r', note=None, pulse=None, taken=None):
    if pos is None or a <= 0.01:
        return
    d = ImageDraw.Draw(ov)
    x, y = pos
    halo = rgba(st.paper, 0.9 * a) if st.kind == 'vector' and sum(st.paper) > 300 else rgba((10, 8, 6), 0.8 * a)
    col = rgba(st.ink if st.kind == 'vector' else (245, 240, 228), a)
    if kind == 'region':
        f = font(st.label_font, 50 * S) if st.label_font != 'Oswald' else font('Oswald', phone_size('Oswald', 46 * S, ov.height, ov.width, 0.028, 400), 400)
        spaced(d, (x, y), name.upper(), f, rgba(col, 0.75 * a), 14 * S, 'm', stroke=int(3 * S), stroke_fill=rgba(halo, 0.5 * a))
        return
    portrait = ov.height > ov.width
    sz_i = 20 * S * (1.4 if portrait else 1.0)
    if pulse is not None and kind != 'region':      # a soft ring keeps every labelled place alive during holds
        ph = pulse % 1.6 / 1.6
        r = sz_i * (0.6 + 1.6 * ph)
        d.ellipse([x - r, y - r, x + r, y + r], outline=rgba(st.accent, a * 0.7 * (1 - ph)), width=max(2, int(3 * S)))
    icon(d, kind if kind != 'region' else 'dot', x, y, sz_i, col if kind != 'battle' else rgba(st.accent, a), halo)
    wt = None if st.label_font in ('Fell', 'Playfair') else 600
    base = 40 * S if wt is None else 34 * S
    txt = name if st.label_font == 'Fell' else name.upper()
    size = phone_size(st.label_font, base, ov.height, ov.width, LABEL_CAP, wt)
    while size > base and text_w(txt, font(st.label_font, size, wt), 1.5 * S) > ov.width * 0.62:
        size *= 0.92                                   # long names shrink to fit, never below the landscape size
    f = font(st.label_font, size, wt)
    off = 26 * S * (size / base) ** 0.5
    tw = text_w(txt, f, 1.5 * S)
    if side == 'r' and x + off + tw > ov.width - 16 * S:      # flip so the label stays on screen
        side = 'l'
    elif side == 'l' and x - off - tw < 16 * S:
        side = 'r'
    def box(sd, dy):
        x0 = x + off if sd == 'r' else x - off - tw
        return (x0, y + dy - size * 0.6, x0 + tw, y + dy + size * (1.6 if note else 0.6))
    def hits(b):
        return any(not (b[2] < o[0] or b[0] > o[2] or b[3] < o[1] or b[1] > o[3]) for o in (taken or []))
    dy = 0.0
    if taken is not None and hits(box(side, 0)):       # avoid other labels: flip side, then nudge down/up
        other = 'l' if side == 'r' else 'r'
        ok_other = (x - off - tw > 16 * S) if other == 'l' else (x + off + tw < ov.width - 16 * S)
        if ok_other and not hits(box(other, 0)):
            side = other
        else:
            for cand in (size * 1.15, -size * 1.15, size * 2.2):
                if not hits(box(side, cand)):
                    dy = cand; break
    if taken is not None:
        taken.append(box(side, dy))
    tx = x + off if side == 'r' else x - off
    anc = 'l' if side == 'r' else 'r'
    sp = 1.5 * S if st.label_font != 'Fell' else 0.5 * S
    spaced(d, (tx, y - 2 * S + dy), txt, f, col, sp, anc, stroke=int(5 * S * (size / base) ** 0.5), stroke_fill=halo)
    if note:
        fn = font(st.hand_font, 34 * S * (size / base) ** 0.7, 600)
        spaced(d, (tx, y + dy + size * 1.05), note, fn, rgba(st.accent, a), 0, anc, stroke=int(4 * S), stroke_fill=halo)


# ---------------------------------------------------------------- header / year / title / captions
def header(ov, st, S, L, kicker, title, t, t0, t1):
    a = fade(t, t0, t1, 0.3, 0.3)
    if a <= 0:
        return
    d = ImageDraw.Draw(ov)
    W = ov.width; y0 = L['header_y']
    lw = int(L['header_w'] * eout((t - t0) / 0.5))
    lc = st.ink if st.kind == 'vector' and sum(st.paper) > 300 else (230, 224, 210)
    halo = rgba(st.paper, 0.85 * a) if sum(st.paper) > 300 else rgba((0, 0, 0), 0.6 * a)
    hw = None if st.title_font in ('Playfair', 'Fell') else 400
    hs = phone_size(st.title_font, 54 * S, ov.height, ov.width, PHONE_CAP, hw)
    while title and hs > 54 * S and text_w(title.upper(), font(st.title_font, hs, hw), 8 * S) > ov.width * 0.9:
        hs *= 0.93
    ex = hs - 54 * S                                   # extra height on phone-sized headers
    ks = phone_size(st.ui_font, 26 * S, ov.height, ov.width, 0.018, 500)
    for yy in (y0 - 46 * S - 0.55 * ex - (ks - 26 * S), y0 + 62 * S + 0.55 * ex):
        d.line([(W / 2 - lw / 2, yy), (W / 2 + lw / 2, yy)], fill=rgba(lc, 0.55 * a), width=max(1, int(2 * S)))
    if kicker:
        spaced(d, (W / 2, y0 - 18 * S - 0.45 * ex - 0.6 * (ks - 26 * S)), kicker.upper(), font(st.ui_font, ks, 500), rgba(st.accent, a), 7 * S,
               stroke=int(3 * S), stroke_fill=halo)
    if title:
        n = int(len(title) * min(1, max(0, (t - t0 - 0.12) / 0.6)))
        tf = font(st.title_font, hs, hw)
        spaced(d, (W / 2, y0 + 26 * S + 0.3 * ex), title.upper()[:n], tf, rgba(lc, a), 8 * S, stroke=int(4 * S), stroke_fill=halo)


def year_badge(ov, st, S, L, text, a, flip=0.0):
    if a <= 0.01 or not text:
        return
    d = ImageDraw.Draw(ov)
    x, y = L['year_xy']
    f = font(st.title_font, 92 * S) if st.title_font in ('Playfair', 'Fell') else font(st.title_font, 92 * S, 600)
    halo = rgba(st.paper, 0.9 * a) if sum(st.paper) > 300 else rgba((0, 0, 0), 0.75 * a)
    col = st.ink if sum(st.paper) > 300 else (244, 238, 224)
    yy = y - 40 * S * flip
    d.text((x, yy), str(text), font=f, fill=rgba(col, a * (1 - abs(flip))), anchor='lm', stroke_width=int(5 * S), stroke_fill=halo)
    tw = d.textlength(str(text), font=f)
    d.line([(x, y + 58 * S), (x + tw, y + 58 * S)], fill=rgba(st.accent, a), width=max(2, int(5 * S)))


def title_card(ov, st, S, L, title, subtitle, a):
    """title cartouche: paper panel with a double rule, title in the style's display face"""
    if a <= 0.01:
        return
    W, H = ov.size
    tf = font(st.title_font, 92 * S) if st.title_font in ('Playfair', 'Fell') else font(st.title_font, 96 * S, 600)
    sf = font(st.ui_font, 30 * S, 500)
    lines = wrap(title.upper(), tf, W * 0.78)
    lh = 104 * S
    tw = max(text_w(ln, tf, 4 * S) for ln in lines)
    if subtitle:
        tw = max(tw, text_w(subtitle.upper(), sf, 8 * S))
    pw = int(tw + 120 * S); ph = int(len(lines) * lh + (70 * S if subtitle else 0) + 90 * S)
    panel = _paper(pw, ph, st, seed=5)
    d = ImageDraw.Draw(panel)
    ink = st.ink if sum(st.paper) > 300 else (236, 240, 238)
    bw = max(2, int(4 * S))
    d.rectangle([bw, bw, pw - 1 - bw, ph - 1 - bw], outline=rgba(ink), width=bw)
    d.rectangle([bw * 4, bw * 4, pw - 1 - bw * 4, ph - 1 - bw * 4], outline=rgba(ink, 0.5), width=max(1, bw // 2))
    y = 45 * S + lh / 2
    for ln in lines:
        spaced(d, (pw / 2, y), ln, tf, rgba(ink), 4 * S); y += lh
    if subtitle:
        d.line([(pw / 2 - 60 * S, y - 22 * S), (pw / 2 + 60 * S, y - 22 * S)], fill=rgba(st.accent), width=max(1, int(2 * S)))
        spaced(d, (pw / 2, y + 16 * S), subtitle.upper(), sf, rgba(st.accent), 8 * S)
    spr = shadowed(panel, int(16 * S), (0, int(10 * S)), 150)
    paste(ov, spr, W / 2, L['title_y'], 0.94 + 0.06 * eout(a), a)


def captions(ov, st, S, L, words, t, max_words=3):
    """words: [(text, t_start, t_end)] for the current beat; 3-word chunks, active word in the accent colour"""
    if not words or t < words[0][1] - 0.05 or t > words[-1][2] + 0.3:
        return
    chunks = [words[i:i + max_words] for i in range(0, len(words), max_words)]
    cur = None
    for i, c in enumerate(chunks):
        st0 = c[0][1]; en = chunks[i + 1][0][1] if i + 1 < len(chunks) else c[-1][2] + 0.3
        if st0 - 0.05 <= t < en:
            cur = c; break
    if cur is None:
        return
    d = ImageDraw.Draw(ov)
    toks = [w[0].upper() for w in cur]
    sp = 18 * S
    size = phone_size('Oswald', L['cap_size'] * S, ov.height, ov.width, PHONE_CAP, 650)
    while True:                                        # phone-safe size, shrunk only if the chunk would not fit
        f = font('Oswald', size, 650)
        ws = [d.textlength(w, font=f) for w in toks]
        tot = sum(ws) + sp * (len(toks) - 1)
        if tot <= ov.width * 0.92 or size <= L['cap_size'] * S * 0.8:
            break
        size *= 0.94
    x = ov.width / 2 - tot / 2; y = L['cap_y']
    for tok, wd, (_, s0, e0) in zip(toks, ws, cur):
        on = s0 - 0.03 <= t < e0 + 0.12
        col = st.cap_hl if on else st.cap_fg
        d.text((x, y + 4 * S), tok, font=f, fill=(0, 0, 0, 120), anchor='lm', stroke_width=int(7 * S), stroke_fill=(0, 0, 0, 90))
        d.text((x, y), tok, font=f, fill=rgba(col), anchor='lm', stroke_width=int(5 * S), stroke_fill=rgba(st.cap_stroke))
        x += wd + sp


# ---------------------------------------------------------------- cards
def _paper(w, h, st, seed=1):
    base = np.zeros((h, w, 4), np.uint8)
    pc = np.array(st.paper, np.float32)
    rg = np.random.default_rng(seed)
    amp = 0.0 if min(st.paper) >= 250 else (5 if sum(st.paper) > 300 else 2.5)    # true white stays white
    tex = cv2.GaussianBlur(rg.normal(0, 1, (h, w)).astype(np.float32), (0, 0), 1.6) * amp
    base[..., :3] = np.clip(pc[None, None, :] + tex[..., None], 0, 255).astype(np.uint8)
    base[..., 3] = 255 if min(st.paper) >= 250 else (246 if sum(st.paper) > 300 else 222)   # white cards are opaque
    return Image.fromarray(base)


def card(st, S, c, t_local=1e9, W=1080):
    """build one info card sprite. c: {kind: fact|stat|quote|portrait, kicker, title, body, value, from, unit, label,
    quote, by, image, name, role}. t_local = seconds since the card entered (drives the stat counter)."""
    kind = c.get('kind', 'fact')
    w = int(c.get('width', 620) * S)
    pad = int(34 * S)
    ink = st.ink if sum(st.paper) > 300 else (236, 240, 238)
    f_k = font(st.ui_font, 24 * S, 500)
    f_t = font(st.title_font, 50 * S) if st.title_font in ('Playfair', 'Fell') else font(st.title_font, 48 * S, 600)
    f_b = font('Fell', 36 * S) if st.label_font == 'Fell' else font(st.ui_font, 32 * S, 400)
    rows = []   # (kind, payload, height)
    if c.get('kicker'):
        rows.append(('k', c['kicker'].upper(), int(36 * S)))
    if kind == 'stat':
        v1 = float(c.get('value', 0)); v0 = float(c.get('from', 0))
        k = eout(min(1.0, max(0.0, (t_local - 0.15) / 1.3)))
        v = v0 + (v1 - v0) * k
        txt = c.get('prefix', '') + (f'{int(round(v)):,}' if abs(v1) >= 100 or float(v1).is_integer() else f'{v:.1f}') + c.get('unit', '')
        f_n = font(st.title_font, 104 * S) if st.title_font in ('Playfair', 'Fell') else font(st.title_font, 104 * S, 700)
        rows.append(('n', (txt, f_n), int(118 * S)))
        if c.get('label'):
            for ln in wrap(c['label'], f_b, w - 2 * pad):
                rows.append(('b', ln, int(44 * S)))
    elif kind == 'quote':
        f_q = font('Fell', 44 * S) if st.label_font == 'Fell' else font('Playfair', 40 * S)
        for i, ln in enumerate(wrap('“' + c.get('quote', '') + '”', f_q, w - 2 * pad)):
            rows.append(('q', (ln, f_q), int(54 * S)))
        if c.get('by'):
            rows.append(('by', '— ' + c['by'], int(46 * S)))
    else:
        if kind == 'portrait':
            rows.append(('img', c, int(w * 0.62)))
        if c.get('title') or c.get('name'):
            for ln in wrap((c.get('title') or c.get('name')).upper(), f_t, w - 2 * pad):
                rows.append(('t', ln, int(58 * S)))
        if c.get('role'):
            rows.append(('k2', c['role'].upper(), int(36 * S)))
        if c.get('body'):
            for ln in wrap(c['body'], f_b, w - 2 * pad):
                rows.append(('b', ln, int(44 * S)))
    h = pad * 2 + sum(r[2] for r in rows)
    im = _paper(w, h, st, seed=len(str(c)))
    d = ImageDraw.Draw(im)
    bw = max(2, int(3 * S))
    d.rectangle([bw, bw, w - 1 - bw, h - 1 - bw], outline=rgba(ink, 0.85), width=bw)
    d.rectangle([bw * 3, bw * 3, w - 1 - bw * 3, h - 1 - bw * 3], outline=rgba(ink, 0.35), width=max(1, bw // 2))
    y = pad
    for kd, p, rh in rows:
        cy = y + rh / 2
        if kd == 'k':
            spaced(d, (pad, cy), p, f_k, rgba(st.accent), 5 * S, 'l')
        elif kd == 'k2':
            spaced(d, (pad, cy), p, f_k, rgba(st.muted), 4 * S, 'l')
        elif kd == 't':
            spaced(d, (pad, cy), p, f_t, rgba(ink), 2 * S, 'l')
        elif kd == 'b':
            d.text((pad, cy), p, font=f_b, fill=rgba(ink, 0.92), anchor='lm')
        elif kd == 'n':
            spaced(d, (pad, cy), p[0], p[1], rgba(st.accent), 2 * S, 'l')
        elif kd == 'q':
            d.text((pad, cy), p[0], font=p[1], fill=rgba(ink), anchor='lm')
        elif kd == 'by':
            d.text((pad, cy), p, font=font(st.ui_font, 28 * S, 500), fill=rgba(st.muted), anchor='lm')
        elif kd == 'img':
            portrait_block(im, st, p, pad, y, w - 2 * pad, rh - int(14 * S))
        y += rh
    return shadowed(im, int(12 * S), (0, int(8 * S)), 130)


def portrait_block(im, st, c, x, y, w, h):
    """licensed image (c['image']) in sepia/duotone, or a monogram plate when there is none"""
    path = c.get('image')
    if path and os.path.exists(path):
        src = Image.open(path).convert('L')
        r = max(w / src.width, h / src.height)
        src = src.resize((int(src.width * r) + 1, int(src.height * r) + 1), Image.LANCZOS)
        src = src.crop(((src.width - w) // 2, int((src.height - h) * 0.25), (src.width - w) // 2 + w, int((src.height - h) * 0.25) + h))
        a = np.array(src).astype(np.float32) / 255
        lo = np.array(st.ink, np.float32); hi = np.array(st.paper, np.float32)
        duo = (lo[None, None] * (1 - a[..., None]) + hi[None, None] * a[..., None]).astype(np.uint8)
        im.paste(Image.fromarray(duo), (x, y))
    else:
        d = ImageDraw.Draw(im)
        d.rectangle([x, y, x + w, y + h], fill=rgba(st.ink, 0.12 if sum(st.paper) > 300 else 0.5))
        name = c.get('name') or c.get('title') or '?'
        ini = ''.join(p[0] for p in name.split()[:2]).upper()
        f = font(st.title_font, h * 0.42) if st.title_font in ('Playfair', 'Fell') else font(st.title_font, h * 0.42, 600)
        d.text((x + w / 2, y + h / 2), ini, font=f, fill=rgba(st.ink if sum(st.paper) > 300 else (230, 230, 230), 0.55), anchor='mm')


def stamp(st, S, text, rot=-8, seed=0):
    col = tuple(getattr(st, 'stamp', st.accent))
    f = font(st.ui_font, 52 * S, 700)
    tw = text_w(text.upper(), f, 5 * S)
    w, h = int(tw + 60 * S), int(52 * S * 1.75)
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle([3, 3, w - 4, h - 4], outline=rgba(col), width=max(3, int(5 * S)))
    d.rectangle([int(12 * S), int(12 * S), w - 1 - int(12 * S), h - 1 - int(12 * S)], outline=rgba(col), width=max(1, int(2 * S)))
    spaced(d, (w / 2, h / 2 + 2), text.upper(), f, rgba(col), 5 * S)
    a = np.array(im); rg = np.random.default_rng(len(text) * 7 + seed)
    noise = cv2.GaussianBlur(rg.random((h, w)).astype(np.float32), (0, 0), 1.3)
    a[..., 3] = (a[..., 3] * np.clip((noise - 0.1) * 2.6, 0, 1)).astype(np.uint8)
    return shadowed(Image.fromarray(a).rotate(rot, Image.BICUBIC, expand=True), 3, (0, 2), 120)


def end_card(ov, st, S, L, lines, credit, a):
    if a <= 0.01:
        return
    d = ImageDraw.Draw(ov)
    W, H = ov.size
    veil = Image.new('RGBA', (W, H), rgba(st.paper if sum(st.paper) > 300 else (0, 0, 0), 0.55 * a))
    ov.alpha_composite(veil)
    col = st.ink if sum(st.paper) > 300 else (240, 236, 226)
    cy = H * 0.42
    f1 = font(st.ui_font, 26 * S, 500)
    spaced(d, (W / 2, cy - 70 * S), 'SOURCES', f1, rgba(st.accent, a), 8 * S)
    fb = font(st.ui_font, 28 * S, 400)
    y = cy - 20 * S
    for ln in lines[:5]:
        d.text((W / 2, y), ln, font=fb, fill=rgba(col, a), anchor='mm'); y += 44 * S
    y += 40 * S
    d.text((W / 2, y), credit, font=font(st.ui_font, 24 * S, 400), fill=rgba(st.muted, a), anchor='mm')
    fm = font(st.title_font, 46 * S) if st.title_font in ('Playfair', 'Fell') else font(st.title_font, 46 * S, 600)
    d.text((W / 2, y + 90 * S), 'made with rrender.ai', font=fm, fill=rgba(col, a), anchor='mm')


# ---------------------------------------------------------------- route heads (drawn on a cv2 RGBA layer)
def head(lay, kind, tip, back, col, S):
    d = np.asarray(tip) - np.asarray(back); L = np.linalg.norm(d)
    if L < 1e-3 or kind == 'none':
        return
    d /= L; nrm = np.array([-d[1], d[0]]); c = np.asarray(tip)
    def poly(shape, sz, color):
        p = np.array([c + d * x * sz + nrm * y * sz for x, y in shape])
        cv2.fillPoly(lay, [np.round(p * 4).astype(np.int32)], color, cv2.LINE_AA, shift=2)
    dark = (20, 12, 8, 200)
    if kind == 'arrow':
        sh = [(0.9, 0), (-0.6, 0.75), (-0.3, 0), (-0.6, -0.75)]
        poly(sh, 30 * S, dark); poly(sh, 26 * S, col + (255,))
    elif kind == 'dot':
        cv2.circle(lay, tuple(int(v) for v in c), int(14 * S), dark, -1, cv2.LINE_AA)
        cv2.circle(lay, tuple(int(v) for v in c), int(10 * S), col + (255,), -1, cv2.LINE_AA)
    elif kind == 'plane':
        sh = [(1.0, 0), (0.3, 0.12), (0.05, 0.95), (-0.15, 0.95), (0.0, 0.14), (-0.65, 0.12), (-0.8, 0.42), (-0.95, 0.42),
              (-0.88, 0), (-0.95, -0.42), (-0.8, -0.42), (-0.65, -0.12), (0.0, -0.14), (-0.15, -0.95), (0.05, -0.95), (0.3, -0.12)]
        poly(sh, 30 * S, dark); poly(sh, 27 * S, (245, 240, 230, 255))
    elif kind == 'ship':
        hull = [(0.9, 0), (0.5, 0.32), (-0.8, 0.32), (-0.9, 0), (-0.8, -0.32), (0.5, -0.32)]
        poly(hull, 30 * S, dark); poly(hull, 26 * S, col + (255,))
        sail = [(0.25, 0), (-0.1, 0.55), (-0.45, 0), (-0.1, -0.55)]
        poly(sail, 26 * S, (245, 238, 220, 255))
    elif kind == 'army':     # banner chevron
        sh = [(0.9, 0), (0.1, 0.7), (-0.5, 0.7), (0.15, 0), (-0.5, -0.7), (0.1, -0.7)]
        poly(sh, 32 * S, dark); poly(sh, 28 * S, col + (255,))
