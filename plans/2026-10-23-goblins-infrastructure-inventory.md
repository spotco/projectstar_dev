# Goblins RPG 3 — Port Infrastructure Inventory for ProjectStar Reuse

Date: 2026-10-23 (audit of HEAD)  
Repo audited: `~/workspace/dev/goblinsrpg3_dev` — **read-only in this pass, not modified**  
Git: **73 commits** (count in task brief; `git log --oneline --all | wc -l` in this checkout returned 73 lines before truncation in tool output — first `0ea772b Add original Goblins RPG 3 source and port plan`, last `3827854 Use goblinsrpg3 project icon as site favicon`)  
Source deck: `goblins3 v.1.0 LAUNCH.pps` — PowerPoint 97-2003 / OLE binary, SHA-256 `5EF9EF5169B09119FD3E9CD7015FC8F25FF78BF104041CBC1EBBCA13BE45FA93`, **201 slides, 4:3, 5760×4320 source coords → 720×540 stage**  
Purpose: what ProjectStar (newer PPTX format, extra features) can copy verbatim, what must be re-parameterised, and what must be thrown away / rewritten.

> **Critical format warning for ProjectStar:** Goblins is a **binary `.pps` (OLE/MS-PPT)** deck. Almost every extractor below is a hand-rolled OLE record parser + Apache POI HSLF audit, *not* a `python-pptx`/OOXML parser. ProjectStar is `.pptx` (ZIP/OOXML) — the *concepts, runtime, manifest schema, advancement policy, animation scheduler, and all bug lessons transfer*; the *binary parsers do not*. For ProjectStar you will write OOXML equivalents (`ppt/slides/slideN.xml`, `ppt/slides/_rels/*.rels`, `p:timing`, `p:transition`, `a:hlinkClick`) that emit **the same manifest JSON shapes**, so `docs/app.js` can be reused with minimal change.

---

## 1. Pipeline — steps in order

Canonical rebuild list is in `README.md` § “Rebuild generated data”. Order matters: later steps consume `generated/` outputs of earlier ones. Serving is independent.

### 1.0 Prerequisites / one-time

```bash
python3 -m venv .venv
.venv/bin/pip install -r tools/requirements.txt   # olefile>=0.47, Pillow>=12.0 only
# + portable JDK 21 + Apache POI 5.2.3 in _port_analysis_tmp/ (gitignored, see POI_EVALUATION.md)
# + ffmpeg on PATH (audio), Playwright + Chromium (only for verify_*_combat / limit tests)
# Compile POI audit:
#   javac -cp "_port_analysis_tmp/poi-*/..." tools/poi/PoiAudit.java  →  java PoiAudit "goblins3 v.1.0 LAUNCH.pps" > generated/poi_audit.tsv
```

No Aspose, no LibreOffice, no Office on the publish path (`RENDERING.md`). LibreOffice/PowerPoint was only ever an *oracle / debug lens*: `source/goblins3_v.1.0_launch-pptx.pptx` (1.2 MB, a converted re-export) is checked in as a **debug lens only** — its slide file number == presentation order, its `p:transition` names and hyperlink targets are cross-checked against the binary oracle. It is **not** an input to extraction. For ProjectStar, which *starts* as PPTX, that lens becomes the primary source — invert the relationship, keep a `.pps`-style DocSummary check if a binary original exists.

### 1.1 Inventory / binary extraction — `extract_ppt.py`

```powershell
python tools/extract_ppt.py "goblins3 v.1.0 LAUNCH.pps"
# in:  .pps OLE streams (PowerPoint Document, Pictures, \x05DocumentSummaryInformation, \x05SummaryInformation)
# out: generated/inventory.json (652 KB) — slides, presentation {5760×4320,4:3},
#      assets[] extracted to generated/assets/asset-NNN.png (PNG blip 0xF01E verbatim, DIB 0xF01F → BMP header → PNG via Pillow),
#      interactive_actions[217], hyperlinks[194], text (TEXT_CHARS 4000 / TEXT_BYTES 4008), record_type_counts
# also: SlideListWithText (4080) / SlidePersistAtom (1011) → slideId→order map; DocSummary hyperlink destinations (see §3.1)
```

Record constants baked in: `SLIDE=1006, SLIDE_ATOM=1007, INTERACTIVE_INFO_ATOM=4083, EX_HYPERLINK=4055, EX_HYPERLINK_ATOM=4051, SOUND=2022/2023, OFFICEART_SP_CONTAINER=0xF004, SP=0xF00A, CLIENT_ANCHOR=0xF010, CSTRING=4026`. Walks records recursively when `version==0xF`, tracking slide order + shape_id/bounds from OfficeArt containers.

### 1.2 Timing / transitions (legacy) — `extract_timing.py`, `audit_timing_tree.py`

```powershell
python tools/extract_timing.py            # → generated/timing_manifest.json (218 KB): 201 transitions (SSSlideInfoAtom) + 341 legacy AnimationInfoAtoms (4081)
python tools/audit_timing_tree.py "goblins3 v.1.0 LAUNCH.pps"  # → generated/timing_tree_audit.json: PP10 counts (see ANIMATION_EVALUATION.md)
python tools/verify_timing_tree.py; python tools/verify_poi_audit.py  # POI cross-check: 0 missing animation shapes
```

### 1.3 PP10 animation manifest — `extract_animation_manifest.py`

```powershell
python tools/extract_animation_manifest.py "goblins3 v.1.0 LAUNCH.pps"   # [--poi-audit generated/poi_audit.tsv]
# in: ___PPT10 SlideProgTagsContainer / RT_BinaryTagDataBlob per slide
# out: docs/animation-manifest.json (12 MB, format=goblins-rpg3-animation-manifest-v1) AND generated/animations.json (12 MB)
#     {format, source, slides:[{slide, sourceRecordOffset, recordCounts, builds[], rootTimeNodes[]}], summary}
# Decodes: ExtTimeNodeContainer hierarchy, TimeNode/Condition/Modifier/SequenceData/IterateData,
#   behaviors (animate/effect/motion/scale/set/command), variants/keyframes, ParaBuild (209: 208 asAWhole + 1 allAtOnce),
#   SubEffects (126, kept as node.subEffects — NOT hoisted), slide builds.
```

Counts proven in `ANIMATION_EVALUATION.md`: 197/201 slides with PP10 blobs, 2,407 ExtTimeNodeContainers, 2,533 TimeNodes, 2,093 TimeConditions, 478 TimeModifiers (3=accel,4=decel,5=auto-reverse), 1,004 behavior containers (18 animate, 291 effect, 215 motion, 3 scale, 466 set, 11 command), 6,078 TimeVariants, 1,022 visual targets (1,015 shape + 7 sound, 0 unresolved).

### 1.4 Layers — `extract_layers.py` (POI-dependent)

```powershell
# requires generated/poi_audit.tsv first
python tools/extract_layers.py
# in:  poi_audit.tsv (SHAPE/GEOMETRY/STYLE/PICTURE/CLIP/GEOTEXT/TEXT/TEXTSTYLE/PARAGRAPH/RUN/SLIDEBG rows),
#      generated/inventory.json assets, timing audit (animated target set)
# out: generated/layers.json (2.3 MB) + docs/assets/slide-assets/slide-NNN/shape-<id>.png (per-instance picture copies)
#     1,182 layers: 532 image instances, 465 text, 185 shape; 567 animated; wordArtGeometry, emptyTextPlaceholder (110),
#     normalize_ppt_text() mojibake repair (see §3.8), clean_geotext() strips +...+ WordArt markers
```

### 1.5 Embedded + linked audio

```powershell
python tools/extract_embedded_audio.py "goblins3 v.1.0 LAUNCH.pps"  # → generated/embedded-audio/sound-NNN-*.wav (5 embedded sounds) + manifest
python tools/render_midi.py    # library, not usually run alone: deterministic additive synth goblins-python-additive-v1, Ffvictory.mid → .rendered.wav (no FluidSynth/Timidity/soundfont)
python tools/convert_audio.py  # ffmpeg: *.wma (titlesong.wma, rocksong.wma) + generated/embedded-audio/*.wav + *.mid
                               #   → generated/audio/*.{mp3 (libmp3lame 128k), opus (libopus 96k)} + audio_manifest.json
                               # then build_game_manifest copies to docs/assets/audio/ (mp3+opus pairs, e.g. sound-001-bomb, titlesong)
python tools/verify_embedded_audio.py; python tools/verify_audio_cues.py
```

Root loose files in repo: `titlesong.wma`, `rocksong.wma`, `Ffvictory.mid` — linked, not embedded; do not assume they are inside the deck.

### 1.6 Reconstructed screens — `render_reconstructed.py`

