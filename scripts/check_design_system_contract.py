#!/usr/bin/env python3
"""Fail-closed checks for the public CodeGraph design-system contract."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
from typing import Iterable
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


def public_pages() -> list[Path]:
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
    if "@deprecated" not in source:
        errors.append("css: legacy token layer has no deprecation marker")


def check_metadata_contract(pages: Iterable[Path], errors: list[str]) -> None:
    """Require page-specific metadata and parity across social/schema surfaces."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if not manifest.get("metadata_source") or not manifest.get("metadata_fields"):
        errors.append("manifest: metadata source and fields are required")
    titles: list[tuple[str, str]] = []
    descriptions: list[tuple[str, str]] = []
    normalize = lambda value: re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()
    for path in pages:
        route = _route(path)
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        description_tag = soup.select_one('meta[name="description"]')
        description = description_tag.get("content", "").strip() if description_tag else ""
        og_title = soup.select_one('meta[property="og:title"]')
        og_description = soup.select_one('meta[property="og:description"]')
        twitter_title = soup.select_one('meta[name="twitter:title"]')
        twitter_description = soup.select_one('meta[name="twitter:description"]')
        webpage = []
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                payload = json.loads(script.string or script.get_text())
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("@type") == "WebPage":
                webpage.append(payload)
        if not title or not description:
            errors.append(f"{route}: title and description are required")
        if og_title is None or normalize(og_title.get("content", "")) != normalize(title):
            errors.append(f"{route}: og:title must equal title")
        if og_description is None or normalize(og_description.get("content", "")) != normalize(description):
            errors.append(f"{route}: og:description must equal description")
        if twitter_title is None or normalize(twitter_title.get("content", "")) != normalize(title):
            errors.append(f"{route}: twitter:title must equal title")
        if twitter_description is None or normalize(twitter_description.get("content", "")) != normalize(description):
            errors.append(f"{route}: twitter:description must equal description")
        if len(webpage) != 1 or normalize(str(webpage[0].get("name", ""))) != normalize(title) or normalize(str(webpage[0].get("description", ""))) != normalize(description):
            errors.append(f"{route}: WebPage metadata must match title and description")
        titles.append((title, route))
        descriptions.append((description, route))
    for value, count in Counter(normalize(item[0]) for item in titles).items():
        if value and count > 1:
            routes = ", ".join(route for title, route in titles if normalize(title) == value)
            errors.append(f"title duplicated on {routes}")
    for value, count in Counter(normalize(item[0]) for item in descriptions).items():
        if value and count > 1:
            routes = ", ".join(route for description, route in descriptions if normalize(description) == value)
            errors.append(f"description duplicated on {routes}")


