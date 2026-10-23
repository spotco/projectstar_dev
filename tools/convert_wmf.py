"""Convert extracted WMF assets to browser-usable PNGs (ProjectStar).

ProjectStar contains two Office clip-art WMF pictures (a silhouette figure
on slide 188 and candy clip-art on slide 272). Browsers cannot render WMF,
so this step rasterises each ``generated/assets/asset-NNN.wmf`` with
LibreOffice headless, autocrops the A4 page LibreOffice renders to the
artwork's non-white bounding box, and flood-fills the page white to
transparent from the image edges (interior whites are preserved).

Output: ``generated/assets/asset-NNN.wmf.png`` plus
``generated/wmf_conversions.json``. Requires ``soffice`` on PATH.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from collections import deque
from pathlib import Path

from PIL import Image


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def flood_transparent(image: Image.Image, threshold: int = 248) -> Image.Image:
    """Make edge-connected near-white pixels transparent."""
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()
    seen = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    def is_white(x: int, y: int) -> bool:
        r, g, b, a = pixels[x, y]
        return a > 0 and r >= threshold and g >= threshold and b >= threshold

    for x in range(width):
        for y in (0, height - 1):
            if is_white(x, y):
                queue.append((x, y))
    for y in range(height):
        for x in (0, width - 1):
            if is_white(x, y):
                queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        idx = y * width + x
        if seen[idx]:
            continue
        seen[idx] = 1
        if not is_white(x, y):
            continue
        r, g, b, _a = pixels[x, y]
        pixels[x, y] = (r, g, b, 0)
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < width and 0 <= ny < height and not seen[ny * width + nx]:
                queue.append((nx, ny))
    return rgba


def convert_one(soffice: str, wmf: Path, out_png: Path) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="wmf-convert-") as tmp:
        tmpdir = Path(tmp)
        shutil.copy2(wmf, tmpdir / wmf.name)
        subprocess.run(
            [
                soffice,
                "--headless",
                f"-env:UserInstallation=file://{tmpdir}/lo-profile",
                "--convert-to",
                "png",
                "--outdir",
                str(tmpdir),
                str(tmpdir / wmf.name),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        rendered = tmpdir / (wmf.stem + ".png")
        if not rendered.exists():
            raise FileNotFoundError(f"LibreOffice did not render {wmf}")
        image = Image.open(rendered).convert("RGBA")
        # Autocrop to non-white content.
        gray = image.convert("L")
        mask = gray.point(lambda v: 0 if v >= 248 else 255)
        bbox = mask.getbbox()
        if bbox:
            image = image.crop(bbox)
        image = flood_transparent(image)
        image.save(out_png, format="PNG")
    return {
        "source": wmf.as_posix(),
        "output": out_png.as_posix(),
        "width": image.size[0],
        "height": image.size[1],
        "bytes": out_png.stat().st_size,
        "sha256": sha256(out_png),
        "converter": "libreoffice-headless + autocrop + edge flood transparency",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=Path("generated/inventory.json"))
    parser.add_argument("--output", type=Path, default=Path("generated/wmf_conversions.json"))
    parser.add_argument("--soffice", default=shutil.which("soffice") or "soffice")
    args = parser.parse_args()

    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    records = []
    for asset in inventory["embedded_assets"]:
        if asset.get("encoding") != "wmf":
            continue
        wmf = Path(asset["path"])
        out_png = wmf.with_suffix(".wmf.png")
        record = convert_one(args.soffice, wmf, out_png)
        record["assetId"] = asset["id"]
        records.append(record)
        print(f"Converted {asset['id']}: {wmf} -> {out_png} ({record['width']}x{record['height']})")

    payload = {"format": "projectstar-wmf-conversions-v1", "conversions": records}
    args.output.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} with {len(records)} conversions")


if __name__ == "__main__":
    main()
