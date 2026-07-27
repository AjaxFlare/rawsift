"""Runtime configuration for the local UI and optional vision provider."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .security import validate_api_base_url


@dataclass(frozen=True)
class VisionConfig:
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-5.6"
    api_mode: str = "responses"

    def __post_init__(self) -> None:
        object.__setattr__(self, "base_url", validate_api_base_url(self.base_url))
        if not self.api_key.strip():
            raise ValueError("API Key is required")
        if not self.model.strip():
            raise ValueError("Model is required")
        if self.api_mode not in {"responses", "chat-completions"}:
            raise ValueError("API mode must be responses or chat-completions")

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "VisionConfig":
        key = str(payload.get("api_key") or os.getenv("OPENAI_API_KEY") or "")
        return cls(
            api_key=key,
            base_url=str(payload.get("base_url") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"),
            model=str(payload.get("model") or os.getenv("RAWSIFT_VISION_MODEL") or "gpt-5.6"),
            api_mode=str(payload.get("api_mode") or os.getenv("RAWSIFT_API_MODE") or "responses"),
        )

    def public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["api_key"] = ""
        data["api_key_configured"] = bool(self.api_key)
        return data


def data_root() -> Path:
    path = Path(os.getenv("RAWSIFT_DATA_DIR", Path.home() / ".rawsift" / "jobs")).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def public_environment_settings() -> dict[str, Any]:
    key = os.getenv("OPENAI_API_KEY", "")
    return {
        "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        "model": os.getenv("RAWSIFT_VISION_MODEL", "gpt-5.6"),
        "api_mode": os.getenv("RAWSIFT_API_MODE", "responses"),
        "api_key_configured": bool(key),
    }
