#!/usr/bin/env python3
"""Fail-closed checks for the public CodeGraph design-system contract."""

from __future__ import annotations

import argparse
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
        if route in PRODUCT_ROUTES:
            main = soup.find("main")
            if main is None:
                errors.append(f"{route}: missing main landmark")
                continue
            hero = main.find("section")
            if hero is None or not hero.find("a", class_=lambda value: value and "cg-button" in value):
                errors.append(f"{route}: hero primary action must use cg-button")
            if route != "index.html" and not main.select('[data-visual-kind="product-preview"]'):
                errors.append(f"{route}: hero ProductPreview is missing")
        if route == "index.html":
            h2_count = len(soup.select("main > section h2"))
            if h2_count > 8:
                errors.append(f"{route}: top-level section headings={h2_count}, expected <= 8")


def check_diagram_tokens(pages: Iterable[Path], errors: list[str]) -> None:
    raw = re.compile(r"(?:fill|stroke)-(?:blue|slate)-|#[0-9a-fA-F]{6}")
    for path in pages:
        route = _route(path)
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        for figure in soup.select("[data-product-diagram]"):
            svg = figure.find("svg")
            if svg is None or not svg.find("title") or not svg.find("desc"):
                errors.append(f"{route}: diagram lacks title/desc")
            if not figure.select_one(".cg-diagram-mobile-summary") and not figure.select_one("[data-screen-viewer]"):
                errors.append(f"{route}: wide diagram lacks mobile strategy")
        for svg in soup.find_all("svg"):
            if raw.search(" ".join(svg.get("class", []))):
                errors.append(f"{route}: raw diagram color class")


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
