"""Path and network validation helpers for the local application."""

from __future__ import annotations

import ipaddress
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse


def safe_relative_path(value: str) -> Path:
    """Return a normalized relative upload path without traversal components."""
    normalized = value.replace("\\", "/")
    raw_parts = normalized.split("/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or "\x00" in normalized
        or normalized.startswith("/")
        or path.is_absolute()
        or any(part in {"", ".", ".."} or ":" in part for part in raw_parts)
    ):
        raise ValueError("Invalid relative file path")
    return Path(*path.parts)


def contained_path(root: Path, relative: str) -> Path:
    """Resolve a user-supplied relative path and require it to stay below root."""
    root = root.resolve()
    target = (root / safe_relative_path(relative)).resolve()
    if target != root and root not in target.parents:
        raise ValueError("Path escapes its allowed directory")
    return target


def validate_api_base_url(value: str) -> str:
    """Allow HTTPS providers and explicit loopback HTTP development endpoints."""
    parsed = urlparse(value.strip().rstrip("/"))
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("API address must be a simple absolute URL")
    if parsed.scheme == "https":
        return value.strip().rstrip("/")
    if parsed.scheme != "http":
        raise ValueError("API address must use HTTPS")
    host = parsed.hostname
    try:
        loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = host == "localhost"
    if not loopback:
        raise ValueError("Plain HTTP is allowed only for localhost providers")
    return value.strip().rstrip("/")
