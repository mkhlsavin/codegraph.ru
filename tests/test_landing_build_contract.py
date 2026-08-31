"""Contracts for the DRY landing route and content sources."""

from __future__ import annotations

import fnmatch
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from bs4 import BeautifulSoup

LANDING_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = LANDING_ROOT.parents[1]
PUBLIC_PAGE_EXCLUSIONS = ("docs/**", "whitepaper.html")
ROOT_ROUTE_REGISTRY = REPOSITORY_ROOT / "scripts" / "landing_build_registry.py"
if ROOT_ROUTE_REGISTRY.is_file() and str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.landing_content import SITE_CONTENT  # noqa: E402


def _load_design_contract_module() -> ModuleType:
    """Load the standalone landing design contract from its exact file path."""
    module_path = LANDING_ROOT / "scripts" / "check_design_system_contract.py"
    spec = importlib.util.spec_from_file_location(
        "landing_design_system_contract", module_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _shared_routes(repository_root: Path, landing_root: Path) -> list[Any]:
    """Load canonical source routes or skip when validating a standalone projection."""

    registry = repository_root / "scripts" / "landing_build_registry.py"
    if not registry.is_file():
        pytest.skip(
            "canonical root route registry is unavailable in standalone projection"
        )
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))
    from scripts.landing_build_registry import iter_shared_routes

    return list(iter_shared_routes(landing_root))


def _public_manifest_routes() -> list[str]:
    """Expand every public-page manifest include into a deterministic route list."""
    manifest = json.loads(
        (LANDING_ROOT / "public-pages.json").read_text(encoding="utf-8")
    )
    routes = {
        path.relative_to(LANDING_ROOT).as_posix()
        for pattern in manifest["include"]
        for path in LANDING_ROOT.glob(pattern)
        if path.is_file()
    }
    return sorted(
        route
        for route in routes
        if not any(
            fnmatch.fnmatch(route, pattern) for pattern in PUBLIC_PAGE_EXCLUSIONS
        )
    )


def test_shared_route_registry_is_unique_and_points_to_existing_pages() -> None:
    """Require every shared route to be unique and backed by a public page."""
    routes = _shared_routes(REPOSITORY_ROOT, LANDING_ROOT)
    paths = [route.path for route in routes]

    assert paths
    assert len(paths) == len(set(paths))
    assert all((LANDING_ROOT / path).is_file() for path in paths)
    assert "whitepaper.html" in paths
    assert any(path.startswith("compare/") for path in paths)
    assert any(path.startswith("research/") for path in paths)


def test_standalone_projection_skips_only_the_source_registry_assertion(
    tmp_path: Path,
) -> None:
    """A distribution checkout must collect the suite without the root source repository."""

    with pytest.raises(pytest.skip.Exception):
        _shared_routes(tmp_path / "source-absent", LANDING_ROOT)


def test_shared_positioning_contract_has_all_non_empty_values() -> None:
    """Require every canonical positioning field to have public content."""
    expected = {
        "canonical_category",
        "canonical_seo_title",
        "canonical_meta_description",
        "home_h1",
        "social_image_alt",
    }

    assert set(SITE_CONTENT) == expected
    assert all(value.strip() for value in SITE_CONTENT.values())


@pytest.mark.nfr(
    "CNFR-Q05-RELIABILITY-NONREGRESSION-01",
    scenarios=("primary", "negative", "observability"),
)
def test_homepage_heading_budget_includes_the_benefits_surface() -> None:
    """Keep the intentional benefits section inside the homepage heading budget."""
    contract = _load_design_contract_module()
    homepage = BeautifulSoup(
        (LANDING_ROOT / "index.html").read_text(encoding="utf-8"), "html.parser"
    )
    headings = [
        heading.get_text(" ", strip=True)
        for heading in homepage.select("main > section h2")
    ]

    assert "Что меняется в\u00a0ежедневной работе" in headings
    assert len(headings) == contract.HOME_TOP_LEVEL_HEADING_LIMIT == 9


@pytest.mark.nfr(
    "CNFR-Q05-RELIABILITY-NONREGRESSION-01",
    scenarios=("primary", "negative", "observability"),
)
def test_public_favicon_endpoint_is_backed_by_a_real_icon() -> None:
    """Keep the browser fallback favicon request on a successful static route."""
    favicon = LANDING_ROOT / "favicon.ico"
    demo_html = (LANDING_ROOT / "demo" / "index.html").read_text(encoding="utf-8")

    assert favicon.is_file()
    assert favicon.stat().st_size > 0
    assert 'rel="icon" href="/favicon.ico"' in demo_html


@pytest.mark.nfr(
    "CNFR-Q01-SECURE-BY-DESIGN-01",
    "CNFR-Q05-RELIABILITY-NONREGRESSION-01",
    scenarios=("primary", "negative", "observability"),
)
def test_yandex_metrika_csp_allows_only_the_observed_runtime_endpoints() -> None:
    """Allow Metrika websocket and frame traffic without broad CSP wildcards."""
    head_html = (LANDING_ROOT / "templates" / "head.html").read_text(encoding="utf-8")

    assert "wss://mc.yandex.ru" in head_html
    assert "frame-src https://mc.yandex.ru https://mc.yandex.com" in head_html
    assert "*.yandex" not in head_html


