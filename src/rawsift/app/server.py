"""FastAPI application serving the local rawsift user interface."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

try:
    from fastapi import FastAPI, File, Form, HTTPException, UploadFile
    from fastapi.responses import FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
except ImportError as exc:  # pragma: no cover - exercised by the launcher
    raise RuntimeError('Install the application dependencies with: pip install ".[app]"') from exc

from .config import VisionConfig, public_environment_settings
from .jobs import JobStore
from .security import safe_relative_path
from .vision import review_previews, test_provider


def create_app(store: JobStore | None = None):
    app = FastAPI(title="rawsift local API", version="0.2.0")
    jobs = store or JobStore()

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "version": "0.2.0", "local_only": True}

    @app.get("/api/settings")
    def settings() -> dict[str, Any]:
        return public_environment_settings()

    @app.post("/api/settings/test")
    def test_settings(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            config = VisionConfig.from_payload(payload)
            response = test_provider(config)
            return {"ok": response.lower().startswith("rawsift-ok"), "response": response}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/jobs")
    def list_jobs() -> list[dict[str, Any]]:
        return jobs.list()

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        try:
            return jobs.read(job_id)
        except (FileNotFoundError, ValueError):
            raise HTTPException(status_code=404, detail="Job not found")

    @app.post("/api/jobs")
    def create_job(
        files: Annotated[list[UploadFile], File()],
        paths: Annotated[list[str], Form()],
        name: Annotated[str, Form()] = "",
        profile: Annotated[str, Form()] = "general",
    ) -> dict[str, Any]:
        if len(files) != len(paths):
            raise HTTPException(status_code=400, detail="Every file must include a relative path")
        if not files or len(files) > 10000:
            raise HTTPException(status_code=400, detail="Select between 1 and 10,000 files")
        if profile not in {"general", "macro-nature"}:
            raise HTTPException(status_code=400, detail="Invalid culling settings")
        job = jobs.create(name, {"profile": profile})
        try:
            for upload, relative in zip(files, paths, strict=True):
                safe_relative_path(relative)
                jobs.save_stream(job["id"], relative, upload.file)
            return jobs.queue(job["id"])
        except Exception as exc:
            jobs.update(job["id"], status="failed", error=str(exc))
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/jobs/{job_id}/analysis")
    def analysis(job_id: str) -> dict[str, Any]:
        try:
            return jobs.analysis(job_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Analysis is not ready")

    @app.get("/api/jobs/{job_id}/files/{relative:path}")
    def report_file(job_id: str, relative: str):
        try:
            return FileResponse(jobs.report_path(job_id, relative))
        except (FileNotFoundError, ValueError):
            raise HTTPException(status_code=404, detail="Report file not found")

    @app.post("/api/jobs/{job_id}/vision-review")
    def vision_review(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            sources = payload.get("sources") or []
            if not isinstance(sources, list):
                raise ValueError("sources must be an array")
            config = VisionConfig.from_payload(payload)
            previews = jobs.selected_previews(job_id, [str(source) for source in sources])
            result = review_previews(previews, config, display_names=[str(source) for source in sources])
            jobs.save_ai_review(job_id, result)
            return result
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    static_root = Path(__file__).resolve().parents[1] / "web" / "dist"
    if static_root.is_dir() and (static_root / "index.html").is_file():
        assets = static_root / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{path:path}")
        def spa(path: str):
            candidate = static_root / path
            if path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(static_root / "index.html")
    else:
        @app.get("/")
        def missing_frontend():
            return JSONResponse(
                status_code=503,
                content={"detail": "Frontend has not been built. Run: cd web && npm install && npm run build"},
            )

    return app
