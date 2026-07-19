---
type: Development Note
title: Agents
description: Development Note for Agents.
tags:
- development_note
timestamp: '2026-06-14T13:13:53Z'
doc_kind: development_note
language: mixed
source_path: docs/landing/AGENTS.md
status: active
owner: engineering
audience:
- engineering
memory_policy: repo_only
topic: documentation
public_projection: internal
reason_unclassified: fallback_classifier_rule
migration_followup: review_for_more_specific_okf_type
---
# AGENTS.md — Landing

Agent guide for `D:\work\codegraph\docs\landing`.

## Scope and source of truth
- Public static landing site for CodeGraph (`codegraph.ru`).
- Separate subproject and separate public repo workflow from the backend.
- Russian-first landing pages plus the bilingual docs hub.
- Treat the code and build assets as the source of truth:
  - pages and assets under `docs/landing/`
  - templates under `docs/landing/templates/`
  - build scripts under `scripts/build_landing.py` and `scripts/build_docs.py`
- Use `docs/landing/CLAUDE.md` only as secondary context when it matches the code.
- Inherit shared repo constraints from `../../AGENTS.md`.

## Critical rules
1. Keep header and footer synchronized across all 7 root HTML pages.
2. Keep docs footer templates synchronized in the docs builder sources as well as the landing templates.
3. Preserve internal SEO links to every vertical page registered in
   `scripts/build_landing.py`; do not maintain a second hard-coded count here.
4. Keep landing user-facing content Russian-first.
5. Regenerate minified assets when CSS or JS changes.
6. Respect the separate submodule workflow when syncing this subproject with the parent repo.
7. CodeGraph has 21 scenarios, and S21 is `Interface Docs Sync`; do not label it as pattern search.

## Local preview
```bash
python -m http.server 8000
```

## Build commands
Run these from the CodeGraph root, not from `docs/landing/`.

```bash
python scripts/build_landing.py
python scripts/build_landing.py --sections
python scripts/build_landing.py --assets
python scripts/build_landing.py --all

python scripts/build_docs.py --no-translate
python scripts/build_docs.py --validate
```

## Content and layout reminders
- `templates/header.html` and `templates/footer.html` are the source of truth for shared landing chrome.
- `solution.html` is the interactive demo section; `solutions.html` is the role-cards section.
- Keep JSON-LD `FAQPage` data aligned with the visible FAQ content on each page.
- Do not add framework dependencies to `js/main.js`.
- The hero demo uses local API in dev and `api.codegraph.ru` in prod; preserve that auto-detection behavior.

## Localization reminders
- Landing copy should stay Russian except for accepted product names and technical abbreviations.
- Prefer established translations already used in templates, pages, and generated docs, for example:
  - `taint analysis` -> `анализ потоков данных`
  - `pattern matching` -> `сопоставление шаблонов`
  - `dead experiments` -> `завершённые эксперименты`
  - `audit trail` -> `журнал аудита`
  - `PII` -> `ПДн`

## SEO and deployment reminders
- Keep `CNAME`, `sitemap.xml`, `robots.txt`, and verification files intact.
- Vertical pages must keep their own FAQ structured data in `<head>`.
- GitHub Pages deployment is driven from the landing repo on `main`.

## Workflow safety
- After changes to shared HTML fragments, rebuild affected pages instead of editing generated output inconsistently.
- After CSS or JS edits, regenerate `styles.min.css` and `main.min.js`.
- If this subproject is pushed independently, update the parent repo submodule pointer afterward.
