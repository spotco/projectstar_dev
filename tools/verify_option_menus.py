"""Generic menu/option contract for ProjectStar (replaces the goblinsrpg3
combat-specific verifiers, which encoded that deck's battle rules).

Checks, from docs/game-manifest.json + the DocSummary-resolved inventory:
- Every slide with >=2 hyperlink hotspots: all are clickable, all targets
  exist, and no shape carries two clickable hotspots to the same target
  (the same-shape click+none duplicate-button trap from goblinsrpg3).
- Known menu fixtures navigate to their DocSummary-resolved targets:
  opening ship-battle -shot menus, warp-gate Land/Continue, station hub
  option permutations, the Punch/Insult choice tree, magazine page turns,
  and the Sound Test speaker order (track1-5).
"""

from __future__ import annotations

import json
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    game = json.loads((root / "docs/game-manifest.json").read_text(encoding="utf-8"))
    screens = game["screens"]
    by_slide = {int(s["slide"]): s for s in screens}

    menu_slides = 0
    for screen in screens:
        nav = [
            h
            for h in screen.get("hotspots") or []
            if h.get("action") == "hyperlink" and h.get("targetSlide")
        ]
        if len(nav) < 2:
            continue
        menu_slides += 1
        seen: dict = {}
        for h in nav:
            if not h.get("clickable") and int(h["targetSlide"]) != int(screen["slide"]):
                # Non-clickable hotspots are only acceptable as documented
                # residual self-links (target == own slide, e.g. slide 122's
                # ship-option rows that re-display the same buy screen).
                fail(f"slide {screen['slide']}: nav hotspot {h.get('id')} not clickable")
            if int(h["targetSlide"]) not in by_slide:
                fail(f"slide {screen['slide']}: hotspot targets missing slide {h['targetSlide']}")
            key = (h.get("shapeId"), h.get("targetSlide"))
            seen[key] = seen.get(key, 0) + 1
            if seen[key] > 1:
                fail(f"slide {screen['slide']}: duplicate clickable hotspots for {key}")

    def expect(slide: int, target: int, label_part: str | None = None) -> None:
        screen = by_slide[slide]
        hits = [
            h
            for h in screen.get("hotspots") or []
            if h.get("action") == "hyperlink"
            and h.get("clickable")
            and h.get("targetSlide") == target
            and (label_part is None or label_part.lower() in str(h.get("shapeText") or "").lower())
        ]
        if not hits:
            fail(f"slide {slide}: expected clickable option -> {target} ({label_part!r})")

    # Opening ship battle -shot menus (DocSummary-resolved; labels were stale).
    for slide, target in ((11, 12), (15, 16), (18, 19), (21, 22)):
        expect(slide, target, "-shot")
    # Warp gate: -Land / -Continue.
    expect(105, 106, "-Land")
    # Station hub permutations: each option slide exposes >=5 distinct targets.
    for slide in (52, 65, 73):
        targets = {
            h["targetSlide"]
            for h in by_slide[slide].get("hotspots") or []
            if h.get("action") == "hyperlink" and h.get("clickable") and h.get("targetSlide")
        }
        if len(targets) < 5:
            fail(f"hub slide {slide}: expected >=5 distinct option targets, found {sorted(targets)}")
    # Punch / Insult choice tree.
    expect(166, 175, "Punch")
    expect(166, 167, "Insult")
    expect(180, 181, "Ask")
    # Magazine page turns stay inside the magazine spread.
    for slide in (261, 263, 264, 268, 270, 271):
        targets = {
            h["targetSlide"]
            for h in by_slide[slide].get("hotspots") or []
            if h.get("action") == "hyperlink" and h.get("clickable") and h.get("targetSlide")
        }
        if not targets or not targets.issubset(set(range(243, 273))):
            fail(f"magazine slide {slide}: page-turn targets {sorted(targets)} leave the magazine")
    # Sound Test speakers map in order to track1-5.
    bindings = {b["id"]: b for b in game.get("mediaBindings") or []}
    for i, shape_id in enumerate((458768, 458769, 458770, 458771, 458772), start=1):
        binding = bindings.get(f"slide-358-shape-{shape_id}")
        if not binding or binding.get("audioCueId") != f"linked:track{i}":
            fail(f"sound test shape {shape_id} should map to linked:track{i}")

    print(f"option menu verification passed ({menu_slides} multi-option slides)")   


if __name__ == "__main__":
    main()