```powershell
python tools/render_reconstructed.py [--slides 2,14-16]
# in:  generated/layers.json
# out: generated/reconstructed/slide-NNN.png (201 × 720×540) + generated/reconstructed/render_manifest.json
#      {rendererId: goblins-layer-reconstruction-v2, per-slide path/bytes/sha256/rendered-layer counts}
python tools/verify_render_manifest.py   # asserts 720×540, contiguous 1..201
```
Pillow compositing: solid slide background, picture layers (flip/rotate — PPT clockwise vs Pillow counter-clockwise, expanded canvas preserving centre), AutoShape polygons (`AUTOSHAPE_POLYGONS` for IRREGULAR_SEAL_1/2 etc.), text with Windows-font candidate chain (`C:/Windows/Fonts/{impact,ariblk,BROADW,arial,tahoma,times,segoeui}.ttf` → `ImageFont.load_default()` fallback — **Windows-path bug for Linux/macOS, see §4**).

### 1.7 Game manifest — the runtime contract — `build_game_manifest.py`

```powershell
python tools/build_game_manifest.py [--slides 2,14-16]   # --slides only limits PNG refresh; manifest always full
# in:  generated/inventory.json, layers.json, timing/transitions, animations, audio_manifest, media bindings,
#      generated/reconstructed/*.png, source_semantics
# out: docs/game-manifest.json (2.8 MB), docs/screens/slide-NNN.png (201), docs/assets/slide-assets/**, docs/assets/audio/**
#     {title, source{path,bytes,sha256}, presentation, startScreen:"slide-001", screenImageStatus:"custom_reconstruction",
#      layerStatus{...}, animationStatus{path:"animation-manifest.json",summary}, transitionStatus{count:201},
#      advancementPolicy{version:4,...}, audio[], audioCues[], mediaBindings[], screens[201]}
# Each screen: {id:"slide-NNN", slide:N, image:"screens/slide-NNN.png", hotspots[], advancement{}, layers[], backgroundColor, transition}
# Each hotspot: {id:"sNNN-a<record_offset>", shapeId, actionCode, action, soundRef, hyperlinkId, targetSlide, targetLabel,
#                label, enabled, clickable, behaviorStatus, resolveMethod, originalTargetSlide, binarySelfLink?, shapeText, bounds{x,y,w,h normalised, raw, clipped}}
# Each layer: {id:"slide-NNN-shape-<id>", slide, shapeId, zOrder, kind, name, bounds{x,y,w,h,points{x,y,w,h in 720×540 pts}},
#              animated, shapeType, transform{rotation,flipH,flipV}, placeholder, style{fillColor,lineColor,lineWidth,lineDash,...},
#              type:image|text|shape, text, wordArt, emptyTextPlaceholder, wordArtGeometry, geoText{unicode,fontFamily,rawUnicode},
#              textStyle{...insets...}, paragraphs[], textRuns[], instancePath}
# Uses tools/advancement_lib.py: resolve_self_hyperlink, resolve_explicit_noop, apply_residual_self_policy,
#   apply_media_residual_policy, combat_all_self_slide_ids, build_screen_advancement, terminal_kind_for_screen, shape_text_map
```

### 1.8 Semantics, reviews, advancement & playability reports (all under `generated/`)

```powershell
python tools/extract_source_semantics.py       # → generated/source_semantics.json (249 KB): stable IDs, master/layout flags, z-order, transitions, anim counts, audio cue status — hard-fails if slides != 201
python tools/generate_visual_review.py         # → generated/visual_review_checklist.json (96 KB, 201 screens, pending)
python tools/generate_gameplay_behavior_review.py # → generated/gameplay_behavior_review.json (169 KB): 217 actions = 194 nav + 7 clickable media + 1 zero-area media + 3 unresolved media + 12 noop
python tools/build_advancement_model.py        # → generated/advancement_model.json (529 KB)
python tools/analyze_start_graph.py            # → generated/start_graph_analysis.json (68 KB)
python tools/scan_advancement_coverage.py      # → generated/advancement_coverage_scan.json
python tools/build_offline_playability.py      # → generated/path_walk_report.json (771 KB), chapter_entry_map.json, promote_audit.json, clickable_contract.json (+ playability_graph.py shared lib)
python tools/build_combat_option_matrix.py     # → generated/combat_option_matrix.json (52 KB) — DocSummary vs pptx lens, mismatchCount=0 at ship
python tools/build_media_death_report.py       # → generated/media_death_residuals.json
python tools/build_chapter_walks.py            # → generated/chapter_walks.json + docs/chapter-entries.json (runtime, slim)
python tools/build_fidelity_reports.py         # → generated/sequential_advance_edges.json, auto_advance_timing.json, opening_animation_trains.json, motion_path_inventory.json (via motion_path_lib.py)
python tools/build_text_fidelity_report.py     # → generated/text_fidelity_report.json
python tools/audit_visual_risks.py             # → generated/visual_risks.json (211 KB, format v2, post-resolve)
python tools/analyze_opening_slides.py         # → generated/slide_1_10_feature_gaps.json
python tools/analyze_stuck_hyperlinks.py       # → generated/stuck_hyperlink_analysis.json; also hyperlink_pattern_analysis.json via related tools
python tools/audit_combat_interpretation.py    # → generated/combat_interpretation_audit.json
python tools/debug_slide.py N                  # → generated/debug/slide-NNN.json; debug_bundle.py N → generated/debug/bundles/slide-NNN/
```

### 1.9 Verification suite (gate, in README order — ~25 verifiers)

`verify_extractor_contract, verify_inventory, verify_timing_tree, verify_animation_manifest, verify_animation_player_contract, verify_layers, verify_animated_layer_coverage (567/567 animated targets have layers), verify_embedded_audio, verify_audio_cues, verify_gameplay_behavior, verify_site, verify_runtime_traversal, verify_advancement, verify_start_graph, verify_offline_playability, verify_fidelity, verify_visual_risks, verify_text_fidelity, verify_limit_combat (Playwright), verify_click_advance_combat (Playwright), verify_combat_visual_options (Playwright), verify_transition_effects, verify_render_manifest, verify_poi_audit`.

**Rule from PLAN.md:** after any manifest change, always re-run `build_advancement_model + analyze_start_graph + build_offline_playability`. After layer/text: `extract_layers → build_game_manifest → verify_text_fidelity/verify_visual_risks`. After animation extractor: `extract_animation_manifest → build_game_manifest → fidelity/player verifies`.

### 1.10 Serve

```powershell
python tools/serve_docs.py --port 8765 --directory docs   # ThreadingHTTPServer, NoCacheHandler: no-store/no-cache on every response
# → http://127.0.0.1:8765/   (GitHub Pages: publish docs/ from master, same tree, no server needed)
```

`generated/` full inventory (32 JSON + subdirs at audit): `advancement_*.json, animated_layer_coverage.json, animation_player_contract.json, animations.json, auto_advance_timing.json, chapter_entry_map.json, chapter_walks.json, clickable_contract.json, combat_*.json, extractor_contract.json, gameplay_behavior_review.json, hyperlink_pattern_analysis.json, inventory.json, layers.json, media_death_residuals.json, motion_path_inventory.json, opening_animation_trains.json, path_walk_report.json, poi_audit.tsv (503 KB), promote_audit.json, runtime_traversal.json, sequential_advance_edges.json, slide_1_10_feature_gaps.json, source_semantics.json, start_graph_analysis.json, stuck_hyperlink_analysis.json, text_fidelity_report.json, timing_manifest.json, timing_tree_audit.json, visual_review_checklist.json, visual_risks.json` + `assets/, audio/, debug/, embedded-audio/, reconstructed/, slide-assets/`.

---

## 2. Runtime architecture — `docs/` (static, no backend, browser never loads the .pps)

```
docs/
  index.html          42 lines — shell only
  app.js              5,173 lines — entire runtime, no framework, no build step
  styles.css          716 lines
  game-manifest.json  2.8 MB (see §1.7)
  animation-manifest.json 12 MB (lazy-fetched, see loadAnimations)
  chapter-entries.json     slim runtime copy of chapter_entry_map
  DEBUGGING.md        runtime + offline debugging playbook
  favicon.png, assets/project/{goblinsrpg3_banner.png,goblinsrpg3_button.png}  (branding — goblins-specific)
  screens/slide-NNN.png    201 reconstructed composites
  assets/slide-assets/slide-NNN/shape-<id>.png   per-layer pictures
  assets/audio/*.{mp3,opus}                      converted audio (prefer mp3 on Apple/Pages — commit f4a2886)
  assets/title/                                  title-redesign assets (goblins-specific)
```

### 2.1 `index.html`

`<main.game-shell><section.stage-wrap><div#stage.stage[data-loading]><img#screen.screen><div#layers.layers><div#missing-render hidden><div#hotspots.hotspots></div></section><nav.control-strip><button#restart><button#mute><output#status></nav></main>` + inline cache-bust bootstrap: `styles.css?no-cache=<Date.now()>` and dynamically appended `app.js?no-cache=…`. Title/favicon hardcoded “Goblins RPG 3” / `goblinsrpg3_button.png`.

### 2.2 `styles.css`

