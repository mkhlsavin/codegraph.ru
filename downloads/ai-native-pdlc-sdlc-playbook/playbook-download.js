"use strict";

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

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("playbook-lead-form");
  const button = document.getElementById("playbook-submit");
  const status = document.getElementById("playbook-status");
  const result = document.getElementById("playbook-download-result");
  const link = document.getElementById("playbook-download-link");
  const consent = document.getElementById("playbook-consent");
  if (!form || !button || !status || !result || !link || !consent) return;

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
      sessionStorage.setItem("codegraph_playbook_unlocked", "1");
    } catch (_error) {
      // The accepted lead must remain usable when browser storage is restricted.
    }
    result.focus();
  };

  const wasUnlocked = () => {
    try {
      return sessionStorage.getItem("codegraph_playbook_unlocked") === "1";
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
      initiative_task: "ai_native_pdlc_sdlc_playbook",
      source_page: "playbook_lead_magnet",
      intent: "resource_download",
      cta_variant: "playbook_pdf_gate",
      use_case: "ai_native_pdlc_sdlc",
      page_id: "downloads-ai-native-pdlc-sdlc-playbook",
      page_stage: "resource",
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
        window.ym(107046651, "reachGoal", "playbook_pdf_unlocked", {
          source: "playbook_lead_magnet",
        });
      }
    } catch (error) {
      const failure = classifyLeadSubmissionException(error);
      console.warn("Lead form submission failed:", failure.reason);
      hideDownload();
      status.textContent = failure.statusText;
    } finally {
      button.disabled = false;
      button.textContent = "Получить PDF";
    }
  });
});
