"use strict";

(() => {
  const root = document.querySelector("[data-screening-app]");
  if (!root) return;

  const sessionKey = "eligibl.syntheticCandidateId";
  const intro = document.getElementById("screening-intro");
  const chat = document.getElementById("screening-chat");
  const complete = document.getElementById("screening-complete");
  const messages = document.getElementById("message-list");
  const textArea = document.getElementById("candidate-message");
  const count = document.getElementById("character-count");
  const sendButton = document.getElementById("send-button");
  const typing = document.getElementById("typing-indicator");
  const quickReplies = document.getElementById("quick-replies");
  let candidateId = window.localStorage.getItem(sessionKey);

  async function post(url, data) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    const payload = await response.json();
    if (!response.ok) {
      const error = new Error(payload.error || "Something went wrong. Please try again.");
      error.safetyPause = payload.safety_pause === true;
      throw error;
    }
    return payload;
  }

  function addMessage(role, content) {
    const article = document.createElement("article");
    article.className = `chat-message ${role === "assistant" ? "from-assistant" : "from-candidate"}`;
    const label = document.createElement("span");
    label.className = "message-label";
    label.textContent = role === "assistant" ? "Eligibl" : "You";
    const paragraph = document.createElement("p");
    paragraph.textContent = content;
    article.append(label, paragraph);
    return article;
  }

  function render(state) {
    messages.replaceChildren(...state.messages.map((item) => addMessage(item.role, item.content)));
    messages.scrollTop = messages.scrollHeight;
    const total = Math.max(1, state.question_total || 1);
    const question = Math.min(total, Math.max(1, state.question_number || 1));
    document.getElementById("progress-label").textContent = `Question ${question} of ${total}`;
    const percent = Math.round(((question - 1) / total) * 100);
    const track = document.querySelector(".progress-track");
    track.setAttribute("aria-valuenow", String(percent));
    document.getElementById("progress-fill").style.width = `${percent}%`;
    quickReplies.replaceChildren(...(state.quick_replies || []).map((reply) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "quick-reply";
      button.textContent = reply;
      button.addEventListener("click", () => sendMessage(reply));
      return button;
    }));
    const safetyNotice = document.getElementById("safety-notice");
    const noticeText = state.budget_paused
      ? "Screening is paused for today. Please try again tomorrow."
      : state.safety_notice || "";
    safetyNotice.textContent = noticeText;
    safetyNotice.hidden = !noticeText;
    if (state.budget_paused) {
      textArea.disabled = true;
      sendButton.disabled = true;
    }
    const reviewStatus = document.getElementById("screening-status");
    reviewStatus.hidden = state.review_status !== "Flagged";
    if (state.status !== "in_progress") {
      chat.hidden = true;
      intro.hidden = true;
      complete.hidden = false;
      document.getElementById("completion-name").textContent = state.first_name;
      const finalLine = [...state.messages].reverse().find((item) => item.role === "assistant");
      document.getElementById("completion-message").textContent = finalLine?.content || `Thanks, ${state.first_name}. Your answers are with the study team. A coordinator will review them and reach out within 2 business days.`;
      return;
    }
    intro.hidden = true;
    complete.hidden = true;
    chat.hidden = false;
    textArea.focus();
  }

  function showError(id, error) {
    const node = document.getElementById(id);
    node.textContent = error.message;
    node.hidden = false;
  }

  function setBusy(value) {
    typing.hidden = !value;
    sendButton.disabled = value || textArea.disabled;
  }

  async function sendMessage(message) {
    if (!candidateId || !message.trim()) return;
    document.getElementById("chat-error").hidden = true;
    textArea.value = "";
    count.textContent = "0 / 800";
    setBusy(true);
    try {
      render(await post(`/api/screen/${encodeURIComponent(candidateId)}/message`, { message }));
    } catch (error) {
      showError("chat-error", error);
      if (error.safetyPause) {
        const notice = document.getElementById("safety-notice");
        notice.textContent = "Screening is paused for today. Please try again tomorrow.";
        notice.hidden = false;
        textArea.disabled = true;
        sendButton.disabled = true;
      }
      textArea.value = message;
      count.textContent = `${message.length} / 800`;
    } finally {
      setBusy(false);
    }
  }

  document.getElementById("screening-start-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const button = event.currentTarget.querySelector("button[type=submit]");
    button.disabled = true;
    document.getElementById("start-error").hidden = true;
    try {
      const state = await post("/api/screen/start", {
        first_name: String(form.get("first_name") || "").trim(),
        consent: document.getElementById("consent").checked,
      });
      candidateId = state.candidate_id;
      window.localStorage.setItem(sessionKey, candidateId);
      render(state);
    } catch (error) {
      showError("start-error", error);
      button.disabled = false;
    }
  });

  document.getElementById("message-form").addEventListener("submit", (event) => {
    event.preventDefault();
    sendMessage(textArea.value);
  });
  textArea.addEventListener("input", () => {
    count.textContent = `${textArea.value.length} / 800`;
  });
  textArea.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      document.getElementById("message-form").requestSubmit();
    }
  });

  if (candidateId) {
    fetch(`/api/screen/${encodeURIComponent(candidateId)}`)
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("No saved screening session.")))
      .then(render)
      .catch(() => window.localStorage.removeItem(sessionKey));
  }
})();
