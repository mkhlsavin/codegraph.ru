"""Browser regression for declarative context on nested public pages."""

from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from playwright.sync_api import Browser, sync_playwright


LANDING_ROOT = Path(__file__).resolve().parents[1]
ROUTES = {
    "compare/codegraph-fortify.html": "compare-codegraph-fortify",
    "scenarios/ai-code-control.html": "scenarios-ai-code-control",
    "problems/kak-ponyat-chuzhuyu-kodovuyu-bazu.html": "problems-kak-ponyat-chuzhuyu-kodovuyu-bazu",
    "research/tochnost-otvetov-i-skorost-razbora.html": "research-tochnost-otvetov-i-skorost-razbora",
    "authors/mikhail-savin.html": "authors-mikhail-savin",
}


@pytest.fixture(scope="module")
def site_url():
    handler = lambda *args, **kwargs: SimpleHTTPRequestHandler(
        *args, directory=str(LANDING_ROOT), **kwargs
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.fixture(scope="module")
def browser() -> Browser:
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(headless=True)
        yield instance
        instance.close()


@pytest.mark.parametrize(("route", "page_id"), ROUTES.items())
def test_nested_cta_preserves_declared_page_context(browser: Browser, site_url: str, route: str, page_id: str) -> None:
    page = browser.new_page()
    try:
        page.goto(f"{site_url}/{route}", wait_until="networkidle")
        cta = page.locator('a[href*="#demo"]').first
        href = cta.get_attribute("href") or ""
        assert f"page_id={page_id}" in href
        assert f"source_page={page_id}" in href
        assert "#demo" in href
    finally:
        page.close()
