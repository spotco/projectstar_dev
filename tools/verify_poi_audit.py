"""Verify Apache POI audit output against extracted timing data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--poi-audit", type=Path, default=Path("generated/poi_audit.tsv"))
    parser.add_argument("--timing", type=Path, default=Path("generated/timing_manifest.json"))
    args = parser.parse_args()

    lines = args.poi_audit.read_text(encoding="utf-8-sig").splitlines()
    timing = json.loads(args.timing.read_text(encoding="utf-8"))

    poi_shapes = set()
    counters = {
        "slides": 0,
        "pictures": 0,
        "pictureInstances": 0,
        "sounds": 0,
        "transitions": 0,
        "links": 0,
        "geometry": 0,
        "style": 0,
        "clip": 0,
        "textStyle": 0,
        "paragraphs": 0,
        "textRuns": 0,
    }
    for line in lines:
        parts = line.split("\t")
        key = parts[0]
        if key == "slides=358":
            counters["slides"] = 358
        elif key == "pictures=282":
            counters["pictures"] = 282
        elif key == "sounds=17":
            counters["sounds"] = 17
        elif key == "SHAPE":
            poi_shapes.add((int(parts[1]), int(parts[3])))
        elif key == "PICTURE":
            counters["pictureInstances"] += 1
        elif key == "GEOMETRY":
            counters["geometry"] += 1
        elif key == "STYLE":
            counters["style"] += 1
        elif key == "CLIP":
            counters["clip"] += 1
        elif key == "TEXTSTYLE":
            counters["textStyle"] += 1
        elif key == "PARAGRAPH":
            counters["paragraphs"] += 1
        elif key == "TEXTRUN":
            counters["textRuns"] += 1
        elif key == "TRANSITION":
            counters["transitions"] += 1
        elif key in {"TEXTLINK", "SHAPELINK"}:
            counters["links"] += 1

    animations = timing["animations"]
    missing_animation_shapes = [
        (animation["slide"], animation["shapeId"])
        for animation in animations
        if (animation["slide"], animation["shapeId"]) not in poi_shapes
    ]
    assert counters["slides"] == 358, counters
    assert counters["pictures"] == 282, counters
    assert counters["sounds"] == 17, counters
    assert counters["pictureInstances"] == 770, counters
    assert counters["geometry"] == 2603, counters
    assert counters["style"] == 2603, counters
    assert counters["clip"] == 770, counters
    assert counters["textStyle"] == 1833, counters
    assert counters["paragraphs"] == 2149, counters
    assert counters["textRuns"] == 2245, counters
    assert counters["transitions"] == 358, counters
    assert counters["links"] == 218, counters
    assert len(timing["transitions"]) == 358
    assert len(animations) == 922
    assert not missing_animation_shapes, missing_animation_shapes[:10]
    print("POI audit verification passed")


if __name__ == "__main__":
    main()
