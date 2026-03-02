# Вайбкодинг без страховки — технический долг. С CPG-конвейером — скорость + качество

**Канал**: Habr
**Дата публикации**: Март 2026, Неделя 2
**Целевой ICP**: ICP #3 — Техлид / старший разработчик (Алексей)
**Целевые ключевые слова**: вайбкодинг, догфуддинг, CPG, непрерывная верификация, Claude Code, предкоммитные хуки, AI-ассистированная разработка
**Целевая страница**: codegraph.ru/ai-engineering
**Статус**: Черновик

---

## Хук

> Клод написал 47 файлов за сессию. 1 892 строки. Два новых сценария, рефакторинг шести обработчиков, миграция конфига. 38 минут.
>
> Каждый коммит — автоматический CPG-анализ. Каждый промпт — обогащение контекстом из графа. Каждый PR — blast radius и risk score.
>
> Не потому что мы не доверяем ИИ. А потому что мы не доверяем **никакому** генератору кода без автоматической верификации. Включая себя.

Термин «вайбкодинг» придумал Андрей Карпати: пишешь промпт — получаешь код — принимаешь результат, не всегда вчитываясь. Модель — генератор. Разработчик — ревьюер. Если повезёт.

Проблема не в модели. Проблема в отсутствии конвейера верификации. Линтеры ловят синтаксис. Тесты ловят поведение. Но никто не ловит *структурную деградацию* — рост цикломатической сложности, расширение радиуса поражения, дрейф числовых утверждений в документации.

Мы в CodeGraph решили: если вайбкодинг неизбежен — его надо обвязать графом свойств кода. Не запретить ИИ — а сделать так, чтобы каждый артефакт, порождённый моделью, проходил через CPG-конвейер автоматически, без ручного запуска, в реальном времени.

Эта статья — подробное руководство, как мы это устроили. Пять хуков Claude Code, три git-хука, CI/CD на GitHub Actions, валидатор числовых утверждений и трекинг тренда качества по коммитам. Всё на реальной кодовой базе CodeGraph (42 тыс. методов, 2 170 файлов, 11 языков).

---

## 1. Вайбкодинг — что это и почему пугает техлидов

### Масштаб

По данным GitHub (2025): Copilot генерирует 46% нового кода в репозиториях, где он включён. По нашим собственным замерам: в сессиях Claude Code на кодовой базе CodeGraph модель пишет 50–70% строк. Оставшиеся 30–50% — промпты, ревью, правки.

Это уже не эксперимент. Это основной режим работы.

### Проблема

Ревью не масштабируется. Один техлид физически не может проверять 1 892 строки за 38 минут — а именно столько генерирует Claude Code за типичную сессию рефакторинга.

Три типичных провала вайбкодинга без контроля:

1. **Рост сложности**: модель дублирует логику вместо вынесения в общий метод. CC растёт, fan-out расширяется — и никто не замечает до следующего релиза.
2. **Каскадные поломки**: изменение в одном обработчике ломает 12 вызывающих. Модель не видит граф вызовов — видит только файл.
3. **Документационный дрейф**: модель добавляет сценарий 22 — а в документации по-прежнему «21 сценарий». В [статье 8](habr-08-meta-audit.md) мы нашли 14 таких расхождений за один вечер.

### Тезис

> Вайбкодинг без контроля = технический долг.
> Вайбкодинг с CPG-конвейером = скорость + качество.

Дальше — конкретная архитектура.

---

## 2. Конвейер — пять хуков, один граф

### Архитектура

Claude Code поддерживает пять типов хуков — точек вмешательства в жизненный цикл сессии. Каждый хук получает JSON на stdin, возвращает JSON на stdout. Если в ответе есть `additionalContext` — контекст встраивается в диалог.

Мы используем все пять:

