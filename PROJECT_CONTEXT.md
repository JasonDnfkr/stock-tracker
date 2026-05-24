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

刚完成对 `README.md` 的重写，把文档从“介绍型说明”改成了更贴近当前工作流的“操作手册”。当前没有新的功能开发在进行中，下一步更可能是继续做前端细节优化或数据录入体验优化。

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


# 4. 当前 blocker / 风险

## 当前卡点

当前没有阻塞开发的硬 blocker。项目处于“可运行、可部署、可维护”的状态。

## 潜在风险

- 数据源依赖 Yahoo Finance chart API，若接口限流、改字段或偶发失败，会进入 failures
- `metrics.json` 是生成产物，如果修改了 `recommendations.csv` 但没跑 `scripts/update_data.py`，本地页面会和 CSV 不一致
- GitHub Pages 是静态部署，无法直接在网页前端写入数据
- 当前没有自动化测试，只做语法和手工页面验证
- 当前分组折叠状态只保存在前端内存中，刷新页面会丢失

## 已知 bug

当前没有明确已确认但未修复的功能性 bug。最近一次用户反馈的“多次推荐只显示一次”问题已经通过分组渲染修正。

## 未验证假设

- `Intl.NumberFormat(..., { signDisplay: "exceptZero" })` 在目标浏览器环境下是否都表现一致，没有做兼容性回归
- Yahoo Finance 对全部 A 股代码的覆盖和稳定性没有做更大样本验证
- 前端当前紧凑布局在非常窄的移动端上是否仍完全满足用户偏好，没有系统验证


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

- push 到 `main` 时触发
- `workflow_dispatch` 手动触发
- `schedule` 定时触发，当前 `cron: "10 10 * * *"`，即北京时间每天 `18:10`
- 执行 `python scripts/update_data.py`
- 上传 `docs/` 为 Pages artifact 并部署

### `docs/index.html`

负责：

- 页面骨架
- 概览区、分组视图、事件视图、待跟踪区、失败区

关键现状：

- `<header class="hero hidden">` 顶部 hero 被隐藏但保留
- 底部“录入方式” section 也被 `hidden`
- 分组视图和事件视图都共享单次表头

### `docs/app.js`

负责：

- 加载 `./data/metrics.json`
- 渲染 summary cards
- 渲染 grouped view / event view
- 搜索过滤
- 多次推荐股票的折叠/展开
- 渲染 pending / failures

关键变量：

- `let allRecords = []`
- `let currentView = "grouped"`
- `const expandedGroups = new Set()`

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
- `renderSummary(summary)`
- `stockSummaryMap(records)`
- `buildGroupedStocks(records)`
- `renderGroupedView(records)`
- `renderTable(records)`
- `syncViewButtons()`
- `renderFilteredViews(records)`
- `toggleGroup(symbol)`
- `renderFailures(failures)`
- `renderPendingRecords(records)`
- `applyFilter()`
- `loadData()`

重要展示约束：

- 股票列已经和推荐日期合并
- grouped view 中只有展开后、且该股票存在多次推荐时，才显示 `第 N 次`
- grouped view 的后续行使用 `.group-follow-row { opacity: 0.75; }`
- “当前价”列实际是“当前价 + 收益率”
- `5日 / 10日 / 20日 / 最大涨幅 / 最大回撤` 都是“百分比 + 第二行对应价格”

### `docs/styles.css`

负责：

- A 股视觉风格
- 紧凑表格布局
- 分组折叠行的视觉弱化

关键样式约束：

- `--profit: #c61f35`
- `--loss: #0f8a5f`
- `.group-follow-row td { opacity: 0.75; }`
- `.group-follow-row.hidden { display: none; }`
- `.hidden { display: none; }`

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

按 `git status --short`，当前工作区有修改：

- `README.md`
- `docs/app.js`
- `docs/data/metrics.json`
- `docs/index.html`
- `docs/styles.css`
- `scripts/update_data.py`
- `scripts/__pycache__/update_data.cpython-311.pyc`

说明：

- `docs/app.js` / `docs/index.html` / `docs/styles.css` 是这轮前端迭代的主战场
- `scripts/update_data.py` 是数据结构演进的关键文件
- `README.md` 刚被改写为操作手册
- `docs/data/metrics.json` 是生成产物，不要把它误当作手工源数据


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

