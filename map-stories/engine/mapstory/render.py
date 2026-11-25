"""Timeline + spec -> frames. One Renderer per process; frame(t) returns an HxWx3 uint8 RGB array."""
import math
import numpy as np, cv2
from PIL import Image

from . import draw as D
from .geo import Cam, ll2v_arr
from .spec import camera, route_progress, window_alpha, latlon
from .styles import Style, render_base
from .world import World, Rays

LAYOUT = {
    '16:9': dict(header_y=92, header_w=900, year_xy=(64, 96), cap_y=1080 - 104, cap_size=62, title_y=430,
                 card_xy=('right', 0.50), stamp_xy=(0.5, 0.66)),
    '9:16': dict(header_y=250, header_w=880, year_xy=(64, 110), cap_y=1560, cap_size=66, title_y=700,
                 card_xy=('center', 0.665), stamp_xy=(0.5, 0.50)),
    '1:1': dict(header_y=96, header_w=820, year_xy=(56, 96), cap_y=960, cap_size=60, title_y=430,
                card_xy=('center', 0.66), stamp_xy=(0.5, 0.5)),
    '4:5': dict(header_y=120, header_w=860, year_xy=(56, 110), cap_y=1190, cap_size=62, title_y=520,
                card_xy=('center', 0.66), stamp_xy=(0.5, 0.5)),
}


