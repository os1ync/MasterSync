from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
ICONS_DIR = ROOT / "assets" / "icons"
LUCIDE_BASE_URL = "https://raw.githubusercontent.com/lucide-icons/lucide/main/icons"
ICON_SIZE = 512
STROKE = 34
PRIMARY = (168, 85, 247, 255)
SECONDARY = (56, 189, 248, 255)
SOFT = (124, 58, 237, 80)


@dataclass(frozen=True)
class IconSpec:
    local_name: str
    lucide_name: str
    description: str

    @property
    def svg_name(self) -> str:
        return f"{self.local_name}.svg"

    @property
    def png_name(self) -> str:
        return f"{self.local_name}.png"


ICONS: tuple[IconSpec, ...] = (
    IconSpec("coins", "coins", "Economia MasterCoins"),
    IconSpec("casino", "club", "Cassino e jogos"),
    IconSpec("dice", "dice-5", "Dados"),
    IconSpec("slot", "badge-dollar-sign", "Slot machine"),
    IconSpec("welcome", "party-popper", "Boas-vindas"),
    IconSpec("shield", "shield", "Moderacao"),
    IconSpec("user", "user", "Usuario"),
    IconSpec("warning", "triangle-alert", "Avisos e erros"),
    IconSpec("bank", "landmark", "Banco"),
    IconSpec("ranking", "trophy", "Ranking"),
    IconSpec("work", "briefcase-business", "Trabalho"),
    IconSpec("daily", "calendar-check", "Recompensa diaria"),
    IconSpec("success", "circle-check", "Confirmacoes"),
    IconSpec("settings", "settings", "Configuracoes"),
    IconSpec("info", "info", "Informacoes"),
    IconSpec("cherry", "cherry", "Simbolo de slot: cherry"),
    IconSpec("lemon", "circle", "Simbolo de slot: lemon"),
    IconSpec("grape", "grape", "Simbolo de slot: grape"),
    IconSpec("bell", "bell", "Simbolo de slot: bell"),
    IconSpec("diamond", "gem", "Simbolo de slot: diamond"),
    IconSpec("seven", "badge-7", "Simbolo de slot: seven"),
)


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def themed_svg(svg: str) -> str:
    svg = svg.replace('stroke="currentColor"', f'stroke="#a855f7"')
    svg = svg.replace('color="currentColor"', 'color="#a855f7"')
    svg = svg.replace("<svg ", '<svg width="512" height="512" ')
    return svg


