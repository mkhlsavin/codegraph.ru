"""Regression checks for the immediate public-claims patch."""

from __future__ import annotations

import re
from pathlib import Path


LANDING_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_CATEGORY = (
    "CodeGraph — платформа сквозной прослеживаемости и доказательного исполнения "
    "требований в PDLC."
)

FORBIDDEN_MARKETING_PATTERNS = {
    "scenario_count": re.compile(r"\b(?:21|36)\s+(?:сценар\w*|карточ\w*)", re.IGNORECASE),
    "unsupported_quality_score": re.compile(r"(?<!\d)0[,.]83(?!\d)"),
    "unsupported_30ms": re.compile(r"(?<!\d)30\s*мс\b", re.IGNORECASE),
    "unsupported_71s": re.compile(r"(?<!\d)71\s*(?:с|сек\w*)\b", re.IGNORECASE),
    "unsupported_false_positive_rate": re.compile(
        r"(?<!\d)12\s*%[^\n]{0,80}ложн\w*\s+срабатыван", re.IGNORECASE
    ),
    "unsupported_cve_detection": re.compile(
        r"(?<!\d)100\s*%[^\n]{0,80}CVE", re.IGNORECASE
    ),
    "unsupported_23ms": re.compile(r"(?<!\d)23\s*мс\b", re.IGNORECASE),
    "unsupported_indexing_sla": re.compile(
        r"(?:1M|1\s*млн)[^\n]{0,100}30\s*мин", re.IGNORECASE
    ),
    "unsupported_availability": re.compile(r"(?<!\d)99[,.]9\s*%(?!\d)"),
    "unsupported_support_sla": re.compile(
        r"(?:4\s*/\s*24\s*/\s*72|время\s+реакции:\s*(?:4|24|72)\s*час)",
        re.IGNORECASE,
    ),
    "unsupported_fixed_rollout": re.compile(
        r"разв[её]ртыван\w*\s*[—:-]\s*1\s*[-–]\s*2\s*дн", re.IGNORECASE
    ),
    "unsupported_fixed_pilot": re.compile(
        r"до\s+3\s+(?:выбранных\s+)?сценар\w*[^\n]{0,80}"
        r"4\s*[-–]\s*8\s*нед", re.IGNORECASE
    ),
    "unsupported_economics_example": re.compile(
        r"(?:17[,.]25\s*млн|2\s*415\s*(?:час|×)|6[,.]04\s*млн)",
        re.IGNORECASE,
    ),
    "unsupported_pilot_threshold": re.compile(
        r"(?:порог\s*20\s*%|20\s*[-–]\s*40\s*инженер|"
        r"35\s*%[^\n]{0,80}(?:час|эффект))",
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
    "unsupported_false_positive_effort": re.compile(
        r"512\s*час", re.IGNORECASE
    ),
    "unsupported_contact_response_time": re.compile(
        r"в\s+течение\s+24\s+час", re.IGNORECASE
    ),
    "unsupported_internal_scale": re.compile(
        r"(?:75K\+\s*метод|3[,.]4M\s*узл)", re.IGNORECASE
    ),
    "unsupported_f1_uplift": re.compile(r"(?<!\d)33[,.]6\s*%\s*F1", re.IGNORECASE),
    "unsupported_graph_latency": re.compile(
        r"(?<!\d)2\s*[-–]\s*3\s*мс\b", re.IGNORECASE
    ),
    "quarter_only_roadmap": re.compile(r"\bQ[23]\s*2026\b", re.IGNORECASE),
    "absolute_data_egress": re.compile(
        r"(?:данные\s+никуда\s+не\s+уходят|код\s+не\s+переда[её]тся|"
        r"внешн(?:ий|его)\s+трафик(?:а)?\s+(?:нет|отсутствует))",
        re.IGNORECASE,
    ),
    "absolute_compliance": re.compile(
        r"обеспечивает\s+соответствие\s+ГОСТ", re.IGNORECASE
    ),
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
        path
        for path in (LANDING_ROOT / "js").rglob("*.js")
        if "node_modules" not in path.parts
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


def test_release_one_surfaces_use_the_canonical_category() -> None:
    """Keep the first release surfaces anchored to one canonical category formula."""
    surfaces = (
        LANDING_ROOT / "index.html",
        LANDING_ROOT / "whitepaper.html",
        LANDING_ROOT / "product-delivery.html",
        LANDING_ROOT / "templates" / "head.html",
        LANDING_ROOT / "templates" / "footer.html",
    )
    missing = [
        str(path.relative_to(LANDING_ROOT))
        for path in surfaces
        if CANONICAL_CATEGORY not in path.read_text(encoding="utf-8")
    ]

    assert not missing, f"Canonical category is missing from: {missing}"
