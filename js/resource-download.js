const LEAD_SUBMISSION_TIMEOUT_MS = 20000;

const isLocalhost = (hostname) => ["localhost", "127.0.0.1"].includes(hostname);

const getLeadsApiUrl = () => isLocalhost(window.location.hostname)
  ? "http://localhost:8001/api/v1/leads"
  : "https://api.codegraph.ru/api/v1/leads";

async function fetchWithTimeout(url, options, timeout) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeout);

  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    window.clearTimeout(timeoutId);
  }
}

function classifyLeadSubmissionResponse(response) {
  if (response.status === 400) {
    return {
      reason: "lead_api_400",
      statusText: "Заявка не отправлена: проверьте обязательные поля и выбранные значения.",
    };
  }
  if (response.status === 422) {
    return {
      reason: "lead_api_422",
      statusText: "Заявка не отправлена: проверьте формат email и согласие на обработку данных.",
    };
  }
  if (response.status === 429) {
    return {
      reason: "lead_api_429",
      statusText: "Заявка не отправлена: слишком много попыток. Подождите немного и повторите.",
    };
  }
  if (response.status >= 500) {
    return {
      reason: "lead_api_5xx",
      statusText: "Заявка не отправлена: сервер временно недоступен. Повторите позже.",
    };
  }
  return {
    reason: `lead_api_${response.status}`,
    statusText: "Заявка не отправлена: произошла ошибка отправки. Повторите позже.",
  };
}

function classifyLeadSubmissionException(error) {
  if (error?.name === "AbortError") {
    return {
      reason: "timeout",
      statusText: "Заявка не отправлена: сервер не ответил вовремя. Повторите позже.",
    };
  }
  if (error instanceof TypeError) {
    return {
      reason: "network",
      statusText: "Заявка не отправлена: нет соединения с сервером. Проверьте интернет и повторите.",
    };
  }
  return {
    reason: "exception",
    statusText: "Заявка не отправлена: произошла ошибка отправки. Повторите позже.",
  };
}

function initResourceLeadForm(form) {
  const button = form.querySelector("[data-resource-submit]");
  const status = form.querySelector("[data-resource-status]");
  const result = form.querySelector("[data-resource-download-result]");
  const link = form.querySelector("[data-resource-download-link]");
  const consent = form.elements.consent;
  if (!button || !status || !result || !link || !consent) return;

  const config = {
    initiativeTask: form.dataset.initiativeTask,
    sourcePage: form.dataset.sourcePage,
    intent: form.dataset.intent || "resource_download",
    ctaVariant: form.dataset.ctaVariant,
    useCase: form.dataset.useCase,
    pageId: form.dataset.pageId,
    pageStage: form.dataset.pageStage || "resource",
    sessionKey: form.dataset.sessionKey || `codegraph_${form.dataset.resourceForm}_unlocked`,
    successEvent: form.dataset.successEvent || "resource_pdf_unlocked",
    submitLabel: form.dataset.submitLabel || "Получить PDF",
  };

  const hideDownload = () => {
    result.hidden = true;
    link.hidden = true;
    link.setAttribute("aria-hidden", "true");
    link.setAttribute("tabindex", "-1");
  };

  const revealDownload = () => {
    result.hidden = false;
    link.hidden = false;
    link.setAttribute("aria-hidden", "false");
    link.removeAttribute("tabindex");
    try {
      sessionStorage.setItem(config.sessionKey, "1");
    } catch (_error) {
      // The accepted lead remains usable when browser storage is restricted.
    }
    result.focus();
  };

  const wasUnlocked = () => {
    try {
      return sessionStorage.getItem(config.sessionKey) === "1";
    } catch (_error) {
      return false;
    }
  };

  hideDownload();
  if (wasUnlocked()) {
    revealDownload();
    status.textContent = "PDF уже доступен в этой сессии браузера.";
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    hideDownload();
    status.textContent = "";

    if (!form.checkValidity()) {
      form.reportValidity();
      status.textContent = "Не удалось отправить форму: проверьте обязательные поля и согласие.";
      return;
    }

    button.disabled = true;
    button.textContent = "Отправляем…";
    const payload = {
      name: form.elements.name.value.trim(),
      email: form.elements.email.value.trim(),
      company: form.elements.company.value.trim(),
      position: form.elements.position.value.trim() || null,
      buyer_role: form.elements.buyer_role.value,
      initiative_task: config.initiativeTask,
      source_page: config.sourcePage,
      intent: config.intent,
      cta_variant: config.ctaVariant,
      use_case: config.useCase,
      page_id: config.pageId,
      page_stage: config.pageStage,
      consent: consent.checked,
    };

    try {
      const response = await fetchWithTimeout(
        getLeadsApiUrl(),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
        LEAD_SUBMISSION_TIMEOUT_MS,
      );

      if (!response.ok) {
        const failure = classifyLeadSubmissionResponse(response);
        hideDownload();
        status.textContent = failure.statusText;
        return;
      }

      status.textContent = "Готово: заявка принята, ссылка на PDF открыта.";
      revealDownload();
      if (typeof window.ym === "function") {
        window.ym(107046651, "reachGoal", config.successEvent, {
          source: config.sourcePage,
        });
      }
    } catch (error) {
      const failure = classifyLeadSubmissionException(error);
      console.warn("Lead form submission failed:", failure.reason);
      hideDownload();
      status.textContent = failure.statusText;
    } finally {
      button.disabled = false;
      button.textContent = config.submitLabel;
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("form[data-resource-form]").forEach(initResourceLeadForm);
});
