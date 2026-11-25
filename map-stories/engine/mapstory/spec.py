"""Story spec -> timeline (beats, camera, routes, overlays, captions, sound events).

The spec format is documented in schema/story.schema.json and PLAYBOOK.md. The timeline is a
plain dict (JSON-serialisable) so render workers and the audio mixer share exactly the same plan.
"""
import json, math, os
import numpy as np

from .geo import ll2v, v2ll, angle, slerp, ease, eout, route_points, cum_length, zoom_distance, frame_points, fit_distance

ASPECTS = {'16:9': (1920, 1080), '9:16': (1080, 1920), '1:1': (1080, 1080), '4:5': (1080, 1350)}
LEAD, TAIL, OUTRO = 0.12, 0.33, 4.0     # lead + tail <= 0.5 s keeps voice gaps tight


def load(path):
    with open(path, encoding='utf8') as f:
        s = json.load(f)
    s['_dir'] = os.path.dirname(os.path.abspath(path))
    validate(s)
    return s


def validate(s):
    errs = []
    for k in ('id', 'title', 'beats', 'places'):
        if k not in s:
            errs.append(f'missing "{k}"')
    places = s.get('places', {}); routes = s.get('routes', {}); areas = s.get('areas', {})
    for pid, p in places.items():
        if not (-90 <= p.get('lat', 999) <= 90 and -180 <= p.get('lon', 999) <= 180):
            errs.append(f'place {pid}: lat/lon out of range')
    def ref(x, where):
        if isinstance(x, str) and x not in places:
            errs.append(f'{where}: unknown place "{x}"')
    for rid, r in routes.items():
        if len(r.get('path', [])) < 2:
            errs.append(f'route {rid}: path needs 2+ points')
        for x in r.get('path', []):
            ref(x, f'route {rid}')
    for i, b in enumerate(s.get('beats', [])):
        w = f'beat {i + 1}'
        if not b.get('vo') and not b.get('min'):
            errs.append(f'{w}: needs "vo" (narration) or "min" (seconds)')
        cam = b.get('camera', {})
        to = cam.get('to')
        if to is None and i == 0:
            errs.append(f'{w}: first beat needs camera.to')
        if isinstance(to, list) and to and isinstance(to[0], str):
            for x in to: ref(x, w)
        elif isinstance(to, str):
            ref(to, w)
        for x in b.get('labels', []):
            ref(x, w)
        for d in b.get('draw', []):
            rid = d if isinstance(d, str) else d.get('route')
            if rid not in routes:
                errs.append(f'{w}: unknown route "{rid}"')
        if cam.get('move') == 'follow' and cam.get('route') not in routes:
            errs.append(f'{w}: camera.move=follow needs camera.route')
        for h in b.get('highlight', []):
            if not isinstance(h, str):
                errs.append(f'{w}: highlight entries are country names or area ids')
    if 'TODO' in json.dumps({k: v for k, v in s.items() if k not in ('notes', '_dir')}):
        errs.append('still contains TODO placeholders (finish the PLAYBOOK steps first)')
    if errs:
        raise ValueError('story spec problems:\n  ' + '\n  '.join(errs))


def latlon(s, x):
    if isinstance(x, str):
        p = s['places'][x]; return (p['lat'], p['lon'])
    return (float(x[0]), float(x[1]))


# ---------------------------------------------------------------- word timing
def word_times(text, t0, t1):
    """spread the caption words over the speech span, weighted by length and punctuation"""
    words = text.split()
    if not words:
        return []
    wts = [len(w.strip('.,;:!?')) + 1.5 + (3 if w[-1] in ',;:' else 0) + (5 if w[-1] in '.!?' else 0) for w in words]
    tot = sum(wts); out = []; c = t0
    for w, k in zip(words, wts):
        d = (t1 - t0) * k / tot
        out.append([w, c, c + d * 0.85]); c += d
    return out


