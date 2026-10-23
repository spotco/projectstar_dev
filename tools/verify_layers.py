"""Regression checks for the generated non-Aspose layer manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", nargs="?", type=Path, default=Path("generated/layers.json"))
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    summary = manifest["summary"]
    assert manifest["format"] == "projectstar-layer-manifest-v1"
    assert summary["slides"] == 358
    assert summary["layers"] == 2603
    assert summary["imageInstances"] == 770
    assert summary["textLayers"] == 1192
    assert summary["shapeLayers"] == 641
    assert summary["animatedShapeTargets"] == 1373
    assert summary["animatedLayers"] == 1373
    assert summary["styledLayers"] == 2603
    assert summary["transformLayers"] == 2603
    assert summary["textStyleLayers"] == 1192
    assert summary["paragraphs"] == 1508
    assert summary["textRuns"] == 1604
    assert summary["actionBoundLayers"] == 257
    assert summary["hyperlinkBoundLayers"] == 213

    image_layers = []
    animated_images = 0
    animated_text = 0
    animated_shape = 0
    action_bound_layers = 0
    hyperlink_bound_layers = 0
    for slide in manifest["slides"]:
        assert "layers" in slide
        z_orders = [layer["zOrder"] for layer in slide["layers"]]
        assert z_orders == sorted(z_orders), slide["slide"]
        for layer in slide["layers"]:
            bounds = layer["bounds"]
            assert "points" in bounds
            assert layer["type"] in {"image", "text", "shape"}
            assert "shapeType" in layer
            assert "transform" in layer
            assert {"rotation", "flipHorizontal", "flipVertical"} <= set(layer["transform"])
            assert "style" in layer
            if "actions" in layer:
                action_bound_layers += 1
                for action in layer["actions"]:
                    assert "actionCode" in action
                    assert "hyperlinkId" in action
            if "hyperlinks" in layer:
                hyperlink_bound_layers += 1
                for hyperlink in layer["hyperlinks"]:
                    assert "id" in hyperlink
                    assert "type" in hyperlink
            if layer["animated"] and layer["type"] == "image":
                animated_images += 1
            if layer["animated"] and layer["type"] == "text":
                animated_text += 1
            if layer["animated"] and layer["type"] == "shape":
                animated_shape += 1
            if layer["type"] == "image":
                assert "clip" in layer
                image_layers.append(layer)
                path = Path(layer["instancePath"])
                assert path.exists(), path
                assert path.stat().st_size == layer.get("instanceBytes", layer["sourceBytes"]), path
            if layer["type"] == "text":
                assert "textStyle" in layer
                assert "paragraphs" in layer
                assert "textRuns" in layer
                assert layer["textStyle"]["wordWrap"] in {True, False}

    assert len(image_layers) == 770
    assert animated_images > 0
    assert animated_text > 0
    assert animated_shape > 0
    assert action_bound_layers == 257
    assert hyperlink_bound_layers == 213
    print("layer manifest verification passed")


if __name__ == "__main__":
    main()
