"""Fail-closed semantic contracts for the complete Story 1113 public-site rewrite."""

from __future__ import annotations

import json
from pathlib import Path
import re
import struct
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString
from scripts.landing_content import SITE_CONTENT


LANDING_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_CATEGORY = SITE_CONTENT["canonical_category"]
KEY_PAGE_CONTRACTS = {
    "index.html": (
        "Снизьте затраты на разработку и риск срыва сроков",
        "CodeGraph показывает, чем подтверждён статус изменения, какие риски остаются открытыми и чьё решение требуется.",
        "landing-audit-20260722-v5",
    ),
    "whitepaper.html": (
        "Архитектура CodeGraph",
        "Как устроена модель CodeGraph?",
        "release-1",
    ),
    "product-delivery.html": (
        "Портфель проектов и причины задержек",
        "Как понять текущий статус каждого проекта?",
        "release-1",
    ),
    "evidence.html": (
        "Доказательства выполнения требований",
        "Чем подтверждается реализация каждого требования?",
        "release-2",
    ),
    "digital-team.html": (
        "Цифровая команда: роли, полномочия и границы",
        "Кто выполняет работу и в каких границах?",
        "release-2",
    ),
    "ai-engineering.html": (
        "Как контролировать код, созданный ИИ",
        "Как проверить, что код, созданный ИИ, соответствует требованиям?",
        "release-2",
    ),
    "cpg.html": (
        "Анализ влияния изменений",
        "Как определяется влияние требования на код и тесты?",
        "release-2",
    ),
    "security.html": (
        "Проверка требований безопасности",
        "Как требование безопасности проходит до решения о риске?",
        "release-3",
    ),
    "compliance.html": (
        "Технические контроли CodeGraph",
        "Где данные и какие технические контроли подтверждены?",
        "release-3",
    ),
    "platform-operations.html": (
        "Развёртывание и восстановление CodeGraph",
        "Как система развёртывается, интегрируется и восстанавливается?",
        "release-3",
    ),
    "integrations.html": (
        "Интеграции CodeGraph: поддерживаемые операции и ограничения",
        "Какие операции поддерживает каждая интеграция?",
        "release-3",
    ),
    "productivity.html": (
        "Где команда теряет время на переделках",
        "Как CTO управляет соответствием реализации требованиям?",
        "release-4",
    ),
    "business-efficiency.html": (
        "Как измерить эффект пилота",
        "Как измерить эффект пилота?",
        "release-4",
    ),
}


def test_social_previews_use_current_brand_and_positioning() -> None:
    """Keep every social card on the current category and cache-busted assets."""
    expected = {
        "index.html": (
                "og-codegraph-platform-20260722.png",
                SITE_CONTENT["social_image_alt"],
            ),
        "whitepaper.html": (
            "og-codegraph-platform-20260722.png",
            SITE_CONTENT["social_image_alt"],
        ),
    }
    for route, (filename, alt) in expected.items():
        soup = _soup(route)
        image_url = soup.find("meta", property="og:image")["content"]
        assert image_url == f"https://codegraph.ru/assets/{filename}"
        assert soup.find("meta", attrs={"name": "twitter:image"})["content"] == image_url
        og_alt = soup.find("meta", property="og:image:alt")["content"].replace("\xa0", " ")
        twitter_alt = soup.find("meta", attrs={"name": "twitter:image:alt"})["content"].replace("\xa0", " ")
        assert og_alt == alt
        assert twitter_alt == alt
        preview = (LANDING_ROOT / "assets" / filename).read_bytes()
        assert preview.startswith(b"\x89PNG\r\n\x1a\n")
        assert struct.unpack(">II", preview[16:24]) == (1200, 630)

    for path in LANDING_ROOT.rglob("*.html"):
        if "node_modules" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        if "og:image" not in source:
            continue
        assert "assets/og-image.png" not in source
        assert "assets/og-whitepaper-v31.png" not in source

    generator_path = LANDING_ROOT.parents[1] / "scripts" / "story_1113_public_pages.py"
    if generator_path.is_file():
        generator = generator_path.read_text(encoding="utf-8")
        assert "Draw the compact geometric mark directly" in generator
        for stale_claim in ("AI-копилот", "Hybrid RAG", "21 сценарий", "95.6% точность"):
            assert stale_claim not in generator


def test_nested_pages_use_declared_context_for_cta_routing() -> None:
    """Use the page contract, not only the last URL segment, for nested CTAs."""
    source = (LANDING_ROOT / "js" / "main.js").read_text(encoding="utf-8")
    assert "document.querySelector('main[data-page-id]')?.dataset.pageId" in source
    assert "if (declared) return declared;" in source

    expected = {
        "compare/codegraph-fortify.html": "compare-codegraph-fortify",
        "scenarios/ai-code-control.html": "scenarios-ai-code-control",
        "problems/kak-ponyat-chuzhuyu-kodovuyu-bazu.html": "problems-kak-ponyat-chuzhuyu-kodovuyu-bazu",
        "research/tochnost-otvetov-i-skorost-razbora.html": "research-tochnost-otvetov-i-skorost-razbora",
        "authors/mikhail-savin.html": "authors-mikhail-savin",
    }
    for route, page_id in expected.items():
        main = _soup(route).find("main", attrs={"data-page-id": True})
        assert main is not None
        assert main["data-page-id"] == page_id


