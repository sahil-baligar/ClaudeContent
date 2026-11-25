# Map stories: agent playbook

Follow these steps in order to turn **one topic** into **one finished map-story video**. Every step has
a concrete output, so a coding agent can do the whole thing alone and a reviewer can check each step.
For mass production, run the same steps once per row of `topics/topics.csv`, then `batch` render.

```
topic -> 1 research -> 2 story -> 3 beats -> 4 places -> 5 camera plan -> 6 overlays -> 7 spec -> 8 stills -> 9 render -> 10 check
```

---

## 1. Research (output: 5-12 sourced facts)

- Read 2-4 reliable sources (Wikipedia plus the sources it cites is the minimum). Write each fact with
  its date, place and number, and the URL it came from.
- Write down the place names **as they were at the time** (Kovno, not Kaunas; Constantinople before 1930).
- When sources disagree on a number, either quote one named source ("Minard's count") or give a range. Never invent precision.
- Drop any fact you can't source.

## 2. Story (output: a hook line and a one-paragraph arc)

A map story is **one journey or one change over space**, told in time order. Good shapes:
- **a journey:** an army, an expedition, a voyage, a migration;
- **a spread:** a plague, a language, a railway;
- **a squeeze:** a blockade, a siege, a border being drawn;
- **a what-if:** two famous figures whose paths cross. Use people the audience already knows.

The **hook** is the first line, spoken over the spinning globe while the title shows. It must make
someone stay: a paradox, a number or a question ("Five ships left Spain. Three years later, one came back").
The **ending** pays off the hook and pulls the camera out to show the whole route.

## 3. Beats (output: 6-12 beats, 45-90 s total)

One beat = one or two spoken sentences = one camera move. Rules:
- 12-25 words per beat (about 4-8 s). The whole video runs 45-90 s at about 2.7 words a second.
- Each beat moves the story to a new place or a new moment. No beat without a reason to look at the map.
- Write `vo` the way it should be **said** ("eighteen twelve"), and `caption` the way it should be **read** ("1812").
- Keep proper nouns in their normal spelling. Phonetic respellings usually sound worse with neural TTS.
  Check names by listening, or with a speech-to-text pass (see step 10).

## 4. Places (output: the `places` block)

