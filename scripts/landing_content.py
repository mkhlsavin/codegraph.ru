"""Standalone landing content constants for the public site repository."""

from __future__ import annotations

import json
from pathlib import Path

SITE_CONTENT = json.loads(
    (Path(__file__).resolve().parents[1] / "site_content.json").read_text(
        encoding="utf-8"
    )
)
