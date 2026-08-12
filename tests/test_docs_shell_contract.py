"""Regression checks for the shared shell and public metadata on generated docs."""

import json
from pathlib import Path

from bs4 import BeautifulSoup

LANDING_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = LANDING_ROOT / "docs"


def test_generated_docs_use_the_shared_shell() -> None:
    """Require every generated documentation page to use the shared shell."""
    pages = sorted(DOCS_ROOT.rglob("*.html"))
    assert pages

    for page in pages:
        html = page.read_text(encoding="utf-8")
        assert html.count("data-shell-header") == 1, page
        assert html.count("data-shell-footer") == 1, page
        assert 'id="main-content"' in html, page
        assert "docs-shell-header" not in html, page
        assert "Сквозная прослеживаемость и" not in html, page
        assert "Разобрать инициативу" not in html, page
        assert "/svg/logo.svg" not in html, page


def test_generated_docs_use_current_favicon_and_public_social_card() -> None:
    """Keep docs previews aligned with the main public landing brand contract."""
    site_content = json.loads(
        (LANDING_ROOT / "site_content.json").read_text(encoding="utf-8")
    )
    social_image = "https://codegraph.ru/assets/og-codegraph-platform-20260722.png"

    pages = sorted(DOCS_ROOT.rglob("*.html"))
    assert pages
    for page in pages:
        html = page.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        favicon = soup.find("link", rel="icon")
        assert favicon and favicon.get("href", "").endswith("/assets/favicon.svg"), page
        assert "logo-compact.svg" not in html, page

        assert soup.find("meta", property="og:image")["content"] == social_image
        assert (
            soup.find("meta", attrs={"name": "twitter:image"})["content"]
            == social_image
        )
        assert (
            soup.find("meta", property="og:image:alt")["content"].replace("\xa0", " ")
            == site_content["social_image_alt"]
        )
        assert (
            soup.find("meta", attrs={"name": "twitter:image:alt"})["content"].replace(
                "\xa0", " "
            )
            == site_content["social_image_alt"]
        )

    ru_index = BeautifulSoup(
        (DOCS_ROOT / "ru" / "index.html").read_text(encoding="utf-8"),
        "html.parser",
    )
    assert (
        ru_index.title.get_text(strip=True).replace("\xa0", " ")
        == site_content["canonical_seo_title"]
    )
    assert (
        ru_index.find("meta", attrs={"name": "description"})["content"].replace(
            "\xa0", " "
        )
        == site_content["canonical_meta_description"]
    )
