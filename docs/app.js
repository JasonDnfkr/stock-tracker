const summaryGrid = document.getElementById("summary-grid");
const recordsBody = document.getElementById("records-body");
const stockGroupList = document.getElementById("stock-group-list");
const updatedAt = document.getElementById("updated-at");
const searchInput = document.getElementById("search-input");
const emptyState = document.getElementById("empty-state");
const groupedEmptyState = document.getElementById("grouped-empty-state");
const pendingPanel = document.getElementById("pending-panel");
const pendingList = document.getElementById("pending-list");
const failuresPanel = document.getElementById("failures-panel");
const failuresList = document.getElementById("failures-list");
const groupedView = document.getElementById("grouped-view");
const eventView = document.getElementById("event-view");
const groupedViewBtn = document.getElementById("grouped-view-btn");
const eventViewBtn = document.getElementById("event-view-btn");

let allRecords = [];
let currentView = "grouped";
const expandedGroups = new Set();

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

function renderMetricWithPrice(rate, price) {
  const toneClass = metricClass(rate);
  return `
    <div class="price-cell">
      <span class="${toneClass}">${formatSignedPercent(rate)}</span>
      ${price === null || price === undefined ? "" : `<span class="cell-note ${toneClass}">${formatNumber(price)}</span>`}
    </div>
  `;
}

function renderPriceWithMetric(price, rate) {
  const toneClass = metricClass(rate);
  return `
    <div class="price-cell">
      <span class="${toneClass}">${formatNumber(price)}</span>
      <span class="cell-note ${toneClass}">${formatSignedPercent(rate)}</span>
    </div>
  `;
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

function renderSummary(summary) {
  const cards = [
    ["推荐总数", summary.total_picks, ""],
    ["覆盖股票数", summary.unique_symbols, ""],
    ["当前盈利数", summary.profitable_picks, ""],
    ["当前胜率", formatPercent(summary.win_rate), ""],
    ["平均收益率", formatSignedPercent(summary.average_return), metricClass(summary.average_return)],
    ["平均 5 日收益", formatSignedPercent(summary.average_return_5d), metricClass(summary.average_return_5d)],
  ];

  summaryGrid.innerHTML = cards
    .map(
      ([label, value, valueClass]) => `
        <article class="metric-card">
          <p class="metric-label">${label}</p>
          <p class="metric-value ${valueClass}">${value ?? "--"}</p>
        </article>
      `,
    )
    .join("");
}

function stockSummaryMap(records) {
  const grouped = new Map();
  for (const record of records) {
    if (!grouped.has(record.symbol)) {
      grouped.set(record.symbol, []);
    }
    grouped.get(record.symbol).push(record);
  }

  for (const symbolRecords of grouped.values()) {
    symbolRecords.sort((a, b) => {
      if (a.recommendation_sequence !== b.recommendation_sequence) {
        return a.recommendation_sequence - b.recommendation_sequence;
      }
      return a.recommend_date.localeCompare(b.recommend_date);
    });
  }

  return grouped;
}

function buildGroupedStocks(records) {
  const grouped = stockSummaryMap(records);
  const groups = [];

  for (const [symbol, symbolRecords] of grouped.entries()) {
    const latestRecord = [...symbolRecords].sort((a, b) => b.recommend_date.localeCompare(a.recommend_date))[0];
    groups.push({
      symbol,
      name: latestRecord?.name || "--",
      records: symbolRecords,
      recommendation_count: symbolRecords.length,
      latest_recommend_date: latestRecord?.recommend_date || "",
    });
  }

  groups.sort((a, b) => {
    if (b.recommendation_count !== a.recommendation_count) {
      return b.recommendation_count - a.recommendation_count;
    }
    if (b.latest_recommend_date !== a.latest_recommend_date) {
      return b.latest_recommend_date.localeCompare(a.latest_recommend_date);
    }
    return a.symbol.localeCompare(b.symbol);
  });

  return groups;
}

function renderGroupedView(records) {
  const groups = buildGroupedStocks(records);

  if (!groups.length) {
    stockGroupList.innerHTML = "";
    groupedEmptyState.classList.remove("hidden");
    return;
  }

  groupedEmptyState.classList.add("hidden");

  stockGroupList.innerHTML = groups
    .map((group) => {
      const events = group.records;

      const eventRows = events
        .map((record, index) => {
          const profitClass = record.is_profitable ? "profit" : "loss";
          const profitLabel = record.is_profitable ? "盈利" : "亏损";
          const isGroupStart = index === 0;
          const isExpanded = expandedGroups.has(group.symbol);
          const rowStateClass = isGroupStart
            ? "group-start-row"
            : isExpanded
              ? "group-follow-row"
              : "group-follow-row hidden";
          const stockCell = isGroupStart
            ? `
                <div class="stock-cell compact">
                  <span class="stock-symbol">${record.symbol}</span>
                  <span class="stock-name" title="事件 ID：${record.id}">${record.name || "--"}</span>
                  ${
                    group.recommendation_count > 1
                      ? `
                        <button
                          class="group-toggle-btn"
                          type="button"
                          data-group-symbol="${group.symbol}"
                          aria-expanded="${isExpanded ? "true" : "false"}"
                        >
                          ${isExpanded ? "收起" : `展开其余 ${group.recommendation_count - 1} 条`}
                        </button>
                      `
                      : ""
                  }
                </div>
              `
            : `<span class="group-placeholder"></span>`;

          return `
            <tr class="group-event-row ${rowStateClass}">
              <td>${stockCell}</td>
              <td title="事件 ID：${record.id}">${record.recommend_date}</td>
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
              <td>${renderPriceWithMetric(record.current_price, record.return_rate)}</td>
              <td>${renderMetricWithPrice(record.return_5d, record.return_5d_price)}</td>
              <td>${renderMetricWithPrice(record.return_20d, record.return_20d_price)}</td>
              <td>${renderMetricWithPrice(record.max_gain, record.max_gain_price)}</td>
              <td>${renderMetricWithPrice(record.max_drawdown, record.max_drawdown_price)}</td>
              <td><span class="pill ${profitClass}">${profitLabel}</span></td>
            </tr>
          `;
        })
        .join("");

      return eventRows;
    })
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

      return `
        <tr class="event-row">
          <td>
            <div class="stock-cell">
              <span class="stock-symbol">${record.symbol}</span>
              <div class="stock-meta">
                <span class="stock-name" title="事件 ID：${record.id}">${record.name || "--"}</span>
                ${
                  record.recommendation_count_for_symbol > 1
                    ? `<span class="repeat-badge">共 ${record.recommendation_count_for_symbol} 次</span>`
                    : ""
                }
              </div>
            </div>
          </td>
          <td title="事件 ID：${record.id}">${record.recommend_date}</td>
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
          <td>${renderPriceWithMetric(record.current_price, record.return_rate)}</td>
          <td>${renderMetricWithPrice(record.return_5d, record.return_5d_price)}</td>
          <td>${renderMetricWithPrice(record.return_20d, record.return_20d_price)}</td>
          <td>${renderMetricWithPrice(record.max_gain, record.max_gain_price)}</td>
          <td>${renderMetricWithPrice(record.max_drawdown, record.max_drawdown_price)}</td>
          <td><span class="pill ${profitClass}">${profitLabel}</span></td>
        </tr>
      `;
    })
    .join("");
}

