# ProjectStar Part 1 — Web Port Plan

Date: **2026-10-23**
Author: Muse (umaMUSEume), at Shiny's direction
Source repo: `spotco/projectstar_dev` @ `8226ea9` (initial commit)
Reference port: `spotco/goblinsrpg3_dev` @ `3827854` (73 commits, completed browser port)
Companion inventory: `plans/2026-10-23-goblins-infrastructure-inventory.md`
(full audit of the goblins pipeline/runtime/bug history this plan reuses)

Goal: a static, GitHub-Pages-ready browser port of ProjectStar Part 1 in
`docs/`, built by copying the goblinsrpg3 infrastructure into this repo and
adapting it — same manifest schemas, same runtime architecture, same
verification discipline — plus new work for the features ProjectStar uses
that Goblins RPG 3 does not.

---

## 0. What the source actually is (verified 2026-10-23, not assumed)

| Fact | ProjectStar | Goblins RPG 3 (for contrast) |
|---|---|---|
| File | `ProjectStar Part1 V1.1.ppt`, 5,511,168 B, SHA-256 `888ba774…021` | `goblins3 v.1.0 LAUNCH.pps`, 1.6 MB |
| Container | OLE / PowerPoint 97-2003 binary (`Composite Document File V2`), created 2005-06-13, last saved 2006-03-05, rev 1031, app "Microsoft Office PowerPoint" | Same container family, created 2005-03-15, saved 2005-05-20, rev 653 |
| Slides | **358** | 201 |
| Presentation size | 5760×4320 EMU-ish source coords, 4:3 → 720×540 stage | identical |
| Shapes (OfficeArt) | **3,340** | 1,591 |
| Text runs | 960 (395 TextChars + 565 TextBytes records) | 357 |
| Legacy animation atoms (4081) | **922** | 341 |
| PP10 timing trees | all 358 slides; 7,741 TimeNodes, 3,813 behaviors (843 animate / 434 effect / 448 motion / 30 scale / 1,991 set / 29 command), 443 iterate nodes, 552 ParaBuilds | 197 slides; 2,533 TimeNodes; 1,015 visual targets |
| Interactive actions (4083) | 265 = 218 hyperlink + 26 media + 21 explicit none | 217 = 194 + 11 + 12 |
| Hyperlinks (ExHyperlink) | 218; DocSummary destinations 217; **stale friendly labels: 0** | 194; stale labels: 75 |
| Embedded images | 279 blips extracted (PNG/DIB path) | 116 |
| Embedded sounds | **17 WAV** (cashreg, chimes, explode, push, suction, voltage, wind, j0214098, MSj*/MSSN*…) | 5 |
| Linked audio | **track1–5.mp3 in repo root** (absolute `C:\…\Project star folder\trackN.mp3` refs in binary) | titlesong.wma / rocksong.wma / Ffvictory.mid in repo root |
| Transitions (SSSlideInfoAtom) | cut 273, fade(23) 47, **unknown_6 ×15, unknown_5 ×2, unknown_8 ×2, unknown_10 ×2, unknown_26 ×3**, circle(27) 14 | cut 181, fade 9, newsflash(22) 6, zoom(11) 2, checker(3) 1, comb(21) 1, circle 1 |
| Auto-advance slides | **238 / 358** (this deck is far more cinematic) | 59 / 201 |
| Fonts | Arial (dominant), Arial Black, Times New Roman | more varied |
| Extra files in repo | `art1.JPG` (800×600 cover art), `Manual.txt`, `Cd manual.txt`, track1–5.mp3 | — |

**Format note / correction to the brief:** the brief says ProjectStar uses a
"newer PowerPoint format". The file in this repo is the *same* OLE binary
family as goblins' `.pps` (not OOXML `.pptx`), but it is a **later, larger,
heavier revision** of that format in practice: saved a year later with
PowerPoint 2003, ~2.7× the animation atoms, PP10 timing on every slide, and
record types goblins never contains — 1008/1009 (notes master/slide),
3035, 4006, 4035, 4041, 4044/4045, 4089. The goblins binary parsers therefore
**do** run on it (verified: inventory + timing extraction succeed verbatim),
but the feature delta in §3 is real and is where the new work lives. A
LibreOffice-converted `.pptx` will be checked into `source/` as a *debug
lens only* (exactly as goblins did) — LO renumbers shape IDs, so it can
never be the extraction source; the binary + POI audit remain the oracle.

