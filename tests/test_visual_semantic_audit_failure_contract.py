"""Behavioral contract for visual-audit failure classification."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).parent))

from visual_semantic_audit import (
    PROFILES,
    _failures,
    _inspect_route,
    _public_layout_failure_reasons,
    _serve_local_request,
)


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


def test_mobile_meta_refresh_route_is_inspected_after_navigation(
    tmp_path: Path,
) -> None:
    """The legacy demo redirect must not race semantic inspection or screenshots."""

    async def inspect_redirect() -> dict[str, object]:
        base_url = "http://story1113.local"
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(
                **PROFILES["mobile"]["context"],
                color_scheme="light",
            )
            await context.route(
                "**/*",
                lambda route: _serve_local_request(route, base_url=base_url),
            )
            try:
                return await asyncio.wait_for(
                    _inspect_route(
                        context,
                        base_url=base_url,
                        output=tmp_path,
                        profile="mobile",
                        route="demo/index.html",
                        semaphore=asyncio.Semaphore(1),
                    ),
                    timeout=10,
                )
            finally:
                await context.close()
                await browser.close()

    result = asyncio.run(inspect_redirect())

    assert "error" not in result
    assert result["console_errors"] == []
    assert result["screenshot"] == "mobile__demo__index.html.jpg"
    assert (tmp_path / str(result["screenshot"])).is_file()


def test_homepage_accepts_governed_nine_chapter_limit() -> None:
    """The visual gate must share the design contract's nine-chapter limit."""
    row = {"route": "index.html", "data_density": "expressive", "top_level_h2": 9}

    assert _public_layout_failure_reasons(row) == []
