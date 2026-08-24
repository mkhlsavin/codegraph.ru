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
REQUIRED_DOC_REDIRECTS = {
    "docs/en/api/README.html": "docs/en/api/index.html",
    "docs/ru/api/README.html": "docs/ru/api/index.html",
    "docs/en/enterprise/README.html": "docs/en/enterprise/index.html",
    "docs/ru/enterprise/README.html": "docs/ru/enterprise/index.html",
    "docs/en/enterprise/HYPOTHESIS_WHITEPAPER.html": "docs/en/reference/HYPOTHESIS_SYSTEM.html",
    "docs/ru/enterprise/HYPOTHESIS_WHITEPAPER.html": "docs/ru/reference/HYPOTHESIS_SYSTEM.html",
    "docs/en/guides/README.html": "docs/en/guides/index.html",
    "docs/ru/guides/README.html": "docs/ru/guides/index.html",
    "docs/en/guides/COMPLIANCE_REPORT.html": "docs/en/enterprise/GOST_56939_COMPLIANCE.html",
    "docs/ru/guides/COMPLIANCE_REPORT.html": "docs/ru/enterprise/GOST_56939_COMPLIANCE.html",
    "docs/en/guides/REFACTORING.html": "docs/en/guides/scenarios/05-refactoring.html",
    "docs/ru/guides/REFACTORING.html": "docs/ru/guides/scenarios/05-refactoring.html",
    "docs/en/guides/scenarios/21-pattern-search.html": "docs/en/guides/PATTERN_SEARCH.html",
    "docs/ru/guides/scenarios/21-pattern-search.html": "docs/ru/guides/PATTERN_SEARCH.html",
    "docs/en/integrations/README.html": "docs/en/integrations/index.html",
    "docs/ru/integrations/README.html": "docs/ru/integrations/index.html",
    "docs/en/reference/README.html": "docs/en/reference/index.html",
    "docs/ru/reference/README.html": "docs/ru/reference/index.html",
    "docs/en/reference/API.html": "docs/en/api/index.html",
    "docs/ru/reference/API.html": "docs/ru/api/index.html",
    "docs/en/reference/APPROVAL_ENGINE.html": "docs/en/reference/index.html",
    "docs/ru/reference/APPROVAL_ENGINE.html": "docs/ru/reference/index.html",
    "docs/en/reference/MCP_TOOLS.html": "docs/en/api/MCP_OPERATOR_GUIDE.html",
    "docs/ru/reference/MCP_TOOLS.html": "docs/ru/api/MCP_OPERATOR_GUIDE.html",
    "docs/en/reference/SECURITY.html": "docs/en/enterprise/index.html",
    "docs/ru/reference/SECURITY.html": "docs/ru/enterprise/index.html",
    "docs/en/reference/WORKFLOWS.html": "docs/en/guides/SCENARIOS.html",
    "docs/ru/reference/WORKFLOWS.html": "docs/ru/guides/SCENARIOS.html",
}
FORBIDDEN_PUBLIC_DOC_ORIGINS = ("https://github.com/mkhlsavin/codegraph/",)
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
        name = attributes.get("name") or ""
        rel = attributes.get("rel") or ""
        as_type = attributes.get("as") or ""
        if tag in {"title", "h1"} and (tag != "h1" or not self.h1):
            self._capture = tag
        if tag == "meta" and name == "cg:release":
            self.release = attributes.get("content") or ""
        if tag == "meta" and name.casefold() == "robots":
            self.robots = attributes.get("content") or ""
        if tag == "link" and rel.casefold() == "canonical":
            self.canonical = attributes.get("href") or ""
        if tag == "link" and rel.casefold() == "stylesheet":
            self.stylesheet = attributes.get("href") or ""
        if (
            tag == "link"
            and rel.casefold() == "preload"
            and as_type.casefold() == "style"
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
        """Initialize the collected docs-shell contract fields."""
        super().__init__()
        self.meta: dict[str, str] = {}
        self.stylesheets: list[str] = []
        self.scripts: list[str] = []
        self.text: list[str] = []
        self.classes: set[str] = set()
        self.has_header = False
        self.has_footer = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Collect metadata, assets, classes, and shell landmarks."""
        attributes = dict(attrs)
        self.classes.update((attributes.get("class") or "").split())
        self.has_header = self.has_header or tag == "header"
        self.has_footer = self.has_footer or tag == "footer"
        name = attributes.get("name") or ""
        rel = attributes.get("rel") or ""
        if tag == "meta" and name.startswith("cg:"):
            self.meta[name] = attributes.get("content") or ""
        if tag == "link" and rel.casefold() == "stylesheet":
            self.stylesheets.append(attributes.get("href") or "")
        if tag == "script" and attributes.get("src"):
            self.scripts.append(attributes["src"] or "")

    def handle_data(self, data: str) -> None:
        """Collect visible text fragments for later normalization."""
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
        headers={
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": "CodeGraphReleaseGate/1.0",
        },
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


def _fetch_many(
    base_url: str, routes: tuple[str, ...], release: str
) -> dict[str, bytes]:
    """Fetch the release route set concurrently without changing per-request checks."""
    if not routes:
        return {}
    workers = min(16, len(routes))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            route: executor.submit(_fetch, base_url, route, release) for route in routes
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
    return tuple(sorted(route for route in routes if route.endswith(".html")))


def _expected_canonical(route: str) -> str:
    """Return the exact canonical expected for one published HTML route."""
    return (
        f"https://codegraph.ru/{route}"
        if route != "index.html"
        else "https://codegraph.ru/"
    )


def _normalized_robots(value: str) -> str:
    """Normalize a robots content value for policy comparison."""
    return ", ".join(
        part.strip().casefold() for part in value.split(",") if part.strip()
    )


def _parse_home_contract(payload: bytes) -> HomeContractParser:
    """Parse one public-page payload into its semantic contract."""
    parser = HomeContractParser()
    parser.feed(payload.decode("utf-8"))
    return parser


def _plain_probe_result(probe_url: str) -> dict[str, dict[str, object]]:
    """Collect root and explicit-index contracts without cache-busting parameters."""
    result: dict[str, dict[str, object]] = {}
    for label, route in (("root", ""), ("index", "index.html")):
        payload, headers = _fetch_plain(probe_url, route)
        contract = _parse_home_contract(payload)
        result[label] = {
            "sha256": _normalized_sha256(payload),
            "title": contract.title.strip(),
            "h1": _normalized_text(contract.h1),
            "css": contract.stylesheet,
            **headers,
        }
    return result


def _verify_plain_probes(
    base_url: str,
    probe_urls: tuple[str, ...],
) -> tuple[dict[str, dict[str, dict[str, object]]], list[str]]:
    """Verify root and explicit-index parity on every public hostname."""
    probes = {url: _plain_probe_result(url) for url in (base_url, *probe_urls)}
    failures = [
        f"plain root/index {field} mismatch at {probe_url}"
        for probe_url, probe in probes.items()
        for field in ("sha256", "title", "h1", "css")
        if probe["root"].get(field) != probe["index"].get(field)
    ]
    return probes, failures


def _route_identity_failures(
    route: str,
    public: HomeContractParser,
    local: HomeContractParser,
    release: str,
) -> list[str]:
    """Validate canonical and release metadata for one route."""
    expected_canonical = _expected_canonical(route)
    values = [
        ("canonical", public.canonical, expected_canonical),
        ("local canonical", local.canonical, expected_canonical),
    ]
    if not route.startswith("docs/"):
        values.extend(
            (
                ("release", public.release.strip(), release),
                ("local release", local.release.strip(), release),
            )
        )
    return [
        f"{route}: {label}={actual!r}, expected={expected!r}"
        for label, actual, expected in values
        if actual != expected
    ]


def _route_semantic_failures(
    route: str,
    public: HomeContractParser,
    local: HomeContractParser,
) -> list[str]:
    """Validate visible semantics and stylesheet links for one route."""
    failures: list[str] = []
    comparisons = (
        ("title", _normalized_text(public.title), _normalized_text(local.title)),
        ("H1", _normalized_text(public.h1), _normalized_text(local.h1)),
        ("stylesheet link", public.stylesheet, local.stylesheet),
        ("stylesheet preload", public.style_preload, local.style_preload),
    )
    if not public.title.strip() or not public.h1.strip():
        failures.append(f"{route}: missing title or H1")
    failures.extend(
        f"{route}: {label} differs from local"
        for label, public_value, local_value in comparisons
        if public_value != local_value
    )
    if not route.startswith("docs/"):
        expected = ROBOTS_POLICY.get(route, "")
        if _normalized_robots(public.robots) != expected:
            failures.append(f"{route}: robots={public.robots!r}, expected={expected!r}")
    return failures


def _docs_shell_failures(
    route: str,
    contract: DocsContractParser,
    expected_security: str,
    expected_css_build: str,
    shell_html: str,
) -> list[str]:
    """Validate the generated documentation shell for one route."""
    failures: list[str] = []
    build_commit = contract.meta.get("cg:build-commit", "").strip()
    css_build = contract.meta.get("cg:css-build", "").strip()
    stylesheet = contract.stylesheets[0] if contract.stylesheets else ""
    checks = (
        ("page-docs" in contract.classes, "missing page-docs shell class"),
        (contract.has_header and contract.has_footer, "missing shared header/footer"),
        (
            expected_security in contract.visible_text,
            f"missing expected navigation label {expected_security!r}",
        ),
        (
            bool(build_commit) and build_commit.casefold() != "unknown",
            "cg:build-commit is empty or unknown",
        ),
        (
            css_build == expected_css_build,
            f"cg:css-build={css_build!r}, expected={expected_css_build!r}",
        ),
        (
            "tailwind.min.css?v=" in stylesheet,
            "missing versioned Tailwind stylesheet link",
        ),
        (
            any(path.endswith("js/main.min.js") for path in contract.scripts),
            "missing versioned main.min.js reference",
        ),
        (
            css_build not in PREVIOUS_DOC_CSS_HASHES,
            f"previous CSS build hash is still served: {css_build}",
        ),
        (
            "&para;" not in shell_html
            and re.search(r">\s*(?:Доверие|Trust)\s*<", shell_html) is None,
            "stale Trust/paragraph shell marker found",
        ),
    )
    failures.extend(f"{route}: {message}" for passed, message in checks if not passed)
    return failures


def _verify_docs_contract(
    route: str,
    payload: bytes,
    root: Path,
) -> tuple[dict[str, object], list[str]]:
    """Return documentation-shell evidence and failures for one route."""
    contract = DocsContractParser()
    raw_public = payload.decode("utf-8")
    contract.feed(raw_public)
    expected_security = "Безопасность" if route.startswith("docs/ru/") else "Security"
    build_commit = contract.meta.get("cg:build-commit", "").strip()
    css_build = contract.meta.get("cg:css-build", "").strip()
    expected_css_build = _normalized_sha256(
        (root / "css/tailwind.min.css").read_bytes()
    )[:12]
    stylesheet = contract.stylesheets[0] if contract.stylesheets else ""
    failures = _docs_shell_failures(
        route,
        contract,
        expected_security,
        expected_css_build,
        raw_public.split("<main", 1)[0],
    )
    failures.extend(
        f"{route}: forbidden private repository origin {origin!r}"
        for origin in FORBIDDEN_PUBLIC_DOC_ORIGINS
        if origin.casefold() in raw_public.casefold()
    )
    evidence: dict[str, object] = {
        "build_commit": build_commit,
        "build_commit_semantics": DOC_BUILD_COMMIT_SEMANTICS,
        "css_build": css_build,
        "stylesheet": stylesheet,
        "scripts": contract.scripts,
        "security_label": expected_security in contract.visible_text,
    }
    return evidence, failures


def _verify_doc_redirects(
    remote: dict[str, bytes],
    root: Path,
) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Verify every audited legacy route as a noindex local/public redirect stub."""

    evidence: dict[str, dict[str, str]] = {}
    failures: list[str] = []
    for route, target in REQUIRED_DOC_REDIRECTS.items():
        local_path = root / route
        if not local_path.is_file():
            failures.append(f"missing local redirect: {route}")
            continue

        public_payload = remote[route]
        local_payload = local_path.read_bytes()
        raw_public = public_payload.decode("utf-8")
        expected_url = f"/{target}"
        expected_canonical = f"https://codegraph.ru/{target}"
        contract = _parse_home_contract(public_payload)
        local_hash = _normalized_sha256(local_payload)
        public_hash = _normalized_sha256(public_payload)
        evidence[route] = {
            "target": target,
            "canonical": contract.canonical,
            "robots": _normalized_robots(contract.robots),
            "local_hash": local_hash,
            "public_hash": public_hash,
        }
        checks = (
            (local_hash == public_hash, "content hash differs from local"),
            (
                contract.canonical == expected_canonical,
                f"canonical={contract.canonical!r}, expected={expected_canonical!r}",
            ),
            (
                _normalized_robots(contract.robots) == "noindex, follow",
                f"robots={contract.robots!r}, expected='noindex, follow'",
            ),
            (
                re.search(
                    rf'<meta\s+http-equiv="refresh"\s+content="0;\s*url={re.escape(expected_url)}"',
                    raw_public,
                    re.IGNORECASE,
                )
                is not None,
                f"missing refresh target {expected_url!r}",
            ),
            (
                f'location.replace("{expected_url}")' in raw_public,
                f"missing script target {expected_url!r}",
            ),
            (
                not any(
                    origin.casefold() in raw_public.casefold()
                    for origin in FORBIDDEN_PUBLIC_DOC_ORIGINS
                ),
                "forbidden private repository origin",
            ),
        )
        failures.extend(
            f"{route}: {message}" for passed, message in checks if not passed
        )
    return evidence, failures


def _verify_route_contracts(
    routes: tuple[str, ...],
    remote: dict[str, bytes],
    root: Path,
    release: str,
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, object]], list[str]]:
    """Verify all public route contracts against the checked-out artifact."""
    route_contracts: dict[str, dict[str, str]] = {}
    docs_contracts: dict[str, dict[str, object]] = {}
    failures: list[str] = []
    for route in routes:
        local_path = root / route
        if not local_path.is_file():
            failures.append(f"missing local route: {route}")
            continue
        public = _parse_home_contract(remote[route])
        local = _parse_home_contract(local_path.read_bytes())
        route_contracts[route] = {
            "canonical": public.canonical,
            "release": public.release.strip(),
            "robots": _normalized_robots(public.robots),
        }
        failures.extend(_route_identity_failures(route, public, local, release))
        failures.extend(_route_semantic_failures(route, public, local))
        if route.startswith("docs/"):
            evidence, docs_failures = _verify_docs_contract(route, remote[route], root)
            docs_contracts[route] = evidence
            failures.extend(docs_failures)
    return route_contracts, docs_contracts, failures


