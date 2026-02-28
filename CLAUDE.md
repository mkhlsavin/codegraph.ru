# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Landing is a sub-project of CodeGraph. See [`../../CLAUDE.md`](../../CLAUDE.md) for the main project context (Python backend, architecture, build scripts, domain plugins, config).

## What This Is

Public landing site for CodeGraph (codegraph.ru) — a static website deployed to GitHub Pages via the `codegraph-landing` repo (`github.com/mkhlsavin/codegraph-landing`). The site is bilingual (Russian primary, English docs), serves as both marketing landing and documentation hub.

## Local Preview

```bash
python -m http.server 8000
# Open http://localhost:8000
```

## Build Scripts

Build scripts live in the parent codegraph repo (`../../scripts/`). Run from the codegraph root.

### Landing (`build_landing.py`)
```bash
python scripts/build_landing.py              # Update header/footer in all HTML pages from templates
python scripts/build_landing.py --sections   # Rebuild index.html from modular sections (templates/sections/)
python scripts/build_landing.py --assets     # Minify CSS/JS only (styles.min.css, main.min.js)
python scripts/build_landing.py --all        # HTML + minification
```

### Documentation (`build_docs.py`)
```bash
python scripts/build_docs.py --no-translate              # Build EN docs only (default usage)
python scripts/build_docs.py                              # Full build with EN → RU translation (needs LLM API keys)
python scripts/build_docs.py --provider yandex            # Use YandexGPT (YANDEX_API_KEY, YANDEX_FOLDER_ID)
python scripts/build_docs.py --provider gigachat          # Use GigaChat (GIGACHAT_CREDENTIALS)
python scripts/build_docs.py --provider openai            # Use OpenAI (OPENAI_API_KEY)
python scripts/build_docs.py --force-translate            # Re-translate all, ignore existing RU files
python scripts/build_docs.py --mock                       # Mock translator (testing, no API calls)
python scripts/build_docs.py --validate                   # Validate links in existing output only
python scripts/build_docs.py --check-status               # Show translation status summary
```
Output goes to `docs/en/` and `docs/ru/`.

## Repository Structure

### Pages (root-level HTML)
- `index.html` — Main landing page (Russian). ~118KB, contains all sections inline
- `whitepaper.html` — Technical whitepaper
- `security.html`, `productivity.html`, `compliance.html`, `cpg.html` — Vertical-specific landing pages

### Templates (source of truth for shared components)
Templates use `{variable}` placeholder syntax (e.g., `{base_url}`, `{docs_url}`, `{nav_features}`). They are NOT auto-compiled — changes in templates must be manually applied to the HTML pages.

- `templates/header.html` — Navigation header (shared across all pages)
- `templates/footer.html` — Footer with links (shared across all pages)
- `templates/sections/*.html` — Modular landing page sections (hero, problems, solution, features, metrics, integrations, architecture, usp, faq, cta)

### CSS Architecture
`css/styles.css` is the entry point — it `@import`s all partials:

```
css/
├── styles.css              # Entry point (imports only)
├── styles.min.css          # Minified bundle
├── base/
│   ├── _variables.css      # Design tokens (colors, spacing, typography, shadows)
│   ├── _reset.css
│   ├── _typography.css
│   └── _animations.css
├── components/             # One file per landing section
│   ├── _header.css, _hero.css, _problems.css, _solution.css,
│   ├── _features.css, _metrics.css, _integrations.css,
│   ├── _usp.css, _faq.css, _cta.css, _footer.css, _buttons.css, _sections.css
├── architecture/
│   └── _architecture.css
├── pages/
│   ├── _whitepaper.css
│   └── _docs.css
└── layout/
    ├── _responsive.css     # Breakpoints: 1200px+ desktop, 1024px+ tablet, <1024px mobile
    └── _print.css
```

### Design Tokens
All in `css/base/_variables.css`. Light theme by default, dark theme via `[data-theme="dark"]` attribute. Key values:
- Primary: `#2563EB` / Font: Inter / Mono: JetBrains Mono
- Container max: `1280px`

### JavaScript
Single file: `js/main.js` (+ minified `main.min.js`). IIFE pattern, no framework.

Key features:
- **Theme toggle** — persists to `localStorage`, respects `prefers-color-scheme`
- **Live demo terminal** — hero section interactive demo that calls CodeGraph API (`api.codegraph.ru` in prod, `localhost:8000` in dev) with mock response fallbacks
- **Animated counters** — `[data-count]` elements animate on scroll via IntersectionObserver
- **Feature tabs, FAQ accordion, integration filters** — all vanilla JS
- **Smooth scroll** — for `#anchor` links with 80px offset

### Documentation (`docs/`)
Pre-built HTML documentation in `docs/en/` and `docs/ru/`, organized as:
- `getting-started/` — Installation, configuration
- `guides/` — 20 scenario guides (01-onboarding through 20-dependencies), plus reference guides
- `api/` — REST, WebSocket, ACP, Demo API
- `integrations/` — Claude Code, GigaChat, Yandex AI Studio
- `reference/` — Agents, architecture
- `enterprise/` — Enterprise docs

### SEO & Deployment
- `CNAME` → `codegraph.ru` (GitHub Pages custom domain)
- `sitemap.xml` — Lists all public pages
- `robots.txt` — Allows crawling, disallows `/admin/`, `/api/`
- `BingSiteAuth.xml` — Bing webmaster verification
- `.nojekyll` — Disables Jekyll processing on GitHub Pages
- `index.html` contains JSON-LD structured data (Organization, SoftwareApplication, FAQPage)

## Critical Rules

1. **Footer/header sync** — When editing the footer or header, update ALL HTML pages (index.html, whitepaper.html, security.html, productivity.html, compliance.html, cpg.html) to stay consistent. Use `python scripts/build_landing.py` from codegraph root to automate this, or edit each file manually.
2. **ICP links** — Footer must include links to all vertical pages (security, productivity, compliance, cpg) for SEO internal linking.
3. **Russian-first** — The main landing (`index.html`) is in Russian. English content lives only in `docs/en/`.
4. **Minified assets** — `styles.min.css` and `main.min.js` are regenerated via `python scripts/build_landing.py --assets`. CSS `@import` in `styles.css` works directly in browsers without bundling.

## Git Workflow

Remote: `origin` → `github.com/mkhlsavin/codegraph.ru.git` (public). Branch: `main`. Deployed automatically via GitHub Pages on push.

```bash
git add .
git commit -m "docs: update landing page"
git push origin main
```

Commit prefixes: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`
