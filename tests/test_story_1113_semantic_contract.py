"""Fail-closed semantic contracts for the complete Story 1113 public-site rewrite."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup


LANDING_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_CATEGORY = (
    "CodeGraph — платформа сквозной прослеживаемости и доказательного исполнения "
    "требований в PDLC."
)
KEY_PAGE_CONTRACTS = {
    "index.html": (
        "От продуктового замысла до доказанной реализации",
        "Что такое CodeGraph и почему он нужен CPO и CTO?",
        "release-1",
    ),
    "whitepaper.html": (
        "Сквозная прослеживаемость требований и доказательное исполнение в PDLC",
        "Как устроена каноническая модель продукта?",
        "release-1",
    ),
    "product-delivery.html": (
        "От продуктового замысла до доказанной реализации",
        "Как Product Intent превращается в requirements и доказанную реализацию?",
        "release-1",
    ),
    "evidence.html": (
        "Как CodeGraph доказывает реализацию требований",
        "Чем подтверждается реализация каждого требования?",
        "release-2",
    ),
    "digital-team.html": (
        "Цифровая команда: роли, полномочия и границы",
        "Кто выполняет работу и в каких границах?",
        "release-2",
    ),
    "ai-engineering.html": (
        "Как доказать, что AI-код реализует требования",
        "Чем governed requirement-bound work отличается от обычной AI-разработки?",
        "release-2",
    ),
    "cpg.html": (
        "Как CodeGraph связывает требование с затронутым кодом и тестами",
        "Как определяется влияние требования на код и тесты?",
        "release-2",
    ),
    "security.html": (
        "Как требование безопасности проходит до решения о риске",
        "Как security requirement проходит до решения о риске?",
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
        "Интеграции CodeGraph: подтверждённая глубина подключения",
        "Какая capability-depth реально доступна?",
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


def _soup(relative: str) -> BeautifulSoup:
    """Parse one UTF-8 public projection."""
    return BeautifulSoup((LANDING_ROOT / relative).read_text(encoding="utf-8"), "html.parser")


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
        if h1 != [expected_h1]:
            errors.append(f"{relative}: h1={h1!r}")
        if not meta or meta.get("content") != expected_question:
            errors.append(f"{relative}: buyer meta mismatch")
        if not main or main.get("data-buyer-question") != expected_question:
            errors.append(f"{relative}: main question mismatch")
        if not main or main.get("data-release") != expected_release:
            errors.append(f"{relative}: release mismatch")
        if CANONICAL_CATEGORY not in soup.get_text(" ", strip=True):
            errors.append(f"{relative}: canonical category absent from visible HTML")

    assert not errors, "\n".join(errors)


def test_every_public_document_has_one_question_owner_and_canonical() -> None:
    """Require one explicit page question and canonical URL on every public document."""
    errors: list[str] = []
    for path in _public_html_files():
        relative = path.relative_to(LANDING_ROOT).as_posix()
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        questions = soup.find_all("meta", attrs={"name": "cg:buyer-question"})
        mains = soup.find_all("main")
        canonicals = soup.find_all("link", rel="canonical")
        if len(questions) != 1 or not questions[0].get("content", "").strip():
            errors.append(f"{relative}: buyer-question meta count={len(questions)}")
            continue
        if len(mains) != 1 or mains[0].get("data-buyer-question") != questions[0]["content"]:
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
        if og_title != title:
            errors.append(f"{relative}: og:title mismatch")
        if og_description != description or twitter_description != description:
            errors.append(f"{relative}: description parity mismatch")
        if len(web_pages) != 1:
            errors.append(f"{relative}: WebPage schema count={len(web_pages)}")
        elif web_pages[0].get("name") != title or web_pages[0].get("description") != description:
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
        if parity != expected:
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
            web_pages[0].get("name") != title
            or web_pages[0].get("description") != description
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

    assert not errors, "\n".join(errors[:100])


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
    evidence_text = evidence.get_text(" ", strip=True)
    for phrase in (
        "Product Intent",
        "Functional Requirement",
        "Non-functional Requirement",
        "Impact Scope",
        "Code Change",
        "Check Result",
        "Осталось непроверенным",
        "Не подтверждено",
    ):
        assert phrase in evidence_text
    assert len(evidence.select("[data-traceability-example]")) == 1

    team = _soup("digital-team.html")
    roles = team.select("[data-digital-role]")
    assert len(roles) == 13
    assert len({role["data-digital-role"] for role in roles}) == 13
    team_text = team.get_text(" ", strip=True)
    for phrase in ("Digital employee", "Functional role", "AI agent", "RBAC role", "Human owner"):
        assert phrase in team_text

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
