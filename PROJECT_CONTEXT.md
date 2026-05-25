# 1. 项目目标

## 当前项目在做什么

这是一个面向 A 股荐股追踪的零服务器静态项目，部署方式是：

- 前端静态页面放在 `docs/`
- 数据源输入是 `docs/data/recommendations.csv`
- 计算脚本是 `scripts/update_data.py`
- GitHub Actions 负责定时刷新 `docs/data/metrics.json`
- GitHub Pages 负责展示结果

项目的核心统计单位是“推荐事件”，不是“股票去重后的一条记录”。同一只股票在不同日期可以多次推荐，每次推荐都要保留为一条独立事件并分别计算收益。

## 最终目标是什么

最终目标是让用户以最低维护成本持续观察“群主荐股的长期胜率和收益表现”，并满足以下约束：

- 不依赖自购服务器
- 不要求数据库
- 可直接通过 GitHub Pages 展示
- 数据维护成本尽量低
- 对错误录入有兜底，不因单条脏数据导致整次更新失败
- 同一只股票多次推荐时，展示方式要合理且紧凑


# 2. 当前任务状态

## 当前正在做什么

刚完成一轮散点图与标签交互迭代。当前页面除了表格视图外，概览区还集成了“推荐事件收益时间线”散点图，后续若继续开发，最可能继续打磨的是这张图的标签布局、hover 体验和边缘点展示。

## 已完成什么

已完成的核心能力：

- A 股代码校验与标准化
- `recommendations.csv` 到 `metrics.json` 的完整生成链路
- GitHub Actions 自动刷新 + GitHub Pages 部署
- 同一股票多次推荐的独立建模和展示
- 前端的两种视图：
  - 按股票分组
  - 按事件平铺
- 搜索过滤
- “待跟踪”与“失败记录”分流展示
- 本地管理工具 `scripts/manage_recommendations.py`
- `5日 / 10日 / 20日收益`
- `最大涨幅 / 最大回撤`
- A 股红涨绿跌配色
- 概览区散点图：
  - 推荐事件收益时间线
  - 压缩纵轴
  - 横向滚动
  - 常驻标签
  - hover tooltip
  - hover overlay label

## 哪些问题已经解决

已解决的问题：

- CSV 中有错误行时，不再让整次更新失败
- 非法代码、空字段、日期格式错误、重复 `id` 都改成 failure 记录
- 推荐日期晚于当前可交易区间时，不再混入 failures，而是进入 `pending_records`
- 同一只股票多次推荐时，不再相互覆盖，而是保留多条独立事件
- 分组视图中多次推荐股票支持折叠/展开
- 表头只出现一次，不在每个组里重复出现
- 股票列与推荐日期已合并，减少横向空间浪费
- “当前价”和“收益率”已合并到同一列
- `5日 / 10日 / 20日收益`、`最大涨幅`、`最大回撤` 都改成双行展示，第二行显示对应价格
- 当天价格的顺延说明已压缩为 `MM-DD(顺延)`，避免撑宽布局
- 顶部 hero 和底部录入说明已从页面上隐藏，但代码仍保留
- 分组间的装饰色已去掉，避免花哨和干扰
- 概览区新增散点图，且已并入 summary panel，不再单独占一个 panel
- 散点图纵轴已改成压缩刻度，避免极值点把其余点挤扁
- 散点图横轴在点多时支持横向滚动
- 散点图 tooltip 已从原生 `<title>` 改成自定义浮层，hover 响应更快
- tooltip 中的事件 ID 已移除
- tooltip 的 `5日 / 10日 / 20日收益` 读取问题已修复，原因是 `dataset` 不能再用 `data-return-5d` 这类带数字键
- 散点图会尽量给所有点显示常驻标签，重叠时按优先级隐藏
- 默认可见标签 hover 时不再跳位置
- 默认隐藏的点 hover 时会单独以 overlay label 形式展示，并置于最上层
- 边缘点 hover 时也会显示 overlay label
- 横轴左右边距已加大，最左/最右刻度和点位不再贴边

## 哪些方案被否决，以及为什么

被否决/放弃的方案：

- 直接做“前端录入 + 在线存储”：
  - 原因：用户没有自购服务器，不想引入额外后端复杂度
  - 结论：暂时回到“本地改 CSV / 本地脚本辅助”方案