@pytest.mark.nfr(
    "CNFR-Q05-RELIABILITY-NONREGRESSION-01",
    scenarios=("primary", "negative", "observability"),
)
def test_article_shell_has_explicit_hero_and_section_geometry() -> None:
    """Keep ArticleShell content aligned and prevent section width cascade drift."""
    css = (LANDING_ROOT / "css" / "tailwind.css").read_text(encoding="utf-8")

    hero_rule = re.search(r"\.cg-article-hero\s*\{(?P<body>.*?)\n\}", css, re.DOTALL)
    assert hero_rule is not None
    hero_body = hero_rule.group("body")
    assert (
        "padding-left: max(32px, calc((100% - var(--container-max)) / 2 + 32px));"
        in hero_body
    )
    assert (
        "padding-right: max(32px, calc((100% - var(--container-max)) / 2 + 32px));"
        in hero_body
    )

    section_rule = re.search(
        r"\.cg-article\s*>\s*\.cg-article-section\s*\{(?P<body>.*?)\n\}",
        css,
        re.DOTALL,
    )
    assert section_rule is not None
    assert "max-width: var(--container-max);" in section_rule.group("body")

    article_pages = []
    for page in LANDING_ROOT.rglob("*.html"):
        html = page.read_text(encoding="utf-8")
        if 'class="cg-article"' in html and 'class="cg-article-hero"' in html:
            article_pages.append(page)

    assert len(article_pages) >= 25


@pytest.mark.nfr(
    "CNFR-Q05-RELIABILITY-NONREGRESSION-01",
    scenarios=("primary", "negative", "observability"),
)
def test_comparison_article_primitives_have_readable_surface_and_mobile_table_contract() -> (
    None
):
    """Keep comparison trust and tables aligned with the shared design system."""
    css = (LANDING_ROOT / "css" / "tailwind.css").read_text(encoding="utf-8")

    trust_rule = re.search(r"\.cg-article-trust\s*\{(?P<body>.*?)\n\}", css, re.DOTALL)
    assert trust_rule is not None
    assert "color: var(--cg-text-primary);" in trust_rule.group("body")

    assert ".cg-article-trust a" in css
    assert "color: var(--cg-primary);" in css
    assert '.cg-article-table th[scope="col"]' in css
    assert '.cg-article-table th[scope="row"]' in css
    assert '[data-page-stage="comparison"] .cg-article-table-wrap::before' in css
    assert 'content: "Прокрутите вправо, чтобы увидеть все колонки";' in css


@pytest.mark.nfr(
    "CNFR-Q05-RELIABILITY-NONREGRESSION-01",
    scenarios=("primary", "negative", "observability"),
)
def test_comparison_article_shell_keeps_desktop_widths_coherent() -> None:
    """Keep comparison shell blocks at the vertical-page width on desktop."""
    css = (LANDING_ROOT / "css" / "tailwind.css").read_text(encoding="utf-8")

    assert '[data-page-stage="comparison"] .cg-article-hero' not in css
    assert "max-width: 920px;" not in css
    assert "max-width: 800px;" not in css


@pytest.mark.nfr(
    "FR-P1248-SHELL-01",
    "FR-P1248-ROUTES-01",
    "CNFR-Q1248-RESPONSIVE-01",
    scenarios=("primary", "negative", "observability"),
)
def test_every_public_page_uses_the_vertical_content_shell() -> None:
    """BDD: Given every manifest route, Then each page uses the vertical shell.

    The whitepaper TOC and documentation grid are the only intentional scope
    exclusions; all other public routes must keep a page-level 1200px authority.
    """
    routes = _public_manifest_routes()
    assert "whitepaper.html" not in routes
    assert not any(route.startswith("docs/") for route in routes)
    assert "security.html" in routes
    assert any(route.startswith("compare/") for route in routes)

    css = (LANDING_ROOT / "css" / "tailwind.css").read_text(encoding="utf-8")
    assert "--container-max: 1200px;" in css
    assert ".cg-article > .cg-article-section" in css
    assert "max-width: 920px;" not in css
    assert "max-width: 800px;" not in css

    article_routes: list[str] = []
    shell_routes: list[str] = []
    for route in routes:
        page = BeautifulSoup(
            (LANDING_ROOT / route).read_text(encoding="utf-8"), "html.parser"
        )
        main = page.find("main")
        assert main is not None, route
        article = main.find("article", class_="cg-article")
        if article is not None:
            article_routes.append(route)
            assert article.find(class_="cg-article-hero") is not None, route
        else:
            shell_routes.append(route)
            assert main.find(class_="cg-content-shell") is not None, route

    assert article_routes
    assert shell_routes
    assert len(article_routes) + len(shell_routes) == len(routes)
