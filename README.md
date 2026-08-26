---
type: Directory Index
title: CodeGraph public site
description: Maintainer guide for the generated CodeGraph landing and documentation site.
tags:
- directory_index
- landing
timestamp: '2026-08-26T00:00:00Z'
doc_kind: directory_index
language: ru
source_path: docs/landing/README.md
status: active
owner: documentation
audience:
- engineering
- documentation
memory_policy: repo_only
topic: public_site
public_projection: internal
section: docs/landing
---
# Публичный сайт CodeGraph

Этот репозиторий хранит собранный лендинг, публичную HTML-документацию и статические ресурсы.
README проверен по текущему дереву и командам родительского проекта 26 августа 2026 года.

## Где находится источник

- Контент и шаблоны лендинга находятся в родительском репозитории: `scripts/landing_content.py`,
  `docs/landing/templates/` и `docs/landing/templates/sections/`.
- Markdown-источники документации находятся в `docs/getting-started`, `docs/guides`, `docs/api`,
  `docs/integrations`, `docs/reference` и `docs/enterprise` родительского репозитория.
- `docs/landing/docs/` — сгенерированная HTML-проекция. Не редактируйте её вручную.
- Общие стили, JavaScript, изображения, шрифты и favicon лежат в `css/`, `js/` и `assets/`.

Один только checkout этого подрепозитория пригоден для просмотра готового сайта, но не содержит
полного набора исходников и сборочных скриптов.

## Локальный просмотр

Из каталога `docs/landing`:

```powershell
python -m http.server 8000
```

Откройте `http://127.0.0.1:8000/`. Для проверки документации используйте также
`/docs/en/` и `/docs/ru/`.

## Сборка из родительского репозитория

```powershell
# Лендинг и минимизированные assets
python scripts/build_landing.py

# Явные режимы сборщика
python scripts/build_landing.py --sections
python scripts/build_landing.py --assets
python scripts/build_landing.py --all

# Документация без обращения к провайдеру перевода
python scripts/build_docs.py --no-translate --validate-content

# Проверка ссылок в готовой HTML-проекции
python scripts/build_docs.py --validate
```

`build_landing.py` принимает один из перечисленных флагов; отдельного `--help` у него нет.
`build_docs.py --translate` используйте только для осознанной пересборки перевода с доступными
credentials; ключи и токены не должны попадать в репозиторий или generated HTML.

## Что проверять в diff

- публичные маршруты, canonical и hreflang;
- sitemap, robots и структурированные данные;
- согласованность русской и английской документации;
- отсутствие приватных runbook-ссылок, внутренних evidence carrier, секретов и сырых ответов
  провайдеров;
- отсутствие случайных изменений сгенерированных страниц вне заявленного источника;
- визуальный smoke на desktop и mobile для изменённых маршрутов.

Статические числа страниц, URL и FAQ здесь не фиксируются: они быстро расходятся с generated
output. Текущий состав проверяйте по файлам, sitemap и валидаторам.

## Публикация

Сборка и локальная проверка не означают публикацию. Deploy выполняется отдельной авторизованной
операцией после просмотра diff, проверок публичной границы и подтверждения целевого revision.
README не задаёт команду push и не является доказательством успешного deploy.
