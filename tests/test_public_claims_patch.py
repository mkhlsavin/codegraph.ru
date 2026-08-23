"""Regression checks for the immediate public-claims patch."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

LANDING_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_CATEGORY = json.loads((LANDING_ROOT / "site_content.json").read_text(encoding="utf-8"))[
    "canonical_category"
]
FOOTER_DESCRIPTOR = CANONICAL_CATEGORY.split("—", 1)[1].strip()

FORBIDDEN_MARKETING_PATTERNS = {
    "scenario_count": re.compile(r"\b(?:21|36)\s+(?:сценар\w*|карточ\w*)", re.IGNORECASE),
    "unsupported_quality_score": re.compile(r"(?<!\d)0[,.]83(?!\d)"),
    "unsupported_30ms": re.compile(r"(?<!\d)30\s*мс\b", re.IGNORECASE),
    "unsupported_71s": re.compile(r"(?<!\d)71\s*(?:с|сек\w*)\b", re.IGNORECASE),
    "unsupported_false_positive_rate": re.compile(
        r"(?<!\d)12\s*%[^\n]{0,80}ложн\w*\s+срабатыван", re.IGNORECASE
    ),
    "unsupported_cve_detection": re.compile(r"(?<!\d)100\s*%[^\n]{0,80}CVE", re.IGNORECASE),
    "unsupported_23ms": re.compile(r"(?<!\d)23\s*мс\b", re.IGNORECASE),
    "unsupported_indexing_sla": re.compile(r"(?:1M|1\s*млн)[^\n]{0,100}30\s*мин", re.IGNORECASE),
    "unsupported_availability": re.compile(r"(?<!\d)99[,.]9\s*%(?!\d)"),
    "unsupported_support_sla": re.compile(
        r"(?:4\s*/\s*24\s*/\s*72|время\s+реакции:\s*(?:4|24|72)\s*час)",
        re.IGNORECASE,
    ),
    "unsupported_fixed_rollout": re.compile(
        r"разв[её]ртыван\w*\s*[—:-]\s*1\s*[-–]\s*2\s*дн", re.IGNORECASE
    ),
    "unsupported_fixed_pilot": re.compile(
        r"до\s+3\s+(?:выбранных\s+)?сценар\w*[^\n]{0,80}" r"4\s*[-–]\s*8\s*нед",
        re.IGNORECASE,
    ),
    "unsupported_economics_example": re.compile(
        r"(?:17[,.]25\s*млн|2\s*415\s*(?:час|×)|6[,.]04\s*млн)",
        re.IGNORECASE,
    ),
    "unsupported_pilot_threshold": re.compile(
        r"(?:порог\s*20\s*%|20\s*[-–]\s*40\s*инженер|" r"35\s*%[^\n]{0,80}(?:час|эффект))",
        re.IGNORECASE,
    ),
    "unsupported_pilot_timeline": re.compile(
        r"(?:недел[ия]\s*[136](?:\s*[-–]\s*[25])?|"
        r"за\s+пять\s+рабочих\s+дней|через\s+шесть\s+недель)",
        re.IGNORECASE,
    ),
    "unsupported_commercial_price": re.compile(
        r"(?:от\s*7\s*млн\s*руб|Fortify\s*\(~?15\s*млн)",
        re.IGNORECASE,
    ),
    "unsupported_false_positive_effort": re.compile(r"512\s*час", re.IGNORECASE),
    "unsupported_contact_response_time": re.compile(r"в\s+течение\s+24\s+час", re.IGNORECASE),
    "unsupported_internal_scale": re.compile(r"(?:75K\+\s*метод|3[,.]4M\s*узл)", re.IGNORECASE),
    "unsupported_f1_uplift": re.compile(r"(?<!\d)33[,.]6\s*%\s*F1", re.IGNORECASE),
    "unsupported_graph_latency": re.compile(r"(?<!\d)2\s*[-–]\s*3\s*мс\b", re.IGNORECASE),
    "quarter_only_roadmap": re.compile(r"\bQ[23]\s*2026\b", re.IGNORECASE),
    "absolute_data_egress": re.compile(
        r"(?:данные\s+никуда\s+не\s+уходят|код\s+не\s+переда[её]тся|"
        r"внешн(?:ий|его)\s+трафик(?:а)?\s+(?:нет|отсутствует))",
        re.IGNORECASE,
    ),
    "absolute_compliance": re.compile(r"обеспечивает\s+соответствие\s+ГОСТ", re.IGNORECASE),
    "absolute_findings": re.compile(r"только\s+реальные\s+уязвимости", re.IGNORECASE),
    "absolute_determinism": re.compile(
        r"(?:весь\s+анализ\s+детерминирован|сам\s+анализ\s*[—-]\s*"
        r"детерминирован|полная\s+согласованность)",
        re.IGNORECASE,
    ),
}


def _public_projection_files() -> list[Path]:
    """Return every public HTML, template, script and LLM projection."""
    files: set[Path] = {
        path
        for path in LANDING_ROOT.rglob("*.html")
        if "node_modules" not in path.parts and not path.name.startswith("yandex_")
    }
    files.update(
        path for path in (LANDING_ROOT / "js").rglob("*.js") if "node_modules" not in path.parts
    )
    files.update(LANDING_ROOT.glob("llms*.txt"))
    return sorted(files)


def _line_number(text: str, offset: int) -> int:
    """Return the one-based line number for a regex match offset."""
    return text.count("\n", 0, offset) + 1


def test_sitewide_claims_patch_has_no_forbidden_public_claims() -> None:
    """Reject every unsupported P0 claim in all public projections, including docs."""
    findings: list[str] = []
    for path in _public_projection_files():
        text = path.read_text(encoding="utf-8")
        for claim_name, pattern in FORBIDDEN_MARKETING_PATTERNS.items():
            for match in pattern.finditer(text):
                relative = path.relative_to(LANDING_ROOT)
                findings.append(
                    f"{relative}:{_line_number(text, match.start())}: "
                    f"{claim_name}: {match.group(0)!r}"
                )

    assert not findings, "Forbidden public claims remain:\n" + "\n".join(findings)


def test_home_and_shared_sources_use_the_canonical_category() -> None:
    """Keep the category on the homepage and shared sources without serial hero repetition."""
    surfaces = (
        LANDING_ROOT / "index.html",
        LANDING_ROOT / "templates" / "head.html",
        LANDING_ROOT / "templates" / "footer.html",
    )
    missing_category = [
        str(path.relative_to(LANDING_ROOT))
        for path in surfaces[:2]
        if CANONICAL_CATEGORY.replace(" ", "")
        not in path.read_text(encoding="utf-8").replace(" ", "").replace("\xa0", "")
    ]
    footer = surfaces[2].read_text(encoding="utf-8").replace(" ", "").replace("\xa0", "")

    assert not missing_category, f"Canonical category is missing from: {missing_category}"
    assert "{footer_tagline}" in footer, "Footer tagline placeholder is missing"


def test_public_ctas_do_not_route_through_legacy_index_file() -> None:
    """Keep every public CTA on the canonical root document."""
    forbidden = ("index.html#demo", "../index.html#demo")
    findings = []
    for path in _public_projection_files():
        text = path.read_text(encoding="utf-8")
        if any(value in text for value in forbidden):
            findings.append(str(path.relative_to(LANDING_ROOT)))
    assert not findings, "Legacy homepage CTA targets remain: " + ", ".join(findings)


def test_demo_route_redirects_to_the_canonical_home_form() -> None:
    """Keep the externally shared /demo URL working on static GitHub Pages."""
    demo_page = (LANDING_ROOT / "demo" / "index.html").read_text(encoding="utf-8")

    assert 'http-equiv="refresh" content="0; url=/#demo"' in demo_page
    assert '<meta name="robots" content="noindex,follow">' in demo_page
    assert '<link rel="canonical" href="https://codegraph.ru/">' in demo_page
    assert 'href="/#demo"' in demo_page
    assert "<h1" in demo_page


def test_privacy_page_has_real_security_link_and_canonical_cta() -> None:
    """Reject escaped markup and obsolete documentation paths in privacy.html."""
    privacy = (LANDING_ROOT / "privacy.html").read_text(encoding="utf-8")
    assert "&lt;a" not in privacy
    assert "/документация/" not in privacy
    assert 'href="/docs/ru/enterprise/SECURITY_BRIEF.html"' in privacy
    assert 'href="/#demo"' in privacy


def test_benchmark_page_is_a_reproducible_template_until_evidence_exists() -> None:
    """Prevent a methodology page from quietly reintroducing unsupported results."""
    benchmark = (LANDING_ROOT / "research" / "tochnost-otvetov-i-skorost-razbora.html").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "Высокое качество на опубликованном наборе",
        "Ускорение отдельных задач на опубликованном стенде",
        "Ускорение по сравнению с Joern на опубликованном стенде",
        "153/160",
    )
    assert not [phrase for phrase in forbidden if phrase in benchmark]
    for field in (
        "Набор данных",
        "Протокол",
        "Среда",
        "Исходный результат",
        "Расчёт",
        "Ограничения",
        "Контрольные суммы",
    ):
        assert field in benchmark


def test_comparison_rows_link_to_their_source_scope() -> None:
    """Keep competitor claims navigable to the dated primary-source scope."""
    comparison_paths = sorted((LANDING_ROOT / "compare").glob("*.html"))
    assert comparison_paths
    for path in comparison_paths:
        source = path.read_text(encoding="utf-8")
        assert 'id="source-scope"' in source
        assert 'href="#source-scope"' in source


def test_public_person_schema_does_not_repeat_unverified_tenure() -> None:
    """Keep author authority claims aligned between visible copy and JSON-LD."""
    forbidden = "Более 15 лет в кибербезопасности и анализе кода"
    findings = []
    for path in (
        LANDING_ROOT / "authors",
        LANDING_ROOT / "compare",
        LANDING_ROOT / "problems",
        LANDING_ROOT / "research",
    ):
        for page in path.rglob("*.html"):
            if forbidden in page.read_text(encoding="utf-8"):
                findings.append(str(page.relative_to(LANDING_ROOT)))
    assert not findings, "Unverified author tenure remains: " + ", ".join(findings)


def test_benchmark_metadata_matches_unpublished_evidence_status() -> None:
    """Keep machine-readable benchmark metadata aligned with visible content."""
    benchmark = (LANDING_ROOT / "research" / "tochnost-otvetov-i-skorost-razbora.html").read_text(
        encoding="utf-8"
    )
    for phrase in (
        "Точность ответов и скорость разбора CodeGraph",
        "Как публиковать benchmark CodeGraph",
        "опубликованные цифры CodeGraph",
        "опубликованные на сайте CodeGraph контрольные измерения",
        '"articleSection": "Данные"',
        "Можно ли переносить эти цифры на любой контур без оговорок?",
        "Эти цифры полезны как ориентир",
    ):
        assert phrase not in benchmark
    assert "Как будет устроено измерение CodeGraph" in benchmark
    assert re.search(
        r"<h1>Как\s+будет\s+устроено\s+измерение\s+CodeGraph</h1>",
        benchmark,
    )
    assert "Шаблон доказательного пакета для будущих измерений CodeGraph." in benchmark
    assert '"articleSection": "Методология"' in benchmark


def test_all_non_documentation_pages_declare_form_context() -> None:
    """Require every public landing route to expose its declarative lead context."""
    required = (
        "data-page-id",
        "data-page-stage",
        "data-buyer-role",
        "data-initiative-task",
        "data-intent",
        "data-use-case",
    )
    offenders: list[str] = []
    for path in _public_projection_files():
        relative = path.relative_to(LANDING_ROOT)
        if (
            path.suffix.lower() != ".html"
            or "docs" in relative.parts
            or "templates" in relative.parts
        ):
            continue
        source = path.read_text(encoding="utf-8")
        main = re.search(r"<main\b[^>]*>", source, flags=re.IGNORECASE)
        if main is None or any(attribute not in main.group(0) for attribute in required):
            offenders.append(str(relative))
    assert not offenders, "Pages without declarative form context: " + ", ".join(offenders)


def test_legacy_hero_copy_is_absent_from_all_templates() -> None:
    """Prevent an unused legacy hero fragment from reintroducing stale positioning."""
    forbidden = (
        "CodeGraph — цифровая команда для ИТ-бизнеса",
        "Снижайте стоимость разработки",
        "Сдерживание роста ФОТ",
        "Больше результата тем же составом",
    )
    findings: list[str] = []
    for path in (LANDING_ROOT / "templates").rglob("*.html"):
        source = path.read_text(encoding="utf-8")
        for phrase in forbidden:
            if phrase in source:
                findings.append(f"{path.relative_to(LANDING_ROOT)}: {phrase}")
    assert not findings, "Legacy hero copy remains:\n" + "\n".join(findings)


def test_legacy_category_copy_is_absent_from_public_html() -> None:
    """Keep generated pages aligned with the canonical positioning sentence."""
    legacy = "решение для управления разработкой цифровых продуктов, выполняемой с"
    findings: list[str] = []
    for path in LANDING_ROOT.rglob("*.html"):
        relative = path.relative_to(LANDING_ROOT)
        if "node_modules" in relative.parts or path.name.startswith("yandex_"):
            continue
        if legacy in path.read_text(encoding="utf-8"):
            findings.append(str(relative))
    assert not findings, "Legacy category copy remains:\n" + "\n".join(findings)


def test_public_pages_use_the_generated_versioned_tailwind_bundle() -> None:
    """Prevent HTML from pointing at an unversioned or stale CSS asset."""
    css_path = LANDING_ROOT / "css" / "tailwind.min.css"
    version = hashlib.sha256(css_path.read_bytes()).hexdigest()[:12]
    offenders: list[str] = []
    for path in LANDING_ROOT.rglob("*.html"):
        relative = path.relative_to(LANDING_ROOT)
        if (
            "node_modules" in relative.parts
            or "templates" in relative.parts
            or path.name.startswith("yandex_")
        ):
            continue
        source = path.read_text(encoding="utf-8")
        stylesheets = re.findall(
            r'<link\b[^>]*\brel="stylesheet"[^>]*\bhref="([^"]+)"',
            source,
            flags=re.IGNORECASE,
        )
        preloads = re.findall(
            r'<link\b(?=[^>]*\brel="preload")(?=[^>]*\bas="style")[^>]*\bhref="([^"]+)"',
            source,
            flags=re.IGNORECASE,
        )
        if len(stylesheets) != 1 or not stylesheets[0].endswith(f"?v={version}"):
            offenders.append(f"{relative}: {stylesheets}")
        if preloads and preloads != stylesheets:
            offenders.append(f"{relative}: preload={preloads}, stylesheet={stylesheets}")
    assert not offenders, "Unversioned or mismatched Tailwind links:\n" + "\n".join(offenders)