- 继续手工编辑 `recommendations.csv`：
  - 原因：手动维护 `id` 容易出错，重复推荐时更难管理
  - 结论：新增 `scripts/manage_recommendations.py`
- 把同一股票合并成单条统计：
  - 原因：会丢失每次推荐的独立样本，不利于观察荐股表现
  - 结论：按推荐事件建模，前端只是在视觉上按股票分组
- 在分组页面为每组使用不同强调色：
  - 原因：用户反馈眼花缭乱，噪音过大
  - 结论：去掉分组色彩差异，只保留结构分组
- 在分组页面给每组单独渲染表头：
  - 原因：重复信息过多，页面不紧凑
  - 结论：整页共享一次表头
- 在多次推荐股票上显示“关注次数 / 关注跨度 / 单票胜率”：
  - 原因：用户明确表示不是核心诉求，且会引入额外认知噪音
  - 结论：只保留原始收益指标，分组只是为了表达“同一股票被多次推荐”
- 给散点图所有点强制显示静态标签且不做隐藏：
  - 原因：会导致标签大面积重叠，读不清
  - 结论：改成“尽量全部显示 + 冲突时按优先级隐藏”
- 继续使用浏览器原生 `<title>` 作为散点图 tooltip：
  - 原因：hover 延迟明显，用户感知较差
  - 结论：改成自定义 tooltip 浮层
- hover 时让默认可见标签也改位置：
  - 原因：用户反馈跳动感强，观感不好
  - 结论：默认可见标签保持原位，仅原本隐藏的点使用 hover overlay label
- hover label 仍要求完全安全才显示：
  - 原因：会导致边缘点 hover 时没有 label
  - 结论：边缘点 hover 时直接以上层 overlay label 展示


# 3. 关键架构/设计决策

## 设计决策 1：以“推荐事件”为主实体，而不是以股票为主实体

为什么这样设计：

- 用户要观察的是群主每次推荐的效果，而不是单只股票的长期走势图
- 同一只股票多次推荐，本质上是多个样本，不能被一条记录覆盖

tradeoff：

- 好处：胜率和收益统计更准确，样本不丢失
- 代价：前端展示复杂度更高，需要处理同股多事件的分组/折叠

绝对不能破坏：

- 任何时候都不能把多次推荐静默合并成一条结果
- `id` 必须代表单个推荐事件，而不是单个股票

## 设计决策 2：前端分组只是展示层，底层数据仍是事件平铺

为什么这样设计：

- 统计和计算天然以事件为单位
- 展示上为了减少视觉重复，才按股票分组

tradeoff：

- 好处：数据结构简单，统计清晰
- 代价：前端需要维护 `expandedGroups` 这样的 UI 状态

绝对不能破坏：

- `metrics.json.records` 仍应保持事件数组，不要为了前端分组去改成嵌套结构作为唯一主数据

## 设计决策 3：错误记录进入 `failures`，待开盘/未来记录进入 `pending_records`

为什么这样设计：

- “录错了”和“还没到可计算时点”是两类完全不同的问题
- 如果都扔到 failures，用户会误以为系统或数据源出错

tradeoff：

- 好处：页面语义清晰
- 代价：脚本和前端都要维护两个列表

绝对不能破坏：

- 未来日期或暂无后续交易日的记录不能再回退成 failure

## 设计决策 4：保留 `docs/index.html` 中被隐藏的版块，不直接删除

为什么这样设计：

- 用户只是“暂时不展示”，不是永久废弃
- 后续可以随时取消 `hidden` 恢复

tradeoff：

- 好处：恢复成本低
- 代价：HTML 中存在当前不可见的结构

绝对不能破坏：

- 修改页面时不要误删 `.hero.hidden` 和底部录入说明区块

## 设计决策 5：录入工具优先，而不是让用户直接改 CSV

为什么这样设计：

- CSV 对事件 `id`、日期和代码格式较脆弱
- 本地脚本可以自动生成 `id` 并降低维护成本

tradeoff：

- 好处：人为错误显著减少
- 代价：用户本地需要执行 Python 命令

绝对不能破坏：

- `scripts/manage_recommendations.py` 的主参数名是 `--code`
- 虽然 CSV 列名仍是 `symbol`，但 CLI 层不能再回退成只暴露 `--symbol`

## 设计决策 6：A 股视觉口径固定为“红涨绿跌”

为什么这样设计：

- 用户明确要求使用 A 股风格

tradeoff：

