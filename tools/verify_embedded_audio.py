"""Regression checks for extracted and converted embedded PowerPoint sounds."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--embedded", type=Path, default=Path("generated/embedded-audio/embedded_audio_manifest.json"))
    parser.add_argument("--audio", type=Path, default=Path("generated/audio/audio_manifest.json"))
    args = parser.parse_args()

    embedded = json.loads(args.embedded.read_text(encoding="utf-8"))
    audio = json.loads(args.audio.read_text(encoding="utf-8"))
    assert len(embedded) == 17
    assert [item["embeddedSoundId"] for item in embedded] == [9, 10, 12, 15, 17, 18, 21, 22, 27, 28, 31, 34, 46, 48, 55, 57, 62]
    for item in embedded:
        path = Path(item["path"])
        assert path.exists(), path
        assert path.stat().st_size == item["bytes"], path
        assert path.read_bytes().startswith(b"RIFF"), path

    converted_embedded = [item for item in audio if item.get("embeddedSoundId") is not None]
    assert len(audio) == 22
    assert len(converted_embedded) == 17
    midi_entries = [item for item in audio if item["source"].endswith(".mid")]
    assert len(midi_entries) == 0  # ProjectStar has no MIDI sources (goblins did)
    linked_mp3 = [item for item in audio if item["source"].endswith(".mp3")]
    assert [item["source"] for item in linked_mp3] == ["track1.mp3", "track2.mp3", "track3.mp3", "track4.mp3", "track5.mp3"]
    for item in linked_mp3:
        assert item["status"] == "converted"
        assert len(item["outputs"]) == 2
        for output in item["outputs"]:
            path = Path(output["path"])
            assert path.exists(), path
            assert path.stat().st_size == output["bytes"], path
    assert [item["embeddedSoundId"] for item in converted_embedded] == [9, 10, 12, 15, 17, 18, 21, 22, 27, 28, 31, 34, 46, 48, 55, 57, 62]
    for item in converted_embedded:
        assert item["status"] == "converted"
        assert len(item["outputs"]) == 2
        for output in item["outputs"]:
            path = Path(output["path"])
            assert path.exists(), path
            assert path.stat().st_size == output["bytes"], path
    print("embedded audio verification passed")


if __name__ == "__main__":
    main()
