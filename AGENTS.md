# AGENTS.md — Landing

Agent guide for `D:\work\codegraph\docs\landing`.
Primary source of truth: `docs/landing/CLAUDE.md`.

## Scope
- Public static landing site for CodeGraph (`codegraph.ru`).
- Separate subproject/repo workflow from backend code.
- Russian-first marketing pages + bilingual docs hub.

## Critical rules
1. Keep header/footer synchronized across all 7 root HTML pages.
2. Keep docs footer templates synchronized in docs builder scripts.
3. Preserve internal linking to all vertical pages for SEO.
4. Keep landing user-facing content Russian-first.
5. Regenerate minified assets via build scripts when CSS/JS changes.
6. Respect submodule workflow when syncing with parent repo.

## Local preview
```bash
python -m http.server 8000
```

## Build commands (run from codegraph root)
```bash
python scripts/build_landing.py
python scripts/build_landing.py --sections
python scripts/build_landing.py --assets
python scripts/build_landing.py --all

python scripts/build_docs.py --no-translate
python scripts/build_docs.py --validate
```

## Content/layout reminders
- `solution.html` is interactive demo section; `solutions.html` is role cards section.
- Keep JSON-LD FAQPage data consistent with visible FAQ content.
- Do not introduce framework dependencies into `js/main.js`.
