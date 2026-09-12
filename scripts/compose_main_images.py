#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the four Leyoujia marketplace main images from one clean product photo.

Outputs:
  天猫主图-1440.jpg       1440x1440, Tmall logo, no size cap
  天猫3比4主图.jpg        1440x1920, Tmall logo, no size cap
  唯品会主图-1440.jpg     1440x1440, no logo, 800-999KB
  唯品会主图950.jpg       950x1200, no logo, 800-999KB
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SKILL_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = SKILL_DIR / "assets"

TEXT_COLOR = (90, 47, 1, 255)
TITLE_FONT_CANDIDATES = (
    ASSETS_DIR / "DreamHanSerifExpCN-W12.ttf",
    Path.home() / "AppData/Local/Microsoft/Windows/Fonts/DreamHanSerifExpCN-W12.ttf",
    Path(r"C:\Windows\Fonts\Source Han Serif SC Heavy (TrueType).ttf"),
    Path(r"C:\Windows\Fonts\NotoSerifSC-VF.ttf"),
)
POINTS_FONT_CANDIDATES = (
    ASSETS_DIR / "DreamHanSerifExpCN-W8.ttf",
    Path.home() / "AppData/Local/Microsoft/Windows/Fonts/DreamHanSerifExpCN-W8.ttf",
    Path(r"C:\Windows\Fonts\Source Han Serif SC Heavy (TrueType).ttf"),
    Path(r"C:\Windows\Fonts\NotoSerifSC-VF.ttf"),
)


@dataclass(frozen=True)
class Target:
    filename: str
    width: int
    height: int
    title_size: int
    subtitle_size: int
    title_top: int
    subtitle_top: int
    title_max_width: int
    subtitle_max_width: int
    min_title_size: int
    min_subtitle_size: int
    logo: Path | None = None
    tmall: bool = False
    max_bytes: int | None = None
    quality: int = 95
    min_bytes: int | None = None
    default_focus: tuple[float, float] = (0.5, 0.65)
    crop_zoom: float = 1.0


TARGETS = (
    Target(
        "天猫主图-1440.jpg", 1440, 1440, 100, 67, 275, 416, 980, 970, 68, 44,
        ASSETS_DIR / "tmall_logo_1440x1440.png", True, None, 100,
    ),
    Target(
        "天猫3比4主图.jpg", 1440, 1920, 107, 72, 326, 478, 1050, 1040, 74, 48,
        ASSETS_DIR / "tmall_logo_1440x1920.png", True, None, 100, None, (0.5, 1.0), 0.90,
    ),
    Target(
        "唯品会主图-1440.jpg", 1440, 1440, 100, 67, 275, 416, 980, 970, 68, 44,
        None, False, 999_000, 100, 819_200, (0.5, 1.0), 0.90,
    ),
    Target(
        "唯品会主图950.jpg", 950, 1200, 71, 48, 197, 298, 680, 680, 46, 30,
        None, False, 999_000, 100, 819_200, (0.5, 1.0), 0.90,
    ),
)




def parse_color_arg(value: str) -> tuple[int, int, int, int]:
    text = value.strip().lstrip('#')
    if len(text) == 6:
        text += "FF"
    if len(text) != 8 or any(ch not in "0123456789abcdefABCDEF" for ch in text):
        raise argparse.ArgumentTypeError("color must be #RRGGBB or #RRGGBBAA")
    return tuple(int(text[i:i + 2], 16) for i in range(0, 8, 2))

def find_font(requested: str | None, candidates: tuple[Path, ...]) -> Path:
    if requested:
        path = Path(requested)
        if path.is_file():
            return path
        raise FileNotFoundError(f"font not found: {path}")
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError("No Chinese font found; pass --title-font/--points-font explicitly.")


def parse_focus(value: str) -> tuple[float, float]:
    try:
        x_text, y_text = value.replace("，", ",").split(",", 1)
        x, y = float(x_text.strip()), float(y_text.strip())
    except Exception as exc:
        raise argparse.ArgumentTypeError("focus must be 'x,y', e.g. 0.5,0.55") from exc
    if not (0 <= x <= 1 and 0 <= y <= 1):
        raise argparse.ArgumentTypeError("focus values must be within 0..1")
    return x, y


def normalize_points(value: str) -> list[str]:
    normalized = value.strip()
    for old in ("，", ",", "、", ";", "；", "|", "｜"):
        normalized = normalized.replace(old, "\n")
    parts = [part.strip() for part in normalized.splitlines() if part.strip()]
    if len(parts) != 3:
        raise ValueError(
            "3个小字卖点必须正好是3项；请用 |、｜、逗号或顿号分隔，例如："
            "全棉磨毛|数码印花|不易掉毛"
        )
    return parts


