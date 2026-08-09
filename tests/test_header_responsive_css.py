"""Regression checks for the shared landing-page header breakpoints."""

import re
from pathlib import Path

LANDING_ROOT = Path(__file__).resolve().parents[1]
HEADER_TEMPLATE = LANDING_ROOT / "templates" / "header.html"
MINIFIED_CSS = LANDING_ROOT / "css" / "tailwind.min.css"


def test_full_header_navigation_starts_only_when_all_controls_fit() -> None:
    """Keep desktop links and the mobile-menu cutoff on one Tailwind breakpoint."""
    header = HEADER_TEMPLATE.read_text(encoding="utf-8")

    assert 'class="cg-shell-nav-list items-center gap-8"' in header
    assert "cg-mobile-toggle" in header


def test_built_css_carries_the_safe_header_breakpoint() -> None:
    """Ensure production receives the same responsive contract as source CSS."""
    minified_css = MINIFIED_CSS.read_text(encoding="utf-8")

    assert re.search(r"@media\s*\(min-width:1024px\)", minified_css)
    assert ".cg-shell-nav-list" in minified_css
    assert ".cg-mobile-toggle" in minified_css