Dark theme vars, `.stage{aspect-ratio:4/3; width:min(100%,(100vh-72px)*4/3); container-type:size}` (font sizing uses container units via `point*ToContainer` in JS), `.screen.png-underlay{z-index:0}`, `.layers{z-index:1}`, hotspot, WordArt (`.wordart-layer{background:transparent}`, `.wordart-deflate/curve-*` + SVG `paint-order:stroke fill`), `.empty-text-placeholder`, `.layer.hybrid-png-text-hidden{visibility:hidden}`, `.layer.residual-combat-option{opacity:.45}`, `.pure-green-placeholder` (see §3.7), Debug HUD + collapsed chip, combat overlay, and **slide-transition keyframes** (see §2.7). All deck-agnostic except colours/fonts/branding.

### 2.3 `app.js` — structure

**Config / boot:**
```js
const RUNTIME_CONFIG = Object.freeze({loggingEnabled:false, debugCssEnabled:false, hudEnabled:false});
parseRuntimeQuery() // ?debug=1 → logging+css+hud; ?log=1, ?hotspots=1, ?hud=1 individually; ?slide=N → startSlide (floor, >0)
const RUNTIME_QUERY, ASSET_CACHE_BUSTER=String(Date.now()); assetUrl(path) // appends ?no-cache= / &no-cache=
state = {manifest, screens:Map<id,screen>, current, muted, audioUnlocked, audioElements:Map, mediaBindings:Map,
  pendingAudioCommands[], animations, animationSlides:Map, animationQueue[], pendingAfterEffectHides[], animationTimers[],
  transitionTimers[] /*separate bucket — critical, §3.3*/, animationTriggerWaiters:Map, animationStarted/CompletedNodes:Set,
  currentLayerElements:Map<shapeId,el>, debug, logging, hudEnabled, startSlideOverride, lastRenderDecision, lastInteraction,
  playthroughHistory[], selectedDebugLayerId, logSequence, animationTimerSequence, autoAdvanceTimer, chapterEntries}
```
Boot: fetch `game-manifest.json` (no-store) → build `screens` Map → `prepareAudio()` → `navigateTo(startScreen or ?slide override)` → lazy `loadAnimations(manifest)` (fetches `animationStatus.path`; on late arrival re-runs `setupAnimations` + `renderHotspots` so animated-continue gating applies — a race that caused bugs, see §3.5). Per-load cache-busting on scripts/styles/manifests/images/audio + server no-store headers = “refresh always fresh” (commit `cb1cca2`).

**Key functions by area (name → purpose):**

- *Navigation/render:* `screenId(n)→"slide-NNN"`, `navigateTo(id,interaction)`, `renderScreen(screen)` (decides layers vs hybrid vs PNG, sets background, calls renderLayers/renderHotspots/setupAnimations/applySlideTransition/scheduleAutoAdvance), `screenNeedsPngUnderlay(screen)`, `positionLayerElement`, `applyLayerVisualStyle/Transform`, `applyAutoShapeGeometry`, `renderHotspots(screen)`, `handleHotspotAction(hotspot)`, `handleStageClick()`, `nextSequentialScreenId`, `screenAllowsStageClickAdvance/AutoAdvance`.
- *Layers/text:* `mountWordArtPathWarp, wordArtWarpPathD, wordArtDeflateGuides, cubicBezierPoint, applyTextLayerStyle`, `AUTOSHAPE_CLIP_PATHS` + `autoShapeClipPath`, `cssColorFromPpt` (8-digit hex → rgba), `pointWidth/Height/FontToContainer`.
- *Animation scheduler:* `setupAnimations(screen), advanceAnimation(), runAnimationNode(node,baseDelay,allowClickNode,allowTriggeredNode,autoplay,iterateContext), scheduleChildNodes, scheduleSubEffectNodes, collectAnimatedShapeIds, collectEntranceHiddenShapeIds, motionPathStartsNearOrigin, nodeDuration/Timing/SequenceData, subtreeDuration, nodeOnEndDelayMs, animationTimelineForScreen, scheduleAnimation` (timer registry)`, applyBehavior → applySet/Effect/Animate/Motion/Scale/CommandBehavior, targetsFor, revealAnimationElement, syncHotspotsForShapeVisibility/AllAnimatedHotspots`.
- *Motion:* `tokenizeMotionPath, parseMotionPath, densifyMotionPath, sampleMotionPath(path,48), pointOnCubic, motionEndpoint, motionTranslate, applyMotionBehavior` — arc-length M/L/C sampling, WAAPI keyframes, endpoint preserved. Mirrored offline in `tools/motion_path_lib.py` (215 paths: 173 line, 42 cubic).
- *Iterate:* `iterateKind/IntervalMs, splitIterateText, ensureIterateUnits, prepareIterateTargets, animateIterateUnitFade/Scale, applyBehaviorToIterateUnits, buildIterateContext`.
- *AfterEffect:* `isAfterEffectNode, isHideOnNextClickAfterEffect, queueHideOnNextClickAfterEffect, applyHideOnNextClickAfterEffectNow, flushPendingAfterEffectHides`.
- *Gating/drain:* `isEmptyClickAdvanceNode/nodeSubtreeHasBehaviors, isMediaCommandOnlyNode, isNonGatingClickAdvanceNode, drainNonGatingAnimationNodes, fireMediaCommandsInSubtree, screenShouldAutoplayAnimations, hotspotLooksLikeMenuOption/ContinueOrMedia`.
- *Audio:* `unlockAudio (first gesture), prepareAudio, playAudioSource(source,startSec,behavior), stopAudio/Except, flushPendingAudioCommands, applyCommandBehavior (playFrom(N) parsing), updateAudioMute`. Preference order in `prepareAudio`: mp3 preferred on Pages/Apple (f4a2886), opus alternative present in manifest.
- *Transitions:* `applySlideTransition, transitionEffectClass/DirectionClass, transitionDuration, finishSlideTransition, scheduleTransitionTimer, clearTransitionTimers/ClearSlideTransitionClasses`.
- *Debug:* `runtimeLog("[GoblinsRPG3] …"), dumpScreen, collectRuntimeProblems/listProblems, buildCombatSlideAnnotation/inferSlideRole/extractSlideHpHints/hotspotOptionSummary/animationBehaviorSummary, ensureDebugHud/updateDebugHud/setDebugMode, loadChapterEntriesIntoSelect, load/persist/pushPlaythroughEvent/history, ensure/updateCombatDebugOverlay, set/toggleHudCollapsed`.

**Global debug API (`window.goblinsRpg3Debug`):** `goto(n|"slide-NNN"), dumpScreen([n]), listProblems(), snapshot(), history([n]), clearHistory(), combatAnnot([n]), setDebugMode({logging,css,hud}), toggle(), setEnabled(bool), toggleHudCollapsed(), setHudCollapsed(bool)`. Storage keys (rename for ProjectStar): `goblinsRpg3.debugHistory` (sessionStorage, ring 100), `goblinsRpg3.debugHudCollapsed`.

### 2.4 Screens, layers, hotspots — rendering decision

1. If screen has layers: render addressable HTML layers (image `<img>`, text `<div>` with runs/paragraph styling, shape `<div>` with fill/line + clip-path, WordArt SVG) positioned by normalised bounds, z-order = PPT zOrder, hotspot buttons inherit layer zOrder (fix for overlapping OPTION boxes, §3.5).
2. **Hybrid PNG underlay:** `screenNeedsPngUnderlay(screen)` — if layers exist but coverage is sparse, keep `docs/screens/slide-NNN.png` visible *under* layers (`screenImage.hidden = renderedLayers && !pngUnderlay`). Text already baked into PNG is hidden on live layers via `.hybrid-png-text-hidden` + WordArt hole masks (`applyPngUnderlayWordArtHoles`) to avoid double-text. **Exception:** returns `false` when a large animated text layer (area ≥0.35) exists — s201 credits crawl would otherwise double-scroll.
3. If no layers / missing render: PNG only, or `#missing-render` “Screen render pending”.
4. Media/speaker shapes: hidden — PPT `display="0"` media nodes and yellow speaker bitmaps must never paint (`hideMediaSpeaker…` logic, f4a2886); a mapped media hotspot is a transparent button, not the speaker icon.

Hotspots are `<button>`s absolutely positioned from `bounds{x,y,w,h}`, `stopPropagation` (always first consumer of a click), disabled/non-clickable when `clickable==false` (residual self / unresolved media / zero-area). Animated-shape hotspots start `pointer-events:none` until `revealAnimationElement`/set-visible for that shape (§3.5).

### 2.5 Animation scheduler (the hardest reusable piece)

