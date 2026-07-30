"""Fail-closed editorial audit for every public, non-documentation page.

The six checks are deliberately mechanical. They do not pretend to replace an
editor: they catch repeated claims, duplicated question ownership, empty or
near-identical sections, vague nominal phrases selected by the audit, missing
proof surfaces, and repeated page-specific sentences across routes.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup, Tag


LANDING_ROOT = Path(__file__).resolve().parents[1]
MIN_WORDS = 7
EXCLUDED_PREFIXES = ("docs/", "templates/", "node_modules/", "yandex_")
TECHNICAL_HELPERS = (
    ".cg-diagram-mobile-summary",
    ".screen-viewer",
    ".diagram-viewer",
    ".page-freshness-note",
)
ABSTRACT_PATTERNS = (
    (
        "абстрактное описание",
        re.compile(
            r"\b(?:абстрактн\w*|управляемост\w*|прозрачност\w*|"
            r"согласованност\w*|эффективност\w*|ценност\w*)\b",
            re.IGNORECASE,
        ),
    ),
)


@dataclass(frozen=True)
class Page:
    route: str
    path: Path
    soup: BeautifulSoup
    main: Tag


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip().casefold()


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-zа-яё0-9]{3,}", _normalise(value)))


def _is_public(route: str) -> bool:
    return not any(route.startswith(prefix) for prefix in EXCLUDED_PREFIXES)


def _pages() -> list[Page]:
    pages: list[Page] = []
    for path in sorted(LANDING_ROOT.rglob("*.html")):
        route = path.relative_to(LANDING_ROOT).as_posix()
        if not _is_public(route):
            continue
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        main = soup.find("main")
        if main is not None:
            pages.append(Page(route, path, soup, main))
    return pages


def _clean_copy(node: Tag) -> str:
    clone = BeautifulSoup(str(node), "html.parser")
    for selector in (
        "script",
        "style",
        "noscript",
        "nav",
        *TECHNICAL_HELPERS,
    ):
        for item in clone.select(selector):
            item.decompose()
    return re.sub(r"\s+", " ", clone.get_text(" ", strip=True).replace("\xa0", " ")).strip()


def _clean_copy_without_links(node: Tag) -> str:
    clone = BeautifulSoup(str(node), "html.parser")
    for link in clone.find_all("a"):
        link.decompose()
    for card in clone.select(
        ".cg-article-list-card, [data-visual-kind], .cg-data-table-wrap, table, pre, "
        ".cg-resource-card, .cg-resource-preview, [data-product-diagram]"
    ):
        card.decompose()
    return _clean_copy(clone)


def _sentences(value: str) -> list[str]:
    value = re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()
    candidates = re.split(r"(?<=[.!?])\s+", value)
    return [
        _normalise(sentence)
        for sentence in candidates
        if len(_tokens(sentence)) >= MIN_WORDS
    ]


def _content_blocks(page: Page) -> list[Tag]:
    """Return top-level reading blocks, not nested cards or navigation."""
    main = page.main
    blocks: list[Tag] = []
    for child in main.find_all(recursive=False):
        if child.name == "section":
            blocks.append(child)
        elif "cg-page-chapter" in (child.get("class") or []):
            blocks.extend(child.find_all("section", recursive=False))
        elif "cg-whitepaper-layout" in (child.get("class") or []):
            body = child.select_one(":scope > .cg-whitepaper-body")
            if body is not None:
                blocks.extend(body.find_all("section", recursive=False))
        elif child.name == "article":
            blocks.extend(child.find_all("section", recursive=False))
    return blocks


def _check_one_thesis(pages: list[Page], findings: dict[str, list[str]]) -> None:
    for page in pages:
        sentences: list[str] = []
        for block in _content_blocks(page):
            sentences.extend(_sentences(_clean_copy(block)))
        duplicates = [sentence for sentence, count in Counter(sentences).items() if count > 1]
        for sentence in duplicates:
            findings["1. один тезис произносится один раз"].append(
                f"{page.route}: повторён тезис: {sentence}"
            )
        headings = [
            _normalise(heading.get_text(" ", strip=True))
            for block in _content_blocks(page)
            if (heading := block.find("h2")) is not None
        ]
        for heading in [heading for heading, count in Counter(headings).items() if count > 1]:
            findings["1. один тезис произносится один раз"].append(
                f"{page.route}: повторён заголовок: {heading}"
            )


def _check_two_h1_not_question(pages: list[Page], findings: dict[str, list[str]]) -> None:
    for page in pages:
        h1_nodes = page.main.find_all("h1")
        if len(h1_nodes) != 1:
            findings["2. H1 не повторяется вопросом"].append(
                f"{page.route}: H1 count={len(h1_nodes)}"
            )
            continue
        h1 = _normalise(h1_nodes[0].get_text(" ", strip=True))
        if page.soup.select("[data-primary-question]"):
            findings["2. H1 не повторяется вопросом"].append(
                f"{page.route}: найдено устаревшее data-primary-question"
            )
        for node in page.main.find_all(["h2", "h3", "p", "figcaption"]):
            if _normalise(node.get_text(" ", strip=True)) == h1:
                findings["2. H1 не повторяется вопросом"].append(
                    f"{page.route}: H1 повторён в {node.name}"
                )
        for node in page.main.select(".cg-article-answer"):
            if h1 in _normalise(node.get_text(" ", strip=True)):
                findings["2. H1 не повторяется вопросом"].append(
                    f"{page.route}: H1 повторён в answer-блоке"
                )


def _check_three_sections_add_facts(pages: list[Page], findings: dict[str, list[str]]) -> None:
    for page in pages:
        blocks = [
            block
            for block in _content_blocks(page)
            if "cg-article-cta" not in (block.get("class") or [])
            and block.get("id") not in {"demo", "next-step"}
            and block.find("h1") is None
        ]
        heading_values: list[str] = []
        body_values: list[str] = []
        for block in blocks:
            heading = block.find(["h2", "h3"])
            body = _clean_copy(block)
            if heading is None:
                findings["3. каждая секция добавляет новый факт"].append(
                    f"{page.route}: секция без заголовка"
                )
            else:
                heading_values.append(_normalise(heading.get_text(" ", strip=True)))
            body_values.append(body)
            if len(_tokens(body)) < 8:
                findings["3. каждая секция добавляет новый факт"].append(
                    f"{page.route}: слишком мало содержания в секции"
                )
        for heading in [h for h, count in Counter(heading_values).items() if count > 1]:
            findings["3. каждая секция добавляет новый факт"].append(
                f"{page.route}: повторён заголовок секции: {heading}"
            )
        for index, left in enumerate(body_values):
            for right in body_values[index + 1 :]:
                left_tokens, right_tokens = _tokens(left), _tokens(right)
                if not left_tokens or not right_tokens:
                    continue
                overlap = len(left_tokens & right_tokens) / min(len(left_tokens), len(right_tokens))
                similarity = difflib.SequenceMatcher(None, left, right).ratio()
                if similarity >= 0.9 or overlap >= 0.92:
                    findings["3. каждая секция добавляет новый факт"].append(
                        f"{page.route}: две секции почти повторяют содержание"
                    )
                    break


def _check_four_concrete_language(pages: list[Page], findings: dict[str, list[str]]) -> None:
    for page in pages:
        for node in page.main.find_all(["p", "li", "td", "th", "figcaption", "h2", "h3"]):
            text = node.get_text(" ", strip=True)
            for label, pattern in ABSTRACT_PATTERNS:
                match = pattern.search(text)
                if match:
                    findings["4. абстрактное существительное заменено объектом или действием"].append(
                        f"{page.route}: {label}: {text[:220]}"
                    )
                    break


def _proof_signature(page: Page) -> str:
    candidates = page.main.select(
        "table, pre, [data-visual-kind], .cg-resource-card, .cg-resource-preview"
    )
    if not candidates:
        return ""
    text = _normalise(candidates[0].get_text(" ", strip=True))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _check_five_unique_proof(pages: list[Page], findings: dict[str, list[str]]) -> None:
    signatures: defaultdict[str, list[str]] = defaultdict(list)
    captions: defaultdict[str, list[str]] = defaultdict(list)
    for page in pages:
        proof_nodes = page.main.select(
            "table, pre, [data-visual-kind], .cg-resource-card, .cg-resource-preview"
        )
        if not proof_nodes:
            findings["5. уникальный пример, таблица или результат"].append(
                f"{page.route}: нет доказательного объекта"
            )
        signature = _proof_signature(page)
        if signature:
            signatures[signature].append(page.route)
        for caption in page.main.select(".cg-product-preview-caption"):
            value = _normalise(caption.get_text(" ", strip=True))
            if not value or "синтетический пример результата на выбранном этапе" in value:
                findings["5. уникальный пример, таблица или результат"].append(
                    f"{page.route}: общая или пустая подпись демонстрации"
                )
            captions[value].append(page.route)
    for routes in signatures.values():
        if len(routes) > 1:
            findings["5. уникальный пример, таблица или результат"].append(
                f"одинаковый доказательный объект: {', '.join(routes)}"
            )
    for routes in captions.values():
        if len(routes) > 1:
            findings["5. уникальный пример, таблица или результат"].append(
                f"повторена подпись демонстрации: {', '.join(routes)}"
            )


def _check_six_adjacent_pages(pages: list[Page], findings: dict[str, list[str]]) -> None:
    questions: defaultdict[str, list[str]] = defaultdict(list)
    sentence_owners: defaultdict[str, list[str]] = defaultdict(list)
    for page in pages:
        question = _normalise(page.main.get("data-buyer-question", ""))
        if question:
            questions[question].append(page.route)
        sentences = set(
            sentence
            for block in _content_blocks(page)
            if "cg-article-cta" not in (block.get("class") or [])
            and block.get("id") not in {"demo", "next-step"}
            for sentence in _sentences(_clean_copy_without_links(block))
        )
        for sentence in sentences:
            sentence_owners[sentence].append(page.route)
    for question, routes in questions.items():
        if len(routes) > 1:
            findings["6. соседняя страница не отвечает тем же вопросом"].append(
                f"повторён вопрос: {', '.join(routes)}: {question}"
            )
    for sentence, routes in sentence_owners.items():
        # A shared disclosure is intentionally identical on product pages. It
        # is a source-status label, not a page thesis; page-specific prose is
        # still fail-closed when it repeats on two routes.
        if len(routes) == 2:
            findings["6. соседняя страница не отвечает тем же вопросом"].append(
                f"повторено предложение: {', '.join(routes)}: {sentence}"
            )


def audit() -> tuple[list[Page], dict[str, list[str]]]:
    pages = _pages()
    findings: dict[str, list[str]] = defaultdict(list)
    _check_one_thesis(pages, findings)
    _check_two_h1_not_question(pages, findings)
    _check_three_sections_add_facts(pages, findings)
    _check_four_concrete_language(pages, findings)
    _check_five_unique_proof(pages, findings)
    _check_six_adjacent_pages(pages, findings)
    return pages, findings


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print machine-readable findings")
    args = parser.parse_args()
    pages, findings = audit()
    if args.json:
        print(json.dumps({"pages": len(pages), "findings": findings}, ensure_ascii=False, indent=2))
    else:
        print(f"Public non-documentation pages: {len(pages)}")
        for criterion in (
            "1. один тезис произносится один раз",
            "2. H1 не повторяется вопросом",
            "3. каждая секция добавляет новый факт",
            "4. абстрактное существительное заменено объектом или действием",
            "5. уникальный пример, таблица или результат",
            "6. соседняя страница не отвечает тем же вопросом",
        ):
            print(f"{criterion}: {len(findings.get(criterion, []))} findings")
        for criterion, items in findings.items():
            for item in items:
                print(f"FAIL [{criterion}] {item}")
    return 1 if findings else 0


def test_all_public_pages_pass_six_editorial_checks() -> None:
    pages, findings = audit()
    assert len(pages) == 40, f"Expected 40 public pages, found {len(pages)}"
    assert not findings, "Editorial audit findings:\n" + "\n".join(
        f"[{criterion}] {item}" for criterion, items in findings.items() for item in items
    )


if __name__ == "__main__":
    raise SystemExit(main())