function syncViewButtons() {
  groupedView.classList.toggle("hidden", currentView !== "grouped");
  eventView.classList.toggle("hidden", currentView !== "event");
  groupedViewBtn.classList.toggle("active", currentView === "grouped");
  eventViewBtn.classList.toggle("active", currentView === "event");
}

function renderFilteredViews(records) {
  renderTable(records);
  renderGroupedView(records);
  syncViewButtons();
}

function toggleGroup(symbol) {
  if (expandedGroups.has(symbol)) {
    expandedGroups.delete(symbol);
  } else {
    expandedGroups.add(symbol);
  }
  applyFilter();
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

function renderPendingRecords(records) {
  if (!records.length) {
    pendingPanel.classList.add("hidden");
    pendingList.innerHTML = "";
    return;
  }

  pendingPanel.classList.remove("hidden");
  pendingList.innerHTML = records
    .map((record) => {
      const title = [record.symbol || "未填写代码", record.name || ""]
        .filter(Boolean)
        .join(" · ");

      return `
        <article class="pending-item">
          <p class="failure-title">${title}</p>
          <p class="failure-detail">事件 ID：${record.id || "--"}</p>
          <p class="failure-detail">推荐日期：${record.recommend_date}</p>
          <p class="failure-detail">当前状态：${record.message}</p>
        </article>
      `;
    })
    .join("");
}

function applyFilter() {
  const keyword = searchInput.value.trim().toLowerCase();
  if (!keyword) {
    renderFilteredViews(allRecords);
    return;
  }

  const filtered = allRecords.filter((record) => {
    return (
      record.symbol.toLowerCase().includes(keyword) ||
      (record.name || "").toLowerCase().includes(keyword)
    );
  });

  renderFilteredViews(filtered);
}

async function loadData() {
  const response = await fetch("./data/metrics.json", { cache: "no-store" });

  if (!response.ok) {
    throw new Error(`加载失败: ${response.status}`);
  }

  const data = await response.json();
  allRecords = data.records || [];
  renderSummary(data.summary || {});
  renderFilteredViews(allRecords);
  renderPendingRecords(data.pending_records || []);
  renderFailures(data.failures || []);
  updatedAt.textContent = `最近更新：${data.generated_at || "--"}`;
}

searchInput.addEventListener("input", applyFilter);
stockGroupList.addEventListener("click", (event) => {
  const button = event.target.closest(".group-toggle-btn");
  if (!button) {
    return;
  }
  toggleGroup(button.dataset.groupSymbol || "");
});
groupedViewBtn.addEventListener("click", () => {
  currentView = "grouped";
  syncViewButtons();
});
eventViewBtn.addEventListener("click", () => {
  currentView = "event";
  syncViewButtons();
});

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
