# Plan: Update whitepaper.html and index.html

## Context

Four ICP-targeted landing pages were recently created (security.html, productivity.html, compliance.html, cpg.html), but neither whitepaper.html nor index.html link to them. Additionally, whitepaper.html is missing SEO meta tags that all other pages already have (OG, canonical, hreflang, Twitter Cards, JSON-LD, Yandex Metrika). The index.html is also missing mentions of newer technical features (pattern engine, watch mode, MCP, FFI).

Data in whitepaper.html (v3.0, Feb 2026) is already current -- no metric updates needed.

## Files to Modify

- `D:\work\codegraph\docs\landing\whitepaper.html` (1421 lines)
- `D:\work\codegraph\docs\landing\index.html` (~2110 lines)

## Changes

### 1. whitepaper.html -- Add SEO meta tags to `<head>` (lines 6-9)

Insert after line 7 (after keywords meta), before `<title>`:
- Open Graph tags (og:title, og:description, og:type=article, og:url, og:image)
- Canonical URL + hreflang (ru + x-default)
- Twitter Card (summary_large_image)
- JSON-LD: `TechArticle` (with datePublished/dateModified) + `BreadcrumbList`

Pattern: identical structure to security.html/index.html head sections.

### 2. whitepaper.html -- Add Yandex Metrika (before `</body>`, after line 1418)

Same Metrika snippet as all other pages (XXXXXX placeholder counter ID).

### 3. whitepaper.html -- Add cross-links to ICP pages (before CTA box, line 1334)

Insert a "Подробнее по направлениям" block with 4 linked cards:
- security.html (Безопасность)
- productivity.html (Продуктивность)
- compliance.html (Compliance)
- cpg.html (Code Property Graph)

Uses existing `highlight-box` CSS class for visual consistency.

### 4. whitepaper.html -- Add ICP links to footer "Ресурсы" (line 1385-1387)

Add 4 footer links after existing "Whitepaper" and "Документация (EN)" entries:
- security.html, productivity.html, compliance.html, cpg.html

### 5. index.html -- New "Решения по ролям" section (between lines 714-716)

Insert between metrics section (`</section>` at line 714) and integrations section (line 716). Four clickable cards using existing `feature-card` CSS:
- CISO/DevSecOps -> security.html (taint analysis, 12% FP, SIEM, SARIF)
- CTO/VP Engineering -> productivity.html (6x onboarding, 600x search, 60M ROI)
- CIO/Compliance -> compliance.html (152-FZ, GOST, DLP, RBAC)
- VP Eng/Tech Lead -> cpg.html (GoCPG, 33 passes, 11 langs, 30-60x faster)

### 6. index.html -- Add ICP links to footer "Ресурсы" (lines 2063-2064)

Add 4 footer links after existing "Whitepaper" and "Документация (EN)".

### 7. index.html -- Add new feature cards to capability tabs

- **DevSecOps tab**: Add "Структурный поиск паттернов" card (70+ YAML rules, CST matching, CPG constraints) and "Live-мониторинг кода" card (watch mode, MCP server, live dashboard)
- **Разработчики tab**: Add "Кросс-языковый анализ (FFI)" card (CGO Go->C, ctypes Python->C)
- **Архитекторы tab**: Add "LLM-генерация правил анализа" card (natural language -> YAML rule generation)

### 8. index.html -- Update solution subtitle (line 357)

From: `Yandex AI + Code Property Graph + гибридный поиск + 13 агентов`
To: `Yandex AI + Code Property Graph + гибридный поиск + 13 агентов + 70 YAML-правил`

### 9. Bonus: Fix "30 passes" -> "33 passes" in security.html and cpg.html

These pages currently say "30 аналитических пассов" but the correct number is 33 (per CLAUDE.md and whitepaper.html). Quick find-and-replace.

## Verification

1. Open each modified HTML file in a browser and verify:
   - All new links work (click-through to ICP pages)
   - No layout breakage in new sections
   - Footer links render correctly
2. Validate JSON-LD with Google Rich Results Test (paste `<script>` blocks)
3. Check OG/Twitter cards with metatags.io or Twitter Card validator
4. `git diff` to confirm only intended changes
