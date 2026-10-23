# Project Star — Part 1 (web port)

A browser port of **Project Star Part 1**, a 2005–2006 PowerPoint game
(358 slides, OLE/PPT97-2003 binary, author FragsL) by Shiny/spotco.

The port reuses the extraction + runtime infrastructure built for
`goblinsrpg3_dev`, adapted to this deck's extra features: animated GIFs
hidden in PNG blips, WMF clip-art, a Photoshop OLE object, per-text-run
hyperlinks, linked MP3 music tracks, and five transition types goblins
never used. The binary `.ppt` is the oracle for every decision — see
`NOTES.md` for the bug/fix log and `plans/` for the dated port plan.

## Play it

The game is a static site in `docs/`. Serve it locally:

```bash
python tools/serve_docs.py --port 8766 --directory docs
# open http://127.0.0.1:8766/
```

- Click the stage to advance animations and click-advance slides.
- Click text options (`-Start-`, `-shot`, `-Land`, …) to choose paths.
- Speaker icons play music/SFX (the Sound Test is slide 358).
- **Restart** returns to the title; **Mute** toggles audio.
- It can also be hosted as-is from `docs/` (e.g. GitHub Pages).

Debug affordances (inherited from the goblins runtime):

| URL | Effect |
|---|---|
| `?slide=N` | Start on slide N |
| `?debug=1` | Debug HUD + logging + hotspot outlines |
| `?log=1` | Console logging only (`[ProjectStar] …`) |
| `?hotspots=1` | Outline clickable hotspots |
| `window.projectStarDebug` | `goto(n)`, `snapshot()`, `history()`, `dumpScreen()` |

## Rebuild from the source deck

Everything in `docs/` and `generated/` is produced from
`ProjectStar Part1 V1.1.ppt` by the tools in `tools/`:

```bash
# prerequisites: Python 3 + olefile + Pillow, JDK 21 + Apache POI 5.2.3
# (audit only), ffmpeg, LibreOffice (WMF conversion + reference renders)
python tools/extract_ppt.py            # records → generated/inventory.json + assets
python tools/convert_wmf.py            # WMF → transparent PNG
python tools/extract_timing.py         # transitions + legacy animation atoms
python tools/extract_animation_manifest.py   # PP10 timing tree → animations
python tools/extract_layers.py         # POI + binary text → layers
python tools/extract_embedded_audio.py # 17 embedded WAVs
python tools/convert_audio.py          # WAV/MP3 → mp3 + opus cues
python tools/render_reconstructed.py   # per-slide composite PNGs
python tools/build_game_manifest.py    # → docs/game-manifest.json + site assets
python tools/build_chapter_walks.py    # chapter menu entries
python tools/build_offline_playability.py
```

## Verify

22 checkers guard the port (extraction contracts, hyperlink graph,
animation coverage, audio cues, text fidelity, transitions, runtime
traversal, offline playability, …):

```bash
for f in tools/verify_*.py; do python3 "$f"; done   # all must print PASS
```

## Layout

- `ProjectStar Part1 V1.1.ppt`, `track*.mp3`, `art1.JPG`, manuals — the
  original game, untouched.
- `tools/` — extraction pipeline, manifest builders, verifiers, dev server.
- `generated/` — extraction evidence (inventory, layers, reports, renders).
- `docs/` — the playable static site (runtime `app.js`, manifests, assets).
- `source/` — LibreOffice-converted `.pptx`, a debug lens only (never an
  extraction source; LO renumbers shape IDs).
- `plans/` — the dated port plan and the goblins infrastructure inventory.
- `NOTES.md` — bug/fix log and known residuals. `docs/DEBUGGING.md` —
  how to debug the port.