### Deck structure (from extracted text, for chapter/debug entries)
- s1–5: Presents / title (`-Start-`, s3) / opening starfield cinematics
- s6–33: opening ship battle (dialogue + `-shot` combat, HP counters), Game Over s26
- s34–42: local-map / warp-gate hub (`-Land` / `-Continue` choices)
- s43–80: warp-gate station hub — Info/Business permutations (author's own
  ordering notes are baked into slides 60/63/70–72), ship info, exit s78
- s81–103: travel / operator / credits-facility sequence
- s104–130: Leahin town, shipyard/buy screens (s121–122), train sequence
- s131–161: homecoming, intruder scene, Punch/Insult choice tree (s166–184),
  "YOU FREEZE THE GAME" loop s159–161→157, Game Over s174
- s185–242: escape, auto-taxi, city 87, convention center, Caina apartment
- s243–272: in-game magazine (SPOTCO Weekly) — clickable page-flip section,
  Photoshop-OLE art (s243/246), animated-GIF demo page (s271), WMF art (s272)
- s273–307: departure cinematics, GIF showcase (s303: "look at that GIF technology")
- s308–355: final battles (GIF starfield art s308–336), ending, credits s356
- s357: Aww Yeah. · s358: **Sound Test** (speaker icons play track1–5)

---

## 1. Standing rules inherited from goblins (non-negotiable)

1. **The binary is the oracle.** Hyperlink targets resolve via
   DocumentSummaryInformation `slideId` → SlideListWithText presentation
   order, *never* via the ExHyperlink `"Slide N"` friendly label alone, and
   **never via invented target overrides** (goblins removed all overrides in
   `db303a4`; a remembered/intended story edge that contradicts the binary
   gets documented, not remapped). ProjectStar shows 0 stale labels today —
   the DocSummary path is still used so the pipeline stays correct by
   construction.
2. **No target/story invention anywhere:** no bridging "islands", no
   promoting self-links without recorded provenance (sole-hyperlink /
   combat-all-self policies in `advancement_lib.py` keep their audit trail
   in `generated/promote_audit.json`).
3. **Extraction before runtime opinions.** Every runtime weirdness is first
   checked extract → manifest → runtime decision (goblins `DEBUGGING.md`
   protocol), with `?debug=1&slide=N`, `projectStarDebug.dumpScreen()`,
   history ring buffer, and offline verifiers as the gate — not eyeballing.
