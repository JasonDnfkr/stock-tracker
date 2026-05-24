const summaryGrid = document.getElementById("summary-grid");
const recordsBody = document.getElementById("records-body");
const summaryBody = document.getElementById("summary-body");
const updatedAt = document.getElementById("updated-at");
const searchInput = document.getElementById("search-input");
const emptyState = document.getElementById("empty-state");
const summaryEmptyState = document.getElementById("summary-empty-state");
const failuresPanel = document.getElementById("failures-panel");
const failuresList = document.getElementById("failures-list");

let allRecords = [];
let allStockSummaries = [];

const percent = new Intl.NumberFormat("zh-CN", {
  style: "percent",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const signedPercent = new Intl.NumberFormat("zh-CN", {
  style: "percent",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  signDisplay: "exceptZero",
});

const number = new Intl.NumberFormat("zh-CN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function formatPercent(value) {
  if (value === null || value === undefined) {
    return "--";
  }

  return percent.format(value);
}

function formatSignedPercent(value) {
  if (value === null || value === undefined) {
    return "--";
  }

  return signedPercent.format(value);
}

function formatNumber(value) {
  if (value === null || value === undefined) {
    return "--";
  }

  return number.format(value);
}

function metricClass(value) {
  if (value === null || value === undefined) {
    return "neutral-text";
  }
  if (value > 0) {
    return "profit-text";
  }
  if (value < 0) {
    return "loss-text";
  }
  return "neutral-text";
}

function groupAccent(symbol) {
  let hash = 0;
  for (const char of symbol) {
    hash = (hash * 31 + char.charCodeAt(0)) % 360;
  }
  return `hsl(${hash} 70% 45%)`;
}

function winRateClass(value) {
  if (value === null || value === undefined) {
    return "neutral-text";
  }
  if (value > 0.5) {
    return "profit-text";
  }
  if (value < 0.5) {
    return "loss-text";
  }
  return "neutral-text";
}

function renderSummary(summary) {
  const cards = [
    ["推荐总数", summary.total_picks],
    ["覆盖股票数", summary.unique_symbols],
    ["当前盈利数", summary.profitable_picks],
    ["当前胜率", formatPercent(summary.win_rate)],
    ["平均收益率", formatSignedPercent(summary.average_return)],
    ["平均 5 日收益", formatSignedPercent(summary.average_return_5d)],
  ];

  summaryGrid.innerHTML = cards
    .map(
      ([label, value]) => `
        <article class="metric-card">
          <p class="metric-label">${label}</p>
          <p class="metric-value">${value ?? "--"}</p>
        </article>
      `,
    )
    .join("");
}

function renderTable(records) {
  if (!records.length) {
    recordsBody.innerHTML = "";
    emptyState.classList.remove("hidden");
    return;
  }

  emptyState.classList.add("hidden");

  recordsBody.innerHTML = records
    .map((record) => {
      const profitClass = record.is_profitable ? "profit" : "loss";
      const profitLabel = record.is_profitable ? "盈利" : "亏损";
      const hasRepeat = record.recommendation_count_for_symbol > 1;
      const rowClass = hasRepeat ? "event-row repeat-group" : "event-row";
      const rowStyle = hasRepeat ? `style="--group-accent: ${groupAccent(record.symbol)}"` : "";

      return `
        <tr class="${rowClass}" ${rowStyle}>
          <td class="id-cell">${record.id}</td>
          <td>
            <div class="stock-cell">
              <span class="stock-symbol">${record.symbol}</span>
              <div class="stock-meta">
                <span class="stock-name">${record.name || "--"}</span>
                ${
                  hasRepeat
                    ? `<span class="repeat-badge">共 ${record.recommendation_count_for_symbol} 次</span>`
                    : ""
                }
              </div>
            </div>
          </td>
          <td>
            <span class="sequence-badge">第 ${record.recommendation_sequence} 次</span>
          </td>
          <td>${record.recommend_date}</td>
          <td>
            <div class="price-cell">
              <span>${formatNumber(record.entry_price)}</span>
              ${
                record.entry_date && record.entry_date !== record.recommend_date
                  ? `<span class="cell-note">顺延到 ${record.entry_date}</span>`
                  : ""
              }
            </div>
          </td>
          <td>${formatNumber(record.current_price)}</td>
          <td class="${metricClass(record.return_rate)}">${formatSignedPercent(record.return_rate)}</td>
          <td class="${metricClass(record.return_5d)}">${formatSignedPercent(record.return_5d)}</td>
          <td class="${metricClass(record.return_20d)}">${formatSignedPercent(record.return_20d)}</td>
          <td class="${metricClass(record.max_gain)}">${formatSignedPercent(record.max_gain)}</td>
          <td class="${metricClass(record.max_drawdown)}">${formatSignedPercent(record.max_drawdown)}</td>
          <td><span class="pill ${profitClass}">${profitLabel}</span></td>
        </tr>
      `;
    })
    .join("");
}

function renderStockSummaries(summaries) {
  if (!summaries.length) {
    summaryBody.innerHTML = "";
    summaryEmptyState.classList.remove("hidden");
    return;
  }

  summaryEmptyState.classList.add("hidden");
  summaryBody.innerHTML = summaries
    .map(
      (item) => `
        <tr>
          <td>
            <div class="stock-cell">
              <span class="stock-symbol">${item.symbol}</span>
              <span class="stock-name">${item.name || "--"}</span>
            </div>
          </td>
          <td>${item.recommendation_count}</td>
          <td>${item.profitable_count}</td>
          <td class="${winRateClass(item.win_rate)}">${formatPercent(item.win_rate)}</td>
          <td class="${metricClass(item.average_return)}">${formatSignedPercent(item.average_return)}</td>
          <td class="${metricClass(item.latest_return)}">${formatSignedPercent(item.latest_return)}</td>
          <td>${item.first_recommend_date}</td>
          <td>${item.latest_recommend_date}</td>
        </tr>
      `,
    )
    .join("");
}

function renderFailures(failures) {
  if (!failures.length) {
    failuresPanel.classList.add("hidden");
    failuresList.innerHTML = "";
    return;
  }

  failuresPanel.classList.remove("hidden");
  failuresList.innerHTML = failures
    .map((failure) => {
      const title = [failure.symbol || "未填写代码", failure.name || ""]
        .filter(Boolean)
        .join(" · ");

      return `
        <article class="failure-item">
          <p class="failure-title">${title}</p>
          <p class="failure-detail">事件 ID：${failure.id || "--"}</p>
          <p class="failure-detail">推荐日期：${failure.recommend_date}</p>
          <p class="failure-detail">失败原因：${failure.error}</p>
        </article>
      `;
    })
    .join("");
}

function applyFilter() {
  const keyword = searchInput.value.trim().toLowerCase();
  if (!keyword) {
    renderTable(allRecords);
    renderStockSummaries(allStockSummaries);
    return;
  }

  const filtered = allRecords.filter((record) => {
    return (
      record.symbol.toLowerCase().includes(keyword) ||
      (record.name || "").toLowerCase().includes(keyword)
    );
  });

  const filteredSummaries = allStockSummaries.filter((item) => {
    return (
      item.symbol.toLowerCase().includes(keyword) ||
      (item.name || "").toLowerCase().includes(keyword)
    );
  });

  renderTable(filtered);
  renderStockSummaries(filteredSummaries);
}

async function loadData() {
  const response = await fetch("./data/metrics.json", { cache: "no-store" });

  if (!response.ok) {
    throw new Error(`加载失败: ${response.status}`);
  }

  const data = await response.json();
  allRecords = data.records || [];
  allStockSummaries = data.stock_summaries || [];
  renderSummary(data.summary || {});
  renderTable(allRecords);
  renderStockSummaries(allStockSummaries);
  renderFailures(data.failures || []);
  updatedAt.textContent = `最近更新：${data.generated_at || "--"}`;
}

searchInput.addEventListener("input", applyFilter);

loadData().catch((error) => {
  updatedAt.textContent = "数据加载失败";
  summaryGrid.innerHTML = `
    <article class="metric-card">
      <p class="metric-label">错误</p>
      <p class="metric-value">无法读取 metrics.json</p>
      <p class="metric-label">${error.message}</p>
    </article>
  `;
});
