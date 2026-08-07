#!/usr/bin/env python3
"""Fail closed until the public domain serves the expected static release."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import Request, urlopen
from scripts.landing_content import SITE_CONTENT


EXPECTED_TITLE = SITE_CONTENT["canonical_seo_title"]
EXPECTED_H1 = SITE_CONTENT["home_h1"]
EXPECTED_RELEASE = "landing-audit-20260722-v5"
FORBIDDEN_TEXT = ("21 сценарий", "0,83")
EXTRA_PUBLIC_ROUTES = (
    "research/tochnost-otvetov-i-skorost-razbora.html",
    "downloads/digital-role-passport/index.html",
    "downloads/digital-role-passport/role-passport.html",
)
DOC_PUBLIC_ROUTES = (
    "docs/ru/index.html",
    "docs/en/index.html",
    "docs/ru/enterprise/index.html",
    "docs/ru/enterprise/GOCPG_VS_JOERN_ANALYSIS.html",
    "docs/ru/getting-started/QUICK_START.html",
    "docs/en/api/REST_API.html",
)
REQUIRED_PUBLIC_ASSETS = (
    "css/tailwind.min.css",
    "js/main.min.js",
    "docs/ru/search-index.json",
    "docs/en/search-index.json",
    "downloads/digital-role-passport/CODEGRAPH_DIGITAL_ROLE_PASSPORT.pdf",
)
PREVIOUS_DOC_CSS_HASHES = ("4adb3bb2edfa", "fd24c80f711f")
DOC_BUILD_COMMIT_SEMANTICS = (
    "cg:build-commit is the source checkout commit used to generate the HTML; "
    "the exact local/public HTML hashes certify the published release artifact."
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


class DocsContractParser(HTMLParser):
    """Extract the static shell and provenance contract from a docs page."""

    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, str] = {}
        self.stylesheets: list[str] = []
        self.scripts: list[str] = []
        self.text: list[str] = []
        self.classes: set[str] = set()
        self.has_header = False
        self.has_footer = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        self.classes.update((attributes.get("class") or "").split())
        self.has_header = self.has_header or tag == "header"
        self.has_footer = self.has_footer or tag == "footer"
        if tag == "meta" and attributes.get("name", "").startswith("cg:"):
            self.meta[attributes["name"]] = attributes.get("content") or ""
        if tag == "link" and attributes.get("rel", "").casefold() == "stylesheet":
            self.stylesheets.append(attributes.get("href") or "")
        if tag == "script" and attributes.get("src"):
            self.scripts.append(attributes["src"] or "")

    def handle_data(self, data: str) -> None:
        self.text.append(data)

    @property
    def visible_text(self) -> str:
        """Return normalized text for language and stale-shell checks."""
        return _normalized_text(" ".join(self.text))


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


def _fetch_plain(base_url: str, route: str) -> tuple[bytes, dict[str, str]]:
    """Fetch an ordinary URL without cache-bypass parameters and retain headers."""
    url = urljoin(base_url.rstrip("/") + "/", route)
    request = Request(url, headers={"User-Agent": "CodeGraphReleaseGate/1.0"})
    with urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"plain {route}: HTTP {response.status}")
        headers = {
            key: value
            for key, value in (
                ("ETag", response.headers.get("ETag", "")),
                ("Age", response.headers.get("Age", "")),
                ("Last-Modified", response.headers.get("Last-Modified", "")),
                ("Cache-Control", response.headers.get("Cache-Control", "")),
            )
            if value
        }
        return response.read(), headers


def _fetch_many(base_url: str, routes: tuple[str, ...], release: str) -> dict[str, bytes]:
    """Fetch the release route set concurrently without changing per-request checks."""
    if not routes:
        return {}
    workers = min(16, len(routes))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            route: executor.submit(_fetch, base_url, route, release)
            for route in routes
        }
        return {route: future.result() for route, future in futures.items()}


def _routes_from_sitemap(payload: bytes) -> tuple[str, ...]:
    """Extract HTML routes from the local sitemap without including documentation."""
    text = payload.decode("utf-8")
    routes = {
        unquote(urlsplit(value).path.lstrip("/"))
        for value in re.findall(r"<loc>\s*(https://codegraph\.ru/[^<]+)\s*</loc>", text)
    }
    routes.discard("")
    routes.update(EXTRA_PUBLIC_ROUTES)
    routes.update(DOC_PUBLIC_ROUTES)
    routes.add("index.html")
    return tuple(
        sorted(
            route for route in routes if route.endswith(".html")
        )
    )


def _expected_canonical(route: str) -> str:
    """Return the exact canonical expected for one published HTML route."""
    return f"https://codegraph.ru/{route}" if route != "index.html" else "https://codegraph.ru/"


def _normalized_robots(value: str) -> str:
    """Normalize a robots content value for policy comparison."""
    return ", ".join(part.strip().casefold() for part in value.split(",") if part.strip())


def verify_once(
    base_url: str,
    root: Path,
    release: str,
    probe_urls: tuple[str, ...] = (),
) -> dict[str, object]:
    """Verify semantics, required routes, forbidden claims, and artifact hashes once."""
    local_sitemap = (root / "sitemap.xml").read_bytes()
    sitemap = _fetch(base_url, "sitemap.xml", release)
    routes = _routes_from_sitemap(local_sitemap)
    remote = _fetch_many(base_url, routes, release)
    remote["sitemap.xml"] = sitemap
    remote_assets = _fetch_many(base_url, REQUIRED_PUBLIC_ASSETS, release)
    homepage = remote["index.html"].decode("utf-8")
    root_homepage = _fetch(base_url, "", release).decode("utf-8")
    plain_probes: dict[str, dict[str, object]] = {}
    failures: list[str] = []
    for probe_url in (base_url, *probe_urls):
        plain_root, root_headers = _fetch_plain(probe_url, "")
        plain_index, index_headers = _fetch_plain(probe_url, "index.html")
        root_contract = HomeContractParser()
        root_contract.feed(plain_root.decode("utf-8"))
        index_contract = HomeContractParser()
        index_contract.feed(plain_index.decode("utf-8"))
        root_hash = _normalized_sha256(plain_root)
        index_hash = _normalized_sha256(plain_index)
        plain_probes[probe_url] = {
            "root": {
                "sha256": root_hash,
                "title": root_contract.title.strip(),
                "h1": _normalized_text(root_contract.h1),
                "css": root_contract.stylesheet,
                **root_headers,
            },
            "index": {
                "sha256": index_hash,
                "title": index_contract.title.strip(),
                "h1": _normalized_text(index_contract.h1),
                "css": index_contract.stylesheet,
                **index_headers,
            },
        }
    for probe_url, probe in plain_probes.items():
        for field in ("sha256", "title", "h1", "css"):
            if probe["root"].get(field) != probe["index"].get(field):
                failures.append(f"plain root/index {field} mismatch at {probe_url}")
    route_contracts: dict[str, dict[str, str]] = {}
    docs_contracts: dict[str, dict[str, object]] = {}
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
        contract_values = [
            ("canonical", public_parser.canonical, expected_canonical),
            ("local canonical", local_parser.canonical, expected_canonical),
        ]
        if not route.startswith("docs/"):
            contract_values.extend(
                (
                    ("release", public_parser.release.strip(), release),
                    ("local release", local_parser.release.strip(), release),
                )
            )
        for label, actual, expected in contract_values:
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
        if not route.startswith("docs/"):
            expected_robots = ROBOTS_POLICY.get(route, "")
            if _normalized_robots(public_parser.robots) != expected_robots:
                failures.append(f"{route}: robots={public_parser.robots!r}, expected={expected_robots!r}")

        if route.startswith("docs/"):
            public_docs = DocsContractParser()
            public_docs.feed(remote[route].decode("utf-8"))
            local_docs = DocsContractParser()
            local_docs.feed(local_path.read_text(encoding="utf-8"))
            expected_security = "Безопасность" if route.startswith("docs/ru/") else "Security"
            build_commit = public_docs.meta.get("cg:build-commit", "").strip()
            css_build = public_docs.meta.get("cg:css-build", "").strip()
            expected_css_build = _normalized_sha256((root / "css/tailwind.min.css").read_bytes())[:12]
            stylesheet = public_docs.stylesheets[0] if public_docs.stylesheets else ""
            script_paths = public_docs.scripts
            if "page-docs" not in public_docs.classes:
                failures.append(f"{route}: missing page-docs shell class")
            if not public_docs.has_header or not public_docs.has_footer:
                failures.append(f"{route}: missing shared header/footer")
            if expected_security not in public_docs.visible_text:
                failures.append(f"{route}: missing expected navigation label {expected_security!r}")
            if not build_commit or build_commit.casefold() == "unknown":
                failures.append(f"{route}: cg:build-commit is empty or unknown")
            if css_build != expected_css_build:
                failures.append(f"{route}: cg:css-build={css_build!r}, expected={expected_css_build!r}")
            if "tailwind.min.css?v=" not in stylesheet:
                failures.append(f"{route}: missing versioned Tailwind stylesheet link")
            if not any(path.endswith("js/main.min.js") for path in script_paths):
                failures.append(f"{route}: missing versioned main.min.js reference")
            if css_build in PREVIOUS_DOC_CSS_HASHES:
                failures.append(f"{route}: previous CSS build hash is still served: {css_build}")
            raw_public = remote[route].decode("utf-8")
            shell_html = raw_public.split("<main", 1)[0]
            if "&para;" in shell_html or re.search(r">\s*(?:Доверие|Trust)\s*<", shell_html):
                failures.append(f"{route}: stale Trust/paragraph shell marker found")
            docs_contracts[route] = {
                "build_commit": build_commit,
                "build_commit_semantics": DOC_BUILD_COMMIT_SEMANTICS,
                "css_build": css_build,
                "stylesheet": stylesheet,
                "scripts": script_paths,
                "security_label": expected_security in public_docs.visible_text,
            }

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
        "docs_contracts": docs_contracts,
        "assets": asset_hashes,
        "plain_probes": plain_probes,
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
    parser.add_argument(
        "--probe-base-url",
        action="append",
        default=[],
        help="Additional base URL to verify with ordinary / and /index.html requests.",
    )
    args = parser.parse_args()
    result: dict[str, object] = {"ok": False, "failures": ["not run"]}
    for attempt in range(1, args.attempts + 1):
        try:
            result = verify_once(
                args.base_url,
                args.root.resolve(),
                args.release,
                tuple(args.probe_base_url),
            )
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
