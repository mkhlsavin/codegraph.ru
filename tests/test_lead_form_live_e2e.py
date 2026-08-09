"""Live E2E checks for the public CodeGraph lead form."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect, sync_playwright  # noqa: E402


@pytest.mark.skipif(
    os.environ.get("CODEGRAPH_RUN_LIVE_LEAD_FORM_E2E") != "1",
    reason="Set CODEGRAPH_RUN_LIVE_LEAD_FORM_E2E=1 to create a synthetic live lead.",
)
def test_public_lead_form_creates_lead_and_reaches_terminal_success_status() -> None:
    """FR-P1217-03/05: live form submit must create a lead and reach success status."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    email = f"lead-e2e-live-{stamp}@codegraph.ru"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1365, "height": 900})
        page.goto(
            f"https://codegraph.ru/?v=live-e2e-{stamp}#demo",
            wait_until="domcontentloaded",
            timeout=30000,
        )

        expect(page.locator("#demo-form")).to_be_visible(timeout=10000)
        page.locator("#name").fill("CodeGraph Live E2E Probe")
        page.locator("#email").fill(email)
        page.locator("#company").fill("CodeGraph Synthetic E2E")
        page.locator("#buyer-role").select_option("cto")
        page.locator("#initiative-task").select_option("quality")
        page.locator("#team-size").evaluate("""(el) => {
              el.value = '80-149';
              el.dispatchEvent(new Event('input', { bubbles: true }));
              el.dispatchEvent(new Event('change', { bubbles: true }));
            }""")
        page.locator("#consent").check()
        assert (
            page.locator("#demo-form").evaluate("(form) => form.checkValidity()")
            is True
        )

        page.locator("#demo-submit-btn").scroll_into_view_if_needed()
        page.locator("#demo-submit-btn").click(force=True)

        expect(page.locator("#demo-status")).to_contain_text(
            "Заявка отправлена", timeout=10000
        )
        browser.close()
