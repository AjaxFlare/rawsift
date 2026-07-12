#!/usr/bin/env python3
"""Non-destructive technical first-pass culling for RAW and ordinary photos."""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


SUPPORTED_EXTENSIONS = {
    ".nef", ".nrw", ".dng", ".cr2", ".cr3", ".arw", ".raf",
    ".orf", ".rw2", ".pef", ".srw", ".jpg", ".jpeg", ".png",
    ".tif", ".tiff", ".webp", ".bmp",
}
ORDINARY_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}
LABEL_ZH = {
    "pick": "精选候选",
    "maybe": "备选",
    "duplicate": "重复备选",
    "reject": "技术淘汰候选",
    "focus-bracket": "对焦包围",
    "exposure-bracket": "曝光包围",
}
LABEL_EN = {
    "pick": "PICK",
    "maybe": "MAYBE",
    "duplicate": "DUP",
    "reject": "REJECT",
    "focus-bracket": "FOCUS",
    "exposure-bracket": "EXPOSURE",
}
LABEL_COLOR = {
    "pick": "#18a56a",
    "maybe": "#d79b25",
    "duplicate": "#6a75d8",
    "reject": "#d65252",
    "focus-bracket": "#168aa3",
    "exposure-bracket": "#d47725",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely score and group RAW/JPEG photos without modifying originals."
    )
    parser.add_argument("input", type=Path, help="Input photo or directory")
    parser.add_argument("--output", type=Path, default=Path("rawsift-report"), help="Output report directory")
    parser.add_argument("--profile", choices=("general", "macro-nature"), default="general")
    parser.add_argument("--keep-rate", type=float, default=0.25)
    parser.add_argument("--duplicate-window", type=int, default=8)
    parser.add_argument("--duplicate-similarity", type=float, default=0.90)
    parser.add_argument("--max-preview", type=int, default=1600)
    parser.add_argument("--bracket-detection", choices=("auto", "off"), default="auto")
    parser.add_argument("--copy-bracket-originals", action="store_true", help="Copy detected bracket originals into report subfolders")
    parser.add_argument("--export-xmp", action="store_true", help="Export optional rating sidecars under the report directory")
    args = parser.parse_args()
    if not 0.10 <= args.keep_rate <= 0.80:
        parser.error("--keep-rate must be between 0.10 and 0.80")
    if not 1 <= args.duplicate_window <= 100:
        parser.error("--duplicate-window must be between 1 and 100")
    if not 0.80 <= args.duplicate_similarity <= 0.99:
        parser.error("--duplicate-similarity must be between 0.80 and 0.99")
    if not 800 <= args.max_preview <= 4000:
        parser.error("--max-preview must be between 800 and 4000")
    return args


def unique_output_dir(requested: Path) -> Path:
    requested = requested.expanduser().resolve()
    if requested.exists() and not requested.is_dir():
        raise ValueError(f"Output path is not a directory: {requested}")
    if not requested.exists() or not any(requested.iterdir()):
        requested.mkdir(parents=True, exist_ok=True)
        return requested
    for index in range(2, 1000):
        candidate = requested.with_name(f"{requested.name}-{index}")
        if not candidate.exists():
            candidate.mkdir(parents=True)
            return candidate
    raise RuntimeError("Could not create a unique output directory")


def discover_files(source: Path) -> tuple[Path, list[Path]]:
    source = source.expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"Input does not exist: {source}")
    if source.is_file():
        if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported input extension: {source.suffix}")
        return source.parent, [source]
    files = sorted(
        (p for p in source.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS),
        key=lambda p: str(p.relative_to(source)).casefold(),
    )
    return source, files


def open_pillow(path: Path) -> Image.Image:
    with Image.open(path) as image:
        image.load()
        return ImageOps.exif_transpose(image).convert("RGB")


def image_from_jpeg_bytes(blob: bytes) -> Image.Image:
    with Image.open(io.BytesIO(blob)) as image:
        image.load()
        return ImageOps.exif_transpose(image).convert("RGB")