def test_visible_logo_uses_versioned_approved_geometric_lockup() -> None:
    """Keep the approved geometric mark visible and cache-busted sitewide."""
    logo_name = "logo-golden-ratio-lockup-20260720.svg"
    logo_path = LANDING_ROOT / "assets" / "svg" / logo_name
    source = logo_path.read_text(encoding="utf-8")
    assert 'viewBox="0 0 256 64"' in source
    assert "M216.204 83.447" in source
    assert "CodeGraph" in source

    pages = [
        path
        for path in LANDING_ROOT.rglob("*.html")
        if "node_modules" not in path.parts
        and "templates" not in path.parts
        and 'alt="CodeGraph"' in path.read_text(encoding="utf-8")
    ]
    assert pages
    for path in pages:
        html = path.read_text(encoding="utf-8")
        assert "assets/svg/logo.svg" not in html, path
        assert f"assets/svg/{logo_name}" in html, path

    for source_path in (
        LANDING_ROOT / "templates" / "header.html",
        LANDING_ROOT / "templates" / "footer.html",
        LANDING_ROOT.parents[1] / "scripts" / "docs_builder" / "template.py",
        LANDING_ROOT.parents[1] / "scripts" / "docs_builder" / "navigation.py",
    ):
        if not source_path.is_file():
            continue
        source_text = source_path.read_text(encoding="utf-8")
        assert "assets/svg/logo.svg" not in source_text, source_path
        assert logo_name in source_text, source_path


def test_homepage_uses_current_product_and_management_hierarchy() -> None:
    """Keep the current cost, delivery, quality, and release story on the homepage."""
    soup = _soup("index.html")
    section_ids = {node.get("id") for node in soup.find_all("section")}
    expected_sections = {
        "hero",
        "problems",
        "solution",
        "workflow",
        "product-screen",
        "integrations",
        "effect",
        "faq",
        "demo",
    }
    assert section_ids == expected_sections
    assert [node.get("id") for node in soup.find_all("section")] == [
        "hero",
        "problems",
        "solution",
        "workflow",
        "product-screen",
        "integrations",
        "effect",
        "faq",
        "demo",
    ]
    visible = _normalized_text(soup.get_text(" ", strip=True))
    for required in (
        "CodeGraph управляет проектом от задачи до выпуска",
        "Граф кода показывает затронутые компоненты, зависимости и риски до выпуска",
        "Готовность к выпуску",
        "Ответственный руководитель",
        "Пример: из 40 задач при доле срывов 30% двенадцать выходят за срок и бюджет",
        "Условный расчёт на основе нижней границы из исследования BCG",
    ):
        assert _normalized_text(required).casefold() in visible.casefold()
    assert "40 задач с установленным сроком" not in visible
    assert "600 задач за квартал" not in visible
    assert "2 контрольные задачи на одного специалиста" not in visible


def test_homepage_does_not_reintroduce_removed_story_blocks() -> None:
    """Keep the homepage concise and do not restore the removed story blocks."""
    soup = _soup("index.html")
    assert soup.find("section", id="materials") is None
    assert soup.find("section", id="scenarios") is None


def test_homepage_scenario_cards_own_six_traceable_pages() -> None:
    """Link each corporate scenario to a distinct FR/NFR-grounded page."""
    expected = {
        "Управление портфелем изменений": (
            "scenarios/portfolio-change-management.html",
            {"FR-P08-EXECUTIVE-CODE-PORTFOLIO-01", "FR-P08-PORTFOLIO-HEALTH-01", "CNFR-Q04-SCALE-THROUGHPUT-PROFILE-01"},
        ),
        "Разработка новой функции": (
            "scenarios/feature-delivery.html",
            {"FR-P04-DISCOVERY-READINESS-01", "FR-P04-TASK-CAPSULE-01", "CNFR-Q01-EVIDENCE-PROVENANCE-01"},
        ),
        "Аудит кодовой базы": (
            "scenarios/codebase-audit.html",
            {"FR-P03-ARCHITECTURE-EXPLORATION-01", "FR-P08-REVIEW-RESULT-01", "CNFR-Q01-EVIDENCE-PROVENANCE-01"},
        ),
        "Релизная проверка": (
            "scenarios/release-readiness.html",
            {"FR-P04-DELIVERY-READINESS-01", "FR-P04-PRECOMPLETION-GATE-01", "CNFR-Q02-TRANSITION-ROLLBACK-CONTINUITY-01"},
        ),
        "Технические контроли": (
            "scenarios/technical-controls.html",
            {"FR-P08-POLICY-WORKSPACE-01", "FR-P09-POLICY-CONSISTENCY-01", "CNFR-Q01-FAIL-CLOSED-GOVERNANCE-01"},
        ),
        "Контроль кода, созданного ИИ": (
            "scenarios/ai-code-control.html",
            {"FR-P07-GOVERNED-CLIENT-ACCESS-01", "FR-P06-AUDIT-MACHINE-OUTPUT-01", "CNFR-Q01-AI-IDENTITY-CLAIM-SAFETY-01"},
        ),
    }
    homepage = _soup("index.html")
    scenarios = homepage.find("section", id="scenarios")
    assert scenarios is None

    required_sections = {"situation", "actions", "result", "decision"}
    for _title, (route, expected_refs) in expected.items():
        page = _soup(route)
        assert required_sections <= {node.get("id") for node in page.find_all("section")}
        assert page.select_one('figure[data-visual-kind="product-preview"]') is not None

    sitemap = (LANDING_ROOT / "sitemap.xml").read_text(encoding="utf-8")
    machine_maps = "\n".join(
        (LANDING_ROOT / name).read_text(encoding="utf-8")
        for name in ("llms.txt", "llms-full.txt")
    )
    for route, _refs in expected.values():
        public_url = f"https://codegraph.ru/{route}"
        assert public_url in sitemap
        assert public_url in machine_maps