def _homepage_failures(
    homepage: str, root_homepage: str, release: str
) -> tuple[str, list[str]]:
    """Validate homepage semantics, parity, and forbidden claims."""
    public = _parse_home_contract(homepage.encode("utf-8"))
    root = _parse_home_contract(root_homepage.encode("utf-8"))
    failures: list[str] = []
    expected_values = (
        ("title", _normalized_text(public.title), EXPECTED_TITLE),
        ("h1", _normalized_text(public.h1), EXPECTED_H1),
        ("release", public.release.strip(), release),
    )
    failures.extend(
        f"{label}={actual!r}"
        for label, actual, expected in expected_values
        if actual != expected
    )
    if (
        _normalized_text(root.title) != _normalized_text(public.title)
        or _normalized_text(root.h1) != _normalized_text(public.h1)
        or root.release.strip() != public.release.strip()
    ):
        failures.append("root/index.html semantic mismatch")
    if _normalized_sha256(root_homepage.encode("utf-8")) != _normalized_sha256(
        homepage.encode("utf-8")
    ):
        failures.append("root/index.html content hash mismatch")
    folded_homepage = homepage.casefold()
    failures.extend(
        f"forbidden={text!r}"
        for text in FORBIDDEN_TEXT
        if text.casefold() in folded_homepage
    )
    return public.release.strip(), failures