- Data: `animation-manifest.json` → `animationSlides: Map<slide, {rootTimeNodes[]}>`. Each node: `{id:"sNNN-tnNNNN", kind, timeNode{restart,nodeType,fill,durationMs,flags}, conditions[{triggerEvent,delayMs,targetId}], modifiers[{accel,decel,autoReverse}], sequence, iterate, targets, behaviors[{kind,variants,keyframes,...}], subEffects[], children[]}`.
- On slide entry `setupAnimations`: compute entrance-hidden set (targets of set/effect entrances, *excluding* motion-only origins near (0,0) and exit-only shapes), pre-hide them, queue click-triggered (`triggerEvent 9=OnNext / 10=OnPrev`) roots in `animationQueue`, auto-run non-click roots with delays, chain `OnBegin(1)/OnStart(3)/OnEnd(4)` via `animationTriggerWaiters`.
- `advanceAnimation()` (stage click, first consumer): pops next OnNext node; if node is an OnNext *sequence container*, runs its **first child on the same click** (s003 fix); drains empty/non-gating nodes in-line and returns `false` if only those drained, so the same physical click can fall through to hyperlink/stage-advance.
- Behaviors via WAAPI (`element.animate`) + CSS transitions: `set` (visibility), `effect` (fade/dissolve/blinds/box — in *and* out, using TimeEffectBehaviorAtom transition flag), `animate` (numeric `ppt_x/ppt_y/#ppt_*`, `calcMode=1` linear + accel/decel modifiers + auto-reverse + hold/restart), `motion` (sampled path), `scale` (little-endian float decode from hex variants), `command` (`playFrom`, stop-audio event 11).
- Timeline estimate `animationTimelineForScreen` mirrors offline `tools/animation_timeline.py`; auto-advance delay = `max(slideTimeMs, timeline)`.
- SubEffects run *with* parent via `scheduleSubEffectNodes`; `nodeDuration/subtreeDuration` include them; OnEnd emission waits for **children, not OnEnd-waiting subEffects** (§3.3).

### 2.6 Audio

Manifest `audio[]` (converted files), `audioCues[]`, `mediaBindings[] {id:"slide-NNN-shape-<id>", cueId/source, status:mapped|unresolved, cueBehavior{trigger,startOffset,loop,stop,replace}}`. Embedded WAV cues are referenced from timing-tree command behaviors and InteractiveInfo media actions (actionCode 6). Runtime: one `HTMLAudioElement` per source in `audioElements`, first-gesture unlock (autoplay policy — queue commands in `pendingAudioCommands` until unlocked, then `flushPendingAudioCommands`), `playFrom(N)` seeks, stop/replace honoured where atoms expose it. Loop/stop/replace edge cases are explicitly **open** in PLAN §5.10. Three legacy cue IDs (3/4, slides 54/96/193) are *unresolvable* — documented non-clickable, no invented sounds.

### 2.7 Transitions

Source: SSSlideInfoAtom per slide (POI-validated) + pptx `p:transition` lens. **Correct mapping for this deck (fix 8d03732, verified by `verify_transition_effects.py` asserting PPS↔pptx counts):**

| SSSlideInfoAtom effectType | OOXML name | CSS class/keyframe in styles.css |
|---|---|---|
| 3 | checker(board) | `slide-checker-in` (contrast/scale approx) |
| 11 | zoom | `slide-zoom-in` (scale .2→1) |
| 21 | comb | `slide-comb-in` (clip-path polygon sweep) |
| 22 | newsflash | `slide-newsflash-in` (scale/rotate pop) — **was wrongly wipe** |
| 23 | fade | `slide-fade-in` |
| 27 | circle | `slide-circle-in` (clip-path circle) |
| — | cut | none / immediate |

Prior CSS wrongly mapped 22→wipe and 11→push. Runtime: `applySlideTransition` adds `.is-transitioning.transition-effect-N[.transition-direction-*]` to `#stage`, `--transition-duration` from atom speed/duration, cleanup on a **separate `transitionTimers` bucket** so late animation boot cannot cancel it (§3.3). Directions/speed are in manifest `screens[].transition`.

### 2.8 Advancement — stage-click continuum (data-driven, no slide-number hardcodes in the *policy*)

Per-screen `advancement` block (policy **v4**, from `advancement_lib.build_screen_advancement`):

```
{modes[], stageClickAdvancesSlide, stageClickResolveMethod, autoAdvance, autoAdvanceDelayMs,
 nextSequentialSlide, nextSequentialId, onNextConditionCount, leavePaths[], stuckReason, deathTerminal, terminalKind, terminalNotes}
```

Stage click order (`handleStageClick`): ① unlock audio → ② if OnNext queue non-empty, `advanceAnimation()` → ③ else if `stageClickAdvancesSlide` (PPT `manualAdvance` bit, or documented interstitial fallback) → next sequential → ④ else no-op. Hotspots always pre-empt (stopPropagation), *except* the deliberate bypasses in §3.5.

Deck totals at ship: 59 auto-advance, 14 stage-click-advance (9 manualAdvance + 5 interstitial fallbacks), 0 stuck leave-paths, 202 manifest hyperlinks (194 binary + 8 noop promotes). **Leave-path stuck==0 ≠ playable from title** — start-directed reachability was 29 before the DocSummary fix, 193 after (§3.1); Tier B is via chapter select, not invented bridges.

### 2.9 Debug HUD & deep links

`?debug=1&slide=N` is the universal QA entry: logging (`[GoblinsRPG3]` prefix), hotspot outlines, HUD (screen id/slide, render decision, advancement modes + autoTimer, animation queue, pending AfterEffect hides, problems, combat annotation, history last 8, selected-layer detail, Chapters `<select>`+Go fetching `chapter-entries.json`), combat overlay (top-left, `pointer-events:none`), layer click-to-select (cyan outline). HUD shell is `pointer-events:none` — only buttons/selects/header re-enable — and capped `max-height:min(48vh,100vh-120px)` (fix eb3a513: HUD was covering first-combat Attack/Flee). Collapsible to a `▸ Debug` chip, ≥44 px, persisted per-tab. `?slide=N` only sets the boot slide — auto-advance slides still leave after `max(slideTime,timeline)`.

Offline debug mirrors: `debug_slide.py / debug_bundle.py / probe_mechanic.py {wordart,hotspots,animation,media,background,pictures,all} / debug_lib.py` — compare **extract → manifest → runtime decision**, not pixels alone.

---

## 3. Bug / fix lessons — grouped by theme (NOTES.md + PLAN.md + git log)

Commit hashes below are from `git log` / NOTES.md citations in the audited tree.

### 3.1 Hyperlink resolution — the single biggest lesson

- **ExHyperlink labels are stale; DocSummary slideId is the oracle (8d03732, NOTES 2026-09-13, overturns months of work).** The CString `"Slide N"` in an ExHyperlink record is a *friendly name frozen at authoring time*. 75/194 labels were stale after slide reordering. Real destinations: `\x05DocumentSummaryInformation` stream, UTF-16 entries `"slideId,staleNum,Slide staleNum"`, paired **1:1 in order** with ExHyperlink records, resolved `slideId → presentation order` via SlideListWithText/SlidePersistAtom. Implementation: `extract_ppt.DOCSUM_HLINK_RE`, `build_slide_id_to_presentation_order()`, `parse_docsum_hyperlink_destinations()`. Effect: s002 start→3 (was self), s042→**22** not 21, s046→47 natively (promote no longer needed), start reachability **29 → 193**, sealed islands → 0. **For ProjectStar/PPTX:** the analogue is *never trust link display text / `slideN.xml` filename order* — resolve `r:id → _rels → target slide → its `p:sldIdLst` position*. Filename number ≠ presentation order in reordered PPTX decks, for exactly the same reason.
- **No target overrides, ever (db303a4, b1cc0e7→reverted, 9c34cdd→reverted).** A `USER_AUTHORIZED_TARGET_OVERRIDES` / Pass-4 remap table (e.g. flee-fail Continue s017→32 to preserve goblin count, s015 Flee→17) was built from remembered play, then **removed completely**. Policy now: binary (here: DocSummary + InteractiveInfoAtom + POI TEXTLINK) is oracle; if memory conflicts with binary, fix *interpretation*, document the conflict, do not remap. Irreducible conflicts documented verbatim in NOTES (boredom≠kill, opening Attack≠kill-ladder, flee-fail Continue→22 drops ×2→×1) with an exhaustive falsification audit (`audit_combat_interpretation.py`: SSSlideInfoAtom bits, ExtTimeNode targets, InteractiveInfo parents — mouse-click instance 0 for all combat options, multi-info/shape = 0, `"Slide 23"` string absent from Document stream, orphan s023 has no inbound).
- **Self-links: promote only with provenance, or document as residual.** Pre-DocSummary policy (advancement v4, still the fallback logic in `advancement_lib.resolve_self_hyperlink`): `self_continue_to_next` (continue/start text, sole leave), `sole_image_self_to_next`, `combat_all_self_to_next_outcome` (s046: *every* option self → next; partial combat selfs are **not** bulk-promoted). Residuals (`s015/s027/s039` combat, `s050/s052` hub image): `residualStatus=accepted_source_self`, non-clickable *when another leave exists*, rationale on the hotspot; later s015 Flee became `residual_self_reload` — clickable, re-enters itself (PPT self-hyperlink semantics, timer resets) because muting it diverged from PPT (f6186e0 line). Manifest must carry `originalTargetSlide, resolveMethod, resolveRationale, binarySelfLink` on every promoted hotspot; `generated/promote_audit.json` must be regenerable and `verify_visual_risks` must show **0 clickable self-links**.
- **Explicit-noop (`action=none`, code 0) controls (Phase 2, 48af3b7).** Labeled noops that should navigate: `noop_continue_to_next` (sole continue: s155/s158/s163 → next) and `noop_mirror_sibling_hyperlink` (continue text matches a sibling control: s051; combat: s150 `-limit`→167, s156/s159/s164 `-attack`→ sibling). **Same-shape noop trap (NOTES 2026-09-13 Limit):** a noop record on the *same shape* as a real hyperlink must stay `explicit_noop` (not rendered) — mirroring it emitted **two stacked buttons** for one control. `noop_mirror` is now reserved for *different-shape* siblings; none remain. Empty-text noops (s010/s012/s014/s036) are decorative — real continue is another hotspot, accept.
- **Stale-label symptom pattern:** a “closed loop / sealed island / zero-inbound root” graph (29 reachable, islands s043–s054 and s020–s025, 18 zero-inbound roots) was an *extraction* bug, not authored design, until proven otherwise. Do not invent title→midgame bridges (s042→…) without a PPT-UI oracle or misparse proof (PLAN Phase 4, still open). Chapter entries were the honest Tier-B workaround *while* the graph was broken — see §4 for which chapter entries survive the fix.
- **Hotspot↔shape mapping was not the bug:** POI TEXTLINK + inventory agreed on every early-combat shape→target (s015 Attack shape 17419, hlId 62, jump=NoJump). Debug *role inference* was: `inferSlideRole` used the caption `CAN'T ESCAPE` alone, so Attack→s018 (which reuses that caption + attack motion paths) read as “flee-fail”. Fix: prefer inbound option labels (`attack-result` vs `flee-fail`).

