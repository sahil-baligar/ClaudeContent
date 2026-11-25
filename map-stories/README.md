# Map stories

Zoom-in / zoom-out map animations that tell a historic story: one continuous camera flies around a globe,
draws the route, drops place labels, flips the year and slams stamps and info cards, while a narrator
tells the story. One JSON file in, a finished 16:9 and 9:16 video out.

Part of the [ClaudeContent](../README.md) open content factory. Use it here, or for free at [rrender.ai](https://rrender.ai).

| Example | |
|---|---|
| `examples/napoleon-1812_16x9.mp4` | *The March on Moscow*, Napoleon 1812, told through Minard's 1869 chart (default light style, Kokoro voice, no music) |
| `examples/napoleon-1812_9x16.mp4` | the same story for Shorts / Reels / TikTok |
| `examples/*_contact.jpg` | contact sheets |
| `stories/magellan-1519.json`, `stories/berlin-airlift-1948.json` | two more specs (antique, warroom); render them yourself |
| `design/styles/` | the same frame in all four era styles |

## Quick start

```bash
pip install -r requirements.txt          # numpy, opencv-python, Pillow (+ kokoro-onnx for narration); ffmpeg on PATH
cd engine
python -m mapstory validate ../stories/napoleon-1812.json
python -m mapstory stills   ../stories/napoleon-1812.json --aspect 16:9 --draft     # 12 preview PNGs in ../out/
# without a voice installed the engine says so and times the video silently
python -m mapstory render   ../stories/napoleon-1812.json --aspect 16:9,9:16 --workers 6
```

**Narration.** The examples use Kokoro-82M (Apache-2.0 weights), a free local voice:
```bash
pip install kokoro-onnx
mkdir voices && cd voices   # inside engine/
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```
Then set `"voice": {"engine": "kokoro", "speaker": "am_fenrir"}`. Engines:

| engine | use |
|---|---|
| `kokoro` | the default open voice (any Kokoro voice name in `speaker`) |
| `piper` | Piper TTS (`pip install piper-tts`, a voice `.onnx` in `engine/voices/`) |
| `command` | **bring your own voice**: any TTS, cloud API or voice clone you are allowed to use. `"command": "mytts --text {text} --out {out}"` runs once per beat and must write a wav |
| `files` | your own recordings, `"audio": "vo/beat01.wav"` on each beat |
| `none` | silent, timed at 2.7 words a second |

If the chosen voice isn't installed, the engine says so and times the video silently. TTS padding is trimmed,
so lines follow each other with about 0.4 s of air.

**Sound effects.** `"sfx": "synth"` (default) uses the built-in generated whoosh/pop/stamp/pen/tick set,
`"sfx": false` is voice only (the example), and `"sfx": {"dir": "my_sfx"}` plays your own licensed samples
named `whoosh*`, `pop*`, `tick*`, `stamp*`, `scratch*`, `count*`. There is no music unless you add a `music` track.

**Satellite style** (optional): `python tools/fetch_data.py --bluemarble` (NASA Blue Marble, public domain).
The other three styles work offline with the shipped Natural Earth data.

## Built-in rules (you get these for free)

- **No still holds.** Between flights, every shot keeps moving: a constant-speed drift (`camera.drift`, default 1.0)
  plus a slow push-in (`camera.push`, default 0.08). Labelled places pulse, labels fade in staggered, and routes draw across the beat.
- **Phone-safe type.** On portrait frames (9:16, 4:5), captions, header titles and map labels are scaled to a cap height of
  at least 3.5% of the frame height (67 px at 1080x1920). A long name or caption chunk shrinks only as far as it needs to fit.
  Labels that would overlap flip side or move down.
- **Tight narration.** TTS padding is trimmed, leaving about 0.4 s between lines. No music by default.

## What's inside

```
map-stories/
  PLAYBOOK.md            the step-by-step outline an agent follows: topic -> story -> beats -> places -> camera -> overlays -> spec -> render -> check
  schema/story.schema.json   the input format for one video
  stories/               example specs (copy one to start)
  topics/topics.csv      40 topics ready for mass production (hooks are leads; verify them)
  engine/mapstory/       the renderer (pure Python: numpy, OpenCV, Pillow, ffmpeg)
    geo.py               sphere math, great-circle routes, perspective globe camera, framing
    world.py             Natural Earth masks, per-pixel ray cast, crisp coastlines at any zoom
    styles.py            map styles: light (default), antique, atlas, dark/warroom, satellite; the map base
    draw.py              labels, icons, header, year counter, cards, stamps, captions, route heads, end card
    spec.py              spec -> timeline: beat timing from the narration, camera plan, overlay windows, sound cues
    render.py            frames
    audio.py             voice engines (kokoro / piper / command = bring your own / files / none), SFX, optional music with ducking, mix
    cli.py               validate / stills / render / batch / countries
  engine/data/world.npz  Natural Earth countries, lakes and rivers (decimated, 2.6 MB)
  engine/fonts/          OFL fonts with their licences
  design/                DESIGN.md + exported palettes, icons, cards, type specimens and style frames
  tools/                 fetch_data.py, build_world.py, make_design.py, new_story.py
  examples/              rendered examples
  ATTRIBUTION.md         data, font and voice licences
```

## Mass production

```bash
python tools/new_story.py --from-csv topics/topics.csv     # a starter spec per topic
# an agent fills each spec, following PLAYBOOK.md steps 1-8
cd engine && python -m mapstory batch ../stories --aspect 16:9,9:16
```

Speed: a 70-second 1080p video renders in about 10-15 minutes per aspect on a 16-thread CPU with 6 workers.
Each worker needs about 1-1.5 GB of RAM (about 2 GB for the satellite style), so use `--workers` of about RAM in GB / 2
(RAM / 3 for satellite).
No GPU, no accounts, no paid APIs.

## Licence

Code: MIT. Data, fonts and voice: see [ATTRIBUTION.md](ATTRIBUTION.md). Made with [rrender.ai](https://rrender.ai).
