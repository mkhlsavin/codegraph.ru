# DuckDB вместо Neo4j: почему мы храним граф кода в колоночной СУБД

**Канал**: Habr
**Дата публикации**: Май 2026, Неделя 1
**Целевой ICP**: ICP #3 — Архитектор / Tech Lead, ICP #1 — DevSecOps-инженер
**Целевые ключевые слова**: DuckDB, граф свойств кода, SQL/PGQ, колоночная СУБД, статический анализ, графовые запросы
**Целевая страница**: codegraph.ru/cpg
**Статус**: Черновик

---

## Хук

> Скрипт `compatibility.py` выполнял DROP TABLE, ALTER TABLE и пересоздавал 733 тысячи строк при каждом парсинге. Нагрузка на диск — 100%. Файловые блокировки не позволяли запускать анализ параллельно.

Это был постпроцессор, который «подгонял» схему базы данных после генерации графа. Мы использовали Joern (JVM/Scala) для парсинга и проприетарный бинарный формат flatgraph для хранения. Запросы к графу делались через Joern DSL — своеобразный диалект Scala, для которого не существует ни IDE-поддержки, ни инструментов отладки.

Когда мы написали собственный парсер GoCPG (см. [статью 4](habr-04-why-own-parser.md)), встал вопрос: куда складывать граф? Графовые базы данных — очевидный ответ. Мы выбрали неочевидный: DuckDB — встраиваемую колоночную аналитическую СУБД. И не пожалели.

---

## 1. Почему не графовая СУБД

Граф свойств кода (Code Property Graph, CPG) — это граф. Казалось бы, храни его в Neo4j, JanusGraph или ArangoDB. Но у графовых СУБД есть три свойства, которые плохо сочетаются с нашей задачей.

### Проблема 1: сервер

Neo4j, JanusGraph, Dgraph — это серверные процессы. Их нужно устанавливать, настраивать, запускать и поддерживать. Для корпоративного продукта, который должен работать в изолированном контуре (без доступа к интернету), это дополнительная инфраструктура.

Нам нужна была **встраиваемая** база данных: один файл, без сервера, открывается из Python и Go.

### Проблема 2: аналитические запросы

Большинство запросов к CPG — не «найди соседей вершины» (для этого графовые БД оптимальны), а **аналитические агрегации**:

- Сколько методов в каждом модуле? (`GROUP BY filename`)
- Какие методы имеют цикломатическую сложность > 20? (`WHERE cyclomatic_complexity > 20`)
- Топ-10 методов по количеству входящих вызовов? (`ORDER BY fan_in DESC LIMIT 10`)
- Сколько строк кода в каждом файле? (`SUM(line_number_end - line_number)`)

Это работа для колоночных СУБД, не для графовых.

### Проблема 3: экосистема

SQL знают все. Joern DSL — единицы. Neo4j Cypher — десятки. А нам нужно, чтобы:

- Разработчик мог написать произвольный запрос к CPG
- MCP-сервер мог принимать SQL-запросы от IDE
- TUI мог показывать результаты в таблице
- CI/CD мог выполнять проверки через shell-скрипт

SQL покрывает все четыре сценария без дополнительного слоя абстракции.

---

## 2. Почему DuckDB

DuckDB — встраиваемая колоночная аналитическая СУБД. Аналог SQLite, но не для транзакционных приложений, а для аналитики.

| Свойство | SQLite | DuckDB | Neo4j |
|----------|:---:|:---:|:---:|
| Встраиваемая (без сервера) | да | да | нет |
| Один файл | да | да | каталог |
| Колоночное хранение | нет | да | нет |
| Аналитические запросы | медленно | быстро | медленно |
| Графовые запросы (SQL/PGQ) | нет | да (расширение) | да (Cypher) |
| Работа из Python | да | да | через драйвер |
| Работа из Go | да | да | через драйвер |

Для нас ключевые свойства:

**Встраиваемость.** Один файл `.duckdb` — это весь граф проекта. Его можно копировать, архивировать, передавать по сети. Никакого сервера.