def cover_image(
    image: Image.Image,
    size: tuple[int, int],
    focus: tuple[float, float],
    zoom: float = 1.0,
) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGBA")
    target_w, target_h = size
    src_w, src_h = image.size
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        crop_h = src_h
        crop_w = int(round(src_h * target_ratio))
    else:
        crop_w = src_w
        crop_h = int(round(src_w / target_ratio))

    crop_w = max(1, min(src_w, int(round(crop_w * zoom))))
    crop_h = max(1, min(src_h, int(round(crop_h * zoom))))
    center_x = focus[0] * src_w
    center_y = focus[1] * src_h
    left = max(0, min(int(round(center_x - crop_w / 2)), src_w - crop_w))
    top = max(0, min(int(round(center_y - crop_h / 2)), src_h - crop_h))
    cropped = image.crop((left, top, left + crop_w, top + crop_h))
    return cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)


def _split_balanced(text: str, lines: int) -> list[str]:
    """Split into a small number of reasonably balanced lines."""
    if lines <= 1:
        return [text]
    best: list[str] | None = None
    best_score = None
    n = len(text)

    def walk(start: int, remaining: int, current: list[str]) -> None:
        nonlocal best, best_score
        if remaining == 1:
            candidate = current + [text[start:]]
            lengths = [len(part) for part in candidate]
            score = max(lengths) - min(lengths)
            if best_score is None or score < best_score:
                best, best_score = candidate, score
            return
        min_end = start + 1
        max_end = n - (remaining - 1)
        for end in range(min_end, max_end + 1):
            walk(end, remaining - 1, current + [text[start:end]])

    if n <= lines:
        return list(text)
    walk(0, lines, [])
    return best or [text]


def fit_text(
    text: str,
    font_path: Path,
    max_size: int,
    min_size: int,
    max_width: int,
    max_lines: int,
) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    for size in range(max_size, min_size - 1, -1):
        font = ImageFont.truetype(str(font_path), size)
        for line_count in range(1, max_lines + 1):
            lines = _split_balanced(text, line_count)
            if all(font.getlength(line) <= max_width for line in lines):
                return font, lines
    font = ImageFont.truetype(str(font_path), min_size)
    return font, _split_balanced(text, max_lines)


def split_point_candidates(parts: list[str]) -> list[list[list[str]]]:
    if len(parts) != 3:
        return []
    return [[parts[:1], parts[1:]], [parts[:2], parts[2:]]]


def _measure_points_line(parts: list[str], font: ImageFont.FreeTypeFont) -> int:
    text_width = sum(font.getlength(part) for part in parts)
    if len(parts) <= 1:
        return int(round(text_width))
    separator_width = max(2, int(round(font.size * 0.0534)))
    side_gap = max(5, int(round(font.size * 0.34)))
    return int(round(text_width + (len(parts) - 1) * (separator_width + side_gap * 2)))


def fit_points(
    parts: list[str],
    font_path: Path,
    max_size: int,
    min_size: int,
    max_width: int,
) -> tuple[ImageFont.FreeTypeFont, list[list[str]]]:
    for size in range(max_size, min_size - 1, -1):
        font = ImageFont.truetype(str(font_path), size)
        candidates = [[parts]]
        candidates.extend(split_point_candidates(parts))
        for candidate in candidates:
            if all(_measure_points_line(line, font) <= max_width for line in candidate):
                return font, candidate
    font = ImageFont.truetype(str(font_path), min_size)
    return font, [parts]


def draw_centered_block(
    draw: ImageDraw.ImageDraw,
    canvas_width: int,
    top: int,
    font: ImageFont.FreeTypeFont,
    lines: list[str],
    color: tuple[int, int, int, int],
) -> None:
    # Keep the centre of a multi-line block close to the single-line reference position.
    line_height = int(round(font.size * 1.06))
    block_height = line_height * len(lines)
    first_line_top = top - (block_height - font.size) // 2
    for index, line in enumerate(lines):
        bbox = font.getbbox(line)
        text_width = font.getlength(line)
        x = int(round((canvas_width - text_width) / 2))
        y = first_line_top + index * line_height - bbox[1]
        draw.text((x, y), line, font=font, fill=color)


