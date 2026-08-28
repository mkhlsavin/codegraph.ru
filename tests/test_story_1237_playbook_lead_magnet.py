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
    """FR-P1237-LEAD-PAGE-01/AC-1237-08: render a form-first download flow."""
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
    assert "После успешной регистрации заявки появится ссылка на PDF." in soup.get_text(
        " ", strip=True
    )


def test_playbook_page_matches_revised_playbook_content_contract() -> None:
    """FR-P1237-CONTENT-SYNC-01/AC-1237-01: expose the revised playbook promise."""
    page = RESOURCE_ROOT / "index.html"
    soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
    page_text = soup.get_text(" ", strip=True)

    assert soup.title is not None
    assert (
        soup.title.get_text(strip=True)
        .replace("\u00a0", " ")
        .startswith("Плейбук CodeGraph для разработки с ИИ-агентами")
    )
    assert soup.find("h1").get_text(" ", strip=True).replace("\u00a0", " ") == (
        "Плейбук CodeGraph для разработки с ИИ-агентами"
    )
    assert "От продуктовой задачи до проверенного выпуска" in page_text
    assert (
        soup.find("meta", attrs={"name": "dateModified"}).get("content") == "2026-08-27"
    )

    for marker in (
        "семь принципов",
        "25 процессных областей",
        "обнаружение, стабилизация, восстановление",
        "четыре показателя DORA",
        "шесть рабочих недель",
    ):
        assert marker.lower() in page_text.lower()


def test_playbook_uses_the_shared_landing_shell() -> None:
    """AC-1237-10: keep the playbook navigation and footer on the shared shell."""
    page = RESOURCE_ROOT / "index.html"
    soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")

    header = soup.find("header", attrs={"data-shell-header": True})
    footer = soup.find("footer", attrs={"data-shell-footer": True})
    assert header is not None
    assert footer is not None
    assert soup.find(attrs={"data-shell-logo": True}) is not None
    assert soup.find(attrs={"data-theme-toggle": True}) is not None
    assert soup.find(attrs={"data-mobile-menu-toggle": True}) is not None
    assert soup.find(attrs={"data-mobile-nav": True}) is not None
    assert soup.find("header", class_="cg-resource-header") is None
    assert soup.find("footer", class_="cg-resource-footer") is None

    registry = (
        LANDING_ROOT.parents[1] / "scripts" / "landing_build_registry.py"
    ).read_text(encoding="utf-8")
    assert '"downloads/ai-native-pdlc-sdlc-playbook/index.html"' in registry
    assert '    "blog",' in registry


def test_corporate_blog_template_defines_reviewable_article_slots() -> None:
    """The reusable corporate article template must compose with shared chrome."""
    template = LANDING_ROOT / "templates" / "corporate-blog-article.html"
    source = template.read_text(encoding="utf-8")

    for marker in (
        "CORPORATE_BLOG_ARTICLE_TEMPLATE_START",
        "CORPORATE_BLOG_ARTICLE_TEMPLATE_END",
        "{{article_title}}",
        "{{article_description}}",
        "{{article_author}}",
        "{{published_date}}",
        "{{updated_date}}",
        "{{reading_time}}",
        'data-article-template="corporate-blog"',
        'class="cg-article-hero"',
        'class="cg-article-answer"',
        'class="cg-article-section"',
        'class="cg-article-related-links"',
        "templates/header.html",
        "templates/footer.html",
    ):
        assert marker in source


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
        "AbortController",
        "lead_api_400",
        "lead_api_422",
        "lead_api_429",
        "lead_api_5xx",
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