**Колоночное хранение.** CPG PostgreSQL — это 52 тыс. методов, 1.4 млн вызовов, 8.4 млн рёбер потока данных. Колоночный формат позволяет сканировать только нужные столбцы. Запрос `SELECT name, cyclomatic_complexity FROM nodes_method WHERE cyclomatic_complexity > 20` читает только два столбца из двадцати — в строковой БД пришлось бы прочитать все.

**SQL/PGQ.** Расширение DuckPGQ добавляет стандарт ISO SQL/PGQ (Property Graph Queries) — графовые запросы поверх реляционных таблиц. Об этом — в разделе 5.

---

## 3. Схема: 42 таблицы узлов, 25 таблиц рёбер

GoCPG записывает граф напрямую в DuckDB — никакого промежуточного формата. Схема состоит из трёх слоёв.

### Слой 1: узлы

Каждый тип CPG-узла — отдельная таблица со своими столбцами. Не одна гигантская таблица `nodes` с JSON-полем `properties`, а 42 типизированных таблицы:

| Таблица | Назначение | Ключевые столбцы |
|---------|------------|------------------|
| `nodes_method` | Функции и методы | `full_name`, `signature`, `cyclomatic_complexity`, `fan_in`, `fan_out`, `is_test`, `is_entry_point` |
| `nodes_call` | Вызовы функций | `name`, `dispatch_type`, `type_full_name`, `containing_method_id` |
| `nodes_identifier` | Идентификаторы | `name`, `type_full_name` |
| `nodes_literal` | Литералы | `code`, `type_full_name` |
| `nodes_file` | Исходные файлы | `name`, `content`, `ast_hash`, `language` |
| `nodes_type_decl` | Объявления типов | `full_name`, `inherits_from_type_full_name[]` |
| `nodes_comment` | Комментарии | `code`, `comment_type`, `documented_node_id` |
| `nodes_finding` | Результаты анализа | `severity`, `category`, `rule_id`, `confidence` |
| ... | ... | ... |

Почему не одна таблица? Потому что **колоночная СУБД оптимизирует запрос под столбцы конкретной таблицы**. Запрос к `nodes_method` не трогает данные `nodes_literal` — они физически хранятся в разных колонках.

### Слой 2: рёбра

25 таблиц рёбер — по таблице на каждый тип связи:

| Таблица | Связь | Записей (PostgreSQL CPG) |
|---------|-------|:---:|
| `edges_ast` | Родитель → потомок в синтаксическом дереве | 5.8M |
| `edges_cfg` | Управляющий поток (control flow) | 4.2M |
| `edges_reaching_def` | Поток данных (определение → использование) | 8.4M |
| `edges_call` | Вызывающий → вызываемый | 1.7M |
| `edges_cdg` | Управляющие зависимости | 3.5M |
| `edges_dominate` | Доминирование | — |
| `edges_post_dominate` | Постдоминирование | — |
| `edges_pdg` | Граф программных зависимостей | 7.7M |
| `edges_ddg` | Граф зависимостей данных | 1.9M |
| `edges_parameter_link` | Связь фактических и формальных параметров | — |
| `edges_eval_type` | Узел → его тип | 4.2M |
| ... | ... | ... |

Для GoCPG на Go-кодовой базе (215 файлов): **4.1 миллиона рёбер**. Для Python-кодовой базы (1 183 файла): **65.8 миллионов рёбер**. У Joern на той же Python-кодовой базе — 35.9 млн, но с 15.9 млн ложных call-рёбер от `NaiveCallLinker`.

### Слой 3: представления

Два денормализованных представления ускоряют частые запросы:

**`call_containment`** — кто кого вызывает (используется в 24 файлах Python-кода):

