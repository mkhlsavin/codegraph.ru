# CodeGraph Landing Page

Статический сайт [codegraph.ru](https://codegraph.ru) — маркетинговый лендинг и документация продукта CodeGraph. Деплоится на GitHub Pages при пуше в `main`.

## Локальный запуск

```bash
python -m http.server 8000
# Открыть http://localhost:8000
```

## Сборка

Скрипты сборки находятся в родительском репозитории codegraph (`../../scripts/`). Запускать из корня codegraph.

### Сборка лендинга

```bash
# Обновить header/footer во всех HTML-страницах из шаблонов
python scripts/build_landing.py

# Пересобрать index.html из модульных секций (templates/sections/)
python scripts/build_landing.py --sections

# Только минификация CSS/JS (styles.min.css, main.min.js)
python scripts/build_landing.py --assets

# Всё вместе: HTML + минификация
python scripts/build_landing.py --all
```

### Сборка документации

```bash
# Сборка документации (по умолчанию без перевода)
python scripts/build_docs.py --no-translate

# Полная сборка с переводом EN → RU (требует API-ключи LLM)
python scripts/build_docs.py

# Выбор LLM-провайдера для перевода
python scripts/build_docs.py --provider yandex    # YandexGPT (YANDEX_API_KEY, YANDEX_FOLDER_ID)
python scripts/build_docs.py --provider gigachat   # GigaChat (GIGACHAT_CREDENTIALS)
python scripts/build_docs.py --provider openai     # OpenAI (OPENAI_API_KEY)

# Принудительный переперевод всех файлов (игнорирует существующие RU)
python scripts/build_docs.py --force-translate

# Тест с мок-переводчиком (без реальных API-вызовов)
python scripts/build_docs.py --mock

# Только валидация ссылок в существующей документации
python scripts/build_docs.py --validate

# Показать статус переводов и выйти
python scripts/build_docs.py --check-status
```

Результат сборки документации попадает в `docs/en/` и `docs/ru/`.

## Структура проекта

```
landing/
├── index.html              # Основной лендинг (RU)
├── whitepaper.html         # Технический whitepaper
├── security.html           # Лендинг: безопасность
├── productivity.html       # Лендинг: продуктивность
├── compliance.html         # Лендинг: комплаенс
├── cpg.html                # Лендинг: технология CPG
│
├── css/
│   ├── styles.css          # Точка входа (@import всех партиалов)
│   ├── styles.min.css      # Минифицированный бандл
│   ├── base/               # _variables.css, _reset.css, _typography.css, _animations.css
│   ├── components/         # По файлу на каждую секцию лендинга
│   ├── architecture/       # _architecture.css
│   ├── pages/              # _whitepaper.css, _docs.css
│   └── layout/             # _responsive.css, _print.css
│
├── js/
│   ├── main.js             # Вся логика: тема, мобильное меню, демо-терминал, счётчики
│   └── main.min.js         # Минифицированная версия
│
├── assets/
│   ├── favicon.svg
│   ├── og-image.png        # OpenGraph-картинка для соцсетей
│   └── svg/                # Логотипы, иконки, диаграммы
│
├── templates/              # Шаблоны (source of truth для header/footer)
│   ├── header.html         # Навигация (переменные: {base_url}, {docs_url}, ...)
│   ├── footer.html         # Футер с ссылками
│   └── sections/           # Секции лендинга (hero, problems, solution, ...)
│
├── blog/                   # Статьи (Markdown)
│
├── docs/                   # HTML-документация
│   ├── en/                 # English
│   └── ru/                 # Русский
│
├── robots.txt              # Директивы для поисковиков
├── sitemap.xml             # XML-карта сайта
├── CNAME                   # Кастомный домен (codegraph.ru)
├── BingSiteAuth.xml        # Верификация Bing
└── .nojekyll               # Отключение Jekyll на GitHub Pages
```

## Работа со страницами

### Шаблоны

`templates/header.html` и `templates/footer.html` — источник истины для общих компонентов. Используют синтаксис `{variable}` для подстановки (например, `{base_url}`, `{nav_features}`, `{docs_url}`).

При изменении header/footer нужно обновить все HTML-страницы. Это можно сделать автоматически через `python scripts/build_landing.py` (из корня codegraph) или вручную в каждом файле:
- `index.html`
- `whitepaper.html`
- `security.html`
- `productivity.html`
- `compliance.html`
- `cpg.html`

### Секции лендинга

`templates/sections/` содержит модульные секции `index.html`. Порядок на странице:

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

## Дизайн-система

### Цвета

Определены в `css/base/_variables.css`. Светлая тема по умолчанию, тёмная через атрибут `[data-theme="dark"]`.

| Токен | Светлая | Тёмная | Назначение |
|-------|---------|--------|------------|
| `--color-primary` | `#2563EB` | — | Ссылки, кнопки, акценты |
| `--color-bg` | `#FFFFFF` | `#0F172A` | Фон страницы |
| `--color-bg-alt` | `#F8FAFC` | `#1E293B` | Фон карточек, альт. секции |
| `--color-text` | `#1E293B` | `#F1F5F9` | Основной текст |
| `--color-text-muted` | `#64748B` | `#94A3B8` | Второстепенный текст |

### Типографика

- **Шрифт**: `Inter` (с системным фолбеком)
- **Моноширинный**: `JetBrains Mono`
- **Заголовки**: semibold (600), line-height 1.25
- **Текст**: regular (400), line-height 1.5

### Иконки

Монохромные SVG в `assets/svg/`:
- `currentColor` fill для совместимости с темами
- Размер по умолчанию: 24x24

### Адаптивные брейкпоинты

| Брейкпоинт | Ширина | Лейаут |
|------------|--------|--------|
| Mobile | <768px | Гамбургер-меню, 1 колонка |
| Tablet | 768px+ | 2 колонки, навигация видна |
| Desktop | 1024px+ | 4 колонки, полный лейаут |
| Large | 1280px+ | Расширенная сетка интеграций |

## JavaScript

`js/main.js` — единый файл, IIFE, без зависимостей. Основные модули:

| Модуль | Описание |
|--------|----------|
| Theme | Переключение свет/тёмн, сохранение в `localStorage`, `prefers-color-scheme` |
| Demo terminal | Интерактивный терминал в hero, запросы к API (`api.codegraph.ru` / `localhost:8000`), мок-ответы при недоступности |
| Counters | Анимация `[data-count]` элементов при скролле (IntersectionObserver) |
| Feature tabs | Переключение табов в секции features |
| FAQ | Аккордеон, поиск, фильтры по категориям |
| Integration filters | Фильтрация карточек интеграций |

## SEO

- `index.html` содержит JSON-LD (Organization, SoftwareApplication, FAQPage)
- OpenGraph и Twitter Card метатеги
- `robots.txt` — разрешает всё кроме `/admin/` и `/api/`
- `sitemap.xml` — все публичные страницы

## Деплой

Автоматический через GitHub Pages при пуше в `main`:

```bash
git add .
git commit -m "docs: описание изменений"
git push origin main
```

Remote: `github.com/mkhlsavin/codegraph.ru.git` (публичный).
