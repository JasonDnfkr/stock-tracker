const summaryGrid = document.getElementById("summary-grid");
const recordsBody = document.getElementById("records-body");
const stockGroupList = document.getElementById("stock-group-list");
const updatedAt = document.getElementById("updated-at");
const searchInput = document.getElementById("search-input");
const emptyState = document.getElementById("empty-state");
const groupedEmptyState = document.getElementById("grouped-empty-state");
const failuresPanel = document.getElementById("failures-panel");
const failuresList = document.getElementById("failures-list");
const groupedView = document.getElementById("grouped-view");
const eventView = document.getElementById("event-view");
const groupedViewBtn = document.getElementById("grouped-view-btn");
const eventViewBtn = document.getElementById("event-view-btn");

let allRecords = [];
let allStockSummaries = [];
let currentView = "grouped";

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

function renderGroupedView(summaries, records) {
  if (!summaries.length) {
    stockGroupList.innerHTML = "";
    groupedEmptyState.classList.remove("hidden");
    return;
  }

  groupedEmptyState.classList.add("hidden");
  const recordsBySymbol = stockSummaryMap(records);

  stockGroupList.innerHTML = summaries
    .map((summary) => {
      const groupColor = groupAccent(summary.symbol);
      const events = recordsBySymbol.get(summary.symbol) || [];
      const shouldOpen = summary.recommendation_count > 1;

      const eventRows = events
        .map((record) => {
          const profitClass = record.is_profitable ? "profit" : "loss";
          const profitLabel = record.is_profitable ? "盈利" : "亏损";

          return `
            <tr>
              <td><span class="sequence-badge" title="事件 ID：${record.id}">第 ${record.recommendation_sequence} 次</span></td>
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

      return `
        <details class="stock-group-card" style="--group-accent: ${groupColor}" ${shouldOpen ? "open" : ""}>
          <summary class="stock-group-summary">
            <div class="group-main">
              <div class="group-title">
                <span class="group-symbol">${summary.symbol}</span>
                <span class="group-name">${summary.name || "--"}</span>
                <span class="repeat-badge">共 ${summary.recommendation_count} 次</span>
              </div>
              <div class="group-subtitle">
                <span>首次推荐 ${summary.first_recommend_date}</span>
                <span>最近推荐 ${summary.latest_recommend_date}</span>
              </div>
            </div>
            <div class="group-metrics">
              <div class="group-metric">
                <span class="group-metric-label">盈利次数</span>
                <span class="group-metric-value">${summary.profitable_count}/${summary.recommendation_count}</span>
              </div>
              <div class="group-metric">
                <span class="group-metric-label">胜率</span>
                <span class="group-metric-value ${winRateClass(summary.win_rate)}">${formatPercent(summary.win_rate)}</span>
              </div>
              <div class="group-metric">
                <span class="group-metric-label">平均收益</span>
                <span class="group-metric-value ${metricClass(summary.average_return)}">${formatSignedPercent(summary.average_return)}</span>
              </div>
              <div class="group-metric">
                <span class="group-metric-label">最近一次</span>
                <span class="group-metric-value ${metricClass(summary.latest_return)}">${formatSignedPercent(summary.latest_return)}</span>
              </div>
            </div>
          </summary>
          <div class="group-detail">
            <div class="detail-note">展开后按时间线查看该股票的全部推荐事件，鼠标悬浮“第几次推荐”徽标可查看事件 ID。</div>
            <div class="table-wrap">
              <table class="nested-table">
                <thead>
                  <tr>
                    <th>推荐次序</th>
                    <th>推荐日期</th>
                    <th>当天价格</th>
                    <th>当前价</th>
                    <th>收益率</th>
                    <th>5日收益</th>
                    <th>20日收益</th>
                    <th>最大涨幅</th>
                    <th>最大回撤</th>
                    <th>是否盈利</th>
                  </tr>
                </thead>
                <tbody>${eventRows}</tbody>
              </table>
            </div>
          </div>
        </details>
      `;
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
      const hasRepeat = record.recommendation_count_for_symbol > 1;
      const rowClass = hasRepeat ? "event-row repeat-group" : "event-row";
      const rowStyle = hasRepeat ? `style="--group-accent: ${groupAccent(record.symbol)}"` : "";

      return `
        <tr class="${rowClass}" ${rowStyle}>
          <td>
            <div class="stock-cell">
              <span class="stock-symbol">${record.symbol}</span>
              <div class="stock-meta">
                <span class="stock-name" title="事件 ID：${record.id}">${record.name || "--"}</span>
                ${
                  hasRepeat
                    ? `<span class="repeat-badge">共 ${record.recommendation_count_for_symbol} 次</span>`
                    : ""
                }
              </div>
            </div>
          </td>
          <td>
            <span class="sequence-badge" title="事件 ID：${record.id}">第 ${record.recommendation_sequence} 次</span>
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

function sortGroupedSummaries(summaries) {
  return [...summaries].sort((a, b) => {
    if (b.recommendation_count !== a.recommendation_count) {
      return b.recommendation_count - a.recommendation_count;
    }
    if (b.latest_recommend_date !== a.latest_recommend_date) {
      return b.latest_recommend_date.localeCompare(a.latest_recommend_date);
    }
    return a.symbol.localeCompare(b.symbol);
  });
}

function syncViewButtons() {
  groupedView.classList.toggle("hidden", currentView !== "grouped");
  eventView.classList.toggle("hidden", currentView !== "event");
  groupedViewBtn.classList.toggle("active", currentView === "grouped");
  eventViewBtn.classList.toggle("active", currentView === "event");
}

function renderFilteredViews(records, summaries) {
  renderTable(records);
  renderGroupedView(sortGroupedSummaries(summaries), records);
  syncViewButtons();
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
    renderFilteredViews(allRecords, allStockSummaries);
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

  renderFilteredViews(filtered, filteredSummaries);
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
  renderFilteredViews(allRecords, allStockSummaries);
  renderFailures(data.failures || []);
  updatedAt.textContent = `最近更新：${data.generated_at || "--"}`;
}

searchInput.addEventListener("input", applyFilter);
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
