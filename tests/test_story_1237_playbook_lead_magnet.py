"""Story 1237 contracts for the AI-native PDLC-SDLC playbook lead magnet."""

from __future__ import annotations

import json
from pathlib import Path
import re

from bs4 import BeautifulSoup
import pdfplumber
from pypdf import PdfReader

LANDING_ROOT = Path(__file__).resolve().parents[1]
RESOURCE_ROOT = LANDING_ROOT / "downloads" / "ai-native-pdlc-sdlc-playbook"


def test_playbook_covers_requested_governance_contours() -> None:
    """FR-P1237-EDITORIAL/RBPO/RELEASE/INCIDENT/FINANCE/DORA-01: cover the full lifecycle."""
    pdf = RESOURCE_ROOT / "CODEGRAPH_AI_NATIVE_PDLC_SDLC_PLAYBOOK_RU.pdf"
    with pdfplumber.open(str(pdf)) as document:
        text = re.sub(
            r"\s+",
            " ",
            " ".join((page.extract_text() or "") for page in document.pages),
        )

    required_sections = (
        "Безопасная разработка и соответствие требованиям",
        "Этап 6. Подготовить и выполнить выпуск",
        "Этап 7. Вернуть результат в продуктовый цикл",
        "Поток поставки",
        "Экономика",
    )
    for section in required_sections:
        assert section in text

    for marker in (
        "карту 25 процессных областей ГОСТ Р 56939-2024",
        "Кандидат — это точная комбинация кода, сборки, конфигурации и целевой среды",
        "обнаружение, стабилизация, восстановление",
        "четыре показателя DORA",
        "Экономический эффект",
    ):
        assert marker in text


def test_playbook_page_is_form_first_and_initially_hides_pdf() -> None:
    """FR-P1237-LEAD-PAGE-01/AC-1237-08: render a form-first soft gate."""
    page = RESOURCE_ROOT / "index.html"
    soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")

    form = soup.find("form", attrs={"id": "playbook-lead-form"})
    assert form is not None
    assert form.get("data-resource-form") == "playbook"
    assert soup.find("input", attrs={"name": "name", "required": True}) is not None
    assert soup.find("input", attrs={"name": "email", "required": True}) is not None
    assert soup.find("input", attrs={"name": "company", "required": True}) is not None
    assert soup.find("input", attrs={"name": "consent", "required": True}) is not None

    link = soup.find("a", attrs={"id": "playbook-download-link"})
    assert link is not None
    assert link.has_attr("hidden")
    assert link.get("aria-hidden") == "true"
    assert link.get("tabindex") == "-1"
    assert link.get("href") == "CODEGRAPH_AI_NATIVE_PDLC_SDLC_PLAYBOOK_RU.pdf"
    assert "мягкий gate" in soup.get_text(" ", strip=True)


def test_playbook_form_script_keeps_failure_closed_and_reveals_on_success() -> None:
    """FR-P1237-FORM-GATE-01/AC-1237-09: reveal only after accepted lead response."""
    source = (RESOURCE_ROOT / "playbook-download.js").read_text(encoding="utf-8")

    for contract in (
        "https://api.codegraph.ru/api/v1/leads",
        "playbook_lead_magnet",
        "response.ok",
        "link.hidden = false",
        'link.setAttribute("aria-hidden", "false")',
        'link.removeAttribute("tabindex")',
        "link.hidden = true",
        "consent: consent.checked",
        "sessionStorage",
    ):
        assert contract in source
    assert "localStorage" not in source


def test_playbook_public_metadata_and_route_registry() -> None:
    """CNFR-Q1237-WEB-QUALITY/TRACEABILITY-01: register an indexable metadata-complete route."""
    page = RESOURCE_ROOT / "index.html"
    soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
    canonical = soup.find("link", attrs={"rel": "canonical"})
    assert canonical is not None
    assert (
        canonical.get("href")
        == "https://codegraph.ru/downloads/ai-native-pdlc-sdlc-playbook/"
    )
    assert soup.find("meta", attrs={"name": "description"}) is not None
    assert soup.find("meta", attrs={"property": "og:title"}) is not None
    assert soup.find("script", attrs={"type": "application/ld+json"}) is not None
    assert soup.find("meta", attrs={"name": "robots"}).get("content") == "index, follow"

    registry = json.loads(
        (LANDING_ROOT / "public-pages.json").read_text(encoding="utf-8")
    )
    assert "downloads/ai-native-pdlc-sdlc-playbook/index.html" in registry["include"]


def test_playbook_pdf_is_searchable_metadata_complete_and_geometrically_valid() -> None:
    """FR-P1237-PDF-01/AC-1237-07: verify the generated publication artifact."""
    pdf = RESOURCE_ROOT / "CODEGRAPH_AI_NATIVE_PDLC_SDLC_PLAYBOOK_RU.pdf"
    assert pdf.stat().st_size > 100_000
    assert pdf.read_bytes()[:5] == b"%PDF-"

    reader = PdfReader(str(pdf))
    metadata = reader.metadata
    assert metadata is not None
    assert metadata.title == "Плейбук CodeGraph для разработки с ИИ-агентами"
    assert metadata.author == "CodeGraph"
    assert len(reader.pages) >= 15

    with pdfplumber.open(str(pdf)) as document:
        extracted_pages = [
            (page.extract_text() or "").strip() for page in document.pages
        ]
        assert all(len(text) >= 100 for text in extracted_pages)
        assert {
            (round(page.width, 2), round(page.height, 2)) for page in document.pages
        } == {(595.28, 841.89)}
    extracted = re.sub(r"\s+", " ", "\n".join(extracted_pages))
    for marker in (
        "Плейбук CodeGraph",
        "Безопасная разработка",
        "Кандидат на выпуск",
        "DORA",
    ):
        assert marker in extracted