- 好处：符合用户习惯
- 代价：与常见国际市场 UI 习惯相反

绝对不能破坏：

- `.profit-text` / `.pill.profit` 必须是红色正收益
- `.loss-text` / `.pill.loss` 必须是绿色负收益

## 设计决策 7：散点图并入概览区，而不是单独再开一个 panel

为什么这样设计：

- 用户认为图较离散，适合当作概览视图的一部分，而不是与主表格并列的独立大模块
- 这样页面更紧凑，也符合“先看整体，再看明细”的阅读路径

tradeoff：

- 好处：页面层级更紧凑，图表与 summary 指标联系更强
- 代价：summary panel 内部承担的信息更多，后续排版要更谨慎

绝对不能破坏：

- 图表当前在 `summary-panel` 内部，不要再无故拆回独立 panel

## 设计决策 8：散点图纵轴使用压缩刻度，而不是线性刻度

为什么这样设计：

- 用户明确反馈极值点会把其他点挤扁
- 当前收益分布可能有少数大幅盈利样本，线性刻度可读性差

tradeoff：

- 好处：中间区间的点位更可读
- 代价：纵轴不再是直观线性距离，需要通过刻度文本理解真实收益

绝对不能破坏：

- 刻度文本仍必须显示真实收益率，而不是内部压缩值
- 代码中的 `compressReturn(value)` / `expandCompressedReturn(value)` 是配套的一组逻辑，不能只改其一

## 设计决策 9：散点图默认标签与 hover 标签分离

为什么这样设计：

- 用户要求默认标签尽量全部展示，但又不希望 hover 时默认可见标签跳位
- 同时用户又要求默认隐藏的点在 hover 时依然要看到 label

tradeoff：

- 好处：默认视图稳定，hover 时信息补足
- 代价：需要维护两套标签逻辑：
  - 默认 label
  - hover overlay label

绝对不能破坏：

- 默认已显示的 label hover 时不能改位置
- 原本隐藏的点 hover 时要用 overlay label，而不是改写默认 label 位置
- overlay label 必须在最上层

## 设计决策 10：散点图 hover tooltip 不再展示事件 ID

为什么这样设计：

- 用户明确不需要在 tooltip 中看到事件 ID
- tooltip 目标是快速看核心收益信息，不是调试信息

tradeoff：

- 好处：tooltip 更短、更聚焦
- 代价：如果要查事件 ID，只能通过其他方式（如表格 hover）

绝对不能破坏：

- 散点图 tooltip 当前不要再显示事件 ID，除非用户再次明确要求


# 4. 当前 blocker / 风险

## 当前卡点

当前没有阻塞开发的硬 blocker。项目处于“可运行、可部署、可维护”的状态。

## 潜在风险

- 数据源依赖 Yahoo Finance chart API，若接口限流、改字段或偶发失败，会进入 failures
- `metrics.json` 是生成产物，如果修改了 `recommendations.csv` 但没跑 `scripts/update_data.py`，本地页面会和 CSV 不一致
- GitHub Pages 是静态部署，无法直接在网页前端写入数据
- 当前没有自动化测试，只做语法和手工页面验证
- 当前分组折叠状态只保存在前端内存中，刷新页面会丢失
- 散点图标签布局采用轻量贪心+候选位置策略，不是完整布局引擎；数据量更大时仍可能出现较多隐藏标签
- hover overlay label 当前允许与其他 label 视觉重叠，只保证位于最上层并靠描边提高可读性

## 已知 bug

当前没有明确已确认但未修复的功能性 bug。最近几轮已修复的问题包括：

- 多次推荐股票只显示一次
- tooltip 的 `5日 / 10日 / 20日收益` 不显示
- 默认可见 label hover 时跳位
- 边缘点 hover 时不显示 label

## 未验证假设

- `Intl.NumberFormat(..., { signDisplay: "exceptZero" })` 在目标浏览器环境下是否都表现一致，没有做兼容性回归
- Yahoo Finance 对全部 A 股代码的覆盖和稳定性没有做更大样本验证
- 前端当前紧凑布局在非常窄的移动端上是否仍完全满足用户偏好，没有系统验证
- 散点图标签的当前候选位置集合，是否已经是用户最满意的布局，尚未最终定稿


# 5. 文件与代码结构

## 关键目录

- `.github/workflows/`
  - GitHub Actions 工作流
- `docs/`
  - GitHub Pages 静态站点根目录
