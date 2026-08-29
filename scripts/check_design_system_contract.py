#!/usr/bin/env python3
"""Fail-closed checks for the public CodeGraph design-system contract."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
from typing import Any, Iterable
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "public-pages.json"
CSS = ROOT / "css" / "tailwind.css"
JS = ROOT / "js" / "main.js"
PRODUCT_ROUTES = {
    "index.html",
    "whitepaper.html",
    "privacy.html",
    "security.html",
    "productivity.html",
    "compliance.html",
    "cpg.html",
    "ai-engineering.html",
    "business-efficiency.html",
    "product-delivery.html",
    "platform-operations.html",
    "evidence.html",
    "digital-team.html",
    "integrations.html",
    "scenarios/portfolio-change-management.html",
    "scenarios/feature-delivery.html",
    "scenarios/codebase-audit.html",
    "scenarios/release-readiness.html",
    "scenarios/technical-controls.html",
    "scenarios/ai-code-control.html",
}
HOME_TOP_LEVEL_HEADING_LIMIT = 9
RESOURCE_ROUTES = {
    "downloads/digital-role-passport/index.html",
    "downloads/digital-role-passport/role-passport.html",
}
BLOG_ARTICLE_ROUTE = "blog/kogda-kod-perestaet-byt-uzkim-mestom/index.html"


def public_pages() -> list[Path]:
    """Return every public HTML page declared by the publication manifest."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    paths: set[Path] = set()
    for pattern in manifest["include"]:
        paths.update(ROOT.glob(pattern))
    return sorted(
        path
        for path in paths
        if path.is_file()
        and not any(part in manifest.get("exclude", []) for part in path.parts)
        and not path.name.startswith("yandex_")
    )


def _route(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def check_design_tokens_parity(errors: list[str]) -> None:
    """Append errors when authored and generated design tokens diverge."""
    source = CSS.read_text(encoding="utf-8")
    for token in (
        "--cg-primary",
        "--cg-canvas",
        "--cg-surface",
        "--cg-border-subtle",
        "--cg-radius-control",
        "--cg-radius-card",
        "--cg-radius-panel",
        "--cg-density-control-height",
    ):
        if token not in source:
            errors.append(f"css: missing semantic token {token}")
    migration = ROOT / "design-token-migration.md"
    if not migration.is_file():
        errors.append("css: design-token-migration.md is missing")
    for legacy_token in (
        "--color-primary",
        "--color-bg",
        "--color-text",
        "--font-family",
        "--radius-sm",
        "--transition-fast",
    ):
        if legacy_token in source:
            errors.append(f"css: retired legacy token remains: {legacy_token}")


def _normalize_metadata(value: object) -> str:
    """Normalize one metadata value for deterministic parity checks."""
    return re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()


def _metadata_content(node: Any) -> str:
    """Return a scalar content attribute from an optional DOM node."""
    return str(node.get("content", "")).strip() if node is not None else ""


def _webpage_schemas(soup: Any) -> list[dict[str, Any]]:
    """Extract valid WebPage JSON-LD objects from one parsed page."""
    payloads: list[dict[str, Any]] = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or script.get_text())
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("@type") == "WebPage":
            payloads.append(payload)
    return payloads


def _append_page_metadata_errors(
    route: str,
    soup: Any,
    title: str,
    description: str,
    errors: list[str],
) -> None:
    """Append social and schema parity errors for one page."""
    pairs = (
        ("og:title", soup.select_one('meta[property="og:title"]'), title),
        (
            "og:description",
            soup.select_one('meta[property="og:description"]'),
            description,
        ),
        ("twitter:title", soup.select_one('meta[name="twitter:title"]'), title),
        (
            "twitter:description",
            soup.select_one('meta[name="twitter:description"]'),
            description,
        ),
    )
    for label, node, expected in pairs:
        if _normalize_metadata(_metadata_content(node)) != _normalize_metadata(
            expected
        ):
            errors.append(
                f"{route}: {label} must equal {'title' if label.endswith('title') else 'description'}"
            )
    webpage = _webpage_schemas(soup)
    if len(webpage) != 1:
        errors.append(f"{route}: WebPage metadata must match title and description")
        return
    schema = webpage[0]
    if _normalize_metadata(schema.get("name", "")) != _normalize_metadata(
        title
    ) or _normalize_metadata(schema.get("description", "")) != _normalize_metadata(
        description
    ):
        errors.append(f"{route}: WebPage metadata must match title and description")


