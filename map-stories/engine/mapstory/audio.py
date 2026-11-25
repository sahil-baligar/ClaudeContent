"""Narration hook, synthesised sound effects and the final mix.

Voice engines (spec "voice.engine"):
  piper  local Piper TTS (pip install piper-tts). voice.model = a .onnx path, or a bare voice name found in
         MAPSTORY_VOICES or engine/voices/ (or set MAPSTORY_PIPER_MODEL)
  kokoro local Kokoro-82M TTS (pip install kokoro-onnx; Apache-2.0 weights). voice.model = folder holding
         kokoro-v1.0.onnx + voices-v1.0.bin (or MAPSTORY_VOICES); voice.speaker = a Kokoro voice, e.g. "am_fenrir"
  command  bring your own voice: any TTS or voice clone. voice.command = a shell command with {text} and {out}
         placeholders that writes a wav, e.g. "mytts --text {text} --out {out}"
  files  your own recordings: beat["audio"] = path to a wav/mp3 per beat
  none   silent; beats are timed at ~2.7 words/s (captions still run)
Music (spec "music"): optional {path, gain_db, credit}; ducked under the voice. Default: none.
Sound effects (spec "sfx"):
  "synth"            generated here from noise and sine waves (no third-party audio); the default
  false              no effects, voice only
  {"dir": "path"}    your own licensed samples, picked by name: whoosh*, pop*, tick*, stamp*, scratch*, count*
                     (any kind without a file falls back to silence)
"""
import hashlib, json, math, os, subprocess, wave
import numpy as np

SR = 48000


def _read_wav(path):
    with wave.open(path) as w:
        n, ch, sr = w.getnframes(), w.getnchannels(), w.getframerate()
        a = np.frombuffer(w.readframes(n), np.int16).astype(np.float32) / 32768
    a = a.reshape(-1, ch).mean(1)
    return a, sr


def _decode(path, sr=SR, mono=True):
    """any audio file -> float32 at sr via ffmpeg"""
    cmd = ['ffmpeg', '-v', 'error', '-i', path, '-f', 's16le', '-ac', '1' if mono else '2', '-ar', str(sr), '-']
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    return a if mono else a.reshape(-1, 2)


def write_wav(path, a, sr=SR):
    a = np.clip(a, -1, 1)
    if a.ndim == 1:
        a = a[:, None]
    with wave.open(path, 'wb') as w:
        w.setnchannels(a.shape[1]); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((a * 32767).astype(np.int16).tobytes())


def speech_span(a, sr):
    env = np.sqrt(np.convolve(a * a, np.ones(int(sr * 0.02)) / int(sr * 0.02), 'same'))
    on = np.flatnonzero(env > max(0.01, env.max() * 0.06))
    if not len(on):
        return [0.0, len(a) / sr]
    return [on[0] / sr, on[-1] / sr]


_PIPER = {}
_WARNED = []


def piper_tts(text, out, model, speaker=None, speed=1.0):
    from piper import PiperVoice, SynthesisConfig
    if model not in _PIPER:
        _PIPER[model] = PiperVoice.load(model)
    cfg = SynthesisConfig(speaker_id=speaker, length_scale=1.0 / max(0.5, speed))
    tmp = out + '.22k.wav'
    with wave.open(tmp, 'wb') as w:
        _PIPER[model].synthesize_wav(text, w, syn_config=cfg)
    a = _decode(tmp)            # resample to 48 kHz
    os.remove(tmp)
    write_wav(out, a)


_KOKORO = {}


def kokoro_tts(text, out, v):
    try:
        from kokoro_onnx import Kokoro
    except ImportError:
        return False
    d = v.get('model') or os.environ.get('MAPSTORY_VOICES') or os.path.join(os.path.dirname(__file__), '..', 'voices')
    onnx, bins = os.path.join(d, 'kokoro-v1.0.onnx'), os.path.join(d, 'voices-v1.0.bin')
    if not (os.path.exists(onnx) and os.path.exists(bins)):
        return False
    if d not in _KOKORO:
        _KOKORO[d] = Kokoro(onnx, bins)
    sp = v.get('speaker') or 'am_fenrir'
    a, sr = _KOKORO[d].create(text, voice=sp, speed=float(v.get('speed', 1.0)), lang='en-gb' if sp.startswith('b') else 'en-us')
    tmp = out + '.raw.wav'; write_wav(tmp, np.asarray(a, np.float32), sr)
    write_wav(out, _decode(tmp)); os.remove(tmp)
    return True


def command_tts(text, out, v):
    cmd = v.get('command')
    if not cmd:
        return False
    import shlex
    tmp = out + '.cmd.wav'
    args = [x.replace('{text}', text).replace('{out}', tmp) for x in shlex.split(cmd, posix=os.name != 'nt')]
    subprocess.run(args, check=True)          # no shell: the narration text is passed as one argument
    write_wav(out, _decode(tmp)); os.remove(tmp)
    return True


