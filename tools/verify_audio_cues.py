"""Verify browser audio cue metadata and media binding behavior."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("docs/game-manifest.json"))
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    audio = manifest.get("audio", [])
    cues = manifest.get("audioCues", [])
    bindings = manifest.get("mediaBindings", [])

    assert len(audio) == 22
    assert len(cues) == 22
    assert len(bindings) == 26
    assert Counter(binding["status"] for binding in bindings) == {"mapped": 26}

    source_cues = [cue for cue in cues if cue.get("source")]
    unresolved_cues = [cue for cue in cues if cue.get("kind") == "unresolved_legacy_media_cue"]
    assert len(source_cues) == 22
    assert len(unresolved_cues) == 0
    assert {cue["legacyCueId"] for cue in unresolved_cues} == set()

    cue_ids = {cue["id"] for cue in source_cues}
    assert {f"linked:track{n}" for n in range(1, 6)}.issubset(cue_ids)
    midi = next(cue for cue in source_cues if cue["id"] == "linked:track1")
    assert midi["outputs"]
    assert all(output["path"].startswith("assets/audio/") for output in midi["outputs"])

    embedded_sound_cues = {cue.get("embeddedSoundId") for cue in source_cues if cue.get("embeddedSoundId") is not None}
    assert embedded_sound_cues == {9, 10, 12, 15, 17, 18, 21, 22, 27, 28, 31, 34, 46, 48, 55, 57, 62}

    for binding in bindings:
        behavior = binding.get("cueBehavior")
        assert behavior, binding["id"]
        assert behavior["trigger"] == "animation_command"
        assert behavior["command"] == "playFrom"
        assert behavior["startSeconds"] == 0.0
        assert behavior["requiresUserGesture"] is True
        if binding["status"] == "mapped":
            assert binding.get("audioCueId") in cue_ids
            assert binding.get("audioOutputs")
        else:
            assert binding.get("unresolvedReason")

    print("audio cue verification passed")


if __name__ == "__main__":
    main()