```sql
CREATE VIEW call_containment AS
SELECT DISTINCT
    caller.name         AS containing_method_name,
    caller.full_name    AS containing_method_full_name,
    callee.name         AS callee_name,
    callee.full_name    AS callee_full_name,
    caller.filename     AS caller_filename,
    callee.filename     AS callee_filename,
    nc.line_number      AS call_line_number
FROM edges_call ec
JOIN nodes_call nc ON ec.src = nc.id
JOIN nodes_method caller ON nc.containing_method_id = caller.id
JOIN nodes_method callee ON ec.dst = callee.id;
```

Раньше это была **материализованная таблица** — 733 тыс. строк, 4 индекса, пересоздавалась при каждом парсинге. Теперь — ленивое представление (`VIEW`), которое DuckDB вычисляет на лету. Трёхстороннее соединение на колоночных данных настолько быстрое, что материализация не нужна.

---

## 4. Запросы: 11 миксинов вместо ORM

`CPGQueryService` — точка входа для всех запросов к графу. Он собран из 11 миксинов, каждый из которых отвечает за свою область:

```python
class CPGQueryService(
    CPGQueryBase,
    SubsystemQueriesMixin,      # Подсистемы (по шаблонам путей)
    CallGraphQueriesMixin,       # Граф вызовов (BFS, вызывающие/вызываемые)
    SecurityQueriesMixin,        # Анализ уязвимостей (taint, CWE)
    PerformanceQueriesMixin,     # Горячие точки (сложность, fan-in/fan-out)
    QualityQueriesMixin,         # Мёртвый код, метрики качества
    SemanticQueriesMixin,        # Потоки данных, reaching definitions
    StatisticsQueriesMixin,      # Статистика (счётчики, кардинальность)
    CommentQueriesMixin,         # Извлечение документации
    ExternalQueriesMixin,        # Импорты, зависимости
    TypeQueriesMixin,            # Типы, наследование
    PatternQueriesMixin,         # Результаты структурного поиска
):
    pass  # Все методы — из миксинов
```

Каждый миксин — это набор SQL-запросов к DuckDB с параметризацией. Никакого ORM: прямые запросы, полный контроль над планом выполнения.

Пример — получение графа вызовов методом BFS:

```python
class CallGraphQueriesMixin:
    def get_callees(self, method_id: int, depth: int = 2):
        visited = set()
        queue = deque([(method_id, 0)])

        while queue:
            current_id, current_depth = queue.popleft()
            if current_id in visited or current_depth > depth:
                continue
            visited.add(current_id)

            # Один запрос на уровень глубины
            rows = self.conn.execute("""
                SELECT DISTINCT m.id, m.name, m.full_name
                FROM edges_call ec
                JOIN nodes_call nc ON ec.src = nc.id
                JOIN nodes_method m ON ec.dst = m.id
                WHERE nc.containing_method_id = ?
            """, [current_id]).fetchall()

            for row in rows:
                queue.append((row[0], current_depth + 1))
```

Этот Python BFS работает, но для глубоких обходов (depth > 5) он медленный: каждый уровень — отдельный запрос к DuckDB. Для ускорения мы подключаем SQL/PGQ.

---

## 5. SQL/PGQ: графовые запросы поверх реляционных таблиц

DuckPGQ — расширение DuckDB, реализующее стандарт ISO SQL/PGQ. Оно позволяет создать **граф свойств** (Property Graph) поверх существующих таблиц и выполнять графовые запросы в SQL.

### Создание графа

```sql
-- Загрузка расширения (один раз)
INSTALL duckpgq FROM community;
LOAD duckpgq;

-- Создание графа свойств поверх CPG-таблиц
CREATE PROPERTY GRAPH cpg_call_graph
VERTEX TABLES (
    nodes_method
        PROPERTIES (id, name, full_name, filename, line_number)
        LABEL Method
)
EDGE TABLES (
    method_calls
        SOURCE KEY (caller_id) REFERENCES nodes_method (id)
        DESTINATION KEY (callee_id) REFERENCES nodes_method (id)
        LABEL CALLS
);
```

Данные **не копируются** — граф свойств это «вид» поверх реляционных таблиц. Те же столбцы, тот же колоночный формат, но теперь к ним можно обращаться через синтаксис `MATCH`.