```
Сессия разработчика
    │
    ▼
[SessionStart] ──► CPG-контекст: 42K методов, 2170 файлов, avg CC 4.2
    │
    ▼
[UserPromptSubmit] ──► «рефакторинг CommitAnalyzer»
                       + CPG: определён в commit_analyzer.py:34, CC=8, fan-out=5
    │
    ▼
[PreToolUse:Edit] ──► ⚠ analyze_commit: CC=15, 3 TODO
    │
    ▼
Claude Code пишет код
    │
    ▼
[PostToolUse:Bash(git commit)] ──►
    Фаза 1: проверка свежести CPG (2с)
    Фаза 2: gocpg update инкрементально (3с)
    Фаза 3: анализ качества + радиус поражения (8с)
    ──► отчёт встраивается в диалог
    │
    ▼
[Stop] ──► пост-анализ: упомянутые файлы, спайки CC
    │
    ▼
[git push → PR] ──►
    gocpg-analysis.yml: SARIF-аннотации, метрики в комментарии PR
```

### Конфигурация

Все хуки описаны в `.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [{
      "hooks": [{
        "type": "command",
        "command": "python .claude/hooks/session_context.py",
        "timeout": 10000
      }]
    }],
    "UserPromptSubmit": [{
      "hooks": [{
        "type": "command",
        "command": "python .claude/hooks/enrich_prompt.py",
        "timeout": 15000
      }]
    }],
    "PreToolUse": [{
      "hooks": [{
        "type": "command",
        "command": "python .claude/hooks/pre_tool_use.py",
        "timeout": 8000
      }]
    }],
    "PostToolUse": [{
      "matcher": "Bash",
      "hooks": [{
        "type": "command",
        "command": "python .claude/hooks/commit_analysis.py",
        "timeout": 60000
      }]
    }],
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "python .claude/hooks/post_analysis.py",
        "timeout": 10000
      }]
    }]
  }
}
```

Каждый хук — независимый Python-скрипт. Общая инфраструктура в `_utils.py`: чтение stdin, вывод JSON, разрешение активного проекта из `config.yaml`, выполнение SQL через `gocpg query`.

Ключевой принцип: **хуки не блокируют генерацию**. SessionStart, UserPromptSubmit и PreToolUse добавляют контекст *до* того, как модель начнёт писать. PostToolUse и Stop анализируют *после*. Модель работает в полную силу — а конвейер страхует результат.

---

## 3. Глубокое погружение: анализ коммита

Главный хук — `commit_analysis.py`. Запускается после каждого `git commit` внутри Claude Code. Бюджет: 58 секунд (60с таймаут минус 2с запас).

### Четыре фазы

| Фаза | Бюджет | Что делает |
|------|--------|------------|
| 1. Свежесть CPG | 2с | Сравнивает `cpg_git_state.commit_hash` с `git rev-parse HEAD` |
| 2. Обновление | 40с | Если CPG устарел — `gocpg update` инкрементально |
| 3. Качество | 8с | CC, fan-out, TODO/FIXME, debug-код, deprecated |
| 4. Радиус поражения | 8с | Кто вызывает изменённые методы? |

### Как это работает

```python
# Упрощённый поток (реальный код в src/dogfooding/commit_analyzer.py)

# Фаза 1: изменённые файлы
files = git_diff("HEAD~1", "HEAD")  # ["src/dogfooding/commit_analyzer.py", ...]

# Фаза 2: методы в этих файлах (из CPG)
methods = duckdb.execute("""
    SELECT full_name, cyclomatic_complexity, fan_in, fan_out,
           has_todo_fixme, has_debug_code, has_deprecated
    FROM nodes_method
    WHERE filename LIKE '%commit_analyzer.py%'
    ORDER BY cyclomatic_complexity DESC
""")

# Фаза 3: качество
high_cc = [m for m in methods if m.cc > 10]
blast    = duckdb.execute("""
    SELECT callee_full_name, containing_method_full_name
    FROM call_containment
    WHERE callee_full_name IN (...)
""")
```

### Реальный отчёт

Вот что Claude Code видит после коммита:

```
## Commit Analysis Report
**Summary:** 4 files, 12 methods, 1 high-CC, 8 affected callers
**CPG status:** fresh

**Impact of changes:**
- `CommitAnalyzer.analyze_commit`: CC 8→12 (+4)
- `format_report_markdown`: FanOut 5→3 (-2)

**High complexity methods:**
- `analyze_blast_radius` (CC: 14)

**Blast radius:** 8 callers affected
- `analyze_commit` called by: `_run_analyze`, `_run_report`, `commit_analysis.run_with_duckdb`

*Analysis completed in 1340ms*
```

Модель *видит* этот отчёт и учитывает его в следующем ответе. Если CC вырос — модель знает. Если blast radius широкий — модель предупредит. Без дополнительных промптов от человека.

### Дельты: до и после

Особенно полезна таблица дельт: метрики *до* коммита vs *после*. Реализация в `_compute_deltas()`: перед обновлением CPG сохраняем текущие метрики изменённых методов, после обновления — сравниваем.

```
CC 8→12 (+4)     — усложнение, обратить внимание
FanOut 5→3 (-2)  — упрощение, хорошо
```

---

## 4. Обогащение промпта — контекст ДО генерации

Пост-анализ ловит проблемы *после*. Обогащение промпта предотвращает их *до*.

### Как работает enrich_prompt.py

1. Пользователь пишет: «рефакторинг CommitAnalyzer»
2. Хук извлекает сущности из текста: `CommitAnalyzer` (CamelCase), `commit_analyzer` (если есть snake_case)
3. Для каждой сущности — SQL-запрос к CPG:

```sql
SELECT full_name, filename, cyclomatic_complexity, fan_in, fan_out
FROM nodes_method
WHERE full_name LIKE '%CommitAnalyzer%'
ORDER BY cyclomatic_complexity DESC
LIMIT 5
```

4. Результат встраивается в контекст:

```
CPG Context for CommitAnalyzer:
- src/dogfooding/commit_analyzer.py:34 — CommitAnalyzer.__init__ (CC: 1)
- src/dogfooding/commit_analyzer.py:55 — CommitAnalyzer.get_changed_files (CC: 3)
- src/dogfooding/commit_analyzer.py:324 — CommitAnalyzer.analyze_commit (CC: 8)
```

### Без контекста vs с контекстом

**Без CPG** (наивный вайбкодинг):
- Промпт: «рефакторинг CommitAnalyzer»
- Модель: ищет файл, читает, предлагает изменения. Не знает: кто вызывает `analyze_commit`? какова сложность? есть ли TODO?

**С CPG**:
- Промпт: то же самое
- Контекст: CC=8, fan_out=5, 3 TODO/FIXME, 8 прямых вызывающих
- Модель: *знает* структуру до начала генерации. Предлагает изменения с учётом blast radius.

Бюджет: 10с (3с на сущность, максимум 3 сущности). Реальное время: 1–3с.

---

## 5. Git-хуки — фоновое обновление CPG

### Проблема

CPG устаревает после каждого коммита. Если при коммите #N парсер нашёл 42 000 методов, а коммит #N+1 добавил новый файл — CPG больше не актуален. Анализ на устаревшем CPG даёт неточные результаты.

### Решение: gocpg hooks install

```bash
$ gocpg hooks install --repo=. --db=data/projects/codegraph.duckdb
✓ Installed post-commit hook
✓ Installed post-merge hook
✓ Installed post-checkout hook
```

Три git-хука, одна задача: после каждого коммита/merge/checkout — запуск `gocpg update` в фоновом режиме. Разработчик не ждёт.

### Тайминги

| Операция | Время |
|----------|-------|
| Полный парсинг (42K методов) | ~85с |
| Инкрементальное обновление (1–5 файлов) | 2–5с |
| Инкрементальное обновление (10–20 файлов) | 5–12с |

Инкрементальный режим определяется автоматически: если в DuckDB есть таблица `cpg_git_state` с записями — GoCPG парсит только изменённые файлы (`git diff --name-only`). Если БД не существует — полный парсинг.

### Асинхронный режим

Конфигурация в `config.yaml`:

```yaml
gocpg:
  hooks:
    hook_types: "post-commit,post-merge,post-checkout"
    async_hooks: true
```

