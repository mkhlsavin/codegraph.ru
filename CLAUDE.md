# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Landing is a sub-project of CodeGraph. See [`../../CLAUDE.md`](../../CLAUDE.md) for the main project context (Python backend, architecture, build scripts, domain plugins, config).

## What This Is

Public landing site for CodeGraph (codegraph.ru) — a static website deployed to GitHub Pages. Russian-first marketing landing (7 HTML pages) + bilingual documentation hub (`docs/en/`, `docs/ru/`).

## Local Preview

```bash
python -m http.server 8000
# Open http://localhost:8000
```

The demo terminal in the hero section calls `localhost:8000` in dev or `api.codegraph.ru` in prod (auto-detected by hostname). Falls back to mock responses when API is unavailable.

## Build Scripts

Build scripts live in `../../scripts/`. **Run from the codegraph root**, not from landing/.

### Landing (`build_landing.py`)
```bash
python scripts/build_landing.py              # Update header/footer in all 7 HTML pages from templates
python scripts/build_landing.py --sections   # Rebuild index.html from modular sections (templates/sections/)
python scripts/build_landing.py --assets     # Minify CSS/JS only (styles.min.css, main.min.js)
python scripts/build_landing.py --all        # HTML + minification
```

### Documentation (`build_docs.py`)
```bash
python scripts/build_docs.py --no-translate              # Build EN docs only (default, no API keys needed)
python scripts/build_docs.py                              # Full build with EN → RU translation (needs LLM API keys)
python scripts/build_docs.py --provider yandex            # YandexGPT (YANDEX_API_KEY, YANDEX_FOLDER_ID)
python scripts/build_docs.py --provider gigachat          # GigaChat (GIGACHAT_CREDENTIALS)
python scripts/build_docs.py --provider openai            # OpenAI (OPENAI_API_KEY)
python scripts/build_docs.py --force-translate            # Re-translate all, ignore existing RU files
python scripts/build_docs.py --mock                       # Mock translator (testing, no API calls)
python scripts/build_docs.py --validate                   # Validate links in existing output only
```
Markdown source: `D:/work/codegraph/docs/{section}/`. Output: `docs/en/` and `docs/ru/`.

## Pages (7 root-level HTML files)

All share header/footer from templates. All must stay in sync.

| File | Purpose |
|------|---------|
| `index.html` | Main landing (Russian, ~128KB, all sections inline) |
| `whitepaper.html` | Technical whitepaper |
| `security.html` | Vertical: SAST, taint analysis, SIEM |
| `productivity.html` | Vertical: onboarding, code search |
| `compliance.html` | Vertical: 152-ФЗ, ГОСТ, ФСТЭК |
| `cpg.html` | Vertical: CPG technology deep-dive |
| `ai-engineering.html` | Vertical: ML infrastructure, AI-generated code verification, completed experiments cleanup |

Each vertical page has its own FAQ section (unique questions per page, no overlap) and JSON-LD FAQPage structured data in `<head>`.

## Templates

### Header & Footer
`templates/header.html` and `templates/footer.html` are the source of truth. They use `{variable}` placeholder syntax (`{base_url}`, `{docs_url}`, `{nav_features}`, etc.) substituted by `build_landing.py`. They are **NOT auto-compiled** — either run the build script or edit all 7 HTML pages manually.

### Sections
`templates/sections/` contains modular sections for `index.html`, rebuilt via `--sections` flag. Order:
hero → problems → solution → features → metrics → integrations → architecture → usp → faq → cta

## CSS Architecture

`css/styles.css` is the entry point — `@import`s all partials. Works in browsers without bundling; `styles.min.css` is the production bundle.

```
css/
├── styles.css, styles.min.css
├── base/          _variables.css (design tokens), _reset.css, _typography.css, _animations.css
├── components/    One file per section (_header, _hero, _problems, _solution, _features,
│                  _metrics, _integrations, _usp, _faq, _cta, _footer, _buttons, _sections)
├── architecture/  _architecture.css
├── pages/         _whitepaper.css, _docs.css
└── layout/        _responsive.css, _print.css
```