def prepare_vo(spec, work):
    """-> one dict per beat: {path, dur, speech}"""
    v = spec.get('voice', {'engine': 'none'})
    eng = v.get('engine', 'none')
    os.makedirs(os.path.join(work, 'vo'), exist_ok=True)
    out = []
    for i, b in enumerate(spec['beats']):
        text = b.get('vo', '').strip()
        if not text:
            out.append(dict(path=None, dur=0.0, speech=[0, 0])); continue
        if eng == 'none':
            d = len(text.split()) / 2.7 + 0.3
            out.append(dict(path=None, dur=d, speech=[0.1, d - 0.1])); continue
        if eng == 'files':
            src = b.get('audio')
            if not src:
                raise ValueError(f'beat {i + 1}: voice.engine=files needs beat.audio')
            src = src if os.path.isabs(src) else os.path.join(spec['_dir'], src)
            path = os.path.join(work, 'vo', f'b{i + 1:02d}.wav')
            write_wav(path, _decode(src))
        elif eng in ('kokoro', 'command'):
            h = hashlib.sha1(json.dumps([eng, text, v.get('speaker'), v.get('speed', 1.0), v.get('command')]).encode()).hexdigest()[:10]
            path = os.path.join(work, 'vo', f'b{i + 1:02d}_{h}.wav')
            if not os.path.exists(path):
                ok = (kokoro_tts if eng == 'kokoro' else command_tts)(text, path, v)
                if not ok:
                    if not _WARNED:
                        print(f'[mapstory] voice engine "{eng}" unavailable (see README "Narration"); timing the video silently instead')
                        _WARNED.append(1)
                    d = len(text.split()) / 2.7 + 0.3
                    out.append(dict(path=None, dur=d, speech=[0.1, d - 0.1])); continue
        elif eng == 'piper':
            model = v.get('model') or os.environ.get('MAPSTORY_PIPER_MODEL') or ''
            try:
                import piper  # noqa: F401
                have_piper = True
            except ImportError:
                have_piper = False
            if model and not os.path.exists(model):   # a bare voice name: look in MAPSTORY_VOICES or engine/voices
                for d in (os.environ.get('MAPSTORY_VOICES', ''), os.path.join(os.path.dirname(__file__), '..', 'voices')):
                    if d and os.path.exists(os.path.join(d, os.path.basename(model))):
                        model = os.path.join(d, os.path.basename(model)); break
            # cache key uses the voice file NAME, so a VO folder rendered on one machine is reused on another
            h = hashlib.sha1(json.dumps([text, os.path.basename(model) or 'default', v.get('speaker'), v.get('speed', 1.0)]).encode()).hexdigest()[:10]
            path = os.path.join(work, 'vo', f'b{i + 1:02d}_{h}.wav')
            if not os.path.exists(path):
                if not have_piper or not model or not os.path.exists(model):
                    if not _WARNED:
                        print('[mapstory] no Piper voice found (pip install piper-tts, and put the voice .onnx in engine/voices/ '
                              'or set MAPSTORY_VOICES); timing the video silently instead')
                        _WARNED.append(1)
                    d = len(text.split()) / 2.7 + 0.3
                    out.append(dict(path=None, dur=d, speech=[0.1, d - 0.1])); continue
                piper_tts(text, path, model, v.get('speaker'), v.get('speed', 1.0))
        else:
            raise ValueError(f'unknown voice.engine "{eng}"')
        a, sr = _read_wav(path)
        out.append(dict(path=path, dur=len(a) / sr, speech=speech_span(a, sr)))
    return out


# ---------------------------------------------------------------- synthesised effects
def _biquad_bp(x, f0s, q=1.2, sr=SR):
    """band-pass with a time-varying centre frequency (per-sample array f0s)"""
    y = np.zeros_like(x); x1 = x2 = y1 = y2 = 0.0
    step = 64
    for i0 in range(0, len(x), step):
        w0 = 2 * math.pi * float(f0s[i0]) / sr; al = math.sin(w0) / (2 * q); cw = math.cos(w0)
        b0, b2 = al, -al; a0, a1, a2 = 1 + al, -2 * cw, 1 - al
        b0, b2, a1, a2 = b0 / a0, b2 / a0, a1 / a0, a2 / a0
        for i in range(i0, min(len(x), i0 + step)):
            xi = x[i]; yi = b0 * xi + b2 * x2 - a1 * y1 - a2 * y2
            x2, x1, y2, y1 = x1, xi, y1, yi; y[i] = yi
    return y


