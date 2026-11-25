# ClaudeContent

Open-source pieces of the [rrender.ai](https://rrender.ai) content factory, released one tool at a time.
Use the code here and render on your own machine, or use the same tools for free at rrender.ai.

| Tool | What it makes | Status |
|---|---|---|
| [`map-stories/`](map-stories/) | Zoom-in / zoom-out map animations that tell a historic story (routes, battles, years, cards, narration) | v0.1 |

## Folder layout (every tool follows it)

Each tool is one self-contained folder. A coding agent, or a person, should be able to open the folder,
read `PLAYBOOK.md` and produce a finished video without asking anyone anything.

```
<tool>/
  README.md        what it makes, quick start, example output
  PLAYBOOK.md      the step-by-step outline an agent follows (topic -> spec -> render -> check)
  schema/          JSON Schema for ONE video's input spec. One file = one video.
  engine/          code that renders a spec. No accounts, no paid APIs, no keys.
  design/          the design system: DESIGN.md + exported palettes, icons, cards, style frames
  stories/         example specs (copy one to start)
  topics/          topic lists for mass production
  examples/        rendered example videos
  tools/           helpers (data download, scaffolding, design export)
  ATTRIBUTION.md   every third-party data set, font and voice, with its licence
```

Mass production is always the same loop: **topics list -> one spec per topic (written by an agent
following the PLAYBOOK) -> `batch` render -> check -> publish.**

## Rules for everything in this repo

- Only free and open data, fonts and voices, each credited in the tool's `ATTRIBUTION.md`.
- No secrets, keys or personal paths. Configuration goes through environment variables.
- No background music by default. A tool may offer a music hook; only use CC0 or properly licensed tracks.
- Facts in example stories are sourced (see each spec's `sources`); check them again before you publish.

## Licence

Code and docs: [MIT](LICENSE). Data, fonts and voices keep their own licences (see each tool's `ATTRIBUTION.md`).
