const summaryGrid = document.getElementById("summary-grid");
const recordsBody = document.getElementById("records-body");
const updatedAt = document.getElementById("updated-at");
const searchInput = document.getElementById("search-input");
const emptyState = document.getElementById("empty-state");
const failuresPanel = document.getElementById("failures-panel");
const failuresList = document.getElementById("failures-list");

let allRecords = [];

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

function renderSummary(summary) {
  const cards = [
    ["推荐总数", summary.total_picks],
    ["当前盈利数", summary.profitable_picks],
    ["当前胜率", formatPercent(summary.win_rate)],
    ["平均收益率", formatPercent(summary.average_return)],
    ["平均 5 日收益", formatPercent(summary.average_return_5d)],
    ["平均 20 日收益", formatPercent(summary.average_return_20d)],
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

      return `
        <tr>
          <td>
            <div class="stock-cell">
              <span class="stock-symbol">${record.symbol}</span>
              <span class="stock-name">${record.name || "--"}</span>
            </div>
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

function renderFailures(failures) {
  if (!failures.length) {
    failuresPanel.classList.add("hidden");
    failuresList.innerHTML = "";
    return;
  }

  failuresPanel.classList.remove("hidden");
  failuresList.innerHTML = failures
    .map(
      (failure) => `
        <article class="failure-item">
          <p class="failure-title">${failure.symbol} ${failure.name ? `· ${failure.name}` : ""}</p>
          <p class="failure-detail">推荐日期：${failure.recommend_date}</p>
          <p class="failure-detail">失败原因：${failure.error}</p>
        </article>
      `,
    )
    .join("");
}

function applyFilter() {
  const keyword = searchInput.value.trim().toLowerCase();
  if (!keyword) {
    renderTable(allRecords);
    return;
  }

  const filtered = allRecords.filter((record) => {
    return (
      record.symbol.toLowerCase().includes(keyword) ||
      (record.name || "").toLowerCase().includes(keyword)
    );
  });

  renderTable(filtered);
}

async function loadData() {
  const response = await fetch("./data/metrics.json", { cache: "no-store" });

  if (!response.ok) {
    throw new Error(`加载失败: ${response.status}`);
  }

  const data = await response.json();
  allRecords = data.records || [];
  renderSummary(data.summary || {});
  renderTable(allRecords);
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
