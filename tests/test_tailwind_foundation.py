"""Fail-closed contracts for the Story 1113 public-site Tailwind foundation."""

from __future__ import annotations

import gzip
import json
import re
from pathlib import Path


LANDING_ROOT = Path(__file__).resolve().parents[1]
PINNED_TAILWIND_VERSION = "4.3.0"
INLINE_STYLE_BASELINE = 0
STYLE_BLOCK_BASELINE = 0
DOM_STYLE_MUTATION_BASELINE = 0
LEGACY_CSS_FILE_BASELINE = 0
# Governed Python-rendered pages add utility classes after template scanning.
TAILWIND_RAW_BUDGET = 155_000
TAILWIND_GZIP_BUDGET = 25_000
JAVASCRIPT_RAW_BUDGET = 50_000
JAVASCRIPT_GZIP_BUDGET = 15_000
IMAGE_TOTAL_BUDGET = 1_500_000
IMAGE_SINGLE_FILE_BUDGET = 200_000
SHARED_SHELL_TEMPLATES = (
    "templates/header.html",
    "templates/footer.html",
    "templates/sections/cta.html",
)
LEGACY_SHARED_SHELL_CLASSES = {
    "skip-link",
    "header",
    "nav",
    "container",
    "logo",
    "nav-list",
    "nav-link",
    "header-actions",
    "theme-toggle",
    "header-cta",
    "mobile-menu-toggle",
    "mobile-nav",
    "mobile-nav-list",
    "mobile-nav-link",
    "mobile-nav-cta",
    "footer",
    "footer-content",
    "footer-brand",
    "footer-logo",
    "footer-description",
    "footer-links",
    "footer-links-group",
    "footer-links-list",
    "footer-link",
    "footer-social",
    "footer-social-link",
    "footer-bottom",
    "footer-copyright",
    "section",
    "cta",
    "cta-content",
    "cta-trust",
    "cta-trust-item",
    "demo-form-full",
    "form-row",
    "form-group",
    "cta-alternatives",
    "cta-alt-btn",
    "btn",
    "btn-primary",
    "btn-outline",
    "btn-lg",
}


def _source_files(pattern: str) -> list[Path]:
    """Return landing source files while excluding installed dependencies."""
    return [
        path
        for path in LANDING_ROOT.rglob(pattern)
        if "node_modules" not in path.parts
    ]


def _public_html_files() -> list[Path]:
    """Return complete public HTML documents rather than template fragments."""
    return [
        path
        for path in _source_files("*.html")
        if "templates" not in path.relative_to(LANDING_ROOT).parts
        and not path.name.startswith("yandex_")
    ]


def _count_matches(pattern: re.Pattern[str], paths: list[Path]) -> int:
    """Count regex matches across UTF-8 source files."""
    return sum(
        len(pattern.findall(path.read_text(encoding="utf-8")))
        for path in paths
    )


def _class_tokens(source: str) -> set[str]:
    """Return static class tokens from one HTML template."""
    return {
        token
        for value in re.findall(r'class="([^"]*)"', source)
        for token in value.split()
    }