class Renderer:
    def __init__(self, spec, tl, map_scale=0.667):
        self.s, self.tl = spec, tl
        self.W, self.H = tl['W'], tl['H']
        self.S = min(self.W, self.H) / 1080.0
        self.L = dict(LAYOUT[tl['aspect']])
        from .spec import ASPECTS
        ys = self.H / ASPECTS[tl['aspect']][1]          # 0.5 in --draft
        for k in ('header_y', 'cap_y', 'title_y'):
            self.L[k] = self.L[k] * ys
        self.L['header_w'] = self.L['header_w'] * self.S
        self.L['year_xy'] = (self.L['year_xy'][0] * self.S, self.L['year_xy'][1] * self.S)
        self.st = Style(tl['style'], tl.get('style_overrides'))
        self.world = World()
        self.ms = map_scale
        self.routes = {}
        for rid, r in tl['routes'].items():
            self.routes[rid] = dict(r, pts=np.array(r['pts']), cum=np.array(r['cum']))
        self.hl_masks = {}
        areas = spec.get('areas', {})
        for key in tl['hl']:
            if key in areas:
                poly = np.array([[p[1], p[0]] for p in areas[key]['polygon']], np.float32)
                self.hl_masks[key] = self.world.area_mips('area:' + key, [poly])
            else:
                self.hl_masks[key] = self.world.area_mips(key, self.world.country_rings(key))
        self.card_cache = {}
        yy, xx = np.mgrid[0:self.H, 0:self.W].astype(np.float32)
        vr = np.sqrt(((xx - self.W / 2) / (self.W * 0.72)) ** 2 + ((yy - self.H / 2) / (self.H * 0.72)) ** 2)
        self.vign = np.clip(1 - self.st.vignette * vr ** 2.4, 0.2, 1).astype(np.float32)[..., None]
        bands = getattr(self.st, 'bands', 0)
        if bands:      # dark top/bottom bands so white header and captions read over bright imagery
            y = np.arange(self.H, dtype=np.float32)[:, None, None]
            top = np.clip(1 - y / (self.L['header_y'] + 140 * self.S), 0, 1) ** 1.5
            bot = np.clip((y - (self.L['cap_y'] - 170 * self.S)) / (self.H - self.L['cap_y'] + 170 * self.S), 0, 1) ** 1.5
            self.vign = self.vign * (1 - bands * np.maximum(top, bot))
        rg = np.random.default_rng(7)
        self.grain = [rg.normal(0, 1, (self.H // 2, self.W // 2)).astype(np.float32) for _ in range(6)]
        srcs = [x.get('title', '') for x in spec.get('sources', [])]
        credit = 'Map data: Natural Earth (public domain)'
        if self.st.name == 'satellite':
            credit += ' + NASA Blue Marble'
        vc = spec.get('voice', {}).get('credit')
        if vc:
            credit += '  ·  Voice: ' + vc
        mc = (spec.get('music') or {}).get('credit')
        if mc:
            credit += '  ·  Music: ' + mc
        self.end_lines, self.credit = srcs, credit

    # ------------------------------------------------------------------ map layers
    def _map(self, cam_params):
        lat, lon, d, tilt = cam_params
        W, H = self.W, self.H
        small = Cam(lat, lon, d, tilt, int(W * self.ms), int(H * self.ms), oy=self.tl['oy'] * self.ms)
        rays = Rays(small)
        t = self._t
        hls = [(self.hl_masks[k], window_alpha(ws, t)) for k, ws in self.tl['hl'].items()]
        img = render_base(rays, self.world, self.st, [h for h in hls if h[1] > 0], self.tl['map']['graticule'])
        img = cv2.resize(img, (W, H), interpolation=cv2.INTER_CUBIC)
        cam = Cam(lat, lon, d, tilt, W, H, oy=self.tl['oy'])
        # vector borders and rivers at full resolution
        st = self.st
        lay = np.zeros((H, W), np.uint8)
        bk = float(np.clip((2.6 - d) / 1.2, 0, 1))
        if bk > 0 and st.border_a > 0 and self.tl['map']['borders']:
            pl = self.world.screen_lines(cam, 'borders')
            if pl:
                cv2.polylines(lay, [np.round(p * 4).astype(np.int32) for p in pl], False, 255, max(1, int(1.6 * self.S)), cv2.LINE_AA, shift=2)
                a = (lay.astype(np.float32) / 255 * st.border_a * bk)[..., None]
                img += (np.array(st.border, np.float32) / 255 - img) * a
        rk = float(np.clip((0.9 - d) / 0.4, 0, 1))
        if rk > 0 and st.kind == 'vector' and self.tl['map']['rivers']:
            lay[:] = 0
            pl = self.world.screen_lines(cam, 'rivers')
            if pl:
                cv2.polylines(lay, [np.round(p * 4).astype(np.int32) for p in pl], False, 255, max(1, int(2.4 * self.S)), cv2.LINE_AA, shift=2)
                a = (lay.astype(np.float32) / 255 * st.river_a * rk)[..., None]
                img += (np.array(st.river, np.float32) / 255 - img) * a
        return img, cam

    def _routes(self, img, cam, t):
        lay = np.zeros((self.H, self.W, 4), np.uint8)
        zf = float(np.clip((1.0 / max(cam.d, 0.05)) ** 0.18, 0.75, 1.35))
        heads = []
        for rid, r in self.routes.items():
            p = route_progress(r, t)
            if p <= 0.0005:
                continue
            col = self.st.route_color(r['color'])
            cum = r['cum']; n = max(2, int(np.searchsorted(cum, p)) + 1)
            px, vis = cam.project(r['pts'][:n])
            w = r['width']; w0, w1 = (w, w) if not isinstance(w, list) else (w[0], w[1])
            wid = (w0 + (w1 - w0) * cum[:n]) * self.S * zf
            ok = vis & (np.abs(px[:, 0]) < 4 * self.W) & (np.abs(px[:, 1]) < 4 * self.H)
            # chunk so the width can taper and dashes can break
            if r['style'] == 'dashed':
                sl = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(px, axis=0), axis=1))])
                ok &= ((sl // (26 * self.S)) % 2 == 0)
            for casing in (True, False):
                j = 0
                while j < n - 1:
                    k = min(n, j + 6)
                    seg = slice(j, k)
                    if ok[seg].all():
                        ww = float(wid[(j + k) // 2])
                        q = np.round(px[seg] * 4).astype(np.int32)
                        if casing:
                            cv2.polylines(lay, [q], False, (24, 14, 8, 110), int(ww + max(2.0, min(6.0, ww * 0.35)) * self.S), cv2.LINE_AA, shift=2)
                        else:
                            cv2.polylines(lay, [q], False, col + (255,), max(1, int(ww)), cv2.LINE_AA, shift=2)
                    j = k - 1
            last = r['segs'][-1] if r['segs'] else None
            drawing = any(a <= t <= b + 0.8 for a, b, _, _ in r['segs'])
            if drawing and vis[n - 1] and n >= 4:
                heads.append((r['head'], px[n - 1], px[max(0, n - 8)], col))
        for kind, tip, back, col in heads:
            D.head(lay, kind, tip, back, col, self.S * zf)
        la = lay.astype(np.float32) / 255
        img *= (1 - la[..., 3:]); img += la[..., :3] * la[..., 3:]

    # ------------------------------------------------------------------ overlays
    def _overlays(self, ov, cam, t):
        s, tl, st, S, L = self.s, self.tl, self.st, self.S, self.L
        W, H = self.W, self.H
        end_a = float(np.clip((t - tl['body_end'] - 0.9) / 0.6, 0, 1))
        # place labels (greedy collision avoidance in label order)
        taken = []
        for lid, ws in tl['labels'].items():
            a = window_alpha(ws, t, 0.3, 0.35) * (1 - end_a)
            if a <= 0:
                continue
            p = s['places'][lid]
            pos = cam.pt(p['lat'], p['lon'])
            if pos and -50 < pos[0] < W + 50 and -50 < pos[1] < H + 50:
                D.place_label(ov, st, S, pos, p['name'], p.get('kind', 'city'), a, p.get('side', 'r'), p.get('note'),
                              pulse=t + (sum(map(ord, lid)) % 7) * 0.23, taken=taken)
        # header
        for h in tl['headers']:
            D.header(ov, st, S, L, h['kicker'], h['title'], t, h['t0'], h['t1'])
        # year counter
        ys = [y for y in tl['years'] if y['t'] <= t]
        if ys:
            cur = ys[-1]; prev = ys[-2] if len(ys) > 1 else None
            k = (t - cur['t']) / 0.45
            ya = 1 - end_a
            if prev and k < 1 and prev['text'] != cur['text']:
                D.year_badge(ov, st, S, L, prev['text'], ya, flip=min(1, k))
                D.year_badge(ov, st, S, L, cur['text'], ya * min(1, k * 1.5), flip=-(1 - min(1, k)))
            else:
                D.year_badge(ov, st, S, L, cur['text'], ya * min(1, (t - ys[0]['t']) / 0.4))
        # cards
        for c in tl['cards']:
            k, a = D.pop(t, c['t0'], c['t1'])
            if a <= 0:
                continue
            spec = c['spec']
            if spec.get('kind') == 'stat' and t - c['t0'] < 1.6:
                spr = D.card(st, S, self._abs(spec), t - c['t0'])
            else:
                key = id(c)
                if key not in self.card_cache:
                    self.card_cache[key] = D.card(st, S, self._abs(spec))
                spr = self.card_cache[key]
            side, fy = L['card_xy']
            side = spec.get('side', side if tl['aspect'] == '16:9' else 'center')
            if side == 'right':
                cx = W - 70 * S - spr.width / 2
            elif side == 'left':
                cx = 70 * S + spr.width / 2
            else:
                cx = W / 2
            D.paste(ov, spr, cx, H * spec.get('y', fy), k, a, spec.get('rot', -1.2 if side != 'left' else 1.2))
        # stamps
        for i, sp in enumerate(tl['stamps']):
            sc, a = D.slam(t, sp['t0'], sp['t1'])
            if a <= 0:
                continue
            key = ('stamp', i)
            if key not in self.card_cache:
                self.card_cache[key] = D.stamp(st, S, sp['text'], sp['rot'], i)
            fx, fy = L['stamp_xy']
            D.paste(ov, self.card_cache[key], W * fx, H * fy, sc, a)
        # title over the first beat
        b0 = tl['beats'][0]
        ta = D.fade(t, 0.25, min(b0['end'] - 0.5, 4.2), 0.5, 0.5)
        D.title_card(ov, st, S, L, s['title'], s.get('subtitle'), ta)
        # captions
        if tl['captions'] and ta < 0.3:
            for b in tl['beats']:
                if b['start'] <= t < b['end'] + 0.3:
                    D.captions(ov, st, S, L, b['words'], t)
        D.end_card(ov, st, S, L, self.end_lines, self.credit, end_a)

    def _abs(self, c):
        if c.get('image') and not str(c['image']).startswith(('/', '\\')) and ':' not in str(c['image']):
            c = dict(c); c['image'] = __import__('os').path.join(self.s['_dir'], c['image'])
        return c

    # ------------------------------------------------------------------ frame
    def frame(self, t):
        self._t = t
        cp = camera(self.tl, t)
        img, cam = self._map(cp)
        self._routes(img, cam, t)
        img *= self.vign
        g = cv2.resize(self.grain[int(t * self.tl['fps']) % len(self.grain)], (self.W, self.H), interpolation=cv2.INTER_LINEAR)
        img += g[..., None] * self.st.grain
        np.clip(img, 0, 1, out=img)
        base = Image.fromarray((img * 255).astype(np.uint8)).convert('RGBA')
        ov = Image.new('RGBA', (self.W, self.H), (0, 0, 0, 0))
        self._overlays(ov, cam, t)
        base.alpha_composite(ov)
        out = np.array(base.convert('RGB'))
        for k in self.tl['keys']:
            if k['move'] == 'cut':
                x = abs(t - k['fs'])
                if x < 0.12:
                    out = (out * (0.3 + 0.7 * x / 0.12)).astype(np.uint8)
        fo = float(np.clip((self.tl['end'] - t) / 0.5, 0, 1))
        if fo < 1:
            out = (out * fo).astype(np.uint8)
        return out