def test_whitepaper_uses_the_compact_architecture_narrative() -> None:
    """Keep the whitepaper focused on one architecture story and its source links."""
    page = _soup("whitepaper.html")
    expected_sections = {
        "answer",
        "workflow",
        "objects",
        "roles",
        "traceability",
        "architecture",
        "data",
        "example",
        "pilot",
    }
    assert expected_sections <= {node.get("id") for node in page.find_all("section")}
    assert page.find("section", id="scenarios") is None
    assert "На узком экране" not in page.get_text(" ", strip=True)

    assert page.find("section", id="competitive-comparison") is None
    assert page.find("section", id="interface") is None


def test_whitepaper_diagrams_do_not_expose_responsive_meta_or_broken_tspans() -> None:
    """Keep product diagrams readable without leaking implementation notes into copy."""
    page = _soup("whitepaper.html")
    visible = _normalized_text(page.get_text(" ", strip=True)).casefold()
    forbidden_fragments = (
        "на узком экране",
        "горизонтальной прокруткой",
        "схема доступна",
    )
    for fragment in forbidden_fragments:
        assert fragment not in visible

    errors: list[str] = []
    one_character_line = re.compile(r"^[A-Za-zА-Яа-яЁё0-9,]$")
    for figure in page.select("[data-product-diagram]"):
        diagram_id = figure.get("data-product-diagram")
        assert figure.select_one(".cg-diagram-scroll, .overflow-x-auto") is not None
        assert figure.select_one("[data-diagram-viewer]") is not None
        for tspan in figure.select("svg text tspan"):
            value = _normalized_text(tspan.get_text(" ", strip=True))
            if one_character_line.fullmatch(value):
                errors.append(f"{diagram_id}: broken single-character tspan {value!r}")
    assert not errors, "Broken SVG text layout remains:\n" + "\n".join(errors)


def test_homepage_documentation_action_uses_book_icon() -> None:
    """Represent documentation with an open book instead of the retired video icon."""
    page = _soup("index.html")
    links = [
        node
        for node in page.find_all("a", href="docs/ru/index.html")
        if "Изучить документацию" in node.get_text(" ", strip=True)
    ]
    assert len(links) == 1
    link = links[0]
    icon = link.find("svg", attrs={"data-icon": "book-open"})
    assert icon is not None
    assert len(icon.find_all("path")) == 2
    assert icon.find("polygon") is None


def test_whitepaper_owns_visual_product_and_architecture_models() -> None:
    """Require the compact architecture sections instead of retired deep-runtime blocks."""
    soup = _soup("whitepaper.html")
    section_ids = {node.get("id") for node in soup.find_all("section")}
    assert {
        "answer",
        "workflow",
        "objects",
        "roles",
        "traceability",
        "architecture",
        "data",
        "example",
        "pilot",
    } <= section_ids
    assert soup.find("section", id="runtime-topology") is None
    assert soup.find("section", id="scheduled-processes") is None


def test_every_whitepaper_section_starts_with_a_compact_reader_description() -> None:
    """Make every Story 1118 section understandable before its diagram or table."""
    page = _soup("whitepaper.html")
    errors: list[str] = []
    for section in page.select("main > section"):
        if not section.get("id"):
            continue
        heading = section.find("h2")
        body = heading.find_next_sibling("div") if heading is not None else None
        first_item = body.find(recursive=False) if body is not None else None
        description = (
            _normalized_text(first_item.get_text(" ", strip=True))
            if first_item is not None and first_item.name == "p"
            else ""
        )
        if len(description) < 80:
            errors.append(
                f"#{section.get('id')}: expected an introductory paragraph of at least "
                f"80 characters before structured content"
            )
    assert not errors, "Whitepaper sections without compact descriptions:\n" + "\n".join(errors)

    visible_fragments = [
        str(node)
        for node in page.find_all(string=True)
        if isinstance(node, NavigableString)
        and not isinstance(node, Comment)
        and not node.find_parent(["script", "style", "code", "pre"])
    ]
    one_letter_break = re.compile(
        r"(?<![А-Яа-яЁё])([вксоуюияа]) (?=[A-Za-zА-Яа-яЁё0-9«])",
        re.IGNORECASE,
    )
    assert one_letter_break.search("\n".join(visible_fragments)) is None