For every location the beats mention: `name` (period name), `lat`, `lon` (decimal degrees, from the
source or Wikipedia's coordinates), and `kind`:
`city`, `capital`, `battle`, `port`, `camp`, `x` (a point of interest), `dot`, or `region` (big spaced
text with no marker, for seas, empires and zones). Add `note` (up to 24 characters, handwritten under the label) for a date.
Use `side: "l"` when a label would run into a neighbour or off-screen.

Historic zones or empires go in `areas` as a rough `polygon` of `[lat, lon]` points. Mark them as
schematic in `notes`. Modern countries can be highlighted by their Natural Earth name
(`python -m mapstory countries` lists them). Use modern outlines only where they match the story.

## 5. Camera plan (output: a `camera` object per beat)

The camera is the storyteller. The grammar is **zoom out to show where, zoom in to show what happened**:

| Beat role | camera |
|---|---|
| hook / title | `{"to": [lat, lon], "zoom": "globe", "tilt": 0}` (a slow spin in) |
| establish a region | `{"to": ["a", "b", "c"], "tilt": 25-30}` frames several places together |
| an event at one place | `{"to": "place", "zoom": 2-5, "tilt": 30-36}` |
| a long movement | `{"move": "follow", "route": "id", "zoom": 4-9}` rides the head of the line |
| a jump in place or time | `{"move": "cut"}` (use rarely) |
| ending | frame the whole route; the engine adds a final pull-out behind the end card |

- `zoom` is the radius in degrees that stays visible: `globe` 72, `continent` 26, `country` 9,
  `region` 3.6, `city` 1.1. Numbers work too.
- Alternate wide and close shots. Two "region" beats in a row at the same place feel static.
- The engine flies between beats on a great circle and pulls out on long hops (`hop`). **Holds are never still:**
  each one drifts at constant speed (`drift`, default 1.0; alternating direction per beat) and pushes in (`push`, default 0.08).
  Give long holds something that draws, counts or pops as well (a `draw`, a stat `card` or a `stamp`).

## 6. Overlays (output: per-beat `header`, `labels`, `draw`, `card`, `stamp`, `year`, `highlight`)

Give every beat **one** main device and at most two small ones:
- `header`: kicker (a date) + title (2-4 words), at the top. Change it every beat or two.
- `year`: the top-left counter. Set it when the year changes; it flips.
- `labels`: the places named in this beat's narration, and only those.
- `draw`: animate a route to a progress value (`"to": 0.5`). Split one journey over several beats.
  `width: [start, end]` tapers the line. That is Minard's trick: width = people.
- `card`: `stat` (a number counting up or down), `fact` (kicker, title, one short sentence),
  `quote` (under 140 characters, from a source), `portrait` (only with a public-domain or licensed `image`;
  without one it shows a monogram).
- `stamp`: one or two words slammed on at the dramatic moment ("Moscow burns"). Use 2-3 per video at most.
- `highlight`: fill a country or area while it matters.

## 7. Spec (output: `stories/<id>.json`)

Copy `stories/napoleon-1812.json` and replace its contents. The format is defined in
`schema/story.schema.json`. Use the default `style`, `light`, unless the brief asks for a theme:

| style | use for |
|---|---|
| `light` | **default** for every era: true-white land, pale blue sea with ripple lines, ink coast, red routes |
| `antique` | optional theme, before about 1850: sepia chart paper, ink coastlines |
| `atlas` | optional theme, about 1850-1950: school-atlas cream and blue |
| `warroom` / `dark` | optional dark theme for 1939-1991 conflicts and the Cold War: dark slate, cyan coast, amber routes |
| `satellite` | modern stories, or any story where real terrain matters (needs `python tools/fetch_data.py --bluemarble`; keep `zoom` at 4 deg or wider, Blue Marble is about 500 m per pixel) |

Set `"map": {"borders": false}` for anything before about 1950: Natural Earth borders are modern.
Fill `sources` (it prints on the end card) and `notes` (what is schematic, which numbers are disputed).
Then validate:

```
cd engine
python -m mapstory validate ../stories/<id>.json
```

## 8. Stills (output: PNGs to eyeball before you spend render time)

```
python -m mapstory stills ../stories/<id>.json --aspect 16:9,9:16 --draft
```

Check that every label is on screen and readable, the route goes where the story says, cards don't
cover the subject, and the camera isn't framing empty land or sea. On 9:16, type auto-scales to a 3.5%-of-height cap
height, so keep labels to the places this beat names; two or three at a time reads best. Fix the spec and repeat.

## 9. Render (output: `out/<id>/<id>_16x9.mp4`, `_9x16.mp4`, cover and contact sheet)

```
python -m mapstory render ../stories/<id>.json --aspect 16:9,9:16 --workers 6
python -m mapstory batch  ../stories --aspect 9:16          # every spec in a folder, skips ones already rendered
```

A 70 s video at 1080p takes about 10-15 minutes per aspect on a 16-thread CPU with 6 workers
(each worker needs about 1-1.5 GB of RAM). Narration:
set `voice.engine` to `kokoro` (local and free; see README), `piper`, `command` (bring your own TTS or voice clone),
`files` (your own recordings, one per beat) or `none` (silent, timed at 2.7 words a second). **There is no background music by default.**
Effects: `"sfx": "synth"` (built-in), `false` (voice only) or `{"dir": ...}` (your own licensed samples).
If you add some, use only CC0 or licensed tracks and credit them in `music.credit`.

## 10. Check (output: a pass/fail note per video)

1. Watch the whole video once with sound.
2. Run speech-to-text (e.g. faster-whisper) on the narration and compare it with the script. Fix names it gets badly wrong.
3. Open `<id>_16x9_contact.jpg` and check:
   - the camera moves in every shot;
   - labels are readable;
   - every number on screen matches a source;
   - no modern borders appear in a historic story.
4. Re-read the facts against the sources. A wrong date is worse than a missing one.
5. Ship it with its spec, so anyone can re-render or translate it.

---

### Mass production recipe

```
topics/topics.csv  ->  (agent) one spec per row, steps 1-8  ->  stories/*.json
                   ->  python -m mapstory batch ../stories --aspect 16:9,9:16
                   ->  step 10 on every output
```

`python tools/new_story.py --from-csv topics/topics.csv` writes a starter spec for every topic that
doesn't have one yet (id, title, style, era defaults and empty beats), so the agent only fills them in.
