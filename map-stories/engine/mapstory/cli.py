"""Command line.

  python -m mapstory validate stories/napoleon-1812.json
  python -m mapstory stills   stories/napoleon-1812.json --aspect 16:9 --times 1,6,12      # quick look, PNGs
  python -m mapstory render   stories/napoleon-1812.json --aspect 16:9,9:16 --workers 6
  python -m mapstory batch    stories/ --aspect 9:16                                       # every *.json in a folder
  python -m mapstory countries                                                             # valid highlight names
Run from map-stories/engine (or put it on PYTHONPATH). Output: <out>/<id>/<id>_16x9.mp4 (+ cover, contact sheet).
"""
import argparse, glob, json, math, os, shutil, subprocess, sys, time

import numpy as np

from . import spec as SP
from . import audio as AU

ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _plan(spec, aspect, work, draft=False):
    vo = AU.prepare_vo(spec, work)
    tl = SP.build(spec, aspect, vo)
    if draft:
        tl['W'] //= 2; tl['H'] //= 2; tl['oy'] /= 2
    return tl


def _save_tl(tl, path):
    with open(path, 'w', encoding='utf8') as f:
        json.dump(tl, f)


def cmd_validate(a):
    for p in a.specs:
        s = SP.load(p)
        from .world import World
        w = World(); names = set(w.names)
        bad = [h for b in s['beats'] for h in b.get('highlight', []) if h not in names and h not in s.get('areas', {})]
        if bad:
            raise SystemExit(f'{p}: unknown highlight(s) {sorted(set(bad))}; see `python -m mapstory countries`')
        n_words = sum(len(b.get('vo', '').split()) for b in s['beats'])
        print(f'ok  {p}: {len(s["beats"])} beats, {n_words} words (~{n_words / 2.7:.0f} s of narration)')


def cmd_countries(a):
    from .world import World
    print('\n'.join(World().country_names()))


def cmd_stills(a):
    from .render import Renderer
    from PIL import Image
    s = SP.load(a.spec)
    out = os.path.join(a.out, s['id']); work = os.path.join(out, 'work'); os.makedirs(work, exist_ok=True)
    for aspect in a.aspect.split(','):
        tl = _plan(s, aspect, work, a.draft)
        r = Renderer(s, tl)
        times = [float(x) for x in a.times.split(',')] if a.times else list(np.linspace(0.5, tl['end'] - 0.6, 12))
        for t in times:
            fn = os.path.join(out, f'still_{aspect.replace(":", "x")}_{t:06.2f}.png')
            Image.fromarray(r.frame(t)).save(fn); print(fn)
        print(f'duration {tl["end"]:.1f} s')


def cmd_part(a):
    """internal: render frames [k/N] of a saved timeline to an mp4"""
    from .render import Renderer
    s = SP.load(a.spec)
    with open(a.timeline, encoding='utf8') as f:
        tl = json.load(f)
    r = Renderer(s, tl)
    N = int(round(tl['end'] * tl['fps'])); per = math.ceil(N / a.parts)
    f0, f1 = a.part * per, min(N, (a.part + 1) * per)
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{tl["W"]}x{tl["H"]}',
                          '-r', str(tl['fps']), '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', str(a.crf),
                          '-pix_fmt', 'yuv420p', a.dst], stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(f0, f1):
        p.stdin.write(r.frame(i / tl['fps']).tobytes())
        if (i - f0) % 30 == 0:
            el = time.time() - t0; done = i - f0 + 1
            print(f'part {a.part}: {done}/{f1 - f0}  {el / done:.2f} s/frame', flush=True)
    p.stdin.close(); p.wait()


