"use strict";

(() => {
  const dataNode = document.querySelector("#analytics-data");
  if (!dataNode) return;
  const stats = JSON.parse(dataNode.textContent);
  const shortCriterionLabels = {
    C1: "Age",
    C2: "Sleep symptoms",
    C3: "BMI",
    C4: "Sleep treatment",
    C5: "Study procedures",
    C6: "Health conditions",
    C7: "Sleep apnea / CPAP",
    C8: "Night shift",
    C9: "Sleep-affecting meds",
    C10: "Drug use",
    C11: "Pregnancy / breastfeeding",
    C12: "Uncontrolled conditions",
  };
  const chartOptions = {
    responsive: true,
    plugins: { legend: { display: false } },
    scales: {
      x: { beginAtZero: true, ticks: { color: "#514B46", precision: 0, font: { size: 12, weight: 600 } }, grid: { color: "#E7E5E4" } },
      y: { ticks: { color: "#514B46", font: { size: 12, weight: 600 } }, grid: { color: "#E7E5E4" } },
    },
  };
  const renderChart = (canvasId, table, labels, values, label, color, horizontal = false) => {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !window.Chart) return;
    try {
      const scales = {
        x: { ...chartOptions.scales.x, ticks: { ...chartOptions.scales.x.ticks } },
        y: { ...chartOptions.scales.y, ticks: { ...chartOptions.scales.y.ticks } },
      };
      if (horizontal) scales.y.ticks.font = { size: 9, weight: 600 };
      new window.Chart(canvas, {
        type: horizontal ? "bar" : "bar",
        data: { labels, datasets: [{ label, data: values, backgroundColor: color, borderRadius: 5 }] },
        options: { ...chartOptions, scales, indexAxis: horizontal ? "y" : "x" },
      });
      table.hidden = true;
    } catch (_error) {
      // The readable table remains the fallback if a browser cannot render Chart.js.
    }
  };
  renderChart(
    "funnel-chart",
    document.querySelector("#funnel-chart")?.nextElementSibling,
    stats.funnel.map((row) => `${row.stage} · ${row.conversion_percent}%`),
    stats.funnel.map((row) => row.count),
    "Candidates",
    "#0F5F5C",
  );
  const failureTable = document.querySelector("#failures-chart")?.nextElementSibling;
  if (stats.why_not_a_match.length) {
    renderChart("failures-chart", failureTable, stats.why_not_a_match.map((row) => shortCriterionLabels[row.criterion_id] || row.label), stats.why_not_a_match.map((row) => row.count), "Not satisfied", "#B85C16", true);
  }

  const button = document.querySelector("#weekly-insights");
  const feedback = document.querySelector("#insights-feedback");
  const summary = document.querySelector("#weekly-summary");
  button?.addEventListener("click", async () => {
    button.disabled = true;
    feedback.textContent = "Preparing an aggregate-only weekly summary…";
    summary.hidden = true;
    try {
      const response = await fetch("/api/coordinator/insights/weekly", { method: "POST" });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Could not generate the weekly summary.");
      summary.textContent = result.summary;
      summary.hidden = false;
      feedback.textContent = `Generated with ${result.usage.input + result.usage.output} tokens.`;
    } catch (error) {
      feedback.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });
})();