- `docs/data/`
  - 输入 CSV 和生成后的 JSON
- `scripts/`
  - 数据抓取、计算、录入工具

## 关键文件

### `.github/workflows/pages.yml`

负责：

- 当前唯一的 GitHub Actions 工作流
- push 到 `main` 时触发
- `workflow_dispatch` 手动触发
- `schedule` 定时触发
- 执行 `python scripts/update_data.py`
- 定时/手动触发时自动提交并 `git push` 最新 `docs/data/metrics.json`
- 上传 `docs/` 为 Pages artifact 并部署

当前 schedule（UTC）：

- `0,33 1-2 * * 1-5`
- `0,33 3 * * 1-5`
- `0,33 5-6 * * 1-5`
- `0 7 * * 1-5`

对应北京时间工作日：

- `09:00 / 09:33 / 10:00 / 10:33`
- `11:00 / 11:33`
- `13:00 / 13:33 / 14:00 / 14:33`
- `15:00`

关键现状：

- 不再存在单独的 `.github/workflows/update.yml`
- `pages.yml` 已经合并了“更新数据”和“部署页面”两项职责
- 为避免定时任务 `git push` 后再次触发 workflow 死循环，job 上有 bot push 保护判断

### `docs/index.html`

负责：

- 页面骨架
- 概览区、分组视图、事件视图、待跟踪区、失败区

关键现状：

- `<header class="hero hidden">` 顶部 hero 被隐藏但保留
- 底部“录入方式” section 也被 `hidden`
- 分组视图和事件视图都共享单次表头
- 散点图容器 `#timeline-chart` 现在位于 `summary-panel` 内部，而不是独立 section

### `docs/app.js`

负责：

- 加载 `./data/metrics.json`
- 渲染 summary cards
- 渲染概览区散点图
- 渲染 grouped view / event view
- 搜索过滤
- 多次推荐股票的折叠/展开
- 渲染 pending / failures

关键变量：

- `let allRecords = []`
- `let currentView = "grouped"`
- `const expandedGroups = new Set()`
- `const timelineChart = document.getElementById("timeline-chart")`
- `const timelineEmptyState = document.getElementById("timeline-empty-state")`
- `const chartTooltip = document.createElement("div")`
- `let activeTooltipId = null`
- `let activeChartLabelId = null`

关键函数：

- `formatPercent(value)`
- `formatSignedPercent(value)`
- `formatNumber(value)`
- `formatShortDate(dateText)`
- `formatEntryDateLabel(entryDate, recommendDate)`
- `renderMetricWithPrice(rate, price)`
- `renderPriceWithMetric(price, rate)`
- `renderEntryPrice(price, entryDate, recommendDate)`
- `metricClass(value)`
- `clamp(value, minValue, maxValue)`
- `dateToTimestamp(dateText)`
- `buildTickValues(minValue, maxValue, tickCount)`
- `escapeHtml(text)`
- `tooltipMetricText(value)`
- `tooltipMetricClass(value)`
- `estimateLabelWidth(text)`
- `rectsOverlap(a, b)`
- `rectOverlapsPoint(rect, point, padding = 6)`
- `compressReturn(value)`
- `expandCompressedReturn(value)`
- `renderSummary(summary)`
- `renderTimelineChart(records)`
- `stockSummaryMap(records)`
- `buildGroupedStocks(records)`
- `renderGroupedView(records)`
- `renderTable(records)`
- `syncViewButtons()`
- `renderFilteredViews(records)`
- `toggleGroup(symbol)`
- `renderFailures(failures)`
- `renderPendingRecords(records)`
- `hideChartTooltip()`
- `hideHoverLabelOverlay()`
- `showHoverLabelOverlay(point)`
- `setActiveChartLabel(labelId)`
- `positionChartTooltip(event)`
- `renderChartTooltip(target)`
- `applyFilter()`
- `loadData()`

重要展示约束：

