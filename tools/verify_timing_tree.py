"""Regression checks for extracted PP10 animation timing-tree data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def as_count_map(items: list[dict[str, object]]) -> dict[int, int]:
    return {int(item["value"]): int(item["count"]) for item in items}


def record_count(report: dict[str, object], rec_type: int) -> int:
    for item in report["recordCounts"]:
        if int(item["type"]) == rec_type:
            return int(item["count"])
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", nargs="?", type=Path, default=Path("generated/timing_tree_audit.json"))
    args = parser.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    assert report["source"] == "ProjectStar Part1 V1.1.ppt"
    assert report["binaryTagBlobsWithTimingTrees"] == 358
    assert report["slidesWithTimingTrees"] == 358

    visual_targets = report["visualTargetReferences"]
    assert visual_targets["count"] == 3871
    assert visual_targets["shapeReferenceCount"] == 3846
    assert visual_targets["soundReferenceCount"] == 25
    assert visual_targets["unresolvedShapeReferenceCount"] == 0

    assert report["visualShapeReferences"]["count"] == 3846
    assert report["visualShapeReferences"]["unresolvedCount"] == 0

    assert record_count(report, 61764) == 7349  # RT_TimeExtTimeNodeContainer
    assert record_count(report, 61735) == 7741  # RT_TimeNode
    assert record_count(report, 61736) == 5738  # RT_TimeCondition
    assert record_count(report, 61737) == 1366  # RT_TimeModifier
    assert record_count(report, 61761) == 232  # RT_TimeSequenceData
    assert record_count(report, 61762) == 22289  # RT_TimeVariant

    condition_events = as_count_map(report["conditionSummary"]["triggerEvents"])
    assert condition_events == {0: 4551, 1: 227, 3: 28, 4: 369, 5: 10, 9: 249, 10: 253, 11: 51}

    modifier_types = as_count_map(report["modifierSummary"]["modifierTypes"])
    assert modifier_types == {0: 73, 3: 577, 4: 576, 5: 140}

    animate_calc_modes = as_count_map(report["animateBehaviorSummary"]["calcModes"])
    assert animate_calc_modes == {0: 802, 1: 41}
    animate_value_types = as_count_map(report["animateBehaviorSummary"]["valueTypes"])
    assert animate_value_types == {1: 41, 2: 802}

    animation_value_times = as_count_map(report["animationValueSummary"]["times"])
    assert animation_value_times == {0: 841, 500: 805, 1000: 39}

    sequence_next_actions = as_count_map(report["sequenceSummary"]["nextActions"])
    assert sequence_next_actions == {1: 232}

    variant_strings = {item["value"]: int(item["count"]) for item in report["variantSummary"]["strings"]}
    for required in ("style.visibility", "visible", "fade", "ppt_x", "ppt_y", "#ppt_x", "#ppt_y"):
        assert required in variant_strings, required

    print("timing tree verification passed")


if __name__ == "__main__":
    main()
