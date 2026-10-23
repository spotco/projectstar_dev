# Project Star port — notes, bug/fix log, residuals

Format per entry: symptom → extract evidence → root cause → fix → verify.
The binary `.ppt` is the oracle throughout; LibreOffice renders are a
comparison baseline only (no PowerPoint reference exists).

## 1. Hyperlink targets: 139 of 218 labels are stale

- **Symptom:** the copied goblins resolver produced wrong targets and
  unreachable slides.
- **Evidence:** 218 ExHyperlink records vs 217 DocSummary destinations.
  The count mismatch is the deck's one external-URL link (slide 91).
- **Root cause:** the copied code fell back to parsing the friendly
  `"Slide N"` labels for *all* links when counts mismatched. In this
  deck 139 labels disagree with the DocSummary slideId destinations.
- **Fix (`extract_ppt.py`):** partition external-URL links out first
  (`resolveMethod="external_url"`, no slide target), then pair the
  remaining 217 with DocSummary destinations 1:1 in append order and map
  slideId → presentation order.
- **Verify:** stale-number agreement 216/217 against the pptx lens;
  all 358 slides reachable from slide 1, one weak component, stuck = 0;
  `verify_start_graph`, `verify_advancement` PASS.

## 2. External URL dropped by the action builder

- **Symptom:** slide 91's Mr. T picture link (`obeygiant.com`, 2005)
  produced no hotspot behavior.
- **Root cause:** `resolve_method` was discarded when `target_slide`
  was `None`, so the link looked like a dead `none` action.
- **Fix:** check `resolveMethod == "external_url"` before the target
  check; manifest marks the hotspot `externalUrl`, runtime opens it in
  a new tab (`noopener`) and never navigates the game.
- **Verify:** browser click opens a popup and the game stays on slide
  91 (the 2005 URL itself is dead — the mechanics are what we verify).

## 3. Media/BGM binding via record 3009 (refId)

- **Symptom:** none of the 26 media shapes (music, SFX, Sound Test)
  resolved to an audio file with the goblins logic.
- **Evidence:** media shapes carry record **3009 (0xBC1)** = a refId
  into the Document external-media list: type **4109** containers
  (ExMediaAtom 4100 + CString path) name linked files; type **4111**
  (ExMediaViewAtom 4115, first dword) names embedded sound ids.
- **Fix:** resolve refId → external list. track1–5 map to slides
  3/9/134/309/337 and sequentially to the Sound Test (refIds
  27683–27687); embedded pairs 27/28 recur on the train slides.
  Record 3009 on slides 243/246 points at the Photoshop OLE object →
  classified `external_object` (preview picture renders; no OLE run).
- **Verify:** 26/26 media bindings mapped, 0 unresolved, 22 audio cues;
  `verify_audio_cues`, `verify_embedded_audio` PASS; Sound Test click
  logs `audio:play source: track2.mp3` in the browser.

## 4. Animated GIFs live inside PNG blips (`msOG` chunk)

- **Symptom:** two pictures were animated in PowerPoint but static here.
- **Evidence:** PNG blips `asset-228` (slide 271) and `asset-257`
  (slides 308–336) contain an `msOG` chunk: `MSOFFICE9.0` header + full
  GIF bytes. The PNG IDAT is only the first frame.
- **Fix:** extract the GIF bytes at picture extraction; layers reference
  them as `animatedInstancePath`.
- **Verify:** extracted GIFs are SHA-256 byte-identical to LibreOffice's
  own extraction; two browser screenshots 1.2 s apart differ exactly in
  the GIF region. **Do not flatten these to static PNGs.**

## 5. WMF pictures and the POI +22-byte quirk

- **Symptom:** the deck's 2 WMF pictures (slides 188, 272) failed the
  layers byte-size check.
- **Evidence:** the real WMF stream (zlib at offset 50 of the blip
  payload) is 22 bytes shorter than POI reports: POI synthesizes an
  Aldus placeable header (`sourceBytes = fileBytes + 22`).