- 股票列已经和推荐日期合并
- grouped view 中只有展开后、且该股票存在多次推荐时，才显示 `第 N 次`
- grouped view 的后续行使用 `.group-follow-row { opacity: 0.75; }`
- “当前价”列实际是“当前价 + 收益率”
- `5日 / 10日 / 20日 / 最大涨幅 / 最大回撤` 都是“百分比 + 第二行对应价格”
- summary panel 内置散点图，不要再额外渲染独立图表 panel
- 散点图默认标签尽量全显，但冲突时按优先级隐藏
- 散点图默认已显示 label hover 时不能跳位
- 散点图默认隐藏点 hover 时要通过 `#chart-hover-label-layer` 生成 overlay label
- overlay label 需要在最上层，且靠更强描边保证重叠时可读
- 边缘点 hover 时也必须显示 label
- 散点图 tooltip 当前不展示事件 ID
- 横轴左右两侧有额外 padding，最左/最右刻度和点不要贴边

### `docs/styles.css`

负责：

- A 股视觉风格
- 紧凑表格布局
- 分组折叠行的视觉弱化
- 散点图、散点图标签、overlay label、tooltip 样式

关键样式约束：

- `--profit: #c61f35`
- `--loss: #0f8a5f`
- `.group-follow-row td { opacity: 0.75; }`
- `.group-follow-row.hidden { display: none; }`
- `.hidden { display: none; }`
- `.chart-label-text` 是纯文字 label，不再有背景块或边框
- `.chart-hover-label-layer` 是 hover overlay label 的单独图层
- `.chart-hover-label-text` 的描边比默认 label 更重

### `docs/data/recommendations.csv`

负责：

- 用户维护的推荐事件输入

关键字段：

- `id,symbol,name,recommend_date,note`

### `docs/data/metrics.json`

负责：

- 前端唯一直接消费的数据文件
- 由 `scripts/update_data.py` 自动生成

### `scripts/update_data.py`

负责：

- 读取 `recommendations.csv`
- 规范化/校验 A 股代码
- 调用 Yahoo Finance chart API 拉取历史日线
- 计算收益相关指标
- 输出 `metrics.json`

关键类/异常：

- `class PendingTrackingError(RuntimeError)`
- `@dataclass class Recommendation`

关键函数签名：

- `normalize_symbol(raw_symbol: str) -> str`
- `validate_symbol(raw_symbol: str) -> str`
- `sanitize_id(raw_id: str) -> str`
- `generate_recommendation_id(symbol: str, recommend_date: str, row_number: int) -> str`
- `read_recommendations(csv_path: Path) -> tuple[list[Recommendation], list[dict]]`
- `yahoo_history(symbol: str, start_date: dt.date, end_date: dt.date) -> list[dict]`
- `first_index_on_or_after(bars: list[dict], target_date: dt.date) -> int | None`
- `calculate_max_drawdown(closes: list[float]) -> tuple[float | None, float | None]`
- `compute_record(rec: Recommendation, bars: list[dict]) -> dict`
- `annotate_recommendation_sequences(records: list[dict]) -> list[dict]`
- `build_stock_summaries(records: list[dict]) -> list[dict]`
- `average(values: list[float | None]) -> float | None`
- `build_summary(records: list[dict]) -> dict`
- `main() -> int`

### `scripts/manage_recommendations.py`

负责：

- 本地 CRUD `recommendations.csv`
- 自动生成/重建推荐事件 `id`
- 可选执行 `--refresh`

关键数据结构：

- `CSV_FIELDS = ["id", "symbol", "name", "recommend_date", "note"]`
- `@dataclass class RecommendationRow`

关键函数签名：

- `read_rows(csv_path: Path) -> list[RecommendationRow]`
- `write_rows(csv_path: Path, rows: list[RecommendationRow]) -> None`
- `parse_date(date_text: str) -> str`
- `parse_symbol(symbol_text: str) -> str`
- `generate_id(existing_rows: list[RecommendationRow], symbol: str, recommend_date: str) -> str`
- `find_row(rows: list[RecommendationRow], recommendation_id: str) -> RecommendationRow`
- `render_table(rows: list[RecommendationRow]) -> str`
- `maybe_refresh_metrics(should_refresh: bool) -> None`
- `cmd_list(args: argparse.Namespace) -> int`
- `cmd_add(args: argparse.Namespace) -> int`
- `cmd_remove(args: argparse.Namespace) -> int`
- `cmd_update(args: argparse.Namespace) -> int`
- `build_parser() -> argparse.ArgumentParser`
- `main() -> int`

CLI contract：

- `list --code`
- `add --code --name --recommend-date [--note] [--refresh]`
- `remove --id [--refresh]`
- `update --id [--code] [--name] [--recommend-date] [--note] [--new-id] [--regenerate-id] [--refresh]`

## 最近修改了哪些文件