def test_corporate_blog_article_is_published_and_linked_from_playbook() -> None:
    """FR-P1237-BLOG-PUBLICATION-01/AC-1237-11: publish the reviewed article and its route."""
    article = (
        LANDING_ROOT / "blog" / "kogda-kod-perestaet-byt-uzkim-mestom" / "index.html"
    )
    blog_index = LANDING_ROOT / "blog" / "index.html"
    article_soup = BeautifulSoup(article.read_text(encoding="utf-8"), "html.parser")
    article_text = article_soup.get_text(" ", strip=True)

    assert (
        article_soup.find("h1")
        .get_text(" ", strip=True)
        .startswith("Когда код перестаёт быть узким местом")
    )
    assert (
        article_soup.find("meta", attrs={"name": "robots"}).get("content")
        == "index, follow"
    )
    assert article_soup.find("link", attrs={"rel": "canonical"}).get("href") == (
        "https://codegraph.ru/blog/kogda-kod-perestaet-byt-uzkim-mestom/"
    )
    assert article_soup.find(
        "script", string=lambda value: value and "BlogPosting" in value
    )
    assert article_soup.find("header", attrs={"data-shell-header": True}) is not None
    assert article_soup.find("footer", attrs={"data-shell-footer": True}) is not None
    assert article_soup.find(id="pdlc") is not None
    assert article_soup.find(id="schools") is not None
    assert article_soup.find(id="conclusion") is not None
    assert (
        len(
            [
                h2
                for h2 in article_soup.find_all("h2")
                if h2.get_text(" ", strip=True) == "Основной вывод"
            ]
        )
        == 1
    )
    for marker in (
        "Anthropic",
        "AWS",
        "Референсная архитектура AI-native PDLC",
        "Минимально жизнеспособный плейбук на 90 дней",
    ):
        assert marker in article_text
    assert "{{" not in article.read_text(encoding="utf-8")

    blog_soup = BeautifulSoup(blog_index.read_text(encoding="utf-8"), "html.parser")
    assert (
        blog_soup.find("a", href="/blog/kogda-kod-perestaet-byt-uzkim-mestom/")
        is not None
    )

    playbook = BeautifulSoup(
        (RESOURCE_ROOT / "index.html").read_text(encoding="utf-8"), "html.parser"
    )
    assert (
        playbook.find("a", href="/blog/kogda-kod-perestaet-byt-uzkim-mestom/")
        is not None
    )

    registry = json.loads(
        (LANDING_ROOT / "public-pages.json").read_text(encoding="utf-8")
    )
    assert "blog/index.html" in registry["include"]
    assert "blog/*.html" in registry["include"]
    assert "blog/kogda-kod-perestaet-byt-uzkim-mestom/index.html" in registry["include"]
    sitemap = (LANDING_ROOT / "sitemap.xml").read_text(encoding="utf-8")
    assert "https://codegraph.ru/blog/" in sitemap
    assert "https://codegraph.ru/blog/kogda-kod-perestaet-byt-uzkim-mestom/" in sitemap


def test_corporate_blog_index_uses_visual_cards_and_vertical_links() -> None:
    """FR-P1237-BLOG-PUBLICATION-01/AC-1237-12: make the blog index visual and navigable."""
    blog_index = LANDING_ROOT / "blog" / "index.html"
    soup = BeautifulSoup(blog_index.read_text(encoding="utf-8"), "html.parser")

    assert soup.select_one(".cg-article-trust") is None

    feature = soup.select_one("a.cg-blog-feature-card")
    assert feature is not None
    assert feature.get("href") == "/blog/kogda-kod-perestaet-byt-uzkim-mestom/"
    feature_image = feature.find("img")
    assert feature_image is not None
    assert feature_image.get("src") == "../assets/ui/ad-ai-hero.png"
    assert feature_image.get("width") == "1440"
    assert feature_image.get("height") == "980"

    topics = soup.select("a.cg-blog-topic-card")
    assert len(topics) == 3
    assert [topic.get("href") for topic in topics] == [
        "/product-delivery.html",
        "/ai-engineering.html",
        "/evidence.html",
    ]
    assert all(topic.find("img") is not None for topic in topics)


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