Design tokens in `_variables.css`: primary `#2563EB`, fonts Inter + JetBrains Mono, container max `1280px`. Dark theme via `[data-theme="dark"]` attribute. Breakpoints: mobile (<768px), tablet (768px+), desktop (1024px+), large (1280px+).

## JavaScript

Single file `js/main.js` (+ minified `main.min.js`). IIFE, no framework, no dependencies.

Key modules: theme toggle (localStorage + prefers-color-scheme), demo terminal (API at `/api/v1/demo/chat`, 180s timeout, mock fallback), animated counters (`[data-count]` via IntersectionObserver), feature tabs, FAQ accordion (search + category filters), integration filters, smooth scroll (80px offset).

API auto-detection: `localhost:8000` in dev, `api.codegraph.ru` in prod. Rate limiting (429) handled with user message. XSS protection via `escapeHtml()` on API responses.

## Critical Rules

1. **Header/footer sync** — When editing header or footer, update ALL 7 HTML pages. Use `build_landing.py` from codegraph root to automate, or edit each file manually.
2. **ICP links** — Footer must include links to all 5 vertical pages (security, productivity, compliance, cpg, ai-engineering) for SEO internal linking.
3. **Russian-first** — All user-facing text on landing pages must be in Russian. English only for proper names and abbreviations (CPG, AST, CFG, SARIF, DuckDB). English content lives only in `docs/en/`.
4. **Minified assets** — `styles.min.css` and `main.min.js` are regenerated via `--assets`. CSS `@import` in `styles.css` works directly in browsers without bundling.
5. **Submodule workflow** — After pushing to landing, update submodule pointer in parent codegraph: `cd D:/work/codegraph && git add docs/landing && git commit`.
6. **Scenario count** — CodeGraph has **21** scenarios (not 20). #21 is "Структурный поиск паттернов".

## Localization

Terms that must be translated (not left in English) on landing pages:
- taint analysis → анализ потоков данных
- pattern matching → сопоставление шаблонов
- source/sink → источник/приёмник
- code smells → признаки плохого кода
- knowledge base → база знаний
- air-gapped → изолированная среда / изолированный контур
- compliance evidence → доказательства соответствия
- audit trail → журнал аудита
- PII → ПДн (персональные данные)
- findings → обнаружения
- on-premise — keep as-is (accepted IT term in Russian)

## Blog

`blog/` contains Habr article drafts (markdown, `habr-NN-slug.md`). 9 articles covering CPG vs SAST, onboarding, dogfooding, parser design, taint analysis, DuckDB for CPG, handler-formatter architecture, and audit. Disallowed in `robots.txt` — not indexed by search engines.

## SEO & Deployment

- `CNAME` → `codegraph.ru` (GitHub Pages custom domain)
- `index.html` contains JSON-LD structured data (Organization, SoftwareApplication, FAQPage)
- Vertical pages have their own FAQPage JSON-LD in `<head>`
- `sitemap.xml` — 15 public URLs with priorities
- `robots.txt` — allows crawling, disallows `/admin/`, `/api/`, `/templates/`, `/blog/`, `/.claude/`, `*.json`
- `.nojekyll` — disables Jekyll processing on GitHub Pages
- `yandex_76c03f1a56dcfce0.html` — Yandex Webmaster verification
- `BingSiteAuth.xml` — Bing Webmaster verification

## Git Workflow

Remote: `origin` → `github.com/mkhlsavin/codegraph.ru.git` (public). Branch: `main`. Auto-deployed via GitHub Pages on push.

```bash
git push origin main
# Then update submodule in codegraph:
cd D:/work/codegraph && git add docs/landing && git commit -m "docs: update landing submodule"
```

Commit prefixes: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`
