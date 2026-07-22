#!/usr/bin/env python3
"""Fail closed until the public domain serves the expected static release."""

from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import Request, urlopen


EXPECTED_TITLE = "CodeGraph — связь инициативы, кода и решения о выпуске"
EXPECTED_H1 = "Свяжите продуктовую инициативу с кодом, проверками и решением о выпуске"
EXPECTED_RELEASE = "landing-audit-20260722-v4"
FORBIDDEN_TEXT = ("21 сценарий", "0,83")
EXTRA_PUBLIC_ROUTES = (
    "research/tochnost-otvetov-i-skorost-razbora.html",
    "downloads/digital-role-passport/index.html",
    "downloads/digital-role-passport/role-passport.html",
)
REQUIRED_PUBLIC_ASSETS = (
    "css/tailwind.min.css",
    "downloads/digital-role-passport/CODEGRAPH_DIGITAL_ROLE_PASSPORT.pdf",
)
ROBOTS_POLICY = {
    EXTRA_PUBLIC_ROUTES[0]: "noindex, nofollow",
    EXTRA_PUBLIC_ROUTES[1]: "noindex, follow",
    EXTRA_PUBLIC_ROUTES[2]: "noindex, follow",
}


class HomeContractParser(HTMLParser):
    """Extract the public homepage title, first H1, and release marker."""

    def __init__(self) -> None:
        """Initialize bounded homepage extraction state."""
        super().__init__()
        self.title = ""
        self.h1 = ""
        self.release = ""
        self.canonical = ""
        self.robots = ""
        self.stylesheet = ""
        self.style_preload = ""
        self._capture = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Capture title, first H1, and the release metadata value."""
        attributes = dict(attrs)
        if tag in {"title", "h1"} and (tag != "h1" or not self.h1):
            self._capture = tag
        if tag == "meta" and attributes.get("name") == "cg:release":
            self.release = attributes.get("content") or ""
        if tag == "meta" and attributes.get("name", "").casefold() == "robots":
            self.robots = attributes.get("content") or ""
        if tag == "link" and attributes.get("rel", "").casefold() == "canonical":
            self.canonical = attributes.get("href") or ""
        if tag == "link" and attributes.get("rel", "").casefold() == "stylesheet":
            self.stylesheet = attributes.get("href") or ""
        if (
            tag == "link"
            and attributes.get("rel", "").casefold() == "preload"
            and attributes.get("as", "").casefold() == "style"
        ):
            self.style_preload = attributes.get("href") or ""

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


def _routes_from_sitemap(payload: bytes) -> tuple[str, ...]:
    """Extract HTML routes from the local sitemap without including documentation."""
    text = payload.decode("utf-8")
    routes = {
        unquote(urlsplit(value).path.lstrip("/"))
        for value in re.findall(r"<loc>\s*(https://codegraph\.ru/[^<]+)\s*</loc>", text)
    }
    routes.discard("")
    routes.update(EXTRA_PUBLIC_ROUTES)
    routes.add("index.html")
    return tuple(
        sorted(
            route
            for route in routes
            if route.endswith(".html") and not route.startswith("docs/")
        )
    )


def _expected_canonical(route: str) -> str:
    """Return the exact canonical expected for one published HTML route."""
    return f"https://codegraph.ru/{route}" if route != "index.html" else "https://codegraph.ru/"


def _normalized_robots(value: str) -> str:
    """Normalize a robots content value for policy comparison."""
    return ", ".join(part.strip().casefold() for part in value.split(",") if part.strip())


def verify_once(base_url: str, root: Path, release: str) -> dict[str, object]:
    """Verify semantics, required routes, forbidden claims, and artifact hashes once."""
    local_sitemap = (root / "sitemap.xml").read_bytes()
    sitemap = _fetch(base_url, "sitemap.xml", release)
    routes = _routes_from_sitemap(local_sitemap)
    remote = {route: _fetch(base_url, route, release) for route in routes}
    remote["sitemap.xml"] = sitemap
    remote_assets = {
        route: _fetch(base_url, route, release) for route in REQUIRED_PUBLIC_ASSETS
    }
    homepage = remote["index.html"].decode("utf-8")
    root_homepage = _fetch(base_url, "", release).decode("utf-8")
    failures: list[str] = []
    route_contracts: dict[str, dict[str, str]] = {}
    for route in routes:
        public_parser = HomeContractParser()
        public_parser.feed(remote[route].decode("utf-8"))
        local_path = root / route
        if not local_path.is_file():
            failures.append(f"missing local route: {route}")
            continue
        local_parser = HomeContractParser()
        local_parser.feed(local_path.read_text(encoding="utf-8"))
        expected_canonical = _expected_canonical(route)
        route_contracts[route] = {
            "canonical": public_parser.canonical,
            "release": public_parser.release.strip(),
            "robots": _normalized_robots(public_parser.robots),
        }
        for label, actual, expected in (
            ("canonical", public_parser.canonical, expected_canonical),
            ("release", public_parser.release.strip(), release),
            ("local canonical", local_parser.canonical, expected_canonical),
            ("local release", local_parser.release.strip(), release),
        ):
            if actual != expected:
                failures.append(f"{route}: {label}={actual!r}, expected={expected!r}")
        if not public_parser.title.strip() or not public_parser.h1.strip():
            failures.append(f"{route}: missing title or H1")
        if _normalized_text(public_parser.title) != _normalized_text(local_parser.title):
            failures.append(f"{route}: title differs from local")
        if _normalized_text(public_parser.h1) != _normalized_text(local_parser.h1):
            failures.append(f"{route}: H1 differs from local")
        if public_parser.stylesheet != local_parser.stylesheet:
            failures.append(f"{route}: stylesheet link differs from local")
        if public_parser.style_preload != local_parser.style_preload:
            failures.append(f"{route}: stylesheet preload differs from local")
        expected_robots = ROBOTS_POLICY.get(route, "")
        if _normalized_robots(public_parser.robots) != expected_robots:
            failures.append(f"{route}: robots={public_parser.robots!r}, expected={expected_robots!r}")

    parser = HomeContractParser()
    root_parser = HomeContractParser()
    parser.feed(homepage)
    root_parser.feed(root_homepage)
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
    for route in (*routes, "sitemap.xml"):
        local = (root / route).read_bytes()
        local_hash = _normalized_sha256(local)
        remote_hash = _normalized_sha256(remote[route])
        hashes[route] = {"local": local_hash, "public": remote_hash}
        if local_hash != remote_hash:
            failures.append(f"hash mismatch: {route}")
    asset_hashes: dict[str, dict[str, str]] = {}
    for route in REQUIRED_PUBLIC_ASSETS:
        local_path = root / route
        if not local_path.is_file():
            failures.append(f"missing local asset: {route}")
            continue
        local_hash = _normalized_sha256(local_path.read_bytes())
        remote_hash = _normalized_sha256(remote_assets[route])
        asset_hashes[route] = {"local": local_hash, "public": remote_hash}
        if local_hash != remote_hash:
            failures.append(f"hash mismatch: {route}")
    return {
        "ok": not failures,
        "failures": failures,
        "hashes": hashes,
        "routes": list(routes),
        "release": parser.release.strip(),
        "route_contracts": route_contracts,
        "assets": asset_hashes,
    }


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