### 3.2 Animations — general scheduler

- **OnNext empty nodes are dead clicks (61e35cc, 02ffbff).** Root-sibling OnNext nodes with 0 behaviors/children in their whole subtree (Display/MediaVolume variant placeholders) queued and swallowed a click. Fix: `isEmptyClickAdvanceNode / !nodeSubtreeHasBehaviors` — `advanceAnimation` **drains** empties in-line and returns `false` if only empties drained, so hyperlink/media fires on the *same* click. Deck scan: **11 empty OnNext nodes** — s002-tn0007, s013-tn0007, s014-tn0040, s030-tn0013, s054-tn0018, s074-tn0014, s081-tn0017, s096-tn0018, s104-tn0007, s193-tn0011, s197-tn0013. Expected after fix: s002 start leaves in 2 clicks (media + hyperlink), not 3. General rule, not slide-2-only.
- **OnNext sequence first-child (cecd36b, s003).** Clicking an OnNext *sequence* only enqueued its builds — first click looked dead. Fix: `scheduleChildNodes(...,allowClickNode)` runs the first child on the same click. s003: click1 → “100 to 150 years ago…”, 2 → peace, 3 → Until…, 4 → s004.
- **Non-gating nodes (dee5143).** Media-command-only OnNext nodes (`playFrom` BGM) must not gate navigation: sync-fire / autoplay on entry for continue-like slides, drain as side-effects on a hyperlink click. Title then leaves in **1 click** with `audio:play` logged.
- **Duration-0 parents emit OnEnd too early (2026-09-11 s015).** An effect-group with `durationMs=0` emitted OnEnd at 1 ms, running AfterEffect hide before its 500 ms motion child — standing goblin invisible. Fix: `nodeOnEndDelayMs` waits for **children** (not OnEnd-waiting subEffects).
- **Pre-hide discipline (4485b53, 738f34c, ae0163c).** Entrance pre-hide must be selective: (a) fly-in/motion targets whose path origin is far from (0,0) *are* pre-hidden; (b) motion-only counter goblins whose path starts ≈(0,0) (s023/s025/s032) must **stay visible** — pre-hiding all motion targets left them invisible until the path ran; (c) **exit-only** shapes (s019 goblin, blinds exit) must not be entrance-pre-hidden — an exit preset hidden by the entrance pass never appeared to be killed. `collectEntranceHiddenShapeIds` + `motionPathStartsNearOrigin` encode this.
- **Autoplay policy flip-flopped — learn the final state (f6186e0 → 76f159e reversal).** Removing continue-only autoplay made Attack land on entrance-hidden layers (blank slide, green debug boxes). Final: `screenShouldAutoplayAnimations` = **true for continue/result/media-only beats and for PPT `autoAdvance` slides; false for menu slides** (Attack/Flee menus stay click-gated). But autoplay must *never auto-navigate*: 29/30/31 result beats animate in-slide, slide change still requires the continue hyperlink (9b13ce9 data-driven auto-advance restored separately, only when `advancement.autoAdvance`).

### 3.3 Animations — AfterEffect hide

- **Hide-on-Next-Click is a SubEffect, not a node flag (0f267a6, 3f3d697, PLAN 5.2).** Encoding: `RT_TimeSubEffectContainer` with TimeProperty AfterEffect (TPID 13)=true, Display=1, MasterPos=2, behavior `SET style.visibility=hidden`, *no* OnEnd condition. Runtime: defer into `pendingAfterEffectHides`, on next OnNext apply **synchronously before** the next entrance (`applyHideOnNextClickAfterEffectNow`: cancel WAAPI + `visibility:hidden` + `opacity:0`). Without it, s003 narrative captions (shapes 3079→3077→3078, near-identical bounds) stack.
- **OnEnd AfterEffect target-ID mismatch (NOTES s194, 073652a).** Extracted OnEnd `targetId` is the OOXML cTn id, while `emitAnimationTrigger` keys on extract serial — hide never fired, dissolved white STAR_4 shapes stacked over art. Fix: bind mismatched OnEnd hides to parent entrance end **+32 ms** and apply via the same hard-hide path; also race with dissolve `finishIn` at the same ms had to be ordered.
- **Transition-timer race (3f3d697).** Late `setupAnimations` (async animation-manifest load) cancelled the slide-transition cleanup, leaving `#layers` at opacity 0 on `?slide=` deep links (s003/s005). Fix: separate `transitionTimers` bucket, never cleared by animation code.

### 3.4 Animations — motion paths, effects, iterate

- **Motion paths: endpoint-only is wrong (PLAN 5.4, 6a45151).** Runtime now `parseMotionPath/sampleMotionPath/densifyMotionPath`: tokenise VML-like `M/L/C`, arc-length densify cubics (16 steps/cubic offline, 48 WAAPI keyframes default runtime), preserve exact endpoint. 215 paths deck-wide. No rotation/color/filter animate variants exist in this deck — do not build them speculatively. Residual: path progress vs accel/decel easing coupling is approximate (5.4.1).
- **Effect stubs hide kills (ae0163c, s019).** Anything except fade/dissolve was stubbed as `effect-skipped`. Goblin death is `presetClass=exit, blinds(horizontal)` + hide-after ~500 ms. `applyEffectBehavior` now honours the TimeEffectBehaviorAtom in/out flag and plays blinds / box(in) / fade / dissolve **out** as well as in. `verify_transition_effects` also asserts image effect filters.
- **Iterate / byLetter (1863a04, 073652a, PLAN 5.2.1).** Only **2** `TimeIterateData` nodes deck-wide (both byLetter: s001 “Presents”, s183 caption). Implementation: split text into unit spans at extract/runtime, stagger fade/grow. **Bug (s183):** units created at `opacity:0` for stagger, but set-visible only flipped `visibility` when `opacity===""` — letters stayed invisible inside the white box. Fix: iterate set-visible → `opacity:1` (hidden→`0`). ParaBuild: 209 builds, 208 `asAWhole` + 1 `allAtOnce` — whole-shape handling is PPT-correct here; do not build paragraph-split scheduling until a deck actually authors it.
- **SubEffects must stay subordinate (PLAN 5.2).** Early extractor hoisted 126 SubEffects into parent behaviors/conditions — wrong timing/visibility. Keep them as `node.subEffects`, schedule with parent, include in duration/timeline.

### 3.5 Combat / hotspot gating