def draw_centered_points_block(
    draw: ImageDraw.ImageDraw,
    canvas_width: int,
    top: int,
    font: ImageFont.FreeTypeFont,
    lines: list[list[str]],
    color: tuple[int, int, int, int],
) -> None:
    line_height = int(round(font.size * 1.06))
    block_height = line_height * len(lines)
    first_line_top = top - (block_height - font.size) // 2
    separator_width = max(2, int(round(font.size * 0.0534)))
    side_gap = max(5, int(round(font.size * 0.34)))
    separator_height = max(12, int(round(font.size * 0.856)))

    for line_index, parts in enumerate(lines):
        line_width = _measure_points_line(parts, font)
        x = int(round((canvas_width - line_width) / 2))
        line_top = first_line_top + line_index * line_height
        for part_index, part in enumerate(parts):
            bbox = font.getbbox(part)
            y = line_top - bbox[1]
            draw.text((x, y), part, font=font, fill=color)
            x += int(round(font.getlength(part)))
            if part_index < len(parts) - 1:
                x += side_gap
                y0 = line_top + max(1, int(round(font.size * 0.02)))
                draw.rectangle((x, y0, x + separator_width - 1, y0 + separator_height - 1), fill=color)
                x += separator_width + side_gap


def render_target(
    source: Image.Image,
    target: Target,
    title: str,
    points: list[str],
    title_font_path: Path,
    points_font_path: Path,
    focus: tuple[float, float] | None,
    text_color: tuple[int, int, int, int] = TEXT_COLOR,
    shadow_color: tuple[int, int, int, int] | None = None,
) -> Image.Image:
    target_focus = focus if focus is not None else target.default_focus
    canvas = cover_image(source, (target.width, target.height), target_focus, target.crop_zoom)
    title_font = ImageFont.truetype(str(title_font_path), target.title_size)
    title_lines = [title]
    points_font = ImageFont.truetype(str(points_font_path), target.subtitle_size)
    points_lines = [points]

    if shadow_color is not None:
        shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        draw_centered_block(shadow_draw, target.width, target.title_top, title_font, title_lines, shadow_color)
        draw_centered_points_block(shadow_draw, target.width, target.subtitle_top, points_font, points_lines, shadow_color)
        shadow = shadow.filter(ImageFilter.GaussianBlur(1.15))
        shadow_canvas = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        shadow_canvas.alpha_composite(shadow, (1, 2))
        canvas = Image.alpha_composite(canvas, shadow_canvas)
        text_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_layer)
        draw_centered_block(text_draw, target.width, target.title_top, title_font, title_lines, text_color)
        draw_centered_points_block(text_draw, target.width, target.subtitle_top, points_font, points_lines, text_color)
        canvas = Image.alpha_composite(canvas, text_layer)
    else:
        draw = ImageDraw.Draw(canvas)
        draw_centered_block(draw, target.width, target.title_top, title_font, title_lines, text_color)
        draw_centered_points_block(draw, target.width, target.subtitle_top, points_font, points_lines, text_color)

    if target.logo:
        if not target.logo.is_file():
            raise FileNotFoundError(f"logo asset missing: {target.logo}")
        logo = Image.open(target.logo).convert("RGBA")
        canvas.alpha_composite(logo, (0, 0))
    return canvas


def _encode_jpeg(image: Image.Image, quality: int, optimize: bool = True) -> bytes:
    buf = BytesIO()
    image.convert("RGB").save(
        buf,
        format="JPEG",
        quality=quality,
        subsampling=0,
        optimize=optimize,
        progressive=True,
    )
    return buf.getvalue()


