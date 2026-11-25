# Map stories: design system

Every frame is drawn from code, so the design system is defined in code (`engine/mapstory/styles.py`
and `engine/mapstory/draw.py`). The files in this folder are exports of that code, made with `python tools/make_design.py`.

| File | What it shows |
|---|---|
| `palettes.svg` | every colour token of the four era styles |
| `type_<style>.png` | type specimen per style: title, labels, captions, hand notes |
| `styles/<style>_16x9.png`, `_9x16.png` | a full style frame per style and aspect |
| `styles/<style>_title.png` | the opening globe with the title cartouche |
| `cards/<style>_<kind>.png` | stat, fact, quote and portrait cards, and the rubber stamp |
| `icons/*.svg` | place markers (city, capital, battle, port, camp, x) and route heads (arrow, army, ship, plane) |

## Principles

1. **The map is the set; the camera is the storyteller.** One continuous take: fly, push in, pull out. No hard
   cuts unless the story jumps (`move: cut`).
2. **Light by default.** True white and ink, like a clean printed atlas. Era themes (antique, atlas, dark, satellite) are optional.
3. **One device per beat.** A beat gets one main overlay (card *or* stamp *or* a route that draws) plus labels.
4. **Only name what is spoken.** Labels appear when the narration says the place, and leave with the beat.
5. **Numbers move.** Stat cards count from their `from` value: up for growth, down for loss.
6. **The line is the story.** Routes taper with the people they carry (Minard). A retreat runs beside the advance, never on top of it.
7. **Readable at phone size.** On portrait frames, captions, header titles and labels have a cap height of at least 3.5% of
   the frame height (67 px at 1920). Captions are Oswald with a heavy stroke, three words at a time, with the spoken word in the
   accent colour. Overlapping labels flip side or move down.
8. **Honest maps.** Natural Earth borders are modern, so turn them off for historic stories. Draw zones as
   schematic polygons and say so in the notes. Every number on screen has a source on the end card.

## Styles

**`light` is the default.** True white land and paper (no cream), a pale blue sea `#e4ecf2` with ripple lines, ink coast `#1c2026`,
red accent and routes `#d6281e`, Playfair Display titles and Oswald labels. The table below lists the optional themes.

| Token | antique (pre-1850) | atlas (1850-1950) | warroom / dark (optional) | satellite (modern) |
|---|---|---|---|---|
| land | parchment `#eadcb8` | cream `#f0e8ce` | slate `#222e2e` | Blue Marble, graded warm |
| sea | sepia-grey `#c4ba9c`, ripple lines | soft blue `#aac8d6` | near-black `#0e181e` | Blue Marble |
| coast | ink `#462e1c` | blue-grey `#466078` | cyan `#6eced6` | none |
| accent | oxblood `#9a241a` | atlas red `#c82e28` | amber `#f4aa3c` | gold `#d6b25c` (stamps red `#ce2c24`) |
| cards / panels | parchment paper | white paper | dark glass | true black, gold rule |
| title face | Playfair Display Bold | Oswald | Roboto Bold | Playfair Display Bold |
| label face | IM FELL English | Oswald | Roboto Bold | Oswald |
| graticule | 15 deg, faint ink | 10 deg | 10 deg, cyan | none |

Captions are always Oswald (`cap_fg` / `cap_hl` / `cap_stroke`). Hand notes are always Caveat in the accent colour.
Any token can be overridden per story with `style_overrides`.

## Layout (safe zones)

| | 16:9 (1920x1080) | 9:16 (1080x1920) |
|---|---|---|
| header (kicker + title between rules) | top centre, y 46-154 | top centre, y 204-312 |
| year counter | top left (64, 96) | top left (64, 110) |
| subject (camera look-at) | frame centre | raised to 39% of the height so it clears the cards and captions |
| cards | right column, vertical centre | centred at 66% of the height |
| stamps | centre, 66% of the height | centre, 50% of the height |
| captions | bottom centre, y 976 | y 1560 (above the platform UI) |
| readability bands (satellite) | dark gradient behind header and captions | same |
| end card | sources, map/voice credit, "made with rrender.ai" | same |

## Motion

- Camera flights are great-circle slerps with quintic easing. Height is interpolated in log space plus a
  `hop` pull-out proportional to the distance, so long jumps zoom out and back in. Tilt flattens mid-flight.
- Holds never stop: a constant-speed drift (about 4.5% of the half-view per second, alternating direction per beat) plus an 8% push-in. Labelled places pulse with a soft accent ring.
- Cards pop with a back-ease overshoot (0.42 s), stamps slam from 190% with a small wobble, labels fade in staggered by 0.18 s.
- Routes draw with an eased progress, their head marker leading, and an optional taper.
- The video closes with a 4 s end card over a pull-out that frames every place shown.

## Sound

There is no background music, on purpose: the narration carries the video. Voice gaps stay under 0.5 s
(TTS padding is trimmed; 0.12 s lead plus 0.33 s tail per beat). Effects are optional (`sfx`). When they're on, each one marks a move:
a whoosh on every flight, a pen scratch while a route draws, a pop when a card appears, ticks while a counter runs,
and a thud when a stamp lands. The example ships voice only. Final loudness is -14 LUFS.