最近主要修改的是：

- `PROJECT_CONTEXT.md`
- `.github/workflows/pages.yml`
- `.github/workflows/update.yml`（已删除）
- `docs/app.js`
- `docs/styles.css`

说明：

- 最近这一轮除了散点图交互迭代，还做了 workflow 合并
- `docs/app.js` / `docs/styles.css` 是这轮前端迭代的主战场
- workflow 现在只剩 `.github/workflows/pages.yml`
- `docs/data/metrics.json` 仍然是生成产物，不要把它误当作手工源数据


# 6. 数据结构 / API / SQL 变化

## SQL / 数据库

当前没有数据库，也没有 SQL 结构。不要在 handoff 中假设存在 Supabase / Postgres / 后端表。

## 输入 CSV 结构

文件：`docs/data/recommendations.csv`

表头固定为：

```csv
id,symbol,name,recommend_date,note
```

字段含义：

- `id`：推荐事件唯一 ID
- `symbol`：A 股代码。CSV 里字段名仍然是 `symbol`
- `name`：股票名称
- `recommend_date`：推荐日期，要求 `YYYY-MM-DD`
- `note`：备注

输入约束：

- 行可以乱序
- `id` 必须全表唯一
- `symbol` 可以写裸 6 位代码，也可以写 `.SH/.SS/.SZ`
- 空行允许存在，会被忽略

## `metrics.json` contract

文件：`docs/data/metrics.json`

顶层结构：

```json
{
  "generated_at": "2026-05-25 02:20:04 CST",
  "summary": {},
  "records": [],
  "stock_summaries": [],
  "pending_records": [],
  "failures": []
}
```

### `summary`

当前字段：

- `total_picks: number`
- `unique_symbols: number`
- `profitable_picks: number`
- `win_rate: number | null`
- `average_return: number | null`
- `average_return_5d: number | null`
- `average_return_10d: number | null`
- `average_return_20d: number | null`

注意：

- 前端 `renderSummary()` 当前只渲染到 `average_return_10d`
- `average_return_20d` 已存在于 JSON，但当前页面未展示

### `records[]`

每一项代表一个推荐事件。当前字段：

- `id: string`
- `symbol: string`
- `query_symbol: string`
- `name: string`
- `note: string`
- `recommend_date: string`
- `entry_date: string`
- `entry_price: number`
- `current_price: number`
- `return_rate: number`
- `return_5d: number | null`
- `return_5d_price: number | null`
- `return_10d: number | null`
- `return_10d_price: number | null`
- `return_20d: number | null`
- `return_20d_price: number | null`
- `max_gain: number | null`
- `max_gain_price: number | null`
- `max_drawdown: number | null`
- `max_drawdown_price: number | null`
- `is_profitable: boolean`
- `current_date: string`
- `recommendation_sequence: number`
- `recommendation_count_for_symbol: number`

字段含义补充：

- `entry_date`：实际建仓对应的交易日；若推荐日不是交易日，会顺延
- `query_symbol`：给 Yahoo Finance 使用的标准代码，如 `600584.SS`
- `recommendation_sequence`：该股票按时间排序后的第几次推荐
- `recommendation_count_for_symbol`：该股票在全量事件中的推荐总次数

### `stock_summaries[]`

这是为可能的分组/汇总展示保留的派生数据。当前字段：

- `symbol`
- `name`
- `recommendation_count`
- `profitable_count`
- `win_rate`
- `average_return`
- `latest_return`
- `first_recommend_date`
- `latest_recommend_date`

注意：

- 当前前端分组页并没有直接消费 `stock_summaries`
- 前端是基于 `records` 本地再分组

### `pending_records[]`

当前字段：

- `id`
- `symbol`
- `query_symbol`
- `name`
- `recommend_date`
- `status`
- `message`

目前 `status` 取值实际为：

- `pending_tracking`

### `failures[]`

失败记录字段：

- `id`
- `symbol`
- `query_symbol`（部分场景可能没有）
- `name`
- `recommend_date`
- `error`

## 外部 API contract

当前唯一外部数据接口是 Yahoo Finance chart API：

- 常量：`YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"`

请求参数来自 `yahoo_history()`：

- `period1`
- `period2`
- `interval=1d`
- `includePrePost=false`
- `events=div,splits`

脚本假设返回结构中存在：

- `chart.result[0].timestamp`
- `chart.result[0].indicators.quote[0].open/high/low/close/volume`

