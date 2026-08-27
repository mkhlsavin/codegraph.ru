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
EXCLUDED_PREFIXES = (
    "demo/",
    "docs/",
    "templates/",
    "node_modules/",
    "yandex_",
)
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
            r"согласованност\w*|эффективност\w*|ценност\w*|"
            r"доказательн\w*\s+баз\w*|квалифицир\w*\s+вывод\w*|"
            r"объясним\w*\s+статус\w*|статус\s+готовност\w*|"
            r"пакет\s+(?:подтвержден\w*|готовност\w*)|"
            r"живой\s+пакет\s+документаци\w*|"
            r"управленческий\s+выигрыш|нехватк\w*\s+видимост\w*|"
            r"портфельн\w*\s+контекст|рассчитать\s+состояни\w*|"
            r"путь\s+к\s+основани\w*|локальн\w*\s+контур\w*|"
            r"контур\s+(?:правил|понимани\w*|управлени\w*|контрол\w*)|"
            r"состоян\w*\s+готовност\w*)",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_COPY_PATTERNS = (
    (
        "старое позиционирование",
        re.compile(
            r"решение для управляемой разработки цифровых продуктов", re.IGNORECASE
        ),
    ),
    ("инициатива", re.compile(r"\bинициатив\w*", re.IGNORECASE)),
    ("контур", re.compile(r"\bконтур\w*", re.IGNORECASE)),
    ("доказательная база", re.compile(r"\bдоказательн\w*\s+баз\w*", re.IGNORECASE)),
    ("пакет подтверждений", re.compile(r"\bпакет\s+подтвержден\w*", re.IGNORECASE)),
    ("пакет готовности", re.compile(r"\bпакет\s+готовност\w*", re.IGNORECASE)),
    ("прослеживаемость", re.compile(r"\bпрослеживаем\w*", re.IGNORECASE)),
    ("продуктовый замысел", re.compile(r"\bпродуктов\w*\s+замыс\w*", re.IGNORECASE)),
    (
        "управленческий выигрыш",
        re.compile(r"\bуправленческ\w*\s+выигрыш\w*", re.IGNORECASE),
    ),
    (
        "живой пакет документации",
        re.compile(r"\bжив\w*\s+пакет\w*\s+документаци\w*", re.IGNORECASE),
    ),
    (
        "мета-комментарий о материале",
        re.compile(
            r"\b(?:публичн(?:ая|ый|ого|ом|ой)\s+страниц\w*|публичн(?:ый|ого|ом|ой)\s+источник\w*|базов\w*\s+публичн\w*\s+источник\w*|в\s+публичн\w*\s+источник\w*|публичн\w*\s+выборк\w*|на\s+опубликованн\w*\s+страниц\w*|страниц\w*\s+отделя\w*|публичн\w*\s+клиентск\w*\s+пример\w*|жанр\s+материал\w*|иллюстративн\w*\s+расч\w*)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "метаописание страницы",
        re.compile(
            r"\b(?:на странице|описан\w*\s+отдельно\s+на\s+странице|начните\s+с\s+материала|ссылки\s+ведут\s+к\s+публичным\s+материалам|здесь\s+остают\w*)\b",
            re.IGNORECASE,
        ),
    ),
)
GRAMMAR_REGRESSION_PATTERNS = (
    "нужен локальная среда",
    "не требует дополнительной результатов",
    "к результатах проверок",
    "в матрица версий поддержки",
    "вместе с набор данных, протокол",
    "после проверки набор данных",
    "в локальном системае",
    "единый система",
    "локального средаа",
    "локальном средае",
    "как должен выглядеть проверка",
)


@dataclass(frozen=True)
class Page:
    """One public route and its parsed source context."""

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
    return re.sub(
        r"\s+", " ", clone.get_text(" ", strip=True).replace("\xa0", " ")
    ).strip()


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


def _metadata_values(page: Page) -> list[str]:
    values: list[str] = []
    for node in page.soup.find_all(["title", "meta"]):
        if node.name == "title":
            values.append(node.get_text(" ", strip=True))
        else:
            content = node.get("content")
            if content:
                values.append(str(content))
    for script in page.soup.select('script[type="application/ld+json"]'):
        raw = script.get_text(strip=True)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            values.append(raw)
            continue

        def collect(value: object) -> None:
            if isinstance(value, str):
                values.append(value)
            elif isinstance(value, dict):
                for item in value.values():
                    collect(item)
            elif isinstance(value, list):
                for item in value:
                    collect(item)

        collect(payload)
    return values


def _editorial_scan_text(page: Page) -> str:
    return " ".join([_clean_copy(page.main), *_metadata_values(page)])


def _check_seven_regressions(pages: list[Page], findings: dict[str, list[str]]) -> None:
    for page in pages:
        text = _editorial_scan_text(page)
        for label, pattern in FORBIDDEN_COPY_PATTERNS:
            match = pattern.search(text)
            if match:
                findings["7. запрещённые термины и метаописания отсутствуют"].append(
                    f"{page.route}: {label}: {match.group(0)}"
                )
        lower = text.casefold()
        for phrase in GRAMMAR_REGRESSION_PATTERNS:
            if phrase.casefold() in lower:
                findings["7. запрещённые термины и метаописания отсутствуют"].append(
                    f"{page.route}: грамматический регресс: {phrase}"
                )


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
        duplicates = [
            sentence for sentence, count in Counter(sentences).items() if count > 1
        ]
        for sentence in duplicates:
            findings["1. один тезис произносится один раз"].append(
                f"{page.route}: повторён тезис: {sentence}"
            )
        headings = [
            _normalise(heading.get_text(" ", strip=True))
            for block in _content_blocks(page)
            if (heading := block.find("h2")) is not None
        ]
        for heading in [
            heading for heading, count in Counter(headings).items() if count > 1
        ]:
            findings["1. один тезис произносится один раз"].append(
                f"{page.route}: повторён заголовок: {heading}"
            )


def _check_two_h1_not_question(
    pages: list[Page], findings: dict[str, list[str]]
) -> None:
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


def _check_three_sections_add_facts(
    pages: list[Page], findings: dict[str, list[str]]
) -> None:
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
                overlap = len(left_tokens & right_tokens) / min(
                    len(left_tokens), len(right_tokens)
                )
                similarity = difflib.SequenceMatcher(None, left, right).ratio()
                if similarity >= 0.9 or overlap >= 0.92:
                    findings["3. каждая секция добавляет новый факт"].append(
                        f"{page.route}: две секции почти повторяют содержание"
                    )
                    break


def _check_four_concrete_language(
    pages: list[Page], findings: dict[str, list[str]]
) -> None:
    for page in pages:
        for node in page.main.find_all(
            ["p", "li", "td", "th", "figcaption", "h2", "h3"]
        ):
            text = node.get_text(" ", strip=True)
            for label, pattern in ABSTRACT_PATTERNS:
                match = pattern.search(text)
                if match:
                    findings[
                        "4. абстрактное существительное заменено объектом или действием"
                    ].append(f"{page.route}: {label}: {text[:220]}")
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
            if (
                not value
                or "синтетический пример результата на выбранном этапе" in value
            ):
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


def _check_six_adjacent_pages(
    pages: list[Page], findings: dict[str, list[str]]
) -> None:
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
        # Genre and source disclosures are metadata, not page theses. Every
        # other repeated sentence is a collision, including three or more
        # owners; limiting this to exactly two used to hide recurring copy.
        if (
            "жанр материала" in sentence
            or "ссылки ведут к публичным материалам" in sentence
            or "это не независимое исследование" in sentence
        ):
            continue
        if len(routes) >= 2:
            findings["6. соседняя страница не отвечает тем же вопросом"].append(
                f"повторено предложение: {', '.join(routes)}: {sentence}"
            )


def _check_hero_first_section(
    pages: list[Page], findings: dict[str, list[str]]
) -> None:
    """Catch a first section that merely restates the answer in the hero."""
    for page in pages:
        hero = page.main.find("section")
        blocks = _content_blocks(page)
        if hero is None or len(blocks) < 2 or blocks[0] is not hero:
            continue
        hero_text = _clean_copy_without_links(hero)
        first_text = _clean_copy_without_links(blocks[1])
        hero_tokens, first_tokens = _tokens(hero_text), _tokens(first_text)
        if not hero_tokens or not first_tokens:
            continue
        overlap = len(hero_tokens & first_tokens) / min(
            len(hero_tokens), len(first_tokens)
        )
        similarity = difflib.SequenceMatcher(None, hero_text, first_text).ratio()
        if similarity >= 0.78 or overlap >= 0.84:
            findings["8. Hero и первая секция различаются"].append(
                f"{page.route}: первая секция повторяет ответ Hero"
            )


def _check_neighbor_cta(pages: list[Page], findings: dict[str, list[str]]) -> None:
    """Catch duplicate action labels within the same visible block."""
    for page in pages:
        for block in page.main.find_all("section"):
            labels = [
                _normalise(node.get_text(" ", strip=True))
                for node in block.select("a.cg-button, button.cg-button")
            ]
            for left, right in zip(labels, labels[1:]):
                if left and left == right:
                    findings["9. соседние CTA не повторяются"].append(
                        f"{page.route}: повторена кнопка: {left}"
                    )


def _check_test_data_labels(pages: list[Page], findings: dict[str, list[str]]) -> None:
    """Require a short, explicit label for public fictional artifacts."""
    fictional_markers = re.compile(
        r"\b(?:SEC-ADM-014|PR-842|AC-14|FR-AP-07|NFR-AUD-02|PI-AP-03|R-09)\b",
        re.IGNORECASE,
    )
    for page in pages:
        proof = " ".join(
            node.get_text(" ", strip=True) for node in page.main.select("pre, table")
        )
        if fictional_markers.search(proof) and not re.search(
            r"\bтестовые\s+данные\b", _clean_copy(page.main), re.IGNORECASE
        ):
            findings["10. тестовые примеры помечены"].append(
                f"{page.route}: пример с идентификаторами без метки «Тестовые данные»"
            )


def audit() -> tuple[list[Page], dict[str, list[str]]]:
    """Run all editorial checks and return findings grouped by rule."""
    pages = _pages()
    findings: dict[str, list[str]] = defaultdict(list)
    _check_one_thesis(pages, findings)
    _check_two_h1_not_question(pages, findings)
    _check_three_sections_add_facts(pages, findings)
    _check_four_concrete_language(pages, findings)
    _check_five_unique_proof(pages, findings)
    _check_six_adjacent_pages(pages, findings)
    _check_seven_regressions(pages, findings)
    _check_hero_first_section(pages, findings)
    _check_neighbor_cta(pages, findings)
    _check_test_data_labels(pages, findings)
    return pages, findings


def main() -> int:
    """Run the public content audit as a command-line check."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json", action="store_true", help="print machine-readable findings"
    )
    args = parser.parse_args()
    pages, findings = audit()
    if args.json:
        print(
            json.dumps(
                {"pages": len(pages), "findings": findings},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"Public non-documentation pages: {len(pages)}")
        for criterion in (
            "1. один тезис произносится один раз",
            "2. H1 не повторяется вопросом",
            "3. каждая секция добавляет новый факт",
            "4. абстрактное существительное заменено объектом или действием",
            "5. уникальный пример, таблица или результат",
            "6. соседняя страница не отвечает тем же вопросом",
            "7. запрещённые термины и метаописания отсутствуют",
            "8. Hero и первая секция различаются",
            "9. соседние CTA не повторяются",
            "10. тестовые примеры помечены",
        ):
            print(f"{criterion}: {len(findings.get(criterion, []))} findings")
        for criterion, items in findings.items():
            for item in items:
                print(f"FAIL [{criterion}] {item}")
    return 1 if findings else 0


def test_all_public_pages_pass_six_editorial_checks() -> None:
    """Require every declared public page to pass all editorial checks."""
    pages, findings = audit()
    assert len(pages) == 41, f"Expected 41 public pages, found {len(pages)}"  # FR-P1237-LEAD-PAGE-01
    assert not findings, "Editorial audit findings:\n" + "\n".join(
        f"[{criterion}] {item}"
        for criterion, items in findings.items()
        for item in items
    )


if __name__ == "__main__":
    raise SystemExit(main())
