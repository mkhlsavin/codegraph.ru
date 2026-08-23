"""Regression contracts for the documentation repeat-audit findings."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path

LANDING_ROOT = Path(__file__).resolve().parents[1]
PARENT_ROOT = LANDING_ROOT.parents[1]
FORBIDDEN_RU_SEARCH_PHRASES = (
    "provides practical guidance",
    "governed usage notes",
    "callable codegraph tools",
    "technical reference for",
)


def test_release_smoke_includes_the_six_documentation_routes_and_js_asset() -> None:
    """Keep the production gate closed when docs or the JS bundle drift."""
    source = (LANDING_ROOT / "tests" / "verify_live_release.py").read_text(
        encoding="utf-8"
    )
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
    assert '"docs/ru/search-index.json"' in source
    assert '"docs/en/search-index.json"' in source
    assert "DocsContractParser" in source
    assert "ThreadPoolExecutor" in source
    assert "_fetch_many" in source
    assert 'raw_public.split("<main", 1)[0]' in source
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
    assert (
        "border-bottom: 1px solid var(--doc-border)"
        not in css.split(".page-docs .doc-content h2 {", 1)[1].split("}", 1)[0]
    )
    assert "search-index.json" in js
    assert "aria-activedescendant" in js
    assert "event.key === 'ArrowDown'" in js
    assert "getClientRects()" in js
    assert "wrapper.tabIndex = overflowed ? 0 : -1" in js
    assert "drawer.inert = true" in js
    assert "drawer.inert = false" in js
    assert "if (openDrawer === 'toc' && !sidebarQuery.matches && sidebar)" in js
    assert "target.setAttribute('tabindex', '-1')" in js
    assert "target.focus({ preventScroll: true })" in js
    assert "data-doc-live" in js
    assert (
        "position: absolute"
        in css.split(".page-docs .doc-code-copy", 1)[1].split("}", 1)[0]
    )
    assert "padding: 48px 18px 18px" in css
    toggle_css = css.split(".page-docs .doc-sidebar-toggle {", 1)[1].split("}", 1)[0]
    toggle_icon_css = css.split(".page-docs .doc-sidebar-toggle::after {", 1)[1].split(
        "}", 1
    )[0]
    assert "padding: 0 6px 0 0" in toggle_css
    assert "flex: 0 0 8px" in toggle_icon_css


def test_generated_docs_use_heading_specific_table_labels_and_current_css() -> None:
    """Tables remain distinguishable to assistive technology and use the live CSS hash."""
    page = (
        LANDING_ROOT / "docs" / "ru" / "enterprise" / "GOCPG_VS_JOERN_ANALYSIS.html"
    ).read_text(encoding="utf-8")
    css_hash = (
        __import__("hashlib")
        .sha256((LANDING_ROOT / "css" / "tailwind.min.css").read_bytes())
        .hexdigest()[:12]
    )
    assert f'cg:css-build" content="{css_hash}' in page
    labels = re.findall(r'aria-label="([^"]+)"', page)
    assert any("Парсинг" in label for label in labels)
    assert any("Время по пассам" in label for label in labels)
    assert 'tabindex="-1"' in page
    assert "4adb3bb2edfa" not in page


def test_section_index_items_have_visible_descriptions_and_ordered_links() -> None:
    """Section indexes expose readable descriptions instead of bare title lists."""
    page = (LANDING_ROOT / "docs" / "ru" / "enterprise" / "index.html").read_text(
        encoding="utf-8"
    )
    descriptions = [
        re.sub(r"<[^>]+>", "", unescape(value)).strip()
        for value in re.findall(
            r'class="doc-section-description">(.*?)</span>', page, flags=re.DOTALL
        )
    ]
    assert descriptions
    assert all(len(description) >= 60 for description in descriptions)
    hrefs = re.findall(r'<a href="([^"]+\.html)">', page)
    assert hrefs
    assert "…" not in " ".join(descriptions)
    assert any(
        "инфраструктур" in description.casefold() for description in descriptions
    )


def test_russian_search_index_uses_localized_descriptions_and_keywords() -> None:
    """RU search metadata must not expose English frontmatter boilerplate."""
    records = json.loads(
        (LANDING_ROOT / "docs" / "ru" / "search-index.json").read_text(encoding="utf-8")
    )
    serialized = json.dumps(records, ensure_ascii=False)
    assert not re.search(r"\bTechnical Reference for\b", serialized)
    assert not re.search(r"\bEnterprise Compliance Reference for\b", serialized)
    acp = next(record for record in records if "ACP" in record["title"].upper())
    assert "интеграции" in acp["description"].casefold()
    assert any("ACP" in keyword for keyword in acp["keywords"])
    serialized_casefold = serialized.casefold()
    assert not any(
        phrase in serialized_casefold for phrase in FORBIDDEN_RU_SEARCH_PHRASES
    )


def test_competitive_matrix_separates_lead_from_snapshot_callout() -> None:
    """Keep the generated lead concise and preserve the snapshot sentence boundary."""
    page = (
        LANDING_ROOT / "docs" / "ru" / "enterprise" / "COMPETITIVE_MATRIX.html"
    ).read_text(encoding="utf-8")
    lead_match = re.search(r'<p class="doc-lead">(.*?)</p>', page, flags=re.DOTALL)
    assert lead_match
    lead = re.sub(r"<[^>]+>", "", unescape(lead_match.group(1))).replace("\xa0", " ")
    body = re.sub(r"<[^>]+>", " ", unescape(page)).replace("\xa0", " ")
    body = " ".join(body.split())

    assert "Дата среза" not in lead
    assert "пилота. Дата среза: 21 июля 2026 года" in body
    assert "пилота Дата среза" not in body


def _canonical_public_release_date(index_html: str) -> str:
    """Return the single release date declared by the public projection."""

    values = re.findall(r'"dateModified"\s*:\s*"([^"]+)"', index_html)
    assert values
    assert len(set(values)) == 1
    return values[0]


def test_public_release_date_is_independent_from_the_runner_clock() -> None:
    """Use projection metadata even when its release date differs from the runner date."""

    assert (
        _canonical_public_release_date('{"dateModified": "2030-01-02"}') == "2030-01-02"
    )


def test_sitemap_covers_indexable_documentation_pages_with_canonical_release_date() -> (
    None
):
    """Every generated article is discoverable while README duplicates stay excluded."""
    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    sitemap = ET.parse(LANDING_ROOT / "sitemap.xml")
    entries = {
        row.findtext("sm:loc", namespaces=namespace): row
        for row in sitemap.findall("sm:url", namespace)
    }
    expected_date = _canonical_public_release_date(
        (LANDING_ROOT / "index.html").read_text(encoding="utf-8")
    )
    generated: list[tuple[str, Path]] = []
    for language in ("ru", "en"):
        generated.extend(
            (language, document)
            for document in (LANDING_ROOT / "docs" / language).rglob("*.html")
        )
    for language, document in generated:
        relative = document.relative_to(LANDING_ROOT).as_posix()
        loc = f"https://codegraph.ru/{relative}"
        if document.name.upper() == "README.HTML":
            assert loc not in entries
            continue
        html = document.read_text(encoding="utf-8")
        if re.search(
            r'<meta\s+[^>]*name=["\']robots["\'][^>]*content=["\'][^"\']*noindex',
            html,
            re.I,
        ):
            assert loc not in entries
            continue
        assert loc in entries
        assert (
            entries[loc].findtext("sm:lastmod", namespaces=namespace) == expected_date
        )
        if document.name.lower() == "index.html":
            expected_changefreq = (
                "weekly"
                if document.parent == LANDING_ROOT / "docs" / language
                else "monthly"
            )
            expected_priority = (
                "0.8"
                if language == "ru" and expected_changefreq == "weekly"
                else ("0.7" if expected_changefreq == "weekly" else "0.7")
            )
        else:
            expected_changefreq = "monthly"
            expected_priority = "0.6"
        assert (
            entries[loc].findtext("sm:changefreq", namespaces=namespace)
            == expected_changefreq
        )
        assert (
            entries[loc].findtext("sm:priority", namespaces=namespace)
            == expected_priority
        )
    assert (
        "https://codegraph.ru/docs/ru/enterprise/GOCPG_VS_JOERN_ANALYSIS.html"
        in entries
    )
    for route in (
        "downloads/digital-role-passport/index.html",
        "downloads/digital-role-passport/role-passport.html",
        "research/tochnost-otvetov-i-skorost-razbora.html",
    ):
        assert f"https://codegraph.ru/{route}" not in entries


def test_generated_docs_mark_documentation_as_the_current_global_section() -> None:
    """The shared shell exposes the current documentation section to all users."""
    page = (
        LANDING_ROOT / "docs" / "ru" / "enterprise" / "GOCPG_VS_JOERN_ANALYSIS.html"
    ).read_text(encoding="utf-8")
    assert page.count('data-nav-link aria-current="page"') == 2


def test_service_typography_meets_documentation_scale() -> None:
    """Search, sidebar and card metadata must not fall below the docs scale."""
    css = (LANDING_ROOT / "css" / "tailwind.css").read_text(encoding="utf-8")
    assert (
        "font-size: 12px;"
        in css.split(".page-docs .doc-sidebar-title", 1)[1].split("}", 1)[0]
    )
    assert (
        "font-size: 14px;"
        in css.split(".page-docs .doc-search-input", 1)[1].split("}", 1)[0]
    )
    assert ".page-docs .doc-search-result-title { font-size: 14px; }" in css
    assert (
        ".page-docs .doc-search-result-section { margin-top: 2px; color: var(--doc-text-muted); font-size: 12px; }"
        in css
    )
    assert (
        "font-size: 12px;"
        in css.split(".page-docs .doc-card-count", 1)[1].split("}", 1)[0]
    )


def test_documentation_geometry_uses_shared_radius_and_shadow_tokens() -> None:
    """Keep the remaining documentation controls on the shared design tokens."""
    css = (LANDING_ROOT / "css" / "tailwind.css").read_text(encoding="utf-8")
    assert "--cg-radius-micro: 4px;" in css
    expected_tokens = {
        ".page-docs .doc-search-input": "var(--cg-radius-control)",
        ".page-docs .doc-search-results": "var(--cg-radius-control)",
        ".page-docs .doc-card": "var(--cg-radius-card)",
        ".page-docs .doc-code-copy": "var(--cg-radius-micro)",
        ".page-docs .heading-anchor::before": "var(--cg-radius-micro)",
    }
    for selector, token in expected_tokens.items():
        block = css.split(f"{selector} {{", 1)[1].split("}", 1)[0]
        assert f"border-radius: {token};" in block
    search_results = css.split(".page-docs .doc-search-results", 1)[1].split("}", 1)[0]
    assert "box-shadow: var(--shadow-md);" in search_results