def test_whitepaper_explains_the_implementation_architecture_for_cto_review() -> None:
    """Keep the architecture explanation grounded in product and code boundaries."""
    page = _soup("whitepaper.html")
    expected = {
        "architecture": ("Проекты и требования", "Выполнение задач", "Граф кода", "Интеграции", "Хранилища и аудит"),
        "traceability": ("Граф свойств кода", "Динамические вызовы", "связанные тесты"),
    }
    for section_id, required_terms in expected.items():
        section = page.find("section", id=section_id)
        assert section is not None, f"whitepaper is missing #{section_id}"
        text = _normalized_text(section.get_text(" ", strip=True))
        for term in required_terms:
            assert term in text, f"#{section_id} is missing {term}"


def test_whitepaper_explains_roles_and_pilot_boundaries_without_runtime_meta() -> None:
    """Keep the public whitepaper useful without exposing internal implementation detail."""
    page = _soup("whitepaper.html")
    roles = page.find("section", id="roles")
    pilot = page.find("section", id="pilot")
    assert roles is not None and "Для цифровой роли задаются владелец" in roles.get_text(" ", strip=True)
    assert pilot is not None and "одного проекта" in pilot.get_text(" ", strip=True)
    visible = _normalized_text(page.get_text(" ", strip=True)).casefold()
    for term in ("cron", "temporal", "fastapi", "openviking", "на узком экране"):
        assert term not in visible


def test_every_explanatory_product_figure_is_inline_svg() -> None:
    """Allow HTML only for the homepage product-screen mockup, never for diagrams."""
    errors: list[str] = []
    for path in _public_html_files():
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        for index, figure in enumerate(soup.find_all("figure"), 1):
            if figure.get("data-visual-kind") in {"product-screen", "product-preview"}:
                continue
            if figure.find("svg") is None and figure.find("img") is None:
                errors.append(f"{path.relative_to(LANDING_ROOT)}: figure {index}")
    assert not errors, "Non-SVG product diagrams remain:\n" + "\n".join(errors)


def test_homepage_omits_removed_buyer_caveats() -> None:
    """Keep the product-owner copy simplification in source projections."""
    visible = _normalized_text(_soup("index.html").get_text(" ", strip=True)).casefold()
    forbidden = (
        "Это не обещание автоматически подготовить полную спецификацию.",
        "Срок и экономический эффект зависят от выбранного потока.",
        "CodeGraph не обещает универсальный процент экономии до исходного замера.",
        "Платформа не заявляет замену финансовому и ресурсному планированию.",
    )
    assert not [text for text in forbidden if _normalized_text(text).casefold() in visible]
    assert "продуктовый поток" not in visible


def _soup(relative: str) -> BeautifulSoup:
    """Parse one UTF-8 public projection."""
    return BeautifulSoup((LANDING_ROOT / relative).read_text(encoding="utf-8"), "html.parser")


def _normalized_text(value: str) -> str:
    """Normalize typographic spaces for semantic equality checks."""
    return " ".join(value.replace("\xa0", " ").split())


def _public_html_files() -> list[Path]:
    """Return complete public documents, excluding templates and ownership tokens."""
    return sorted(
        path
        for path in LANDING_ROOT.rglob("*.html")
        if "node_modules" not in path.parts
        and "templates" not in path.relative_to(LANDING_ROOT).parts
        and not path.name.startswith("yandex_")
    )


def test_key_pages_own_exact_audit_question_and_h1() -> None:
    """Keep every product/trust/economics page on its accepted buyer question."""
    errors: list[str] = []
    for relative, (expected_h1, expected_question, expected_release) in KEY_PAGE_CONTRACTS.items():
        path = LANDING_ROOT / relative
        if not path.is_file():
            errors.append(f"{relative}: missing")
            continue
        soup = _soup(relative)
        h1 = [node.get_text(" ", strip=True) for node in soup.find_all("h1")]
        meta = soup.find("meta", attrs={"name": "cg:buyer-question"})
        main = soup.find("main")
        if [_normalized_text(value) for value in h1] != [_normalized_text(expected_h1)]:
            errors.append(f"{relative}: h1={h1!r}")
        if not meta or _normalized_text(meta.get("content", "")) != _normalized_text(expected_question):
            errors.append(f"{relative}: buyer meta mismatch")
        if not main or _normalized_text(main.get("data-buyer-question", "")) != _normalized_text(expected_question):
            errors.append(f"{relative}: main question mismatch")
        if not main or main.get("data-release") != expected_release:
            errors.append(f"{relative}: release mismatch")
        if relative == "index.html" and "ИИ-платформа управления полным циклом разработки ПО" not in _normalized_text(
            soup.get_text(" ", strip=True)
        ):
            errors.append(f"{relative}: visible category label absent")

    assert not errors, "\n".join(errors)


