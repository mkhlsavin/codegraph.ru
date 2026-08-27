"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("playbook-lead-form");
  const button = document.getElementById("playbook-submit");
  const status = document.getElementById("playbook-status");
  const result = document.getElementById("playbook-download-result");
  const link = document.getElementById("playbook-download-link");
  const consent = document.getElementById("playbook-consent");
  if (!form || !button || !status || !result || !link || !consent) return;

  const leadsApiUrl = ["localhost", "127.0.0.1"].includes(window.location.hostname)
    ? "http://localhost:8001/api/v1/leads"
    : "https://api.codegraph.ru/api/v1/leads";

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
    sessionStorage.setItem("codegraph_playbook_unlocked", "1");
    result.focus();
  };

  hideDownload();
  if (sessionStorage.getItem("codegraph_playbook_unlocked") === "1") {
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
      const response = await fetch(leadsApiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error(`lead_api_${response.status}`);
      }
      status.textContent = "Готово: заявка принята, ссылка на PDF открыта.";
      revealDownload();
      if (typeof window.ym === "function") {
        window.ym(107046651, "reachGoal", "playbook_pdf_unlocked", { source: "playbook_lead_magnet" });
      }
    } catch (_error) {
      hideDownload();
      status.textContent = "Не удалось отправить форму. Проверьте соединение или попробуйте позже.";
    } finally {
      button.disabled = false;
      button.textContent = "Получить PDF";
    }
  });
});