def check_component_contracts(pages: Iterable[Path], errors: list[str]) -> None:
    redundant_theme_utilities = {
        "dark:bg-cg-surface": "bg-cg-surface",
        "dark:bg-cg-surface-subtle": "bg-cg-surface-subtle",
        "dark:border-cg-border": "border-cg-border",
        "dark:text-cg-ink": "text-cg-ink",
        "dark:text-cg-muted": "text-cg-muted",
        "dark:hover:bg-cg-surface-subtle": "hover:bg-cg-surface-subtle",
        "dark:hover:text-cg-ink": "hover:text-cg-ink",
    }
    for path in pages:
        route = _route(path)
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        body = soup.body
        if body and body.get("data-density") != "expressive":
            errors.append(f"{route}: body must declare expressive density")
        for control in soup.find_all(["button", "input", "select"]):
            classes = set(control.get("class", []))
            if {"rounded-cg-card", "rounded-cg-panel"} & classes:
                errors.append(f"{route}: control uses a surface radius")
        for card in soup.select(".cg-article-list-card, .cg-article-related-link, .cg-article-fact"):
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
            faq_classes = set(faq_list.get("class", []))
            if {"grid", "gap-3"}.issubset(faq_classes):
                errors.append(f"{route}: FAQ list must use divider rhythm, not grid gap")
        if soup.select_one(".cg-article-hero") and not soup.select_one(
            ".cg-article-hero .cg-article-kicker"
        ):
            errors.append(f"{route}: ArticleShell hero lacks article kicker")
        if route == "downloads/digital-role-passport/role-passport.html":
            for selector in (".cg-resource-brand", ".cg-resource-intro", ".cg-resource-body"):
                if not soup.select_one(f".cg-resource-shell {selector}"):
                    errors.append(f"{route}: resource shell lacks {selector}")
        if route in PRODUCT_ROUTES:
            main = soup.find("main")
            if main is None:
                errors.append(f"{route}: missing main landmark")
                continue
            classes = set(main.get("class", []))
            if route == "index.html" and "cg-home-flow" not in classes:
                errors.append(f"{route}: home flow contract is missing")
            if route not in {"index.html", "whitepaper.html"} and "cg-page-flow" not in classes:
                errors.append(f"{route}: page flow contract is missing")
            hero = main.find("section")
            if route != "privacy.html" and (
                hero is None or not hero.find("a", class_=lambda value: value and "cg-button" in value)
            ):
                errors.append(f"{route}: hero primary action must use cg-button")
            if route not in {"index.html", "privacy.html"} and not main.select(
                '[data-visual-kind="product-preview"]'
            ):
                errors.append(f"{route}: hero ProductPreview is missing")
        if route == "index.html":
            h2_count = len(soup.select("main > section h2"))
            if h2_count > 8:
                errors.append(f"{route}: top-level section headings={h2_count}, expected <= 8")
            if not soup.select_one("main .cg-process-track"):
                errors.append(f"{route}: main process must use cg-process-track")
            if soup.select_one("main .business-steps"):
                errors.append(f"{route}: legacy business-steps process is still present")


def check_diagram_tokens(pages: Iterable[Path], errors: list[str]) -> None:
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
            if viewer is None or not viewer.get("data-diagram-id") or not soup.find(id=viewer.get("data-diagram-id")):
                errors.append(f"{route}: wide diagram lacks fullscreen viewer")
            if not figure.select_one(".cg-diagram-mobile-summary, .cg-diagram-mobile"):
                errors.append(f"{route}: wide diagram lacks mobile strategy")
            if svg is None:
                continue
            active_nodes = svg.select("rect.cg-diagram-node-active")
            for node in active_nodes:
                group = node.parent
                active_text = group.select("text.cg-diagram-title-active, text.cg-diagram-body-active") if group else []
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
    for fragment in ("main.inert", "footer.inert", "event.key !== 'Tab'", "focusFirstItem"):
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
            locations = [element.text for element in root.iter() if element.tag.endswith("}loc")]
            if len(locations) != len(set(locations)):
                errors.append("release: sitemap contains duplicate URLs")
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
            if not value or value.startswith(("#", "//", "http://", "https://", "mailto:", "tel:", "data:", "javascript:")):
                continue
            parsed = urlsplit(value)
            target_value = unquote(parsed.path)
            target = (ROOT / target_value.lstrip("/")) if target_value.startswith("/") else (path.parent / target_value)
            target = target.resolve()
            try:
                target.relative_to(ROOT.resolve())
            except ValueError:
                errors.append(f"{_route(path)}: local link escapes landing root: {value}")
                continue
            if target.is_dir():
                target /= "index.html"
            if not target.is_file():
                errors.append(f"{_route(path)}: local link target missing: {value}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", choices=("all", "design-tokens-parity", "component-contracts", "diagram-tokens", "public-shell"), default="all")
    args = parser.parse_args()
    errors: list[str] = []
    pages = public_pages()
    if args.check in {"all", "design-tokens-parity"}:
        check_design_tokens_parity(errors)
    if args.check in {"all", "component-contracts"}:
        check_component_contracts(pages, errors)
    if args.check in {"all", "component-contracts"}:
        check_metadata_contract(pages, errors)
    if args.check in {"all", "diagram-tokens"}:
        check_diagram_tokens(pages, errors)
    if args.check in {"all", "public-shell"}:
        check_public_shell(errors)
    if args.check == "all":
        check_release_surface(pages, errors)
    if errors:
        print("\n".join(f"FAIL: {error}" for error in errors))
        return 1
    print(f"Design System contract passed: {len(pages)} public HTML pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