`async_hooks: true` — хук запускает `gocpg update` в фоне (`&` / `nohup`). Разработчик продолжает работу. К моменту следующего коммита CPG, как правило, уже обновлён.

---

## 6. CI/CD — верификация PR

### gocpg-analysis.yml

Всё, что работает локально, воспроизводится в CI. Воркфлоу `.github/workflows/gocpg-analysis.yml` запускается на каждый PR:

```yaml
# Упрощённая структура
jobs:
  analyze:
    steps:
      - name: Build GoCPG
        run: CGO_ENABLED=1 go build -o gocpg ./cmd/gocpg

      - name: Restore cached CPG
        uses: actions/cache@v4
        with:
          key: cpg-${{ github.base_ref }}-${{ hashFiles('src/**') }}

      - name: Incremental CPG update
        run: ./gocpg ci-update --base-ref origin/${{ github.base_ref }}

      - name: Post metrics as PR comment
        # files_changed, nodes_added, duration_ms, cache_hit

  security-review:
    needs: analyze
    steps:
      - name: Security analysis
        run: python -m src.cli exec --db $DB --base-ref ...
              --sarif-file out.sarif --comment-file comment.md

      - name: Upload SARIF
        uses: github/codeql-action/upload-sarif@v3
```

### Кеширование

Ключ кеша: `cpg-{base_ref}-{hash_исходников}`. При повторных пушах в тот же PR — CPG обновляется инкрементально, экономя 80–90% времени парсинга.

### Что видит ревьюер PR

1. **Комментарий с метриками**: файлов изменено, нодов добавлено, время обновления, попадание в кеш
2. **SARIF-аннотации**: уязвимости безопасности прямо в диффе, кликабельные маркеры рядом с проблемными строками
3. **Blast radius**: какие модули затронуты изменениями

Ревьюер не анализирует 47 файлов вручную. Он смотрит на CPG-метрики и SARIF-маркеры.

---

## 7. Недостающий кусок — валидация числовых утверждений

### Обещание из статьи 8

В [статье 8](habr-08-meta-audit.md) мы нашли 14 расхождений между документацией и кодом. «120+ типов CWE» — а в базе 58. «90+ обработчиков» — а в коде 97. Мы починили числа вручную и пообещали: «в следующей статье — автоматический предкоммитный хук».

Обещание выполнено.

### claims_validator.py

Ядро решения — `src/dogfooding/claims_validator.py`. Принцип: маркдаун-файлы содержат утверждения вида «42 обработчика» или «95+ правил». Валидатор извлекает число и ключевое слово, маппит ключевое слово в SQL-запрос к CPG и сравнивает.

```python
# Извлечение: regex находит "число [+] ключевое_слово"
# "95 обработчиков" → claimed=95, keyword="обработчиков", tolerance=False
# "90+ scenarios"   → claimed=90, keyword="scenarios",    tolerance=True

# Маппинг keyword → SQL (из config.yaml, не хардкод):
rules:
  - keywords: ["handlers", "обработчиков", "обработчики"]
    sql: "SELECT COUNT(DISTINCT full_name) FROM nodes_method
          WHERE full_name LIKE '%Handler%handle%'"
  - keywords: ["scenarios", "сценариев", "сценарии"]
    sql: "SELECT COUNT(DISTINCT ...) FROM nodes_method
          WHERE full_name LIKE '%scenario%' AND full_name LIKE '%handle%'"
```

Двуязычные ключевые слова (русские + английские). Толерантность: «90+» считается корректным, если фактическое значение >= 90.

### Демонстрация

```bash
$ python -m src.cli dogfood validate-claims --path docs/landing/blog/
MISMATCH: habr-01-cpg-vs-sast.md:42
  Claimed: 95 обработчиков
  Actual:  97
  SQL:     SELECT COUNT(DISTINCT full_name) FROM nodes_method WHERE...

OK: habr-08-meta-audit.md
  All 6 numeric claim(s) verified

---
Files: 9 | Claims: 23 | OK: 22 | Mismatches: 1 | Time: 847ms
```