### Кратчайший путь

Найти кратчайшую цепочку вызовов от `main` до `SPI_execute`:

```sql
FROM GRAPH_TABLE(cpg_call_graph
    MATCH p = ANY SHORTEST
        (a:Method WHERE a.name = 'main')
        -[c:CALLS]->{1,10}
        (b:Method WHERE b.name = 'SPI_execute')
    COLUMNS (
        a.name AS source,
        b.name AS target,
        path_length(p) AS hops
    )
);
```

Один запрос вместо рекурсивного CTE с `WITH RECURSIVE` или Python BFS.

### PageRank: какие методы самые критичные

```sql
SELECT * FROM pagerank(cpg_call_graph, Method, CALLS)
ORDER BY pagerank_score DESC
LIMIT 20;
```

DuckPGQ выполняет PageRank на внутреннем представлении графа в формате CSR (Compressed Sparse Row) — это на порядки быстрее, чем считать степень вершины через SQL GROUP BY.

### Компоненты связности: изолированные модули

```sql
SELECT * FROM weakly_connected_component(cpg_call_graph, Method, CALLS);
```

Находит группы методов, не связанных вызовами с остальным кодом. Полезно для выявления мёртвых модулей или микросервисных границ.

### Достижимость: есть ли путь от A до B

```sql
SELECT reachability(cpg_call_graph, source_id, sink_id, Method, CALLS);
```

Быстрая проверка без построения полного пути — для предфильтрации в анализе уязвимостей.

---

## 6. Ускорения: конкретные числа

Мы замеряли время выполнения запросов двумя способами: через рекурсивные SQL-запросы (`WITH RECURSIVE`) и через DuckPGQ (`MATCH`, встроенные алгоритмы).

### Ожидаемые ускорения (из бенчмарков)

| Операция | Legacy (SQL CTE) | DuckPGQ | Ускорение |
|----------|:---:|:---:|:---:|
| Поиск заражённых путей (`find_taint_paths`) | 850 мс | 95 мс | **9x** |
| Проверка достижимости (`check_reachability`) | 120 мс | 8 мс | **15x** |
| Обход синтаксического дерева (AST traversal) | 450 мс | 25 мс | **18x** |
| Полный анализ CPG | 2 500 мс | 180 мс | **14x** |
| PageRank (топ-100 методов) | ~5 000 мс (приближение через степень) | ~50 мс (нативный) | **~100x** |

Почему такая разница? Рекурсивный CTE — это итеративное самосоединение таблицы: на каждом шаге DuckDB создаёт промежуточный результат и джойнит его с полной таблицей рёбер. Для 8.4 миллионов рёбер `edges_reaching_def` и глубины 15 это **O(E³)** в худшем случае.

DuckPGQ хранит граф в формате CSR (Compressed Sparse Row — компактное представление разреженной матрицы смежности через два массива: смещения и индексы соседей). Обход по рёбрам — это чтение подряд идущих ячеек массива, без хеш-таблиц и без джойнов. Сложность — **O(V + E)**.

### Где ускорение не нужно

Не все запросы выигрывают от PGQ. Аналитические агрегации — основная нагрузка — работают на чистом SQL и не требуют обхода графа:

```sql
-- Топ-10 сложных методов: колоночный скан, ~5 мс
SELECT name, full_name, cyclomatic_complexity
FROM nodes_method
WHERE cyclomatic_complexity > 20
ORDER BY cyclomatic_complexity DESC
LIMIT 10;

-- Количество методов по файлам: GROUP BY, ~10 мс
SELECT filename, COUNT(*) AS method_count
FROM nodes_method
GROUP BY filename
ORDER BY method_count DESC;
```

Эти запросы DuckDB выполняет за единицы миллисекунд благодаря колоночному хранению и векторизованному выполнению. Графовая СУБД здесь проигрывает — полный скан всех узлов в Neo4j медленнее, чем колоночный скан в DuckDB.

---

## 7. Предвычисленные колонки: как избежать LIKE-сканирования

