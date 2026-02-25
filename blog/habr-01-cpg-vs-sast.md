# Почему pattern matching больше не работает: CPG против SAST

**Канал**: Habr
**Дата публикации**: Апрель 2026, Неделя 1
**Целевой ICP**: ICP #2 — CISO (Елена)
**Целевые ключевые слова**: SAST ложные срабатывания, CPG vs AST, taint analysis, DevSecOps инструменты
**Целевая страница**: codegraph.ru/security
**Статус**: Идея

---

## Хук

> 91% алертов вашего SAST-инструмента — ложные срабатывания.

Это не гипербола. Это данные Ghost Security за 2025 год. Девять из десяти алертов, которые ваша команда безопасности разбирает вручную, — пустышки. Разработчики перестают читать отчёты. CISO не доверяет инструменту. А реальные уязвимости тонут в потоке шума.

Почему так происходит? Потому что 90% SAST-инструментов до сих пор работают на уровне **pattern matching** — сопоставления шаблонов с абстрактным синтаксическим деревом (AST). Этот подход был хорош в 2010-м. В 2026-м он — архитектурный потолок.

В этой статье разберём, **почему pattern matching принципиально ограничен**, что такое Code Property Graph (CPG) и как он решает проблему ложных срабатываний на реальных примерах.

---

## 1. Как работает традиционный SAST

Классический SAST-инструмент (SonarQube, Semgrep, Fortify) анализирует код в три шага:

1. **Парсинг** — исходный код превращается в AST (Abstract Syntax Tree)
2. **Pattern matching** — набор правил (регулярные выражения или шаблоны AST) сопоставляется с деревом
3. **Отчёт** — каждое совпадение = алерт

Проблема в шаге 2. Pattern matching видит **синтаксис**, но не видит **семантику**. Он не знает:

- Откуда пришли данные (пользовательский ввод или константа?)
- Через какие функции они прошли (была ли валидация?)
- Достигают ли данные опасной точки (SQL-запрос, системный вызов?)

### Пример: ложное срабатывание

```c
void process_request(const char *input) {
    char *sanitized = sanitize_html(input);   // ← валидация
    char query[256];
    snprintf(query, sizeof(query),
             "SELECT * FROM users WHERE name='%s'", sanitized);
    db_execute(query);
}
```

Pattern matching видит: `snprintf` + строковая подстановка + `db_execute` → **SQL injection!**

Но данные прошли через `sanitize_html()`. Реальной уязвимости нет. Это и есть ложное срабатывание.

Умножьте на тысячи функций в вашей кодовой базе — и получите 91% шума.

---

## 2. Что такое Code Property Graph

Code Property Graph (CPG) — это **единая структура данных**, объединяющая три графа:

| Граф | Что показывает | Зачем нужен |
|------|---------------|-------------|
| **AST** (Abstract Syntax Tree) | Синтаксическая структура кода | Что написано |
| **CFG** (Control Flow Graph) | Порядок выполнения инструкций | Как выполняется |
| **PDG** (Program Dependence Graph) | Зависимости по данным и управлению | Откуда что зависит |

Дополнительно CPG включает **DDG** (Data Dependency Graph) — граф зависимостей по данным, который показывает, как значения переменных распространяются между инструкциями.

Когда все четыре графа объединены, аналитик (или инструмент) может задать вопрос:

> «Существует ли путь от пользовательского ввода до SQL-запроса, который **не проходит** через функцию санитизации?»

Это называется **taint analysis** — анализ потоков заражённых данных. И он принципиально невозможен на уровне AST.

---

## 3. Три примера, где SAST промахивается

### Пример 1: Межпроцедурная SQL-инъекция

```c
// file: input.c
char *get_user_input(void) {
    return getenv("USER_QUERY");
}

// file: db.c
void run_query(const char *q) {
    char sql[512];
    snprintf(sql, sizeof(sql), "SELECT * FROM data WHERE id='%s'", q);
    PQexec(conn, sql);
}

// file: main.c
void handle_request(void) {
    char *input = get_user_input();
    run_query(input);
}
```

