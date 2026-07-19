"""Regression checks for the shared landing-page header breakpoints."""

from pathlib import Path
import re


LANDING_ROOT = Path(__file__).resolve().parents[1]
HEADER_CSS = LANDING_ROOT / "css" / "components" / "_header.css"
RESPONSIVE_CSS = LANDING_ROOT / "css" / "layout" / "_responsive.css"
MINIFIED_CSS = LANDING_ROOT / "css" / "styles.min.css"


def test_full_header_navigation_starts_only_when_all_controls_fit() -> None:
    """Keep desktop links and the mobile-menu cutoff on one safe breakpoint."""
    header_css = HEADER_CSS.read_text(encoding="utf-8")
    responsive_css = RESPONSIVE_CSS.read_text(encoding="utf-8")

    assert re.search(
        r"@media\s*\(min-width:\s*1200px\)\s*\{\s*\.nav-list\s*\{[^}]*display:\s*flex",
        header_css,
        re.DOTALL,
    )
    assert re.search(
        r"@media\s*\(min-width:\s*1200px\)\s*\{[^}]*\.mobile-menu-toggle\s*\{[^}]*display:\s*none",
        responsive_css,
        re.DOTALL,
    )


def test_built_css_carries_the_safe_header_breakpoint() -> None:
    """Ensure production receives the same responsive contract as source CSS."""
    minified_css = MINIFIED_CSS.read_text(encoding="utf-8")

    assert re.search(
        r"@media\s*\(min-width:1200px\)\{\.nav-list\{display:flex",
        minified_css,
    )
    assert re.search(
        r"@media\s*\(min-width:1200px\)\{[^}]*\.mobile-menu-toggle\{display:none",
        minified_css,
    )