- **Fix:** `resolve_picture_asset` accepts `sourceBytes − 22` for WMF;
  `tools/convert_wmf.py` rasterizes via LibreOffice + autocrop +
  edge flood-fill transparency (pipeline order: extract_ppt →
  convert_wmf → extract_layers).
- **Verify:** slide 188 backdrop matches the LO reference pixel-for-
  pixel in composition; slide 272 candy clip-art renders in place.

## 6. POI decodes text as literal `?` (396 shapes)

- **Symptom:** dialogue text full of `?` where punctuation belongs.
- **Root cause:** POI HSLF lossy-decodes some chars as `?`; the binary
  TextChars/TextBytes records hold the true text. (The goblins mojibake
  map does **not** apply to this deck.)
- **Fix (`extract_layers.py`):** `apply_binary_text_corrections()`
  substitutes the binary string when the POI string matches it with
  `?` as wildcard (equal length, equal at every non-`?` position —
  genuine question marks are untouched).
- **Verify:** 396 shapes corrected, residualArtifacts = 0;
  `verify_text_fidelity` PASS; OCR of browser vs LO reference agrees
  on slides 3, 159, 272, 358.

## 7. Five transition types goblins never used

- SSSlideInfoAtom types mapped via the pptx lens names:
  **5 = dissolve** (slides 279–280), **6 = fade** (15 slides; a
  different record type from 23 = fade-through-black family used 47×),
  **8 = randomBar** (4, 173), **10 = wipe** (127–128),
  **26 = wheel** (10, 310, 338). CSS classes added per type.
- `verify_transition_effects` PASS with lens counts: fade 62
  (= 47 + 15), circle 14, wheel 3, dissolve 2, randomBar 2, wipe 2.

## 8. Effect filters: diamond, strips, wipe

- The deck's TimeEffectBehavior filters are dissolve ×420, fade ×8,
  diamond ×4, strips ×1, wipe ×1 — goblins' set (blinds/box/…) never
  occurs. `effectFilterName` + `applyEffectBehavior` in `docs/app.js`
  gained diamond (polygon grow), strips (inset sweep), and directional
  wipe branches.

## 9. GIF runtime bug: manifest didn't copy the GIF

- **Symptom:** slides 271/308+ showed the static first frame.
- **Root cause:** layers carried `animatedInstancePath`, but
  `build_game_manifest.copy_layers` didn't copy/rewrite the `.gif`,
  and `app.js` only read `instancePath`.
- **Fix:** copy GIFs to `docs/assets/slide-assets/slide-NNN/` with
  docs-relative paths; image `src = animatedInstancePath || instancePath`.
  16 animated layers across slides 271, 308–317, 323–325, 331–336.

## 10. WordArt plain-fit

- **Symptom:** the slide 3 title rendered ~7× too small.
- **Root cause:** all 12 WordArt layers here are `TEXT_PLAIN_TEXT` /
  `TEXT_SLANT_UP` (geometry field `None`), so they fell through to flat
  text at run font size instead of stretching to their box.
- **Fix:** `mountWordArtPlainFit()` in `app.js` — SVG text with an
  aspect-matched viewBox, `preserveAspectRatio="none"`,
  `textLength` = 98% of box width, font-size 0.8 × box height,
  fill/stroke from the layer style, slant = rotate(−8°).
- **Verify:** slide 3 matches the LO reference closely. Residual:
  "Part 1" sits slightly right of LO's render (authored box x=300pt
  with `anchorCtr` in the lens) — open, cosmetic.

## 11. Per-run hyperlink hit bands

- **Symptom:** on slide 166, "-Punch him" was unclickable — only
  "-Insult" worked. Same-shape options on 42/43/168/180 too.