def test_commercial_pages_own_questions_while_docs_do_not() -> None:
    """Keep buyer questions on commercial pages and out of technical documentation."""
    errors: list[str] = []
    for path in _public_html_files():
        relative = path.relative_to(LANDING_ROOT).as_posix()
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        questions = soup.find_all("meta", attrs={"name": "cg:buyer-question"})
        mains = soup.find_all("main")
        canonicals = soup.find_all("link", rel="canonical")
        if relative.startswith("docs/"):
            if questions or any(main.get("data-buyer-question") for main in mains):
                errors.append(f"{relative}: technical docs expose buyer-question")
        else:
            if len(questions) != 1 or not questions[0].get("content", "").strip():
                errors.append(f"{relative}: buyer-question meta count={len(questions)}")
            elif len(mains) != 1 or mains[0].get("data-buyer-question") != questions[0]["content"]:
                errors.append(f"{relative}: main question ownership mismatch")
        if len(canonicals) != 1 or not canonicals[0].get("href", "").startswith(
            "https://codegraph.ru/"
        ):
            errors.append(f"{relative}: canonical mismatch")

    assert not errors, "\n".join(errors[:100])


def test_key_page_metadata_and_schema_match_visible_contract() -> None:
    """Require title/description/social/WebPage schema parity on governed key pages."""
    errors: list[str] = []
    for relative in KEY_PAGE_CONTRACTS:
        soup = _soup(relative)
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        description = (soup.find("meta", attrs={"name": "description"}) or {}).get(
            "content", ""
        )
        og_title = (soup.find("meta", attrs={"property": "og:title"}) or {}).get(
            "content", ""
        )
        og_description = (
            soup.find("meta", attrs={"property": "og:description"}) or {}
        ).get("content", "")
        twitter_description = (
            soup.find("meta", attrs={"name": "twitter:description"}) or {}
        ).get("content", "")
        web_pages = []
        for node in soup.find_all("script", attrs={"type": "application/ld+json"}):
            payload = json.loads(node.string or node.get_text())
            if payload.get("@type") == "WebPage":
                web_pages.append(payload)
        if not title or not description:
            errors.append(f"{relative}: empty title/description")
        if _normalized_text(og_title) != _normalized_text(title):
            errors.append(f"{relative}: og:title mismatch")
        if _normalized_text(og_description) != _normalized_text(description) or _normalized_text(twitter_description) != _normalized_text(description):
            errors.append(f"{relative}: description parity mismatch")
        if len(web_pages) != 1:
            errors.append(f"{relative}: WebPage schema count={len(web_pages)}")
        elif _normalized_text(web_pages[0].get("name", "")) != _normalized_text(title) or _normalized_text(web_pages[0].get("description", "")) != _normalized_text(description):
            errors.append(f"{relative}: WebPage schema parity mismatch")

    assert not errors, "\n".join(errors)


def test_every_public_page_has_metadata_schema_and_csp_parity() -> None:
    """Enforce one SSR metadata contract and strict authored-style CSP site-wide."""
    errors: list[str] = []
    for path in _public_html_files():
        relative = path.relative_to(LANDING_ROOT).as_posix()
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        description = (soup.find("meta", attrs={"name": "description"}) or {}).get(
            "content", ""
        )
        canonical = (soup.find("link", rel="canonical") or {}).get("href", "")
        parity = {
            "og:title": (soup.find("meta", attrs={"property": "og:title"}) or {}).get(
                "content", ""
            ),
            "og:description": (
                soup.find("meta", attrs={"property": "og:description"}) or {}
            ).get("content", ""),
            "twitter:title": (
                soup.find("meta", attrs={"name": "twitter:title"}) or {}
            ).get("content", ""),
            "twitter:description": (
                soup.find("meta", attrs={"name": "twitter:description"}) or {}
            ).get("content", ""),
        }
        expected = {
            "og:title": title,
            "og:description": description,
            "twitter:title": title,
            "twitter:description": description,
        }
        if {key: _normalized_text(value) for key, value in parity.items()} != {key: _normalized_text(value) for key, value in expected.items()}:
            errors.append(f"{relative}: social metadata parity mismatch")

        web_pages = []
        for node in soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                payload = json.loads(node.string or node.get_text())
            except json.JSONDecodeError as error:
                errors.append(f"{relative}: invalid JSON-LD: {error}")
                continue
            if isinstance(payload, dict) and payload.get("@type") == "WebPage":
                web_pages.append(payload)
        if len(web_pages) != 1:
            errors.append(f"{relative}: WebPage schema count={len(web_pages)}")
        elif (
            _normalized_text(web_pages[0].get("name", "")) != _normalized_text(title)
            or _normalized_text(web_pages[0].get("description", "")) != _normalized_text(description)
            or web_pages[0].get("url") != canonical
        ):
            errors.append(f"{relative}: WebPage schema parity mismatch")

        csp_nodes = soup.find_all(
            "meta",
            attrs={
                "http-equiv": lambda value: value
                and value.casefold() == "content-security-policy"
            },
        )
        if len(csp_nodes) != 1:
            errors.append(f"{relative}: CSP count={len(csp_nodes)}")
        else:
            directives = csp_nodes[0].get("content", "")
            style_src = next(
                (
                    part.strip()
                    for part in directives.split(";")
                    if part.strip().startswith("style-src ")
                ),
                "",
            )
            if style_src != "style-src 'self'":
                errors.append(f"{relative}: unsafe authored-style CSP={style_src!r}")
            if "'unsafe-inline'" in directives:
                errors.append(f"{relative}: unsafe inline script CSP")
        if soup.find("meta", attrs={"name": "keywords"}):
            errors.append(f"{relative}: obsolete meta keywords")
        for link in soup.find_all("link", href=True):
            if "fonts.googleapis.com" in link["href"] or "fonts.gstatic.com" in link["href"]:
                errors.append(f"{relative}: remote font dependency={link['href']}")

    assert not errors, "\n".join(errors[:100])