В `nodes_method` есть 7 булевых флагов и 3 числовые метрики, вычисленные GoCPG при парсинге:

| Колонка | Тип | Что заменяет |
|---------|-----|-------------|
| `is_test` | BOOLEAN | `WHERE full_name LIKE '%test%'` |
| `is_entry_point` | BOOLEAN | `WHERE full_name LIKE '%main%' OR ...` |
| `is_nested` | BOOLEAN | `WHERE ...` (сложная эвристика вложенности) |
| `has_disabled_code` | BOOLEAN | `WHERE code LIKE '%#if 0%'` |
| `has_deprecated` | BOOLEAN | `WHERE code LIKE '%deprecated%'` |
| `has_todo_fixme` | BOOLEAN | `WHERE code LIKE '%TODO%' OR code LIKE '%FIXME%'` |
| `has_debug_code` | BOOLEAN | `WHERE code LIKE '%printf%' OR ...` |
| `cyclomatic_complexity` | INTEGER | Вычисление в Python по AST |
| `fan_in` | INTEGER | `SELECT COUNT(*) FROM edges_call WHERE dst = id` |
| `fan_out` | INTEGER | `SELECT COUNT(*) FROM edges_call WHERE src = id` |

Запрос «найди все тестовые методы» — это `WHERE is_test = TRUE` (колоночный скан булевой колонки, микросекунды) вместо `WHERE full_name LIKE '%test%'` (сканирование и сравнение строк по всем 52 тыс. методов).

---

## 8. История compatibility.py: как мы убрали 733K строк

До GoCPG схема DuckDB была неполной. После парсинга запускался Python-скрипт `compatibility.py`, который:

| Шаг | Что делал | Проблема |
|-----|-----------|----------|
| 1 | `DROP TABLE IF EXISTS call_containment` | Блокировка файла |
| 2 | `CREATE TABLE call_containment AS SELECT ...` (733K строк) | 100% нагрузки на диск |
| 3 | Создавал 4 индекса на новой таблице | Ещё больше записей |
| 4 | `ALTER TABLE nodes_method ADD COLUMN embedding FLOAT[]` | Модификация схемы на лету |
| 5 | `ALTER TABLE nodes_method ADD COLUMN ast_hash VARCHAR` | Модификация схемы на лету |
| 6 | `UPDATE nodes_method SET ast_hash = ...` (52K строк) | Обновление всех записей |

Каждый запуск парсинга — это DROP + CREATE + INSERT 733K строк + 4 индекса + ALTER + UPDATE. На CI/CD это занимало 15–20 секунд и создавало файловые блокировки: если кто-то запускал анализ во время парсинга — ошибка.

Миграция в GoCPG устранила все шесть шагов:

1. **`call_containment`** стал ленивым `VIEW` (ноль записей, вычисляется на лету)
2. **Колонки `embedding` и `ast_hash`** добавлены в DDL-схему GoCPG — они создаются при парсинге, пустые (`NULL`), заполняются позже
3. **`ast_hash`** пропагируется в отдельном проходе конвейера GoCPG (Containment pass)
4. **Python-скрипт `compatibility.py`** удалён целиком

Результат: парсинг стал атомарным — после `gocpg parse` база данных полностью готова к запросам. Никаких постпроцессоров.

---

## 9. Сравнение с альтернативами

| Критерий | DuckDB + PGQ | Neo4j | Joern flatgraph | SQLite |
|----------|:---:|:---:|:---:|:---:|
| Установка | `pip install duckdb` | Сервер + конфигурация | Scala + JVM | `pip install sqlite3` |
| Один файл | да | нет (каталог) | да (бинарный) | да |
| SQL-запросы | да | Cypher | Joern DSL (Scala) | да |
| Графовые алгоритмы | PageRank, WCC, SCC, shortest path | встроенные | через JVM API | нет |
| Колоночное хранение | да | нет | нет | нет |
| Аналитика (GROUP BY, агрегации) | быстро | медленно | нет | медленно |
| Обход графа | SQL/PGQ + CSR | нативный (быстро) | нативный (быстро) | CTE (медленно) |
| Запись из Go | да (нативный драйвер) | через HTTP | через flatgraph API | да |
| Инкрементальные обновления | да (DML) | да (Cypher) | нет | да (DML) |
| Размер CPG (1183 файла Python) | ~800 МБ | ~2 ГБ (оценка) | ~1.2 ГБ | — |