За 847 миллисекунд — проверка всех числовых утверждений в 9 статьях серии. Один расхождённый факт найден автоматически.

### Конфигурация правил

Все маппинги keyword → SQL хранятся в `config.yaml`:

```yaml
dogfooding:
  claims_validation:
    enabled: true
    timeout: 5.0
    rules:
      - keywords: ["handlers", "обработчиков", "обработчики", "обработчика"]
        sql: "SELECT COUNT(DISTINCT full_name) FROM nodes_method ..."
        description: "Scenario handler methods"
      - keywords: ["scenarios", "сценариев", "сценарии", "сценария"]
        sql: "SELECT COUNT(DISTINCT ...) FROM nodes_method ..."
        description: "Workflow scenarios"
      # ... 8 правил для 8 типов утверждений
```

Добавить новое правило = одна запись в YAML. Ноль строк Python.

---

## 8. Сквозная демонстрация

Реальная сессия разработки CodeGraph. Задача: добавить валидатор числовых утверждений (тот самый из раздела 7).

### Шаг 1: Старт сессии

```
[SessionStart] ──► session_context.py
  Проект: codegraph
  Язык: python
  Домен: python_generic
  CPG: 42 156 методов, 2 170 файлов
```

Модель знает масштаб кодовой базы *до первого промпта*.

### Шаг 2: Промпт

```
Пользователь: «Создай claims_validator.py в src/dogfooding/
  по образцу commit_analyzer.py»

[UserPromptSubmit] ──► enrich_prompt.py
  CPG Context:
  - commit_analyzer.py:34 — CommitAnalyzer (CC: 8)
  - commit_analyzer.py:324 — analyze_commit (CC: 8, fan_out: 5)
  - commit_analyzer.py:374 — format_report_markdown (CC: 4)
```

Модель видит паттерн: классы CommitAnalyzer и CommitReport, DuckDB read-only, timeout-бюджеты. Копирует структуру — не изобретает заново.

### Шаг 3: Генерация кода

```
[PreToolUse:Write] ──► pre_tool_use.py
  Новый файл: src/dogfooding/claims_validator.py
  (нет предупреждений — файл создаётся, а не редактируется)
```

Claude Code создаёт `claims_validator.py` (320 строк), `test_claims_validator.py` (29 тестов), обновляет `config.yaml` и `dogfood_commands.py`.

### Шаг 4: Коммит

```
$ git commit -m "feat: add claims validator for documentation verification"

[PostToolUse:Bash(git commit)] ──► commit_analysis.py
  Фаза 1: CPG свежесть ✓ (совпадает с HEAD)
  Фаза 2: gocpg update — 4 новых файла, 2.1с
  Фаза 3: анализ — 3 файла, 8 методов, 0 high-CC
  Фаза 4: blast radius — 2 вызывающих затронуты

  ## Commit Analysis Report
  **Summary:** 4 files, 8 methods, 0 high-CC, 2 affected callers
  **CPG status:** fresh
  *Analysis completed in 2340ms*
```

Чисто. Ноль high-CC. Два вызывающих — `_run_validate_claims` и тесты.

### Шаг 5: PR и CI

```
$ git push → PR #142

[gocpg-analysis.yml]:
  ✓ CPG обновлён инкрементально (cache hit)
  ✓ Метрики: 4 файла, 8 методов, 0 уязвимостей
  ✓ SARIF: пусто (нет проблем безопасности)
  ✓ Комментарий к PR с дельтой метрик
```

Пять шагов. Ноль ручного анализа. Каждый артефакт проверен конвейером.

---

## 9. Тренд качества

Разовый анализ коммита полезен. Но техлиду нужна *динамика*: растёт ли сложность? Появляется ли мёртвый код? Сколько TODO накопилось за спринт?

### cpg_quality_history

Таблица в том же DuckDB, что и CPG:

```sql
CREATE TABLE IF NOT EXISTS cpg_quality_history (
    commit_hash  VARCHAR,
    timestamp    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    branch       VARCHAR,
    total_methods INT,
    total_files   INT,
    avg_cc       FLOAT,
    max_cc       INT,
    high_cc_count INT,
    dead_methods  INT,
    todo_count   INT,
    debug_count  INT
)
```