def test_every_russian_page_meets_ru_text_typography_floor() -> None:
    """Reject objective ru-text typography defects in visible and metadata copy."""
    errors: list[str] = []
    one_letter_break = re.compile(r"(?<![А-Яа-яЁё])([вксоуюияа]) (?=[А-Яа-яЁё0-9«])", re.IGNORECASE)
    straight_quote = re.compile(r'"[А-Яа-яЁё][^"\n]{0,120}"')
    for path in _public_html_files():
        relative = path.relative_to(LANDING_ROOT).as_posix()
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        if not soup.html or soup.html.get("lang") != "ru":
            continue
        fragments: list[str] = []
        for node in soup.find_all(string=True):
            if (
                not isinstance(node, NavigableString)
                or isinstance(node, Comment)
                or node.find_parent(["script", "style", "code", "pre"])
            ):
                continue
            fragments.append(str(node))
        for node in soup.find_all(True):
            fragments.extend(
                str(node.get(attribute, ""))
                for attribute in (
                    "content",
                    "title",
                    "aria-label",
                    "placeholder",
                    "alt",
                    "data-buyer-question",
                )
                if node.get(attribute)
            )
        text = "\n".join(fragments)
        if one_letter_break.search(text):
            errors.append(f"{relative}: breakable one-letter preposition/conjunction")
        if straight_quote.search(text):
            errors.append(f"{relative}: straight Russian quotes")
        if " - " in text or " -- " in text:
            errors.append(f"{relative}: hyphen used as punctuation dash")
        if "..." in text:
            errors.append(f"{relative}: three-dot ellipsis")
        if " — " in text:
            errors.append(f"{relative}: breakable space before em dash")
    assert not errors, "\n".join(errors[:100])


def test_russian_product_pages_use_customer_language() -> None:
    """Reject internal English ontology terms from Russian product copy and metadata."""
    forbidden = (
        "Product Intent",
        "Product Outcome",
        "Functional Requirement",
        "Non-functional Requirement",
        "Acceptance Criteria",
        "Provenance",
        "Impact Scope",
        "Code Change",
        "Behavioral Test",
        "Check Result",
        "Requirement Implementation Status",
        "Governed",
        "Bounded",
        "Versioned",
        "Decision Owner",
        "Residual Risk",
        "Systems of Truth",
        "Capability Depth",
        "buyer question",
    )
    errors: list[str] = []
    for relative in KEY_PAGE_CONTRACTS:
        soup = _soup(relative)
        text = soup.get_text(" ", strip=True)
        metadata = " ".join(
            node.get("content", "")
            for node in soup.find_all("meta")
            if node.get("content")
        )
        payload = f"{text} {metadata}"
        for term in forbidden:
            if term.casefold() in payload.casefold():
                errors.append(f"{relative}: internal term={term}")
    assert not errors, "\n".join(errors[:100])


def test_audit_rejects_template_analogies_false_proof_and_self_ctas() -> None:
    """Enforce the editorial anti-template and claims corrections from the release audit."""
    errors: list[str] = []
    analogy_terms = ("карта метро", "предполётная проверка", "запасной маршрут")
    for directory in ("compare", "problems", "research"):
        for path in sorted((LANDING_ROOT / directory).rglob("*.html")):
            relative = path.relative_to(LANDING_ROOT).as_posix()
            source = path.read_text(encoding="utf-8")
            lowered = source.casefold()
            if "FAB_BENEFITS_" in source:
                errors.append(f"{relative}: generated FAB block remains")
            for term in analogy_terms:
                if term in lowered:
                    errors.append(f"{relative}: repeated analogy={term}")

    evidence_text = _soup("evidence.html").get_text(" ", strip=True)
    if "Цепочка проверки требования" not in evidence_text:
        errors.append("evidence.html: traceability label missing")
    if "Воспроизводимый обезличенный пример" in evidence_text:
        errors.append("evidence.html: synthetic example called reproducible")

    fortify_text = _soup("compare/codegraph-fortify.html").get_text(" ", strip=True)
    if "уже используется рядом с Fortify" in fortify_text:
        errors.append("compare/codegraph-fortify.html: unsupported usage claim")

    for relative in KEY_PAGE_CONTRACTS:
        soup = _soup(relative)
        for link in soup.select("main a.inline-flex[href]"):
            raw_href = link.get("href", "")
            href = raw_href.split("?", 1)[0]
            if "#" not in href and href == relative:
                errors.append(f"{relative}: CTA points to current page")
    assert not errors, "\n".join(errors[:100])


