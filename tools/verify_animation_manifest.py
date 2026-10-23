"""Regression checks for the generated PP10 animation manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", nargs="?", type=Path, default=Path("generated/animations.json"))
    parser.add_argument("--layers", type=Path, default=Path("generated/layers.json"))
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    layers = json.loads(args.layers.read_text(encoding="utf-8"))
    summary = manifest["summary"]

    assert manifest["format"] == "projectstar-animation-manifest-v1"
    assert summary["slidesWithAnimations"] == 358
    assert summary["timeNodeContainers"] == 7349
    assert summary["recordCounts"]["RT_TimeNode"] == 7741
    assert summary["recordCounts"]["RT_TimeCondition"] == 5738
    assert summary["recordCounts"]["RT_TimeModifier"] == 1366
    assert summary["recordCounts"]["RT_TimeSequenceData"] == 232
    assert summary["recordCounts"]["RT_TimeVariant"] == 22289
    assert summary["recordCounts"]["RT_TimeSubEffectContainer"] == 392
    assert summary["recordCounts"]["RT_ParaBuild"] == 552
    assert summary["recordCounts"]["RT_TimeIterateData"] == 443
    assert summary["subEffectContainers"] == 392
    assert summary["paraBuildCount"] == 552
    assert summary["iterateDataCount"] == 443
    assert summary["paraBuildKinds"].get("asAWhole") == 549
    assert summary["paraBuildKinds"].get("allAtOnce") == 3
    assert sum(summary["paraBuildKinds"].values()) == 552
    assert summary["iterateKinds"]["byLetter"] == 443
    assert summary["unresolvedShapeTargets"] == []
    assert summary["conditionEvents"] == {"0": 4551, "1": 227, "3": 28, "4": 369, "5": 10, "9": 249, "10": 253, "11": 51}
    assert summary["modifierTypes"] == {"0": 73, "3": 577, "4": 576, "5": 140}
    assert summary["animateCalcModes"] == {"0": 802, "1": 41}
    # Shape/sound targets include subEffect + behavior targets after Phase 5.2 expansion.
    assert summary["shapeTargets"] >= 1373
    assert summary["soundTargets"] >= 1

    layer_targets = {
        (int(slide["slide"]), int(layer["shapeId"]))
        for slide in layers["slides"]
        for layer in slide["layers"]
        if layer.get("animated")
    }
    manifest_targets = set()
    for slide in manifest["slides"]:
        slide_number = int(slide["slide"])
        stack = list(slide["rootTimeNodes"])
        while stack:
            node = stack.pop()
            for target in node.get("targets", []):
                if target.get("kind") == "shape":
                    manifest_targets.add((slide_number, int(target["shapeId"])))
            for behavior in node.get("behaviors") or []:
                for target in behavior.get("targets") or []:
                    if target.get("kind") == "shape":
                        manifest_targets.add((slide_number, int(target["shapeId"])))
            stack.extend(node.get("subEffects") or [])
            stack.extend(node.get("children") or [])
        # Builds reference shapes that may only appear as build targets.
        for build in slide.get("builds") or []:
            if build.get("shapeId") is not None:
                # builds are not required to equal animated layer set
                pass
    # Every animated layer target must appear in the expanded timing tree.
    missing = layer_targets - manifest_targets
    assert not missing, f"animated layer targets missing from manifest: {sorted(missing)[:20]}"
    # Spot-check SubEffect expansion on an opening battle slide (slide 13).
    slide3 = next(s for s in manifest["slides"] if int(s["slide"]) == 13)
    assert len(slide3.get("builds") or []) == 3
    assert all(
        (b.get("paraBuild") or {}).get("paraBuildName") == "asAWhole" for b in slide3["builds"]
    )
    sub_effect_nodes = []
    stack = list(slide3["rootTimeNodes"])
    while stack:
        node = stack.pop()
        for sub in node.get("subEffects") or []:
            sub_effect_nodes.append(sub)
            stack.append(sub)
        stack.extend(node.get("children") or [])
    assert len(sub_effect_nodes) == 10, len(sub_effect_nodes)
    assert all(n.get("kind") == "subEffect" for n in sub_effect_nodes)
    assert all(n.get("behaviors") for n in sub_effect_nodes), "slide 13 subEffects should carry set behaviors"
    print("animation manifest verification passed")


if __name__ == "__main__":
    main()