不要在没有验证的情况下替换数据源或修改 `compute_record()` 的字段输出，否则会直接影响前端 contract。


# 7. 当前工作分支与环境

## git branch

当前分支：

- `main`

## 启动方式

本地刷新数据：

```bash
python3 scripts/update_data.py
```

本地录入工具：

```bash
python3 scripts/manage_recommendations.py list
python3 scripts/manage_recommendations.py add --code 600519 --name 贵州茅台 --recommend-date 2026-05-25 --note 首次推荐 --refresh
```

本地预览静态页：

```bash
python3 -m http.server 8000 --directory docs
```

然后访问：

- `http://localhost:8000`

## 测试方式

当前没有单元测试。常用检查方式：

```bash
python3 -m py_compile scripts/update_data.py scripts/manage_recommendations.py
node --check docs/app.js
```

建议每次涉及数据结构或 UI 改动后至少做：

1. 运行 `python3 scripts/update_data.py`
2. 运行 `python3 -m http.server 8000 --directory docs`
3. 手动检查 grouped view / event view / pending / failures

## 依赖注意事项

- Python 3.11 在 GitHub Actions 中使用
- 脚本仅依赖标准库
- 前端无 npm、无打包器、无框架
- 页面依赖浏览器直接 `fetch("./data/metrics.json")`
- 因为 `fetch` 限制，不要直接双击 `docs/index.html` 做本地预览
- 图表和标签逻辑目前全部是原生 DOM + 原生 SVG，没有引入任何图表库
- GitHub Actions 当前只有一个 workflow：`.github/workflows/pages.yml`


# 9. 给下一位 agent 的重要提醒

- 这是“事件追踪系统”，不是“股票池系统”。任何试图把同一股票压成一条记录的改动，都会破坏设计前提。
- 用户极度偏好紧凑、直接、低装饰噪音的页面。不要重新引入花哨分组色、重复表头或冗长说明文字。
- 用户明确要求 A 股风格：红涨绿跌，不能改回国际市场常见的绿涨红跌。
- `README.md` 已经刚被重写，不要基于旧理解再把它改回泛介绍文案。
- `docs/index.html` 中顶部 hero 和底部录入说明只是隐藏，不是废弃，不要误删。
- `docs/data/metrics.json` 是生成文件；如果你修改了 `recommendations.csv` 或 `update_data.py`，记得重新生成。
- CLI 参数名对用户很重要：脚本主参数是 `--code`，不是 `--symbol`，虽然兼容 alias 还在。
- grouped view 中“第 N 次推荐”的展示逻辑很容易写错。当前要求是：
  - 只对多次推荐股票生效
  - 只在 grouped view 已展开时显示
  - 在 flat event view 中，多次推荐股票显示 `第 N 次推荐`
- 当前分组页的展开按钮文案只有 `展开` / `收起`，这是为了避免按钮宽度变化导致表格跳动。不要改回长文案按钮文本。
- “待跟踪”和“失败”必须语义分离。未来日期/待开盘/暂无后续交易日，不要再混进 failures。
- `stock_summaries` 目前不是前端主渲染源。若要继续优化 grouped view，先考虑是否仍应基于 `records` 渲染，避免双份逻辑漂移。
- 当前没有自动化测试，任何涉及 `metrics.json` 字段的改动都要同步检查：
  - `scripts/update_data.py`
  - `docs/app.js`
  - `README.md`
- 散点图 tooltip 之前踩过一个坑：`dataset` 不要再用 `data-return-5d` 这种带数字的名字，已经改成 `data-return-five-day` / `data-return-ten-day` / `data-return-twenty-day`
- 散点图 hover 交互当前是两套：
  - 默认 label：静态位置，不跳位
  - hover overlay label：只给原本隐藏的点用
- 如果以后继续改 label 布局，不要把“边缘点 hover 也要显示 label”这个要求弄丢
- 如果以后继续改 hover 交互，不要把“默认已显示 label hover 时不应跳位”这个要求弄丢
- 当前 label 已经被改成纯文字，没有背景块和边框；如果重新加底板，大概率会再次被用户否掉
- workflow 结构最近刚改过：不要再基于旧理解以为有独立的 `update.yml`
- 当前 `pages.yml` 既负责 schedule 更新，也负责部署；如果后续再拆分，必须重新评估 bot push 循环触发问题