После каждого успешного анализа коммита `CommitAnalyzer` автоматически вызывает `record_snapshot()` — сбор метрик по всему CPG и INSERT в историю. Ноль дополнительных команд.

### Тренд

```bash
$ python -m src.cli dogfood trend --commits 5
Commit       Date         Methods  Avg CC   Dead  Hi-CC   TODO
b6f06d60     2026-02-28     42156     4.2      0     23     47
851b5a1a     2026-02-27     42149     4.2      0     22     45
b7945f0d     2026-02-26     42134     4.3      0     24     46
a44e9c3b     2026-02-25     42128     4.3      0     24     44
f19d8e72     2026-02-24     42110     4.3      0     25     44
--------------------------------------------------------------
Trend: methods +0.1%, CC stable, dead code = 0
```

Техлид видит: за неделю прибавилось 46 методов. Средняя CC стабильна. Мёртвого кода нет (все FP-фильтры из [аудита](habr-08-meta-audit.md) работают). High-CC уменьшилось с 25 до 23 — рефакторинг двух тяжёлых методов.

Это *объективная* метрика здоровья проекта. Не ощущение — а вычислимый факт из графа.

---

## 10. Пять уроков

За три месяца использования конвейера мы сформулировали пять принципов:

### 1. Скорость хука < бюджета генерации

Если хук работает 30 секунд, а генерация — 10 секунд, разработчик отключит хук. Наши бюджеты: SessionStart 8с, UserPromptSubmit 10с, PreToolUse 6с, PostToolUse 58с (из них 40с — обновление CPG, которое всё равно пришлось бы делать). Реальное время: обычно 1–5с.

### 2. Контекст ДО генерации > ревью ПОСЛЕ

Обогащение промпта предотвращает ошибки. Пост-анализ находит. Предотвращение дешевле. `enrich_prompt.py` (10с) экономит целый цикл генерации-ревью-переделки (минуты).

### 3. Граф > линтер

Линтер видит файл. Граф видит систему. Blast radius, fan-in/fan-out, call containment — эти метрики невозможно получить из одного файла. CPG строит граф свойств *всей* кодовой базы — и хуки используют его за миллисекунды.

### 4. Один `setup` — и забыл

```bash
$ python -m src.cli dogfood setup --repo . --db data/projects/codegraph.duckdb
```

Одна команда устанавливает: git-хуки (3 шт.), Claude Code хуки (5 шт.), проверяет CPG, загружает правила валидации. Дальше конвейер работает автоматически. Если разработчик не знает о хуках — он всё равно защищён.

### 5. Асинхронность — ключ к adoption

Синхронные хуки блокируют работу. Наш конвейер: git-хуки работают в фоне, CPG обновляется асинхронно, PostToolUse — единственный синхронный хук (и то — 58с бюджет хватает на инкрементальное обновление + анализ). Разработчик не ждёт.

---

## 11. Как воспроизвести

Три шага для любого проекта:

### Шаг 1: Парсинг кодовой базы

```bash
# Установка GoCPG (Go 1.26+, CGO для tree-sitter)
cd gocpg && CGO_ENABLED=1 go build -o gocpg.exe ./cmd/gocpg

# Парсинг
./gocpg parse --input=/path/to/your/code --output=project.duckdb --lang=python
```

GoCPG поддерживает 11 языков: C, C++, Go, Python, JavaScript, TypeScript, Java, Kotlin, C#, PHP, 1C:Enterprise.

### Шаг 2: Установка конвейера

```bash
# Одна команда
python -m src.cli dogfood setup --repo /path/to/repo --db project.duckdb

# Что произойдёт:
# ✓ Git-хуки: post-commit, post-merge, post-checkout
# ✓ Claude Code хуки: 5/5 настроены
# ✓ CPG: свежесть проверена
# ✓ Валидация утверждений: правила загружены
```

### Шаг 3: Работайте как обычно