**Где Neo4j лучше**: обход графа на глубину 20+. Нативное хранение рёбер в узлах делает переход по ребру O(1). В DuckDB, даже с PGQ, доступ через CSR-массив.

**Где DuckDB лучше**: всё остальное. Установка, аналитика, SQL, встраиваемость, размер.

---

## 10. MCP и произвольные SQL-запросы

Одно из следствий хранения в DuckDB: пользователи могут писать **произвольные SQL-запросы** к графу, не изучая проприетарные DSL.

MCP-сервер CodeGraph предоставляет инструмент `codegraph_query`, который принимает SQL и возвращает результат:

```json
{
  "tool": "codegraph_query",
  "arguments": {
    "sql": "SELECT name, cyclomatic_complexity FROM nodes_method WHERE cyclomatic_complexity > 30 ORDER BY cyclomatic_complexity DESC LIMIT 5"
  }
}
```

Более того, пользователи могут определять собственные SQL-инструменты в файле `.codegraph/tools.yaml`:

```yaml
tools:
  find_complex_methods:
    description: "Найти методы со сложностью выше порога"
    sql: |
      SELECT name, full_name, cyclomatic_complexity, filename
      FROM nodes_method
      WHERE cyclomatic_complexity > {{threshold}}
      ORDER BY cyclomatic_complexity DESC
      LIMIT {{limit}}
    parameters:
      threshold: { type: integer, default: 20 }
      limit: { type: integer, default: 10 }
```

Каждый YAML-инструмент автоматически становится доступен через MCP — IDE (Cursor, Zed, VS Code) видит его как нативный инструмент.

Попробуйте сделать это с Neo4j Cypher или Joern DSL.

> **SQL — это AST-first в действии.** Когда MCP-сервер отдаёт языковой модели результат SQL-запроса, LLM получает **структурированные факты** из графа, а не сырой код для угадывания. Модель не «понимает» код — она читает предвычисленные метрики, графы вызовов, пути заражения. Это принципиальное отличие от подходов, где LLM анализирует исходный код напрямую: вместо «прочитай 6 000 строк и найди проблему» — «вот 5 конкретных путей данных, оцени риск каждого». Структурный анализ для обнаружения, LLM для объяснения.

---

## 11. Планы: свой форк DuckPGQ с нативными графовыми алгоритмами

DuckPGQ сегодня поддерживает PageRank, компоненты слабой связности (WCC), локальный коэффициент кластеризации и кратчайший путь. Этого достаточно для базового анализа, но нам не хватает двух алгоритмов — и мы реализуем их сами в C++ для последующего PR в upstream.

### Strongly Connected Components (SCC) — алгоритм Тарьяна

SCC — компоненты **сильной** связности — находит группы методов, вызывающих друг друга циклически. В коде это циклические зависимости: `A → B → C → A`. WCC (слабая связность) видит, что A, B и C связаны, но не видит, что связь **циклическая**.

Для анализа архитектуры это критически важно: циклические зависимости между модулями — один из главных индикаторов архитектурного долга. В нашем самоанализе (см. [статью 3](habr-03-dogfooding.md)) SCC нашёл 4 таких цикла.

Реализация — алгоритм Тарьяна за O(V+E) на CSR-представлении графа:

```sql
-- Предлагаемый синтаксис (после PR)
SELECT * FROM strongly_connected_component(
    cpg_call_graph, Method, CALLS
);
-- Возвращает: rowid, component_id, component_size
```

