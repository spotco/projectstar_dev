#!/usr/bin/env python3
"""Smoke: deck slide transitions + image effect filters have CSS/runtime coverage.

Validates SSSlideInfoAtom effectTypes (PPS timing_manifest) against:
  - effectName mapping in extract_timing
  - CSS .transition-effect-N + @keyframes
  - app.js transitionEffectClass / applySlideTransition
  - pptx p:transition child names (parity with PPS)

Also asserts image TimeEffectBehavior filters used in animations.json
(fade/dissolve/blinds/box) are implemented in applyEffectBehavior (not stubbed).
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
TM = json.loads((ROOT / "generated/timing_manifest.json").read_text())
ANIM = json.loads((ROOT / "generated/animations.json").read_text())
CSS = (ROOT / "docs/styles.css").read_text()
APP = (ROOT / "docs/app.js").read_text()
PPTX = ROOT / "source/projectstar_part1-pptx.pptx"

# SSSlideInfoAtom <-> OOXML names for every non-cut effect in this deck.
# Resolved via the LibreOffice pptx lens (p:transition child per slide):
# type 6 is a second fade encoding; 5/8/10/26 did not exist in goblinsrpg3.
EXPECTED_EFFECTS = {
    5: "dissolve",
    6: "fade",
    8: "randomBar",
    10: "wipe",
    23: "fade",
    26: "wheel",
    27: "circle",
}

PPTX_NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}

failures: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)


# --- PPS slide transitions ---
used = sorted({int(t["effectType"]) for t in TM["transitions"] if int(t.get("effectType") or 0) != 0})
print("PPS used effectTypes:", used)

if set(used) != set(EXPECTED_EFFECTS):
    fail(f"PPS effectTypes {used} != expected {sorted(EXPECTED_EFFECTS)}")

for et, name in EXPECTED_EFFECTS.items():
    got = next((t.get("effectName") for t in TM["transitions"] if int(t["effectType"]) == et), None)
    if got != name:
        fail(f"effectType {et} expected name {name}, got {got}")
    cls = f"transition-effect-{et}"
    if cls not in CSS:
        fail(f"CSS missing .{cls} for effectType {et} ({name})")
    m = re.search(rf"transition-effect-{et}[^{{]*\{{[^}}]*animation-name:\s*([a-z0-9-]+)", CSS)
    if not m:
        fail(f"CSS .{cls} has no animation-name")
    else:
        kf = m.group(1)
        if f"@keyframes {kf}" not in CSS:
            fail(f"missing @keyframes {kf} for effect {et}")

if "transitionEffectClass" not in APP:
    fail("app.js missing transitionEffectClass")
if "applySlideTransition" not in APP:
    fail("app.js missing applySlideTransition")

# Spot checks: s010 wheel (26), s279 dissolve (5), s004 randomBar (8)
for slide_no, et, name in ((10, 26, "wheel"), (279, 5, "dissolve"), (4, 8, "randomBar"), (127, 10, "wipe")):
    tr = next(t for t in TM["transitions"] if t["slide"] == slide_no)
    if int(tr["effectType"]) != et or tr.get("effectName") != name:
        fail(f"s{slide_no:03d} expected {name}/{et}, got {tr}")

# Sample each non-cut type has at least one slide
for et, name in EXPECTED_EFFECTS.items():
    slides = [t["slide"] for t in TM["transitions"] if int(t["effectType"]) == et]
    if not slides:
        fail(f"no slides with effectType {et} ({name})")
    else:
        print(f"  {et} {name}: slides {slides[:6]}{'…' if len(slides) > 6 else ''}")

# --- pptx parity ---
if not PPTX.is_file():
    fail(f"missing pptx debug aid {PPTX}")
else:
    pptx_counts: Counter[str] = Counter()
    with zipfile.ZipFile(PPTX) as zf:
        for name in zf.namelist():
            if not re.fullmatch(r"ppt/slides/slide\d+\.xml", name):
                continue
            root = ET.fromstring(zf.read(name))
            tr = root.find("p:transition", PPTX_NS)
            if tr is None:
                continue
            kids = [child for child in list(tr) if isinstance(child.tag, str)]
            if not kids:
                pptx_counts["cut"] += 1
            else:
                pptx_counts[kids[0].tag.split("}")[-1]] += 1
    print("pptx p:transition:", dict(pptx_counts))
    for et, name in EXPECTED_EFFECTS.items():
        if pptx_counts.get(name, 0) < 1:
            fail(f"pptx missing p:transition/{name} (PPS effectType {et})")
    # Counts should match PPS non-cut frequency
    pps_counts = Counter(
        t.get("effectName") for t in TM["transitions"] if int(t.get("effectType") or 0) != 0
    )
    for name, count in pps_counts.items():
        if pptx_counts.get(name, 0) != count:
            fail(f"pptx count for {name}={pptx_counts.get(name, 0)} != PPS {count}")

# --- Image effect filters (TimeEffectBehavior) ---
filter_counts: Counter[str] = Counter()


def walk_effects(node: dict) -> None:
    for behavior in node.get("behaviors") or []:
        if behavior.get("kind") != "effect":
            continue
        for variant in behavior.get("variants") or []:
            parsed = variant.get("parsed") or {}
            value = parsed.get("stringValue")
            if isinstance(value, str) and value:
                # normalize blinds(horizontal) → blinds, box(in) → box
                key = value.split("(", 1)[0].lower()
                filter_counts[key] += 1
    for child in node.get("children") or []:
        walk_effects(child)
    for sub in node.get("subEffects") or []:
        walk_effects(sub)


for slide in ANIM.get("slides") or []:
    for root in slide.get("rootTimeNodes") or []:
        walk_effects(root)

print("image effect filters:", dict(filter_counts))
required_filters = {"fade", "dissolve", "diamond", "strips", "wipe"}
missing_filters = required_filters - set(filter_counts)
# fade/dissolve/diamond/strips/wipe all appear in this deck
if missing_filters:
    fail(f"animations.json missing expected filters {sorted(missing_filters)}")

for name in sorted(filter_counts):
    # Runtime must recognize the filter (not stub-skip).
    if name in ("fade", "dissolve"):
        if "value === \"fade\" || value === \"dissolve\"" not in APP and 'value === "fade"' not in APP:
            # applyEffectBehavior uses effectFilterName
            if "effectFilterName" not in APP:
                fail("app.js missing effectFilterName for fade/dissolve")
    if name in ("diamond", "strips", "wipe") and f'startsWith("{name}")' not in APP:
        fail(f"app.js missing {name} effect support")

if "effectFilterName" not in APP:
    fail("app.js missing effectFilterName")
if "effectTransitionIsOut" not in APP:
    fail("app.js missing effectTransitionIsOut (in vs out)")
if "animation:effect-skipped" in APP and 'reason: "fade/dissolve not present"' in APP:
    fail("app.js still stubs non-fade effects (fade/dissolve not present skip)")
# Directional out must be implemented (kill fade / blinds exit)
if 'direction: isOut ? "out" : "in"' not in APP and "isOut" not in APP:
    fail("app.js applyEffectBehavior missing exit direction handling")

# s310 uses diamond(in) (final-battle accent entrance)
def find_filter(node: dict, prefix: str) -> bool:
    for behavior in node.get("behaviors") or []:
        if behavior.get("kind") != "effect":
            continue
        for variant in behavior.get("variants") or []:
            value = ((variant.get("parsed") or {}).get("stringValue") or "").lower()
            if value.startswith(prefix):
                return True
    return any(find_filter(c, prefix) for c in (node.get("children") or [])) or any(
        find_filter(s, prefix) for s in (node.get("subEffects") or [])
    )


s310 = next(s for s in ANIM["slides"] if s["slide"] == 310)
if not any(find_filter(r, "diamond") for r in s310.get("rootTimeNodes") or []):
    fail("s310 expected diamond(in) effect in animation manifest")
else:
    print("OK s310 diamond effect present in animation manifest")

if failures:
    print("FAIL")
    for item in failures:
        print(" ", item)
    sys.exit(1)
print("OK transition smoke: slide effects", ", ".join(str(et) for et in used), "; image filters", ", ".join(sorted(filter_counts)))
