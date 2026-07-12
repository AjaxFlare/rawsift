from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from rawsift.cli import main


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def detailed_scene() -> Image.Image:
    width, height = 1200, 800
    image = Image.new("RGB", (width, height), (65, 95, 70))
    draw = ImageDraw.Draw(image)
    for y in range(0, height, 16):
        draw.line((0, y, width, y), fill=(40 + y // 8, 80, 50 + y // 20), width=2)
    for x in range(0, width, 22):
        draw.line((x, 0, width - x // 4, height), fill=(25, 125, 50), width=2)
    draw.ellipse((380, 230, 820, 610), fill=(175, 74, 35), outline=(15, 15, 12), width=10)
    for x in range(420, 800, 28):
        draw.line((x, 250, x + 30, 590), fill=(245, 190, 80), width=5)
    draw.ellipse((350, 250, 470, 370), fill=(20, 20, 15), outline="white", width=5)
    draw.ellipse((388, 285, 420, 317), fill="white")
    return image


def build_fixture(directory: Path) -> None:
    directory.mkdir()
    scene = detailed_scene()
    for index, factor in enumerate((0.38, 1.0, 2.0), 1):
        ImageEnhance.Brightness(scene).enhance(factor).save(directory / f"{index:03d}_exposure.jpg", quality=96)

    separator = Image.new("RGB", scene.size, (25, 55, 125))
    ImageDraw.Draw(separator).polygon([(50, 700), (600, 100), (1150, 700)], fill=(240, 210, 90))
    separator.save(directory / "004_separator.jpg", quality=95)

    blurred = scene.filter(ImageFilter.GaussianBlur(5.5))
    boxes = ((0, 0, 360, 800), (280, 0, 650, 800), (570, 0, 940, 800), (840, 0, 1200, 800))
    for index, box in enumerate(boxes, 5):
        frame = blurred.copy()
        mask = Image.new("L", scene.size, 0)
        ImageDraw.Draw(mask).rectangle(box, fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(35))
        frame.paste(scene, (0, 0), mask)
        frame.save(directory / f"{index:03d}_focus.jpg", quality=96)

    separator2 = Image.new("RGB", scene.size, (110, 40, 90))
    ImageDraw.Draw(separator2).ellipse((250, 100, 950, 700), fill=(30, 180, 200))
    separator2.save(directory / "009_separator.jpg", quality=95)

    burst = scene.copy()
    ImageDraw.Draw(burst).rectangle((40, 40, 140, 140), fill=(40, 80, 180))
    for index in range(10, 13):
        burst.save(directory / f"{index:03d}_burst.jpg", quality=95)


class BracketDetectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        build_fixture(self.source)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_brackets_are_grouped_before_duplicates(self) -> None:
        output = self.root / "report"
        before = {path.name: file_hash(path) for path in self.source.iterdir()}
        argv = [
            "rawsift",
            str(self.source),
            "--output",
            str(output),
            "--profile",
            "macro-nature",
            "--export-xmp",
        ]
        with patch.object(sys, "argv", argv):
            self.assertEqual(main(), 0)

        payload = json.loads((output / "analysis.json").read_text(encoding="utf-8"))
        groups = {(group["type"], group["count"]) for group in payload["summary"]["bracket_groups"]}
        self.assertEqual(groups, {("exposure", 3), ("focus", 4)})
        self.assertFalse(any(item["bracket_group"] and item["duplicate_group"] for item in payload["items"]))
        self.assertGreaterEqual(payload["summary"]["counts"]["duplicate"], 2)

        self.assertTrue((output / "bracket-groups" / "exposure" / "E001" / "manifest.json").exists())
        self.assertTrue((output / "bracket-groups" / "focus" / "F001" / "manifest.json").exists())
        report = (output / "report.html").read_text(encoding="utf-8")
        self.assertIn("曝光包围组", report)
        self.assertIn("对焦包围组", report)

        for sidecar in payload["summary"]["xmp_sidecars"]:
            ET.parse(output / sidecar)
        self.assertEqual(before, {path.name: file_hash(path) for path in self.source.iterdir()})

    def test_bracket_detection_can_be_disabled(self) -> None:
        output = self.root / "report"
        argv = [
            "rawsift",
            str(self.source),
            "--output",
            str(output),
            "--bracket-detection",
            "off",
        ]
        with patch.object(sys, "argv", argv):
            self.assertEqual(main(), 0)
        summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["bracket_groups"], [])
        self.assertFalse(any(label.endswith("-bracket") for label in summary["counts"]))


if __name__ == "__main__":
    unittest.main()

