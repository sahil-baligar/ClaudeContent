"""Export the design system as files: palettes (SVG), icons and route heads (SVG), card sprites (PNG),
type specimens (PNG) and one style frame per era style (PNG), all from the engine's own code.

usage:  python tools/make_design.py            (writes into design/)
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, os.path.join(ROOT, 'engine'))

from PIL import Image, ImageDraw
from mapstory import draw as D
from mapstory.styles import STYLES, Style
from mapstory import spec as SP
from mapstory.render import Renderer

OUT = os.path.join(ROOT, 'design')


def hexc(c):
    return '#%02x%02x%02x' % tuple(int(v) for v in c[:3])


def palettes():
    keys = ['paper', 'ink', 'accent', 'accent2', 'muted', 'land', 'sea', 'coast', 'hl_fill', 'bg']
    rows = []
    y = 40
    for name, st in STYLES.items():
        rows.append(f'<text x="24" y="{y + 30}" font-family="Oswald, sans-serif" font-size="22" fill="#222">{name}</text>')
        x = 150
        for k in keys + ['routes']:
            cols = st.get(k)
            if cols is None:
                continue
            for c in (cols if k == 'routes' else [cols]):
                rows.append(f'<rect x="{x}" y="{y}" width="64" height="44" rx="4" fill="{hexc(c)}" stroke="#0003"/>')
                rows.append(f'<text x="{x + 32}" y="{y + 60}" font-family="monospace" font-size="10" text-anchor="middle" fill="#444">{hexc(c)}</text>')
                rows.append(f'<text x="{x + 32}" y="{y + 72}" font-family="monospace" font-size="10" text-anchor="middle" fill="#888">{k}</text>')
                x += 72
        y += 100
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="1360" height="{y + 20}" viewBox="0 0 1360 {y + 20}">' \
          f'<rect width="100%" height="100%" fill="#fbf8f1"/>{"".join(rows)}</svg>'
    open(os.path.join(OUT, 'palettes.svg'), 'w', encoding='utf8').write(svg)


ICONS = {
    'city': '<circle cx="32" cy="32" r="13" fill="#f0e5ca"/><circle cx="32" cy="32" r="9" fill="#36241a"/>',
    'capital': '<circle cx="32" cy="32" r="13" fill="#f0e5ca"/><circle cx="32" cy="32" r="9" fill="#36241a"/><circle cx="32" cy="32" r="4" fill="#f0e5ca"/>',
    'battle': '<g stroke-linecap="round"><path d="M18 18 L46 46 M46 18 L18 46" stroke="#f0e5ca" stroke-width="10"/>'
              '<path d="M18 18 L46 46 M46 18 L18 46" stroke="#9a241a" stroke-width="5"/>'
              '<path d="M35 45 L45 35 M19 35 L29 45" stroke="#9a241a" stroke-width="4"/></g>',
    'port': '<g fill="none" stroke="#36241a" stroke-width="4" stroke-linecap="round"><circle cx="32" cy="16" r="5"/>'
            '<path d="M32 21 V52 M22 30 H42 M14 38 Q32 62 50 38"/></g>',
    'camp': '<path d="M12 48 L32 16 L52 48 Z" fill="#36241a" stroke="#f0e5ca" stroke-width="2"/><path d="M28 48 L32 34 L36 48 Z" fill="#f0e5ca"/>',
    'x': '<path d="M20 20 L44 44 M44 20 L20 44" stroke="#f0e5ca" stroke-width="12" stroke-linecap="round"/>'
         '<path d="M20 20 L44 44 M44 20 L20 44" stroke="#36241a" stroke-width="6" stroke-linecap="round"/>',
    'head-arrow': '<path d="M58 32 L14 54 L24 32 L14 10 Z" fill="#9c1e16" stroke="#140c08" stroke-width="2"/>',
    'head-army': '<path d="M58 32 L36 54 L18 54 L38 32 L18 10 L36 10 Z" fill="#b5762f" stroke="#140c08" stroke-width="2"/>',
    'head-ship': '<path d="M58 32 L46 42 L8 42 L4 32 L8 22 L46 22 Z" fill="#223e6c" stroke="#140c08" stroke-width="2"/>'
                 '<path d="M38 32 L28 48 L18 32 L28 16 Z" fill="#f5eedc"/>',
    'head-plane': '<path d="M60 32 L40 35 L33 58 L27 58 L31 36 L13 35 L9 44 L5 44 L7 32 L5 20 L9 20 L13 29 L31 28 L27 6 L33 6 L40 29 Z" '
                  'fill="#f5f0e6" stroke="#140c08" stroke-width="2"/>',
}


def icons():
    d = os.path.join(OUT, 'icons'); os.makedirs(d, exist_ok=True)
    for k, body in ICONS.items():
        open(os.path.join(d, f'{k}.svg'), 'w', encoding='utf8').write(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">{body}</svg>')


def cards():
    d = os.path.join(OUT, 'cards'); os.makedirs(d, exist_ok=True)
    demo = [
        ('stat', {'kind': 'stat', 'kicker': "Minard's count", 'value': 422000, 'label': 'soldiers cross into Russia'}),
        ('fact', {'kind': 'fact', 'kicker': '26-29 November 1812', 'title': "Eble's bridges", 'body': 'Pontoon engineers work in the icy river to build two bridges.'}),
        ('quote', {'kind': 'quote', 'quote': 'Short sentences. One idea per card.', 'by': 'the house rule'}),
        ('portrait', {'kind': 'portrait', 'name': 'Ferdinand Magellan', 'role': 'Captain-general'}),
    ]
    for sname in ('light', 'antique', 'atlas', 'warroom'):
        st = Style(sname)
        for kind, c in demo:
            D.card(st, 1.0, c).save(os.path.join(d, f'{sname}_{kind}.png'))
        D.stamp(st, 1.0, 'Moscow burns').save(os.path.join(d, f'{sname}_stamp.png'))


def type_specimens():
    for sname in ('light', 'antique', 'atlas', 'warroom', 'satellite'):
        st = Style(sname)
        W, H = 1200, 520
        bg = st.paper if sum(st.paper) > 300 else (18, 22, 26)
        im = Image.new('RGBA', (W, H), tuple(bg) + (255,)); d = ImageDraw.Draw(im)
        ink = st.ink if sum(st.paper) > 300 else (236, 240, 238)
        tf = D.font(st.title_font, 84) if st.title_font in ('Playfair', 'Fell') else D.font(st.title_font, 84, 600)
        D.spaced(d, (60, 90), 'THE MARCH ON MOSCOW', tf, D.rgba(ink), 3, 'l')
        D.spaced(d, (60, 170), f'TITLE / HEADER  -  {st.title_font}', D.font(st.ui_font, 26, 500), D.rgba(st.accent), 6, 'l')
        lf = D.font(st.label_font, 52) if st.label_font in ('Fell', 'Playfair') else D.font(st.label_font, 44, 600)
        D.spaced(d, (60, 260), 'Smolensk  Borodino  Vilna', lf, D.rgba(ink), 1, 'l')
        D.spaced(d, (60, 320), f'MAP LABELS  -  {st.label_font}', D.font(st.ui_font, 26, 500), D.rgba(st.accent), 6, 'l')
        cf = D.font('Oswald', 64, 650)
        d.text((60, 410), 'CAPTIONS ARE', font=cf, fill=D.rgba(st.cap_fg), anchor='lm', stroke_width=5, stroke_fill=D.rgba(st.cap_stroke))
        d.text((60 + d.textlength('CAPTIONS ARE ', font=cf), 410), 'OSWALD', font=cf, fill=D.rgba(st.cap_hl), anchor='lm',
               stroke_width=5, stroke_fill=D.rgba(st.cap_stroke))
        D.spaced(d, (60, 470), 'HAND NOTES  -  Caveat', D.font(st.ui_font, 26, 500), D.rgba(st.accent), 6, 'l')
        d.text((520, 470), '7 Sept 1812', font=D.font('Caveat', 44, 600), fill=D.rgba(st.accent), anchor='lm')
        im.convert('RGB').save(os.path.join(OUT, f'type_{sname}.png'))


def style_frames():
    d = os.path.join(OUT, 'styles'); os.makedirs(d, exist_ok=True)
    base = {
        'id': 'styleframe', 'title': 'Style frame', 'captions': True, 'map': {'borders': False},
        'voice': {'engine': 'none'},
        'places': {'a': {'name': 'Kovno', 'lat': 54.9, 'lon': 23.9}, 'b': {'name': 'Smolensk', 'lat': 54.78, 'lon': 32.05, 'kind': 'battle'},
                   'c': {'name': 'Moscow', 'lat': 55.76, 'lon': 37.62, 'kind': 'capital'}},
        'routes': {'r': {'path': ['a', 'b', 'c'], 'width': [24, 9], 'head': 'army'}},
        'beats': [
            {'vo': 'one two three four five six', 'camera': {'to': [50, 20], 'zoom': 'globe'}},
            {'vo': 'The army marches east toward Moscow, one town at a time.', 'camera': {'to': ['a', 'c'], 'tilt': 30},
             'year': 1812, 'header': {'kicker': 'Summer 1812', 'title': 'The road east'}, 'labels': ['a', 'b', 'c'],
             'draw': [{'route': 'r', 'to': 0.8}], 'highlight': ['Belarus'],
             'card': {'kind': 'stat', 'kicker': 'Example', 'value': 422000, 'label': 'soldiers', 'at': 0.1}},
            {'vo': 'three four five six', 'camera': {'to': 'c', 'zoom': 'region'}},
        ]}
    for sname in ('light', 'antique', 'atlas', 'warroom', 'satellite'):
        for aspect in ('16:9', '9:16'):
            s = dict(base, style=sname, _dir=ROOT)
            vo = [dict(path=None, dur=len(b['vo'].split()) / 2.7, speech=[0, len(b['vo'].split()) / 2.7]) for b in s['beats']]
            tl = SP.build(s, aspect, vo)
            r = Renderer(s, tl)
            b1 = tl['beats'][1]
            t = b1['end'] - 0.5
            Image.fromarray(r.frame(t)).save(os.path.join(d, f'{r.st.name}_{aspect.replace(":", "x")}.png'))
            if aspect == '16:9':
                Image.fromarray(r.frame(1.6)).save(os.path.join(d, f'{r.st.name}_title.png'))
            print('style frame', sname, aspect)


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    palettes(); icons(); cards(); type_specimens(); style_frames()
    print('design exported to', os.path.abspath(OUT))