def test_tailwind_dependencies_and_build_are_pinned() -> None:
    """Require an exact local Tailwind CLI version and reproducible lockfile."""
    package = json.loads((LANDING_ROOT / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((LANDING_ROOT / "package-lock.json").read_text(encoding="utf-8"))

    assert package["private"] is True
    assert package["devDependencies"] == {
        "@tailwindcss/cli": PINNED_TAILWIND_VERSION,
        "tailwindcss": PINNED_TAILWIND_VERSION,
    }
    assert package["scripts"]["build:tailwind"].endswith("--minify")
    assert lock["packages"][""]["devDependencies"] == package["devDependencies"]


def test_public_asset_bundles_stay_inside_explicit_release_budgets() -> None:
    """Measure CSS, JS, and image bytes against the Story 1113 release budgets."""
    css = (LANDING_ROOT / "css" / "tailwind.min.css").read_bytes()
    javascript = (LANDING_ROOT / "js" / "main.min.js").read_bytes()
    images = [
        path
        for path in (LANDING_ROOT / "assets").rglob("*")
        if path.is_file()
        and path.suffix.casefold() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
    ]

    assert len(css) <= TAILWIND_RAW_BUDGET
    assert len(gzip.compress(css, compresslevel=9)) <= TAILWIND_GZIP_BUDGET
    assert len(javascript) <= JAVASCRIPT_RAW_BUDGET
    assert len(gzip.compress(javascript, compresslevel=9)) <= JAVASCRIPT_GZIP_BUDGET
    assert sum(path.stat().st_size for path in images) <= IMAGE_TOTAL_BUDGET
    assert max(path.stat().st_size for path in images) <= IMAGE_SINGLE_FILE_BUDGET


def test_tailwind_input_and_all_public_links_are_present() -> None:
    """Require global content discovery and one generated stylesheet on every page."""
    source = (LANDING_ROOT / "css" / "tailwind.css").read_text(encoding="utf-8")
    output = LANDING_ROOT / "css" / "tailwind.min.css"

    assert "@layer theme, base, components, utilities;" in source
    assert "styles.min.css" not in source
    assert '@import "tailwindcss/theme.css" layer(theme);' in source
    assert '@import "tailwindcss/utilities.css" layer(utilities);' in source
    for content_source in ("../**/*.html", "../js/*.js"):
        assert f'@source "{content_source}";' in source
    assert "@custom-variant dark" in source
    assert "--color-cg-primary:" in source
    assert output.is_file() and output.stat().st_size > 0

    offenders: dict[str, list[str]] = {}
    for path in _public_html_files():
        html = path.read_text(encoding="utf-8")
        links = re.findall(r'<link\b[^>]*rel="stylesheet"[^>]*href="([^"]+)"', html)
        if len(links) != 1 or not links[0].split("?", 1)[0].endswith("css/tailwind.min.css"):
            offenders[str(path.relative_to(LANDING_ROOT))] = links

    assert not offenders, f"Non-canonical stylesheet ownership remains: {offenders}"


def test_generated_homepage_utility_classes_are_in_the_built_bundle() -> None:
    """Ensure Python-generated hero markup is included in Tailwind content scanning."""
    css = (LANDING_ROOT / "css" / "tailwind.min.css").read_text(encoding="utf-8")
    required = (".h-2", ".h-full", ".w-4\\/5", ".bg-cg-success")
    missing = [selector for selector in required if selector not in css]
    assert not missing, f"Generated homepage utilities are missing from CSS: {missing}"


def test_public_stylesheet_and_preload_paths_resolve_to_built_asset() -> None:
    """Catch relative CSS paths that look canonical but resolve outside the publication."""
    root = LANDING_ROOT.resolve()
    offenders: dict[str, object] = {}
    for path in _public_html_files():
        html = path.read_text(encoding="utf-8")
        stylesheets = re.findall(
            r'<link\b[^>]*\brel="stylesheet"[^>]*\bhref="([^"]+)"',
            html,
            flags=re.IGNORECASE,
        )
        preloads = re.findall(
            r'<link\b(?=[^>]*\brel="preload")(?=[^>]*\bas="style")[^>]*\bhref="([^"]+)"',
            html,
            flags=re.IGNORECASE,
        )
        if len(stylesheets) != 1 or (preloads and preloads != stylesheets):
            offenders[str(path.relative_to(LANDING_ROOT))] = (stylesheets, preloads)
            continue
        href = stylesheets[0].split("?", 1)[0].split("#", 1)[0]
        target = (root / href.lstrip("/")) if href.startswith("/") else (path.parent / href).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            offenders[str(path.relative_to(LANDING_ROOT))] = href
            continue
        if target != root / "css" / "tailwind.min.css" or not target.is_file():
            offenders[str(path.relative_to(LANDING_ROOT))] = href

    assert not offenders, f"Public CSS paths do not resolve to the built bundle: {offenders}"


def test_shared_shell_templates_are_tailwind_owned() -> None:
    """Reject parallel legacy ownership of the shared header, footer and CTA form."""
    sources = {
        relative: (LANDING_ROOT / relative).read_text(encoding="utf-8")
        for relative in SHARED_SHELL_TEMPLATES
    }
    offenders = {
        relative: sorted(_class_tokens(source) & LEGACY_SHARED_SHELL_CLASSES)
        for relative, source in sources.items()
        if _class_tokens(source) & LEGACY_SHARED_SHELL_CLASSES
    }

    assert not offenders, f"Legacy shared-shell classes remain: {offenders}"
    assert "data-shell-header" in sources["templates/header.html"]
    assert "data-theme-toggle" in sources["templates/header.html"]
    assert "data-mobile-menu-toggle" in sources["templates/header.html"]
    assert "data-mobile-nav" in sources["templates/header.html"]
    assert "data-state=\"closed\"" in sources["templates/header.html"]
    assert "cg-mobile-nav" in sources["templates/header.html"]
    assert "cg-mobile-toggle-bar" in sources["templates/header.html"]
    assert "data-[state=closed]:[translate:100%]" not in sources["templates/header.html"]
    assert "data-[state=open]:[translate:0]" not in sources["templates/header.html"]
    assert "data-shell-footer" in sources["templates/footer.html"]
    assert "data-shell-cta" in sources["templates/sections/cta.html"]
    assert "data-submit-state=\"idle\"" in sources["templates/sections/cta.html"]


def test_shared_shell_behavior_uses_data_and_aria_state() -> None:
    """Keep presentation state in Tailwind-scannable data and ARIA attributes."""
    source = (LANDING_ROOT / "js" / "main.js").read_text(encoding="utf-8")
    forbidden_fragments = (
        "document.querySelector('.header')",
        "document.querySelector('.theme-toggle')",
        "document.querySelector('.mobile-menu-toggle')",
        "document.querySelector('.mobile-nav')",
        "DOM.body.style.overflow",
        "DOM.header.classList.add('scrolled')",
        "DOM.header.classList.remove('scrolled')",
        "DOM.mobileMenuToggle.classList.toggle('active')",
        "DOM.mobileNav.classList.toggle('open')",
        "submitBtn.style.background",
    )

    for fragment in forbidden_fragments:
        assert fragment not in source
    for required_fragment in (
        "[data-shell-header]",
        "[data-theme-toggle]",
        "[data-mobile-menu-toggle]",
        "[data-mobile-nav]",
        "DOM.mobileNav.dataset.state",
        "DOM.body.classList.toggle('overflow-hidden'",
        "DOM.header.dataset.scrolled",
        "input.setAttribute('aria-invalid', 'true')",
        "submitBtn.dataset.submitState",
    ):
        assert required_fragment in source


def test_generated_release_one_pages_use_the_tailwind_shared_shell() -> None:
    """Require generated Release 1 projections to contain the canonical shell hooks."""
    for relative in ("index.html", "whitepaper.html", "product-delivery.html"):
        html = (LANDING_ROOT / relative).read_text(encoding="utf-8")
        for marker in ("data-shell-header", "data-shell-footer"):
            assert marker in html, f"{relative} is missing {marker}"
    index = (LANDING_ROOT / "index.html").read_text(encoding="utf-8")
    assert "data-shell-cta" in index


def test_generated_freshness_labels_stay_inside_the_final_cta() -> None:
    """Keep generated update dates on the CTA background, not after ``main``."""
    for relative in ("security.html", "whitepaper.html", "productivity.html"):
        html = (LANDING_ROOT / relative).read_text(encoding="utf-8")
        label_position = html.find("data-freshness-label")
        main_end = html.find("</main>")
        final_section_start = html.rfind("<section", 0, main_end)

        assert label_position >= 0, relative
        assert final_section_start < label_position < main_end, relative


def test_release_one_has_no_inline_style_escape_hatch() -> None:
    """Keep every initial Tailwind surface free of inline and embedded styles."""
    targets = [
        LANDING_ROOT / "index.html",
        LANDING_ROOT / "whitepaper.html",
        LANDING_ROOT / "product-delivery.html",
        *_source_files("templates/**/*.html"),
    ]
    inline = re.compile(r"\sstyle\s*=", re.IGNORECASE)
    blocks = re.compile(r"<style(?:\s|>)", re.IGNORECASE)
    offenders = [
        str(path.relative_to(LANDING_ROOT))
        for path in targets
        if inline.search(path.read_text(encoding="utf-8"))
        or blocks.search(path.read_text(encoding="utf-8"))
    ]

    assert not offenders, f"Release 1 inline style escape hatches remain: {offenders}"


def test_global_legacy_style_debt_is_zero() -> None:
    """Require the Story 1113 global zero threshold across all public sources."""
    html_files = _source_files("*.html")
    js_files = _source_files("*.js")
    inline_count = _count_matches(re.compile(r"\sstyle\s*=", re.IGNORECASE), html_files)
    style_block_count = _count_matches(
        re.compile(r"<style(?:\s|>)", re.IGNORECASE), html_files
    )
    dom_mutation_count = _count_matches(
        re.compile(r"\.style\.|style\.setProperty|setAttribute\([^\n]*style", re.IGNORECASE),
        js_files,
    )
    legacy_css_files = [
        path
        for path in (LANDING_ROOT / "css").rglob("*.css")
        if path.name not in {"tailwind.css", "tailwind.min.css"}
    ]

    assert inline_count == INLINE_STYLE_BASELINE
    assert style_block_count == STYLE_BLOCK_BASELINE
    assert dom_mutation_count == DOM_STYLE_MUTATION_BASELINE
    assert len(legacy_css_files) == LEGACY_CSS_FILE_BASELINE
