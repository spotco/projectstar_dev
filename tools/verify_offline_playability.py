"""Verify offline playability suite (Phase 1 PLAN): path walk, Tier A, catalogs, clickable."""

from __future__ import annotations

import json
from pathlib import Path

from analyze_start_graph import EXPECTED_START_REACHABLE
from build_offline_playability import build_all


def fail(message: str) -> None:
    raise SystemExit(message)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    generated = root / "generated"

    # Rebuild all offline reports so verify is self-contained.
    build_all()

    path_report = load_json(generated / "path_walk_report.json")
    chapters = load_json(generated / "chapter_entry_map.json")
    promotes = load_json(generated / "promote_audit.json")
    clickable = load_json(generated / "clickable_contract.json")
    game = load_json(root / "docs" / "game-manifest.json")

    if path_report.get("format") != "projectstar-path-walk-report-v1":
        fail("path_walk_report format unexpected")

    tier = path_report.get("tierA") or {}
    if not tier.get("matchesStartBaseline"):
        fail(
            f"Tier A reachability does not match EXPECTED_START_REACHABLE "
            f"(count={tier.get('reachableCount')}, "
            f"expected={len(EXPECTED_START_REACHABLE)})"
        )
    if tier.get("reachableCount") != len(EXPECTED_START_REACHABLE):
        fail(f"Tier A reachableCount {tier.get('reachableCount')} != {len(EXPECTED_START_REACHABLE)}")
    if not tier.get("includesStoryBeats"):
        fail("Tier A missing story beats (1–3, 8–9)")
    if not tier.get("includesVillage"):
        fail("Tier A missing Leahin / shipyard slides 104/121")
    if not tier.get("includesCombat"):
        fail("Tier A missing first battle slide 10")
    if not tier.get("deathReachable"):
        fail("Tier A: Game Over slides 26/174/322/330 not reachable from title")
    if not tier.get("freezeLoop161to157"):
        fail("Tier A: expected freeze loop return edge s161 -> s157")

    # Seed-1 walk exists and has no stuck endings
    walk1 = next((w for w in path_report.get("walks") or [] if w.get("seed") == 1), None)
    if not walk1:
        fail("path walk missing seed 1")
    stuck_endings = [e for e in walk1.get("endings") or [] if e.get("kind") == "stuck"]
    if stuck_endings:
        fail(f"Tier A walk has stuck endings: {stuck_endings}")

    # Chapter map
    if chapters.get("format") != "projectstar-chapter-entry-map-v1":
        fail("chapter_entry_map format unexpected")
    if chapters.get("summary", {}).get("chapterCount", 0) < 3:
        fail("chapter map should list title + islands/roots")
    entries = {c.get("entrySlide") for c in chapters.get("chapters") or []}
    for required in (1, 121, 243, 358):
        if required not in entries:
            # 43/55 may be under islands or roots
            all_entries = set(entries)
            for island in chapters.get("sealedIslands") or []:
                all_entries.add(island.get("suggestedEntry"))
            for root in chapters.get("zeroInboundRoots") or []:
                all_entries.add(root.get("slide"))
            if required not in all_entries and required != 1:
                fail(f"chapter map missing entry for slide {required}")
    if 1 not in entries:
        fail("chapter map missing tier-a title entry")

    # Promote audit: known promotes present
    if promotes.get("format") != "projectstar-promote-audit-v1":
        fail("promote_audit format unexpected")
    methods = {p.get("resolveMethod") for p in promotes.get("promotes") or []}
    if "self_continue_to_next" not in methods:
        fail("promote audit missing method self_continue_to_next")
    if "noop_mirror_sibling_hyperlink" not in methods:
        fail("promote audit missing method noop_mirror_sibling_hyperlink")
    # noop_mirror_sibling_hyperlink is only for *different-shape* leftover
    # InteractiveInfo. Same-shape click+none pairs stay explicit_noop (the
    # real DocSum hyperlink is the only clickable button).
    # Self-link promotes (self_continue / combat_all_self / sole_image_self) are no longer
    # required: DocSummary slideId resolve yields the real targets (e.g. s046→47, s002→3).

    # Clickable contract
    if not clickable.get("summary", {}).get("passed"):
        viol = clickable.get("violations") or []
        fail(f"clickable contract failed: {viol[:5]}")

    # Promoted self/noop hotspots: slide 83 travel options self-continue to
    # slide 84; final-battle -Shot shapes on 314-316 mirror their sibling
    # DocSum hyperlink to the next slide.
    for slide in (314, 315, 316):
        screen = game["screens"][slide - 1]
        cont = [
            h
            for h in screen.get("hotspots") or []
            if h.get("resolveMethod") == "noop_mirror_sibling_hyperlink"
            and h.get("targetSlide") == slide + 1
        ]
        if not cont:
            fail(f"slide {slide} expected noop_mirror_sibling_hyperlink -> {slide + 1}")
        if screen["advancement"].get("stuckReason"):
            fail(f"slide {slide} should not be stuck")
    s83 = game["screens"][82]
    cont83 = [
        h
        for h in s83.get("hotspots") or []
        if h.get("resolveMethod") == "self_continue_to_next" and h.get("targetSlide") == 84
    ]
    if len(cont83) < 2:
        fail("slide 83 expected two self_continue_to_next travel options -> 84")

    # Station hub option slides: every menu shape carries exactly one
    # clickable hyperlink hotspot per target (same-shape click+none pairs
    # stay a single button; the DocSum hyperlink is the real one).
    for slide in (52, 65, 73):
        screen = game["screens"][slide - 1]
        nav = [
            h
            for h in screen.get("hotspots") or []
            if h.get("action") == "hyperlink" and h.get("clickable") and h.get("targetSlide")
        ]
        if len(nav) < 5:
            fail(f"hub slide {slide} expected >=5 clickable options, found {len(nav)}")
        seen: dict = {}
        for h in nav:
            key = (h.get("shapeId"), h.get("targetSlide"))
            seen[key] = seen.get(key, 0) + 1
            if seen[key] != 1:
                fail(f"slide {slide} shape {key[0]} has duplicate clickable hotspots -> {key[1]}")

    # Former "self" fixtures were stale ExHyperlink labels. After
    # DocSummary slideId resolve they navigate to the real next slide.
    former_self_fixtures = [
        (11, "-shot", 12),
        (15, "-shot", 16),
        (18, "-shot", 19),
    ]
    for slide, text, target in former_self_fixtures:
        screen = game["screens"][slide - 1]
        hits = [
            h
            for h in screen.get("hotspots") or []
            if h.get("action") == "hyperlink"
            and str(h.get("shapeText") or "").lower().replace(" ", "")
            == text.lower().replace(" ", "")
            and h.get("targetSlide") == target
            and h.get("clickable")
        ]
        if not hits:
            fail(f"slide {slide} {text!r} must navigate ->{target} after slideId resolve")
        if not (screen.get("advancement") or {}).get("leavePaths"):
            fail(f"slide {slide} lost leave paths")
    # Warp-gate -Land option on slide 105 resolves to slide 106.
    s105 = game["screens"][104]
    land = [
        h
        for h in s105.get("hotspots") or []
        if h.get("action") == "hyperlink" and h.get("targetSlide") == 106 and h.get("clickable")
    ]
    if not land:
        fail("slide 105 -Land must navigate ->106 after slideId resolve")

    # Hub image slides also leave via slideId-native hyperlinks (not residual self).
    for slide in (52, 65):
        screen = game["screens"][slide - 1]
        nav = [
            h
            for h in screen.get("hotspots") or []
            if h.get("clickable") and h.get("targetSlide") and h.get("targetSlide") != slide
        ]
        if not nav:
            fail(f"hub slide {slide} expected outbound hyperlinks after slideId resolve")

    # Game manifest still 358 screens
    if len(game.get("screens") or []) != 358:
        fail("expected 358 screens")

    # Combat matrix if present
    matrix_path = generated / "combat_option_matrix.json"
    if matrix_path.exists():
        matrix = load_json(matrix_path)
        if matrix.get("format") not in (
            "projectstar-combat-option-matrix-v1",
            "projectstar-combat-option-matrix-v2",
        ):
            fail("combat_option_matrix format unexpected")
        if matrix.get("summary", {}).get("noopOptions", 1) != 0:
            fail(
                f"combat matrix still has noop options: "
                f"{matrix.get('summary', {}).get('noopOptions')}"
            )
        if matrix.get("summary", {}).get("mismatchCount", 0):
            fail(f"combat matrix web/docsum/pptx mismatches: {matrix.get('mismatches')}")

    # Media residuals: ProjectStar has NO unresolved media bindings (all 26
    # mapped via the binary external-media list). Zero-area mapped media
    # (hidden BGM speaker shapes) are documented, non-clickable residuals.
    for screen in game["screens"]:
        for h in screen.get("hotspots") or []:
            if h.get("residualStatus") == "accepted_unresolved_media":
                fail(f"slide {screen['slide']} has unresolved media residual (all PS media is mapped)")
    zero_area = [
        h
        for screen in game["screens"]
        for h in screen.get("hotspots") or []
        if h.get("residualStatus") == "accepted_zero_area_media"
    ]
    if len(zero_area) != 21:
        fail(f"expected 21 documented zero-area mapped media hotspots, found {len(zero_area)}")
    if any(h.get("clickable") for h in zero_area):
        fail("zero-area media must not be clickable")
    # Sound Test (slide 358): five speaker shapes map in order to track1-5.
    bindings = {b["id"]: b for b in game.get("mediaBindings") or []}
    s358_shapes = [458768, 458769, 458770, 458771, 458772]
    for i, shape_id in enumerate(s358_shapes, start=1):
        b = bindings.get(f"slide-358-shape-{shape_id}")
        if not b or b.get("audioCueId") != f"linked:track{i}":
            fail(f"slide 358 shape {shape_id} should map to linked:track{i}")

    media_report = generated / "media_death_residuals.json"
    if media_report.exists():
        md = load_json(media_report)
        if md.get("format") != "projectstar-media-death-residuals-v1":
            fail("media_death_residuals format unexpected")
        if md.get("summary", {}).get("mediaResidualHotspotCount", 0) != 21:
            fail("media residual report should document 21 zero-area mapped media hotspots")
        if md.get("summary", {}).get("unresolvedBindingCount", 1) != 0:
            fail("media residual report should have 0 unresolved bindings")
        if md.get("summary", {}).get("terminalSlideCount", 0) != 4:
            fail("media residual report should list 4 terminal (Game Over) slides")

    # Phase 3: chapter walks + island integrity + runtime menu
    walks_path = generated / "chapter_walks.json"
    if not walks_path.exists():
        fail("chapter_walks.json missing — run build_chapter_walks / offline playability")
    walks = load_json(walks_path)
    if walks.get("format") != "projectstar-chapter-walks-v1":
        fail("chapter_walks format unexpected")
    if not walks.get("summary", {}).get("allOk"):
        fail(f"chapter walks failed seeds: {walks.get('summary', {}).get('failedSeeds')}")
    for seed in (1, 121, 243, 358):
        w = next((x for x in walks.get("walks") or [] if x.get("seed") == seed), None)
        if not w or not w.get("ok"):
            fail(f"primary chapter seed {seed} walk missing or not ok")
    # Island 43 primary leaveable; orphan 52 if present ok
    islands = walks.get("islands") or []
    # After slideId resolve, undirected graph is one component (no sealed islands).
    if len(islands) != 0:
        fail(f"expected 0 sealed island reports after slideId resolve, got {len(islands)}")
    for isl in islands:
        if not isl.get("ok"):
            fail(f"island {isl.get('slides')} integrity failed")
    if not chapters.get("summary", {}).get("walksAllOk", True) and chapters.get("summary", {}).get(
        "walksAllOk"
    ) is False:
        fail("chapter_entry_map walksAllOk false")
    menu_path = root / "docs" / "chapter-entries.json"
    if not menu_path.exists():
        fail("docs/chapter-entries.json missing for debug chapter menu")
    menu = load_json(menu_path)
    if not (menu.get("entries") or []):
        fail("chapter-entries menu empty")
    menu_slides = {e.get("slide") for e in menu.get("entries") or []}
    for required in (1, 121, 243, 358):
        if required not in menu_slides:
            fail(f"debug chapter menu missing slide {required}")

    print("offline playability verification passed")
    print(
        f"  TierA={tier['reachableCount']} slides "
        f"death={tier['deathReachable']} freezeLoop161->157={tier['freezeLoop161to157']}"
    )
    print(
        f"  chapters={chapters['summary']['chapterCount']} "
        f"promotes={promotes['summary']['promoteCount']} "
        f"residualSelfs={promotes['summary']['residualSelfCount']} "
        f"clickableViolations=0"
    )
    print(
        f"  chapterWalks seeds={walks['summary']['seedCount']} "
        f"allOk={walks['summary']['allOk']} menuEntries={len(menu.get('entries') or [])}"
    )


if __name__ == "__main__":
    main()