def _verify_hashes(
    root: Path,
    routes: tuple[str, ...],
    remote: dict[str, bytes],
) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Compare normalized hashes for generated HTML routes and the sitemap."""
    hashes: dict[str, dict[str, str]] = {}
    failures: list[str] = []
    for route in (*routes, "sitemap.xml"):
        local_hash = _normalized_sha256((root / route).read_bytes())
        remote_hash = _normalized_sha256(remote[route])
        hashes[route] = {"local": local_hash, "public": remote_hash}
        if local_hash != remote_hash:
            failures.append(f"hash mismatch: {route}")
    return hashes, failures


def _verify_asset_hashes(
    root: Path,
    remote_assets: dict[str, bytes],
) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Compare normalized hashes for required public assets."""
    hashes: dict[str, dict[str, str]] = {}
    failures: list[str] = []
    for route in REQUIRED_PUBLIC_ASSETS:
        local_path = root / route
        if not local_path.is_file():
            failures.append(f"missing local asset: {route}")
            continue
        local_hash = _normalized_sha256(local_path.read_bytes())
        remote_hash = _normalized_sha256(remote_assets[route])
        hashes[route] = {"local": local_hash, "public": remote_hash}
        if local_hash != remote_hash:
            failures.append(f"hash mismatch: {route}")
    return hashes, failures


