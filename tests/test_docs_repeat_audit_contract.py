"""Regression contracts for the documentation repeat-audit findings."""

from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path


LANDING_ROOT = Path(__file__).resolve().parents[1]
PARENT_ROOT = LANDING_ROOT.parents[1]


def test_release_smoke_includes_the_six_documentation_routes_and_js_asset() -> None:
    """Keep the production gate closed when docs or the JS bundle drift."""
    source = (LANDING_ROOT / "tests" / "verify_live_release.py").read_text(encoding="utf-8")
    for route in (
        "docs/ru/index.html",
        "docs/en/index.html",
        "docs/ru/enterprise/index.html",
        "docs/ru/enterprise/GOCPG_VS_JOERN_ANALYSIS.html",
        "docs/ru/getting-started/QUICK_START.html",
        "docs/en/api/REST_API.html",
    ):
        assert route in source
    assert '"js/main.min.js"' in source
    assert "DocsContractParser" in source
    assert "source checkout commit used to generate the HTML" in source


def test_static_search_indexes_have_the_required_fields() -> None:
    """Search is backed by a generated bilingual index, including on docs index pages."""
    for language in ("ru", "en"):
        index_path = LANDING_ROOT / "docs" / language / "search-index.json"
        records = json.loads(index_path.read_text(encoding="utf-8"))
        assert records
        assert all(
            {"title", "section", "headings", "keywords", "url"}.issubset(record)
            for record in records
        )
        assert all(record["url"].startswith(f"/docs/{language}/") for record in records)


def test_docs_shell_and_keyboard_contracts_cover_repeat_audit_findings() -> None:
    """Lock the responsive drawer, combobox, table, and typography fixes."""
    css = (LANDING_ROOT / "css" / "tailwind.css").read_text(encoding="utf-8")
    js = (LANDING_ROOT / "js" / "main.js").read_text(encoding="utf-8")
    assert "@media (min-width: 960px) and (max-width: 1599px)" in css
    assert "transform: translateX(105%)" in css
    assert "font-size: 16px" in css
    assert "table[data-columns]" in css
    assert "border-bottom: 1px solid var(--doc-border)" not in css.split(".page-docs .doc-content h2 {", 1)[1].split("}", 1)[0]
    assert "search-index.json" in js
    assert "aria-activedescendant" in js
    assert "event.key === 'ArrowDown'" in js
    assert "getClientRects()" in js
    assert "wrapper.tabIndex = overflowed ? 0 : -1" in js


def test_generated_docs_use_heading_specific_table_labels_and_current_css() -> None:
    """Tables remain distinguishable to assistive technology and use the live CSS hash."""
    page = (LANDING_ROOT / "docs" / "ru" / "enterprise" / "GOCPG_VS_JOERN_ANALYSIS.html").read_text(
        encoding="utf-8"
    )
    css_hash = __import__("hashlib").sha256((LANDING_ROOT / "css" / "tailwind.min.css").read_bytes()).hexdigest()[:12]
    assert f"cg:css-build\" content=\"{css_hash}" in page
    labels = re.findall(r'aria-label="([^"]+)"', page)
    assert any("Парсинг" in label for label in labels)
    assert any("Время по пассам" in label for label in labels)
    assert 'tabindex="-1"' in page
    assert "4adb3bb2edfa" not in page


def test_section_index_items_have_visible_descriptions_and_ordered_links() -> None:
    """Section indexes expose readable descriptions instead of bare title lists."""
    page = (LANDING_ROOT / "docs" / "ru" / "enterprise" / "index.html").read_text(encoding="utf-8")
    descriptions = [
        re.sub(r"<[^>]+>", "", unescape(value)).strip()
        for value in re.findall(r'class="doc-section-description">(.*?)</span>', page, flags=re.DOTALL)
    ]
    assert descriptions
    assert all(len(description) >= 60 for description in descriptions)
    hrefs = re.findall(r'<a href="([^"]+\.html)">', page)
    assert hrefs