- **Animated continue hotspots gate until reveal; menu options do not (6d20c0e).** “Click here to continue” on an animated shape starts `pointer-events:none`; `revealAnimationElement`/set-visible enables it, and late animation-manifest boot re-renders hotspots. Attack/Flee (non-animated OPTION text) are **immediately** clickable. Without the split, early clicks either skip the dissolve or feel dead.
- **Hyperlinks bypass OnNext for navigation, not for builds (dee5143, cecd36b).** Title start and Attack/Flee must not be “stolen” by a pending OnNext queue (boredom title on s016 consumed Attack). Drain non-gating/empty/media nodes, fire the hyperlink on the same click; keep genuine narrative builds click-gated on the *stage*, not on the hotspot.
- **Debug HUD stole combat clicks (eb3a513).** Gold hotspot outlines sat under the HUD; HUD covered bottom-right OPTION. Fix in §2.9 (pointer-events + max-height). Playwright tests that used `button.click()` / aria substring masked this — see §3.9.
- **Z-order in overlapping options (NOTES Limit).** Hotspots inherit layer `zOrder`; s190 Attack/Limit/Flee boxes overlap ~39 EMU — DOM order alone picks the wrong option.
- **Limit is not a gauge (4d4987a, NOTES 2026-09-13).** `00%` is decorative text. Limit exists only where the author placed a Limit hyperlink; outcomes differ per fight by design (kill / 25 dmg+counter / player death s046 / ending s190→194 stars). Deterministic matrix: `combat_option_matrix v2, mismatchCount=0` across web/DocSummary/pptx. Slides: s046→47, s079/s087→80, s092/s094→97, s112/s113→117, s119→146, s123/s156/s159→126, s142→143 (→144→30 death), s150→167, s153→162, s190→194. **Do not “fix” per-fight variance.**
- **Residual Flee UX (2e9ef5a, f6186e0).** A non-clickable muted Flee (`.residual-combat-option{opacity:.45,no underline}`) matched the *dead hit* but not PPT, where a self-hyperlink visibly reloads. Final s015 behaviour is self-reload (§3.1). Lesson: style a residual to match its *actual* runtime behaviour, whatever you choose, and assert it in a regression.
- **Boredom auto-advance is authored (s015).** SSSlideInfoAtom: slideTime 9000, flags `0x0400` autoAdvance, effectType 22. Auto-leave 15→16 drops asset-013 goblin count ×3→×2 and s016 text says so. s016/s021/s022 store slideTime 9000 with flags=0 — **stored time without the bit does not auto-advance** (also s194: 6000 ms, flags=0, `autoAdvance=false` — do not invent).

### 3.6 Audio / media

- **`playFrom` regex over-escaping (AGENT_TESTING WordArt section).** `applyCommandBehavior` used `\\(` / `\\d` in a RegExp literal — never matched, start offset always 0. Now parses `playFrom(N)` correctly (s002/s013/s014 bindings). Classic: test command parsing with a non-zero offset fixture.
- **First-gesture unlock + pending queue.** Browsers block audio before a gesture; commands fired during auto/boot animations must queue (`pendingAudioCommands`) and flush on unlock, or BGM silently never plays.
- **Speaker icons must not paint (f4a2886).** PPT media placeholder/speaker bitmaps (yellow speaker) are not slide art. Hide media-node shapes (`display="0"`), skip their bitmap layer, keep only the transparent hotspot. Also: **prefer MP3 over Opus for Pages/Apple** playback reliability; ship both.
- **Unresolved / zero-area media are documented residuals, not bugs to invent around (PLAN 2.7/2.8).** s054/s096/s193 cue IDs 3/4 absent from the embedded collection → `documented_unresolved_media`, non-clickable. s104 cue 2 mapped but zero-area bounds → `documented_zero_area_media`, non-clickable; timing-tree `playFrom` may still play it automatically.
- **MIDI needs a synth (b6143fe, 4b734b0).** Browsers cannot play `.mid`/`.wma`. `render_midi.py` is a deterministic, soundfont-free additive synth (44.1 kHz, max polyphony 96, GM-lite) — deliberately mediocre but reproducible; then ffmpeg → mp3/opus like everything else.

### 3.7 Rendering — reconstructed layers vs PNG, green placeholders

- **Chosen path: hybrid, not screenshot-only (c22360e, RENDERING.md).** Rejected: Aspose (watermark/cost), LibreOffice/Office export (not publishable/reproducible on Pages). Chosen: Pillow reconstruction from layers (`goblins-layer-reconstruction-v2`) as composite PNG **plus** live addressable layers **plus** transparent hotspots. Animation requires addressable layers; a baked PNG alone cannot be animated, and layers alone miss sparse/complex art.
- **Sparse hybrid underlay (442b4c7, PLAN 5.6/5.8).** Early rule “any layers → hide PNG” produced near-empty slides (s001 white+logo, s029/s032 sparse hills). Fix: `screenNeedsPngUnderlay` (§2.4); sparse-coverage risks demoted to `info` when a composite PNG exists. Conversely, large animated text (s201 crawl) disables underlay to avoid double-draw.
- **Double-text / double-draw (442b4c7, bb46cde).** Title s002: live WordArt + baked PNG text overlapped. Fixes: hide baked-text live duplicates (`.hybrid-png-text-hidden`, pointer-events preserved for hotspots), WordArt hole masks in the underlay, and eventually a bespoke s002 title treatment (landscape PNG carries logo/CTA; live layer suppressed for `screen.id==="slide-002"` in `app.js` ~line 2106 — **goblins-specific hack, see §4**).
- **Pure-green placeholders (2026-09-12 NOTES).** A few extracted pictures are ~100% Office palette green `(0,128,0)` — PPT chroma placeholders — shown as empty green boxes in debug/normal render. Fix: detect near-pure-green picture layers → `.pure-green-placeholder` (hidden). **Do not chroma-key in general:** the same green paints grass/hills/sprite art in mixed images. Debug outlines on `visibility:hidden` layers produced a *different* “empty green boxes” symptom on s018 — fixed by not outlining hidden layers. Two symptoms, one description; disambiguate before fixing.
- **Opening backgrounds / intro fade (442b4c7).** Slide solid fills (often white) come from POI `SLIDEBG`, not pictures; missing them gave wrong (black/transparent) opening slides. Intro fade was a transition-timer + background bug combined.
- **PNG-underlay hole / WordArt plate (a89551a).** WordArt `spPr` is `noFill` — runtime must keep `background:transparent` deck-wide. A white plate behind WordArt glyphs was a layer-style bug, not source art.

### 3.8 Transitions mapping

Covered in §2.7. Lessons: (1) map SSSlideInfoAtom effectType through the **OOXML/pptx names actually used in the deck**, not a generic textbook table — 22 is newsflash here, not wipe; 11 is zoom, not push (8d03732). (2) Validate counts PPS↔pptx exhaustively (`verify_transition_effects`). (3) A transition type with no CSS is silently “fade” — audit the full catalog present in the deck (only 3,11,21,22,23,27 + cut here) before shipping, not every PPT transition ever defined.

### 3.9 Text fidelity / encoding, AutoShape, WordArt

- **Mojibake map is deck-specific data, discovered empirically (PLAN 5.7, 6a45151).** POI HSLF mis-decodes Windows symbol chars: `Æ/æ→'`, `à/Ö→…`, `ô→“`, `ö→”`, `ù→:`. Implemented as `normalize_ppt_text()` in `extract_layers.py`, applied to layer text, runs, *and* geotext; verifier asserts **0 residual artifact chars** in published layers. **For ProjectStar/PPTX (UTF-8 OOXML) this map should be unnecessary — do not copy it blindly; instead copy the *verifier pattern* (scan published text for artifact chars) and build a map only if artefacts appear.**
- **WordArt text lives in geotext, not `getText()` (5983e50).** Escher `geotext.unicode` (with `+...+` markers) is the source; POI text is empty for WordArt shapes. Risk code `empty_text_wordart_unrecovered` flags this. Bounds/stroke recovery (32c503a): fill from `spPr`, stroke from line style, transparent fill (§3.7).
- **WordArt warps (bce2188, da9d850, AGENT_TESTING).** `TEXT_CURVE_UP` (s014 “Yip!”, shape 15382): SVG `<textPath>` on a quadratic arch (`M 0,cy+adj Q cx,cy-adj w,cy+adj`, adj≈h·0.46, av1≈45977). `TEXT_DEFLATE` (s002 “GOBLINSRPG3”, shape 2052): **dual-path** SVG warp — per-glyph `scaleY` from top/bottom cubic guides (adj default 18750), not a uniform CSS `scaleY`. `CURVE_DOWN/ARCH_*` wired through the same `mountWordArtPathWarp`. All other `prstTxWarp` presets (wave, inflate, chevron, fade, cascade, can, ring, stop…) are **not authored in this deck and not implemented**. Residual everywhere: glyph-along-tangent / per-glyph scale, not full OOXML dual-path contour mesh; font substitution (Arial Black/Impact) is approximate.
- **AutoShape clip-path (3417778, f372da2, NOTES world-map).** Geometric AutoShapes with empty text were classified as rectangles — IRREGULAR_SEAL explosions rendered as yellow rectangles, arrows as yellow boxes. Fix: 185 empty non-RECT presets → `type=shape`, runtime `AUTOSHAPE_CLIP_PATHS` (OOXML preset polygons: IRREGULAR_SEAL_1/2, ELLIPSE/OVAL, STAR_4, arrows, TRIANGLE, DIAMOND, PENTAGON, HEXAGON, PLUS/CROSS) + SVG stroke for LINE, stored in `dataset.autoShapeClip`. **Regression (f372da2 / world-map arrows s065/s084/s093):** `applyEffectBehavior.finishIn` *cleared* `clipPath` after every entrance — arrows were correct for ~500 ms, then became solid `#ffff00` rectangles. Fix: `finishIn` restores the AutoShape clip when `dataset.autoShapeClip` is set, `commitStyles+cancel` WAAPI so `fill:forwards` cannot retain a temporary inset/box clip. General lesson: **effect cleanup must restore, not clear, geometry properties owned by another subsystem.**
- **Empty text placeholders (PLAN 5.6).** 110 plate/textbox layers have empty text: flag `emptyTextPlaceholder`, hide non-animated empties at runtime, keep animated targets (they may receive text/effects). Do not delete them at extract — animation targeting breaks.
- **Low contrast is source art until proven otherwise (PLAN 5.9, open).** ~197 low-severity `low_contrast_text` rows in `visual_risks.json` — light text on light background as authored. No mitigation shipped; do not auto-darken.

