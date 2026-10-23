"""Regression checks for the first extraction baseline."""

from __future__ import annotations

import json
from pathlib import Path


EXPECTED_SOURCE_SHA256 = "888ba774bb23cf6bd748240cfafa248577ca522ca90dc202f1f98cfd07534021"


def main() -> None:
    inventory_path = Path("generated/inventory.json")
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    assert inventory["source"]["sha256"] == EXPECTED_SOURCE_SHA256
    assert len(inventory["slides"]) == 358
    assert inventory["record_type_counts"]["1006"] == 358
    assert inventory["record_type_counts"]["4083"] == 265
    assert inventory["record_type_counts"]["4055"] == 218
    assert len(inventory["hyperlinks"]) == 218
    assert len(inventory["objects"]) == 3340
    assert len(inventory["text_runs"]) == 960
    assert len(inventory["interactive_actions"]) == 265
    assert len(inventory["navigation_edges"]) == 217
    assert all(action["shape_id"] is not None for action in inventory["interactive_actions"])
    assert all(action["bounds"] is not None for action in inventory["interactive_actions"])
    assert all(edge["target_slide"] for edge in inventory["navigation_edges"])
    assert len(inventory["embedded_assets"]) == 282
    assert sum(asset["encoding"] == "png" for asset in inventory["embedded_assets"]) == 279
    assert sum(asset["encoding"] == "jpeg" for asset in inventory["embedded_assets"]) == 1
    assert sum(asset["encoding"] == "wmf" for asset in inventory["embedded_assets"]) == 2
    for asset in inventory["embedded_assets"]:
        path = Path(asset["path"])
        assert path.exists(), path
        assert path.stat().st_size == asset["bytes"], path
    print("inventory verification passed")


if __name__ == "__main__":
    main()
