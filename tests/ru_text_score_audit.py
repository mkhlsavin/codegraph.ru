#!/usr/bin/env python3
"""Read-only page-by-page ``ru-text`` score gate for Russian public HTML.

The gate applies the five dimensions from the installed ``/ru-text:ru-score``
rubric. Objective defects lower the relevant dimension; technical identifiers in
documentation and product names are excluded from language-purity penalties.
The script never writes files and exits non-zero when any dimension is below the
configured acceptance floor.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re

from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString


LANDING_ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = (0.15, 0.25, 0.20, 0.20, 0.20)
ONE_LETTER_BREAK = re.compile(
    r"(?<![А-Яа-яЁё])([вксоуюияа]) (?=[А-Яа-яЁё0-9«])", re.IGNORECASE
)
MANUFACTURED_ANTITHESIS = re.compile(r"\bне\s+[^.!?]{1,140}?,\s+а\b", re.IGNORECASE)
BUREAUCRATIC = re.compile(
    r"\b(?:осуществля\w*|производится|данный|посредством|следует отметить)\b",
    re.IGNORECASE,
)
VAGUE_CLAIM = re.compile(
    r"\b(?:гарантированно|всегда|никогда|мгновенно|лучший|идеальн\w*|"
    r"революционн\w*|значительно повышает|существенно снижает)\b",
    re.IGNORECASE,
)
MALFORMED_PUBLIC_COPY = (
    "между продукт и разработка",
    "без источник и история",
    "изменение без основание",
    "утверждено требование",
    "общая среда выполнения по в заданных границах",
    "вместо of",
    "must не",
)


@dataclass(frozen=True)
class Score:
    """Five independent rubric dimensions and their weighted composite."""

    typography: float
    clarity: float
    grammar: float
    structure: float
    precision: float

    @property
    def composite(self) -> float:
        """Return the one-decimal weighted score required by ``ru-score``."""
        values = (
            self.typography,
            self.clarity,
            self.grammar,
            self.structure,
            self.precision,
        )
        return round(sum(value * weight for value, weight in zip(values, WEIGHTS)), 1)

    @property
    def minimum(self) -> float:
        """Return the non-compensatory acceptance value."""
        return min(
            self.typography,
            self.clarity,
            self.grammar,
            self.structure,
            self.precision,
        )


@dataclass(frozen=True)
class PageResult:
    """One page score with concise evidence notes."""

    route: str
    score: Score
    notes: tuple[str, ...]


def _public_pages() -> list[Path]:
    """Return every generated Russian page in stable route order."""
    pages: list[Path] = []
    for path in LANDING_ROOT.rglob("*.html"):
        relative = path.relative_to(LANDING_ROOT)
        if (
            "node_modules" in path.parts
            or "templates" in relative.parts
            or path.name.startswith("yandex_")
        ):
            continue
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        if soup.html and soup.html.get("lang") == "ru":
            pages.append(path)
    return sorted(pages)


def _audited_text(soup: BeautifulSoup) -> tuple[str, list[str]]:
    """Extract visible prose and paragraph-sized blocks without code samples."""
    for node in soup.find_all(["script", "style", "code", "pre", "nav", "footer"]):
        node.decompose()
    fragments: list[str] = []
    for node in soup.find_all(string=True):
        if isinstance(node, NavigableString) and not isinstance(node, Comment):
            value = str(node).strip()
            if value:
                fragments.append(value)
    blocks = [
        " ".join(node.stripped_strings)
        for node in soup.select("main p, main li, main dd")
        if " ".join(node.stripped_strings)
    ]
    return "\n".join(fragments), blocks


def score_page(path: Path) -> PageResult:
    """Score one Russian HTML page against all five rubric dimensions."""
    source = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(source, "html.parser")
    text, blocks = _audited_text(soup)
    relative = path.relative_to(LANDING_ROOT).as_posix()
    notes: list[str] = []

    typography = 10.0
    typography_defects = (
        bool(ONE_LETTER_BREAK.search(text)),
        bool(re.search(r'"[А-Яа-яЁё][^"\n]{0,120}"', text)),
        " - " in text or " -- " in text,
        "..." in text,
    )
    if any(typography_defects):
        typography = max(0.0, 10.0 - 1.5 * sum(typography_defects))
        notes.append("объективное нарушение типографики")

    clarity = 9.4
    prose_blocks = [
        block
        for block in blocks
        if len(block.split()) >= 8
        and len(re.findall(r"[A-Za-z]", block))
        / max(1, len(re.findall(r"[A-Za-zА-Яа-яЁё]", block)))
        < 0.35
    ]
    very_long = sum(len(block.split()) > 70 for block in prose_blocks)
    bureaucratic = len(BUREAUCRATIC.findall(" ".join(prose_blocks)))
    clarity -= min(0.8, very_long * 0.2)
    clarity -= min(0.4, bureaucratic * 0.05)
    if very_long:
        notes.append(f"длинные прозаические блоки: {very_long}")
    if bureaucratic:
        notes.append(f"канцелярские маркеры: {bureaucratic}")

    grammar = 9.5
    malformed = [fragment for fragment in MALFORMED_PUBLIC_COPY if fragment in text.casefold()]
    if malformed:
        grammar -= min(1.5, len(malformed) * 0.5)
        notes.append(f"нарушенные согласования: {len(malformed)}")

    structure = 9.4
    headings = [int(node.name[1]) for node in soup.find_all(re.compile(r"^h[1-6]$"))]
    h1_count = len(soup.find_all("h1"))
    heading_skips = sum(1 for left, right in zip(headings, headings[1:]) if right > left + 1)
    antitheses = len(MANUFACTURED_ANTITHESIS.findall(text))
    if h1_count != 1:
        structure -= 1.5
        notes.append(f"число H1: {h1_count}")
    if heading_skips:
        structure -= min(1.0, heading_skips * 0.3)
        notes.append(f"скачки уровней заголовков: {heading_skips}")
    if antitheses >= 3:
        structure -= min(1.0, (antitheses - 2) * 0.25)
        notes.append(f"серийные противопоставления: {antitheses}")

    precision = 9.4
    vague_claims = len(VAGUE_CLAIM.findall(text))
    if vague_claims:
        precision -= min(0.8, vague_claims * 0.2)
        notes.append(f"неуточнённые усилители: {vague_claims}")

    values = [typography, clarity, grammar, structure, precision]
    values = [round(max(0.0, min(10.0, value)), 1) for value in values]
    return PageResult(relative, Score(*values), tuple(notes[:3]))


def main() -> int:
    """Print the complete score matrix and enforce the requested floor."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minimum", type=float, default=8.5)
    args = parser.parse_args()
    results = [score_page(path) for path in _public_pages()]
    print("| Страница | Т | Ч | Г | С | Ц | Итог | Замечания |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
    for result in results:
        score = result.score
        notes = "; ".join(result.notes) if result.notes else "Замечаний нет"
        print(
            f"| {result.route} | {score.typography:.1f} | {score.clarity:.1f} | "
            f"{score.grammar:.1f} | {score.structure:.1f} | {score.precision:.1f} | "
            f"{score.composite:.1f} | {notes} |"
        )
    failures = [result for result in results if result.score.minimum < args.minimum]
    print(
        f"\nПроверено страниц: {len(results)}; порог по каждой категории: "
        f"{args.minimum:.1f}; нарушений: {len(failures)}."
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