### 3.10 Testing methodology lessons (from NOTES, as important as code lessons)

- **Click visual centres, not DOM nodes (2026-09-09).** `button.hotspot.click()` + `/attack/i` aria matching always hits Attack and can match “Goblin x3 attacked!”. `verify_combat_visual_options.py` mouse-clicks the exact visual centre of `^-?\s*attack$` / flee layer|button and fails if Attack lands on a distinct flee target. Any ProjectStar verifier must do the same for menu text.
- **Wait the full timeline before judging (2026-09-06).** Early “missing text/images” on combat slides was animation delay, not absence. Verifiers wait ~timeline + settle, and for the s016→17 flee regression, a long settle proving one click does *not* continue to s022.
- **Playthrough history is the user-bug-report format (dee5143).** `sessionStorage` ring buffer (§2.3) let a user session (`Attack → s018`, not flee) be recovered post-hoc and disproved a suspected remap. Ship history from day 1.
- **Offline-first gating (PLAN Phases 1–3).** Tier A was locked with zero browser playtest: path walker, clickable contract, promote audit, chapter walks. Browser/OCR QA is for *feel* (Tier C), not for rediscovering the graph.

---

## 4. Deck-agnostic (reuse verbatim / with renaming) vs goblins-specific

### 4.1 Reuse verbatim (only rename branding/keys)

| Asset | Notes |
|---|---|
| `docs/index.html` shell, `tools/serve_docs.py` | Change `<title>`, favicon. NoCacheHandler + cache-bust bootstrap are universal. |
| `docs/app.js` — scheduler core | `runAnimationNode/scheduleChildNodes/scheduleSubEffectNodes`, trigger waiters, WAAPI behavior appliers (set/effect/animate/motion/scale/command), motion-path sampler, iterate splitter, AfterEffect queue, empty/non-gating drain, autoplay policy, timer buckets, `assetUrl`, `parseRuntimeQuery`. Rename `[GoblinsRPG3]` log prefix, `goblinsRpg3Debug` → e.g. `projectStarDebug`, storage keys `goblinsRpg3.*`. |
| `docs/app.js` — render/hotspot core | Layer mounting, z-order, clip-path table (`AUTOSHAPE_CLIP_PATHS` is OOXML-standard, not goblins data), WordArt `textPath`/deflate warps, hybrid-underlay decision (including ≥0.35 animated-text exception), green-placeholder detector (threshold logic), speaker-icon hiding, hotspot gating/reveal, stage-click continuum, auto-advance `max(slideTime,timeline)`. |
| `docs/styles.css` | Except theme colours/fonts and the s002-specific title rules. Transition keyframes are reusable *as a mapping table keyed by OOXML name* — re-derive which types the new deck uses. |
| Manifest **schemas** | `game-manifest.json` / `animation-manifest.json` field shapes (§1.7/§1.3) — keep identical so runtime + verifiers port. Change `format` strings (`goblins-rpg3-animation-manifest-v1` → projectstar equivalent) in both producer and `loadAnimations`. |
| `tools/motion_path_lib.py`, `tools/animation_timeline.py`, `tools/render_midi.py`, `tools/convert_audio.py` (ffmpeg logic), `tools/extract_embedded_audio.py` *concept* | MIDI synth is fully generic. `convert_audio` source-glob defaults (`*.wma/*.mid` at repo root) need ProjectStar filenames. |
| `tools/render_reconstructed.py` *approach* + AutoShape polygons | Polygons are OOXML presets. Font candidate list is Windows-only — add Linux/macOS font paths for ProjectStar (see §5). |
| Advancement **policy engine** (`advancement_lib.py` logic) | manualAdvance/autoAdvance/terminal/residual/noop-mirror *algorithms*, with provenance fields. The *promote decisions* it encodes for specific slides do not transfer — re-derive from ProjectStar's graph. |
| All `verify_*.py` *patterns* | Extractor contract, layer coverage (animated targets ⊆ layers), traversal, clickable contract, visual-centre clicking, transition-count parity. Every hardcoded count inside them must be parameterised (see §4.2). |
| Debugging tooling | `debug_slide/debug_bundle/debug_lib/probe_mechanic`, HUD, `?debug=1&slide=N`, history ring buffer, DEBUGGING.md structure. |
| Offline playability suite | `build_offline_playability/playability_graph/build_chapter_walks/build_advancement_model/scan_advancement_coverage/analyze_start_graph` — graph algorithms generic; seeds/fixtures are not. |

### 4.2 Goblins-specific — do NOT copy (re-derive / delete)

| Item | Where |
|---|---|
| **All numbers “201”** | Hardcoded asserts in ~15 tools: `verify_inventory` (201 slides, record 1006 count), `verify_layers, verify_site, verify_advancement, verify_start_graph, verify_runtime_traversal, verify_offline_playability, verify_render_manifest (720×540, contiguous 1..201), verify_poi_audit, extract_source_semantics (201 slides/zOrder/transitions or exit)`. Also `extract_ppt` presentation `{5760,4320,4:3}` and `render_reconstructed` default `720×540`. ProjectStar: read slide count / size / aspect from the deck; parameterise verifiers from the manifest. A 16:9 ProjectStar deck breaks the stage CSS aspect-ratio too. |
| **Binary .pps parsers** | `extract_ppt.py` record parser, `audit_timing_tree/extract_timing/extract_animation_manifest` PP10 blob decoding, POI HSLF audit (`tools/poi/PoiAudit.java`, `generated/poi_audit.tsv` format consumed by `extract_layers`). For PPTX, replace with OOXML parsers emitting the same JSON. POI itself has a XSLF (PPTX) API — a new `PoiAudit` for XSLF is plausible, but the existing Java/TSV is HSLF-specific. |
| **Combat system** | `advancement_lib.combat_all_self_slide_ids` + s046 promote rationale, `build_combat_option_matrix, audit_combat_interpretation, verify_limit_combat, verify_click_advance_combat, verify_combat_visual_options`, `app.js inferSlideRole/extractSlideHpHints/combatAnnot` (Attack/Flee/Limit/Magic regexes, `goblin xN`, “takes N damage”), `.residual-combat-option` styling, NOTES combat matrices. ProjectStar may have no combat at all — keep only the generic “menu option matrix vs oracle, mismatchCount” pattern if it has menus. |
| **Chapter entries** | `docs/chapter-entries.json` (15 entries: tier-a-title s001, first-goblin-battle s014, roots 20/34/43/52/55/66/70/119/135/145/148/166/171), `generated/chapter_entry_map.json` seeds (1,43,55,…), HUD chapter labels. Rebuild from ProjectStar's zero-inbound/island analysis — *if* its (correctly resolved) graph even needs chapters. |
| **Slide-specific hacks & fixtures** | `app.js`: s002 title suppression (~l.2106), s201 credits underlay exception is generic-by-area but was tuned on s201, s190 overlap, s014/s019/s023 motion-origin lists in comments/fixtures. Tools: every `verify_*` fixture naming s002/s003/s015/s016/s017/s019/s046/s183/s194/s201, opening-trains slides (3–8,12–14), `analyze_opening_slides` (slides 1–10). |
| **Names / keys / branding** | `goblinsRpg3Debug`, `[GoblinsRPG3]`, `goblinsRpg3.debugHistory`, `goblinsRpg3.debugHudCollapsed`, `docs/assets/project/goblinsrpg3_{banner,button}.png`, favicon, `format:goblins-rpg3-animation-manifest-v1`, renderer id `goblins-layer-reconstruction-v2`, MIDI synth id `goblins-python-additive-v1`, CSS theme (Georgia, brown/gold palette). |
| **Audio inventory** | `titlesong.wma, rocksong.wma, Ffvictory.mid`, embedded `sound-001-bomb, sound-002-j0214098, sound-005-MSj00747560000-1, sound-007-MSSN00568A0000-1, sound-008-MSj03884740000-1`, `SOURCE_AUDIO_CUE_IDS` in `build_game_manifest.py` (`linked:titlesong/rocksong/Ffvictory`), unresolved cue IDs 3/4. |
| **Text data** | Mojibake map (`Æàôöù…`, §3.9), WordArt inventory (s002 TEXT_DEFLATE 2052, s014 TEXT_CURVE_UP 15382, 4 WordArt layers total), transition-type *set* (only 3/11/21/22/23/27 present), font usage (Impact/Arial Black/Broadway). |
| **Graph facts** | Start reachability 193 (post-fix), death terminals s030/s197, end card s200, loop s042→s021 (pre-fix label reading), all PLAN promote/residual tables. |
| **Workflow notes in NOTES.md** | “Agent/Grok Bot workflow: branch `grokbot-dev`, never merge to master, work on agent cloud computer” — that was that project's process, superseded for ProjectStar by the parent agent's instructions (repo policy in MEMORY: push to master, no leftover branches). Do not inherit it. |

