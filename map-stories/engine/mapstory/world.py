"""World data (Natural Earth, public domain) and the ray-cast map base for every style.

The vector styles never need a raster download: land, lakes and highlighted countries are
rasterised once from engine/data/world.npz into equirectangular masks (cached in
engine/data/cache/), sampled per pixel and sharpened with a screen-space gradient so
coastlines stay crisp at any zoom. The satellite style samples NASA Blue Marble instead.
"""
import math, os
import numpy as np, cv2

from .geo import ll2v, ll2v_arr

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
CACHE = os.path.join(DATA, 'cache')
MASK_W = 16384


class World:
    def __init__(self):
        z = np.load(os.path.join(DATA, 'world.npz'))
        pts, lens = z['pts'], z['lens']
        idx = np.concatenate([[0], np.cumsum(lens)])
        self.rings = [pts[idx[i]:idx[i + 1]] for i in range(len(lens))]
        self.names = [str(n) for n in z['names']]
        lp, ll = z['lake_pts'], z['lake_lens']
        li = np.concatenate([[0], np.cumsum(ll)])
        self.lakes = [lp[li[i]:li[i + 1]] for i in range(len(ll))]
        self.lines = {'borders': self._lineset(pts, lens)}
        if 'river_pts' in z.files and len(z['river_lens']):
            self.lines['rivers'] = self._lineset(z['river_pts'], z['river_lens'])
        self._masks = {}

    @staticmethod
    def _lineset(pts, lens):
        idx = np.concatenate([[0], np.cumsum(lens)])
        v = ll2v_arr(pts).astype(np.float64)
        cen, rad = [], []
        for i in range(len(lens)):
            seg = v[idx[i]:idx[i + 1]]
            c = seg.mean(0); c /= max(np.linalg.norm(c), 1e-9)
            cen.append(c); rad.append(float(np.arccos(np.clip(seg @ c, -1, 1)).max()))
        return dict(v=v, idx=idx, c=np.array(cen), r=np.array(rad))

    def screen_lines(self, cam, kind, margin=60):
        """visible pieces of a line set as screen polylines (list of (n,2) float arrays)"""
        ls = self.lines.get(kind)
        if ls is None:
            return []
        P = ll2v(cam.lat, cam.lon)
        horizon = math.acos(1 / (1 + cam.d)) + math.radians(cam.tilt) * 0.5 + 0.05
        ang = np.arccos(np.clip(ls['c'] @ P, -1, 1))
        keep = np.flatnonzero(ang - ls['r'] < horizon)
        out = []
        W, H = cam.W, cam.H
        for i in keep:
            a, b = ls['idx'][i], ls['idx'][i + 1]
            px, vis = cam.project(ls['v'][a:b])
            ok = vis & (px[:, 0] > -margin) & (px[:, 0] < W + margin) & (px[:, 1] > -margin) & (px[:, 1] < H + margin)
            if ok.sum() < 2:
                continue
            # split into runs of consecutive ok points
            d = np.diff(np.concatenate([[0], ok.astype(np.int8), [0]]))
            for s0, s1 in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)):
                if s1 - s0 >= 2:
                    out.append(px[s0:s1])
        return out

    def country_names(self):
        return sorted(set(self.names))

    # ---------------------------------------------------------------- equirectangular masks
    def _raster(self, rings, holes=(), w=MASK_W, blur=1.0):
        h = w // 2
        m = np.zeros((h, w), np.uint8)
        def pix(r):
            x = (r[:, 0] + 180.0) / 360.0 * w; y = (90.0 - r[:, 1]) / 180.0 * h
            return np.round(np.stack([x, y], 1) * 8).astype(np.int32)
        cv2.fillPoly(m, [pix(r) for r in rings], 255, cv2.LINE_AA, shift=3)
        if holes:
            cv2.fillPoly(m, [pix(r) for r in holes], 0, cv2.LINE_AA, shift=3)
        if blur:
            m = cv2.GaussianBlur(m, (0, 0), blur)
        return m

    def land_mips(self):
        if 'land' not in self._masks:
            os.makedirs(CACHE, exist_ok=True)
            fn = os.path.join(CACHE, f'land_{MASK_W}.png')
            if os.path.exists(fn):
                m = cv2.imread(fn, cv2.IMREAD_GRAYSCALE)
            else:
                m = self._raster(self.rings, self.lakes)
                tmp = fn + f'.{os.getpid()}.tmp.png'; cv2.imwrite(tmp, m); os.replace(tmp, fn)   # atomic
            self._masks['land'] = mips(m)
        return self._masks['land']

    def coast_distance(self):
        """distance to the nearest coast in degrees (sea side only), 4096 px equirect, capped at 8 deg"""
        if 'dist' not in self._masks:
            fn = os.path.join(CACHE, 'coastdist_4096.npy')
            if os.path.exists(fn):
                d = np.load(fn)
            else:
                m = cv2.resize(self.land_mips()[0], (4096, 2048), interpolation=cv2.INTER_AREA)
                sea = (m < 128).astype(np.uint8)
                d = cv2.distanceTransform(sea, cv2.DIST_L2, 5) * (360.0 / 4096)
                d = np.minimum(d, 8.0).astype(np.float16)
                tmp = fn + f'.{os.getpid()}.tmp.npy'; np.save(tmp, d); os.replace(tmp, fn)
            self._masks['dist'] = d.astype(np.float32)
        return self._masks['dist']

    def area_mips(self, key, rings_lonlat):
        """mask for a highlighted country (key = Natural Earth ADMIN name) or a custom polygon"""
        if key not in self._masks:
            self._masks[key] = mips(self._raster(rings_lonlat, w=8192, blur=1.2))
        return self._masks[key]

    def country_rings(self, name):
        r = [self.rings[i] for i, n in enumerate(self.names) if n == name]
        if not r:
            raise KeyError(f'unknown country "{name}" (use a Natural Earth ADMIN name, e.g. "France", '
                           f'"United States of America"; list them with: python -m mapstory countries)')
        return r