# ---------------------------------------------------------------- the plan
def build(s, aspect, vo):
    """vo: list per beat of {'path': wav or None, 'dur': seconds, 'speech': [s, e]} -> timeline dict"""
    W, H = ASPECTS[aspect]
    beats = []
    t = 0.0
    for i, b in enumerate(s['beats']):
        v = vo[i]
        sp0, sp1 = v.get('speech', [0, v['dur']])
        speech = max(0.0, sp1 - sp0) if v['dur'] > 0 else 0.0
        # the clip is placed so its first spoken sample lands LEAD after the beat starts (TTS padding is skipped)
        dur = max(b.get('min', 0.0), LEAD + speech + b.get('hold', TAIL))
        cap = b.get('caption', b.get('vo', ''))
        words = word_times(cap, t + LEAD, t + LEAD + speech) if (cap and speech > 0) else []
        beats.append(dict(i=i, start=t, end=t + dur, vo_start=t + LEAD - sp0, vo_trim=[sp0, sp1 + 0.06],
                          vo_path=v.get('path'), words=words))
        t += dur
    body_end = t
    end = t + OUTRO

    # ---- routes: geometry + progress segments
    routes = {}
    for k, (rid, r) in enumerate(s.get('routes', {}).items()):
        pts = route_points([latlon(s, x) for x in r['path']], r.get('n', 500), r.get('lift', 0.0), offset_km=r.get('offset_km', 0.0))
        routes[rid] = dict(pts=pts.tolist(), cum=cum_length(pts).tolist(), color=r.get('color', k),
                           width=r.get('width', 9), style=r.get('style', 'solid'), head=r.get('head', 'arrow'),
                           segs=[], label=r.get('label'))

    # ---- camera keys
    def target(b, i):
        cam = b.get('camera', {})
        to = cam.get('to')
        if to is None:
            return None
        if isinstance(to, list) and to and isinstance(to[0], (str, list)):
            lat, lon, d = frame_points([latlon(s, x) for x in to], W, H, cam.get('pad', 1.3))
            if 'zoom' in cam:
                d = max(d, zoom_distance(cam['zoom'], W, H))
        else:
            lat, lon = latlon(s, to)
            d = zoom_distance(cam.get('zoom', 'country'), W, H)
        tilt = cam.get('tilt', 0 if (cam.get('zoom') == 'globe') else 28)
        return [lat, lon, d, tilt]

    keys = []
    prev = None
    for i, b in enumerate(s['beats']):
        tg = target(b, i) or (prev and list(prev['to']))
        cam = b.get('camera', {})
        move = cam.get('move', 'fly')
        bt = beats[i]
        if i == 0:
            lat, lon, d, tilt = tg
            fr = [lat - 6, lon - 38, d * 1.35, 0]
            fly = max(1.0, (bt['end'] - bt['start']) - 0.12)   # the opening globe turns for the whole hook (no idle title)
            k = dict(fs=0.0, fly=fly, frm=fr, to=tg, move='fly', hop=0.0, push=cam.get('push', 0.05))
        else:
            fs = bt['start'] - 0.12
            a = angle(ll2v(*prev['to'][:2]), ll2v(*tg[:2]))
            zr = abs(math.log(tg[2] / prev['to'][2]))
            fly = 0.0 if move == 'cut' else min(max(0.9, 0.7 + 1.1 * a + 0.3 * zr), cam.get('fly_max', 3.0),
                                                 (bt['end'] - bt['start']) * 0.7)
            k = dict(fs=fs, fly=fly, frm=None, to=tg, move=move, hop=cam.get('hop', 0.9), push=cam.get('push', 0.08),
                     route=cam.get('route'), drift=cam.get('drift', 1.0), i=i)
        keys.append(k); prev = k
        bt['arrive'] = k['fs'] + k['fly']

    # outro: pull out to frame everything that was shown
    used = set()
    for b in s['beats']:
        used.update(b.get('labels', []))
        for d in b.get('draw', []):
            rid = d if isinstance(d, str) else d['route']; used.update(x for x in s['routes'][rid]['path'] if isinstance(x, str))
    pts = [latlon(s, x) for x in used] or [tuple(keys[-1]['to'][:2])]
    lat, lon, d = frame_points(pts, W, H, 1.25)
    if d > zoom_distance('globe', W, H):        # the story spans the planet: end on a plain globe, not a pole
        lat, lon, d = max(-25.0, min(45.0, keys[-1]['to'][0])), keys[-1]['to'][1], zoom_distance('globe', W, H)
    keys.append(dict(fs=body_end - 0.2, fly=2.2, frm=None, to=[lat, lon, d * 1.1, 10], move='fly', hop=0.3, push=0.04))

    # ---- per-beat overlays
    hl_win, lab_win, hdr, years, cards, stamps, draws = {}, {}, [], [], [], [], []
    for i, b in enumerate(s['beats']):
        bt = beats[i]; t0, t1 = bt['start'], bt['end']
        appear = max(t0 + 0.35, bt['arrive'] - 0.5)
        for h in b.get('highlight', []):
            hl_win.setdefault(h, []).append([appear, t1])
        for j, lid in enumerate(b.get('labels', [])):
            lab_win.setdefault(lid, []).append([appear + 0.18 * j, t1])
        if b.get('header'):
            h = b['header'] if isinstance(b['header'], dict) else {'title': b['header']}
            if hdr and hdr[-1]['kicker'] == h.get('kicker') and hdr[-1]['title'] == h.get('title') and abs(hdr[-1]['t1'] - t0) < 0.05:
                hdr[-1]['t1'] = t1
            else:
                hdr.append(dict(kicker=h.get('kicker'), title=h.get('title'), t0=t0 + 0.2, t1=t1 - 0.15))
        if b.get('year') is not None:
            years.append(dict(t=t0 + 0.2, text=str(b['year'])))
        bc = b.get('card')
        for c in ([bc] if isinstance(bc, dict) else (bc or [])):
            at = t0 + (t1 - t0) * c.get('at', 0.3)
            cards.append(dict(spec=c, t0=max(at, bt['arrive'] - 0.2), t1=t1 - 0.2))
        stp = b.get('stamp')
        if stp:
            stp = stp if isinstance(stp, dict) else {'text': stp}
            stamps.append(dict(text=stp['text'], t0=t0 + (t1 - t0) * stp.get('at', 0.6), t1=t1 - 0.15, rot=stp.get('rot', -8)))
        for d in b.get('draw', []):
            d = {'route': d} if isinstance(d, str) else d
            r = routes[d['route']]
            p0 = r['segs'][-1][3] if r['segs'] else 0.0
            p1 = d.get('to', 1.0)
            dt0 = max(t0 + 0.3, bt['arrive'] - 0.3) + d.get('delay', 0.0)
            dt1 = max(dt0 + 0.6, t1 - 0.35)
            r['segs'].append([dt0, dt1, p0, p1])
            draws.append([dt0, dt1])

    def merge(ws):
        ws = sorted(ws); out = []
        for w in ws:
            if out and w[0] - out[-1][1] < 0.6:
                out[-1][1] = max(out[-1][1], w[1])
            else:
                out.append(list(w))
        return out
    hl_win = {k: merge(v) for k, v in hl_win.items()}
    lab_win = {k: merge(v) for k, v in lab_win.items()}

    # ---- sound events (all synthesised in audio.py; no third-party audio)
    ev = []
    for k in keys[1:]:
        if k['fly'] >= 0.9:
            ev.append(dict(kind='whoosh', t=k['fs'], dur=k['fly']))
        if k['move'] == 'cut':
            ev.append(dict(kind='pop', t=k['fs']))
    for c in cards:
        ev.append(dict(kind='pop', t=c['t0']))
        if c['spec'].get('kind') == 'stat':
            ev.append(dict(kind='count', t=c['t0'] + 0.15, dur=1.3))
    for st_ in stamps:
        ev.append(dict(kind='stamp', t=st_['t0'] + 0.1))
    for a, b_ in draws:
        ev.append(dict(kind='scratch', t=a, dur=b_ - a))
    firsts = sorted(w[0][0] for w in lab_win.values())
    for tt in firsts:
        ev.append(dict(kind='tick', t=tt))

    oy = {'16:9': 0.0, '9:16': -0.11, '1:1': -0.05, '4:5': -0.07}[aspect] * H
    return dict(id=s['id'], aspect=aspect, W=W, H=H, fps=s.get('fps', 30), end=end, body_end=body_end,
                beats=beats, keys=keys, routes=routes, hl=hl_win, labels=lab_win, headers=hdr, years=years,
                cards=cards, stamps=stamps, events=ev, oy=oy, style=s.get('style', 'light'),
                style_overrides=s.get('style_overrides', {}), captions=s.get('captions', True),
                map=dict({'borders': True, 'rivers': True, 'graticule': True}, **s.get('map', {})),
                sfx=s.get('sfx', 'synth'))