4. **Playwright tests must click visual centers**, not DOM nodes / aria
   substrings (goblins' Attack/Flee false-confidence lesson).
5. **Cache-busting everywhere** (no-store server headers + per-load query),
   or every QA result is suspect.
6. **Git:** work lands on `master`, no leftover branches (Shiny's repo
   policy); the goblins repo's old "push only to grokbot-dev" rule does
   **not** carry over — it was that project's local workflow note.

## 2. Reuse map — what gets copied from goblinsrpg3_dev

Copied into this repo (then adapted per §4), per the user's explicit
permission to copy any needed infrastructure:

- `tools/` — all ~60 Python tools + `tools/poi/PoiAudit.java` +
  `tools/requirements.txt` (pipeline §5 of the inventory doc):
  extractors (`extract_ppt`, `extract_timing`, `audit_timing_tree`,
  `extract_animation_manifest`, `extract_layers`, `extract_embedded_audio`,
  `extract_source_semantics`), audio (`convert_audio`, `render_midi`),
  render (`render_reconstructed`), manifest (`build_game_manifest`,
  `advancement_lib`, `motion_path_lib`, `animation_timeline`), report
  builders, debug tools, `serve_docs.py`, and the `verify_*.py` suite.
- `docs/` runtime — `index.html`, `app.js` (~5,200 lines: layer renderer,
  WAAPI animation scheduler, hotspot engine, audio engine, transition
  engine, Debug HUD/API), `styles.css`, `DEBUGGING.md`.
- Docs: `PLAN.md`→this file's model, `README.md`, `RENDERING.md`,
  `POI_EVALUATION.md`, `ANIMATION_EVALUATION.md`, `AGENT_TESTING.md`,
  `NOTES.md` (continued here as the running bug log).

**Deck-agnostic (reuse near-verbatim):** runtime scheduler/render/debug,
manifest schemas, motion-path sampling, MIDI synth, audio conversion,
advancement algorithms, verifier patterns, local server.
**Must be re-parameterised / stripped (goblins-specific):** every hardcoded
`201`, slide-count asserts, combat option matrix + combat role inference +
Limit logic, chapter entries, `goblinsRpg3Debug`/storage keys/log prefix,
`SOURCE_AUDIO_CUE_IDS` (titlesong/rocksong/Ffvictory), POI mojibake map
(deck-specific — re-derive, don't copy blindly), slide-specific hacks
(s002 title, s015 flee, s046, s183/s194/s201), favicon/project assets,
Windows font paths in `render_reconstructed.py` (portability bug — resolve
fonts cross-platform here).

## 3. New work — features ProjectStar uses that Goblins does not

| # | Feature | Evidence | Work |
|---|---|---|---|
| N1 | **Animated GIFs as slide art** | `image226.gif` 234×156 (51 frames) s271; `image256.gif` 459×347 (5 frames) reused s308–336; s303 text celebrates GIF tech | `extract_ppt.py` only extracts PNG (0xF01E) + DIB (0xF01F) blips. Audit blip record types present in the Pictures stream (GIF 0xF01D, JPEG 0xF01C, EMF/WMF 0xF01A/0xF01B…); extend extraction to emit GIF/JPEG verbatim. POI picture-type mapping in `extract_layers.py` must carry GIFs through as `<img>` layers with animation preserved (no Pillow flattening to frame 0); reconstructed-screen renderer composites frame 0 and notes it. Verify GIF slides render + animate in browser QA (s271, s308). |
| N2 | **WMF images** | `image147.wmf` s188, `image230.wmf` s272 (tiny metafiles, 3 objects) | Browsers can't render WMF. Convert at build time to PNG (LibreOffice headless render of the single shape / `libwmf` if available / POI-picture fallback via the LO-converted pptx media is *not* acceptable as source — use it only to sanity-check the conversion). Keep conversion script + provenance in `generated/`; slide then references the PNG like any picture layer. |
| N3 | **Photoshop OLE object** | `oleObject1.bin` (665 KB, Adobe Photoshop Elements) on s243 + s246; pptx lens shows preview `image89.png` | OLE objects are not playable content — the *preview image* is the slide art. Ensure POI/layer extraction picks the preview picture instance for those shapes and the OLE storage does not leak in as a bogus layer/hotspot. Add a verifier note; if the preview is missing from the binary picture instances, extract the presentation image from the OLE `OlePres000` stream. |
| N4 | **Linked MP3 BGM (5 tracks)** | Binary refs `…\Project star folder\track1..5.mp3`; files ship in repo root; s358 Sound Test names them (Title=FFVIII theme, Battle 1, Train, Battle 2, Battle 3) | Generalise `convert_audio.py` source kinds beyond WMA/MID: MP3 sources pass through + generate Opus twins (runtime prefers MP3 on Pages, per goblins `f4a2886`). Replace `SOURCE_AUDIO_CUE_IDS` with `track1..5.mp3 → linked:trackN`. Map the 26 media actions (action_code 6) to cues; Sound Test speaker icons must play/stop per the slide's own note ("Press Clear and re-enter…") — i.e. preserve authored overlap behaviour, document it, don't "fix" it. BGM start/stop/replace semantics come from the timing-tree command behaviors (29 command behaviors here vs goblins' handful). |
| N5 | **External URL hyperlink** | s91 shape links to `http://www.obeygiant.com/stickers/bootlegs/images/mr-t-02.gif` (also the Mr. T GIF motif) | Runtime hotspot policy for external targets: open in new tab, never navigate the game away; manifest records `externalUrl` distinctly from slide targets. Verifier: exactly 1 external edge, on s91. (Offline, the target may be dead — that's fine; we preserve the link, we don't fetch it into the game.) |
| N6 | **New slide-transition types 5, 6, 8, 10, 26** | SSSlideInfoAtom counts §0; LO pptx lens names them per-slide | Cross-check each type against the pptx lens' `p:transition` names (the goblins method that produced 3=checker, 11=zoom, 21=comb, 22=newsflash, 23=fade, 27=circle). Extend the runtime transition CSS + `verify_transition_effects.py` catalog. Expected candidates from MS-PPT spec: 5=?? — *resolve from the lens, do not guess*. |
| N7 | **Per-text-run hyperlinks** (multiple targets, one shape) | s42 shape 44047 → s42 *and* s80; s166/s180/s261/s263 shapes each carry 2 targets | Goblins' hotspot model is one action per shape record in most paths. Audit how many shapes carry >1 distinct target; if the POI audit exposes run-level links, emit one hotspot per run bounds (or split shape bounds by run); if only shape-level is recoverable, keep shape hotspot to the primary target and log the residual in the gameplay-behavior review — no silent drops. |
| N8 | **Notes master/slide records (1008/1009) + new record types** | 1008×1, 1009×1, 3035×3, 4006×3, 4035×2, 4041×1, 4044×2, 4045×2, 4089×2 — none exist in goblins | Identify each in the extractor's record census; confirm they're inert for gameplay (notes are not slides — slide count must stay 358 in every verifier) and that `extract_ppt.py`'s slide walker isn't off-by-one because of the extra 1006/1007-like records (note: 359 SlideAtom/1011/1017 records vs 358 slides — the +1 is the notes/master side; pin this down explicitly). |
| N9 | **Scale: 358 slides, 922 anim atoms, 238 auto-advance** | §0 | Manifest sizes will roughly double goblins (animation-manifest was 12 MB there — watch GitHub Pages weight; keep `generated/` out of `docs/` except runtime copies). Auto-advance correctness matters far more here: `max(slideTime, timeline)` rule + transition-bucket timers from goblins apply deck-wide; the offline path-walk must cover auto-advance edges, not just hotspots. Heavy slides (s5: 100+ line shapes + 78 motion paths; s39 similar) are the perf test cases. |
| N10 | **Grouped shapes at scale** | OfficeArt group containers 27 (vs 7); several slides with 90–110 shapes | Layer extraction must preserve group nesting/flip/rotation from POI the way goblins did for its 7 groups; add group-heavy slides (s5, s39, s121/122) to visual QA list. |
| N11 | **Magazine sub-game (s261–272)** | Text-run links + page-flip hotspots s261→262/265, s263→264/265; "read some of the magazines" gate at s261/263 | Treat as its own chapter entry; path-walk must prove enter → flip all pages → exit to s265 works, since it's an optional-content cul-de-sac off the main story. |
| N12 | **"Freeze" loop slides s159–161** | Text: "OH SCHNAPPS YOU FREEZE THE GAME"; edges 159→160→161→157 | Verify this is an authored timed loop (auto-advance chain back to s157), not a stuck state; offline walk + browser QA with real timers. Document in NOTES. |

## 4. Adaptation work (copied code that must change)

- [x] Rename runtime identity: `projectStarDebug`, `[ProjectStar]` log
      prefix, `projectstar.debugHistory` storage key, page `<title>`,
      favicon/project assets (use `art1.JPG` → banner/button art).
- [x] All slide-count / page-size constants → read from inventory
      (358 / 5760×4320 / 720×540), no literal `201` anywhere (`grep` gate).
- [x] `build_game_manifest.py`: `SOURCE_AUDIO_CUE_IDS` → track1–5 map;
      default source filename → `ProjectStar Part1 V1.1.ppt`.
- [x] Strip goblins combat matrix/Limit verifiers; replace with a generic
      option-matrix builder (same DocSummary-oracle method) covering
      ProjectStar's menus: ship-battle `-shot` choices (s10–25, s312–347),
      warp-gate Land/Continue, station Info/Business, Punch/Insult tree,
      magazine flips, Sound Test speakers.
- [x] Combat annotation (`inferSlideRole` etc.) → generic or ProjectStar
      ship-battle labels; must not mislabel s10 Attack results the way
      goblins' caption heuristic mislabelled s018.
- [x] Chapter entries (generated from graph roots, as goblins did) with
      ProjectStar labels per §0 structure.
- [x] Re-derive the POI text mojibake map from ProjectStar samples
      (its text already shows clean `'…“”` in the Python extractor; POI
      output is the risk — compare POI text vs binary text runs per shape
      and only map observed artifacts).
- [x] `render_reconstructed.py`: cross-platform font resolution
      (Arial/Times on Linux: Liberation metric equivalents), no Windows paths.
- [x] `.gitignore`: `_port_analysis_tmp/`, `__pycache__`, `build/`, `dist/`,
      `generated/renders/` (keep the rest of `generated/` tracked, as goblins).

## 5. Execution phases (checklist — done means verified, not just run)

### Phase 0 — Setup & toolchain
- [x] Clone both repos locally + to spzeni1 `~/dev/` (2026-10-23; spzeni1:
      LO 26.8, ffmpeg, tesseract, Chromium, node 26 — but no pip/java, so
      builds run on the Muse VM; spzeni1 is the OCR/second-machine test bed)
- [x] Goblins inventory written (`plans/2026-10-23-goblins-infrastructure-inventory.md`)
- [x] This plan
- [x] Python venv + `tools/requirements.txt` (olefile, Pillow)
- [x] Portable Temurin JDK 21 + Apache POI 5.2.3 in `_port_analysis_tmp/`
      (downloads started 2026-10-23; archive.apache.org `.zip`, Adoptium API)
- [x] LibreOffice-convert `.ppt` → `source/projectstar_part1-pptx.pptx`
      (debug lens) + PDF reference renders of all 358 slides for OCR QA
      (PDF already produced in probe; regenerate into `generated/reference/`)

### Phase 1 — Extraction (binary oracle)
- [x] Compile + run `PoiAudit.java` → `generated/poi_audit.tsv`;
      expected: 358 slides, 720×540, sounds, shape count ≈3,340 ballpark
- [x] `extract_ppt.py` → inventory (probe already yields 358 slides /
      701 actions / 279 assets — reproduce in-repo)
- [x] Blip-type census → extend extractor for GIF/JPEG/WMF blips (N1/N2)
- [x] `extract_timing.py` (probe: 358 transitions, 922 animations ✔) +
      `audit_timing_tree.py` + `verify_poi_audit.py` (0 missing shapes)
- [x] `extract_animation_manifest.py` → `docs/animation-manifest.json`;
      census preset classes/IDs vs goblins-supported set; list any preset
      the runtime doesn't implement (emphasis preset 8, entr 27, exit 9… seen
      in the lens) and implement gaps in Phase 3
- [x] `extract_layers.py` → layers + per-slide shape assets; animated-target
      coverage = 100% (goblins: 567/567 rule)
- [x] Audio: `extract_embedded_audio.py` (17 WAVs) + `convert_audio.py`
      (WAV→MP3/Opus; track1–5 MP3 pass-through + Opus twins) (N4)
- [x] Record-type census incl. N8 types; notes/master +1-record question closed

### Phase 2 — Renders & manifest
- [x] WMF→PNG conversion for s188/s272 (N2); OLE preview resolution (N3)
- [x] `render_reconstructed.py` → 358× 720×540 screens + render manifest;
      `verify_render_manifest.py` green
- [x] `build_game_manifest.py` → `docs/game-manifest.json`, `docs/screens/`,
      `docs/assets/slide-assets/`, audio cues + media bindings
- [x] Reports: source semantics, gameplay behavior (265 actions classified,
      0 silently dropped), visual review checklist (358), text fidelity
      (re-derived mojibake), advancement model, start-graph analysis,
      offline playability, chapter walks, promote audit

### Phase 3 — Runtime adaptation
- [x] Copy + adapt runtime per §4 (identity, counts, audio map, chapters)
- [x] New transition types (N6) implemented in CSS + verified vs lens
- [x] External-URL hotspot policy (N5); per-run hyperlinks (N7)
- [x] GIF layers animate; speaker/media icons hidden as in goblins `f4a2886`
      (PPT media speaker icons must not paint)
- [x] Apply every applicable goblins animation lesson pre-emptively:
      empty-OnNext drain (deck-wide scan here — count TBD), first-child-on-
      same-click, AfterEffect hide semantics, OnEnd +32 ms binding,
      motion-near-origin pre-hide exclusion, exit-only pre-hide exclusion,
      duration-0 parent OnEnd, AutoShape clip-path restore in `finishIn`,
      iterate set-visible opacity fix, PNG-underlay suppression for large
      animated text (credits s356), transition timers in their own bucket,
      autoplay continue/result beats but never auto-navigate
- [x] Debug HUD must not cover hotspots (`pointer-events:none` shell) —
      ProjectStar menus sit at varied positions; test on ship-battle slides

### Phase 4 — Verification (offline gates, all must pass)
- [x] `verify_inventory`, `verify_extractor_contract`, `verify_timing_tree`,
      `verify_animation_manifest`, `verify_animation_player_contract`,
      `verify_layers`, `verify_animated_layer_coverage`,
      `verify_embedded_audio`, `verify_audio_cues`, `verify_site`,
      `verify_render_manifest`, `verify_runtime_traversal`,
      `verify_advancement`, `verify_start_graph`,
      `scan_advancement_coverage`, `verify_offline_playability`
      (adapted: full-deck reachability from s1 via hotspots + auto-advance;
      every Game Over / ending reachable; no invented edges),
      `verify_visual_risks` (0 clickable self-links without provenance),
      `verify_text_fidelity`, `verify_transition_effects` (incl. N6 types),
      generic option-matrix verify (Playwright, visual-center clicks)
- [x] Path walks (multi-seed) reach: title→start, first battle win + Game
      Over s26, warp hub, station permutations, shipyard buy, train,
      Punch *and* Insult branches, freeze loop, magazine in/out, final
      battles, credits s356, Sound Test s358

### Phase 5 — Browser + OCR QA
- [x] Serve `docs/` (`tools/serve_docs.py`), QA with `?debug=1&slide=N`
- [x] Screenshot priority slides and OCR/vision-compare vs LibreOffice
      reference renders: s1, 3 (title/start), 5 (starfield perf), 10
      (battle menu), 26 (Game Over), 34/42 (map/hub), 54 (ship info),
      121 (buy screen), 159 (freeze), 188 (WMF), 243/246 (OLE),
      271 (GIF + magazine), 272 (WMF back page), 303 (GIF), 308 (GIF
      battle bg), 356 (credits crawl), 358 (Sound Test)
- [x] Full click-through playthrough in browser (timed slides allowed to
      run; no debug-only shortcuts for the final pass)
- [x] Perf check on s5/s39 (100+ animated shapes) — no jank-driven skips;
      if WAAPI load is a problem, batch identical star motions (document
      any deviation in NOTES)
- [x] Log every bug found + fix in `NOTES.md` (goblins format: symptom,
      extract evidence, root cause, fix, verify) — no silent fixes

### Phase 6 — Publish
- [x] `README.md` (play link, local preview, debug mode, rebuild steps,
      limitations), `RENDERING.md`, `AGENT_TESTING.md`, `NOTES.md` finalised
- [x] Commit in validated chunks; push to `master`; no leftover branches
- [x] Optional (Shiny's call): enable GitHub Pages on `docs/` —
      URL would be `https://spotco.github.io/projectstar_dev/`
- [x] Final report to Shiny: what changed, how to play/test, known residuals

## 6. Risks & open questions (tracked, not blockers to start)

1. **POI on Linux:** goblins used a Windows portable JDK; here Temurin 21
   linux-x64 + POI 5.2.3 zip from archive.apache.org (verified reachable).
   PoiAudit.java is platform-neutral; watch for path/encoding diffs in TSV.
2. **Animation-manifest size:** ~2× goblins' 12 MB possible. If
   `docs/animation-manifest.json` exceeds ~25 MB, consider per-slide lazy
   loading — only with a runtime change + verifier update, not silently.
3. **GIF blip extraction:** if the Pictures stream stores GIFs only as
   DIB-converted blips, the animation may already be lost in the binary —
   then the LO pptx media (`image226.gif`/`image256.gif`, which *are*
   animated) becomes the recovery source for those two assets, documented
   as a lens-sourced exception with hashes recorded.
4. **Sound Test overlap:** authored behaviour lets tracks overlap; the
   runtime's replace/stop cue semantics must match the slide's own
   instructions. Test, don't assume.
5. **Author-note slides** (60/63/70–72 texts like "ALL OUT Info then Busi")
   appear to be real slides in the deck order — the binary oracle decides
   whether they're reachable in play; if reachable, they ship as-is
   (faithfulness over polish, same as goblins' documented conflicts).
6. **Pixel fidelity ceiling:** as with goblins, no Microsoft PowerPoint
   reference screenshots exist in-repo; LibreOffice renders are the
   comparison baseline and are known-imperfect (e.g. LO paints red
   selection dots on the s3 Start shape). Claims stay at that level.

## 7. Definition of done

`docs/` plays ProjectStar Part 1 start-to-finish in a browser: title →
story → battles → hubs/branches → magazine → final battles → credits →
Sound Test, with animations, transitions, embedded SFX and linked BGM
working, every offline verifier green, browser/OCR QA done on the priority
slides, all residuals explicitly documented in `NOTES.md`, and the result
pushed to `master` with no leftover branches.

## 8. Completion status (2026-10-23)

All phases done. Verification: 22/22 `tools/verify_*.py` PASS.
Browser QA (Playwright, zero console errors): title/WordArt, animated
GIFs (frame-diff verified), WMF slides, OLE magazine cover, option
menus with per-run hit bands (Punch→175, Insult→167, Land→44,
Continue→81), Sound Test audio (`audio:play track2.mp3` on speaker
click), external-URL popup, Game Over reveal. OCR (RapidOCR) of
browser renders vs LibreOffice references agrees on slides 3/159/272/358.
Bug/fix log and residuals: `NOTES.md`. N8 closed: 359th persist entry
is the deck's single notes page (1008/1009); 4006 = TextRulerAtom;
3035/4089 unnamed inert atoms (see NOTES §12).