def exiftool_preview(path: Path) -> tuple[Image.Image, str] | None:
    if not shutil.which("exiftool"):
        return None
    for tag in ("JpgFromRaw", "PreviewImage", "OtherImage", "ThumbnailImage"):
        proc = subprocess.run(
            ["exiftool", "-b", f"-{tag}", str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if proc.returncode == 0 and len(proc.stdout) > 4096:
            try:
                return image_from_jpeg_bytes(proc.stdout), f"exiftool:{tag}"
            except Exception:
                continue
    return None


def embedded_jpeg_preview(path: Path) -> tuple[Image.Image, str] | None:
    data = path.read_bytes()
    candidates: list[tuple[int, int, int, int]] = []
    cursor = 0
    while len(candidates) < 64:
        start = data.find(b"\xff\xd8\xff", cursor)
        if start < 0:
            break
        end = data.find(b"\xff\xd9", start + 4)
        cursor = start + 3
        if end < 0:
            continue
        end += 2
        length = end - start
        if length < 4096:
            continue
        try:
            with Image.open(io.BytesIO(data[start:end])) as candidate:
                width, height = candidate.size
            if width >= 320 and height >= 240:
                candidates.append((width * height, start, end, length))
        except Exception:
            continue
    if not candidates:
        return None
    _, start, end, _ = max(candidates)
    return image_from_jpeg_bytes(data[start:end]), "embedded-jpeg"


def rawpy_preview(path: Path) -> tuple[Image.Image, str] | None:
    try:
        import rawpy  # type: ignore
    except ImportError:
        return None
    try:
        with rawpy.imread(str(path)) as raw:
            try:
                thumb = raw.extract_thumb()
                if thumb.format == rawpy.ThumbFormat.JPEG:
                    return image_from_jpeg_bytes(thumb.data), "rawpy:embedded"
                array = thumb.data
            except Exception:
                array = raw.postprocess(
                    use_camera_wb=True,
                    half_size=True,
                    no_auto_bright=False,
                    output_bps=8,
                )
        return Image.fromarray(array).convert("RGB"), "rawpy"
    except Exception:
        return None


def ffmpeg_preview(path: Path) -> tuple[Image.Image, str] | None:
    if not shutil.which("ffmpeg"):
        return None
    handle = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    temp_path = Path(handle.name)
    handle.close()
    try:
        proc = subprocess.run(
            ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(path), "-frames:v", "1", str(temp_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=False,
        )
        if proc.returncode == 0 and temp_path.exists() and temp_path.stat().st_size > 4096:
            return open_pillow(temp_path), "ffmpeg"
    finally:
        temp_path.unlink(missing_ok=True)
    return None


def extract_preview(path: Path) -> tuple[Image.Image, str]:
    errors: list[str] = []
    if path.suffix.lower() in ORDINARY_EXTENSIONS:
        try:
            return open_pillow(path), "pillow"
        except Exception as exc:
            errors.append(f"Pillow: {exc}")
    for decoder in (exiftool_preview, embedded_jpeg_preview, rawpy_preview, ffmpeg_preview):
        try:
            result = decoder(path)
            if result is not None:
                return result
        except Exception as exc:
            errors.append(f"{decoder.__name__}: {exc}")
    detail = "; ".join(errors[-3:]) if errors else "no compatible decoder or embedded JPEG preview"
    raise RuntimeError(detail)


def resize_for_analysis(image: Image.Image, max_edge: int) -> Image.Image:
    image = image.copy().convert("RGB")
    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    return image


def safe_preview_name(index: int, source: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", source.stem).strip("._") or "photo"
    return f"{index:05d}-{stem[:72]}.jpg"


def dct_phash(gray_image: Image.Image) -> int:
    values = np.asarray(gray_image.resize((32, 32), Image.Resampling.LANCZOS), dtype=np.float64) / 255.0
    n = values.shape[0]
    x = np.arange(n)
    u = np.arange(8)[:, None]
    basis = np.cos((2 * x + 1) * u * math.pi / (2 * n))
    basis[0] *= 1 / math.sqrt(2)
    block = basis @ values @ basis.T
    coeffs = block.flatten()[1:64]
    median = float(np.median(coeffs))
    result = 0
    for bit in coeffs > median:
        result = (result << 1) | int(bit)
    return result


def color_histogram(rgb: np.ndarray) -> np.ndarray:
    parts = []
    for channel in range(3):
        hist, _ = np.histogram(rgb[:, :, channel], bins=16, range=(0.0, 1.0))
        parts.append(hist.astype(np.float64))
    combined = np.concatenate(parts)
    norm = np.linalg.norm(combined)
    return combined / norm if norm else combined


def focus_metric(gray: np.ndarray) -> float:
    if min(gray.shape) < 5:
        return 0.0
    center = gray[1:-1, 1:-1]
    laplacian = (
        gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2] + gray[1:-1, 2:] - 4.0 * center
    )
    return float(np.log1p(np.var(laplacian) * 100000.0))


def focus_grid(gray: np.ndarray, divisions: int = 4) -> np.ndarray:
    height, width = gray.shape
    values: list[float] = []
    for row in range(divisions):
        for column in range(divisions):
            y0, y1 = height * row // divisions, height * (row + 1) // divisions
            x0, x1 = width * column // divisions, width * (column + 1) // divisions
            values.append(focus_metric(gray[y0:y1, x0:x1]))
    array = np.asarray(values, dtype=np.float64)
    deviation = float(np.std(array))
    if deviation < 1e-9:
        return np.zeros_like(array)
    return (array - float(np.mean(array))) / deviation


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and value:
        value = value[0]
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def parse_capture_time(value: Any) -> tuple[str | None, float | None]:
    if value is None:
        return None, None
    text = str(value).strip()
    match = re.match(r"(\d{4}):(\d{2}):(\d{2})[ T](\d{2}):(\d{2}):(\d{2})", text)
    if not match:
        return text or None, None
    try:
        parsed = datetime(*[int(part) for part in match.groups()])
        return text, parsed.timestamp()
    except ValueError:
        return text, None


def metadata_from_pillow(path: Path) -> dict[str, Any]:
    try:
        with Image.open(path) as image:
            exif = image.getexif()
            tags = dict(exif)
            try:
                tags.update(exif.get_ifd(34665))
            except Exception:
                pass
    except Exception:
        return {}
    return {
        "capture_time": tags.get(36867) or tags.get(306),
        "exposure_time": tags.get(33434),
        "f_number": tags.get(33437),
        "iso": tags.get(34855) or tags.get(34867),
        "exposure_compensation": tags.get(37380),
        "focus_distance": tags.get(37382),
    }


def metadata_from_exiftool(path: Path) -> dict[str, Any]:
    if not shutil.which("exiftool"):
        return {}
    tags = (
        "DateTimeOriginal", "SubSecDateTimeOriginal", "ExposureTime", "FNumber", "ISO",
        "ExposureCompensation", "FocusDistance", "FocusDistance2", "BracketShotNumber",
        "BracketMode", "AEBBracketValue", "AutoBracket", "DriveMode", "FocusBracket",
        "FocusShiftShooting", "FocusStepWidth",
    )
    command = ["exiftool", "-json", "-n", *[f"-{tag}" for tag in tags], str(path)]
    proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False, text=True)
    if proc.returncode != 0:
        return {}
    try:
        rows = json.loads(proc.stdout)
        return rows[0] if rows else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def active_metadata_hint(value: Any) -> bool:
    if value is None:
        return False
    return str(value).strip().casefold() not in {"", "0", "off", "false", "none", "single", "normal"}


def read_photo_metadata(path: Path) -> dict[str, Any]:
    pillow = metadata_from_pillow(path)
    exiftool = metadata_from_exiftool(path)
    capture_value = exiftool.get("SubSecDateTimeOriginal") or exiftool.get("DateTimeOriginal") or pillow.get("capture_time")
    capture_time, capture_timestamp = parse_capture_time(capture_value)
    exposure_time = as_float(exiftool.get("ExposureTime", pillow.get("exposure_time")))
    f_number = as_float(exiftool.get("FNumber", pillow.get("f_number")))
    iso = as_float(exiftool.get("ISO", pillow.get("iso")))
    exposure_compensation = as_float(exiftool.get("ExposureCompensation", pillow.get("exposure_compensation")))
    focus_distance = as_float(exiftool.get("FocusDistance2") or exiftool.get("FocusDistance") or pillow.get("focus_distance"))
    exposure_ev = None
    if exposure_time and exposure_time > 0 and f_number and f_number > 0 and iso and iso > 0:
        exposure_ev = math.log2((f_number * f_number) / exposure_time) - math.log2(iso / 100.0)
    drive_mode = str(exiftool.get("DriveMode", ""))
    bracket_shot_number = as_float(exiftool.get("BracketShotNumber"))
    exposure_hint = (
        any(active_metadata_hint(exiftool.get(key)) for key in ("BracketMode", "AEBBracketValue", "AutoBracket"))
        or bracket_shot_number not in (None, 0)
        or "bracket" in drive_mode.casefold()
    )
    focus_hint = any(active_metadata_hint(exiftool.get(key)) for key in ("FocusBracket", "FocusShiftShooting", "FocusStepWidth"))
    return {
        "capture_time": capture_time,
        "exposure_time": round(exposure_time, 8) if exposure_time is not None else None,
        "f_number": round(f_number, 3) if f_number is not None else None,
        "iso": round(iso, 1) if iso is not None else None,
        "exposure_compensation": round(exposure_compensation, 3) if exposure_compensation is not None else None,
        "focus_distance": round(focus_distance, 4) if focus_distance is not None else None,
        "exposure_ev": round(exposure_ev, 4) if exposure_ev is not None else None,
        "bracket_shot_number": round(bracket_shot_number, 1) if bracket_shot_number is not None else None,
        "metadata_source": "exiftool" if exiftool else ("pillow" if pillow else "none"),
        "_capture_timestamp": capture_timestamp,
        "_exposure_hint": exposure_hint,
        "_focus_hint": focus_hint,
    }


def analyze_image(image: Image.Image) -> dict[str, Any]:
    sample = image.copy()
    sample.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
    rgb = np.asarray(sample, dtype=np.float32) / 255.0
    gray = 0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]
    height, width = gray.shape
    y0, y1 = int(height * 0.20), max(int(height * 0.80), int(height * 0.20) + 5)
    x0, x1 = int(width * 0.20), max(int(width * 0.80), int(width * 0.20) + 5)
    center_gray = gray[y0:y1, x0:x1]
    p05, median, p95 = np.percentile(gray, [5, 50, 95])
    return {
        "width": image.width,
        "height": image.height,
        "focus_raw": focus_metric(gray),
        "center_focus_raw": focus_metric(center_gray),
        "median_luma": float(median),
        "shadow_clip": float(np.mean(gray <= 2 / 255.0)),
        "highlight_clip": float(np.mean(gray >= 253 / 255.0)),
        "contrast_raw": float(p95 - p05),
        "_phash": dct_phash(sample.convert("L")),
        "_histogram": color_histogram(rgb),
        "_focus_grid": focus_grid(gray),
    }


def robust_scores(values: list[float]) -> list[float]:
    if not values:
        return []
    if len(values) == 1:
        return [60.0]
    low, high = np.percentile(np.asarray(values, dtype=np.float64), [10, 90])
    if high - low < 1e-9:
        return [60.0 for _ in values]
    return [float(np.clip((value - low) / (high - low) * 100.0, 0.0, 100.0)) for value in values]


def exposure_score(item: dict[str, Any]) -> float:
    median = item["median_luma"]
    if median < 0.14:
        mid_penalty = min(1.0, (0.14 - median) / 0.14)
    elif median > 0.86:
        mid_penalty = min(1.0, (median - 0.86) / 0.14)
    else:
        mid_penalty = 0.0
    highlight_penalty = min(1.0, item["highlight_clip"] / 0.08)
    shadow_penalty = min(1.0, item["shadow_clip"] / 0.20)
    return float(np.clip(100.0 * (1.0 - 0.45 * mid_penalty - 0.35 * highlight_penalty - 0.20 * shadow_penalty), 0.0, 100.0))


class UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def phash_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    distance = (left["_phash"] ^ right["_phash"]).bit_count()
    return 1.0 - distance / 63.0


def bracket_candidate_runs(items: list[dict[str, Any]], structural_threshold: float = 0.80, max_gap_seconds: float = 8.0) -> list[list[int]]:
    if not items:
        return []
    runs: list[list[int]] = []
    current = [0]
    for index in range(1, len(items)):
        previous = items[index - 1]
        item = items[index]
        similar = phash_similarity(previous, item) >= structural_threshold
        previous_time, item_time = previous.get("_capture_timestamp"), item.get("_capture_timestamp")
        close_in_time = previous_time is None or item_time is None or abs(item_time - previous_time) <= max_gap_seconds
        if similar and close_in_time:
            current.append(index)
        else:
            if len(current) >= 3:
                runs.append(current)
            current = [index]
    if len(current) >= 3:
        runs.append(current)
    return runs


def focus_pattern_change(members: list[dict[str, Any]]) -> float:
    maximum = 0.0
    for right in range(1, len(members)):
        for left in range(right):
            difference = float(np.mean(np.abs(members[left]["_focus_grid"] - members[right]["_focus_grid"])))
            maximum = max(maximum, difference)
    return maximum


def classify_bracket_run(members: list[dict[str, Any]]) -> tuple[str, str, str] | None:
    if len(members) < 3:
        return None
    adjacent_similarity = min(phash_similarity(members[index - 1], members[index]) for index in range(1, len(members)))
    visual_ev = [math.log2(max(item["median_luma"], 0.01)) for item in members]
    visual_span = max(visual_ev) - min(visual_ev)
    metadata_ev = [item["exposure_ev"] for item in members if item.get("exposure_ev") is not None]
    metadata_span = max(metadata_ev) - min(metadata_ev) if len(metadata_ev) >= 3 else 0.0
    distinct_metadata_exposures = len({round(value * 2) / 2 for value in metadata_ev})
    exposure_hint = any(item.get("_exposure_hint") for item in members)
    if exposure_hint and (metadata_span >= 0.30 or visual_span >= 0.35):
        span = metadata_span if metadata_span >= 0.30 else visual_span
        return "exposure", "high", f"相机包围元数据显示曝光序列，跨度约 {span:.1f} EV"
    if adjacent_similarity >= 0.80 and (
        (len(metadata_ev) >= 3 and metadata_span >= 0.65 and distinct_metadata_exposures >= 3)
        or visual_span >= 0.80
    ):
        span = metadata_span if metadata_span >= 0.65 else visual_span
        basis = "曝光参数" if metadata_span >= 0.65 else "画面亮度"
        return "exposure", "high" if metadata_span >= 0.65 else "medium", f"相邻构图一致，{basis}跨度约 {span:.1f} EV"

    focus_hint = any(item.get("_focus_hint") for item in members)
    focus_distances = [item["focus_distance"] for item in members if item.get("focus_distance") not in (None, 0)]
    focus_distance_span = 0.0
    if len(focus_distances) >= 3 and min(focus_distances) > 0:
        focus_distance_span = math.log2(max(focus_distances) / min(focus_distances))
    pattern_change = focus_pattern_change(members)
    stable_exposure = visual_span <= 0.40 and metadata_span <= 0.40
    if focus_hint and stable_exposure:
        return "focus", "high", "相机元数据显示对焦包围序列"
    if adjacent_similarity >= 0.90 and stable_exposure and focus_distance_span >= 0.04:
        return "focus", "high", "相邻构图与曝光稳定，记录的对焦距离连续变化"
    if adjacent_similarity >= 0.92 and stable_exposure and pattern_change >= 0.55:
        return "focus", "medium", f"相邻构图与亮度稳定，清晰区域分布连续变化（特征差 {pattern_change:.2f}）"
    return None


def detect_brackets(items: list[dict[str, Any]]) -> None:
    counters = {"exposure": 0, "focus": 0}
    for indices in bracket_candidate_runs(items):
        members = [items[index] for index in indices]
        classification = classify_bracket_run(members)
        if classification is None:
            continue
        bracket_type, confidence, reason = classification
        counters[bracket_type] += 1
        prefix = "E" if bracket_type == "exposure" else "F"
        group_id = f"{prefix}{counters[bracket_type]:03d}"
        for order, index in enumerate(indices, 1):
            items[index]["bracket_type"] = bracket_type
            items[index]["bracket_group"] = group_id
            items[index]["bracket_order"] = order
            items[index]["bracket_count"] = len(indices)
            items[index]["bracket_confidence"] = confidence
            items[index]["bracket_reason"] = reason


def group_duplicates(items: list[dict[str, Any]], window: int, threshold: float) -> None:
    union = UnionFind(len(items))
    for right in range(len(items)):
        for left in range(max(0, right - window), right):
            if items[left].get("bracket_group") or items[right].get("bracket_group"):
                continue
            hash_similarity = phash_similarity(items[left], items[right])
            color_similarity = float(np.dot(items[left]["_histogram"], items[right]["_histogram"]))
            if hash_similarity >= threshold and color_similarity >= 0.95:
                union.union(left, right)
    groups: dict[int, list[int]] = {}
    for index in range(len(items)):
        groups.setdefault(union.find(index), []).append(index)
    duplicate_groups = [indices for indices in groups.values() if len(indices) > 1]
    duplicate_groups.sort(key=lambda indices: min(indices))
    for group_number, indices in enumerate(duplicate_groups, 1):
        group_id = f"G{group_number:03d}"
        for index in indices:
            items[index]["duplicate_group"] = group_id
            items[index]["duplicate_count"] = len(indices)


def add_scores_and_labels(items: list[dict[str, Any]], profile: str, keep_rate: float) -> None:
    overall_scores = robust_scores([item["focus_raw"] for item in items])
    center_scores = robust_scores([item["center_focus_raw"] for item in items])
    contrast_scores = robust_scores([item["contrast_raw"] for item in items])
    for item, whole, center, contrast in zip(items, overall_scores, center_scores, contrast_scores):
        item["focus_score"] = round(whole, 1)
        item["center_focus_score"] = round(center, 1)
        item["contrast_score"] = round(contrast, 1)
        item["exposure_score"] = round(exposure_score(item), 1)
        if profile == "macro-nature":
            focus = 0.35 * whole + 0.65 * center
            technical = 0.75 * focus + 0.20 * item["exposure_score"] + 0.05 * contrast
        else:
            focus = whole
            technical = 0.65 * focus + 0.25 * item["exposure_score"] + 0.10 * contrast
        item["combined_focus_score"] = round(focus, 1)
        item["technical_score"] = round(float(technical), 1)

    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        key = (
            f"bracket:{item['bracket_group']}" if item.get("bracket_group")
            else item.get("duplicate_group") or f"single:{item['index']}"
        )
        grouped.setdefault(key, []).append(item)
    winners: list[dict[str, Any]] = []
    for members in grouped.values():
        ordered = sorted(members, key=lambda row: row["technical_score"], reverse=True)
        for rank, member in enumerate(ordered, 1):
            member["duplicate_rank"] = rank if member.get("duplicate_group") else None
        if not ordered[0].get("bracket_group"):
            winners.append(ordered[0])

    eligible_winners = [
        item for item in winners
        if not (item["exposure_score"] < 25 or (len(items) >= 5 and item["combined_focus_score"] <= 8))
    ]
    pick_count = max(1, math.ceil(len(eligible_winners) * keep_rate)) if eligible_winners else 0
    pick_ids = {
        item["index"]
        for item in sorted(eligible_winners, key=lambda row: row["technical_score"], reverse=True)[:pick_count]
    }

    for item in items:
        severe = item["exposure_score"] < 25 or (len(items) >= 5 and item["combined_focus_score"] <= 8)
        if item.get("bracket_type"):
            label = f"{item['bracket_type']}-bracket"
        elif severe:
            label = "reject"
        elif item.get("duplicate_group") and item.get("duplicate_rank", 1) > 1:
            label = "duplicate"
        elif item["index"] in pick_ids:
            label = "pick"
        else:
            label = "maybe"
        item["label"] = label
        reasons: list[str] = []
        if item.get("bracket_group"):
            reasons.append(item["bracket_reason"])
            reasons.append(f"{item['bracket_group']} 组第 {item['bracket_order']}/{item['bracket_count']} 张")
        else:
            if item["combined_focus_score"] >= 80:
                reasons.append("清晰度位于本批前列")
            elif item["combined_focus_score"] <= 20:
                reasons.append("清晰度位于本批后列")
            if profile == "macro-nature" and item["center_focus_score"] >= item["focus_score"] + 15:
                reasons.append("中心主体区域相对清晰")
            if item["highlight_clip"] >= 0.05:
                reasons.append(f"高光剪切 {item['highlight_clip']:.1%}")
            if item["shadow_clip"] >= 0.15:
                reasons.append(f"阴影剪切 {item['shadow_clip']:.1%}")
            if item["median_luma"] < 0.12:
                reasons.append("整体偏暗")
            elif item["median_luma"] > 0.88:
                reasons.append("整体偏亮")
            if item.get("duplicate_group"):
                reasons.append(f"{item['duplicate_group']} 组第 {item['duplicate_rank']}/{item['duplicate_count']} 名")
        if not reasons:
            reasons.append("技术指标中等，需视觉复核")
        item["reason"] = "；".join(reasons)


def public_item(item: dict[str, Any]) -> dict[str, Any]:
    result = {key: value for key, value in item.items() if not key.startswith("_")}
    for key in ("focus_raw", "center_focus_raw", "contrast_raw", "median_luma", "shadow_clip", "highlight_clip"):
        result[key] = round(float(result[key]), 6)
    return result


def write_csv(path: Path, items: list[dict[str, Any]]) -> None:
    fields = [
        "index", "source", "label", "technical_score", "focus_score", "center_focus_score",
        "exposure_score", "contrast_score", "duplicate_group", "duplicate_rank", "duplicate_count",
        "bracket_type", "bracket_group", "bracket_order", "bracket_count", "bracket_confidence",
        "bracket_reason", "capture_time", "exposure_time", "f_number", "iso", "exposure_compensation",
        "focus_distance", "exposure_ev", "bracket_shot_number", "reason", "decoder", "width", "height", "preview", "file_size_bytes",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for item in items:
            writer.writerow(public_item(item))


def load_font(size: int) -> ImageFont.ImageFont:
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def write_contact_sheets(output: Path, items: list[dict[str, Any]]) -> list[str]:
    directory = output / "contact-sheets"
    directory.mkdir(exist_ok=True)
    columns, rows, cell_w, cell_h = 4, 5, 300, 235
    per_sheet = columns * rows
    font = load_font(17)
    small_font = load_font(14)
    generated: list[str] = []
    for page, offset in enumerate(range(0, len(items), per_sheet), 1):
        page_items = items[offset:offset + per_sheet]
        used_rows = max(1, math.ceil(len(page_items) / columns))
        sheet = Image.new("RGB", (columns * cell_w, used_rows * cell_h), "#11151a")
        draw = ImageDraw.Draw(sheet)
        for slot, item in enumerate(page_items):
            col, row = slot % columns, slot // columns
            left, top = col * cell_w, row * cell_h
            preview = open_pillow(output / item["preview"])
            thumb = ImageOps.contain(preview, (cell_w - 18, 170), Image.Resampling.LANCZOS)
            x = left + (cell_w - thumb.width) // 2
            y = top + 8 + (170 - thumb.height) // 2
            sheet.paste(thumb, (x, y))
            color = LABEL_COLOR[item["label"]]
            draw.rectangle((left + 4, top + 4, left + cell_w - 5, top + cell_h - 5), outline=color, width=4)
            filename = Path(item["source"]).name
            if len(filename) > 29:
                filename = filename[:26] + "..."
            draw.text((left + 10, top + 184), f"{LABEL_EN[item['label']]}  {item['technical_score']:.1f}", fill=color, font=font)
            draw.text((left + 10, top + 209), filename, fill="#e8edf3", font=small_font)
        relative = f"contact-sheets/contact-{page:03d}.jpg"
        sheet.save(output / relative, "JPEG", quality=90, optimize=True)
        generated.append(relative)
    return generated


def write_bracket_groups(output: Path, root: Path, items: list[dict[str, Any]], copy_originals: bool) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        if item.get("bracket_group"):
            grouped.setdefault(item["bracket_group"], []).append(item)
    summaries: list[dict[str, Any]] = []
    for group_id in sorted(grouped):
        members = sorted(grouped[group_id], key=lambda row: row["bracket_order"])
        bracket_type = members[0]["bracket_type"]
        group_dir = output / "bracket-groups" / bracket_type / group_id
        preview_group = group_dir / "previews"
        preview_group.mkdir(parents=True, exist_ok=True)
        original_group = group_dir / "originals"
        if copy_originals:
            original_group.mkdir(parents=True, exist_ok=True)
        manifest_items: list[dict[str, Any]] = []
        for item in members:
            order = int(item["bracket_order"])
            source_name = Path(item["source"]).name
            safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", source_name)
            preview_destination = preview_group / f"{order:03d}-{Path(safe_name).stem}.jpg"
            shutil.copy2(output / item["preview"], preview_destination)
            original_relative = None
            if copy_originals:
                original_destination = original_group / f"{order:03d}-{safe_name}"
                shutil.copy2(root / item["source"], original_destination)
                original_relative = original_destination.relative_to(output).as_posix()
            manifest_items.append({
                "order": order,
                "source": item["source"],
                "preview": preview_destination.relative_to(output).as_posix(),
                "copied_original": original_relative,
                "exposure_time": item.get("exposure_time"),
                "f_number": item.get("f_number"),
                "iso": item.get("iso"),
                "exposure_compensation": item.get("exposure_compensation"),
                "focus_distance": item.get("focus_distance"),
                "technical_score": item["technical_score"],
            })
        manifest = {
            "group": group_id,
            "type": bracket_type,
            "confidence": members[0]["bracket_confidence"],
            "reason": members[0]["bracket_reason"],
            "count": len(members),
            "originals_copied": copy_originals,
            "items": manifest_items,
        }
        manifest_path = group_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        summaries.append({
            "group": group_id,
            "type": bracket_type,
            "count": len(members),
            "confidence": members[0]["bracket_confidence"],
            "reason": members[0]["bracket_reason"],
            "path": group_dir.relative_to(output).as_posix(),
            "manifest": manifest_path.relative_to(output).as_posix(),
            "originals_copied": copy_originals,
        })
    if summaries:
        index_path = output / "bracket-groups" / "index.json"
        index_path.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    return summaries


def write_xmp_sidecars(output: Path, items: list[dict[str, Any]]) -> list[str]:
    rating = {"pick": 5, "maybe": 3, "duplicate": 2, "reject": 1, "focus-bracket": 4, "exposure-bracket": 4}
    color = {"pick": "Green", "maybe": "Yellow", "duplicate": "Purple", "reject": "Red", "focus-bracket": "Blue", "exposure-bracket": "Purple"}
    directory = output / "xmp-sidecars"
    generated: list[str] = []
    used: set[Path] = set()
    for item in items:
        source = Path(item["source"])
        relative = source.with_suffix(".xmp")
        if relative in used:
            relative = source.with_name(f"{source.name}.xmp")
        used.add(relative)
        destination = directory / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        label = item["label"]
        body = f'''<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/" xmp:Rating="{rating[label]}" xmp:Label="{color[label]}"/>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>
'''
        destination.write_text(body, encoding="utf-8")
        generated.append(destination.relative_to(output).as_posix())
    return generated


def photo_card_html(item: dict[str, Any]) -> str:
    label = item["label"]
    return f"""
    <article class="photo" data-label="{label}" data-score="{item['technical_score']:.1f}">
      <div class="image-wrap"><img loading="lazy" src="{html.escape(item['preview'])}" alt="{html.escape(item['source'])}"></div>
      <div class="content">
        <div class="line"><span class="badge {label}">{LABEL_ZH[label]}</span><strong>{item['technical_score']:.1f}</strong></div>
        <h3 title="{html.escape(item['source'])}">{html.escape(Path(item['source']).name)}</h3>
        <p>{html.escape(item['reason'])}</p>
        <dl><dt>清晰</dt><dd>{item['combined_focus_score']:.1f}</dd><dt>曝光</dt><dd>{item['exposure_score']:.1f}</dd><dt>预览</dt><dd>{item['width']}×{item['height']}</dd><dt>解码</dt><dd>{html.escape(item['decoder'])}</dd></dl>
      </div>
    </article>"""


def report_html(summary: dict[str, Any], items: list[dict[str, Any]], failures: list[dict[str, str]]) -> str:
    regular_items = [item for item in items if not item.get("bracket_group")]
    cards = [
        photo_card_html(item)
        for item in sorted(regular_items, key=lambda row: (row["label"] != "pick", -row["technical_score"], row["index"]))
    ]
    bracket_sections: list[str] = []
    for bracket_type, heading in (("exposure", "曝光包围组"), ("focus", "对焦包围组")):
        type_items = [item for item in items if item.get("bracket_type") == bracket_type]
        if not type_items:
            continue
        group_blocks: list[str] = []
        group_ids = sorted({item["bracket_group"] for item in type_items})
        for group_id in group_ids:
            members = sorted(
                (item for item in type_items if item["bracket_group"] == group_id),
                key=lambda row: row["bracket_order"],
            )
            reason = html.escape(members[0]["bracket_reason"])
            confidence = "高" if members[0]["bracket_confidence"] == "high" else "中"
            group_blocks.append(
                f'<div class="bracket-group"><div class="group-heading"><h3>{group_id} · {len(members)} 张</h3>'
                f'<span>识别置信度：{confidence}</span></div><p class="group-reason">{reason}</p>'
                f'<div class="grid bracket-grid">{"".join(photo_card_html(item) for item in members)}</div></div>'
            )
        bracket_sections.append(f'<section class="bracket-section"><h2>{heading}</h2>{"".join(group_blocks)}</section>')
    failure_html = ""
    if failures:
        rows = "".join(
            f"<tr><td>{html.escape(row['source'])}</td><td>{html.escape(row['error'])}</td></tr>" for row in failures
        )
        failure_html = f"<section><h2>无法解码的文件</h2><table><thead><tr><th>文件</th><th>原因</th></tr></thead><tbody>{rows}</tbody></table></section>"
    count = summary["counts"]
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>rawsift｜RAW 照片智能初筛工具报告</title>
<style>
:root{{--bg:#f4f5f2;--panel:#fff;--ink:#17211c;--muted:#66716b;--line:#dde2dd;--pick:#168a59;--maybe:#b77b0c;--duplicate:#5965bd;--reject:#c44848;--focus:#168aa3;--exposure:#d47725}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC",sans-serif}}main{{max-width:1500px;margin:auto;padding:32px}}h1{{margin:0 0 8px;font-size:clamp(28px,4vw,50px)}}.subtitle{{color:var(--muted);margin:0 0 24px}}.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin:22px 0}}.stat{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px}}.stat b{{display:block;font-size:28px}}.stat span{{color:var(--muted)}}.controls{{position:sticky;top:0;z-index:5;padding:12px 0;background:rgba(244,245,242,.94);backdrop-filter:blur(8px)}}button,.download{{border:1px solid var(--line);background:#fff;color:var(--ink);padding:9px 13px;border-radius:999px;margin:3px;cursor:pointer;text-decoration:none;font-size:14px}}button.active{{background:#17211c;color:white}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px}}.photo{{background:var(--panel);border:1px solid var(--line);border-radius:16px;overflow:hidden;box-shadow:0 5px 18px rgba(22,35,28,.05)}}.image-wrap{{aspect-ratio:4/3;background:#151a17;display:flex;align-items:center;justify-content:center}}.image-wrap img{{width:100%;height:100%;object-fit:contain}}.content{{padding:14px}}.line{{display:flex;justify-content:space-between;align-items:center}}.line strong{{font-size:22px}}.badge{{color:white;padding:4px 9px;border-radius:999px;font-size:12px}}.badge.pick{{background:var(--pick)}}.badge.maybe{{background:var(--maybe)}}.badge.duplicate{{background:var(--duplicate)}}.badge.reject{{background:var(--reject)}}.badge.focus-bracket{{background:var(--focus)}}.badge.exposure-bracket{{background:var(--exposure)}}h3{{margin:12px 0 7px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:16px}}p{{color:var(--muted);min-height:42px;font-size:13px;line-height:1.55}}dl{{display:grid;grid-template-columns:auto 1fr auto 1fr;gap:5px 10px;font-size:12px}}dt{{color:var(--muted)}}dd{{margin:0;text-align:right}}section{{margin-top:34px}}table{{width:100%;border-collapse:collapse;background:white}}th,td{{text-align:left;padding:10px;border-bottom:1px solid var(--line);font-size:13px}}.note{{background:#eef2ed;border-left:4px solid #66806f;padding:12px 16px;border-radius:8px;margin:18px 0}}.bracket-section>h2{{font-size:28px;margin-bottom:16px}}.bracket-group{{border:1px solid var(--line);border-radius:18px;padding:18px;margin:18px 0;background:#e9eeea}}.group-heading{{display:flex;align-items:center;justify-content:space-between;gap:12px}}.group-heading h3{{font-size:20px;margin:0;overflow:visible}}.group-heading span,.group-reason{{color:var(--muted);font-size:13px}}.group-reason{{min-height:0;margin:6px 0 14px}}.bracket-grid{{grid-template-columns:repeat(auto-fill,minmax(220px,1fr))}}@media(max-width:760px){{main{{padding:18px}}.stats{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body><main>
<h1>rawsift｜RAW 照片智能初筛工具报告</h1><p class="subtitle">{html.escape(summary['generated_at'])} · {html.escape(summary['profile'])} 模式 · 技术评分仅在本批次内有效</p>
<div class="stats"><div class="stat"><b>{summary['analyzed']}</b><span>成功分析</span></div><div class="stat"><b>{count.get('pick',0)}</b><span>精选候选</span></div><div class="stat"><b>{count.get('maybe',0)}</b><span>备选</span></div><div class="stat"><b>{count.get('duplicate',0)}</b><span>重复备选</span></div><div class="stat"><b>{count.get('exposure-bracket',0)}</b><span>曝光包围照片</span></div><div class="stat"><b>{count.get('focus-bracket',0)}</b><span>对焦包围照片</span></div><div class="stat"><b>{count.get('reject',0)}</b><span>技术淘汰候选</span></div></div>
<div class="note">包围序列已先于重复连拍识别，并从重复淘汰中排除。自动识别仍需结合联系表复核；原始照片未被修改。</div>
{''.join(bracket_sections)}
<div class="controls"><button class="active" data-filter="all">全部</button><button data-filter="pick">精选</button><button data-filter="maybe">备选</button><button data-filter="duplicate">重复</button><button data-filter="reject">技术问题</button><a class="download" href="analysis.csv">下载 CSV</a><a class="download" href="analysis.json">查看 JSON</a></div>
<div class="grid culling-grid">{''.join(cards)}</div>{failure_html}
</main><script>document.querySelectorAll('button[data-filter]').forEach(b=>b.addEventListener('click',()=>{{document.querySelectorAll('button[data-filter]').forEach(x=>x.classList.remove('active'));b.classList.add('active');const f=b.dataset.filter;document.querySelectorAll('.culling-grid .photo').forEach(c=>c.style.display=(f==='all'||c.dataset.label===f)?'block':'none')}}));</script></body></html>"""


def main() -> int:
    args = parse_args()
    try:
        root, files = discover_files(args.input)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not files:
        print("ERROR: no supported photos found", file=sys.stderr)
        return 2
    output = unique_output_dir(args.output)
    preview_dir = output / "previews"
    preview_dir.mkdir()
    items: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for source_index, source in enumerate(files, 1):
        relative_source = source.relative_to(root).as_posix()
        try:
            image, decoder = extract_preview(source)
            image = resize_for_analysis(image, args.max_preview)
            preview_name = safe_preview_name(source_index, source)
            preview_path = preview_dir / preview_name
            image.save(preview_path, "JPEG", quality=90, optimize=True)
            metrics = analyze_image(image)
            metadata = read_photo_metadata(source)
            metrics.update({
                "index": source_index,
                "source": relative_source,
                "preview": f"previews/{preview_name}",
                "decoder": decoder,
                "file_size_bytes": source.stat().st_size,
                "duplicate_group": None,
                "duplicate_count": None,
                "bracket_type": None,
                "bracket_group": None,
                "bracket_order": None,
                "bracket_count": None,
                "bracket_confidence": None,
                "bracket_reason": None,
            })
            metrics.update(metadata)
            items.append(metrics)
            print(f"[{source_index}/{len(files)}] OK {relative_source}")
        except Exception as exc:
            failures.append({"source": relative_source, "error": str(exc)})
            print(f"[{source_index}/{len(files)}] FAIL {relative_source}: {exc}", file=sys.stderr)

    if items:
        if args.bracket_detection == "auto":
            detect_brackets(items)
        group_duplicates(items, args.duplicate_window, args.duplicate_similarity)
        add_scores_and_labels(items, args.profile, args.keep_rate)
        contact_sheets = write_contact_sheets(output, items)
        bracket_groups = write_bracket_groups(output, root, items, args.copy_bracket_originals)
        xmp_sidecars = write_xmp_sidecars(output, items) if args.export_xmp else []
    else:
        contact_sheets = []
        bracket_groups = []
        xmp_sidecars = []
    counts = Counter(item.get("label", "unclassified") for item in items)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input": str(args.input.expanduser().resolve()),
        "output": str(output),
        "profile": args.profile,
        "keep_rate": args.keep_rate,
        "bracket_detection": args.bracket_detection,
        "bracket_groups": bracket_groups,
        "bracket_originals_copied": args.copy_bracket_originals,
        "discovered": len(files),
        "analyzed": len(items),
        "failed": len(failures),
        "counts": dict(counts),
        "contact_sheets": contact_sheets,
        "xmp_sidecars": xmp_sidecars,
        "source_files_modified": False,
    }
    write_csv(output / "analysis.csv", items)
    payload = {"summary": summary, "items": [public_item(item) for item in items], "failures": failures}
    (output / "analysis.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "report.html").write_text(report_html(summary, items, failures), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if items else 3


if __name__ == "__main__":
    raise SystemExit(main())
