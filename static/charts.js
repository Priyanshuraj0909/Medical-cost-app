/* Charts are visual enhancements; adjacent lists and tables expose the data. */
'use strict';
window.CareCharts = (() => {
  const charts = new Map();
  function destroy(id) { charts.get(id)?.destroy(); charts.delete(id); }
  function bar(id, labels, values, { horizontal = false, signed = false } = {}) {
    destroy(id);
    if (!window.Chart) return;
    const canvas = document.getElementById(id);
    const style = getComputedStyle(document.documentElement);
    const text = style.getPropertyValue('--chart-text').trim() || '#405a4d';
    const grid = style.getPropertyValue('--chart-grid').trim() || '#dce5d8';
    const format = value => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value);
    const moneyAxis = { grid: { color: grid }, ticks: { color: text, callback: format }, beginAtZero: true };
    const categoryAxis = { grid: { display: false }, ticks: { color: text, font: { family: 'system-ui' } } };
    charts.set(id, new Chart(canvas, {
      type: 'bar',
      data: { labels, datasets: [{ data: values, backgroundColor: values.map((v, i) => signed ? v < 0 ? '#ad793b' : '#407553' : i ? '#407553' : '#8298b3'), borderRadius: 6, maxBarThickness: 34 }] },
      options: {
        responsive: true, maintainAspectRatio: false, indexAxis: horizontal ? 'y' : 'x',
        animation: false, locale: 'en-IN',
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: context => format(context.raw) } } },
        scales: horizontal ? { x: moneyAxis, y: categoryAxis } : { x: categoryAxis, y: moneyAxis },
      },
    }));
  }
  return { bar, destroy, clear: () => { for (const id of [...charts.keys()]) destroy(id); } };
})();