def _append_duplicate_metadata_errors(
    label: str,
    values: list[tuple[str, str]],
    errors: list[str],
) -> None:
    """Append duplicate title or description errors across public routes."""
    counts = Counter(_normalize_metadata(value) for value, _route_name in values)
    for value, count in counts.items():
        if not value or count <= 1:
            continue
        routes = ", ".join(
            route
            for candidate, route in values
            if _normalize_metadata(candidate) == value
        )
        errors.append(f"{label} duplicated on {routes}")


def check_metadata_contract(pages: Iterable[Path], errors: list[str]) -> None:
    """Require page-specific metadata and parity across social/schema surfaces."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if not manifest.get("metadata_source") or not manifest.get("metadata_fields"):
        errors.append("manifest: metadata source and fields are required")
    titles: list[tuple[str, str]] = []
    descriptions: list[tuple[str, str]] = []
    for path in pages:
        route = _route(path)
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        description = _metadata_content(soup.select_one('meta[name="description"]'))
        if not title or not description:
            errors.append(f"{route}: title and description are required")
        _append_page_metadata_errors(route, soup, title, description, errors)
        titles.append((title, route))
        descriptions.append((description, route))
    _append_duplicate_metadata_errors("title", titles, errors)
    _append_duplicate_metadata_errors("description", descriptions, errors)


def _append_control_and_card_errors(route: str, soup: Any, errors: list[str]) -> None:
    """Append control, card, theme, marker, and FAQ component errors."""
    redundant_theme_utilities = {
        "dark:bg-cg-surface": "bg-cg-surface",
        "dark:bg-cg-surface-subtle": "bg-cg-surface-subtle",
        "dark:border-cg-border": "border-cg-border",
        "dark:text-cg-ink": "text-cg-ink",
        "dark:text-cg-muted": "text-cg-muted",
        "dark:hover:bg-cg-surface-subtle": "hover:bg-cg-surface-subtle",
        "dark:hover:text-cg-ink": "hover:text-cg-ink",
    }
    body = soup.body
    if body and body.get("data-density") != "expressive":
        errors.append(f"{route}: body must declare expressive density")
    if soup.find_all(style=True):
        errors.append(f"{route}: inline style attributes are not allowed")
    if route not in RESOURCE_ROUTES and (
        len(soup.select("[data-shell-header]")) != 1
        or len(soup.select("[data-shell-footer]")) != 1
    ):
        errors.append(f"{route}: shared header and footer are required")
    if route in RESOURCE_ROUTES and not soup.select_one(".cg-resource-page-flow"):
        errors.append(f"{route}: resource page flow is missing")
    for table in soup.select("table.cg-data-table, table.cg-article-table"):
        if not table.find("caption") and not table.get("aria-label"):
            errors.append(f"{route}: data table needs caption or accessible name")
        for header in table.find_all("th"):
            if not header.get("scope"):
                errors.append(f"{route}: table header needs scope")
    for control in soup.find_all(["button", "input", "select"]):
        if {"rounded-cg-card", "rounded-cg-panel"} & set(control.get("class", [])):
            errors.append(f"{route}: control uses a surface radius")
    for card in soup.select(
        ".cg-article-list-card, .cg-article-related-link, .cg-article-fact"
    ):
        if any(value.startswith("shadow-") for value in card.get("class", [])):
            errors.append(f"{route}: editorial card has a shadow")
    for node in soup.find_all(class_=True):
        classes = set(node.get("class", []))
        repeated = sorted(
            token
            for token, light_token in redundant_theme_utilities.items()
            if token in classes and light_token in classes
        )
        if repeated:
            errors.append(f"{route}: redundant theme utilities: {', '.join(repeated)}")
    for sup in soup.find_all("sup"):
        if sup.find_parent("td") is None and sup.find_parent("th") is None:
            errors.append(f"{route}: sup marker is outside a table cell")
    for faq_list in soup.select(".cg-faq-list"):
        if {"grid", "gap-3"}.issubset(set(faq_list.get("class", []))):
            errors.append(f"{route}: FAQ list must use divider rhythm, not grid gap")


def _append_shell_component_errors(route: str, soup: Any, errors: list[str]) -> None:
    """Append article and downloadable-resource shell errors."""
    if soup.select_one(".cg-article-hero") and not soup.select_one(
        ".cg-article-hero .cg-article-kicker"
    ):
        errors.append(f"{route}: ArticleShell hero lacks article kicker")
    if route not in RESOURCE_ROUTES:
        return
    for selector in (".cg-resource-body",):
        if (
            route == "downloads/digital-role-passport/role-passport.html"
            and not soup.select_one(selector)
        ):
            errors.append(f"{route}: resource shell lacks {selector}")


def check_article_structure(pages: Iterable[Path], errors: list[str]) -> None:
    """Check ArticleShell hierarchy and table/source composition for editorial pages."""
    for path in pages:
        route = _route(path)
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        if route != BLOG_ARTICLE_ROUTE:
            continue
        article_body = soup.select_one("#article-body")
        if article_body is None:
            errors.append(f"{route}: article body is missing")
            continue
        chapter_headings = article_body.find_all("h2")
        if len(chapter_headings) > 6:
            errors.append(
                f"{route}: ArticleShell has {len(chapter_headings)} content h2 headings; expected <= 6"
            )
        toc = soup.select_one(".cg-article-toc")
        toc_ids = (
            {
                str(link.get("href", ""))[1:]
                for link in toc.find_all("a")
                if link.get("href", "").startswith("#")
            }
            if toc
            else set()
        )
        for heading in chapter_headings:
            if heading.get("id") and heading["id"] not in toc_ids:
                errors.append(f"{route}: ArticleShell TOC misses #{heading['id']}")


def documentation_pages() -> list[Path]:
    """Return indexable documentation pages, excluding generated redirect aliases."""
    pages: list[Path] = []
    for path in sorted((ROOT / "docs").rglob("*.html")):
        source = path.read_text(encoding="utf-8")
        if re.search(
            r'<meta\s+[^>]*name=["\']robots["\'][^>]*content=["\'][^"\']*noindex',
            source,
            flags=re.IGNORECASE,
        ):
            continue
        pages.append(path)
    return pages


def check_documentation_shell(errors: list[str]) -> None:
    """Require the shared expressive shell on every indexable doc page."""
    for path in documentation_pages():
        route = _route(path)
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        body = soup.body
        if body is None or body.get("data-density") != "expressive":
            errors.append(
                f"{route}: documentation body must declare expressive density"
            )
        if (
            len(soup.select("[data-shell-header]")) != 1
            or len(soup.select("[data-shell-footer]")) != 1
        ):
            errors.append(
                f"{route}: documentation must use the shared header and footer"
            )
        if soup.find_all(style=True):
            errors.append(f"{route}: inline style attributes are not allowed")


def check_article_css_contract(errors: list[str]) -> None:
    """Keep ArticleShell source styles single-defined and token-based."""
    css = CSS.read_text(encoding="utf-8")
    for selector in (".cg-article-source-list", ".cg-article-related-link"):
        count = len(
            re.findall(rf"^{re.escape(selector)}\s*(?:\{{|,)", css, flags=re.MULTILINE)
        )
        if count != 1:
            errors.append(
                f"css: ArticleShell selector {selector} must have one definition"
            )


def _append_product_flow_errors(route: str, soup: Any, errors: list[str]) -> None:
    """Append product-page flow, hero action, and preview errors."""
    if route not in PRODUCT_ROUTES:
        return
    main = soup.find("main")
    if main is None:
        errors.append(f"{route}: missing main landmark")
        return
    classes = set(main.get("class", []))
    if route == "index.html" and "cg-home-flow" not in classes:
        errors.append(f"{route}: home flow contract is missing")
    if route not in {"index.html", "whitepaper.html"} and "cg-page-flow" not in classes:
        errors.append(f"{route}: page flow contract is missing")
    hero = main.find("section")
    has_action = hero and hero.find(
        "a", class_=lambda value: value and "cg-button" in value
    )
    if route != "privacy.html" and not has_action:
        errors.append(f"{route}: hero primary action must use cg-button")
    preview_exempt = {"index.html", "privacy.html", "integrations.html"}
    if route not in preview_exempt and not main.select(
        '[data-visual-kind="product-preview"]'
    ):
        errors.append(f"{route}: hero ProductPreview is missing")


def _append_home_flow_errors(route: str, soup: Any, errors: list[str]) -> None:
    """Append top-level homepage information-architecture errors."""
    if route != "index.html":
        return
    h2_count = len(soup.select("main > section h2"))
    if h2_count > HOME_TOP_LEVEL_HEADING_LIMIT:
        errors.append(
            f"{route}: top-level section headings={h2_count}, "
            f"expected <= {HOME_TOP_LEVEL_HEADING_LIMIT}"
        )
    if not soup.select_one("main .cg-process-track"):
        errors.append(f"{route}: main process must use cg-process-track")
    if soup.select_one("main .business-steps"):
        errors.append(f"{route}: legacy business-steps process is still present")


def check_component_contracts(pages: Iterable[Path], errors: list[str]) -> None:
    """Append errors for components that violate the shared visual contract."""
    for path in pages:
        route = _route(path)
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        _append_control_and_card_errors(route, soup, errors)
        _append_shell_component_errors(route, soup, errors)
        _append_product_flow_errors(route, soup, errors)
        _append_home_flow_errors(route, soup, errors)


def check_diagram_tokens(pages: Iterable[Path], errors: list[str]) -> None:
    """Append errors when diagrams bypass canonical design tokens."""
    css = CSS.read_text(encoding="utf-8")
    required_css = (
        "--cg-diagram-node-active",
        "--cg-diagram-text-active",
        "--cg-diagram-text-active-secondary",
        "--cg-diagram-edge",
        "--cg-diagram-edge-active",
        ".cg-diagram-text",
        ".cg-diagram-edge-active",
    )
    for fragment in required_css:
        if fragment not in css:
            errors.append(f"css: missing diagram contract {fragment}")
    diagram_variables = {
        "--cg-diagram-node-active",
        "--cg-diagram-text-active",
        "--cg-diagram-text-active-secondary",
        "--cg-diagram-edge",
        "--cg-diagram-edge-active",
        "--cg-diagram-text",
        "--cg-diagram-text-secondary",
        "--cg-diagram-border",
    }
    defined = set(re.findall(r"(--cg-diagram-[a-z0-9-]+)\s*:", css))
    used = set(re.findall(r"var\((--cg-diagram-[a-z0-9-]+)", css))
    for token in sorted((used & diagram_variables) - defined):
        errors.append(f"css: undefined diagram variable {token}")
    raw = re.compile(r"(?:fill|stroke)-(?:blue|slate)-|#[0-9a-fA-F]{6}")
    text_classes = {
        "cg-diagram-text",
        "cg-diagram-title",
        "cg-diagram-body",
        "cg-diagram-title-active",
        "cg-diagram-body-active",
    }
    for path in pages:
        route = _route(path)
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        for figure in soup.select("[data-product-diagram]"):
            svg = figure.find("svg")
            if svg is None or not svg.find("title") or not svg.find("desc"):
                errors.append(f"{route}: diagram lacks title/desc")
            viewer = figure.select_one("[data-diagram-viewer]")
            if (
                viewer is None
                or not viewer.get("data-diagram-id")
                or not soup.find(id=viewer.get("data-diagram-id"))
            ):
                errors.append(f"{route}: wide diagram lacks fullscreen viewer")
            if not figure.select_one(
                ".cg-diagram-scroll, .overflow-x-auto, .cg-diagram-mobile"
            ):
                errors.append(f"{route}: wide diagram lacks mobile scroll strategy")
            if svg is None:
                continue
            active_nodes = svg.select("rect.cg-diagram-node-active")
            for node in active_nodes:
                group = node.parent
                active_text = (
                    group.select(
                        "text.cg-diagram-title-active, text.cg-diagram-body-active"
                    )
                    if group
                    else []
                )
                if not active_text:
                    errors.append(f"{route}: active diagram node has no active text")
            for text_node in svg.find_all("text"):
                if not text_classes.intersection(text_node.get("class", [])):
                    errors.append(f"{route}: unclassified diagram text")
        for svg in soup.find_all("svg"):
            for element in svg.find_all(True):
                attributes = " ".join(
                    str(element.get(name, ""))
                    for name in ("class", "fill", "stroke", "style")
                )
                if raw.search(attributes):
                    errors.append(f"{route}: raw diagram color declaration")
                    break


def check_public_shell(errors: list[str]) -> None:
    """Append errors when shared public navigation or shell behavior drifts."""
    header = (ROOT / "templates" / "header.html").read_text(encoding="utf-8")
    javascript = JS.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    required = (
        'role="dialog"',
        'aria-modal="true"',
        'aria-labelledby="mobile-menu-title"',
    )
    for fragment in required:
        if fragment not in header:
            errors.append(f"header: missing drawer contract {fragment}")
    for fragment in (
        "main.inert",
        "footer.inert",
        "event.key !== 'Tab'",
        "focusFirstItem",
    ):
        if fragment not in javascript:
            errors.append(f"js: missing drawer behavior {fragment}")
    if '.cg-nav-link[aria-current="page"]' not in css:
        errors.append("css: aria-current page has no visual selected state")


def check_release_surface(pages: Iterable[Path], errors: list[str]) -> None:
    """Keep the published surface and its machine-readable index fail-closed."""
    for name in ("robots.txt", "sitemap.xml", "llms.txt"):
        if not (ROOT / name).is_file():
            errors.append(f"release: missing {name}")

    sitemap = ROOT / "sitemap.xml"
    if sitemap.is_file():
        try:
            root = ET.fromstring(sitemap.read_text(encoding="utf-8"))
            locations = [
                element.text for element in root.iter() if element.tag.endswith("}loc")
            ]
            if len(locations) != len(set(locations)):
                errors.append("release: sitemap contains duplicate URLs")
            for path in pages:
                source = path.read_text(encoding="utf-8")
                if re.search(
                    r'<meta\s+[^>]*name=["\']robots["\'][^>]*content=["\'][^"\']*noindex',
                    source,
                    flags=re.IGNORECASE,
                ):
                    continue
                relative = path.relative_to(ROOT).as_posix()
                public_path = (
                    relative[: -len("index.html")]
                    if relative.endswith("index.html")
                    else relative
                )
                expected = (
                    f"https://codegraph.ru/{public_path}"
                    if public_path
                    else "https://codegraph.ru/"
                )
                if expected not in locations:
                    errors.append(f"release: sitemap missing indexable {relative}")
        except ET.ParseError as error:
            errors.append(f"release: invalid sitemap.xml: {error}")

    llms = ROOT / "llms.txt"
    if llms.is_file():
        text = llms.read_text(encoding="utf-8")
        required_routes = (
            "security.html",
            "compliance.html",
            "productivity.html",
            "platform-operations.html",
            "business-efficiency.html",
            "cpg.html",
            "ai-engineering.html",
            "downloads/ai-native-pdlc-sdlc-playbook/",
            "downloads/digital-role-passport/",
            "downloads/digital-role-passport/role-passport.html",
        )
        for route in required_routes:
            canonical = f"https://codegraph.ru/{route}"
            if canonical not in text:
                errors.append(f"release: llms.txt missing canonical {canonical}")

    for path in pages:
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        for link in soup.select("a[href], link[href], img[src], script[src]"):
            attribute = "href" if link.has_attr("href") else "src"
            value = str(link.get(attribute, "")).strip()
            if not value or value.startswith(
                (
                    "#",
                    "//",
                    "http://",
                    "https://",
                    "mailto:",
                    "tel:",
                    "data:",
                    "javascript:",
                )
            ):
                continue
            parsed = urlsplit(value)
            target_value = unquote(parsed.path)
            target = (
                (ROOT / target_value.lstrip("/"))
                if target_value.startswith("/")
                else (path.parent / target_value)
            )
            target = target.resolve()
            try:
                target.relative_to(ROOT.resolve())
            except ValueError:
                errors.append(
                    f"{_route(path)}: local link escapes landing root: {value}"
                )
                continue
            if target.is_dir():
                target /= "index.html"
            if not target.is_file():
                errors.append(f"{_route(path)}: local link target missing: {value}")


def main() -> int:
    """Run the selected design-system contract checks."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        choices=(
            "all",
            "design-tokens-parity",
            "component-contracts",
            "diagram-tokens",
            "public-shell",
        ),
        default="all",
    )
    args = parser.parse_args()
    errors: list[str] = []
    pages = public_pages()
    if args.check in {"all", "design-tokens-parity"}:
        check_design_tokens_parity(errors)
    if args.check in {"all", "component-contracts"}:
        check_component_contracts(pages, errors)
        check_article_structure(pages, errors)
        check_article_css_contract(errors)
    if args.check in {"all", "component-contracts"}:
        check_metadata_contract(pages, errors)
    if args.check in {"all", "diagram-tokens"}:
        check_diagram_tokens(pages, errors)
    if args.check in {"all", "public-shell"}:
        check_public_shell(errors)
        check_documentation_shell(errors)
    if args.check == "all":
        check_release_surface(pages, errors)
    if errors:
        print("\n".join(f"FAIL: {error}" for error in errors))
        return 1
    print(f"Design System contract passed: {len(pages)} public HTML pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
