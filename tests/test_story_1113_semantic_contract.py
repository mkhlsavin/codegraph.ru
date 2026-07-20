"""Fail-closed semantic contracts for the complete Story 1113 public-site rewrite."""

from __future__ import annotations

import json
from pathlib import Path
import re
import struct
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString


LANDING_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_CATEGORY = (
    "CodeGraph — платформа управления разработкой цифровых продуктов."
)
KEY_PAGE_CONTRACTS = {
    "index.html": (
        "Управляйте разработкой — от продуктовой инициативы до готовности к выпуску",
        "Как связать продуктовый и инженерный циклы разработки?",
        "release-1",
    ),
    "whitepaper.html": (
        "Как CodeGraph связывает PDLC, SDLC и портфель продуктов",
        "Как устроен управляющий контур CodeGraph?",
        "release-1",
    ),
    "product-delivery.html": (
        "Портфель и проекты: от инициативы до готовности",
        "Как видеть основания статуса каждого проекта?",
        "release-1",
    ),
    "evidence.html": (
        "Какими данными подтверждается реализация требований",
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
        "Как CodeGraph связывает требование с затронутым кодом и тестами",
        "Как определяется влияние требования на код и тесты?",
        "release-2",
    ),
    "security.html": (
        "Как требование безопасности проходит до решения о риске",
        "Как требование безопасности проходит до решения о риске?",
        "release-3",
    ),
    "compliance.html": (
        "Граница данных, журнал решений и доказательства технических контролей",
        "Где данные и какие технические контроли подтверждены?",
        "release-3",
    ),
    "platform-operations.html": (
        "Как CodeGraph встраивается в текущий стек и сохраняет управляемое состояние",
        "Как система развёртывается, интегрируется и восстанавливается?",
        "release-3",
    ),
    "integrations.html": (
        "Интеграции CodeGraph: поддерживаемые операции и ограничения",
        "Какие операции поддерживает каждая интеграция?",
        "release-3",
    ),
    "productivity.html": (
        "Как управлять соответствием реализации требованиям",
        "Как CTO управляет соответствием реализации требованиям?",
        "release-4",
    ),
    "business-efficiency.html": (
        "Как считать стоимость разрывов между требованиями и реализацией",
        "Как измерить эффект пилота?",
        "release-4",
    ),
}