def render_one(s, spec_path, aspect, a):
    out = os.path.join(a.out, s['id']); work = os.path.join(out, 'work'); os.makedirs(work, exist_ok=True)
    tag = aspect.replace(':', 'x')
    tl = _plan(s, aspect, work, a.draft)
    tlp = os.path.join(work, f'timeline_{tag}.json'); _save_tl(tl, tlp)
    from .world import World
    w = World(); w.land_mips(); w.coast_distance()     # build the map caches once, before the workers start
    print(f'[{s["id"]} {aspect}] {tl["end"]:.1f} s, {len(tl["beats"])} beats, {a.workers} workers', flush=True)
    parts = []
    procs = []
    env = dict(os.environ, PYTHONPATH=ENGINE + os.pathsep + os.environ.get('PYTHONPATH', ''),
               OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2')
    for k in range(a.workers):
        dst = os.path.join(work, f'part_{tag}_{k}.mp4'); parts.append(dst)
        log = open(os.path.join(work, f'part_{tag}_{k}.log'), 'w')
        procs.append(subprocess.Popen([sys.executable, '-m', 'mapstory', '_part', spec_path, tlp, str(k), str(a.workers), dst,
                                       '--crf', str(a.crf)], env=env, stdout=log, stderr=subprocess.STDOUT, cwd=ENGINE))
    for p in procs:
        if p.wait() != 0:
            raise SystemExit(f'a render worker failed; see {work}/part_{tag}_*.log')
    lst = os.path.join(work, f'parts_{tag}.txt')
    with open(lst, 'w') as f:
        f.write(''.join(f"file '{os.path.abspath(p)}'\n" for p in parts))
    silent = os.path.join(work, f'video_{tag}.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', silent], check=True)
    wav = os.path.join(work, f'mix_{tag}.wav')
    AU.mix(s, tl, wav)
    final = os.path.join(out, f'{s["id"]}_{tag}.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', silent, '-i', wav, '-map', '0:v', '-map', '1:a', '-c:v', 'copy',
                    '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-ar', '48000', '-c:a', 'aac', '-b:a', '192k', '-shortest',
                    '-movflags', '+faststart', final], check=True)
    # cover (end of the title) + contact sheet
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', '2.0', '-i', final, '-frames:v', '1', '-q:v', '2',
                    os.path.join(out, f'{s["id"]}_{tag}_cover.jpg')], check=True)
    cols = 6 if aspect == '9:16' else 4
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', final, '-vf',
                    f'fps={24 / tl["end"]:.5f},scale={360 if aspect == "9:16" else 480}:-1,tile={cols}x{math.ceil(24 / cols)}',
                    '-frames:v', '1', '-q:v', '3', os.path.join(out, f'{s["id"]}_{tag}_contact.jpg')], check=True)
    print('->', final, flush=True)
    return final


def cmd_render(a):
    for sp in a.specs:
        s = SP.load(sp)
        aspects = a.aspect.split(',') if a.aspect else s.get('aspects', ['16:9'])
        for asp in aspects:
            render_one(s, os.path.abspath(sp), asp, a)


def cmd_batch(a):
    specs = sorted(glob.glob(os.path.join(a.folder, '*.json')))
    done = []
    for sp in specs:
        try:
            s = SP.load(sp)
        except Exception as e:
            print(f'skip {sp}: {e}'); continue
        aspects = a.aspect.split(',') if a.aspect else s.get('aspects', ['16:9'])
        for asp in aspects:
            if os.path.exists(os.path.join(a.out, s['id'], f'{s["id"]}_{asp.replace(":", "x")}.mp4')) and not a.force:
                print('have', s['id'], asp); continue
            done.append(render_one(s, os.path.abspath(sp), asp, a))
    print(f'{len(done)} videos rendered')


def main(argv=None):
    ap = argparse.ArgumentParser(prog='mapstory', description='map-animation story videos from a JSON story spec')
    sub = ap.add_subparsers(dest='cmd', required=True)
    def common(p):
        p.add_argument('--out', default=os.path.join(ENGINE, '..', 'out'))
        p.add_argument('--draft', action='store_true', help='half resolution, for quick looks')
    p = sub.add_parser('validate'); p.add_argument('specs', nargs='+'); p.set_defaults(fn=cmd_validate)
    p = sub.add_parser('countries'); p.set_defaults(fn=cmd_countries)
    p = sub.add_parser('stills'); p.add_argument('spec'); p.add_argument('--aspect', default='16:9'); p.add_argument('--times', default='')
    common(p); p.set_defaults(fn=cmd_stills)
    for name, fn in (('render', cmd_render), ('batch', cmd_batch)):
        p = sub.add_parser(name)
        if name == 'render':
            p.add_argument('specs', nargs='+')
        else:
            p.add_argument('folder'); p.add_argument('--force', action='store_true')
        p.add_argument('--aspect', default='', help='16:9, 9:16, 1:1, 4:5 (comma list); default: the spec\'s "aspects"')
        p.add_argument('--workers', type=int, default=max(1, min(6, (os.cpu_count() or 2) // 2)), help='parallel render processes (~1-1.5 GB RAM each)')
        p.add_argument('--crf', type=int, default=20)
        common(p); p.set_defaults(fn=fn)
    p = sub.add_parser('_part'); p.add_argument('spec'); p.add_argument('timeline'); p.add_argument('part', type=int)
    p.add_argument('parts', type=int); p.add_argument('dst'); p.add_argument('--crf', type=int, default=20); p.set_defaults(fn=cmd_part)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == '__main__':
    main()
