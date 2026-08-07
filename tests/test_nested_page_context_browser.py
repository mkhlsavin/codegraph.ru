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


def test_docs_drawers_remove_closed_panels_from_focus_tree(browser: Browser, site_url: str) -> None:
    """Responsive drawers must inert closed panels and the background behind TOC."""
    page = browser.new_page(viewport={"width": 1024, "height": 768})
    try:
        page.goto(
            f"{site_url}/docs/ru/enterprise/GOCPG_VS_JOERN_ANALYSIS.html",
            wait_until="networkidle",
        )
        page.wait_for_function("document.body.dataset.docEnhanced === 'true'")
        sidebar = page.locator(".doc-sidebar")
        toc = page.locator(".doc-toc")
        toggles = page.locator(".doc-sidebar-toggle")

        assert toggles.count() >= 5
        for index in range(toggles.count()):
            toggle = toggles.nth(index)
            assert toggle.evaluate(
                "node => { const style = getComputedStyle(node, '::after'); "
                "return style.flexBasis === '8px' && parseFloat(style.width) >= 7; }"
            )
        assert sidebar.evaluate("node => node.inert") is False
        assert toc.evaluate("node => node.inert") is True

        page.locator('[data-doc-open="toc"]').click()
        assert toc.get_attribute("role") == "dialog"
        assert sidebar.get_attribute("aria-hidden") == "true"
        assert sidebar.evaluate("node => node.inert") is True

        toc_link = toc.locator("a[href^='#']").first
        target_id = (toc_link.get_attribute("href") or "").lstrip("#")
        assert target_id
        toc_link.focus()
        page.keyboard.press("Enter")
        page.wait_for_timeout(100)
        assert toc.evaluate("node => node.inert") is True
        assert page.evaluate("document.activeElement && document.activeElement.id") == target_id
        assert page.locator(f"#{target_id}").get_attribute("tabindex") == "-1"
        assert page.evaluate("document.activeElement.closest('[inert]') === null") is True

        page.locator('[data-doc-open="toc"]').click()
        page.keyboard.press("Escape")
        assert toc.evaluate("node => node.inert") is True
        assert sidebar.evaluate("node => node.inert") is False

        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(100)
        assert sidebar.evaluate("node => node.inert") is True
        assert toc.evaluate("node => node.inert") is True
        page.locator('[data-doc-open="sidebar"]').click()
        assert sidebar.evaluate("node => node.inert") is False
        page.keyboard.press("Escape")
        assert sidebar.evaluate("node => node.inert") is True
    finally:
        page.close()