```bash
# Вайбкодинг с автоматической верификацией
claude  # Запуск Claude Code

# Проверка тренда
python -m src.cli dogfood trend --commits 10

# Валидация числовых утверждений
python -m src.cli dogfood validate-claims --path docs/
```

Всё. Конвейер включается автоматически. Каждый коммит анализируется. Каждый промпт обогащается. Каждый PR верифицируется.

---

## Заключение

Девять статей серии — путь от идеи до конвейера:

1. **CPG**: что такое граф свойств кода ([статья 1](habr-01-cpg-vs-sast.md))
2. **Онбординг**: как разобраться в 42К методов ([статья 2](habr-02-onboarding.md))
3. **Догфуддинг парсера**: от 35 000 FP до нуля ([статья 3](habr-03-dogfooding.md))
4. **Собственный парсер**: зачем мы ушли от Joern ([статья 4](habr-04-why-own-parser.md))
5. **Анализ потоков данных**: от grep до taint analysis ([статья 5](habr-05-taint-analysis.md))
6. **DuckDB**: почему колоночная СУБД лучше графовой ([статья 6](habr-06-duckdb-for-cpg.md))
7. **Handler-Formatter**: минус 90% LLM-вызовов ([статья 7](habr-07-handler-formatter.md))
8. **Мета-аудит**: 14 расхождений, 36 багов, рекурсия ([статья 8](habr-08-meta-audit.md))
9. **Непрерывная верификация**: вайбкодинг + CPG = конвейер *(эта статья)*

Три уровня эволюции догфуддинга:

- **Статья 3**: ручной прогон парсера на своём коде → 9 ошибок
- **Статья 8**: одноразовый аудит документации → 14 расхождений + 36 багов
- **Статья 9**: непрерывный конвейер → каждый коммит, каждый промпт, каждый PR

Мы не остановили вайбкодинг. Мы обвязали его графом. Теперь модель генерирует — а CPG-конвейер верифицирует. Автоматически, в реальном времени, без ручного запуска.

> Вычислимый факт не соврёт. `COUNT(*)` не округлит. `cyclomatic_complexity > 10` не пропустит.
> Граф свойств кода — единственный честный ревьюер при вайбкодинге.

---

## Что дальше

Эта статья — девятая в серии:
- [Статья 1: почему CPG лучше SAST](habr-01-cpg-vs-sast.md) — что такое граф свойств кода и зачем он нужен
- [Статья 2: онбординг в кодовую базу](habr-02-onboarding.md) — как CodeGraph помогает разобраться в 42 тыс. методов
- [Статья 3: догфуддинг](habr-03-dogfooding.md) — от 35 тысяч ложных срабатываний до нуля
- [Статья 4: зачем свой парсер](habr-04-why-own-parser.md) — как Joern нас не устроил
- [Статья 5: эволюция анализа уязвимостей](habr-05-taint-analysis.md) — от grep до анализа потоков данных
- [Статья 6: DuckDB вместо Neo4j](habr-06-duckdb-for-cpg.md) — почему колоночная СУБД лучше графовой для CPG
- [Статья 7: архитектура Handler-Formatter](habr-07-handler-formatter.md) — как снизить стоимость LLM-вызовов на 90%
- [Статья 8: мета-аудит документации](habr-08-meta-audit.md) — 14 расхождений, 36 багов и рекурсивный догфуддинг

Девять статей: от идеи CPG до конвейера непрерывной верификации. Потому что вайбкодинг — реальность. И единственный вопрос — контролируемая она или нет.

---

**Хотите встроить CPG-конвейер в свой процесс AI-ассистированной разработки?**

[AI Engineering](https://codegraph.ru/ai-engineering.html) | [Технический обзор](https://codegraph.ru/whitepaper.html) | [GitHub](https://github.com/mkhlsavin/pg_copilot)

---

*CodeGraph — ИИ-инструмент построения и анализа графа свойств кода. 11 языков, 33 аналитических прохода, 190 правил структурного поиска. Подробнее: [codegraph.ru](https://codegraph.ru)*