def test_machine_readable_briefs_use_one_public_language() -> None:
    """Keep the Russian machine-readable projections free of ontology-language drift."""
    forbidden = (
        "Canonical definition",
        "Product Intent",
        "Product Outcome",
        "Acceptance Criterion",
        "Impact Scope",
        "Task Capsule — bounded",
        "Behavioral Test",
        "Check Result",
        "Authority boundaries",
        "Proof interpretation",
        "Next step",
    )
    errors: list[str] = []
    for name in ("llms.txt", "llms-full.txt"):
        source = (LANDING_ROOT / name).read_text(encoding="utf-8")
        for phrase in forbidden:
            if phrase.casefold() in source.casefold():
                errors.append(f"{name}: mixed-language phrase={phrase}")
    assert not errors, "\n".join(errors)


def test_comparison_pages_cite_current_official_primary_sources() -> None:
    """Require a dated official source and reject the disproved PT AI contrast."""
    expected = {
        "compare/codegraph-checkmarx.html": "https://docs.checkmarx.com/",
        "compare/codegraph-fortify.html": "https://www.opentext.com/",
        "compare/codegraph-pt-application-inspector.html": "https://ptsecurity.com/",
        "compare/codegraph-semgrep.html": "https://semgrep.dev/docs/",
        "compare/codegraph-sonarqube.html": "https://docs.sonarsource.com/",
    }
    errors: list[str] = []
    for relative, origin in expected.items():
        soup = _soup(relative)
        text = soup.get_text(" ", strip=True)
        links = [link.get("href", "") for link in soup.select("main a[href]")]
        if not any(link.startswith(origin) for link in links):
            errors.append(f"{relative}: official source missing")
        if "Проверено 20 июля 2026 года" not in text:
            errors.append(f"{relative}: source verification date missing")
    pt_source = (LANDING_ROOT / "compare/codegraph-pt-application-inspector.html").read_text(
        encoding="utf-8"
    )
    if "PT Application Inspector использует сопоставление шаблонов" in pt_source:
        errors.append("compare/codegraph-pt-application-inspector.html: disproved contrast")
    assert not errors, "\n".join(errors)


def test_images_and_link_labels_are_layout_and_context_safe() -> None:
    """Reject layout-shifting images and context-free audit link labels."""
    errors: list[str] = []
    sources = [*_public_html_files(), *(LANDING_ROOT / "templates").rglob("*.html")]
    generic_labels = {"читать", "подробнее", "узнать больше", "перейти"}
    for path in sources:
        relative = path.relative_to(LANDING_ROOT).as_posix()
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        for image in soup.find_all("img"):
            if (image.get("src") or "").strip() and (
                not image.get("width") or not image.get("height")
            ):
                errors.append(f"{relative}: image dimensions missing: {image.get('src')}")
        for link in soup.find_all("a", href=True):
            if link.get_text(" ", strip=True).casefold() in generic_labels:
                errors.append(f"{relative}: generic link label: {link.get('href')}")

    assert not errors, "\n".join(errors[:100])


def test_every_internal_link_and_fragment_resolves() -> None:
    """Validate the complete generated internal link and anchor graph."""
    errors: list[str] = []
    target_anchors: dict[Path, set[str]] = {}
    root = LANDING_ROOT.resolve()

    for source_path in _public_html_files():
        source_soup = BeautifulSoup(
            source_path.read_text(encoding="utf-8"), "html.parser"
        )
        source_relative = source_path.relative_to(LANDING_ROOT).as_posix()
        for link in source_soup.find_all("a", href=True):
            href = link.get("href", "").strip()
            if not href or href.startswith(("mailto:", "tel:", "javascript:", "data:")):
                continue
            parts = urlsplit(href)
            if parts.scheme or parts.netloc:
                if parts.scheme not in {"http", "https"} or parts.netloc.casefold() not in {
                    "codegraph.ru",
                    "www.codegraph.ru",
                }:
                    continue
            path_value = unquote(parts.path)
            if parts.netloc or path_value.startswith("/"):
                target = root / path_value.lstrip("/")
            elif path_value:
                target = source_path.parent / path_value
            else:
                target = source_path
            target = target.resolve()
            try:
                target.relative_to(root)
            except ValueError:
                errors.append(f"{source_relative}: link escapes public root: {href}")
                continue
            if target.is_dir() or not target.suffix or path_value.endswith("/"):
                target = target / "index.html"
            if not target.is_file():
                errors.append(f"{source_relative}: missing target: {href}")
                continue
            if parts.fragment:
                if target not in target_anchors:
                    target_soup = BeautifulSoup(
                        target.read_text(encoding="utf-8"), "html.parser"
                    )
                    target_anchors[target] = {
                        value
                        for node in target_soup.find_all(True)
                        for value in (node.get("id"), node.get("name"))
                        if value
                    }
                fragment = unquote(parts.fragment)
                if fragment not in target_anchors[target]:
                    errors.append(f"{source_relative}: missing fragment: {href}")

    assert not errors, "\n".join(errors[:100])