### 4.3 Needs adaptation for ProjectStar's newer format (not just renaming)

1. **OOXML timing (`p:timing/p:tnLst, p:cTn, p:childTnLst, p:prevCondLst/nextCondLst, p:stCondLst/endCondLst`)** replaces PP10 blobs — richer and *documented*: presetClass/presetId/presetSubtype, `accel/decel`, `by/from/to/values`, `p:cBhvr/p:tgtEl/p:spTgt`, motion via `p:animMotion origin/layout/rAng/by/from/to/path`, scale via `p:animScale`, effects via `p:animEffect transition/filter`, set via `p:set`, audio via `p:audio/p:video` + `p:cMediaNode`. Map these onto the *same* node/behavior JSON so the scheduler survives.
2. **Newer features goblins never had** (per task brief — inventory ProjectStar's deck for these explicitly): SmartArt, charts/tables, embedded video (not just audio commands), slide masters with inherited animations, `p:transition` effects beyond the 6 above (morph, etc. — OOXML PPTX transitions are named in XML, no SSSlideInfoAtom mapping needed), theme fonts/colours (`a:theme`), grouped shapes (`p:grpSp` with recursive timing targets), trigger-on-shape clicks (`cond evt="onClick" tgtEl`), bookmark/section navigation, hyperlinks to custom shows / `ppaction://` actions. Each needs an extract → manifest → runtime → verifier slice; the goblins code has **no** handling for any of them.
3. **Hyperlinks in PPTX:** `a:hlinkClick r:id` on runs and `p:cxnSp/sp hlinkClick` on shapes, resolved through slide `.rels`; action settings in `ppt/slides/_rels` + `p:action` equivalents. Apply the §3.1 lesson: resolve IDs, never display text or filename order.
4. **Media in PPTX:** embedded files live in `ppt/media/*` with real extensions — no WAV-record extraction or WMA transcode needed for most; video needs `<video>` layer support goblins lacks entirely (it only has `<audio>`).

---

## 5. Dependencies / tools needed

| Dependency | Version / source | Required for | Notes |
|---|---|---|---|
| Python | 3.x (repo used venv `.venv`) | All tools | — |
| `olefile>=0.47` | `tools/requirements.txt` | Binary .pps parsing (`extract_ppt`, DocSummary stream, stuck-hyperlink audit) | **Not needed for pure-PPTX ProjectStar** except if a .pps original must be audited. |
| `Pillow>=12.0` | `tools/requirements.txt` | Picture extraction (DIB→PNG), `render_reconstructed`, PNG stats in debug tools | Core for both projects. |
| Apache POI | **5.2.3** binary zip (last all-in-one zip; newer = Maven only) in `_port_analysis_tmp/poi-5.2.3/` (gitignored) | `PoiAudit.java` validation layer: slides, shapes, text, pictures, sounds, transitions, TEXTLINK | HSLF for .pps. For PPTX, POI XSLF or direct XML parsing — evaluate, don't assume. |
| Portable JDK | **21.0.11+10** in `_port_analysis_tmp/jdk21/` (gitignored) | Compile/run PoiAudit | System JDK also fine if present. |
| `tools/poi/PoiAudit.java` | In-repo | Produces `generated/poi_audit.tsv` (SLIDEBG/SHAPE/GEOMETRY/STYLE/PICTURE/CLIP/GEOTEXT/TEXT/… rows) consumed by `extract_layers, extract_animation_manifest (--poi-audit), extract_source_semantics, audit_timing_tree` | Rewrite for XSLF/OOXML if kept. |
| ffmpeg | System PATH (hard fail in `convert_audio.py` if absent) | WMA/WAV/MIDI-rendered-WAV → MP3 (`libmp3lame` 128k) + Opus (`libopus` 96k) | Still needed if ProjectStar has WMA/legacy audio; not for MP3/MP4-native PPTX media. |
| Playwright (Python) + Chromium | `from playwright.sync_api import sync_playwright` in `verify_click_advance_combat, verify_combat_visual_options, verify_limit_combat` | Browser regressions: visual-centre clicks, 1-click title, Limit matrix, history assertions | **Not in `requirements.txt`** — install separately (`pip install playwright && playwright install chromium`). Other verifiers are pure-Python/static. |
| LibreOffice / PowerPoint | **Not a build dependency** | Oracle only: producing the converted `source/*.pptx` debug lens, PPT UI oracle for Phase 4 graph disputes, reference screenshots for pixel QA (PLAN 5.11, still open) | `RENDERING.md` explicitly: publishable without Office/Aspose/LibreOffice. For ProjectStar the .pptx *is* the source, so no conversion step exists — but a PowerPoint/LibreOffice *render* is still the only pixel oracle. |
| Aspose / python-pptx | **Explicitly not used** for the binary deck (PLAN: “No Aspose, no python-pptx for this binary”) | — | For ProjectStar (OOXML), `python-pptx` becomes a legitimate candidate for shapes/text/hyperlinks — but it does **not** expose `p:timing` trees well; a raw `lxml`/zip XML parser will still be needed for animation, exactly as POI was insufficient for PP10. |
| FluidSynth / Timidity / soundfont | **Deliberately avoided** | — | Replaced by in-repo `render_midi.py` deterministic synth. |
| Windows fonts | `C:/Windows/Fonts/{impact,ariblk,BROADW,arial,tahoma,times,segoeui}.ttf` hardcoded in `render_reconstructed.font_for()` | Pillow text rendering in reconstructed PNGs | **Portability bug to fix for ProjectStar:** on Linux/macOS every candidate misses → `load_default()` (tiny bitmap font, wrong metrics). Add fontconfig / DejaVu / Liberation paths, or bundle metrics-matched fonts. Browser runtime uses web-available fonts + substitution anyway (Impact/Arial Black approximate). |
| Static server | `tools/serve_docs.py` (stdlib only) or GitHub Pages | Preview / ship | No backend, no npm, no bundler anywhere in the project. `docs/app.js` is hand-written vanilla JS (WAAPI + CSS transitions). |
| Git / GitHub Pages | `docs/` on `master` | Publishing | Goblins workflow note (commit locally, push only when asked, branch `grokbot-dev`) is project-specific — see §4.2. |

---

## 6. Bottom line for the ProjectStar port — recommended reuse order

1. **Copy** `docs/` runtime (`app.js` scheduler/render/debug, `styles.css`, `index.html`, `serve_docs.py`) and rename branding/keys; keep manifest schemas identical.
2. **Write new OOXML extractors** (zip + XML) that emit `inventory/layers/animations/audio` JSON in the goblins shapes — including a DocSummary-equivalent *ID-based* hyperlink resolver from day 1, and a hotspot-vs-oracle matrix verifier.
3. **Port the verifiers** with all counts/sizes parameterised from the manifest; add the visual-centre Playwright pattern for any menu-like slides.
4. **Encode the §3 lessons as fixtures before they bite:** empty OnNext drain, AfterEffect hide-on-next, entrance pre-hide exclusions, effect `finishIn` clip restoration, transition-timer separation, media-speaker hiding, green-placeholder detection, mojibake *scanning* (not the goblins map).
5. **Inventory ProjectStar-only features** (video, SmartArt, groups, morph, theme) as separate extract→runtime→verify slices — goblins has zero coverage there, so “reusing the vast majority of infrastructure” holds for navigation/animation/audio/static-publishing, not for those features.

*Sources read for this inventory: PLAN.md, NOTES.md, README.md, RENDERING.md, AGENT_TESTING.md, ANIMATION_EVALUATION.md, POI_EVALUATION.md, docs/DEBUGGING.md, docs/index.html, docs/app.js (structure/RUNTIME_CONFIG/key functions), docs/styles.css, tools/extract_ppt.py, tools/extract_layers.py, tools/build_game_manifest.py, tools/render_reconstructed.py, tools/extract_animation_manifest.py, tools/extract_embedded_audio.py, tools/convert_audio.py, tools/requirements.txt, full tools/*.py listing, git log (73 commits).*
