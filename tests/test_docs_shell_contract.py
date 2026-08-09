"""Regression checks for the shared header and footer on generated docs."""

from pathlib import Path

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
