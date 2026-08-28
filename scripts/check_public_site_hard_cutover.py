#!/usr/bin/env python3
"""Fail closed on retired classes and inline styles in the public landing repo."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_EMAIL = "hello@codegraph.ru"
CODEGRAPH_EMAIL = re.compile(
    r"[A-Za-z0-9._%+][A-Za-z0-9._%+-]*@codegraph\.(?:ru|local)", re.IGNORECASE
)
HTML_INLINE_STYLE = re.compile(r"<style\b|<[A-Za-z][^<>]*\sstyle\s*=", re.IGNORECASE)
CLASS_ATTRIBUTE = re.compile(r'class=["\']([^"\']*)["\']', re.IGNORECASE)
RETIRED_CLASSES = {
    "section",
    "container",
    "section-header",
    "section-eyebrow",
    "solutions-grid",
    "solution-card",
    "faq-list",
    "faq-list-narrow",
    "faq-item",
    "faq-question",
    "faq-answer",
    "faq-icon",
    "logo-optical-offset",
}
RETIRED_SELECTOR = re.compile(
    r"(?m)^\s*\.(?:container|logo-optical-offset|docs-shell-header|nav-list|nav-link)"
    r"(?:[\s:{.]|$)"
)
OLD_STYLESHEET = re.compile(r"(?:^|[/\\])styles(?:\.min)?\.css(?:[?#\"']|$)")


def main() -> int:
    """Validate every landing HTML/CSS projection and CodeGraph contact address."""
    errors: list[str] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or ".git" in path.parts or "node_modules" in path.parts:
            continue
        relative = path.relative_to(ROOT).as_posix()
        if path.suffix.casefold() not in {
            ".html",
            ".css",
            ".js",
            ".json",
            ".md",
            ".py",
            ".yaml",
            ".yml",
        }:
            continue
        source = path.read_text(encoding="utf-8")
        if CODEGRAPH_EMAIL.search(source) and any(
            address.casefold() != CANONICAL_EMAIL
            for address in CODEGRAPH_EMAIL.findall(source)
        ):
            errors.extend(
                f"{relative}: non-canonical CodeGraph email {address}"
                for address in CODEGRAPH_EMAIL.findall(source)
                if address.casefold() != CANONICAL_EMAIL
            )
        if path.suffix.casefold() == ".html":
            if HTML_INLINE_STYLE.search(source):
                errors.append(f"{relative}: embedded or inline HTML style")
            for attributes in CLASS_ATTRIBUTE.findall(source):
                errors.extend(
                    f"{relative}: retired landing class {name}"
                    for name in sorted(RETIRED_CLASSES.intersection(attributes.split()))
                )
        if path.suffix.casefold() == ".css":
            if RETIRED_SELECTOR.search(source):
                errors.append(f"{relative}: retired landing selector")
            if OLD_STYLESHEET.search(source):
                errors.append(f"{relative}: retired stylesheet reference")
    if errors:
        print("Public landing hard-cutover violations:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in sorted(set(errors))), file=sys.stderr)
        return 1
    print(
        "Public landing hard cutover passed: HTML, CSS and CodeGraph email contracts checked."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
