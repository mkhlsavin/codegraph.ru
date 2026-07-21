#!/usr/bin/env python3
"""Fail closed until the public domain serves the expected static release."""

from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


EXPECTED_TITLE = "CodeGraph — связь инициативы, кода и решения о выпуске"
EXPECTED_H1 = "Свяжите продуктовую инициативу с кодом, проверками и решением о выпуске"
EXPECTED_RELEASE = "landing-audit-20260722-v2"
FORBIDDEN_TEXT = ("21 сценарий", "0,83")
HASH_ROUTES = (
    "index.html",
    "whitepaper.html",
    "product-delivery.html",
    "sitemap.xml",
)


class HomeContractParser(HTMLParser):
    """Extract the public homepage title, first H1, and release marker."""

    def __init__(self) -> None:
        """Initialize bounded homepage extraction state."""
        super().__init__()
        self.title = ""
        self.h1 = ""
        self.release = ""
        self._capture = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Capture title, first H1, and the release metadata value."""
        attributes = dict(attrs)
        if tag in {"title", "h1"} and (tag != "h1" or not self.h1):
            self._capture = tag
        if tag == "meta" and attributes.get("name") == "cg:release":
            self.release = attributes.get("content") or ""

    def handle_endtag(self, tag: str) -> None:
        """Stop text capture at the matching closing element."""
        if tag == self._capture:
            self._capture = ""

    def handle_data(self, data: str) -> None:
        """Append normalized text for the active title or H1 element."""
        if self._capture == "title":
            self.title += data
        elif self._capture == "h1":
            self.h1 += data


def _normalized_sha256(payload: bytes) -> str:
    """Hash a static payload after normalizing transport line endings."""
    return hashlib.sha256(payload.replace(b"\r\n", b"\n")).hexdigest()


def _normalized_text(value: str) -> str:
    """Collapse HTML whitespace, including non-breaking spaces, for semantic checks."""
    return " ".join(value.split())


def _fetch(base_url: str, route: str, release: str) -> bytes:
    """Fetch one public route with cache bypass headers and query marker."""
    url = urljoin(base_url.rstrip("/") + "/", route)
    separator = "&" if "?" in url else "?"
    request = Request(
        f"{url}{separator}release={release}&ts={time.time_ns()}",
        headers={"Cache-Control": "no-cache", "Pragma": "no-cache", "User-Agent": "CodeGraphReleaseGate/1.0"},
    )
    with urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"{route}: HTTP {response.status}")
        return response.read()


def verify_once(base_url: str, root: Path, release: str) -> dict[str, object]:
    """Verify semantics, required routes, forbidden claims, and artifact hashes once."""
    remote = {route: _fetch(base_url, route, release) for route in (*HASH_ROUTES, "evidence.html", "integrations.html")}
    parser = HomeContractParser()
    homepage = remote["index.html"].decode("utf-8")
    root_parser = HomeContractParser()
    root_homepage = _fetch(base_url, "", release).decode("utf-8")
    parser.feed(homepage)
    root_parser.feed(root_homepage)
    failures: list[str] = []
    if _normalized_text(parser.title) != EXPECTED_TITLE:
        failures.append(f"title={parser.title.strip()!r}")
    if _normalized_text(parser.h1) != EXPECTED_H1:
        failures.append(f"h1={parser.h1.strip()!r}")
    if parser.release.strip() != release:
        failures.append(f"release={parser.release.strip()!r}")
    if (
        _normalized_text(root_parser.title) != _normalized_text(parser.title)
        or _normalized_text(root_parser.h1) != _normalized_text(parser.h1)
        or root_parser.release.strip() != parser.release.strip()
    ):
        failures.append("root/index.html semantic mismatch")
    if _normalized_sha256(root_homepage.encode("utf-8")) != _normalized_sha256(homepage.encode("utf-8")):
        failures.append("root/index.html content hash mismatch")
    for text in FORBIDDEN_TEXT:
        if text.casefold() in homepage.casefold():
            failures.append(f"forbidden={text!r}")
    hashes: dict[str, dict[str, str]] = {}
    for route in HASH_ROUTES:
        local = (root / route).read_bytes()
        local_hash = _normalized_sha256(local)
        remote_hash = _normalized_sha256(remote[route])
        hashes[route] = {"local": local_hash, "public": remote_hash}
        if local_hash != remote_hash:
            failures.append(f"hash mismatch: {route}")
    return {"ok": not failures, "failures": failures, "hashes": hashes, "release": parser.release.strip()}


def main() -> int:
    """Poll the public domain until the exact checked-out artifact is available."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://codegraph.ru/")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--release", default=EXPECTED_RELEASE)
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--interval", type=float, default=20.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result: dict[str, object] = {"ok": False, "failures": ["not run"]}
    for attempt in range(1, args.attempts + 1):
        try:
            result = verify_once(args.base_url, args.root.resolve(), args.release)
        except (HTTPError, URLError, TimeoutError, RuntimeError, UnicodeDecodeError) as error:
            result = {"ok": False, "failures": [f"{type(error).__name__}: {error}"]}
        result["attempt"] = attempt
        if result["ok"]:
            break
        if attempt < args.attempts:
            time.sleep(args.interval)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    print(payload)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
