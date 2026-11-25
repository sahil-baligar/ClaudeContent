"""Era styles: one palette + map treatment + type set per look. See design/DESIGN.md.

Map colours are floats 0..1 (they go into the numpy map); overlay colours are 0..255 RGB.
"""
import math
import numpy as np

from .world import crisp, contour_lines, geo_noise, bluemarble


def f(rgb):
    return np.array(rgb, np.float32) / 255.0


STYLES = {
    # DEFAULT. Light mode: true-white land and paper, pale blue sea with ripple lines, ink coast, red routes
    'light': dict(
        kind='vector', bg=(255, 255, 255), glow=(205, 215, 225),
        sea=(228, 236, 242), sea_deep=(214, 226, 236), land=(255, 255, 255), land_var=0.0, river=(150, 182, 208), river_a=0.85,
        coast=(28, 32, 38), coast_a=0.9, ripple=(150, 172, 190), ripple_a=0.3, ripple_n=3,
        grat=(176, 186, 196), grat_a=0.28, grat_step=15, border=(165, 170, 178), border_a=0.55,
        hl_fill=(232, 70, 50), hl_fill_a=0.16, hl_line=(214, 48, 34),
        ink=(17, 17, 17), paper=(255, 255, 255), accent=(214, 40, 30), accent2=(24, 90, 180), muted=(108, 114, 122),
        routes=[(214, 40, 30), (17, 17, 17), (24, 90, 180), (232, 140, 20)],
        title_font='Playfair', label_font='Oswald', ui_font='Oswald', hand_font='Caveat',
        cap_fg=(255, 255, 255), cap_hl=(255, 92, 72), cap_stroke=(0, 0, 0),
        vignette=0.0, grain=0.0, limb=0.10),
    # 1500s-1800s: sepia chart paper, ink coast, ripple lines on the sea, rhumb graticule
    'antique': dict(
        kind='vector', bg=(58, 44, 32), glow=(236, 200, 140),
        sea=(196, 186, 156), sea_deep=(178, 170, 142), land=(234, 220, 184), land_var=0.035, river=(92, 112, 118), river_a=0.7,
        coast=(70, 46, 28), coast_a=0.9, ripple=(96, 74, 50), ripple_a=0.32, ripple_n=4,
        grat=(110, 84, 58), grat_a=0.20, grat_step=15, border=(120, 80, 52), border_a=0.42,
        hl_fill=(196, 118, 60), hl_fill_a=0.42, hl_line=(128, 44, 24),
        ink=(54, 36, 22), paper=(240, 229, 202), accent=(154, 36, 26), accent2=(34, 62, 104), muted=(126, 100, 72),
        routes=[(156, 30, 22), (34, 62, 108), (52, 104, 60), (120, 70, 20)],
        title_font='Playfair', label_font='Fell', ui_font='Oswald', hand_font='Caveat',
        cap_fg=(255, 250, 238), cap_hl=(244, 190, 80), cap_stroke=(34, 22, 12),
        vignette=0.55, grain=0.022, limb=0.35),
    # 1880s-1950s school atlas: cream land, soft blue sea, red route
    'atlas': dict(
        kind='vector', bg=(222, 216, 200), glow=(255, 255, 255),
        sea=(170, 200, 214), sea_deep=(140, 176, 196), land=(240, 232, 206), land_var=0.03, river=(96, 150, 190), river_a=0.8,
        coast=(70, 96, 120), coast_a=0.8, ripple=(90, 130, 156), ripple_a=0.22, ripple_n=3,
        grat=(90, 120, 140), grat_a=0.14, grat_step=10, border=(150, 110, 96), border_a=0.5,
        hl_fill=(232, 160, 96), hl_fill_a=0.5, hl_line=(180, 70, 40),
        ink=(30, 36, 44), paper=(252, 249, 240), accent=(200, 46, 40), accent2=(30, 80, 140), muted=(110, 116, 124),
        routes=[(206, 40, 36), (30, 84, 150), (40, 130, 70), (150, 90, 20)],
        title_font='Oswald', label_font='Oswald', ui_font='Oswald', hand_font='Caveat',
        cap_fg=(255, 255, 255), cap_hl=(255, 206, 70), cap_stroke=(20, 26, 34),
        vignette=0.3, grain=0.012, limb=0.25),
    # dark (optional): 1940s-1990s situation room: dark slate, cyan coast, amber routes. Also available as 'dark'.
    'warroom': dict(
        kind='vector', bg=(6, 9, 12), glow=(80, 190, 210),
        sea=(14, 24, 30), sea_deep=(9, 16, 21), land=(34, 46, 46), land_var=0.04, river=(70, 150, 160), river_a=0.6,
        coast=(110, 206, 214), coast_a=0.85, ripple=(70, 150, 160), ripple_a=0.18, ripple_n=3,
        grat=(70, 150, 160), grat_a=0.16, grat_step=10, border=(90, 170, 176), border_a=0.35,
        hl_fill=(230, 160, 60), hl_fill_a=0.30, hl_line=(250, 190, 90),
        ink=(220, 236, 236), paper=(14, 22, 26), accent=(244, 170, 60), accent2=(110, 206, 214), muted=(120, 150, 152),
        routes=[(244, 170, 60), (110, 206, 214), (230, 80, 70), (200, 200, 200)],
        title_font='Roboto', label_font='Roboto', ui_font='Roboto', hand_font='Caveat',
        cap_fg=(240, 248, 248), cap_hl=(244, 180, 70), cap_stroke=(0, 0, 0),
        vignette=0.6, grain=0.02, limb=0.4),
    # modern: NASA Blue Marble, graded warm (needs tools/fetch_data.py --bluemarble; falls back to atlas)
    'satellite': dict(
        kind='satellite', bg=(0, 0, 0), glow=(90, 140, 220),
        coast=(240, 236, 226), coast_a=0.0, grat_a=0.0, border=(236, 230, 216), border_a=0.32,
        hl_fill=(220, 184, 132), hl_fill_a=0.46, hl_line=(250, 230, 190),
        ink=(245, 240, 230), paper=(0, 0, 0), accent=(214, 178, 92), accent2=(190, 36, 30), muted=(190, 182, 166),
        routes=[(190, 36, 30), (214, 176, 84), (240, 240, 240), (90, 160, 220)],
        title_font='Playfair', label_font='Oswald', ui_font='Oswald', hand_font='Caveat',
        cap_fg=(248, 244, 236), cap_hl=(241, 196, 76), cap_stroke=(0, 0, 0),
        stamp=(206, 44, 36), bands=0.7,
        vignette=0.6, grain=0.018, limb=0.45),
}


