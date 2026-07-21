/**
 * CodeGraph Landing Page - Main JavaScript
 * Enterprise TOP-200 RF
 */

(function() {
  'use strict';

  // ============================================
  // Configuration
  // ============================================
  const CONFIG = {
    animationDuration: 300,
    typingSpeed: 50,
    counterDuration: 2000,
    scrollOffset: 80,
    observerThreshold: 0.1,
    // API configuration for demo
    apiBaseUrl: window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
      ? 'http://localhost:8000'
      : 'https://api.codegraph.ru',  // Production API server with SSL
    apiTimeout: 180000  // 180 seconds timeout (LLM responses can take 60+ seconds)
  };

  const METRIKA_COUNTER_ID = 107046651;

  function initiativeContext(sourcePage, intent, useCase) {
    return {
      sourcePage,
      intent,
      useCase,
      defaultCtaVariant: `${sourcePage}_initiative_cta`,
      formTitle: 'Разобрать одну продуктовую инициативу',
      formDescription: 'Результат встречи — черновая цепочка Product Intent → FR/NFR → Impact Scope → required evidence. Это не обещание автоматически подготовить полную спецификацию.',
      formButton: 'Разобрать инициативу',
      contextNote: sourcePage === 'index'
        ? ''
        : `Форма открыта со страницы «${sourcePage}»; source, intent и границы инициативы сохраняются в заявке.`
    };
  }

  const PAGE_CONTEXTS = {
    index: initiativeContext('index', 'product_initiative_review', 'traceability'),
    whitepaper: initiativeContext('whitepaper', 'canonical_model_review', 'traceability'),
    'product-delivery': initiativeContext('product-delivery', 'product_delivery_review', 'requirements_traceability'),
    evidence: initiativeContext('evidence', 'evidence_chain_review', 'conformance_evidence'),
    'digital-team': initiativeContext('digital-team', 'role_contract_review', 'governed_execution'),
    integrations: initiativeContext('integrations', 'integration_depth_review', 'integration_capabilities'),
    security: initiativeContext('security', 'security_requirement_review', 'security_conformance'),
    compliance: initiativeContext('compliance', 'data_boundary_review', 'technical_controls'),
    'platform-operations': initiativeContext('platform-operations', 'runtime_readiness_review', 'operations'),
    productivity: initiativeContext('productivity', 'engineering_conformance_review', 'engineering_management'),
    'business-efficiency': initiativeContext('business-efficiency', 'pilot_measurement_review', 'pilot_economics'),
    cpg: initiativeContext('cpg', 'impact_scope_review', 'code_impact'),
    'ai-engineering': initiativeContext('ai-engineering', 'ai_change_conformance_review', 'ai_code_governance')
  };

  // ============================================
  // Mock Responses (fallback when API unavailable)
  // ============================================
  const MOCK_RESPONSES = {
    'Как устроена авторизация?': {
      answer: "## Обзор механизма  \nМеханизм авторизации реализует многоуровневую систему проверки доступа, объединяющую OAuth, JWT-токены, IAM-политики и CLI-интерфейс. Он обеспечивает аутентификацию пользователей, проверку их прав и предоставление контекста безопасности для API.\n\n## Поток управления  \n\n1. **add_auth_commands**: Точка входа, регистрирующая CLI-команды для управления авторизацией.  \n   - Вызывает: `add_subparsers`, `add_parser`, `add_argument` — для настройки подкоманд (`status`, `roles`, `permissions` и т.д.).\n\n2. **run_auth_command**: Запускается при выполнении одной из подкоманд авторизации.  \n   - Вызывает: `_auth_oauth_status`, `_auth_roles`, `_auth_permissions`, `_auth_ldap_status` — в зависимости от выбранной подкоманды.\n\n3. **_auth_permissions**: Показывает права текущего пользователя.  \n   - Вызывает: `has_permission` — для проверки доступа, `get_role_permissions` — для получения разрешений по ролям.\n\n4. **has_permission**: Центральная функция проверки прав.  \n   - Вызывает: `get_role_permissions` — получает список разрешений роли, затем сравнивает с требуемым действием.\n\n5. **get_auth_context**: Формирует контекст авторизации для обработки запроса.  \n   - Вызывает: `get_iam_validator`, `bearer_scheme`, `is_token_blacklisted`, `api_key_header` — для извлечения и валидации токена.\n\n6. **get_authorization_url**: Генерирует URL для OAuth-авторизации.  \n   - Вызывается через `metaClassAdapter`, используется в OAuth-интеграции.\n\n7. **_validate_jwt**: Проверяет подлинность JWT-токена.  \n   - Используется в цепочке валидации, но не имеет прямых вызовов в графе — предположительно вызывается косвенно через middleware.\n\n## Ключевые функции  \n\n### _auth_permissions  \n- **Назначение**: Предоставить CLI-интерфейс для просмотра прав пользователя.  \n- **Роль**: Агрегирует данные о разрешениях и выводит их в консоль.  \n- **Расположение**: src/cli/auth_commands.py:76  \n\n### has_permission  \n- **Назначение**: Определить, разрешено ли действие для текущего пользователя.  \n- **Роль**: Центральный элемент контроля доступа, использует роли и политики.  \n- **Расположение**: src/api/auth/middleware.py:52  \n\n### get_auth_context  \n- **Назначение**: Собрать и проверить данные аутентификации из запроса.  \n- **Роль**: Извлекает токен, проверяет его через IAM, API-ключ или схему Bearer, блокирует чёрные списки.  \n- **Расположение**: src/api/auth/middleware.py:57  \n\n### get_authorization_url  \n- **Назначение**: Сгенерировать URL для перенаправления пользователя на OAuth-сервер.  \n- **Роль**: Обеспечивает начало OAuth-флоу авторизации.  \n- **Расположение**: src/api/auth/oauth.py:102  \n\n### _validate_jwt  \n- **Назначение**: Проверить подпись, срок действия и статус отзыва JWT-токена.  \n- **Роль**: Обеспечивает безопасность на уровне токена.  \n- **Расположение**: src/mcp/auth.py:80  \n\n## Гарантии согласованности  \nМеханизм обеспечивает согласованность через централизованный `get_auth_context`, который унифицирует обработку всех типов учётных данных (JWT, API-ключ, OAuth). Все проверки прав проходят через `has_permission`, что исключает дублирование логики и гарантирует единообразное применение политик.\n\n## Обработка ошибок  \nХотя в графе вызовов нет явных `try-catch`, предполагается, что:  \n- `is_token_blacklisted` и `bearer_scheme` выбрасывают исключения при невалидном токене, перехватываемые middleware.  \n- `get_iam_validator` может возвращать `None` или ошибку, если IAM недоступен.  \n- CLI-команды используют `warning` для нефатальных ошибок (например, временная недоступность LDAP).  \nТаким образом, ошибки обрабатываются на уровне API-мидлварей и CLI-обёрток, обеспечивая отказоустойчивость.",
      processing_time_ms: 85000
    },
    'Как работает оркестрация сценариев?': {
      answer: "## Обзор механизма\nОркестрация сценариев реализована через централизованное управление потоками обработки пользовательских запросов на основе определённого намерения (intent). Механизм выбирает соответствующий сценарий и последовательно применяет специализированные workflow-функции для анализа, обогащения и безопасной обработки данных. Архитектура построена по принципу модульности, где каждый сценарий изолирован, но следует общему шаблону выполнения, что обеспечивает предсказуемость и масштабируемость.\n\n## Поток управления\n\n1. **classify_intent_node**: Точка входа, определяет намерение пользователя по входному запросу (например, onboarding, tech_debt, compliance). Это первичная классификация, которая решает, какой сценарий будет запущен.\n   - Вызывает: `route_by_intent`\n\n2. **route_by_intent**: На основе результата классификации перенаправляет выполнение в соответствующий workflow (например, `onboarding_workflow`, `tech_debt_workflow`). Является маршрутизатором между intent и конкретной бизнес-логикой.\n   - Вызывает: Один из workflow-методов (например, `onboarding_workflow`, `compliance_workflow`)\n\n3. **onboarding_workflow / tech_debt_workflow / ...**: Каждый из workflow-методов представляет собой независимый сценарий, реализующий логику обработки. Все они следуют схожему шаблону: загрузка конфигурации, выполнение анализа, постобработка.\n   - Вызывает: `get_unified_config`, `_generate_llm_response`, `enrich_onboarding_result`, `_apply_post_processing_safety_net` (в случае onboarding)\n   - Или: `check_complexity`, `readlines`, `__next__`, `join` (в других сценариях)\n\n4. **get_unified_config**: Централизованная загрузка конфигурации, общая для большинства workflow. Обеспечивает единообразие настроек.\n   - Используется в: `onboarding_workflow`, `tech_debt_workflow`, `architecture_workflow`, `optimization_composite_workflow`\n\n5. **_generate_llm_response / check_complexity / ...**: Специализированные действия, зависящие от сценария — от генерации ответов с помощью LLM до проверки соответствия стандартам.\n   - Вызывается в рамках конкретного workflow\n\n6. **_apply_post_processing_safety_net / enrich_onboarding_result**: Финальные этапы обработки, включающие проверку безопасности, обогащение результатов и подготовку к возврату.\n\n## Ключевые функции\n\n### route_by_intent\n- **Назначение**: Централизованная маршрутизация по intent\n- **Роль**: Гарантирует, что каждый запрос попадает в соответствующий сценарий\n- **Расположение**: src/workflow/orchestration/router.py:16\n\n### onboarding_workflow\n- **Назначение**: Обработка сценария онбординга\n- **Роль**: Оркестрирует анализ, генерацию и безопасную выдачу результата\n- **Расположение**: src/workflow/scenarios/onboarding/workflow.py:29\n\n### get_unified_config\n- **Назначение**: Единый источник конфигурации\n- **Роль**: Обеспечивает согласованность настроек между сценариями\n- **Расположение**: Вызывается из нескольких workflow\n\n### compliance_workflow\n- **Назначение**: Проверка соответствия стандартам и сложности кода\n- **Роль**: Анализирует метрики и возвращает результаты проверки\n- **Расположение**: src/workflow/scenarios/compliance.py:54\n\n### optimization_composite_workflow\n- **Назначение**: Композитная оптимизация кода\n- **Роль**: Оркестрирует несколько подзадач оптимизации, объединяя результаты\n- **Расположение**: src/workflow/scenarios/code_optimization_composite.py:59\n\n## Гарантии согласованности\nСогласованность обеспечивается через:\n- Единый `get_unified_config` для всех сценариев\n- Централизованный `route_by_intent` как единую точку входа после классификации\n- Общие паттерны обработки (постобработка, логирование через `info`, `warning`, `error`)\n\n## Обработка ошибок\nПрямые вызовы `error`, `warning`, `info` указывают на использование логирования для отслеживания состояния. Отсутствие явных try/catch в цепочках предполагает, что обработка ошибок может быть реализована на уровне оркестратора или через декораторы. `_apply_post_processing_safety_net` в onboarding явно указывает на наличие \"страховочного\" механизма для предотвращения некорректных выходов.",
      processing_time_ms: 78000
    },
    'Какие функции вызывают get_unified_config?': {
      answer: "Граф вызовов для `get_unified_config`:\n\n> Получить экземпляр унифицированной конфигурации — `src/config/unified_config.py`\n\n**Вызывается из (19):**\n- `_adapt_config` в `src/retrieval/hybrid/retriever.py:120` — # Fallback to vector-only\n- `_add_call_graph` в `src/workflow/handlers/dataflow.py:281`\n- `_add_relaxation_variants` в `src/agents/query_variants.py:275`\n- `_add_scenario_vector_context` в `src/workflow/scenarios/enrichment_adapter.py:212`\n- `_add_target_function` в `src/workflow/handlers/dataflow.py:135`\n- `_analyze_betweenness_risk` в `src/workflow/scenarios/refactoring/workflow.py:288`\n- `_analyze_consolidation_candidates` в `src/workflow/scenarios/cross_repo_handlers/handlers/base.py:188`\n- `_analyze_dependencies` в `src/workflow/scenarios/feature_dev_handlers/handlers/base.py:185`\n- `_analyze_fan_in` в `src/workflow/scenarios/architecture_handlers/handlers/coupling.py:206`\n- `_analyze_fan_out` в `src/workflow/scenarios/architecture_handlers/handlers/coupling.py:131`\n- `_analyze_impact` в `src/workflow/handlers/analysis.py:337`\n- `_analyze_lock_patterns` в `src/workflow/scenarios/concurrency_handlers/handlers/lock_usage.py:146`\n- `_analyze_module_coupling` в `src/workflow/scenarios/architecture_handlers/handlers/coupling.py:59`\n- `_analyze_refactoring_impacts` в `src/workflow/scenarios/refactoring/workflow.py:191`\n- `_analyze_with_cPG` в `src/code_optimization/engine.py:318`\n... и ещё 4\n\n**Вызывает (1):**\n- get_instance",
      processing_time_ms: 17000
    },
    'default': {
      answer: 'CodeGraph использует Code Property Graph как один из механизмов impact analysis. Результат анализа требует версии, области проверки и evidence; демонстрационный ответ не является подтверждением реализации требования.',
      processing_time_ms: 500
    }
  };

  // ============================================
  // DOM Elements Cache
  // ============================================
  const DOM = {};

  function getCurrentPageName() {
    const pathname = window.location.pathname || '';
    const lastSegment = pathname.split('/').filter(Boolean).pop() || 'index.html';
    return lastSegment.replace(/\.html$/u, '') || 'index';
  }

  function getPageContextBySource(sourcePage) {
    const normalizedSource = (sourcePage || 'index').replace(/\.html$/u, '');
    return PAGE_CONTEXTS[normalizedSource] || PAGE_CONTEXTS.index;
  }

  function inferCtaVariant(element, fallbackSource) {
    const sourcePage = (fallbackSource || getCurrentPageName() || 'index').replace(/\.html$/u, '');

    if (!element) {
      return `${sourcePage}_cta`;
    }

    if (element.closest('.hero-actions')) {
      return `${sourcePage}_hero`;
    }

    if (element.closest('.cta-content')) {
      return `${sourcePage}_cta`;
    }

    if (element.closest('.nav')) {
      return `${sourcePage}_header`;
    }

    if (element.closest('.mobile-nav')) {
      return `${sourcePage}_mobile_nav`;
    }

    if (element.closest('.footer')) {
      return `${sourcePage}_footer`;
    }

    return `${sourcePage}_cta`;
  }

  function buildDemoHref(pageContext, ctaVariant) {
    const params = new URLSearchParams({
      source_page: pageContext.sourcePage,
      intent: pageContext.intent,
      use_case: pageContext.useCase,
      cta_variant: ctaVariant || pageContext.defaultCtaVariant
    });

    return `index.html?${params.toString()}#demo`;
  }

  function getLeadContext() {
    const params = new URLSearchParams(window.location.search);
    const sourcePage = (
      DOM.sourcePageInput?.value
      || params.get('source_page')
      || getCurrentPageName()
      || 'index'
    ).replace(/\.html$/u, '');
    const pageContext = getPageContextBySource(sourcePage);

    return {
      sourcePage,
      intent: DOM.intentInput?.value || params.get('intent') || pageContext.intent,
      useCase: DOM.useCaseInput?.value || params.get('use_case') || pageContext.useCase,
      ctaVariant: DOM.ctaVariantInput?.value || params.get('cta_variant') || pageContext.defaultCtaVariant,
      pageContext
    };
  }

  function trackGoal(goalName, params = {}) {
    if (typeof window.ym !== 'function') {
      return;
    }

    try {
      window.ym(METRIKA_COUNTER_ID, 'reachGoal', goalName, params);
    } catch (error) {
      console.warn('Metrika tracking error:', error);
    }
  }

  function applyContextAwareDemoLinks() {
    const currentPageName = getCurrentPageName();

    if (currentPageName === 'index') {
      return;
    }

    const pageContext = getPageContextBySource(currentPageName);
    const demoLinks = document.querySelectorAll('a[href="index.html#demo"], a[href^="index.html#demo"]');

    demoLinks.forEach(link => {
      const ctaVariant = inferCtaVariant(link, pageContext.sourcePage);
      link.href = buildDemoHref(pageContext, ctaVariant);
      link.dataset.sourcePage = pageContext.sourcePage;
      link.dataset.intent = pageContext.intent;
      link.dataset.useCase = pageContext.useCase;
      link.dataset.ctaVariant = ctaVariant;
    });
  }

  function applyLeadContextToForm() {
    if (!DOM.demoForm) return;

    const params = new URLSearchParams(window.location.search);
    const leadContext = getLeadContext();
    const { pageContext } = leadContext;
    const hasContext = params.has('source_page') && leadContext.sourcePage !== 'index';

    if (DOM.demoHeading && !DOM.demoHeading.dataset.defaultText) {
      DOM.demoHeading.dataset.defaultText = DOM.demoHeading.textContent.trim();
    }

    if (DOM.demoDescription && !DOM.demoDescription.dataset.defaultText) {
      DOM.demoDescription.dataset.defaultText = DOM.demoDescription.textContent.trim();
    }

    if (DOM.demoSubmitBtn && !DOM.demoSubmitBtn.dataset.defaultText) {
      DOM.demoSubmitBtn.dataset.defaultText = DOM.demoSubmitBtn.textContent.trim();
    }

    if (DOM.sourcePageInput) {
      DOM.sourcePageInput.value = leadContext.sourcePage;
    }

    if (DOM.intentInput) {
      DOM.intentInput.value = leadContext.intent;
    }

    if (DOM.ctaVariantInput) {
      DOM.ctaVariantInput.value = leadContext.ctaVariant;
    }

    if (DOM.useCaseInput) {
      DOM.useCaseInput.value = leadContext.useCase;
    }

    if (!hasContext) {
      if (DOM.demoHeading?.dataset.defaultText) {
        DOM.demoHeading.textContent = DOM.demoHeading.dataset.defaultText;
      }

      if (DOM.demoDescription?.dataset.defaultText) {
        DOM.demoDescription.textContent = DOM.demoDescription.dataset.defaultText;
      }

      if (DOM.demoSubmitBtn?.dataset.defaultText) {
        DOM.demoSubmitBtn.textContent = DOM.demoSubmitBtn.dataset.defaultText;
      }

      if (DOM.demoContextNote) {
        DOM.demoContextNote.textContent = '';
        DOM.demoContextNote.hidden = true;
      }

      return;
    }

    if (DOM.demoHeading) {
      DOM.demoHeading.textContent = pageContext.formTitle;
    }

    if (DOM.demoDescription) {
      DOM.demoDescription.textContent = pageContext.formDescription;
    }

    if (DOM.demoSubmitBtn) {
      DOM.demoSubmitBtn.textContent = pageContext.formButton;
    }

    if (DOM.demoContextNote) {
      DOM.demoContextNote.textContent = pageContext.contextNote;
      DOM.demoContextNote.hidden = !pageContext.contextNote;
    }
  }

  function initCtaTracking() {
    const trackedLinks = document.querySelectorAll('a[href*="#demo"], a[href*="whitepaper.html"]');
    const currentPageName = getCurrentPageName();
    const pageContext = getPageContextBySource(currentPageName);

    trackedLinks.forEach(link => {
      link.addEventListener('click', () => {
        const href = link.getAttribute('href') || '';
        const ctaVariant = link.dataset.ctaVariant || inferCtaVariant(link, pageContext.sourcePage);

        if (href.includes('whitepaper.html')) {
          trackGoal('whitepaper_click', {
            source_page: pageContext.sourcePage,
            cta_variant: ctaVariant
          });
        }

        if (href.includes('#demo')) {
          trackGoal(currentPageName === 'index' ? 'cta_click' : 'vertical_cta_click', {
            source_page: link.dataset.sourcePage || pageContext.sourcePage,
            intent: link.dataset.intent || pageContext.intent,
            use_case: link.dataset.useCase || pageContext.useCase,
            cta_variant: ctaVariant
          });
        }
      });
    });
  }

  function initFormJourneyTracking() {
    if (!DOM.demoForm) return;

    const leadContext = getLeadContext();
    const params = {
      source_page: leadContext.sourcePage,
      intent: leadContext.intent,
      use_case: leadContext.useCase,
      cta_variant: leadContext.ctaVariant
    };
    let viewed = false;
    const trackView = () => {
      if (viewed) return;
      viewed = true;
      trackGoal('demo_form_view', params);
    };

    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver((entries) => {
        if (entries.some(entry => entry.isIntersecting)) {
          trackView();
          observer.disconnect();
        }
      }, { threshold: 0.2 });
      observer.observe(DOM.demoForm);
    } else {
      trackView();
    }
  }

  function cacheDOM() {
    DOM.html = document.documentElement;
    DOM.body = document.body;
    DOM.header = document.querySelector('[data-shell-header]');
    DOM.themeToggle = document.querySelector('[data-theme-toggle]');
    DOM.mobileMenuToggle = document.querySelector('[data-mobile-menu-toggle]');
    DOM.mobileNav = document.querySelector('[data-mobile-nav]');
    DOM.navLinks = document.querySelectorAll('[data-nav-link]');
    DOM.demoInput = document.getElementById('demo-input');
    DOM.demoOutput = document.getElementById('demo-output');
    DOM.demoCursor = document.querySelector('.demo-cursor');
    DOM.demoExampleBtns = document.querySelectorAll('.demo-example-btn');
    DOM.featureTabs = document.querySelectorAll('.feature-tab');
    DOM.featurePanels = document.querySelectorAll('.features-panel');
    DOM.faqItems = document.querySelectorAll('.faq-item');
    DOM.faqSearch = document.querySelector('.faq-search-input');
    DOM.faqCategoryBtns = document.querySelectorAll('.faq-category-btn');
    DOM.integrationFilterBtns = document.querySelectorAll('.integration-filter-btn');
    DOM.integrationCards = document.querySelectorAll('.integration-card');
    DOM.pipelineSteps = document.querySelectorAll('.pipeline-step');
    DOM.scenarioTabs = document.querySelectorAll('.scenario-tab');
    DOM.counters = document.querySelectorAll('[data-count]');
    DOM.animatedElements = document.querySelectorAll('[data-animate]');
    DOM.demoForm = document.getElementById('demo-form');
    DOM.demoHeading = document.getElementById('demo-heading');
    DOM.demoDescription = document.getElementById('demo-description');
    DOM.demoContextNote = document.getElementById('demo-context-note');
    DOM.demoSubmitBtn = document.getElementById('demo-submit-btn');
    DOM.demoStatus = document.getElementById('demo-status');
    DOM.buyerRoleInput = document.getElementById('buyer-role');
    DOM.initiativeTaskInput = document.getElementById('initiative-task');
    DOM.sourcePageInput = document.getElementById('source-page');
    DOM.intentInput = document.getElementById('intent');
    DOM.ctaVariantInput = document.getElementById('cta-variant');
    DOM.useCaseInput = document.getElementById('use-case');
    // Solution section demo
    DOM.questionInput = document.getElementById('question-input');
    DOM.askBtn = document.getElementById('ask-btn');
    DOM.demoResult = document.getElementById('demo-result');
    DOM.solutionExampleBtns = document.querySelectorAll('.solution .demo-example-btn, #solution .demo-example-btn');
  }

  // ============================================
  // Theme Management
  // ============================================
  function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const theme = savedTheme || (prefersDark ? 'dark' : 'light');
    setTheme(theme);

    if (DOM.themeToggle) {
      DOM.themeToggle.addEventListener('click', toggleTheme);
    }

    // Listen for system theme changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
      if (!localStorage.getItem('theme')) {
        setTheme(e.matches ? 'dark' : 'light');
      }
    });
  }

  function setTheme(theme) {
    DOM.html.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }

  function toggleTheme() {
    const currentTheme = DOM.html.getAttribute('data-theme');
    setTheme(currentTheme === 'dark' ? 'light' : 'dark');
  }

  // ============================================
  // Mobile Navigation
  // ============================================
  function initMobileNav() {
    if (!DOM.mobileMenuToggle || !DOM.mobileNav) return;

    const setMobileNavState = (isOpen) => {
      const state = isOpen ? 'open' : 'closed';
      DOM.mobileMenuToggle.dataset.state = state;
      DOM.mobileNav.dataset.state = state;
      DOM.mobileMenuToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      DOM.body.classList.toggle('overflow-hidden', isOpen);
    };

    DOM.mobileMenuToggle.addEventListener('click', () => {
      setMobileNavState(DOM.mobileNav.dataset.state !== 'open');
    });

    // Close on link click
    DOM.navLinks.forEach(link => {
      link.addEventListener('click', () => {
        setMobileNavState(false);
      });
    });

    // Close on escape
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && DOM.mobileNav.dataset.state === 'open') {
        setMobileNavState(false);
        DOM.mobileMenuToggle.focus();
      }
    });

    setMobileNavState(false);
  }

  // ============================================
  // Header Scroll Behavior
  // ============================================
  function initHeaderScroll() {
    if (!DOM.header) return;

    let ticking = false;

    window.addEventListener('scroll', () => {
      if (!ticking) {
        window.requestAnimationFrame(() => {
          const currentScroll = window.pageYOffset;

          DOM.header.dataset.scrolled = currentScroll > 50 ? 'true' : 'false';
          ticking = false;
        });
        ticking = true;
      }
    });
  }

  // ============================================
  // Screen Viewer
  // ============================================
  function initScreenViewer() {
    const viewer = document.getElementById('screen-viewer');
    const image = document.getElementById('screen-viewer-image');
    const title = document.getElementById('screen-viewer-title');
    const description = document.getElementById('screen-viewer-description');
    const closeButton = document.querySelector('.screen-viewer-close');
    const backdrop = document.querySelector('.screen-viewer-backdrop');
    const triggers = document.querySelectorAll('[data-screen-viewer]');

    if (!viewer || !image || !title || !description || triggers.length === 0) {
      return;
    }

    let lastFocusedElement = null;

    const closeViewer = () => {
      viewer.hidden = true;
      viewer.setAttribute('aria-hidden', 'true');
      image.removeAttribute('src');
      image.alt = '';
      DOM.body.classList.remove('overflow-hidden');
      if (lastFocusedElement instanceof HTMLElement) {
        lastFocusedElement.focus();
      }
    };

    triggers.forEach(trigger => {
      trigger.addEventListener('click', (event) => {
        event.preventDefault();
        lastFocusedElement = trigger;
        image.src = trigger.getAttribute('href') || '';
        image.alt = trigger.querySelector('img')?.alt || '';
        title.textContent = trigger.dataset.screenTitle || '';
        description.textContent = trigger.dataset.screenDescription || '';
        viewer.hidden = false;
        viewer.setAttribute('aria-hidden', 'false');
        DOM.body.classList.add('overflow-hidden');
        closeButton?.focus();
      });
    });

    closeButton?.addEventListener('click', closeViewer);
    backdrop?.addEventListener('click', closeViewer);

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && !viewer.hidden) {
        closeViewer();
      }
    });
  }

  // ============================================
  // Smooth Scroll
  // ============================================
  function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
      anchor.addEventListener('click', function(e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
          const offsetTop = target.offsetTop - CONFIG.scrollOffset;
          window.scrollTo({
            top: offsetTop,
            behavior: 'smooth'
          });
        }
      });
    });
  }

  // ============================================
  // Demo Terminal
  // ============================================
  function initDemoTerminal() {
    if (!DOM.demoInput || !DOM.demoOutput) return;

    // Handle input
    DOM.demoInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const query = DOM.demoInput.value.trim();
        if (query) {
          runDemo(query);
        }
      }
    });

    // Handle example buttons
    DOM.demoExampleBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const query = btn.getAttribute('data-query');
        DOM.demoInput.value = query;
        runDemo(query);
      });
    });

    // Auto-run first demo on load
    setTimeout(() => {
      if (DOM.demoExampleBtns.length > 0) {
        const firstQuery = DOM.demoExampleBtns[0].getAttribute('data-query');
        typeText(DOM.demoInput, firstQuery, () => {
          setTimeout(() => runDemo(firstQuery), 500);
        });
      }
    }, 1500);
  }

  async function runDemo(query) {
    // Animate pipeline
    animatePipeline();

    // Show loading state
    DOM.demoOutput.innerHTML = '<span class="highlight">Анализирую...</span>';
    if (DOM.demoCursor) DOM.demoCursor.hidden = false;

    try {
      // Call the API
      const response = await fetchWithTimeout(
        `${CONFIG.apiBaseUrl}/api/v1/demo/chat`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            query: query,
            language: 'ru'
          })
        },
        CONFIG.apiTimeout
      );

      if (response.status === 429) {
        DOM.demoOutput.innerHTML = '<span class="warning">Превышен лимит запросов. Подождите минуту.</span>';
        if (DOM.demoCursor) DOM.demoCursor.hidden = true;
        return;
      }

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data = await response.json();
      displayHeroDemoResult(data.answer);

    } catch (err) {
      console.warn('API call failed, using mock response:', err.message);
      // Fallback to mock response
      const mockData = MOCK_RESPONSES[query] || MOCK_RESPONSES['default'];

      // Simulate delay for realism
      await new Promise(resolve => setTimeout(resolve, 800 + Math.random() * 400));
      displayHeroDemoResult(mockData.answer);
    }
  }

  function displayHeroDemoResult(answer) {
    DOM.demoOutput.innerHTML = '';

    const MAX_HERO_LENGTH = 300;
    let displayText = answer;
    let isTruncated = false;

    if (displayText.length > MAX_HERO_LENGTH) {
      displayText = displayText.substring(0, MAX_HERO_LENGTH).trim();
      const lastSpace = displayText.lastIndexOf(' ');
      if (lastSpace > MAX_HERO_LENGTH - 50) {
        displayText = displayText.substring(0, lastSpace);
      }
      displayText += '...';
      isTruncated = true;
    }

    typeHTML(DOM.demoOutput, escapeHtml(displayText), () => {
      if (DOM.demoCursor) DOM.demoCursor.hidden = true;
      if (isTruncated) {
        const moreLink = document.createElement('a');
        moreLink.href = '#solution';
        moreLink.className = 'demo-more-link';
        moreLink.textContent = ' Подробнее →';
        moreLink.addEventListener('click', (e) => {
          e.preventDefault();
          document.querySelector('#solution').scrollIntoView({ behavior: 'smooth' });
        });
        DOM.demoOutput.appendChild(moreLink);
      }
    });
  }

  function typeText(element, text, callback) {
    let i = 0;
    element.value = '';

    function type() {
      if (i < text.length) {
        element.value += text.charAt(i);
        i++;
        setTimeout(type, CONFIG.typingSpeed);
      } else if (callback) {
        callback();
      }
    }

    type();
  }

  function typeHTML(element, html, callback) {
    // Parse HTML and type it out
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = html;
    const text = tempDiv.textContent;

    let i = 0;
    let currentHTML = '';

    function type() {
      if (i < html.length) {
        // Handle HTML tags
        if (html[i] === '<') {
          const closeTag = html.indexOf('>', i);
          if (closeTag !== -1) {
            currentHTML += html.substring(i, closeTag + 1);
            i = closeTag + 1;
          }
        } else {
          currentHTML += html[i];
          i++;
        }

        element.innerHTML = currentHTML;

        // Variable speed for more natural feel
        const delay = html[i - 1] === '\n' ? 100 : (Math.random() * 20 + 10);
        setTimeout(type, delay);
      } else if (callback) {
        callback();
      }
    }

    type();
  }

  // ============================================
  // Solution Section Demo
  // ============================================
  function initSolutionDemo() {
    if (!DOM.questionInput || !DOM.demoResult) return;

    // Handle ask button
    if (DOM.askBtn) {
      DOM.askBtn.addEventListener('click', () => {
        const query = DOM.questionInput.value.trim();
        if (query) {
          runSolutionDemo(query);
        }
      });
    }

    // Handle input enter key
    DOM.questionInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const query = DOM.questionInput.value.trim();
        if (query) {
          runSolutionDemo(query);
        }
      }
    });

    // Handle example buttons in solution section
    const exampleBtns = document.querySelectorAll('#solution .demo-example-btn');
    exampleBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const query = btn.getAttribute('data-query');
        DOM.questionInput.value = query;
        runSolutionDemo(query);
      });
    });
  }

  async function runSolutionDemo(query) {
    // Animate pipeline
    animatePipeline();

    // Show loading state
    DOM.demoResult.innerHTML = '<div class="result-loading"><span class="spinner"></span> Анализирую...</div>';

    try {
      // Try to call the API
      const response = await fetchWithTimeout(
        `${CONFIG.apiBaseUrl}/api/v1/demo/chat`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            query: query,
            language: 'ru'
          })
        },
        CONFIG.apiTimeout
      );

      if (response.status === 429) {
        // Rate limit exceeded
        showRateLimitError();
        return;
      }

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data = await response.json();
      showApiResult(data.answer, data.processing_time_ms);

    } catch (err) {
      console.warn('API call failed, using mock response:', err.message);
      // Fallback to mock response
      const mockData = MOCK_RESPONSES[query] || MOCK_RESPONSES['default'];

      // Simulate delay for realism
      await new Promise(resolve => setTimeout(resolve, 800 + Math.random() * 400));
      showApiResult(mockData.answer, mockData.processing_time_ms);
    }
  }

  // Helper function for fetch with timeout
  async function fetchWithTimeout(url, options, timeout) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal
      });
      clearTimeout(timeoutId);
      return response;
    } catch (err) {
      clearTimeout(timeoutId);
      throw err;
    }
  }

  // Render markdown safely (fallback to escaped text if marked unavailable)
  function renderMarkdown(text) {
    if (typeof marked !== 'undefined' && marked.parse) {
      return marked.parse(text, { breaks: true });
    }
    return '<pre>' + escapeHtml(text) + '</pre>';
  }

  // Show API result
  function showApiResult(answer, processingTimeMs) {
    const timeStr = processingTimeMs ? ` <span class="processing-time">(${processingTimeMs.toFixed(0)}ms)</span>` : '';
    DOM.demoResult.innerHTML = `<div class="result-content result-markdown">${renderMarkdown(answer)}${timeStr}</div>`;
  }

  // Show rate limit error
  function showRateLimitError() {
    DOM.demoResult.innerHTML = `<div class="result-error">
      <span class="warning">Превышен лимит запросов (30/мин)</span>
      <p>Пожалуйста, подождите минуту и попробуйте снова.</p>
    </div>`;
  }

  // Show error when API fails
  function showApiError() {
    DOM.demoResult.innerHTML = '<div class="result-error"><span class="warning">API недоступен. Попробуйте позже.</span></div>';
  }

  // Escape HTML to prevent XSS
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // ============================================
  // Pipeline Animation
  // ============================================
  function animatePipeline() {
    if (!DOM.pipelineSteps || DOM.pipelineSteps.length === 0) return;

    // Reset all steps
    DOM.pipelineSteps.forEach(step => step.classList.remove('active'));

    // Animate each step sequentially
    DOM.pipelineSteps.forEach((step, index) => {
      setTimeout(() => {
        // Deactivate previous
        if (index > 0) {
          DOM.pipelineSteps[index - 1].classList.remove('active');
        }
        // Activate current
        step.classList.add('active');
      }, index * 800);
    });

    // Keep last step active
    setTimeout(() => {
      DOM.pipelineSteps[DOM.pipelineSteps.length - 1].classList.add('active');
    }, DOM.pipelineSteps.length * 800);
  }

  // ============================================
  // Feature Tabs
  // ============================================
  function initFeatureTabs() {
    if (!DOM.featureTabs || DOM.featureTabs.length === 0) return;

    DOM.featureTabs.forEach(tab => {
      tab.addEventListener('click', () => {
        const target = tab.getAttribute('data-tab');

        // Update tabs
        DOM.featureTabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');

        // Update panels
        DOM.featurePanels.forEach(panel => {
          panel.classList.remove('active');
          if (panel.getAttribute('data-panel') === target) {
            panel.classList.add('active');
          }
        });
      });
    });
  }

  // ============================================
  // Scenario Tabs
  // ============================================
  function initScenarioTabs() {
    if (!DOM.scenarioTabs || DOM.scenarioTabs.length === 0) return;

    DOM.scenarioTabs.forEach(tab => {
      tab.addEventListener('click', () => {
        const query = tab.getAttribute('data-query');

        // Update tabs
        DOM.scenarioTabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');

        // Run demo for query
        if (query && DOM.demoInput) {
          DOM.demoInput.value = query;
          runDemo(query);
        }
      });
    });
  }

  // ============================================
  // FAQ Accordion
  // ============================================
  function initFAQ() {
    if (!DOM.faqItems || DOM.faqItems.length === 0) return;

    DOM.faqItems.forEach(item => {
      const question = item.querySelector('.faq-question');
      if (question) {
        question.addEventListener('click', () => {
          // Toggle current
          item.classList.toggle('open');
          const isNowOpen = item.classList.contains('open');
          question.setAttribute('aria-expanded', String(isNowOpen));
        });
      }
    });

    // FAQ Search
    if (DOM.faqSearch) {
      DOM.faqSearch.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();

        DOM.faqItems.forEach(item => {
          const text = item.textContent.toLowerCase();
          item.hidden = !text.includes(query);
        });
      });
    }

    // FAQ Category Filter
    if (DOM.faqCategoryBtns) {
      DOM.faqCategoryBtns.forEach(btn => {
        btn.addEventListener('click', () => {
          const category = btn.getAttribute('data-category');

          // Update buttons
          DOM.faqCategoryBtns.forEach(b => {
            b.classList.remove('active');
            b.setAttribute('aria-pressed', 'false');
          });
          btn.classList.add('active');
          btn.setAttribute('aria-pressed', 'true');

          // Filter items
          DOM.faqItems.forEach(item => {
            if (category === 'all') {
              item.hidden = false;
            } else {
              const itemCategory = item.getAttribute('data-category');
              item.hidden = itemCategory !== category;
            }
          });
        });
      });
    }
  }

  // ============================================
  // Integration Filters
  // ============================================
  function initIntegrationFilters() {
    if (!DOM.integrationFilterBtns || DOM.integrationFilterBtns.length === 0) return;

    DOM.integrationFilterBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const filter = btn.getAttribute('data-filter');

        // Update buttons
        DOM.integrationFilterBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        // Filter cards
        DOM.integrationCards.forEach(card => {
          if (filter === 'all') {
            card.hidden = false;
          } else {
            const status = card.getAttribute('data-status');
            card.hidden = status !== filter;
          }
        });
      });
    });
  }

  // ============================================
  // Counter Animation
  // ============================================
  function initCounters() {
    if (!DOM.counters || DOM.counters.length === 0) return;

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          animateCounter(entry.target);
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: CONFIG.observerThreshold });

    DOM.counters.forEach(counter => observer.observe(counter));
  }

  function animateCounter(element) {
    const target = parseInt(element.getAttribute('data-count'), 10);
    const initialValue = parseInt((element.textContent || '0').replace(/[^\d]/gu, ''), 10);
    const startValue = Number.isNaN(initialValue) ? 0 : Math.min(initialValue, target);
    const suffix = element.getAttribute('data-suffix') || '';
    const prefix = element.getAttribute('data-prefix') || '';
    const duration = CONFIG.counterDuration;
    const start = performance.now();

    function update(currentTime) {
      const elapsed = currentTime - start;
      const progress = Math.min(elapsed / duration, 1);

      // Easing function (ease-out)
      const easeOut = 1 - Math.pow(1 - progress, 3);
      const current = Math.floor(startValue + ((target - startValue) * easeOut));

      element.textContent = prefix + current + suffix;

      if (progress < 1) {
        requestAnimationFrame(update);
      } else {
        element.textContent = prefix + target + suffix;
      }
    }

    requestAnimationFrame(update);
  }

  // ============================================
  // Scroll Animations
  // ============================================
  function initScrollAnimations() {
    if (!DOM.animatedElements || DOM.animatedElements.length === 0) return;

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const animation = entry.target.getAttribute('data-animate');
          entry.target.classList.add('animated', `animate-${animation}`);
          observer.unobserve(entry.target);
        }
      });
    }, {
      threshold: CONFIG.observerThreshold,
      rootMargin: '0px 0px -50px 0px'
    });

    DOM.animatedElements.forEach(el => observer.observe(el));
  }

  // ============================================
  // Form Validation
  // ============================================
  function initFormValidation() {
    if (!DOM.demoForm) return;

    // Russian validation messages
    const validationMessages = {
      valueMissing: 'Пожалуйста, заполните это поле',
      typeMismatch: {
        email: 'Пожалуйста, введите корректный email адрес',
        url: 'Пожалуйста, введите корректный URL'
      },
      patternMismatch: 'Пожалуйста, введите данные в правильном формате',
      tooShort: 'Минимальная длина: {minLength} символов',
      tooLong: 'Максимальная длина: {maxLength} символов'
    };

    // Apply Russian validation to all form inputs
    const formInputs = DOM.demoForm.querySelectorAll('input, select, textarea');
    const submitBtn = DOM.demoForm.querySelector('button[type="submit"]');
    const originalText = submitBtn?.textContent || 'Разобрать инициативу';
    let formStarted = false;
    const leadContext = getLeadContext();
    const eventContext = {
      source_page: leadContext.sourcePage,
      intent: leadContext.intent,
      use_case: leadContext.useCase,
      cta_variant: leadContext.ctaVariant
    };
    const setStatus = (text, state = '') => {
      if (!DOM.demoStatus) return;
      DOM.demoStatus.textContent = text;
      DOM.demoStatus.dataset.status = state;
    };
    const setSubmitState = (state, text, disabled) => {
      if (!submitBtn) return;
      submitBtn.dataset.submitState = state;
      submitBtn.textContent = text;
      submitBtn.disabled = disabled;
    };

    formInputs.forEach(input => {
      // Set custom message before validation
      input.addEventListener('invalid', (e) => {
        input.setAttribute('aria-invalid', 'true');
        const validity = input.validity;
        trackGoal('demo_form_field_error', {
          ...eventContext,
          field: input.name || input.id,
          reason: validity.valueMissing ? 'required' : validity.typeMismatch ? 'format' : 'invalid'
        });

        if (validity.valueMissing) {
          input.setCustomValidity(validationMessages.valueMissing);
        } else if (validity.typeMismatch) {
          const type = input.type;
          input.setCustomValidity(validationMessages.typeMismatch[type] || 'Неверный формат');
        } else if (validity.patternMismatch) {
          input.setCustomValidity(validationMessages.patternMismatch);
        } else if (validity.tooShort) {
          input.setCustomValidity(validationMessages.tooShort.replace('{minLength}', input.minLength));
        } else if (validity.tooLong) {
          input.setCustomValidity(validationMessages.tooLong.replace('{maxLength}', input.maxLength));
        }
      });

      // Clear custom validity on input to allow re-validation
      input.addEventListener('input', () => {
        if (!formStarted && input.value.trim()) {
          formStarted = true;
          trackGoal('demo_form_start', eventContext);
        }
        input.setCustomValidity('');
        input.removeAttribute('aria-invalid');
      });

      // Also clear on change for select elements
      input.addEventListener('change', () => {
        if (!formStarted && input.value.trim()) {
          formStarted = true;
          trackGoal('demo_form_start', eventContext);
        }
        input.setCustomValidity('');
        input.removeAttribute('aria-invalid');
      });
    });

    DOM.demoForm.addEventListener('submit', async (e) => {
      e.preventDefault();

      // Simple validation
      const inputs = DOM.demoForm.querySelectorAll('input[required], select[required]');
      let isValid = true;

      inputs.forEach(input => {
        if (!input.value.trim()) {
          isValid = false;
          input.setAttribute('aria-invalid', 'true');
        } else {
          input.removeAttribute('aria-invalid');
        }
      });

      // Email validation
      const emailInput = DOM.demoForm.querySelector('input[type="email"]');
      if (emailInput && emailInput.value) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(emailInput.value)) {
          isValid = false;
          emailInput.setAttribute('aria-invalid', 'true');
        }
      }

      if (!isValid) {
        trackGoal('demo_form_validation_error', eventContext);
        setStatus('Проверьте отмеченные поля и повторите отправку.', 'error');
        DOM.demoForm.querySelector('[aria-invalid="true"]')?.focus();
        return;
      }

      if (isValid) {
        // Submit form to leads API
        if (!submitBtn) return;

        const leadContext = getLeadContext();

        setSubmitState('sending', 'Отправка...', true);
        setStatus('Передаём заявку. После ответа мы предложим следующий шаг.', 'sending');
        trackGoal('demo_form_submit', {
          source_page: leadContext.sourcePage,
          intent: leadContext.intent,
          use_case: leadContext.useCase,
          cta_variant: leadContext.ctaVariant
        });

        // Collect form data
        const formData = {
          name: DOM.demoForm.querySelector('#name').value.trim(),
          email: DOM.demoForm.querySelector('#email').value.trim(),
          company: DOM.demoForm.querySelector('#company').value.trim(),
          position: DOM.demoForm.querySelector('#position')?.value.trim() || DOM.buyerRoleInput?.value || null,
          buyer_role: DOM.buyerRoleInput?.value || null,
          initiative_task: DOM.initiativeTaskInput?.value || null,
          team_size: DOM.demoForm.querySelector('#team-size')?.value || null,
          language: DOM.demoForm.querySelector('#language')?.value || null,
          source_page: leadContext.sourcePage,
          intent: leadContext.intent,
          cta_variant: leadContext.ctaVariant,
          use_case: leadContext.useCase,
        };

        // Determine API URL based on environment
        // Leads API is proxied via nginx on api.codegraph.ru
        const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
        const leadsApiUrl = isLocalhost
          ? 'http://localhost:8001/api/v1/leads'
          : 'https://api.codegraph.ru/api/v1/leads';

        try {
          const response = await fetch(leadsApiUrl, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData),
          });

          if (response.ok) {
            let responseData = {};
            try {
              responseData = await response.clone().json();
            } catch (parseError) {
              responseData = {};
            }
            const leadId = responseData.id || responseData.lead_id;
            trackGoal('demo_form_success', {
              source_page: leadContext.sourcePage,
              intent: leadContext.intent,
              use_case: leadContext.useCase,
              cta_variant: leadContext.ctaVariant,
              ...(leadId ? { lead_id: leadId } : {})
            });
            setSubmitState('success', 'Заявка отправлена!', true);
            setStatus('Заявка отправлена. Следующий шаг — согласовать время и состав участников разбора.', 'success');
            DOM.demoForm.reset();
            applyLeadContextToForm();

            setTimeout(() => {
              setSubmitState('idle', originalText, false);
            }, 3000);
          } else if (response.status === 429) {
            trackGoal('demo_form_rate_limit', eventContext);
            setSubmitState('error', 'Слишком много запросов', true);
            setStatus('Слишком много запросов. Подождите немного и повторите отправку; введённые данные сохранены.', 'error');

            setTimeout(() => {
              setSubmitState('idle', originalText, false);
            }, 3000);
          } else {
            throw new Error(`Server error: ${response.status}`);
          }
        } catch (error) {
          console.error('Form submission error:', error);
          trackGoal('demo_form_error', eventContext);
          setSubmitState('error', 'Ошибка отправки', true);
          setStatus('Не удалось отправить заявку. Проверьте соединение и повторите отправку; введённые данные сохранены.', 'error');

          setTimeout(() => {
            setSubmitState('idle', originalText, false);
          }, 3000);
        }
      }
    });
  }

  // ============================================
  // Active Navigation Highlight
  // ============================================
  function initActiveNavigation() {
    const sections = document.querySelectorAll('section[id]');

    if (sections.length === 0) return;

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const id = entry.target.getAttribute('id');
          DOM.navLinks.forEach(link => {
            link.dataset.current = 'false';
            if (link.getAttribute('href') === `#${id}`) {
              link.dataset.current = 'true';
            }
          });
        }
      });
    }, {
      threshold: 0.3,
      rootMargin: '-80px 0px -50% 0px'
    });

    sections.forEach(section => observer.observe(section));
  }

  // ============================================
  // Keyboard Navigation
  // ============================================
  function initKeyboardNavigation() {
    // Tab focus indicators are handled by CSS :focus-visible

    // Arrow key navigation for tabs
    document.addEventListener('keydown', (e) => {
      if (e.target.classList.contains('feature-tab') ||
          e.target.classList.contains('scenario-tab') ||
          e.target.classList.contains('faq-question')) {

        const parent = e.target.parentElement;
        const items = Array.from(parent.querySelectorAll('[role="tab"], .faq-question'));
        const currentIndex = items.indexOf(e.target);

        let newIndex;
        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
          newIndex = (currentIndex + 1) % items.length;
        } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
          newIndex = (currentIndex - 1 + items.length) % items.length;
        }

        if (newIndex !== undefined) {
          e.preventDefault();
          items[newIndex].focus();
          items[newIndex].click();
        }
      }
    });
  }

  // ============================================
  // Performance Optimization
  // ============================================
  function initPerformanceOptimizations() {
    // Lazy load images (if any)
    if ('loading' in HTMLImageElement.prototype) {
      const images = document.querySelectorAll('img[loading="lazy"]');
      images.forEach(img => {
        const lazySrc = img.dataset.src;
        if (lazySrc) {
          img.src = lazySrc;
        }
      });
    }

    // Prefetch linked pages on hover
    let prefetchedLinks = new Set();
    document.querySelectorAll('a[href^="http"]').forEach(link => {
      link.addEventListener('mouseenter', () => {
        const href = link.getAttribute('href');
        if (!prefetchedLinks.has(href)) {
          const prefetch = document.createElement('link');
          prefetch.rel = 'prefetch';
          prefetch.href = href;
          document.head.appendChild(prefetch);
          prefetchedLinks.add(href);
        }
      }, { once: true });
    });
  }

  // ============================================
  // Accessibility Helpers
  // ============================================
  function initAccessibility() {
    // Add ARIA attributes dynamically
    DOM.faqItems.forEach((item, index) => {
      const question = item.querySelector('.faq-question');
      const answer = item.querySelector('.faq-answer');

      if (question && answer) {
        question.setAttribute('aria-expanded', 'false');
        question.setAttribute('aria-controls', `faq-answer-${index}`);
        answer.setAttribute('id', `faq-answer-${index}`);
      }
    });

    // Add role="tab" to tabs
    DOM.featureTabs.forEach(tab => {
      tab.setAttribute('role', 'tab');
    });

    DOM.scenarioTabs.forEach(tab => {
      tab.setAttribute('role', 'tab');
    });
  }

  // ============================================
  // Error Handling
  // ============================================
  window.onerror = function(msg, url, lineNo, columnNo, error) {
    console.error('Error: ', msg, '\nURL: ', url, '\nLine: ', lineNo);
    return false;
  };

  // ============================================
  // Initialize
  // ============================================
  function init() {
    cacheDOM();
    applyContextAwareDemoLinks();
    applyLeadContextToForm();
    initTheme();
    initMobileNav();
    initHeaderScroll();
    initScreenViewer();
    initSmoothScroll();
    initDemoTerminal();
    initSolutionDemo();
    initFeatureTabs();
    initScenarioTabs();
    initFAQ();
    initIntegrationFilters();
    initCounters();
    initScrollAnimations();
    initFormValidation();
    initActiveNavigation();
    initKeyboardNavigation();
    initPerformanceOptimizations();
    initAccessibility();
    initCtaTracking();
    initFormJourneyTracking();

    console.log('CodeGraph Landing Page initialized');
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