**SAST (pattern matching)**: Не видит связи между тремя файлами. `run_query()` получает параметр `q` — откуда он пришёл? Pattern matching не знает. Алерт **не генерируется**.

**CPG (taint analysis)**: Строит граф: `getenv()` → `get_user_input()` → `handle_request()` → `run_query()` → `PQexec()`. Путь от source (`getenv`) до sink (`PQexec`) существует. Санитизации нет. **Реальная уязвимость найдена.**

### Пример 2: Ложный алерт после валидации

```c
void safe_handler(const char *raw_input) {
    if (!is_valid_integer(raw_input)) {
        return;  // ← ранний выход при невалидных данных
    }
    int id = atoi(raw_input);
    char query[128];
    snprintf(query, sizeof(query), "SELECT * FROM items WHERE id=%d", id);
    db_execute(query);
}
```

**SAST**: Видит `raw_input` → `snprintf` → `db_execute`. Алерт: SQL injection. **Ложное срабатывание.**

**CPG**: Видит, что путь до `snprintf` проходит через guard `is_valid_integer()`, и `atoi()` конвертирует строку в целое число. Инъекция через `%d` с целым числом невозможна. **Алерт не генерируется.**

### Пример 3: Уязвимость через callback

```c
typedef void (*handler_fn)(const char *);

void register_handler(handler_fn fn);

void unsafe_log(const char *data) {
    char cmd[256];
    snprintf(cmd, sizeof(cmd), "echo '%s' >> /var/log/app.log", data);
    system(cmd);  // ← command injection
}

void init(void) {
    register_handler(unsafe_log);
}
```

**SAST**: `register_handler` — вызов с указателем на функцию. Pattern matching не отслеживает, что `unsafe_log` будет вызван с пользовательскими данными. **Пропуск.**

**CPG**: Через VTable/binding pass восстанавливает, что `unsafe_log` регистрируется как обработчик. Через call graph видит, что обработчики вызываются с внешними данными. Строит taint-путь до `system()`. **Уязвимость найдена.**

---

## 4. Цифры: CPG vs Pattern Matching

| Метрика | Pattern Matching (SAST) | CPG (CodeGraph) |
|---------|------------------------|-----------------|
| False Positive Rate | 80-91% | 12% |
| Межпроцедурный анализ | Нет (или ограниченный) | Да, полный |
| Время запроса | Секунды | 2-3 мс |
| Языки | 1-5 | 11 |
| Taint Verification | Нет | Да |

Источники: Ghost Security 2025 (91% FP для традиционных SAST), внутренние бенчмарки CodeGraph.

---

## 5. Почему сейчас

Три тренда делают переход на CPG неизбежным:

1. **AI-генерированный код**: 45% кода от Copilot/Claude Code содержит уязвимости (Veracode 2025). Pattern matching не справляется с нешаблонным кодом.

2. **Импортозамещение**: Fortify и Checkmarx уходят с российского рынка. Отечественные аналоги повторяют архитектуру 2010-х. CPG — шанс перескочить поколение.

3. **Alert fatigue**: Команды безопасности тратят 60%+ времени на разбор ложных срабатываний вместо реальных угроз.

---

## Заключение

Pattern matching — это grep для безопасности. Он был полезен, когда кодовые базы были маленькими, а код писали только люди. В 2026-м, когда 40% нового кода генерируется AI, а уязвимости прячутся за цепочками из 5-10 функций в разных файлах, нужен другой подход.

Code Property Graph — этот подход. Не замена SAST, а его эволюция.

---

**Хотите увидеть, как CPG находит уязвимости в вашем коде?**

→ [Запросить demo безопасности](https://codegraph.ru/security.html)

→ [Читать whitepaper: CPG vs Pattern Matching](https://codegraph.ru/whitepaper.html)

---

*Теги: SAST, CPG, Code Property Graph, taint analysis, статический анализ, безопасность кода, DevSecOps, CodeGraph*
