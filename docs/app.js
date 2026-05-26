const summaryGrid = document.getElementById("summary-grid");
const timelineChart = document.getElementById("timeline-chart");
const timelineEmptyState = document.getElementById("timeline-empty-state");
const recordsBody = document.getElementById("records-body");
const stockGroupList = document.getElementById("stock-group-list");
const updatedAt = document.getElementById("updated-at");
const searchInput = document.getElementById("search-input");
const timelineRangeControls = document.getElementById("timeline-range-controls");
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
const chartTooltip = document.createElement("div");

chartTooltip.className = "chart-tooltip hidden";
document.body.append(chartTooltip);

let allRecords = [];
let currentView = "grouped";
let currentTimelineRange = "20d";
const expandedGroups = new Set();
let activeTooltipId = null;
let activeChartLabelId = null;

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

function formatShortDate(dateText) {
  if (!dateText) {
    return "--";
  }

  const [year, month, day] = dateText.split("-");
  if (!year || !month || !day) {
    return dateText;
  }

  return `${month}-${day}`;
}

function formatTooltipDate(dateText) {
  if (!dateText) {
    return "--";
  }

  return dateText;
}

function formatEntryDateLabel(entryDate, recommendDate) {
  if (!entryDate) {
    return "--";
  }

  const shortDate = formatShortDate(entryDate);
  if (recommendDate && entryDate !== recommendDate) {
    return `${shortDate}(顺延)`;
  }

  return shortDate;
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

function renderEntryPrice(price, entryDate, recommendDate) {
  return `
    <div class="price-cell">
      <span>${formatNumber(price)}</span>
      <span class="cell-note" title="${entryDate && recommendDate && entryDate !== recommendDate ? `顺延到 ${entryDate}` : entryDate || ""}">${formatEntryDateLabel(entryDate, recommendDate)}</span>
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

function clamp(value, minValue, maxValue) {
  return Math.min(Math.max(value, minValue), maxValue);
}

function dateToTimestamp(dateText) {
  const time = Date.parse(`${dateText}T00:00:00`);
  return Number.isNaN(time) ? null : time;
}

function buildTickValues(minValue, maxValue, tickCount) {
  if (tickCount <= 1 || minValue === maxValue) {
    return [minValue];
  }

  const step = (maxValue - minValue) / (tickCount - 1);
  return Array.from({ length: tickCount }, (_, index) => minValue + step * index);
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function tooltipMetricText(value) {
  return value === null || value === undefined ? "--" : formatSignedPercent(value);
}

function tooltipMetricClass(value) {
  return metricClass(value);
}

function estimateLabelWidth(text) {
  return Array.from(text).reduce((width, char) => {
    if (/[\u4e00-\u9fff]/u.test(char)) {
      return width + 13;
    }
    return width + 7.5;
  }, 0);
}

function rectsOverlap(a, b) {
  return !(
    a.right < b.left ||
    a.left > b.right ||
    a.bottom < b.top ||
    a.top > b.bottom
  );
}

function rectOverlapsPoint(rect, point, padding = 6) {
  const nearestX = clamp(point.x, rect.left, rect.right);
  const nearestY = clamp(point.y, rect.top, rect.bottom);
  const dx = point.x - nearestX;
  const dy = point.y - nearestY;
  return dx * dx + dy * dy <= padding * padding;
}

function compressReturn(value) {
  const sign = value < 0 ? -1 : 1;
  return sign * Math.sqrt(Math.abs(value));
}

function expandCompressedReturn(value) {
  const sign = value < 0 ? -1 : 1;
  return sign * value * value;
}

function renderSummary(summary) {
  const cards = [
    ["推荐总数", summary.total_picks, ""],
    ["覆盖股票数", summary.unique_symbols, ""],
    ["当前盈利数", summary.profitable_picks, ""],
    ["当前胜率", formatPercent(summary.win_rate), ""],
    ["平均收益率", formatSignedPercent(summary.average_return), metricClass(summary.average_return)],
    ["平均 5 日收益", formatSignedPercent(summary.average_return_5d), metricClass(summary.average_return_5d)],
    ["平均 10 日收益", formatSignedPercent(summary.average_return_10d), metricClass(summary.average_return_10d)],
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

function latestRecommendTimestamp(records) {
  const timestamps = records
    .map((record) => dateToTimestamp(record.recommend_date))
    .filter((value) => value !== null);

  if (!timestamps.length) {
    return null;
  }

  return Math.max(...timestamps);
}

function filterTimelineRecords(records) {
  if (currentTimelineRange === "all") {
    return records;
  }

  const days = Number.parseInt(currentTimelineRange, 10);
  if (Number.isNaN(days)) {
    return records;
  }

  const latestTimestamp = latestRecommendTimestamp(allRecords);
  if (latestTimestamp === null) {
    return records;
  }

  const dayMs = 24 * 60 * 60 * 1000;
  const cutoff = latestTimestamp - (days - 1) * dayMs;

  return records.filter((record) => {
    const timestamp = dateToTimestamp(record.recommend_date);
    return timestamp !== null && timestamp >= cutoff;
  });
}

function syncTimelineRangeButtons() {
  if (!timelineRangeControls) {
    return;
  }

  for (const button of timelineRangeControls.querySelectorAll("[data-range]")) {
    button.classList.toggle("active", button.dataset.range === currentTimelineRange);
  }
}

function renderTimelineChart(records) {
  const scopedRecords = filterTimelineRecords(records);
  const chartRecords = scopedRecords
    .filter((record) => record.return_rate !== null && record.return_rate !== undefined)
    .map((record) => ({
      ...record,
      recommend_timestamp: dateToTimestamp(record.recommend_date),
    }))
    .filter((record) => record.recommend_timestamp !== null)
    .sort((a, b) => {
      if (a.recommend_timestamp !== b.recommend_timestamp) {
        return a.recommend_timestamp - b.recommend_timestamp;
      }
      return a.id.localeCompare(b.id);
    });

  if (!chartRecords.length) {
    timelineChart.innerHTML = "";
    timelineEmptyState.classList.remove("hidden");
    return;
  }

  timelineEmptyState.classList.add("hidden");

  const chartWidth = Math.max(920, chartRecords.length * 64);
  const chartHeight = 320;
  const margin = { top: 20, right: 56, bottom: 42, left: 84 };
  const plotWidth = chartWidth - margin.left - margin.right;
  const plotHeight = chartHeight - margin.top - margin.bottom;

  const xValues = chartRecords.map((record) => record.recommend_timestamp);
  const yValues = chartRecords.map((record) => record.return_rate);
  const rawMinX = Math.min(...xValues);
  const rawMaxX = Math.max(...xValues);
  const singlePointPaddingMs = 24 * 60 * 60 * 1000;
  const xPadding = rawMinX === rawMaxX
    ? singlePointPaddingMs
    : Math.max((rawMaxX - rawMinX) * 0.06, singlePointPaddingMs);
  const minX = rawMinX - xPadding;
  const maxX = rawMaxX + xPadding;
  const rawMinY = Math.min(...yValues, 0);
  const rawMaxY = Math.max(...yValues, 0);
  const compressedMinY = compressReturn(rawMinY);
  const compressedMaxY = compressReturn(rawMaxY);
  const compressedPadding = Math.max((compressedMaxY - compressedMinY) * 0.12, 0.08);
  const minY = compressedMinY - compressedPadding;
  const maxY = compressedMaxY + compressedPadding;
  const averageReturn = yValues.reduce((sum, value) => sum + value, 0) / yValues.length;

  const xScale = (value) => {
    if (minX === maxX) {
      return margin.left + plotWidth / 2;
    }
    return margin.left + ((value - minX) / (maxX - minX)) * plotWidth;
  };

  const yScale = (value) => {
    if (minY === maxY) {
      return margin.top + plotHeight / 2;
    }
    return margin.top + (1 - (compressReturn(value) - minY) / (maxY - minY)) * plotHeight;
  };

  const yScaleFromCompressed = (value) => {
    if (minY === maxY) {
      return margin.top + plotHeight / 2;
    }
    return margin.top + (1 - (value - minY) / (maxY - minY)) * plotHeight;
  };

  const sameDateGroups = new Map();
  for (const record of chartRecords) {
    if (!sameDateGroups.has(record.recommend_date)) {
      sameDateGroups.set(record.recommend_date, []);
    }
    sameDateGroups.get(record.recommend_date).push(record);
  }

  const positionedRecords = chartRecords.map((record) => {
    const sameDateRecords = sameDateGroups.get(record.recommend_date) || [record];
    const sameDateIndex = sameDateRecords.findIndex((item) => item.id === record.id);
    const offsetUnit = sameDateRecords.length > 1 ? (sameDateIndex - (sameDateRecords.length - 1) / 2) * 8 : 0;
    const x = clamp(xScale(record.recommend_timestamp) + offsetUnit, margin.left + 6, chartWidth - margin.right - 6);
    const y = yScale(record.return_rate);
    return { ...record, x, y };
  });

  const yTicks = buildTickValues(minY, maxY, 5);
  const xTickCount = Math.min(8, chartRecords.length);
  const xTicks = buildTickValues(rawMinX, rawMaxX, xTickCount).map((value) => {
    const date = new Date(value);
    const yyyy = date.getUTCFullYear();
    const mm = String(date.getUTCMonth() + 1).padStart(2, "0");
    const dd = String(date.getUTCDate()).padStart(2, "0");
    return { value, label: `${mm}-${dd}`, fullLabel: `${yyyy}-${mm}-${dd}` };
  });

  const zeroY = yScale(0);
  const averageY = yScale(averageReturn);
  const recentPriorityMap = new Map(
    [...chartRecords]
      .sort((a, b) => {
        if (a.recommend_timestamp !== b.recommend_timestamp) {
          return b.recommend_timestamp - a.recommend_timestamp;
        }
        return a.id.localeCompare(b.id);
      })
      .map((record, index) => [record.id, chartRecords.length - index]),
  );

  const pointHitboxes = positionedRecords.map((record) => ({
    id: record.id,
    x: record.x,
    y: record.y,
  }));

  const labelCandidates = positionedRecords.map((record) => {
    const labelText = `${record.name || record.symbol} ${formatSignedPercent(record.return_rate)}`;
    const textWidth = estimateLabelWidth(labelText);
    const labelWidth = textWidth;
    const labelHeight = 14;
    const priority = (recentPriorityMap.get(record.id) || 0) * 1000 + Math.round(Math.abs(record.return_rate) * 100);
    const candidatePositions = [
      { dx: 7, dy: -6 - labelHeight, textAnchor: "start" },
      { dx: 7, dy: 6, textAnchor: "start" },
      { dx: -7 - labelWidth, dy: -6 - labelHeight, textAnchor: "end" },
      { dx: -7 - labelWidth, dy: 6, textAnchor: "end" },
      { dx: -(labelWidth / 2), dy: -10 - labelHeight, textAnchor: "middle" },
      { dx: -(labelWidth / 2), dy: 10, textAnchor: "middle" },
    ];
    const hoverCandidatePositions = [
      { dx: 11, dy: -10 - labelHeight, textAnchor: "start" },
      { dx: 11, dy: 10, textAnchor: "start" },
      { dx: -11 - labelWidth, dy: -10 - labelHeight, textAnchor: "end" },
      { dx: -11 - labelWidth, dy: 10, textAnchor: "end" },
      { dx: -(labelWidth / 2), dy: -14 - labelHeight, textAnchor: "middle" },
      { dx: -(labelWidth / 2), dy: 14, textAnchor: "middle" },
    ];

    const placed = candidatePositions
      .map((position) => {
        const rectX = clamp(
          record.x + position.dx,
          margin.left + 2,
          chartWidth - margin.right - labelWidth - 2,
        );
        const rectY = clamp(
          record.y + position.dy,
          margin.top + 2,
          chartHeight - margin.bottom - labelHeight - 2,
        );
        const rect = {
          left: rectX,
          right: rectX + labelWidth,
          top: rectY,
          bottom: rectY + labelHeight,
        };
        const overlapsPoint = pointHitboxes.some((point) => {
          return rectOverlapsPoint(rect, point, point.id === record.id ? 6 : 7);
        });
        const textX = position.textAnchor === "start"
          ? rectX
          : position.textAnchor === "end"
            ? rectX + labelWidth
            : rectX + labelWidth / 2;

        return {
          rectX,
          rectY,
          rect,
          textX,
          textY: rectY + 10.5,
          textAnchor: position.textAnchor,
          overlapsPoint,
        };
      })
      .find((position) => !position.overlapsPoint)
      || (() => {
        const fallback = candidatePositions[0];
        const rectX = clamp(
          record.x + fallback.dx,
          margin.left + 2,
          chartWidth - margin.right - labelWidth - 2,
        );
        const rectY = clamp(
          record.y + fallback.dy,
          margin.top + 2,
          chartHeight - margin.bottom - labelHeight - 2,
        );
        return {
          rectX,
          rectY,
          rect: {
            left: rectX,
            right: rectX + labelWidth,
            top: rectY,
            bottom: rectY + labelHeight,
          },
          textX: rectX,
          textY: rectY + 10.5,
          textAnchor: "start",
          overlapsPoint: true,
        };
      })();

    const hoverPlaced = hoverCandidatePositions
      .map((position) => {
        const rectX = clamp(
          record.x + position.dx,
          margin.left + 2,
          chartWidth - margin.right - labelWidth - 2,
        );
        const rectY = clamp(
          record.y + position.dy,
          margin.top + 2,
          chartHeight - margin.bottom - labelHeight - 2,
        );
        const rect = {
          left: rectX,
          right: rectX + labelWidth,
          top: rectY,
          bottom: rectY + labelHeight,
        };
        const overlapsOtherPoint = pointHitboxes.some((point) => {
          if (point.id === record.id) {
            return false;
          }
          return rectOverlapsPoint(rect, point, 7);
        });
        const textX = position.textAnchor === "start"
          ? rectX
          : position.textAnchor === "end"
            ? rectX + labelWidth
            : rectX + labelWidth / 2;

        return {
          rectX,
          rectY,
          textX,
          textY: rectY + 10.5,
          textAnchor: position.textAnchor,
          overlapsOtherPoint,
        };
      })
      .find((position) => !position.overlapsOtherPoint)
      || {
        rectX: placed.rectX,
        rectY: placed.rectY,
        textX: placed.textX,
        textY: placed.textY,
        textAnchor: placed.textAnchor,
        overlapsOtherPoint: placed.overlapsPoint,
      };

    return {
      id: record.id,
      labelText,
      labelWidth,
      labelHeight,
      rectX: placed.rectX,
      rectY: placed.rectY,
      rect: placed.rect,
      textX: placed.textX,
      textY: placed.textY,
      textAnchor: placed.textAnchor,
      priority,
      hidden: false,
      overlapsPoint: placed.overlapsPoint,
      hoverRectX: hoverPlaced.rectX,
      hoverRectY: hoverPlaced.rectY,
      hoverTextX: hoverPlaced.textX,
      hoverTextY: hoverPlaced.textY,
      hoverTextAnchor: hoverPlaced.textAnchor,
      hoverSafe: !hoverPlaced.overlapsOtherPoint,
      toneClass: metricClass(record.return_rate),
    };
  });

  const occupiedRects = [];
  const sortedCandidates = [...labelCandidates].sort((a, b) => {
    if (b.priority !== a.priority) {
      return b.priority - a.priority;
    }
    return a.id.localeCompare(b.id);
  });

  for (const candidate of sortedCandidates) {
    const overlapsLabel = occupiedRects.some((rect) => rectsOverlap(candidate.rect, rect));

    if (candidate.overlapsPoint || overlapsLabel) {
      candidate.hidden = true;
      continue;
    }

    occupiedRects.push(candidate.rect);
  }

  const labelMap = new Map(labelCandidates.map((candidate) => [candidate.id, candidate]));

  timelineChart.innerHTML = `
    <div class="chart-meta">
      <div class="chart-legend">
        <span class="legend-item"><span class="legend-dot profit-dot"></span>盈利</span>
        <span class="legend-item"><span class="legend-dot loss-dot"></span>亏损</span>
        <span class="legend-item"><span class="legend-line"></span>平均收益 ${formatSignedPercent(averageReturn)}</span>
      </div>
    </div>
    <div class="chart-scroll">
      <svg class="timeline-svg" viewBox="0 0 ${chartWidth} ${chartHeight}" role="img" aria-label="推荐事件收益时间线散点图">
        <g class="chart-grid">
          ${yTicks
            .map((tickValue) => {
              const y = yScaleFromCompressed(tickValue);
              return `
                <line x1="${margin.left}" y1="${y}" x2="${chartWidth - margin.right}" y2="${y}" class="chart-grid-line" />
                <text x="${margin.left - 12}" y="${y + 4}" text-anchor="end" class="chart-axis-text">${escapeHtml(formatSignedPercent(expandCompressedReturn(tickValue)))}</text>
              `;
            })
            .join("")}
          ${xTicks
            .map((tick) => {
              const x = xScale(tick.value);
              return `
                <line x1="${x}" y1="${margin.top}" x2="${x}" y2="${chartHeight - margin.bottom}" class="chart-grid-line chart-grid-line-vertical" />
                <text x="${x}" y="${chartHeight - margin.bottom + 24}" text-anchor="middle" class="chart-axis-text" title="${tick.fullLabel}">${tick.label}</text>
              `;
            })
            .join("")}
        </g>
        <line x1="${margin.left}" y1="${zeroY}" x2="${chartWidth - margin.right}" y2="${zeroY}" class="chart-zero-line" />
        <line x1="${margin.left}" y1="${averageY}" x2="${chartWidth - margin.right}" y2="${averageY}" class="chart-average-line" />
        ${positionedRecords
          .map((record) => {
            const label = labelMap.get(record.id);
            if (!label) {
              return "";
            }

            return `
              <g
                class="chart-label-group${label.hidden ? " hidden" : ""}"
                data-label-id="${escapeHtml(record.id)}"
                data-overlaps-point="${label.overlapsPoint ? "true" : "false"}"
                data-hover-safe="${label.hoverSafe ? "true" : "false"}"
              >
                <text
                  x="${label.textX}"
                  y="${label.textY}"
                  text-anchor="${label.textAnchor}"
                  data-base-x="${label.textX}"
                  data-base-y="${label.textY}"
                  data-base-anchor="${label.textAnchor}"
                  data-hover-x="${label.hoverTextX}"
                  data-hover-y="${label.hoverTextY}"
                  data-hover-anchor="${label.hoverTextAnchor}"
                  class="chart-label-text ${label.toneClass}"
                >${escapeHtml(label.labelText)}</text>
              </g>
            `;
          })
          .join("")}
        ${positionedRecords
          .map((record) => {
            const pointClass = record.return_rate >= 0 ? "profit-point" : "loss-point";
            const label = labelMap.get(record.id);

            return `
              <circle
                cx="${record.x}"
                cy="${record.y}"
                r="5.5"
                class="chart-point ${pointClass}"
                data-symbol="${escapeHtml(record.symbol)}"
                data-name="${escapeHtml(record.name || "--")}"
                data-recommend-date="${escapeHtml(formatTooltipDate(record.recommend_date))}"
                data-return-rate="${escapeHtml(tooltipMetricText(record.return_rate))}"
                data-return-rate-value="${record.return_rate}"
                data-return-five-day="${escapeHtml(tooltipMetricText(record.return_5d))}"
                data-return-five-day-value="${record.return_5d ?? ""}"
                data-return-ten-day="${escapeHtml(tooltipMetricText(record.return_10d))}"
                data-return-ten-day-value="${record.return_10d ?? ""}"
                data-return-twenty-day="${escapeHtml(tooltipMetricText(record.return_20d))}"
                data-return-twenty-day-value="${record.return_20d ?? ""}"
                data-id="${escapeHtml(record.id)}"
                data-label-id="${escapeHtml(record.id)}"
                data-label-text="${escapeHtml(label?.labelText || "")}"
                data-label-tone-class="${escapeHtml(label?.toneClass || "neutral-text")}"
                data-label-visible="${label && !label.hidden ? "true" : "false"}"
                data-hover-x="${label?.hoverTextX ?? ""}"
                data-hover-y="${label?.hoverTextY ?? ""}"
                data-hover-anchor="${escapeHtml(label?.hoverTextAnchor || "start")}"
              ></circle>
            `;
          })
          .join("")}
        <g id="chart-hover-label-layer" class="chart-hover-label-layer hidden"></g>
      </svg>
    </div>
  `;
}

function hideChartTooltip() {
  chartTooltip.classList.add("hidden");
  activeTooltipId = null;
}

function hideHoverLabelOverlay() {
  const hoverLayer = timelineChart.querySelector("#chart-hover-label-layer");
  if (!hoverLayer) {
    return;
  }
  hoverLayer.innerHTML = "";
  hoverLayer.classList.add("hidden");
}

function showHoverLabelOverlay(point) {
  const hoverLayer = timelineChart.querySelector("#chart-hover-label-layer");
  if (!hoverLayer) {
    return;
  }

  const {
    labelText = "",
    labelToneClass = "neutral-text",
    hoverX = "",
    hoverY = "",
    hoverAnchor = "start",
  } = point.dataset;

  if (!labelText || hoverX === "" || hoverY === "") {
    hideHoverLabelOverlay();
    return;
  }

  hoverLayer.innerHTML = `
    <text
      x="${escapeHtml(hoverX)}"
      y="${escapeHtml(hoverY)}"
      text-anchor="${escapeHtml(hoverAnchor)}"
      class="chart-label-text chart-hover-label-text ${escapeHtml(labelToneClass)}"
    >${escapeHtml(labelText)}</text>
  `;
  hoverLayer.classList.remove("hidden");
}

function setActiveChartLabel(labelId) {
  if (activeChartLabelId === labelId) {
    return;
  }

  if (activeChartLabelId) {
    const prevLabel = timelineChart.querySelector(`[data-label-id="${CSS.escape(activeChartLabelId)}"]`);
    const prevPoint = timelineChart.querySelector(`.chart-point[data-label-id="${CSS.escape(activeChartLabelId)}"]`);
    prevLabel?.classList.remove("active");
    prevPoint?.classList.remove("active");
  }
  hideHoverLabelOverlay();

  activeChartLabelId = labelId;

  if (!labelId) {
    return;
  }

  const nextLabel = timelineChart.querySelector(`[data-label-id="${CSS.escape(labelId)}"]`);
  const nextPoint = timelineChart.querySelector(`.chart-point[data-label-id="${CSS.escape(labelId)}"]`);
  const labelVisible = nextPoint?.dataset.labelVisible === "true";
  if (labelVisible) {
    nextLabel.classList.add("active");
  } else {
    showHoverLabelOverlay(nextPoint);
  }
  nextPoint?.classList.add("active");
}

function positionChartTooltip(event) {
  const offset = 14;
  const tooltipRect = chartTooltip.getBoundingClientRect();
  const roomOnRight = window.innerWidth - event.clientX - offset - 12;
  const roomBelow = window.innerHeight - event.clientY - offset - 12;

  const preferredLeft = roomOnRight >= tooltipRect.width
    ? event.clientX + offset
    : event.clientX - tooltipRect.width - offset;
  const preferredTop = roomBelow >= tooltipRect.height
    ? event.clientY + offset
    : event.clientY - tooltipRect.height - offset;

  const maxLeft = window.innerWidth - tooltipRect.width - 12;
  const maxTop = window.innerHeight - tooltipRect.height - 12;
  const left = clamp(preferredLeft, 12, maxLeft);
  const top = clamp(preferredTop, 12, maxTop);

  chartTooltip.style.left = `${left}px`;
  chartTooltip.style.top = `${top}px`;
}

function renderChartTooltip(target) {
  const {
    symbol = "--",
    name = "--",
    recommendDate = "--",
    returnRate = "--",
    returnFiveDay = "--",
    returnTenDay = "--",
    returnTwentyDay = "--",
    returnRateValue = "",
    returnFiveDayValue = "",
    returnTenDayValue = "",
    returnTwentyDayValue = "",
  } = target.dataset;

  const tooltipKey = `${symbol}-${recommendDate}-${returnRate}`;
  if (activeTooltipId === tooltipKey && !chartTooltip.classList.contains("hidden")) {
    return;
  }

  const parsedReturnRate = returnRateValue === "" ? null : Number(returnRateValue);
  const parsedReturn5d = returnFiveDayValue === "" ? null : Number(returnFiveDayValue);
  const parsedReturn10d = returnTenDayValue === "" ? null : Number(returnTenDayValue);
  const parsedReturn20d = returnTwentyDayValue === "" ? null : Number(returnTwentyDayValue);

  chartTooltip.innerHTML = `
    <div class="chart-tooltip-title">${escapeHtml(symbol)} ${escapeHtml(name)}</div>
    <div class="chart-tooltip-row"><span>推荐日期</span><strong>${escapeHtml(recommendDate)}</strong></div>
    <div class="chart-tooltip-row"><span>当前收益</span><strong class="${tooltipMetricClass(parsedReturnRate)}">${escapeHtml(returnRate)}</strong></div>
    <div class="chart-tooltip-row"><span>5日收益</span><strong class="${tooltipMetricClass(parsedReturn5d)}">${escapeHtml(returnFiveDay)}</strong></div>
    <div class="chart-tooltip-row"><span>10日收益</span><strong class="${tooltipMetricClass(parsedReturn10d)}">${escapeHtml(returnTenDay)}</strong></div>
    <div class="chart-tooltip-row"><span>20日收益</span><strong class="${tooltipMetricClass(parsedReturn20d)}">${escapeHtml(returnTwentyDay)}</strong></div>
  `;
  chartTooltip.classList.remove("hidden");
  activeTooltipId = tooltipKey;
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
          const showSequenceHint = group.recommendation_count > 1 && isExpanded;
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
                          aria-label="${isExpanded ? "收起后续推荐记录" : `展开其余 ${group.recommendation_count - 1} 条推荐记录`}"
                        >
                          ${isExpanded ? "收起" : "展开"}
                        </button>
                      `
                      : ""
                  }
                </div>
              `
            : `
                <div class="stock-cell compact">
                  <span class="group-placeholder"></span>
                  <span class="stock-subline">
                    ${record.recommend_date}
                    ${showSequenceHint ? ` · 第 ${record.recommendation_sequence} 次` : ""}
                  </span>
                </div>
              `;

          return `
            <tr class="group-event-row ${rowStateClass}">
              <td title="事件 ID：${record.id}">
                ${
                  isGroupStart
                    ? `
                      <div class="stock-cell compact">
                        <span class="stock-symbol">${record.symbol}</span>
                        <span class="stock-name">${record.name || "--"}</span>
                        ${
                          group.recommendation_count > 1
                            ? `
                              <button
                                class="group-toggle-btn"
                                type="button"
                                data-group-symbol="${group.symbol}"
                                aria-expanded="${isExpanded ? "true" : "false"}"
                                aria-label="${isExpanded ? "收起后续推荐记录" : `展开其余 ${group.recommendation_count - 1} 条推荐记录`}"
                              >
                                ${isExpanded ? "收起" : "展开"}
                              </button>
                            `
                            : ""
                        }
                        <span class="stock-subline">
                          ${record.recommend_date}
                          ${showSequenceHint ? ` · 第 ${record.recommendation_sequence} 次` : ""}
                        </span>
                      </div>
                    `
                    : stockCell
                }
              </td>
              <td>
                ${renderEntryPrice(record.entry_price, record.entry_date, record.recommend_date)}
              </td>
              <td>${renderPriceWithMetric(record.current_price, record.return_rate)}</td>
              <td>${renderMetricWithPrice(record.return_5d, record.return_5d_price)}</td>
              <td>${renderMetricWithPrice(record.return_10d, record.return_10d_price)}</td>
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
                    ? `<span class="repeat-badge">第 ${record.recommendation_sequence} 次推荐</span>`
                    : ""
                }
              </div>
              <span class="stock-subline">${record.recommend_date}</span>
            </div>
          </td>
          <td>
            ${renderEntryPrice(record.entry_price, record.entry_date, record.recommend_date)}
          </td>
          <td>${renderPriceWithMetric(record.current_price, record.return_rate)}</td>
          <td>${renderMetricWithPrice(record.return_5d, record.return_5d_price)}</td>
          <td>${renderMetricWithPrice(record.return_10d, record.return_10d_price)}</td>
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
  syncTimelineRangeButtons();
  renderTimelineChart(records);
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
  const refreshContext = data.refresh_context || {};
  const generatedAt = refreshContext.generated_at || data.generated_at || "--";
  const triggerLabel = refreshContext.trigger_label || "未知触发";
  updatedAt.textContent = `最近更新：${generatedAt} · ${triggerLabel}`;
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
timelineRangeControls?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-range]");
  if (!button) {
    return;
  }

  currentTimelineRange = button.dataset.range || "20d";
  applyFilter();
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

timelineChart.addEventListener("mousemove", (event) => {
  const point = event.target.closest(".chart-point");
  if (!point) {
    setActiveChartLabel(null);
    hideChartTooltip();
    return;
  }

  setActiveChartLabel(point.dataset.labelId || null);
  renderChartTooltip(point);
  positionChartTooltip(event);
});

timelineChart.addEventListener("mouseleave", () => {
  setActiveChartLabel(null);
  hideChartTooltip();
});
window.addEventListener("scroll", () => {
  setActiveChartLabel(null);
  hideChartTooltip();
}, { passive: true });
