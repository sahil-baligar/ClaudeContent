"""Build engine/data/world.npz from Natural Earth GeoJSON (public domain): countries, big lakes, rivers.

usage:
  python tools/fetch_data.py                 # downloads the Natural Earth GeoJSON files into engine/data/cache/
  python tools/build_world.py                # -> engine/data/world.npz (country rings, big lakes, rivers; decimated)
  python tools/build_world.py --countries X.geojson --lakes Y.geojson --tol 0.03

The npz holds float32 [lon, lat] rings, one entry per polygon outer ring, with the
Natural Earth ADMIN name of its country, plus the outer rings of large lakes
(scalerank <= 3) and rivers (scalerank <= 6). It is the only geo data the engine needs for the vector styles.
"""
import argparse, json, os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'engine', 'data')


def decimate(ring, tol):
    out = [ring[0]]
    for p in ring[1:]:
        if abs(p[0] - out[-1][0]) + abs(p[1] - out[-1][1]) >= tol:
            out.append(p)
    if out[-1] != ring[-1]:
        out.append(ring[-1])
    return out


def outer_rings(geom):
    polys = [geom['coordinates']] if geom['type'] == 'Polygon' else geom['coordinates']
    return [p[0] for p in polys]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--countries', default=os.path.join(DATA, 'cache', 'ne_10m_admin_0_countries.geojson'))
    ap.add_argument('--lakes', default=os.path.join(DATA, 'cache', 'ne_10m_lakes.geojson'))
    ap.add_argument('--rivers', default=os.path.join(DATA, 'cache', 'ne_10m_rivers_lake_centerlines.geojson'))
    ap.add_argument('--tol', type=float, default=0.03, help='decimation tolerance in degrees (L1)')
    ap.add_argument('--out', default=os.path.join(DATA, 'world.npz'))
    a = ap.parse_args()

    rings, names, iso = [], [], []
    for f in json.load(open(a.countries, encoding='utf8'))['features']:
        p = f['properties']
        for r in outer_rings(f['geometry']):
            if len(r) < 6:
                continue
            r = decimate(r, a.tol)
            if len(r) >= 4:
                rings.append(np.array(r, np.float32)); names.append(p['ADMIN']); iso.append(p.get('ADM0_A3', ''))
    lakes = []
    if os.path.exists(a.lakes):
        for f in json.load(open(a.lakes, encoding='utf8'))['features']:
            if (f['properties'].get('scalerank') or 9) > 3:
                continue
            for r in outer_rings(f['geometry']):
                r = decimate(r, a.tol)
                if len(r) >= 4:
                    lakes.append(np.array(r, np.float32))
    rivers = []
    if os.path.exists(a.rivers):
        for f in json.load(open(a.rivers, encoding='utf8'))['features']:
            g = f['geometry']
            if g is None or (f['properties'].get('scalerank') or 9) > 6:
                continue
            lines = [g['coordinates']] if g['type'] == 'LineString' else g['coordinates']
            for ln in lines:
                ln = decimate(ln, a.tol)
                if len(ln) >= 2:
                    rivers.append(np.array([p[:2] for p in ln], np.float32))
    rlens = np.array([len(r) for r in rivers], np.int32)
    lens = np.array([len(r) for r in rings], np.int32)
    llens = np.array([len(r) for r in lakes], np.int32)
    np.savez_compressed(a.out, pts=np.concatenate(rings), lens=lens, names=np.array(names), iso=np.array(iso),
                        lake_pts=np.concatenate(lakes) if lakes else np.zeros((0, 2), np.float32), lake_lens=llens,
                        river_pts=np.concatenate(rivers) if rivers else np.zeros((0, 2), np.float32), river_lens=rlens)
    print(f'{len(rings)} country rings ({lens.sum()} pts), {len(lakes)} lake rings, {len(rivers)} rivers -> {a.out} '
          f'({os.path.getsize(a.out) / 1e6:.1f} MB)')


if __name__ == '__main__':
    main()