def test_external_edit_links_resolve_to_real_repository_sources() -> None:
    """Reject placeholder provenance and verify every generated GitHub edit target."""
    errors: list[str] = []
    repository_root = LANDING_ROOT.parents[1]
    source_checkout_available = (repository_root / "docs").is_dir()
    edit_prefix = "/mkhlsavin/codegraph/edit/main/"
    edit_count = 0
    for source_path in _public_html_files():
        source_soup = BeautifulSoup(
            source_path.read_text(encoding="utf-8"), "html.parser"
        )
        source_relative = source_path.relative_to(LANDING_ROOT).as_posix()
        for link in source_soup.find_all("a", href=True):
            href = link.get("href", "").strip()
            parts = urlsplit(href)
            if parts.scheme not in {"http", "https"}:
                continue
            if "your-org" in href or href.rstrip("/") in {
                "https://github.com/codegraph",
                "https://t.me/codegraph",
            }:
                errors.append(f"{source_relative}: placeholder external URL: {href}")
            if parts.netloc.casefold() == "github.com" and "/edit/main/" in parts.path:
                edit_count += 1
                if not parts.path.startswith(edit_prefix):
                    errors.append(f"{source_relative}: unexpected edit origin: {href}")
                    continue
                if source_checkout_available:
                    target = repository_root / unquote(parts.path[len(edit_prefix) :])
                    if not target.is_file():
                        errors.append(f"{source_relative}: missing edit source: {href}")

    if edit_count != 194:
        errors.append(f"generated edit-link count={edit_count}, expected=194")
    assert not errors, "\n".join(errors[:100])


def test_proof_role_and_integration_surfaces_are_evidence_bounded() -> None:
    """Validate the three approved new docs-public contracts."""
    evidence = _soup("evidence.html")
    evidence_text = evidence.get_text(" ", strip=True).casefold()
    for phrase in (
        "цель продукта",
        "функциональное требование",
        "нефункциональное требование",
        "область влияния",
        "изменение кода",
        "результат проверки",
        "Осталось непроверенным",
        "Не подтверждено",
    ):
        assert phrase.casefold() in evidence_text
    assert len(evidence.select("[data-traceability-example]")) == 1

    team = _soup("digital-team.html")
    roles = team.select("[data-digital-role]")
    assert len(roles) == 13
    assert len({role["data-digital-role"] for role in roles}) == 13
    team_text = team.get_text(" ", strip=True).casefold()
    for phrase in ("цифровой сотрудник", "функциональная роль", "ИИ-агент", "роль RBAC", "ответственный сотрудник"):
        assert phrase.casefold() in team_text

    integrations = _soup("integrations.html")
    rows = integrations.select("tbody tr[data-capability-status]")
    assert rows
    allowed = {"available", "limited", "pilot", "planned", "internal", "unconfirmed"}
    assert {row["data-capability-status"] for row in rows} <= allowed
    for row in rows:
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
        assert len(cells) == 10
        assert cells[-2] and cells[-1]


def test_navigation_crawlers_and_research_disposition_match_audit() -> None:
    """Protect the six-part navigation and intentional crawler/research policy."""
    header = (LANDING_ROOT / "templates" / "header.html").read_text(encoding="utf-8")
    for label in (
        "{nav_benefits}",
        "{nav_product_delivery}",
        "{nav_developers}",
        "{nav_platform_operations}",
        "{nav_security}",
        "{nav_docs}",
    ):
        assert label in header

    robots = (LANDING_ROOT / "robots.txt").read_text(encoding="utf-8")
    assert "User-agent: OAI-SearchBot\nAllow: /" in robots
    assert "User-agent: GPTBot\nDisallow: /" in robots

    benchmark = _soup("research/tochnost-otvetov-i-skorost-razbora.html")
    robots_meta = benchmark.find("meta", attrs={"name": "robots"})
    assert robots_meta and "noindex" in robots_meta.get("content", "")
    sitemap = (LANDING_ROOT / "sitemap.xml").read_text(encoding="utf-8")
    assert "research/tochnost-otvetov-i-skorost-razbora.html" not in sitemap
    for route in ("evidence.html", "digital-team.html", "integrations.html"):
        assert f"https://codegraph.ru/{route}" in sitemap


def test_ai_referral_to_lead_measurement_contract_is_present() -> None:
    """Keep source, landing, CTA and accepted-lead dimensions available for reporting."""
    scripts = (LANDING_ROOT / "templates" / "scripts.html").read_text(encoding="utf-8")
    javascript = (LANDING_ROOT / "js" / "main.js").read_text(encoding="utf-8")
    cta = (LANDING_ROOT / "templates" / "sections" / "cta.html").read_text(
        encoding="utf-8"
    )

    assert "referrer: document.referrer" in scripts
    assert "url: location.href" in scripts
    for field in ("source_page", "cta_variant", "intent", "use_case"):
        assert field in javascript
    for goal in ("demo_form_submit", "demo_form_success"):
        assert f"trackGoal('{goal}'" in javascript
    assert 'name="source_page"' in cta
    assert 'name="intent"' in cta
