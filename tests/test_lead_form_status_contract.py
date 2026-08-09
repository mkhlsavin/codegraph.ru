"""Contracts for the public lead form submission status behavior."""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

LANDING_ROOT = Path(__file__).resolve().parents[1]


def test_cta_name_field_required_matches_leads_api_contract() -> None:
    """FR-P1217-02: keep visible required fields aligned with the leads API."""
    for relative in ("templates/sections/cta.html", "index.html"):
        soup = BeautifulSoup(
            (LANDING_ROOT / relative).read_text(encoding="utf-8"), "html.parser"
        )
        label = soup.find("label", attrs={"for": "name"})
        field = soup.find("input", attrs={"id": "name", "name": "name"})

        assert label is not None, relative
        assert field is not None, relative
        assert field.has_attr("required"), relative
        assert "*" in label.get_text(" ", strip=True), relative


def test_lead_form_distinguishes_sent_and_not_sent_statuses() -> None:
    """FR-P1217-03/04/CNFR-Q1217-02: explain every submit outcome briefly."""
    source = (LANDING_ROOT / "js" / "main.js").read_text(encoding="utf-8")

    for expected_text in (
        "Заявка отправлена. Следующий шаг",
        "Заявка не отправлена: проверьте отмеченные поля",
        "Заявка не отправлена: проверьте обязательные поля и выбранные значения",
        "Заявка не отправлена: слишком много попыток",
        "Заявка не отправлена: сервер временно недоступен",
        "Заявка не отправлена: сервер не ответил вовремя",
        "Заявка не отправлена: нет соединения с сервером",
        "Заявка не отправлена: произошла ошибка отправки",
    ):
        assert expected_text in source

    for expected_branch in (
        "response.status === 400 || response.status === 422",
        "response.status === 429",
        "response.status >= 500",
        "error.name === 'AbortError'",
        "error instanceof TypeError",
        "fetchWithTimeout(leadsApiUrl",
    ):
        assert expected_branch in source


def test_lead_form_script_has_single_timeout_constant() -> None:
    """CNFR-Q1217-02: prevent script parse failures from duplicate declarations."""
    source = (LANDING_ROOT / "js" / "main.js").read_text(encoding="utf-8")

    assert source.count("const LEAD_SUBMISSION_TIMEOUT_MS = 20000;") == 1