def mips(m, min_w=1024):
    out = [m]
    while out[-1].shape[1] > min_w:
        out.append(cv2.resize(out[-1], (out[-1].shape[1] // 2, out[-1].shape[0] // 2), interpolation=cv2.INTER_AREA))
    return out


# ---------------------------------------------------------------- per-frame ray cast
class Rays:
    """lat/lon of every pixel for one camera (shared by all layers of a frame)"""

    def __init__(self, cam):
        W, H = cam.W, cam.H
        key = (W, H, cam.TH, cam.oy)
        if Rays._grid_key != key:
            yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
            Rays._sx = ((2 * (xx + 0.5) / W - 1) * cam.TH * cam.ASP).astype(np.float32)
            Rays._sy = ((1 - 2 * (yy + 0.5 - cam.oy) / H) * cam.TH).astype(np.float32)
            Rays._grid_key = key
        F, R, U, C = [x.astype(np.float32) for x in (cam.F, cam.R, cam.U, cam.C)]
        sx, sy = Rays._sx, Rays._sy
        dx = F[0] + sx * R[0] + sy * U[0]; dy = F[1] + sx * R[1] + sy * U[1]; dz = F[2] + sx * R[2] + sy * U[2]
        n = np.sqrt(dx * dx + dy * dy + dz * dz); dx /= n; dy /= n; dz /= n
        b = dx * C[0] + dy * C[1] + dz * C[2]; c = float(C @ C - 1); disc = b * b - c
        hs = np.sqrt(np.maximum(disc, 0)) * (b < 0)
        g = np.abs(cv2.Sobel(hs, cv2.CV_32F, 1, 0, ksize=1)) + np.abs(cv2.Sobel(hs, cv2.CV_32F, 0, 1, ksize=1))
        self.hit = np.clip(hs / (g * 0.5 + 1e-6), 0, 1)          # anti-aliased globe coverage
        s = -b - hs
        hx = C[0] + s * dx; hy = C[1] + s * dy; hz = C[2] + s * dz
        self.lat = np.arcsin(np.clip(hz, -1, 1)); self.lon = np.arctan2(hy, hx)
        self.ndv = np.clip(-(hx * dx + hy * dy + hz * dz), 0, 1)
        self.b, self.C = b, C
        self.miss_glow = np.sqrt(np.maximum(float(C @ C) - b * b, 0))   # ray distance from the globe centre
        self.px = cam.px_size()
        self.W, self.H = W, H

    _grid_key = None

    def sample(self, mip_list, tex_w0, px_rad=None, wrap=True):
        """bilinear sample of an equirect texture pyramid at the right level -> float32 HxW in 0..1 (or raw)"""
        px_rad = px_rad or self.px
        lvl = 0
        while lvl < len(mip_list) - 1 and (2 * math.pi / mip_list[lvl + 1].shape[1]) < px_rad * 1.2:
            lvl += 1
        tex = mip_list[lvl]; tw, th = tex.shape[1], tex.shape[0]
        mx = ((self.lon + np.pi) / (2 * np.pi) * tw - 0.5).astype(np.float32)
        my = ((np.pi / 2 - self.lat) / np.pi * th - 0.5).astype(np.float32)
        out = cv2.remap(tex, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP if wrap else cv2.BORDER_REPLICATE)
        return out.astype(np.float32) / (255.0 if tex.dtype == np.uint8 else 1.0)


def crisp(L, sharp=1.0):
    """soft 0..1 field -> anti-aliased step at 0.5 and a ~1.5 px contour line"""
    g = np.abs(cv2.Sobel(L, cv2.CV_32F, 1, 0, ksize=1)) + np.abs(cv2.Sobel(L, cv2.CV_32F, 0, 1, ksize=1))
    g = g * 0.5 + 1e-4
    step = np.clip((L - 0.5) / (g * sharp) + 0.5, 0, 1)
    line = np.clip(1.0 - np.abs(L - 0.5) / (g * 1.4), 0, 1)
    return step, line


def contour_lines(F, width=1.0):
    """lines where the scalar field F crosses an integer, ~width px wide"""
    g = np.abs(cv2.Sobel(F, cv2.CV_32F, 1, 0, ksize=1)) + np.abs(cv2.Sobel(F, cv2.CV_32F, 0, 1, ksize=1))
    g = g * 0.5 + 1e-5
    fr = np.abs(F - np.round(F))
    return np.clip(1.0 - fr / (g * width), 0, 1)


_NOISE = None


def noise_tex():
    global _NOISE
    if _NOISE is None:
        # tileable 1/f noise via FFT (periodic by construction, so BORDER_WRAP has no seams)
        rg = np.random.default_rng(11)
        w = np.fft.fft2(rg.normal(0, 1, (512, 512)))
        fy = np.fft.fftfreq(512)[:, None]; fx = np.fft.fftfreq(512)[None, :]
        f = np.sqrt(fx * fx + fy * fy); f[0, 0] = 1
        n = np.real(np.fft.ifft2(w / f ** 1.5)).astype(np.float32)
        _NOISE = (n - n.mean()) / (n.std() + 1e-6)
    return _NOISE


def geo_noise(rays, cells_per_screen=6.0):
    """geography-locked noise whose scale stays near-constant on screen while zooming (octave blend)"""
    N = noise_tex()
    span = rays.px * rays.H                       # radians across the screen height
    k = 2 * math.pi / span * cells_per_screen / 512.0 * 64   # texture repeats per 2*pi
    lk = math.log2(max(k, 1e-6)); k0 = 2 ** math.floor(lk); f = lk - math.floor(lk)
    out = 0
    for kk, w in ((k0, 1 - f), (k0 * 2, f)):
        mx = ((rays.lon / (2 * math.pi)) * kk * 512 % 512).astype(np.float32)
        my = ((rays.lat / (2 * math.pi)) * kk * 512 % 512).astype(np.float32)
        out = out + w * cv2.remap(N, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    return out


# ---------------------------------------------------------------- Blue Marble (satellite style)
_BM = None


def bluemarble():
    global _BM
    if _BM is None:
        fn = os.environ.get('MAPSTORY_BLUEMARBLE') or os.path.join(CACHE, 'bluemarble.jpg')
        if not os.path.exists(fn):
            return None
        im = cv2.imread(fn, cv2.IMREAD_COLOR)[:, :, ::-1].copy()
        _BM = mips(im, 1500)
    return _BM
