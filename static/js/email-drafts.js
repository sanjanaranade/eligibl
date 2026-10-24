"use strict";

(() => {
  document.querySelectorAll(".email-draft-card[data-status='draft']").forEach((card) => {
    const feedback = card.querySelector(".draft-feedback");
    const payload = () => ({
      subject: card.querySelector(".draft-subject").value,
      body: card.querySelector(".draft-body").value,
    });
    const save = async () => {
      const response = await fetch(`/api/coordinator/email-drafts/${card.dataset.draftId}`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload()),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not save edits.");
      return data;
    };
    card.addEventListener("click", async (event) => {
      const button = event.target.closest("[data-draft-action]");
      if (!button) return;
      feedback.textContent = "";
      button.disabled = true;
      try {
        await save();
        if (button.dataset.draftAction === "save") {
          feedback.textContent = "Edits saved. The draft has not been sent.";
        } else {
          const response = await fetch(`/api/coordinator/email-drafts/${card.dataset.draftId}/queue`, { method: "POST" });
          const data = await response.json();
          if (!response.ok) throw new Error(data.error || "This email did not pass the approval checks.");
          window.location.reload();
        }
      } catch (error) {
        feedback.textContent = error.message;
      } finally {
        button.disabled = false;
      }
    });
  });
})();
