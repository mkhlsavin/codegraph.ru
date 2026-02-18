# Landing Page

Web assets and templates for the CodeGraph public landing page.

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   Landing Page Assets                        │
├─────────────────────────────────────────────────────────────┤
│  Pages               │  Assets              │  Build        │
│  ├─ index.html       │  ├─ CSS styles       │  ├─ Templates │
│  ├─ whitepaper.html  │  ├─ JavaScript       │  ├─ Sections  │
│  └─ docs/            │  └─ SVG graphics     │  └─ Scripts   │
└─────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
landing/
├── index.html              # Main landing page
├── whitepaper.html         # Technical whitepaper
├── robots.txt              # Search engine directives
├── sitemap.xml             # XML sitemap
│
├── css/
│   └── styles.css          # Main stylesheet
│
├── js/
│   └── main.js             # JavaScript functionality
│
├── assets/
│   └── svg/                # SVG graphics
│       ├── logo.svg
│       ├── logo-compact.svg
│       ├── diagram-architecture.svg
│       ├── diagram-pipeline.svg
│       └── icon-*.svg      # Feature icons
│
├── templates/              # Page templates
│   ├── header.html         # Navigation header
│   ├── footer.html         # Page footer
│   └── sections/           # Modular content sections
│       ├── hero.html
│       ├── problems.html
│       ├── solution.html
│       ├── features.html
│       ├── metrics.html
│       ├── integrations.html
│       ├── architecture.html
│       ├── usp.html
│       ├── faq.html
│       └── cta.html
│
└── docs/                   # Generated documentation
    ├── en/                 # English docs
    └── ru/                 # Russian docs
```

## Local Preview

```bash
# Start local server
cd docs/landing
python -m http.server 8000

# Open in browser
open http://localhost:8000
```

## Building Pages

### Build Landing Page

```bash
# Update header/footer in existing files
python scripts/build_landing.py

# Build from modular sections (recommended)
python scripts/build_landing.py --sections
```

### Build Documentation

```bash
# Full build with translation
python scripts/build_docs.py

# English only
python scripts/build_docs.py --no-translate
```

## Design System

### Colors

| Name | Value | Usage |
|------|-------|-------|
| Primary | `#0366d6` | Links, buttons, accents |
| Background | `#0d1117` | Dark theme background |
| Surface | `#161b22` | Cards, panels |
| Text | `#c9d1d9` | Primary text |
| Muted | `#8b949e` | Secondary text |

### Typography

- **Font**: System font stack
- **Headings**: Semi-bold, 1.2-1.4 line height
- **Body**: Regular, 1.5 line height
- **Code**: Monospace, `#58a6ff` accent

### Icons

All icons are monochrome SVGs with:
- `currentColor` fill for theme compatibility
- 24x24 default size
- Consistent stroke width

## Responsive Breakpoints

| Breakpoint | Width | Layout |
|------------|-------|--------|
| Desktop | 1200px+ | Full sidebar + TOC |
| Tablet | 1024px+ | Sidebar only |
| Mobile | <1024px | Collapsed navigation |

## Key CSS Classes

| Class | Description |
|-------|-------------|
| `.doc-layout` | Flexbox container (sidebar + main) |
| `.doc-sidebar` | Sticky sidebar navigation |
| `.doc-main` | Main content area (max-width: 900px) |
| `.doc-hero` | Page header with gradient |
| `.doc-content` | Article content container |
| `.doc-toc` | Sticky table of contents |

## Section Order

When building with `--sections`, sections render in this order:

1. hero
2. problems
3. solution
4. features
5. metrics
6. integrations
7. architecture
8. usp
9. faq
10. cta

## Deployment

The landing page is deployed to GitHub Pages via the `codegraph-landing` repository:

```bash
# From landing directory
git add .
git commit -m "Update landing page"
git push origin main
```

## Related Documentation

- [Build Scripts](../../scripts/README.md) - Build documentation
- [Docs Builder](../../scripts/docs_builder/README.md) - Documentation system
- [Main Documentation](../README.md) - Documentation index
