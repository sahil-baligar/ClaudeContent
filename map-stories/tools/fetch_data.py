"""Download the free map data the engine can use. Nothing here needs an account or a key.

usage:
  python tools/fetch_data.py               # Natural Earth countries + lakes + rivers (GeoJSON, ~25 MB) -> engine/data/cache/
  python tools/fetch_data.py --bluemarble  # also NASA Blue Marble NG (Dec 2004, topo+bathy) for style "satellite"
  python tools/fetch_data.py --bluemarble --small   # the 5400 px Blue Marble instead of 21600 px

Sources (both public domain):
  Natural Earth  https://www.naturalearthdata.com/  (GeoJSON mirror: github.com/nvkelso/natural-earth-vector)
  NASA Blue Marble Next Generation  https://visibleearth.nasa.gov/collection/1484/blue-marble
The repo already ships engine/data/world.npz (built from Natural Earth), so the vector styles
work offline; you only need this script to rebuild it at another detail level or to get the satellite look.
"""
import argparse, os, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, '..', 'engine', 'data', 'cache')
NE = 'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/'
BM = 'https://eoimages.gsfc.nasa.gov/images/imagerecords/74000/74443/'


def get(url, dst):
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        print('have', dst); return
    print('get ', url)
    req = urllib.request.Request(url, headers={'User-Agent': 'map-stories-fetch/1.0'})
    with urllib.request.urlopen(req) as r, open(dst + '.part', 'wb') as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
    os.replace(dst + '.part', dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bluemarble', action='store_true')
    ap.add_argument('--small', action='store_true')
    a = ap.parse_args()
    os.makedirs(CACHE, exist_ok=True)
    for n in ('ne_10m_admin_0_countries.geojson', 'ne_10m_lakes.geojson', 'ne_10m_rivers_lake_centerlines.geojson'):
        get(NE + n, os.path.join(CACHE, n))
    if a.bluemarble:
        n = 'world.topo.bathy.200412.3x5400x2700.jpg' if a.small else 'world.topo.bathy.200412.3x21600x10800.jpg'
        get(BM + n, os.path.join(CACHE, 'bluemarble.jpg'))
        print('satellite style will use', os.path.join(CACHE, 'bluemarble.jpg'), '(or set MAPSTORY_BLUEMARBLE)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