def sfx(kind, dur=0.5, seed=0):
    rg = np.random.default_rng(seed)
    if kind == 'whoosh':
        n = int(SR * max(0.4, dur)); t = np.linspace(0, 1, n)
        f0 = 250 + 1500 * np.sin(np.pi * t) ** 1.5
        y = _biquad_bp(rg.normal(0, 1, n).astype(np.float32), f0, 0.9)
        env = np.sin(np.pi * t ** 0.8) ** 2
        return (y * env / (np.abs(y).max() + 1e-6) * 0.5).astype(np.float32)
    if kind == 'pop':
        n = int(SR * 0.09); t = np.arange(n) / SR
        f = 820 * np.exp(-t * 18) + 380
        y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 40)
        y[:40] += rg.normal(0, 0.3, 40)
        return (y * 0.5).astype(np.float32)
    if kind == 'tick':
        n = int(SR * 0.03); t = np.arange(n) / SR
        return (np.sin(2 * np.pi * 2300 * t) * np.exp(-t * 160) * 0.35).astype(np.float32)
    if kind == 'stamp':
        n = int(SR * 0.35); t = np.arange(n) / SR
        thud = np.sin(2 * np.pi * (70 + 60 * np.exp(-t * 30)) * t) * np.exp(-t * 14)
        nz = rg.normal(0, 1, n) * np.exp(-t * 60)
        nz = np.convolve(nz, np.ones(12) / 12, 'same')
        return ((thud * 0.9 + nz * 1.4) * 0.8).astype(np.float32)
    if kind == 'scratch':
        n = int(SR * max(0.3, dur)); t = np.arange(n) / SR
        y = _biquad_bp(rg.normal(0, 1, n).astype(np.float32), np.full(n, 3200.0), 1.5)
        strokes = 0.5 + 0.5 * np.sin(2 * np.pi * (6.5 + rg.random()) * t + rg.random() * 6) ** 2
        env = np.minimum(1, t / 0.08) * np.minimum(1, (t[-1] - t) / 0.15)
        return (y / (np.abs(y).max() + 1e-6) * strokes * env * 0.18).astype(np.float32)
    if kind == 'count':
        n = int(SR * dur); y = np.zeros(n, np.float32); tk = sfx('tick')
        tt = 0.0; gap = 0.045
        while tt < dur - 0.05:
            i = int(tt * SR); y[i:i + len(tk)] += tk[:max(0, min(len(tk), n - i))] * 0.7
            tt += gap; gap *= 1.09
        return y
    raise ValueError(kind)


GAIN = {'whoosh': 0.32, 'pop': 0.22, 'tick': 0.16, 'stamp': 0.5, 'scratch': 0.5, 'count': 0.22}


def mix(spec, tl, out_wav):
    n = int(SR * tl['end']) + SR
    vo = np.zeros(n, np.float32); fx = np.zeros(n, np.float32)
    for b in tl['beats']:
        if b.get('vo_path'):
            a, sr = _read_wav(b['vo_path'])
            a = a / (np.abs(a).max() + 1e-6) * 0.7
            t0, t1 = b.get('vo_trim', [0, len(a) / sr])
            a = a[int(t0 * sr):int(t1 * sr)].copy()
            f = min(len(a), int(0.01 * sr)); a[:f] *= np.linspace(0, 1, f); a[len(a) - f:] *= np.linspace(1, 0, f)
            i = int((b['vo_start'] + t0) * SR); vo[i:i + len(a)] += a[:max(0, min(len(a), n - i))]
    mode = tl.get('sfx', 'synth')
    samples = {}
    if isinstance(mode, dict) and mode.get('dir'):
        d = mode['dir'] if os.path.isabs(mode['dir']) else os.path.join(spec['_dir'], mode['dir'])
        for fn in sorted(os.listdir(d)):
            for kind in GAIN:
                if fn.lower().startswith(kind) and kind not in samples:
                    samples[kind] = _decode(os.path.join(d, fn))
    for k, e in enumerate(tl['events'] if mode else []):
        if isinstance(mode, dict):
            y = samples.get(e['kind'])
            if y is None:
                continue
            y = y[:int(SR * max(0.3, e.get('dur', 0.5) + 0.3))] * GAIN[e['kind']] * 1.5
        else:
            y = sfx(e['kind'], e.get('dur', 0.5), seed=k) * GAIN[e['kind']]
        i = int(max(0, e['t']) * SR); fx[i:i + len(y)] += y[:max(0, min(len(y), n - i))]
    out = vo + fx
    m = spec.get('music')
    if m and m.get('path'):
        p = m['path'] if os.path.isabs(m['path']) else os.path.join(spec['_dir'], m['path'])
        mu = _decode(p)
        reps = int(math.ceil(n / max(1, len(mu))))
        mu = np.tile(mu, reps)[:n] * (10 ** (m.get('gain_db', -18) / 20))
        env = np.sqrt(np.convolve(vo * vo, np.ones(SR // 10) / (SR // 10), 'same'))
        duck = 1 - 0.6 * np.clip(env / 0.05, 0, 1)
        duck = np.convolve(duck, np.ones(SR // 5) / (SR // 5), 'same')
        fade = np.minimum(1, np.arange(n) / SR / 1.0) * np.clip((tl['end'] - np.arange(n) / SR) / 2.0, 0, 1)
        out += mu * duck * fade
    write_wav(out_wav, np.stack([out, out], 1))
