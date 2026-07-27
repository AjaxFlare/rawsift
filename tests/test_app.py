from __future__ import annotations

import io
import json
import tempfile
import time
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from PIL import Image

from rawsift.app import create_app
from rawsift.app.config import VisionConfig
from rawsift.app.jobs import JobStore
from rawsift.app.launcher import main as launcher_main
from rawsift.app.security import contained_path, safe_relative_path, validate_api_base_url
from rawsift.app.vision import parse_json_response, preview_data_url, review_previews, test_provider as check_provider


def jpeg_bytes(color: tuple[int, int, int] = (50, 120, 80)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (160, 120), color).save(buffer, "JPEG")
    return buffer.getvalue()


class SecurityTests(unittest.TestCase):
    def test_upload_paths_stay_relative(self) -> None:
        self.assertEqual(safe_relative_path("trip/day-1/photo.nef"), Path("trip/day-1/photo.nef"))
        for unsafe in ("../secret", "/absolute/file", "folder/../../secret", "C:/secret", "a/./b"):
            with self.subTest(unsafe=unsafe), self.assertRaises(ValueError):
                safe_relative_path(unsafe)

    def test_contained_path_and_provider_url(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(contained_path(root, "folder/photo.jpg"), root / "folder/photo.jpg")
        self.assertEqual(validate_api_base_url("https://api.example.com/v1/"), "https://api.example.com/v1")
        self.assertEqual(validate_api_base_url("http://127.0.0.1:11434/v1"), "http://127.0.0.1:11434/v1")
        with self.assertRaises(ValueError):
            validate_api_base_url("http://api.example.com/v1")


class FrozenExecutableTests(unittest.TestCase):
    def test_launcher_dispatches_frozen_cli_mode(self) -> None:
        with (
            patch("sys.argv", ["rawsift.exe", "--rawsift-cli", "photos"]),
            patch("rawsift.cli.main", return_value=0) as cli_main,
        ):
            with self.assertRaisesRegex(SystemExit, "0"):
                launcher_main()
        cli_main.assert_called_once_with()


class FakeResponsesClient:
    last_input = None

    def __init__(self, **_kwargs) -> None:
        self.responses = self

    def create(self, **kwargs):
        FakeResponsesClient.last_input = kwargs.get("input")
        if isinstance(kwargs.get("input"), str):
            return SimpleNamespace(output_text="rawsift-ok")
        return SimpleNamespace(output_text='```json\n{"summary":"ok","photos":[{"filename":"photo.jpg","recommendation":"pick","visual_score":88,"subject":"bird","composition":"clean","critical_focus":"eye","notes":"keep"}]}\n```')


class VisionTests(unittest.TestCase):
    def test_response_parsing_and_bounded_preview(self) -> None:
        parsed = parse_json_response('```json\n{"summary":"ok","photos":[]}\n```')
        self.assertEqual(parsed["summary"], "ok")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.png"
            Image.new("RGB", (2000, 1000), (20, 60, 100)).save(path)
            data_url = preview_data_url(path)
            self.assertTrue(data_url.startswith("data:image/jpeg;base64,"))
            self.assertLess(len(data_url), 200_000)

    def test_openai_compatible_responses_mode(self) -> None:
        config = VisionConfig(api_key="test-key", base_url="https://api.example.com/v1", model="vision-model")
        self.assertEqual(check_provider(config, client_factory=FakeResponsesClient), "rawsift-ok")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preview.jpg"
            path.write_bytes(jpeg_bytes())
            result = review_previews([path], config, client_factory=FakeResponsesClient, display_names=["trip/photo.jpg"])
        self.assertEqual(result["photos"][0]["visual_score"], 88)
        serialized = json.dumps(FakeResponsesClient.last_input)
        self.assertIn("trip/photo.jpg", serialized)
        self.assertIn("input_image", serialized)


class AppTests(unittest.TestCase):
    def test_health_upload_and_completed_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JobStore(Path(directory) / "jobs")
            client = TestClient(create_app(store))
            health = client.get("/api/health")
            self.assertEqual(health.status_code, 200)
            self.assertTrue(health.json()["local_only"])

            response = client.post(
                "/api/jobs",
                data={"paths": ["set/one.jpg", "set/two.jpg"], "name": "test set", "profile": "general", "keep_rate": "0.25"},
                files=[
                    ("files", ("one.jpg", jpeg_bytes((30, 100, 60)), "image/jpeg")),
                    ("files", ("two.jpg", jpeg_bytes((35, 105, 65)), "image/jpeg")),
                ],
            )
            self.assertEqual(response.status_code, 200, response.text)
            job_id = response.json()["id"]
            for _ in range(80):
                job = client.get(f"/api/jobs/{job_id}").json()
                if job["status"] in {"completed", "failed"}:
                    break
                time.sleep(0.05)
            self.assertEqual(job["status"], "completed", job.get("error"))
            analysis = client.get(f"/api/jobs/{job_id}/analysis")
            self.assertEqual(analysis.status_code, 200)
            self.assertEqual(analysis.json()["summary"]["analyzed"], 2)
            preview = analysis.json()["items"][0]["preview"]
            self.assertEqual(client.get(f"/api/jobs/{job_id}/files/{preview}").status_code, 200)


if __name__ == "__main__":
    unittest.main()