# ---------------------------------------------------------------- evaluate the plan at time t
def route_progress(r, t):
    p = 0.0
    for a, b, p0, p1 in r['segs']:
        if t >= b:
            p = p1
        elif t >= a:
            p = p0 + (p1 - p0) * ease((t - a) / (b - a)); break
        else:
            break
    return p


def route_point_at(r, p):
    cum = r['cum']; pts = r['pts']
    j = int(np.searchsorted(cum, p)); j = max(1, min(len(pts) - 1, j))
    return v2ll(np.array(pts[j]))


def _hold(k, tl, t, t_next):
    """a held shot is never static: constant-speed drift across about 16% of the view plus a slow push-in"""
    lat, lon, d, tilt = k['to']
    if k['move'] == 'follow' and k.get('route'):
        r = tl['routes'][k['route']]
        lat, lon = route_point_at(r, max(route_progress(r, t), 0.002))
    u = max(0.0, t - k['fs'] - k['fly'])               # seconds into the hold, linear so the camera never stops
    view = math.degrees(d * math.tan(math.radians(20)) * min(1.0, tl['W'] / tl['H']))   # half-width of the view, deg
    drift = k.get('drift', 1.0) * 0.045 * view * u      # ~4.5% of the half-view per second
    sgn = -1 if (k.get('i', 0) % 2) else 1             # alternate drift direction per beat
    return [lat + 0.25 * drift * sgn, lon + drift / max(0.3, math.cos(math.radians(lat))),
            d * max(0.6, 1 - k['push'] * min(1.0, u / 6.0)), tilt]


