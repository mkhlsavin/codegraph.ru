"""Behavioral contract for visual-audit failure classification."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from visual_semantic_audit import _failures


def _valid_row() -> dict[str, object]:
    """Return the smallest row that satisfies all fail-closed defaults."""
    return {
        "profile": "desktop",
        "route": "docs/en/example.html",
        "status": 200,
        "h1_count": 1,
        "main_count": 1,
        "title": "Example",
        "description": "Description",
        "buyer_question": "",
        "main_buyer_question": "",
        "csp": "style-src 'self'",
        "canonical_count": 1,
        "canonical": "https://codegraph.ru/docs/en/example.html",
        "og_title": "Example",
        "og_description": "Description",
        "twitter_title": "Example",
        "twitter_description": "Description",
        "webpage_schema_parity": True,
        "h1_contrast_ratio": 4.5,
        "stylesheet_links": ["../../../css/tailwind.min.css?v=test"],
        "inline_styles": 0,
        "style_blocks": 0,
        "render_signature": "sha256:test",
    }


def test_valid_visual_audit_row_has_no_failure_reasons() -> None:
    """A valid documentation row must remain accepted after complexity refactors."""
    assert _failures([_valid_row()], enforce=True) == []


def test_invalid_visual_audit_row_preserves_cross_category_reasons() -> None:
    """Core, metadata, accessibility, and enforcement defects remain observable."""
    row = _valid_row()
    row.update(
        {
            "status": 500,
            "h1_count": 0,
            "missing_alt": 2,
            "og_title": "Wrong",
            "webpage_schema_parity": False,
            "inline_styles": 1,
        }
    )

    reasons = _failures([row], enforce=True)[0]["reasons"]

    assert "status=500" in reasons
    assert "h1_count=0" in reasons
    assert "missing_alt=2" in reasons
    assert "og:title parity mismatch" in reasons
    assert "WebPage schema parity mismatch count=None" in reasons
    assert "inline_styles=1" in reasons