def download_svg(spec: IconSpec, timeout: int) -> str | None:
    url = f"{LUCIDE_BASE_URL}/{spec.lucide_name}.svg"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "MasterSYNC-icon-downloader/1.0",
            "Accept": "image/svg+xml,text/plain,*/*",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                return None
            return themed_svg(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def fallback_svg(spec: IconSpec) -> str:
    return f"""<svg width="512" height="512" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <title>{spec.description}</title>
  <rect x="3" y="3" width="18" height="18" rx="5" stroke="#a855f7" stroke-width="2"/>
  <path d="M8 12h8M12 8v8" stroke="#38bdf8" stroke-width="2" stroke-linecap="round"/>
</svg>
"""


def try_cairosvg(svg_path: Path, png_path: Path) -> bool:
    try:
        import cairosvg  # type: ignore

        cairosvg.svg2png(
            url=str(svg_path),
            write_to=str(png_path),
            output_width=ICON_SIZE,
            output_height=ICON_SIZE,
        )
        return True
    except Exception:
        return False


def point(x: float, y: float) -> tuple[int, int]:
    return (round(x / 24 * ICON_SIZE), round(y / 24 * ICON_SIZE))


def bbox(x1: float, y1: float, x2: float, y2: float) -> tuple[int, int, int, int]:
    a = point(x1, y1)
    b = point(x2, y2)
    return (a[0], a[1], b[0], b[1])


def line(draw: ImageDraw.ImageDraw, coords: list[tuple[float, float]], fill=PRIMARY, width: int = STROKE) -> None:
    draw.line([point(x, y) for x, y in coords], fill=fill, width=width, joint="curve")


def circle(draw: ImageDraw.ImageDraw, x: float, y: float, r: float, outline=PRIMARY, width: int = STROKE, fill=None) -> None:
    draw.ellipse(bbox(x - r, y - r, x + r, y + r), outline=outline, width=width, fill=fill)


def rounded(draw: ImageDraw.ImageDraw, x1: float, y1: float, x2: float, y2: float, radius: float, outline=PRIMARY, width: int = STROKE, fill=None) -> None:
    draw.rounded_rectangle(bbox(x1, y1, x2, y2), radius=round(radius / 24 * ICON_SIZE), outline=outline, width=width, fill=fill)


def polygon(draw: ImageDraw.ImageDraw, coords: list[tuple[float, float]], outline=PRIMARY, width: int = STROKE, fill=None) -> None:
    pts = [point(x, y) for x, y in coords]
    if fill:
        draw.polygon(pts, fill=fill)
    draw.line(pts + [pts[0]], fill=outline, width=width, joint="curve")


def draw_pip(draw: ImageDraw.ImageDraw, x: float, y: float) -> None:
    circle(draw, x, y, 0.55, outline=SECONDARY, width=14, fill=SECONDARY)


def draw_fallback_png(name: str, png_path: Path) -> None:
    image = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse(bbox(2, 2, 22, 22), outline=SOFT, width=12)

    if name == "coins":
        circle(draw, 9, 9, 4.4)
        circle(draw, 15, 14, 4.4, outline=SECONDARY)
        line(draw, [(9, 7), (9, 11)], width=22)
        line(draw, [(15, 12), (15, 16)], fill=SECONDARY, width=22)
    elif name == "casino":
        polygon(draw, [(12, 3), (20, 11), (12, 21), (4, 11)])
        circle(draw, 12, 11, 1.5, outline=SECONDARY, width=18, fill=SECONDARY)
    elif name == "dice":
        rounded(draw, 4, 4, 20, 20, 3)
        for p in [(8, 8), (16, 8), (12, 12), (8, 16), (16, 16)]:
            draw_pip(draw, *p)
    elif name == "slot":
        rounded(draw, 4, 4, 20, 20, 2.5)
        for x in (8, 12, 16):
            rounded(draw, x - 1.7, 8, x + 1.7, 13.5, 0.8, outline=SECONDARY, width=16)
        line(draw, [(6.5, 17), (17.5, 17)], width=20)
        line(draw, [(20, 7), (22, 5)], fill=SECONDARY, width=18)
        circle(draw, 22, 5, 0.7, outline=SECONDARY, width=14, fill=SECONDARY)
    elif name == "welcome":
        polygon(draw, [(5, 19), (11, 7), (17, 17)], fill=(168, 85, 247, 38))
        line(draw, [(14, 5), (17, 3), (19, 6)], fill=SECONDARY, width=18)
        line(draw, [(18, 10), (21, 9)], fill=SECONDARY, width=18)
        line(draw, [(7, 7), (5, 5)], width=18)
    elif name == "shield":
        polygon(draw, [(12, 3), (20, 7), (18, 17), (12, 21), (6, 17), (4, 7)], fill=(168, 85, 247, 28))
    elif name == "user":
        circle(draw, 12, 8, 3.3)
        draw.arc(bbox(5, 13, 19, 23), 200, 340, fill=PRIMARY, width=STROKE)
    elif name == "warning":
        polygon(draw, [(12, 3.5), (21, 20), (3, 20)])
        line(draw, [(12, 9), (12, 14)], fill=SECONDARY, width=18)
        draw_pip(draw, 12, 17)
    elif name == "bank":
        polygon(draw, [(4, 9), (12, 4), (20, 9)])
        line(draw, [(5, 20), (19, 20)], fill=SECONDARY, width=20)
        for x in (7, 12, 17):
            line(draw, [(x, 10), (x, 18)], width=18)
    elif name == "ranking":
        rounded(draw, 8, 4, 16, 15, 1.5)
        draw.arc(bbox(3, 6, 9, 13), 270, 90, fill=SECONDARY, width=STROKE)
        draw.arc(bbox(15, 6, 21, 13), 90, 270, fill=SECONDARY, width=STROKE)
        line(draw, [(12, 15), (12, 19)], width=18)
        line(draw, [(8, 20), (16, 20)], fill=SECONDARY, width=20)
    elif name == "work":
        rounded(draw, 4, 7, 20, 19, 2)
        rounded(draw, 9, 4, 15, 8, 1, outline=SECONDARY, width=18)
        line(draw, [(4, 12), (20, 12)], fill=SECONDARY, width=18)
    elif name == "daily":
        rounded(draw, 4, 5, 20, 21, 2)
        line(draw, [(8, 3.5), (8, 7)], fill=SECONDARY, width=18)
        line(draw, [(16, 3.5), (16, 7)], fill=SECONDARY, width=18)
        line(draw, [(8, 14), (11, 17), (17, 11)], fill=SECONDARY, width=20)
    elif name == "success":
        circle(draw, 12, 12, 8)
        line(draw, [(8, 12.5), (11, 15.5), (17, 9)], fill=SECONDARY, width=22)
    elif name == "settings":
        circle(draw, 12, 12, 3.2, outline=SECONDARY)
        for angle in range(0, 360, 45):
            import math

            rad = math.radians(angle)
            x1 = 12 + math.cos(rad) * 6.0
            y1 = 12 + math.sin(rad) * 6.0
            x2 = 12 + math.cos(rad) * 8.2
            y2 = 12 + math.sin(rad) * 8.2
            line(draw, [(x1, y1), (x2, y2)], width=18)
    elif name == "info":
        circle(draw, 12, 12, 8)
        line(draw, [(12, 10.5), (12, 16)], fill=SECONDARY, width=20)
        draw_pip(draw, 12, 7.5)
    elif name == "cherry":
        line(draw, [(12, 10), (15, 5)], fill=SECONDARY, width=14)
        line(draw, [(12, 10), (9, 5)], fill=SECONDARY, width=14)
        circle(draw, 9, 15, 3.2, fill=(168, 85, 247, 55))
        circle(draw, 15, 15, 3.2, outline=SECONDARY, fill=(56, 189, 248, 55))
    elif name == "lemon":
        polygon(draw, [(6, 12), (9, 6), (15, 5), (19, 10), (16, 18), (9, 19)], outline=SECONDARY, fill=(56, 189, 248, 40))
        line(draw, [(8, 13), (16, 11)], width=14)
    elif name == "grape":
        for p in [(10, 8), (14, 8), (8, 12), (12, 12), (16, 12), (10, 16), (14, 16)]:
            circle(draw, *p, 1.5, width=12, fill=(168, 85, 247, 55))
        line(draw, [(12, 6), (14, 4)], fill=SECONDARY, width=14)
    elif name == "bell":
        draw.arc(bbox(6, 5, 18, 19), 200, 340, fill=PRIMARY, width=STROKE)
        line(draw, [(6, 16), (18, 16)], width=22)
        draw_pip(draw, 12, 19)
    elif name == "diamond":
        polygon(draw, [(12, 4), (20, 12), (12, 20), (4, 12)], outline=SECONDARY, fill=(56, 189, 248, 42))
        line(draw, [(8, 8), (16, 16)], width=14)
    elif name == "seven":
        rounded(draw, 5, 5, 19, 19, 2)
        line(draw, [(8, 9), (16, 9), (11, 17)], fill=SECONDARY, width=28)
    else:
        rounded(draw, 4, 4, 20, 20, 3)
        line(draw, [(8, 12), (16, 12)], fill=SECONDARY)

    image.save(png_path)


def write_licenses(specs: tuple[IconSpec, ...]) -> None:
    names = "\n".join(
        f"- `{spec.local_name}` generated locally by this script (no external icon source)"
        if spec.local_name == "seven"
        else f"- `{spec.local_name}` from Lucide `{spec.lucide_name}`"
        for spec in specs
    )
    text = f"""# Icon Licenses

Generated by `scripts/download_icons.py`.

## Source

Primary source: Lucide Icons

- Website: https://lucide.dev/
- Repository: https://github.com/lucide-icons/lucide
- License: ISC License

Icons included:

{names}

## Lucide License Notice

Official license URL:

https://lucide.dev/license

ISC License

Copyright (c) 2026 Lucide Icons and Contributors

Permission to use, copy, modify, and/or distribute this software for any purpose
with or without fee is hereby granted, provided that the above copyright notice
and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS
OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER
TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF
THIS SOFTWARE.

## Feather-Derived Icons

Some Lucide icons are derived from Feather and retain the MIT notice listed by
Lucide.

MIT License

Copyright (c) 2013-present Cole Bemis

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to use,
copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the
Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## Flaticon

This project does not download Flaticon assets automatically. If you choose to
use Flaticon manually, check the license for each icon, keep required
attribution, and only use an API key if you have permission for that workflow.
"""
    (ICONS_DIR / "LICENSES.md").write_text(text, encoding="utf-8")


def build_icons(force: bool = False, timeout: int = 15) -> int:
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    fallback = 0
    converted = 0
    drawn = 0

    env = {**read_env_file(ROOT / ".env"), **os.environ}
    if env.get("FLATICON_API_KEY"):
        print("FLATICON_API_KEY found, but Flaticon is intentionally not used by this script.")

    for spec in ICONS:
        svg_path = ICONS_DIR / spec.svg_name
        png_path = ICONS_DIR / spec.png_name
        if not force and svg_path.exists() and png_path.exists():
            print(f"skip {spec.local_name}: files already exist")
            continue

        svg = download_svg(spec, timeout)
        if svg is None:
            svg = fallback_svg(spec)
            fallback += 1
            print(f"fallback svg {spec.local_name}")
        else:
            downloaded += 1
            print(f"downloaded {spec.local_name} from Lucide ({spec.lucide_name})")

        svg_path.write_text(svg, encoding="utf-8")

        if try_cairosvg(svg_path, png_path):
            converted += 1
            print(f"converted {spec.local_name}.svg -> {spec.local_name}.png")
        else:
            draw_fallback_png(spec.local_name, png_path)
            drawn += 1
            print(f"generated {spec.local_name}.png with Pillow fallback renderer")

    write_licenses(ICONS)
    print()
    print(f"done: downloaded={downloaded}, fallback_svg={fallback}, converted={converted}, pillow_png={drawn}")
    print(f"icons directory: {ICONS_DIR}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Download/generate open-source icons for Master SYNC.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing SVG/PNG files.")
    parser.add_argument("--timeout", type=int, default=15, help="Network timeout in seconds per icon.")
    args = parser.parse_args()
    return build_icons(force=args.force, timeout=args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