def camera(tl, t):
    keys = tl['keys']
    i = 0
    while i + 1 < len(keys) and keys[i + 1]['fs'] <= t:
        i += 1
    k = keys[i]
    t_next = keys[i + 1]['fs'] if i + 1 < len(keys) else tl['end']
    if t >= k['fs'] + k['fly']:
        return _hold(k, tl, t, t_next)
    # in flight from the previous state
    if k['frm'] is not None:
        a = k['frm']; b = k['to']; e = eout((t - k['fs']) / max(1e-6, k['fly']))
        e = ease(min(1, max(0, (t - k['fs']) / k['fly']))) * 0.35 + e * 0.65
    else:
        pk = keys[i - 1]
        a = _hold(pk, tl, k['fs'], k['fs'])
        b = list(k['to'])
        if k['move'] == 'follow' and k.get('route'):
            r = tl['routes'][k['route']]
            b[0], b[1] = route_point_at(r, max(route_progress(r, k['fs'] + k['fly']), 0.002))
        e = ease((t - k['fs']) / max(1e-6, k['fly']))
    pa, pb = ll2v(a[0], a[1]), ll2v(b[0], b[1])
    p = slerp(pa, pb, e)
    ang = angle(pa, pb)
    ld = math.log(a[2]) * (1 - e) + math.log(b[2]) * e + k['hop'] * ang * math.sin(math.pi * e)
    tilt = (a[3] * (1 - e) + b[3] * e) * (1 - 0.8 * math.sin(math.pi * e) * min(1, ang * 3))
    lat, lon = v2ll(p)
    return [lat, lon, math.exp(ld), tilt]


def window_alpha(ws, t, fin=0.4, fout=0.4):
    a = 0.0
    for w0, w1 in ws:
        if w0 - 0.01 <= t <= w1 + fout:
            a = max(a, min(1.0, (t - w0) / fin) * (1.0 if t <= w1 else 1 - (t - w1) / fout))
    return a