Сейчас у нас есть fallback-реализация на Python (`PGQComponentAnalyzer`), но она работает через вершинные запросы — на графе с 52 тыс. методов это секунды. Нативный C++ на CSR — миллисекунды.

### Betweenness Centrality — алгоритм Брандеса

Betweenness centrality показывает, какие методы являются **мостами** между частями кода: через них проходит наибольшее количество кратчайших путей. Это bottleneck-методы — если они сломаются, пострадают все, кто от них зависит.

PageRank отвечает на вопрос «какие методы самые вызываемые», а Betweenness — на вопрос «какие методы самые незаменимые». Метод с низким PageRank, но высоким Betweenness — это тихий bottleneck: его вызывают немногие, но если его убрать, граф распадётся.

Реализация — алгоритм Брандеса за O(V × E) с опциональным sampling для больших графов:

```sql
-- Предлагаемый синтаксис (после PR)
SELECT * FROM betweenness_centrality(
    cpg_call_graph, Method, CALLS,
    sample_size := 100  -- для графов > 50K вершин
);
-- Возвращает: rowid, betweenness_score (0.0–1.0)
```

### PGQDataFlowTracer: taint analysis на PGQ

Помимо PR в upstream, мы переводим анализ потоков данных (см. [статью 5](habr-05-taint-analysis.md)) с рекурсивных CTE на SQL/PGQ MATCH-запросы. Текущий `DataFlowTracer` использует `WITH RECURSIVE` по таблице `edges_reaching_def` (8.2 млн рёбер). Новый `PGQDataFlowTracer` создаёт граф свойств для потоков данных и использует MATCH с переменной длиной пути:

```sql
FROM GRAPH_TABLE(cpg_data_flow
    MATCH p = ANY SHORTEST
        (source:Identifier WHERE source.name = 'user_input')
        -[r:REACHES]->{1,15}
        (sink:Identifier)
    WHERE sink.id IN (
        SELECT id FROM nodes_call WHERE name = 'SPI_execute'
    )
    COLUMNS (
        path_length(p) AS depth,
        vertices(p) AS path_vertices
    )
);
```

Ожидаемое ускорение — 5–10x на поиске заражённых путей. Для проверки достижимости (есть ли путь вообще, без построения трассы) — 15x.

### Статус и таймлайн

| Компонент | Статус | Ожидание |
|-----------|--------|----------|
| SCC (Tarjan, C++) | Реализация | PR в DuckPGQ |
| Betweenness (Brandes, C++) | Реализация | PR в DuckPGQ |
| PGQDataFlowTracer (Python) | Проектирование | Интеграция в CodeGraph |
| Интеграция в CPGQueryService | Проектирование | Замена legacy Python BFS |
| AST и Full CPG графы | Проектирование | Новые GraphType |

После интеграции **все** обходы графа в CodeGraph — поиск путей, компоненты связности, центральность, taint analysis — будут выполняться на нативном C++ внутри DuckDB, а не в Python.

---

## Что дальше

Эта статья — шестая в серии:
- [Статья 1: почему CPG лучше SAST](habr-01-cpg-vs-sast.md)
- [Статья 2: онбординг в кодовую базу](habr-02-onboarding.md)
- [Статья 3: догфуддинг](habr-03-dogfooding.md)
- [Статья 4: зачем свой парсер](habr-04-why-own-parser.md)
- [Статья 5: эволюция анализа уязвимостей](habr-05-taint-analysis.md)

В следующей статье — **как снизить стоимость LLM-вызовов на 90%**: архитектура Handler-Formatter и система доменных плагинов, которая позволяет добавить поддержку нового языка за 30 минут — без единой строчки Python.

---

**Хотите увидеть граф свойств кода на вашем проекте?**

[Подробнее о технологии CPG](https://codegraph.ru/cpg.html) | [Технический обзор](https://codegraph.ru/whitepaper.html)

---

*CodeGraph — инструмент построения и анализа графа свойств кода. 11 языков, 33 аналитических прохода, 190 правил структурного поиска. Подробнее: [codegraph.ru](https://codegraph.ru)*