def test_social_previews_use_current_brand_and_positioning() -> None:
    """Keep every social card on the current category and cache-busted assets."""
    expected = {
        "index.html": (
            "og-codegraph-platform-20260720.png",
            "CodeGraph — платформа управления разработкой цифровых продуктов",
        ),
        "whitepaper.html": (
            "og-codegraph-whitepaper-20260720.png",
            "Техническое описание CodeGraph: портфель, PDLC, SDLC и готовность к выпуску",
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
        assert 'docs" / "business" / "brand" / "logo-golden-ratio-preview.png' in generator
        for stale_claim in ("AI-копилот", "Hybrid RAG", "21 сценарий", "95.6% точность"):
            assert stale_claim not in generator


def test_homepage_restores_product_scale_and_management_hierarchy() -> None:
    """Keep portfolio, architecture, audits and release readiness in the category story."""
    soup = _soup("index.html")
    section_ids = {node.get("id") for node in soup.find_all("section")}
    expected_sections = {
        "problem",
        "solution",
        "digital-team",
        "portfolio",
        "architecture",
        "scenarios",
        "results",
        "categories",
        "pilot",
    }
    assert expected_sections <= section_ids
    visible = _normalized_text(soup.get_text(" ", strip=True))
    for required in (
        "цикл разработки цифрового продукта (PDLC)",
        "жизненный цикл разработки программного обеспечения (SDLC)",
        "Портфель цифровых продуктов",
        "Проверки и аудиты",
        "Готовность к выпуску",
        "решение ответственного архитектора",
    ):
        assert _normalized_text(required).casefold() in visible.casefold()


def test_homepage_material_cards_link_to_matching_pages() -> None:
    """Make every next-step material card an unambiguous navigation link."""
    soup = _soup("index.html")
    materials = soup.find("section", id="materials")
    assert materials is not None

    actual = {
        link.find("h3").get_text(" ", strip=True): link.get("href")
        for link in materials.select("a[href]")
        if link.find("h3") is not None
    }
    assert actual == {
        "Техническое описание": "whitepaper.html",
        "Подтверждения": "evidence.html",
        "Интеграции": "integrations.html",
    }


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
    assert scenarios is not None
    actual = {
        link.find("h3").get_text(" ", strip=True): link.get("href")
        for link in scenarios.select("a[href]")
        if link.find("h3") is not None
    }
    assert actual == {title: route for title, (route, _refs) in expected.items()}

    required_sections = {"situation", "actions", "advantages", "benefits", "metrics", "human-decision", "requirement-basis"}
    for _title, (route, expected_refs) in expected.items():
        page = _soup(route)
        assert required_sections <= {node.get("id") for node in page.find_all("section")}
        refs = {node.get("data-requirement-ref") for node in page.select("[data-requirement-ref]")}
        assert expected_refs <= refs
        assert any(ref and ref.startswith("FR-") for ref in refs)
        assert any(ref and ref.startswith("CNFR-") for ref in refs)

    asserted_refs = {ref for _route, refs in expected.values() for ref in refs}
    projection = json.loads(
        (LANDING_ROOT / "scenarios" / "requirement-basis.json").read_text(encoding="utf-8")
    )
    assert asserted_refs == set(projection["requirement_ids"])

    repository_root = LANDING_ROOT.parents[1]
    registry_dir = repository_root / "docs" / "development" / "maps"
    if registry_dir.is_dir():
        registry_ids: set[str] = set()
        for registry in projection["source_registries"]:
            payload = json.loads((registry_dir / registry).read_text(encoding="utf-8"))
            registry_ids.update(
                item["requirement_id"] for item in payload["final_requirements"]
            )
        assert asserted_refs <= registry_ids

    sitemap = (LANDING_ROOT / "sitemap.xml").read_text(encoding="utf-8")
    machine_maps = "\n".join(
        (LANDING_ROOT / name).read_text(encoding="utf-8")
        for name in ("llms.txt", "llms-full.txt")
    )
    for route, _refs in expected.values():
        public_url = f"https://codegraph.ru/{route}"
        assert public_url in sitemap
        assert public_url in machine_maps


def test_whitepaper_links_scenarios_and_shows_scalable_product_ui() -> None:
    """Connect the whitepaper narrative to scenario details and real UI screens."""
    page = _soup("whitepaper.html")
    scenarios = page.find("section", id="scenarios")
    assert scenarios is not None
    assert {link.get("href") for link in scenarios.select("a[href]")} == {
        "scenarios/portfolio-change-management.html",
        "scenarios/feature-delivery.html",
        "scenarios/codebase-audit.html",
        "scenarios/release-readiness.html",
        "scenarios/technical-controls.html",
        "scenarios/ai-code-control.html",
    }

    interface = page.find("section", id="interface")
    assert interface is not None
    screenshots = interface.select('figure[data-visual-kind="ui-screenshot"]')
    assert len(screenshots) == 4
    assert {figure.find("img")["src"] for figure in screenshots} == {
        "assets/ui/portfolio-overview-20260720.png",
        "assets/ui/project-delivery-20260720.png",
        "assets/ui/compliance-center-20260720.png",
        "assets/ui/digital-employee-handoff-map-20260720.png",
    }
    for figure in screenshots:
        link = figure.find("a", href=True)
        image = figure.find("img")
        caption = figure.find("figcaption")
        assert link is not None and link.get("target") == "_blank"
        assert image is not None and image.get("src") == link.get("href")
        assert image.get("alt") and image.get("width") and image.get("height")
        assert image.get("loading") == "lazy"
        assert caption is not None and caption.get_text(" ", strip=True)
        assert (LANDING_ROOT / image["src"]).is_file()


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
    """Require the accepted visual models instead of a flat terminology table."""
    soup = _soup("whitepaper.html")
    section_ids = {node.get("id") for node in soup.find_all("section")}
    assert {
        "pdlc-sdlc",
        "portfolio-model",
        "workflow",
        "team-map",
        "traceability",
        "readiness",
        "architecture",
        "portfolio-audit-release",
        "security-compliance",
        "scenarios",
        "pilot",
    } <= section_ids
    figures = soup.find_all("figure", attrs={"data-product-diagram": True})
    assert len(figures) == 9
    for figure in figures:
        svg = figure.find("svg", attrs={"role": "img"})
        assert svg is not None
        labelled_by = str(svg.get("aria-labelledby") or "").split()
        assert len(labelled_by) == 2
        assert all(soup.find(id=identifier) is not None for identifier in labelled_by)
        assert max((len(text.find_all("tspan")) for text in svg.find_all("text")), default=0) <= 12


def test_every_explanatory_product_figure_is_inline_svg() -> None:
    """Allow HTML only for the homepage product-screen mockup, never for diagrams."""
    errors: list[str] = []
    for path in _public_html_files():
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        for index, figure in enumerate(soup.find_all("figure"), 1):
            if figure.get("data-visual-kind") == "product-screen":
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
        if relative == "index.html" and _normalized_text(CANONICAL_CATEGORY) not in _normalized_text(soup.get_text(" ", strip=True)):
            errors.append(f"{relative}: canonical category absent from visible HTML")

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
    if "Иллюстративный обезличенный пример" not in evidence_text:
        errors.append("evidence.html: illustrative label missing")
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

    if edit_count != 193:
        errors.append(f"generated edit-link count={edit_count}, expected=193")
    assert not errors, "\n".join(errors[:100])


def test_proof_role_and_integration_surfaces_are_evidence_bounded() -> None:
    """Validate the three approved new docs-public contracts."""
    evidence = _soup("evidence.html")
    evidence_text = evidence.get_text(" ", strip=True).casefold()
    for phrase in (
        "продуктовый замысел",
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
    for label in ("Продукт", "Для CPO", "Для CTO", "Как работает", "Доверие", "Документация"):
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
