"""Verify advancement model + game-manifest + runtime hooks stay aligned."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from advancement_lib import build_screen_advancement


def fail(message: str) -> None:
    raise SystemExit(message)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def layer_texts_for_screen(screen: dict) -> list[str]:
    texts: list[str] = []
    for layer in screen.get("layers") or []:
        if layer.get("text"):
            texts.append(str(layer["text"]))
    for hotspot in screen.get("hotspots") or []:
        if hotspot.get("shapeText"):
            texts.append(str(hotspot["shapeText"]))
    return texts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-manifest", type=Path, default=Path("docs/game-manifest.json"))
    parser.add_argument("--advancement-model", type=Path, default=Path("generated/advancement_model.json"))
    parser.add_argument("--app", type=Path, default=Path("docs/app.js"))
    parser.add_argument("--animations", type=Path, default=Path("docs/animation-manifest.json"))
    args = parser.parse_args()

    if not args.game_manifest.exists():
        fail("game-manifest.json missing")
    if not args.app.exists():
        fail("docs/app.js missing")

    app_js = args.app.read_text(encoding="utf-8")
    for snippet in (
        "function handleStageClick",
        "function screenAllowsStageClickAdvance",
        "stageClickAdvancesSlide",
        "click-advance-slide",
        "advanceAnimation()",
    ):
        if snippet not in app_js:
            fail(f"runtime advancement hook missing: {snippet}")

    game = load_json(args.game_manifest)
    screens = game.get("screens") or []
    if len(screens) != 358:
        fail(f"expected 358 screens, found {len(screens)}")
    if not game.get("advancementPolicy"):
        fail("game-manifest missing advancementPolicy")
    policy_version = (game.get("advancementPolicy") or {}).get("version")
    if policy_version is None or int(policy_version) < 4:
        fail("advancementPolicy.version must be >= 4 (noop continue/mirror resolve policy)")

    animations = load_json(args.animations) if args.animations.exists() else {"slides": []}
    anim_by_slide = {int(s["slide"]): s for s in animations.get("slides") or []}

    missing_adv = [s["id"] for s in screens if "advancement" not in s]
    if missing_adv:
        fail(f"screens missing advancement block: {missing_adv[:5]}")

    # Recompute policy for every slide and compare stageClickAdvancesSlide / autoAdvance.
    mismatches = []
    for screen in screens:
        slide = int(screen["slide"])
        recomputed = build_screen_advancement(
            slide=slide,
            total_slides=len(screens),
            transition=screen.get("transition"),
            hotspots=screen.get("hotspots") or [],
            animation_slide=anim_by_slide.get(slide),
            layer_texts=layer_texts_for_screen(screen),
        )
        embedded = screen["advancement"]
        if bool(embedded.get("stageClickAdvancesSlide")) != bool(recomputed.get("stageClickAdvancesSlide")):
            mismatches.append(slide)
        if bool(embedded.get("autoAdvance")) != bool(recomputed.get("autoAdvance")):
            mismatches.append(slide)
    if mismatches:
        fail(f"advancement mismatch vs recomputed policy on slides {sorted(set(mismatches))[:10]}")

    # ProjectStar opening: slides 1-2 auto-advance; slide 3 leaves via the
    # -Start- hotspot resolved by DocSummary slideId to slide 4 (the friendly
    # label was stale). No invented edges.
    for slide in (1, 2):
        screen = screens[slide - 1]
        if not screen["advancement"].get("autoAdvance"):
            fail(f"slide {slide} should autoAdvance (opening cinematic)")
        if screen["advancement"].get("stageClickAdvancesSlide"):
            fail(f"slide {slide} should not stage-click advance")
    s3 = screens[2]
    start_hot = [
        h
        for h in s3.get("hotspots") or []
        if h.get("action") == "hyperlink" and h.get("targetSlide") == 4 and h.get("clickable")
    ]
    if not start_hot:
        fail("slide 3 -Start- hotspot should navigate -> slide 4 (DocSum slideId)")
    if "non_self_hyperlink" not in (s3["advancement"].get("leavePaths") or []):
        fail("slide 3 should have non_self_hyperlink leave path")
    if s3["advancement"].get("stuckReason"):
        fail("slide 3 should not be stuck")

    # Battle interstitial slide 10 stage-clicks to the -shot menu slide 11.
    s10 = screens[9]
    if not s10["advancement"].get("stageClickAdvancesSlide"):
        fail("slide 10 should stageClickAdvancesSlide (click_advance_after_anims)")
    if s10["advancement"].get("nextSequentialId") != "slide-011":
        fail("slide 10 nextSequentialId wrong")

    # Slide 11 -shot: DocSummary slideId -> 12 (stale label read "Slide 11").
    s11 = screens[10]
    shot = [
        h
        for h in s11.get("hotspots") or []
        if h.get("action") == "hyperlink" and h.get("targetSlide") == 12 and h.get("clickable")
    ]
    if not shot:
        fail("slide 11 -shot hotspot should navigate -> slide 12 (DocSum slideId)")

    # Death terminals (Game Over slides) are not stuck.
    for slide in (26, 174, 322, 330):
        sc = screens[slide - 1]
        if not sc["advancement"].get("deathTerminal"):
            fail(f"slide {slide} should be deathTerminal")
        if sc["advancement"].get("stuckReason"):
            fail(f"slide {slide} death should not be stuck")
        if "restart_only" not in (sc["advancement"].get("leavePaths") or []):
            fail(f"slide {slide} should list restart_only leave path")
        if sc["advancement"].get("terminalKind") != "death":
            fail(f"slide {slide} terminalKind should be death")
        if not sc["advancement"].get("terminalNotes"):
            fail(f"slide {slide} missing terminalNotes")

    # No residual stuck slides under policy v3.
    stuck = [s for s in screens if (s.get("advancement") or {}).get("stuckReason")]
    stuck_slides = sorted(int(s["slide"]) for s in stuck)
    if stuck_slides:
        fail(f"unexpected stuck slides after combat all-self resolve: {stuck_slides}")

    if args.advancement_model.exists():
        model = load_json(args.advancement_model)
        if model.get("format") != "projectstar-advancement-model-v1":
            fail("advancement_model format unexpected")
        if model.get("summary", {}).get("slideCount") != 358:
            fail("advancement_model slideCount unexpected")
        if model.get("summary", {}).get("stuckSlideCount") != 0:
            fail(
                f"expected 0 stuck slides after resolve, "
                f"found {model.get('summary', {}).get('stuckSlideCount')}"
            )

    # Hard policy: never ship user_authorized_target_override remaps.
    overridden = [
        (int(s["slide"]), h.get("id") or h.get("shapeId"), h.get("targetSlide"), h.get("originalTargetSlide"))
        for s in screens
        for h in s.get("hotspots") or []
        if h.get("resolveMethod") == "user_authorized_target_override"
    ]
    if overridden:
        fail(f"user_authorized_target_override must be empty, found {overridden[:5]}")

    print("advancement verification passed")


if __name__ == "__main__":
    main()