def _pad_jpeg_to_range(data: bytes, min_bytes: int, max_bytes: int | None) -> bytes:
    """Add standards-compliant JPEG COM segments without changing image pixels."""
    if len(data) >= min_bytes:
        return data
    if max_bytes is None or max_bytes < min_bytes:
        raise ValueError("invalid JPEG size range")
    target = min(max_bytes, max(min_bytes, min_bytes + 2048))
    needed = target - len(data)
    if needed <= 0:
        return data
    if not data.endswith(b"\xff\xd9"):
        raise ValueError("JPEG is missing EOI marker")

    segment_count = max(1, (needed + 65536) // 65537)
    while needed - 4 * segment_count > 65533 * segment_count:
        segment_count += 1
    payload_total = needed - 4 * segment_count
    if payload_total < 0:
        raise ValueError("cannot pad JPEG to requested size")

    payloads: list[int] = []
    remaining = payload_total
    for index in range(segment_count):
        left = segment_count - index - 1
        minimum = max(0, remaining - left * 65533)
        payload = max(minimum, min(remaining, 65533))
        payloads.append(payload)
        remaining -= payload
    if remaining:
        raise RuntimeError("JPEG padding distribution failed")

    segments = []
    fill = b"LEYOUJIA_MAIN_IMAGE_SIZE_PADDING"
    for payload_len in payloads:
        payload = (fill * ((payload_len + len(fill) - 1) // len(fill)))[:payload_len]
        segments.append(b"\xff\xfe" + (payload_len + 2).to_bytes(2, "big") + payload)
    padded = data[:-2] + b"".join(segments) + b"\xff\xd9"
    if len(padded) > max_bytes:
        raise RuntimeError("padded JPEG exceeds maximum size")
    return padded


def save_outputs(canvas: Image.Image, target: Target, out_dir: Path) -> tuple[Path, int, bool]:
    destination = out_dir / target.filename
    if target.max_bytes is None:
        data = _encode_jpeg(canvas, target.quality)
    else:
        lo, hi = 20, target.quality
        best: bytes | None = None
        while lo <= hi:
            quality = (lo + hi) // 2
            data = _encode_jpeg(canvas, quality)
            if len(data) <= target.max_bytes:
                best = data
                lo = quality + 1
            else:
                hi = quality - 1
        if best is None:
            best = _encode_jpeg(canvas, 20)
        data = best
    padded = False
    if target.min_bytes is not None and len(data) < target.min_bytes:
        data = _pad_jpeg_to_range(data, target.min_bytes, target.max_bytes)
        padded = True
    destination.write_bytes(data)
    if target.max_bytes is not None and len(data) > target.max_bytes:
        raise RuntimeError(f"{destination.name} exceeds {target.max_bytes} bytes: {len(data)}")
    if target.min_bytes is not None and len(data) < target.min_bytes:
        raise RuntimeError(f"{destination.name} is below {target.min_bytes} bytes: {len(data)}")
    return destination, len(data), padded


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate four Leyoujia marketplace main images")
    parser.add_argument("image", help="clean source product image")
    parser.add_argument("--title", required=True, help="main selling-point copy")
    parser.add_argument("--points", required=True, help="exactly 3 small selling points, delimiter-separated")
    parser.add_argument("--out", required=True, help="output directory")
    parser.add_argument("--font", default=None, help="override both fonts")
    parser.add_argument("--title-font", default=None, help="title font; defaults to Dream Han Serif Exp CN W12")
    parser.add_argument("--points-font", default=None, help="points font; defaults to Dream Han Serif Exp CN W8")
    parser.add_argument("--focus", type=parse_focus, default=None, help="optional focus override; defaults are tuned per output")
    parser.add_argument("--text-color", type=parse_color_arg, default=None, help="optional text color override, e.g. #F7E8CE")
    parser.add_argument("--shadow-color", type=parse_color_arg, default=None, help="optional text shadow color, e.g. #4A2A18C0")
    parser.add_argument("--manifest", action="store_true", help="write output_manifest.json")
    args = parser.parse_args()

    source_path = Path(args.image)
    if not source_path.is_file():
        parser.error(f"source image not found: {source_path}")
    title = args.title.strip()
    if not title:
        parser.error("--title cannot be empty")
    try:
        points = normalize_points(args.points)
    except ValueError as exc:
        parser.error(str(exc))

    title_font_path = find_font(args.title_font or args.font, TITLE_FONT_CANDIDATES)
    points_font_path = find_font(args.points_font or args.font, POINTS_FONT_CANDIDATES)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(source_path) as opened:
        source = ImageOps.exif_transpose(opened).convert("RGBA")
        records = []
        for target in TARGETS:
            canvas = render_target(
                source, target, title, points, title_font_path, points_font_path, args.focus,
                args.text_color or TEXT_COLOR, args.shadow_color,
            )
            destination, size, padded = save_outputs(canvas, target, out_dir)
            records.append({
                "file": destination.name,
                "width": target.width,
                "height": target.height,
                "bytes": size,
                "size_padded": padded,
                "logo": target.tmall,
                "title": title,
                "points": points,
            })
            print(f"[OK] {destination.name}  {target.width}x{target.height}  {size / 1024:.1f} KiB")

    if args.manifest:
        manifest = {
            "source": str(source_path.resolve()),
            "focus": list(args.focus) if args.focus else "auto",
            "title_font": str(title_font_path),
            "points_font": str(points_font_path),
            "text_color": list(args.text_color or TEXT_COLOR),
            "shadow_color": list(args.shadow_color) if args.shadow_color else None,
            "outputs": records,
        }
        manifest_path = out_dir / "output_manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] {manifest_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


















