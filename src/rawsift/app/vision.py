"""External vision review through OpenAI-compatible APIs."""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any, Callable

from PIL import Image

from .config import VisionConfig


MAX_REVIEW_IMAGES = 8

REVIEW_PROMPT = """You are a conservative professional photo editor. Review the attached compressed previews.
The deterministic local pass has already measured sharpness, exposure, duplicates, and bracket membership.
Judge only visual factors that benefit from semantic vision: subject clarity, composition, timing, expression or animal pose, distracting elements, and artistic usefulness.
Do not recommend deleting originals. Exposure-bracket and focus-bracket members must remain together.
Return only valid JSON in this shape:
{
  "summary": "short batch assessment",
  "photos": [
    {
      "filename": "exact filename",
      "recommendation": "pick|maybe|reject-candidate|preserve-bracket",
      "visual_score": 0,
      "subject": "short subject description",
      "composition": "short assessment",
      "critical_focus": "short assessment",
      "notes": "one actionable sentence"
    }
  ]
}
Use integer visual_score values from 0 to 100 and include every attached image exactly once."""


def preview_data_url(path: Path, max_edge: int = 1280, quality: int = 82) -> str:
    """Create a bounded JPEG data URL without changing the report preview."""
    from io import BytesIO

    with Image.open(path) as source:
        image = source.convert("RGB")
        image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        image.save(buffer, "JPEG", quality=quality, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def parse_json_response(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if match:
        cleaned = match.group(1)
    data = json.loads(cleaned)
    if not isinstance(data, dict) or not isinstance(data.get("photos"), list):
        raise ValueError("Vision provider returned an unexpected JSON structure")
    return data


def _content(paths: list[Path], prompt: str, display_names: list[str] | None = None) -> list[dict[str, Any]]:
    if display_names is not None and len(display_names) != len(paths):
        raise ValueError("Every preview must include one display name")
    content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
    for index, path in enumerate(paths):
        name = display_names[index] if display_names is not None else path.name
        content.append({"type": "input_text", "text": f"Filename: {name}"})
        content.append({"type": "input_image", "image_url": preview_data_url(path)})
    return content


def review_previews(
    paths: list[Path],
    config: VisionConfig,
    prompt: str = REVIEW_PROMPT,
    client_factory: Callable[..., Any] | None = None,
    display_names: list[str] | None = None,
) -> dict[str, Any]:
    if not paths:
        raise ValueError("Select at least one preview")
    if len(paths) > MAX_REVIEW_IMAGES:
        raise ValueError(f"A single review can contain at most {MAX_REVIEW_IMAGES} previews")
    if client_factory is None:
        from openai import OpenAI

        client_factory = OpenAI
    client = client_factory(api_key=config.api_key, base_url=config.base_url)
    if config.api_mode == "responses":
        response = client.responses.create(
            model=config.model,
            input=[{"role": "user", "content": _content(paths, prompt, display_names)}],
        )
        text = response.output_text
    else:
        chat_content: list[dict[str, Any]] = []
        for entry in _content(paths, prompt, display_names):
            if entry["type"] == "input_text":
                chat_content.append({"type": "text", "text": entry["text"]})
            else:
                chat_content.append({"type": "image_url", "image_url": {"url": entry["image_url"]}})
        response = client.chat.completions.create(
            model=config.model,
            messages=[{"role": "user", "content": chat_content}],
        )
        text = response.choices[0].message.content
    return parse_json_response(text)


def test_provider(config: VisionConfig, client_factory: Callable[..., Any] | None = None) -> str:
    if client_factory is None:
        from openai import OpenAI

        client_factory = OpenAI
    client = client_factory(api_key=config.api_key, base_url=config.base_url)
    if config.api_mode == "responses":
        response = client.responses.create(model=config.model, input="Reply with exactly: rawsift-ok")
        return response.output_text.strip()
    response = client.chat.completions.create(
        model=config.model,
        messages=[{"role": "user", "content": "Reply with exactly: rawsift-ok"}],
    )
    return str(response.choices[0].message.content).strip()