def verify_once(
    base_url: str,
    root: Path,
    release: str,
    probe_urls: tuple[str, ...] = (),
) -> dict[str, object]:
    """Verify semantics, required routes, forbidden claims, and artifact hashes once."""
    local_sitemap = (root / "sitemap.xml").read_bytes()
    routes = _routes_from_sitemap(local_sitemap)
    remote = _fetch_many(base_url, routes, release)
    remote_redirects = _fetch_many(base_url, tuple(REQUIRED_DOC_REDIRECTS), release)
    remote["sitemap.xml"] = _fetch(base_url, "sitemap.xml", release)
    remote_assets = _fetch_many(base_url, REQUIRED_PUBLIC_ASSETS, release)
    homepage = remote["index.html"].decode("utf-8")
    root_homepage = _fetch(base_url, "", release).decode("utf-8")

    plain_probes, failures = _verify_plain_probes(base_url, probe_urls)
    route_contracts, docs_contracts, route_failures = _verify_route_contracts(
        routes, remote, root, release
    )
    homepage_release, homepage_contract_failures = _homepage_failures(
        homepage, root_homepage, release
    )
    hashes, hash_failures = _verify_hashes(root, routes, remote)
    asset_hashes, asset_failures = _verify_asset_hashes(root, remote_assets)
    redirect_contracts, redirect_failures = _verify_doc_redirects(
        remote_redirects, root
    )
    failures.extend(route_failures)
    failures.extend(homepage_contract_failures)
    failures.extend(hash_failures)
    failures.extend(asset_failures)
    failures.extend(redirect_failures)
    failures.extend(
        f"redirect route must be excluded from sitemap: {route}"
        for route in REQUIRED_DOC_REDIRECTS
        if route in routes
    )
    return {
        "ok": not failures,
        "failures": failures,
        "hashes": hashes,
        "routes": list(routes),
        "release": homepage_release,
        "route_contracts": route_contracts,
        "docs_contracts": docs_contracts,
        "redirects": redirect_contracts,
        "assets": asset_hashes,
        "plain_probes": plain_probes,
    }


def main() -> int:
    """Poll the public domain until the exact checked-out artifact is available."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://codegraph.ru/")
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
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
        except (
            HTTPError,
            URLError,
            TimeoutError,
            RuntimeError,
            UnicodeDecodeError,
        ) as error:
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
