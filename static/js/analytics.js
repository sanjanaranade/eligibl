"use strict";

(() => {
  const dataNode = document.querySelector("#analytics-data");
  if (!dataNode) return;
  const stats = JSON.parse(dataNode.textContent);
  const pink = "#ed75bd";
  const chartOptions = {
    responsive: true,
    plugins: { legend: { display: false } },
    scales: {
      x: { beginAtZero: true, ticks: { color: "#cbbdcb", precision: 0 }, grid: { color: "#342936" } },
      y: { ticks: { color: "#eadfea" }, grid: { display: false } },
    },
  };
  const renderChart = (canvasId, table, labels, values, label, horizontal = false) => {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !window.Chart) return;
    try {
      new window.Chart(canvas, {
        type: horizontal ? "bar" : "bar",
        data: { labels, datasets: [{ label, data: values, backgroundColor: pink, borderRadius: 5 }] },
        options: { ...chartOptions, indexAxis: horizontal ? "y" : "x" },
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
  );
  const failureTable = document.querySelector("#failures-chart")?.nextElementSibling;
  if (stats.why_not_a_match.length) {
    renderChart("failures-chart", failureTable, stats.why_not_a_match.map((row) => row.label), stats.why_not_a_match.map((row) => row.count), "Not satisfied", true);
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
