"""Persistent local job management for the rawsift application."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO

from .config import data_root
from .security import contained_path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class JobStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or data_root()).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rawsift-job")
        self._lock = threading.RLock()

    def _job_dir(self, job_id: str) -> Path:
        if not job_id or any(char not in "0123456789abcdef-" for char in job_id.lower()):
            raise ValueError("Invalid job id")
        path = (self.root / job_id).resolve()
        if self.root not in path.parents:
            raise ValueError("Invalid job path")
        return path

    def _metadata_path(self, job_id: str) -> Path:
        return self._job_dir(job_id) / "job.json"

    def read(self, job_id: str) -> dict[str, Any]:
        return json.loads(self._metadata_path(job_id).read_text(encoding="utf-8"))

    def _write(self, job_id: str, payload: dict[str, Any]) -> None:
        payload["updated_at"] = utc_now()
        target = self._metadata_path(job_id)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(target)

    def update(self, job_id: str, **changes: Any) -> dict[str, Any]:
        with self._lock:
            payload = self.read(job_id)
            payload.update(changes)
            self._write(job_id, payload)
            return payload

    def list(self) -> list[dict[str, Any]]:
        jobs: list[dict[str, Any]] = []
        for metadata in self.root.glob("*/job.json"):
            try:
                jobs.append(json.loads(metadata.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return sorted(jobs, key=lambda row: row.get("created_at", ""), reverse=True)

    def create(self, name: str, options: dict[str, Any]) -> dict[str, Any]:
        job_id = str(uuid.uuid4())
        job_dir = self._job_dir(job_id)
        (job_dir / "input").mkdir(parents=True)
        payload = {
            "id": job_id,
            "name": name.strip() or f"rawsift-{job_id[:8]}",
            "status": "uploading",
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "file_count": 0,
            "options": options,
            "summary": None,
            "error": None,
        }
        self._write(job_id, payload)
        return payload

    def save_stream(self, job_id: str, relative: str, stream: BinaryIO) -> int:
        destination = contained_path(self._job_dir(job_id) / "input", relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        size = 0
        with destination.open("wb") as handle:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                handle.write(chunk)
        return size

    def queue(self, job_id: str) -> dict[str, Any]:
        input_dir = self._job_dir(job_id) / "input"
        file_count = sum(1 for path in input_dir.rglob("*") if path.is_file())
        if not file_count:
            raise ValueError("No files were uploaded")
        payload = self.update(job_id, status="queued", file_count=file_count)
        self._executor.submit(self._run, job_id)
        return payload

    def _run(self, job_id: str) -> None:
        job_dir = self._job_dir(job_id)
        payload = self.update(job_id, status="running", error=None)
        options = payload.get("options", {})
        command = [sys.executable]
        if getattr(sys, "frozen", False):
            command.append("--rawsift-cli")
        else:
            command.extend(["-m", "rawsift"])
        command.extend([
            str(job_dir / "input"),
            "--output",
            str(job_dir / "report"),
            "--profile",
            str(options.get("profile", "general")),
            "--duplicate-window",
            str(options.get("duplicate_window", 8)),
            "--duplicate-similarity",
            str(options.get("duplicate_similarity", 0.90)),
            "--max-preview",
            str(options.get("max_preview", 1600)),
        ])
        if options.get("bracket_detection") == "off":
            command.extend(["--bracket-detection", "off"])
        if options.get("export_xmp"):
            command.append("--export-xmp")
        try:
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            (job_dir / "stdout.log").write_text(completed.stdout, encoding="utf-8")
            (job_dir / "stderr.log").write_text(completed.stderr, encoding="utf-8")
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.strip() or f"Analyzer exited with code {completed.returncode}")
            summary_path = job_dir / "report" / "summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.update(job_id, status="completed", summary=summary)
        except Exception as exc:
            self.update(job_id, status="failed", error=str(exc))

    def report_path(self, job_id: str, relative: str) -> Path:
        report = self._job_dir(job_id) / "report"
        target = contained_path(report, relative)
        if not target.is_file():
            raise FileNotFoundError(relative)
        return target

    def analysis(self, job_id: str) -> dict[str, Any]:
        return json.loads(self.report_path(job_id, "analysis.json").read_text(encoding="utf-8"))

    def save_ai_review(self, job_id: str, payload: dict[str, Any]) -> Path:
        target = self._job_dir(job_id) / "report" / "ai-review.json"
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return target

    def selected_previews(self, job_id: str, sources: list[str]) -> list[Path]:
        analysis = self.analysis(job_id)
        by_source = {item["source"]: item for item in analysis.get("items", [])}
        paths: list[Path] = []
        for source in sources:
            item = by_source.get(source)
            if item is None:
                raise ValueError(f"Unknown photo: {source}")
            paths.append(self.report_path(job_id, item["preview"]))
        return paths
