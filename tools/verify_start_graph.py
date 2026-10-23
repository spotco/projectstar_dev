"""Verify start-directed graph baseline and sealed-island analysis stay stable."""

from __future__ import annotations

import json
from pathlib import Path

from analyze_start_graph import EXPECTED_SEALED_ISLANDS, EXPECTED_START_REACHABLE, main as rebuild_analysis
from scan_advancement_coverage import build_runtime_out, bfs


def fail(message: str) -> None:
    raise SystemExit(message)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    game_path = root / "docs" / "game-manifest.json"
    analysis_path = root / "generated" / "start_graph_analysis.json"

    if not game_path.exists():
        fail("docs/game-manifest.json missing")

    # Rebuild analysis so verify is self-contained.
    rebuild_analysis()
    if not analysis_path.exists():
        fail("start_graph_analysis.json missing after rebuild")

    game = load_json(game_path)
    screens = game.get("screens") or []
    if len(screens) != 358:
        fail(f"expected 358 screens, found {len(screens)}")

    outbound = build_runtime_out(screens)
    from_start = bfs(outbound, 1)
    if from_start != set(EXPECTED_START_REACHABLE):
        missing = sorted(set(EXPECTED_START_REACHABLE) - from_start)
        extra = sorted(from_start - set(EXPECTED_START_REACHABLE))
        fail(
            "start reachability drifted from baseline "
            f"(missing={missing[:15]}, extra={extra[:15]}, count={len(from_start)})"
        )

    # Freeze-frame gag loop still returns s161 -> s157.
    if 157 not in outbound.get(161, set()):
        fail("s161 should hyperlink/resolve to s157 (freeze loop return)")

    # No edge from baseline set into sealed islands (binary+runtime).
    for island in EXPECTED_SEALED_ISLANDS:
        for slide in EXPECTED_START_REACHABLE:
            leaked = outbound.get(slide, set()) & island
            if leaked:
                fail(f"unexpected edge from start component s{slide} into island {sorted(leaked)}")

    # s011 -shot option resolves via slideId directly to s012 (stale label was self).
    s11 = screens[10]
    if s11["advancement"].get("stuckReason"):
        fail("s011 should leave to s012 (slideId-resolved -shot option)")
    combat = [
        h
        for h in s11.get("hotspots") or []
        if h.get("action") == "hyperlink" and h.get("targetSlide") == 12 and h.get("clickable")
    ]
    if len(combat) < 1:
        fail("s011 expected clickable -shot option -> 12 after slideId resolve")

    analysis = load_json(analysis_path)
    summary = analysis.get("summary") or {}
    if summary.get("sourceLimitation"):
        fail("analysis should mark sourceLimitation false: full deck reachable, no bridges needed")
    if summary.get("inventedBridgeApplied"):
        fail("inventedBridgeApplied should be false (no silent story bridges)")
    if summary.get("reachableFromStartCount") != len(EXPECTED_START_REACHABLE):
        fail("analysis reachable count mismatch")
    if not summary.get("matchesExpectedBaseline"):
        fail("analysis baseline match flag false")

    # Zero-inbound roots after slideId resolve: none (every slide is reached).
    zero = {int(z["slide"]) for z in analysis.get("zeroInboundSlides") or []}
    if zero:
        fail(f"expected no zero-inbound roots, found {sorted(zero)}")

    print("start graph verification passed")
    print(
        f"  reachableFromStart={len(from_start)} "
        f"sealedIslands={len(EXPECTED_SEALED_ISLANDS)} "
        f"sourceLimitation=false"
    )


if __name__ == "__main__":
    main()
