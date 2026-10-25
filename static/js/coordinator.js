"use strict";

(() => {
  const panel = document.querySelector("#candidate-detail");
  const content = document.querySelector("#detail-content");
  const scrim = document.querySelector("#detail-scrim");
  if (!panel || !content) return;
  let activeId = "";

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
  const timeAgo = (value) => {
    if (!value) return "Not yet";
    const seconds = Math.max(0, (Date.now() - new Date(value).getTime()) / 1000);
    if (seconds < 60) return "Just now";
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  };
  document.querySelectorAll(".time-ago").forEach((node) => { node.textContent = timeAgo(node.dataset.time); });

  const openPanel = () => {
    panel.classList.add("open");
    panel.setAttribute("aria-hidden", "false");
    scrim?.classList.add("visible");
    document.body.classList.add("detail-open");
  };
  const closePanel = () => {
    panel.classList.remove("open");
    panel.setAttribute("aria-hidden", "true");
    scrim?.classList.remove("visible");
    document.body.classList.remove("detail-open");
  };

  const renderTrace = (trace) => {
    if (!trace.length) return '<p class="detail-placeholder">No agent trace steps are recorded for this candidate.</p>';
    return `<div class="trace-list">${trace.map((step) => `<article class="trace-step"><div class="trace-top"><span>Step ${step.step_number} · ${escapeHtml(step.agent)}</span><small>${step.input_tokens + step.output_tokens} tokens (${step.cached_input_tokens} cached)</small></div><dl><dt>Received</dt><dd>${escapeHtml(step.input_summary)}</dd><dt>Tools</dt><dd><code>${escapeHtml(JSON.stringify(step.tool_calls))}</code></dd><dt>Produced</dt><dd>${escapeHtml(step.output_summary)}</dd></dl></article>`).join("")}</div>`;
  };
  const renderDetail = (candidate) => {
    const criteria = candidate.criteria || [];
    const initials = candidate.display_name.trim().split(/\s+/).map((part) => part[0]).join("").toUpperCase();
    const statusIcons = { "Likely eligible": "✓", "Not a match": "×", "Needs review": "!", "Flagged": "⚑", "In progress": "◷", "Approved": "✓" };
    const journey = [
      ["Screened", candidate.session_status === "completed"],
      ["Reviewed", (candidate.actions || []).length > 0],
      ["Approved", candidate.coordinator_status === "approved"],
      ["Contacted", Boolean(candidate.contacted_at)],
      ["Reminded", false],
    ];
    let currentJourney = journey.findIndex(([, done]) => !done);
    if (currentJourney < 0) currentJourney = journey.length - 1;
    const journeyMarkup = `<div class="journey" aria-label="Candidate journey">${journey.map(([label, done], index) => `<span class="journey-step ${done ? "done" : ""} ${index === currentJourney ? "current" : ""}">${escapeHtml(label)}</span>`).join("")}</div>`;
    const slotOptions = (candidate.available_slots || []).map((slot) => `<option value="${escapeHtml(slot.label)}" ${candidate.chosen_slot === slot.label ? "selected" : ""}>${escapeHtml(slot.label)}</option>`).join("");
    const criterionCards = criteria.map((item) => {
      const answer = item.answer;
      const verdict = answer?.verdict || "unknown";
      const icon = verdict === "met" ? "✓" : verdict === "not_met" ? "×" : "?";
      const verdictLabel = verdict === "met" ? "Satisfied" : verdict === "not_met" ? "Not satisfied" : "Unclear";
      const quote = answer?.evidence_quote ? `<blockquote><mark>${escapeHtml(answer.evidence_quote)}</mark></blockquote>` : '<p class="detail-placeholder">No quoted evidence recorded.</p>';
      const note = verdict === "unknown" ? `<p class="verifier-note">${escapeHtml(answer?.note || "Coordinator review needed")}</p>` : "";
      const clinic = item.requires_clinic_check ? '<span class="clinic-badge">Checked at clinic visit</span>' : "";
      return `<article class="review-criterion"><div class="review-criterion-head"><span class="verdict-icon verdict-${verdict}">${icon}</span><div><strong>${escapeHtml(item.id)} · ${escapeHtml(verdictLabel)}</strong><p>${escapeHtml(item.requirement)}</p></div></div>${quote}${note}${clinic}</article>`;
    }).join("");
    const transcript = (candidate.transcript || []).map((message) => `<p class="transcript-message transcript-${escapeHtml(message.role)}"><b>${message.role === "user" ? escapeHtml(candidate.display_name) : "Eligibl"}</b><span>${escapeHtml(message.content)}</span></p>`).join("");
    const displayStatus = candidate.decision_label;
    content.innerHTML = `<div class="detail-person"><span class="candidate-avatar large">${escapeHtml(initials)}</span><div><h2>${escapeHtml(candidate.display_name)}</h2><span class="status-pill status-${escapeHtml(displayStatus.toLowerCase().replaceAll(" ", "-"))}"><span aria-hidden="true">${statusIcons[displayStatus] || "◷"}</span> ${escapeHtml(displayStatus)}</span></div></div>
      <p class="detail-meta">${candidate.criteria_met} of ${candidate.criteria_total} criteria met · ${candidate.total_tokens} tokens · $${Number(candidate.total_cost).toFixed(5)}</p>
      ${journeyMarkup}
      ${candidate.override_reason ? `<p class="override-note">Coordinator override: ${escapeHtml(candidate.override_reason)}</p>` : ""}
      <div class="detail-tabs" role="tablist"><button class="detail-tab selected" data-panel="review" role="tab" aria-selected="true">Review</button><button class="detail-tab" data-panel="trace" role="tab" aria-selected="false">Trace (${candidate.trace.length})</button></div>
      <section class="detail-tab-content" data-content="review"><h3>Verifier summary</h3><p class="verifier-summary">${escapeHtml(candidate.verifier_summary || "Verification is pending or was not completed; please review the transcript and evidence.")}</p><h3>Criterion review</h3><div class="review-criteria">${criterionCards}</div>
      <details class="transcript-details"><summary>Full transcript (${candidate.transcript.length} messages)</summary><div class="transcript-list">${transcript || "No transcript available."}</div></details>
      ${(candidate.concerns || []).length ? `<section class="concern-box"><h3>Coordinator flags</h3>${candidate.concerns.map((item) => `<p>${escapeHtml(item.reason)}</p>`).join("")}</section>` : ""}
      <div class="action-history"><h3>Coordinator actions</h3>${(candidate.actions || []).map((item) => `<p><strong>${escapeHtml(item.action.replaceAll("_", " "))}</strong> · ${escapeHtml(timeAgo(item.created_at))}${item.reason ? ` · ${escapeHtml(item.reason)}` : ""}</p>`).join("") || '<p class="detail-placeholder">No review actions yet.</p>'}</div>
      <div class="coordinator-actions"><div class="outreach-slot"><label for="chosen-slot">Reminder schedule visit slot</label><select id="chosen-slot"><option value="">Select a sample visit slot…</option>${slotOptions}</select><small>The invitation includes all three proposed slots. Choose the demo slot that anchors the two reminders.</small></div><button class="button" data-action="approve">Approve</button><button class="button secondary" data-action="show-override">Override decision</button><button class="button danger" data-action="mark_not_match">Mark not a match</button><button class="button secondary" data-action="contacted">Mark contacted</button>
      <div class="override-form" hidden><label>Decision<select id="override-decision"><option>Flagged</option><option>Not a match</option><option>Needs review</option><option>Likely eligible</option></select></label><label>Reason<textarea id="override-reason" rows="2" required></textarea></label><button class="button" data-action="override">Save override</button></div><p class="action-error" role="alert"></p></div></section>
      <section class="detail-tab-content" data-content="trace" hidden>${renderTrace(candidate.trace)}</section>`;
  };

  const loadCandidate = async (id) => {
    activeId = id;
    openPanel();
    content.innerHTML = '<p class="detail-placeholder">Loading screening details…</p>';
    try {
      const response = await fetch(`/api/coordinator/candidates/${encodeURIComponent(id)}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not load candidate.");
      renderDetail(data);
    } catch (error) {
      content.innerHTML = `<p class="action-error">${escapeHtml(error.message)}</p>`;
    }
  };
  document.querySelectorAll("#candidate-rows tr[data-id]").forEach((row) => {
    row.addEventListener("click", () => loadCandidate(row.dataset.id));
    row.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); loadCandidate(row.dataset.id); } });
  });
  document.querySelector("#detail-close")?.addEventListener("click", closePanel);
  scrim?.addEventListener("click", closePanel);
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") closePanel(); });

  content.addEventListener("click", async (event) => {
    const tab = event.target.closest(".detail-tab");
    if (tab) {
      content.querySelectorAll(".detail-tab").forEach((node) => { node.classList.toggle("selected", node === tab); node.setAttribute("aria-selected", String(node === tab)); });
      content.querySelectorAll(".detail-tab-content").forEach((node) => { node.hidden = node.dataset.content !== tab.dataset.panel; });
      return;
    }
    const button = event.target.closest("[data-action]");
    if (!button) return;
    if (button.dataset.action === "show-override") { content.querySelector(".override-form").hidden = false; return; }
    const action = button.dataset.action;
    const reason = action === "override" ? content.querySelector("#override-reason").value.trim() : "";
    if (action === "override" && !reason) { content.querySelector(".action-error").textContent = "Please enter a reason for this override."; return; }
    const payload = { action, reason };
    if (action === "approve") {
      payload.chosen_slot = content.querySelector("#chosen-slot").value;
      if (!payload.chosen_slot) { content.querySelector(".action-error").textContent = "Choose a proposed visit slot to schedule the reminder drafts."; return; }
    }
    if (action === "override") payload.decision = content.querySelector("#override-decision").value;
    button.disabled = true;
    try {
      const response = await fetch(`/api/coordinator/candidates/${encodeURIComponent(activeId)}/actions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Action could not be saved.");
      if (action === "approve") {
        const toast = document.querySelector("#approval-toast");
        if (toast) { toast.hidden = false; window.setTimeout(() => window.location.reload(), 850); }
        else window.location.reload();
      } else window.location.reload();
    } catch (error) {
      content.querySelector(".action-error").textContent = error.message;
      button.disabled = false;
    }
  });

  const applyFilters = () => {
    const query = (document.querySelector("#candidate-search")?.value || "").trim().toLowerCase();
    const status = document.querySelector("#status-filter")?.value || "";
    const sort = document.querySelector("#sort-filter")?.value || "recent";
    const body = document.querySelector("#candidate-rows");
    const rows = [...body.querySelectorAll("tr[data-id]")];
    rows.forEach((row) => { row.hidden = !(row.dataset.name.includes(query) && (!status || row.dataset.status === status)); });
    rows.sort((a, b) => sort === "name" ? a.dataset.name.localeCompare(b.dataset.name) : sort === "decision" ? a.dataset.status.localeCompare(b.dataset.status) : new Date(b.dataset.created) - new Date(a.dataset.created));
    rows.forEach((row) => body.append(row));
  };
  ["#candidate-search", "#status-filter", "#sort-filter"].forEach((selector) => document.querySelector(selector)?.addEventListener("input", applyFilters));
})();