- **Evidence:** five shapes carry 2 hyperlink records (one per text
  run) but every record stores whole-shape bounds, so the hotspots
  stack exactly and the topmost wins. (Slides 52/65/73 were checked
  and are false alarms: one binary action per shape there.)
- **Fix:** `apply_run_hit_bands()` in `tools/advancement_lib.py`
  partitions the shape's height into one band per text line (skipping
  a leading header line like "Options" when lines = hotspots + 1) and
  assigns bands in record order (= reading order in this deck).
- **Verify:** browser clicks land Punch → 175, Insult → 167,
  Land → 44, Continue → 81, Ask → 181, Gun → 183 (then auto-chain).

## 12. Record census leftovers (plan item N8, closed)

- **1008/1009 = Notes / NotesAtom**, appearing once: the deck has a
  single notes page. **SlidePersistAtom and SlideAtom both count
  359 = 358 game slides + that notes page** — this is the whole of
  the "359 vs 358" discrepancy. Game counts use 358 everywhere.
- **4006 = TextRulerAtom** (POI name table), ×3 inside text shapes;
  ruler/tab data, no content impact.
- **3035** (×3) and **4089** (×2): no name in POI's table. 3035 is a
  1-byte flag (`0x01`) inside PP10 TimeNode containers; 4089 is a
  4-byte zero atom inside PP10 prog-tag containers. Both are inert
  for extraction and playback; recorded here so nobody re-chases them.
- 4035/4044/4045 = ExOleObjAtom / ExEmbed / ExEmbedAtom for the
  Photoshop OLE object on slides 243/246.

## 13. Iterate-revealed hotspots never enabled (found by full playthrough)

- **Symptom:** slide 313's "-Shot" option never became clickable — the
  game soft-locked in the final battle chain. A full browser
  playthrough (slide 1 → 313, 224 slides, zero console errors) stalled
  here even though all 172 animation nodes ran to completion and the
  "-Shot" text was visibly on screen.
- **Evidence:** the layer element ended `visibility: visible, opacity: 1`
  while its hotspot button stayed `pointer-events: none`. The shape's
  only reveal (`set style.visibility=visible`, node s313-tn0157) sits
  under a **byLetter iterate** group (s313-tn0156).
- **Root cause:** `applyBehaviorToIterateUnits()` in `docs/app.js`
  reveals the host with a direct style write and never calls
  `syncHotspotsForShapeVisibility()` — the non-iterate path goes
  through `revealAnimationElement()`, which does. Hotspot shapes whose
  *only* reveal is iterate-driven stayed gated forever. Exactly two
  slides affected: **313** and **341** (both "-Shot"-style options in
  the final battles).
- **Fix:** sync the shape's hotspots in the iterate host-reveal block.
- **Verify:** slides 313 → 314 and 341 → 342 click through live; the
  resumed playthrough (308 → 356 credits → 358 Sound Test) completed
  with no problems and no console errors; 22/22 verifiers still PASS.

## Known residuals (ship as-is, by design)

- **21 zero-area media hotspots** are non-clickable (authored zero-size
  speaker shapes); their cues still fire from the timing tree.
- **11 residual self-links** (e.g. slide 122's ship-option rows display
  prices but link to themselves; the slide exits via "<- EXIT").
- **Photoshop OLE object** renders as its stored preview picture; the
  OLE app is not executed (same policy as the goblins port).
- **Sound Test (slide 358)** queues all five tracks on entry and they
  flush on first click — authored behavior ("things will get pretty
  crazy", per the slide's own note).
- **`docs/animation-manifest.json` is 43 MB** — fine locally; a
  per-slide lazy-load split would need a runtime + verifier change.
- Author-note slides (60/63/70–72, ordering notes baked into the art)
  are reachable and ship exactly as authored.
- No Microsoft PowerPoint reference exists; fidelity claims are
  relative to LibreOffice renders, which are themselves imperfect
  (e.g. LO paints red corner dots on the slide 3 Start shape that the
  runtime, following the binary, does not).
