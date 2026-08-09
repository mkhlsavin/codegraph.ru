#!/usr/bin/env python3
"""Validate freshness metadata across the public landing projection."""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ISO_DATE = re.compile(r'"dateModified"\s*:\s*"([^"]+)"')
VISIBLE_DATE = re.compile(r"Обновлено:\s*([^<]+)")
LASTMOD = re.compile(r"<lastmod>([^<]+)</lastmod>")
RU_MONTHS = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


def visible_date(value: str) -> str:
    """Render an ISO date as the canonical Russian public date."""
    parsed = date.fromisoformat(value)
    return f"{parsed.day} {RU_MONTHS[parsed.month - 1]} {parsed.year}"


def main() -> int:
    """Validate public release and sitemap freshness against canonical index metadata."""
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    iso_matches = ISO_DATE.findall(index)
    visible_matches = [match.strip() for match in VISIBLE_DATE.findall(index)]
    if not iso_matches or not visible_matches:
        print("index.html must contain dateModified and a visible freshness label")
        return 1

    expected_iso = iso_matches[0]
    expected_visible = visible_date(expected_iso)
    errors: list[str] = []

    if visible_matches[0] != expected_visible:
        errors.append(
            f"index.html: visible date {visible_matches[0]!r} != {expected_visible!r}"
        )

    for path in ROOT.rglob("*.html"):
        relative = path.relative_to(ROOT)
        if (
            "docs" in relative.parts
            or "templates" in relative.parts
            or path.name.startswith("yandex_")
        ):
            continue
        text = path.read_text(encoding="utf-8")
        for value in ISO_DATE.findall(text):
            if value != expected_iso:
                errors.append(f"{relative}: dateModified={value}")
        for value in (match.strip() for match in VISIBLE_DATE.findall(text)):
            if value != expected_visible:
                errors.append(f"{relative}: visible freshness={value}")

    cta = (ROOT / "templates" / "sections" / "cta.html").read_text(encoding="utf-8")
    if "{{public_visible_date}}" not in cta and expected_visible not in cta:
        errors.append("templates/sections/cta.html: freshness date is stale")

    sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    for value in LASTMOD.findall(sitemap):
        if value != expected_iso:
            errors.append(f"sitemap.xml: lastmod={value}")

    if errors:
        print("Freshness validation failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1

    print(f"Freshness validation passed: {expected_iso} ({expected_visible})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
