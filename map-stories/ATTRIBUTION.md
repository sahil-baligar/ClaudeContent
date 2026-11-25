# Attribution and licences

The code and docs in this folder are MIT licensed (see `../LICENSE`). Everything else keeps its own licence:

## Map data
- **Natural Earth** (public domain): admin-0 countries, lakes, rivers + lake centrelines at 1:10m.
  `engine/data/world.npz` is a decimated copy built by `tools/build_world.py`.
  "Made with Natural Earth. Free vector and raster map data @ naturalearthdata.com."
- **NASA Blue Marble Next Generation** (public domain), December 2004 topography + bathymetry. Used only by the
  `satellite` style. Not shipped: `tools/fetch_data.py --bluemarble` downloads it.
  Credit: NASA Earth Observatory (Reto Stöckli).

There are no OpenStreetMap tiles here. If you add OSM-derived tiles, credit
"© OpenStreetMap contributors" (ODbL) on screen.

## Fonts (all SIL Open Font License 1.1; licence texts in `engine/fonts/licenses/`)
- Oswald: The Oswald Project Authors
- Playfair Display (bold): The Playfair Display Project Authors
- IM FELL English: Igino Marini (via Google Fonts)
- Roboto (bold): The Roboto Project Authors
- Caveat: The Caveat Project Authors

## Voice (only if you turn narration on)
- **The example videos** use **Kokoro-82M** (hexgrad; weights under **Apache-2.0**), voice `am_fenrir`, run through
  `kokoro-onnx` (MIT, thewh1teagle). Neither is bundled: `pip install kokoro-onnx` and download the model files (README).
  `kokoro-onnx` phonemises with espeak-ng (GPL-3.0), which installs as a separate library. Generated audio is yours to publish;
  credit the voice as the example end cards do.
- **Piper** (MIT) is supported too (`voice.engine = "piper"`). Check each Piper voice's model card for its dataset licence
  (for example, `en_US-libritts_r-medium` is LibriTTS-R, CC BY 4.0).
- **Bring your own voice** (`voice.engine = "command"` or `"files"`): you are responsible for the rights to that voice.
  Only clone a voice with its owner's consent.

## Sound
- The built-in sound effects (`"sfx": "synth"`: whoosh, pop, tick, stamp, pen scratch, counter) are synthesised in
  `engine/mapstory/audio.py`. No samples are shipped. The example video is voice only (`"sfx": false`).
  If you use `"sfx": {"dir": ...}`, only use samples you are licensed to publish.
- No music is included. If you use the music hook, use CC0 or licensed tracks and set `music.credit`.

## Images
- No photographs are included. Portrait cards show a monogram unless you supply a public-domain or licensed image.
  Credit it in the spec's `sources`.

## Facts
The example stories cite their sources in each spec (`sources`) and on the end card. Routes and zone outlines are
schematic illustrations, as each spec's `notes` says.

Made with [rrender.ai](https://rrender.ai).
