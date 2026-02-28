# CodeGraph Landing Page

Статический сайт [codegraph.ru](https://codegraph.ru) — маркетинговый лендинг и документация продукта CodeGraph. Деплоится на GitHub Pages при пуше в `main`.

## Локальный запуск

```bash
python -m http.server 8000
# Открыть http://localhost:8000
```

Демо-терминал в hero-секции автоматически определяет окружение: `localhost:8000` в dev, `api.codegraph.ru` в prod. При недоступности API отображает мок-ответы.

## Сборка

Скрипты сборки находятся в родительском репозитории codegraph (`../../scripts/`). **Запускать из корня codegraph**, не из landing/.

### Лендинг

```bash
python scripts/build_landing.py              # Обновить header/footer во всех 6 HTML-страницах
python scripts/build_landing.py --sections   # Пересобрать index.html из модульных секций
python scripts/build_landing.py --assets     # Минификация CSS/JS (styles.min.css, main.min.js)
python scripts/build_landing.py --all        # Всё вместе
```

### Документация

```bash
python scripts/build_docs.py --no-translate              # Сборка EN-документации (по умолчанию, без API-ключей)
python scripts/build_docs.py                              # Полная сборка с переводом EN → RU
python scripts/build_docs.py --provider yandex            # YandexGPT
python scripts/build_docs.py --provider gigachat          # GigaChat
python scripts/build_docs.py --provider openai            # OpenAI
python scripts/build_docs.py --validate                   # Только валидация ссылок
```

Результат: `docs/en/` и `docs/ru/`.

## Структура

```
landing/
├── index.html              # Основной лендинг (RU, ~128KB)
├── whitepaper.html         # Технический whitepaper
├── security.html           # Вертикаль: SAST, анализ потоков данных, SIEM
├── productivity.html       # Вертикаль: онбординг, поиск по коду
├── compliance.html         # Вертикаль: 152-ФЗ, ГОСТ, ФСТЭК
├── cpg.html                # Вертикаль: технология CPG
│
├── css/
│   ├── styles.css          # Точка входа (@import партиалов)
│   ├── styles.min.css      # Минифицированный бандл
│   ├── base/               # Дизайн-токены, ресет, типографика, анимации
│   ├── components/         # По файлу на секцию лендинга
│   ├── pages/              # Стили whitepaper, документации
│   └── layout/             # Адаптивность, печать
│
├── js/
│   ├── main.js             # Вся логика (IIFE, без зависимостей)
│   └── main.min.js         # Минифицированная версия
│
├── templates/
│   ├── header.html         # Шаблон навигации ({base_url}, {docs_url}, ...)
│   ├── footer.html         # Шаблон футера
│   └── sections/           # Модульные секции index.html
│
├── assets/svg/             # Логотипы, иконки, диаграммы
├── docs/{en,ru}/           # HTML-документация
├── sitemap.xml             # 14 публичных URL с приоритетами
├── CNAME                   # codegraph.ru
└── .nojekyll
```

## Страницы и FAQ

Все 6 HTML-страниц используют общий header/footer из шаблонов. При изменении навигации или футера — обновить все страницы через `build_landing.py` или вручную.

Каждая вертикальная страница имеет уникальный FAQ (вопросы не пересекаются между страницами) и JSON-LD FAQPage в `<head>`:

| Страница | FAQ-тематика | Вопросов |
|----------|-------------|----------|
| `index.html` | Общие вопросы о продукте, AI, надёжность, POC | 26 |
| `security.html` | DLP, сравнение со сканерами, изолированный контур | 8 |
| `productivity.html` | vs Copilot, миграция, метрики, внедрение | 8 |
| `compliance.html` | Тендеры, госреференсы, русская документация | 8 |
| `cpg.html` | CGO/FFI, масштабируемость, глубина анализа, CI/CD | 8 |

## Дизайн-система

Дизайн-токены в `css/base/_variables.css`:
- **Основной цвет**: `#2563EB`
- **Шрифты**: Inter (текст), JetBrains Mono (код)
- **Контейнер**: max `1280px`
- **Темы**: светлая по умолчанию, тёмная через `[data-theme="dark"]`
- **Брейкпоинты**: mobile (<768px), tablet (768px+), desktop (1024px+), large (1280px+)

## Локализация

Лендинг — русскоязычный. Английский контент только в `docs/en/`. Технические термины переводятся:

| English | Русский |
|---------|---------|
| taint analysis | анализ потоков данных |
| pattern matching | сопоставление шаблонов |
| source / sink | источник / приёмник |
| code smells | признаки плохого кода |
| air-gapped | изолированная среда |
| compliance evidence | доказательства соответствия |
| audit trail | журнал аудита |
| PII | ПДн |

Исключения: on-premise, CPG, AST, CFG, SARIF, DuckDB — оставляются как есть.

## SEO

- JSON-LD (Organization, SoftwareApplication, FAQPage) в `index.html` и вертикальных страницах
- OpenGraph и Twitter Card метатеги
- `robots.txt` — разрешает всё кроме `/admin/`, `/api/`, `*.json`
- `sitemap.xml` — 14 URL с приоритетами
- `BingSiteAuth.xml` — верификация Bing

## Деплой

Автоматический через GitHub Pages при пуше в `main`:

```bash
git push origin main
```

После пуша — обновить субмодуль в родительском codegraph:

```bash
cd D:/work/codegraph
git add docs/landing
git commit -m "docs: update landing submodule"
```

Remote: `github.com/mkhlsavin/codegraph.ru.git` (публичный). Префиксы коммитов: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`.