ALIASES = {'dark': 'warroom'}


class Style:
    def __init__(self, name='light', overrides=None):
        name = ALIASES.get(name, name)
        if name not in STYLES:
            raise KeyError(f'unknown style "{name}" (choose one of {", ".join(STYLES)})')
        d = dict(STYLES[name]); d.update(overrides or {})
        if d['kind'] == 'satellite' and bluemarble() is None:
            print('[mapstory] Blue Marble not found (python tools/fetch_data.py --bluemarble); using style "atlas"')
            d = dict(STYLES['atlas']); d.update(overrides or {}); name = 'atlas'
        self.name = name
        self.__dict__.update(d)

    def route_color(self, i_or_rgb):
        if isinstance(i_or_rgb, int):
            return tuple(self.routes[i_or_rgb % len(self.routes)])
        if isinstance(i_or_rgb, str) and i_or_rgb.startswith('#'):
            h = i_or_rgb.lstrip('#'); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
        if isinstance(i_or_rgb, str):
            return tuple(getattr(self, i_or_rgb))
        return tuple(i_or_rgb)


def render_base(rays, world, st, highlights=(), graticule=True):
    """the map itself (no overlays) -> float32 HxWx3; highlights = [(mask_mips, strength 0..1)]"""
    deg_px = math.degrees(rays.px)
    if st.kind == 'satellite':
        col = rays.sample(bluemarble(), 0)
        lum = col @ np.array([0.3, 0.59, 0.11], np.float32)
        col = col * 0.72 + lum[..., None] * 0.28
        sea = np.clip((col[..., 2] - col[..., 0]) * 4, 0, 1)[..., None]
        col = col * (1 - 0.45 * sea) + np.array([0.03, 0.06, 0.11], np.float32) * 0.45 * sea
        col = np.clip((col - 0.04) * 1.18, 0, 1) ** 1.08
        col *= np.array([1.06, 1.0, 0.86], np.float32)   # warmer than raw Blue Marble
        land = None
    else:
        L = rays.sample(world.land_mips(), 0)
        land, coast = crisp(L)
        n = geo_noise(rays)
        D = rays.sample([world.coast_distance()], 0)
        deep = np.clip(D / 5.0, 0, 1)[..., None]
        sea = f(st.sea) * (1 - deep) + f(st.sea_deep) * deep
        sea = sea * (1 + 0.012 * n[..., None])
        lnd = f(st.land) * (1 + st.land_var * n[..., None])
        col = sea * (1 - land[..., None]) + lnd * land[..., None]
        if st.ripple_a > 0:
            sp = deg_px * 11.0
            fade = float(np.clip((sp - 0.01) / 0.03, 0, 1))
            if fade > 0:
                F = D / sp
                rip = contour_lines(F, 0.9) * (F > 0.5) * np.clip(1 - F / st.ripple_n, 0, 1) * (1 - land)
                a = (rip * st.ripple_a * fade)[..., None]
                col += (f(st.ripple) - col) * a
        if st.grat_a > 0 and graticule:
            latd = np.degrees(rays.lat) / st.grat_step; lond = np.degrees(rays.lon) / st.grat_step
            g = np.maximum(contour_lines(latd, 0.8), contour_lines(lond, 0.8))
            a = (g * st.grat_a)[..., None]
            col += (f(st.grat) - col) * a
        a = (coast * st.coast_a)[..., None]
        col += (f(st.coast) - col) * a
    for mm, k in highlights:
        if k <= 0.001:
            continue
        A = rays.sample(mm, 0)
        step, line = crisp(A)
        a = (step * st.hl_fill_a * k)[..., None]
        col += (f(st.hl_fill) - col) * a
        a = (np.clip(line * 1.3, 0, 1) * k)[..., None]
        col += (f(st.hl_line) - col) * a
    col *= (1 - st.limb + st.limb * np.sqrt(rays.ndv))[..., None]
    hit = rays.hit[..., None]
    col -= f(st.bg); col *= hit; col += f(st.bg)
    m = rays.miss_glow
    glow = np.exp(-np.maximum(m - 1, 0) / 0.02) * (rays.b < 0) * (1 - rays.hit)
    col += glow[..., None] * (f(st.glow) * 0.5)
    np.clip(col, 0, 1, out=col)
    return col
