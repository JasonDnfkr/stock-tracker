# Development Guide

这份文档用于指导后续功能迭代。它不是项目背景说明，也不是用户使用说明：

- `README.md`：面向使用者，说明怎么录入、刷新、预览和部署
- `PROJECT_CONTEXT.md`：面向接手者，说明项目目标、设计决策、当前状态和历史取舍
- `DEVELOPMENT_GUIDE.md`：面向开发者和 agent，说明每次改动时要检查哪些技术影响面


# 1. 核心数据流

项目没有数据库，当前主链路固定为：

```text
docs/data/recommendations.csv
  -> scripts/update_data.py
  -> docs/data/metrics.json
  -> docs/app.js
  -> docs/index.html
```

关键原则：

- `recommendations.csv` 是人工维护源数据
- `metrics.json` 是生成产物，前端唯一直接消费它
- `scripts/manage_recommendations.py` 是本地录入和修改工具，不应绕开它重复实现 CSV 写入规则
- 前端不直接读取 `recommendations.csv`
- 前端不能写文件，GitHub Pages 是静态部署


# 2. 改动影响面

## 改 CSV 字段

如果改 `docs/data/recommendations.csv` 的字段名、字段含义或默认规则，必须同步检查：

- `scripts/manage_recommendations.py`
  - `CSV_FIELDS`
  - `RecommendationRow`
  - `read_rows()`
  - `write_rows()`
  - `cmd_add()`
  - `cmd_update()`
  - `wizard` 相关交互
- `scripts/update_data.py`
  - `Recommendation`
  - `read_recommendations()`
  - failures / pending_records 中携带的字段
- `docs/app.js`
  - 是否有展示、筛选、tooltip 或 fallback 依赖该字段
- `README.md`
  - CSV 示例和字段说明
- `PROJECT_CONTEXT.md`
  - 数据结构 contract

不要只改 CSV 表头。这个项目的 CSV 字段是跨脚本和前端的 contract。

## 改 metrics.json 字段

如果改 `metrics.json` 的顶层结构或 `records[]` 字段，必须同步检查：

- `scripts/update_data.py`
  - `compute_record()`
  - `append_pending_record()`
  - `append_failure()`
  - `build_summary()`
  - `build_stock_summaries()`
- `docs/app.js`
  - summary cards
  - grouped view
  - event view
  - chart tooltip
  - pending / failures rendering
- `README.md`
- `PROJECT_CONTEXT.md`

前端当前主要基于 `records` 本地分组渲染，不直接依赖 `stock_summaries` 作为主渲染源。

## 改标签 tag 逻辑

标签是业务分类维度。改动时至少检查：

- CSV 字段必须仍是 `tag`
- `metrics.json.records[]` 必须输出 `tag`
- summary 统计口径按 `tag + symbol` 去重
- 股票分组视图按 `tag + symbol` 分组
- 同一股票在不同标签下不能混在一起统计或展示
- `failures` 和 `pending_records` 也要携带 `tag`
- 前端在「全部」标签页可以显示 tag 徽标；在具体标签页不要重复显示当前 tag

旧的 `group` / `recommender` 概念已经移除，不要重新引入 CLI alias 或字段 fallback。

## 改推荐价格逻辑

推荐价当前优先级：

1. `recommend_price` 手工价
2. `recommend_time` 对应的 1 分钟行情价
3. 推荐日或顺延交易日的日线收盘价

改动时检查：

- `parse_recommend_time()`
- `parse_recommend_price()`
- `resolve_entry_price()`
- `entry_price_source`
- `entry_time`
- 前端 `formatEntryPriceMeta()`
- 前端 `entryPriceSourceLabel()`

页面展示约定：

- 自动分钟价：显示 `09:32`
- 手工价：显示 `09:32(手填)`
- 日线收盘价：显示 `MM-DD收盘`
- 非交易日顺延：显示 `MM-DD(顺延)收盘`
- 不显示 `1分` 字样

## 改止盈点逻辑

止盈点字段：

- `take_profit_date`
- `take_profit_time`
- `take_profit_price`

当前规则：

- 止盈价优先使用手工 `take_profit_price`
- 如果只填写 `take_profit_date + take_profit_time`，刷新脚本会尝试使用止盈时刻之后第一条 1 分钟行情价格
- 如果自动分钟价抓不到，记录进入 `failures`，提示手工补 `take_profit_price`
- 填写止盈时间时必须填写止盈日期
- 填写止盈价时必须填写止盈日期
- 如果只填写止盈日期但没有止盈时间和止盈价，无法定价，应该拒绝
- 止盈日期不能早于推荐日期
- 有止盈点时，`current_price` 固定为 `take_profit_price`
- 有止盈点时，`return_rate` / `is_profitable` / summary / 散点图都按止盈价计算
- 5/10/20 日收益如果对应窗口落在止盈日之后，按止盈价固定
- 最大涨幅和最大回撤只计算持有区间到止盈日，并纳入止盈价
- `market_current_price` / `market_current_date` 保留真实最新市场价，避免丢失参考信息

改动时检查：

- `scripts/manage_recommendations.py`
  - `CSV_FIELDS`
  - 普通 `add/update` 参数
  - `wizard` 新增和修改止盈点
- `scripts/update_data.py`
  - CSV 解析和校验
  - `compute_record()`
  - `current_price_source`
  - `take_profit_price_source`
  - `return_5d_price_source` / `return_10d_price_source` / `return_20d_price_source`
- `docs/app.js`
  - 表格止盈徽标
  - 当前/止盈价列
  - tooltip 止盈点信息
- `README.md`
- `PROJECT_CONTEXT.md`

## 改录入工具

`scripts/manage_recommendations.py` 同时提供普通 CLI 和 `wizard` 交互向导。

改动时检查：

- 普通子命令仍可用：
  - `list`
  - `add`
  - `update`
  - `remove`
  - `wizard`
- `--code` 是主要参数名，`--symbol` 只是兼容股票代码输入的 alias
- 不要恢复 `--group` / `--recommender`
- `wizard` 写入前要展示记录并让用户确认
- `wizard` 写入后可以选择是否刷新 `metrics.json`
- `wizard` 的日期选择在 TTY 下支持方向键，在非 TTY 下回退普通输入
- 修改推荐时间和推荐价格时，输入 `-` 表示清空
- 修改止盈点时也要支持清空

## 改前端表格

前端有两种明细视图：

- grouped view：按 `tag + symbol` 折叠展示
- event view：按推荐事件平铺展示

改动时检查：

- 不要把底层数据改成只保留每只股票一条
- grouped view 只是在视觉层分组
- 同股多次推荐展开后才显示后续记录
- grouped view 中“第 N 次”只在展开时显示
- event view 中多次推荐股票可以显示 `第 N 次推荐`
- 表头只渲染一次，不要回到每个组重复表头
- 股票列和推荐日期当前是合并展示，避免无谓加宽表格

## 改散点图

散点图在 `summary-panel` 内部，不是独立 panel。

改动时检查：

- 默认时间范围是 `20d`
- 时间范围切换只影响散点图，不影响表格
- 纵轴使用 `compressReturn()` / `expandCompressedReturn()` 成对逻辑
- 坐标轴文字显示真实收益率，不显示压缩值
- 默认标签尽量显示，冲突时隐藏
- 默认已显示标签 hover 时不能跳位
- 默认隐藏点 hover 时用 overlay label
- 边缘点 hover 也要显示 label
- tooltip 不显示事件 ID
- `dataset` 字段不要使用 `data-return-5d` 这种带数字键的形式；使用 `data-return-five-day`

## 改 GitHub Actions

当前只有 `.github/workflows/pages.yml`，它同时负责刷新数据和部署 Pages。

改动时检查：

- 定时任务是北京时间工作日：
  - `09:00 / 09:30 / 10:00 / 10:30`
  - `11:00 / 11:30`
  - `13:00 / 13:30 / 14:00 / 14:30`
  - `15:00`
- workflow 会注入 `REFRESH_TRIGGER`
- `refresh_context` 依赖该环境变量显示触发方式
- 定时或手动触发会自动提交生成的 `metrics.json`
- 注意 bot push 循环触发保护
- 不要基于旧信息恢复 `.github/workflows/update.yml`


# 3. 不变量

以下规则是项目核心约束，改动时不能破坏：

- 统计单位是推荐事件，不是股票
- `id` 代表单个推荐事件
- 同一股票可以在不同日期重复推荐
- 同一股票不同 tag 下不能合并
- `records` 必须保持事件数组
- `pending_records` 和 `failures` 语义分离
- 未来日期、当天未出日线、推荐后暂无交易日，进入 `pending_records`
- 录入错误、非法代码、重复 ID、抓价失败，进入 `failures`
- A 股视觉口径是红涨绿跌
- `.profit-text` / `.pill.profit` 对应红色
- `.loss-text` / `.pill.loss` 对应绿色
- `docs/index.html` 中 `.hero.hidden` 和底部隐藏录入说明不要误删
- `metrics.json` 是生成产物，不要手工改它作为长期修复


# 4. 常见验证命令

改 Python 后：

```bash
python3 -m py_compile scripts/update_data.py scripts/manage_recommendations.py
```

改前端 JS 后：

```bash
node --check docs/app.js
```

改数据结构、抓价或计算逻辑后：

```bash
python3 scripts/update_data.py
```

检查生成数据概况：

```bash
python3 -c "import json; d=json.load(open('docs/data/metrics.json', encoding='utf-8')); print(len(d.get('records', [])), len(d.get('pending_records', [])), len(d.get('failures', [])))"
```

检查录入工具：

```bash
python3 scripts/manage_recommendations.py list
python3 scripts/manage_recommendations.py wizard
```

本地预览页面：

```bash
python3 -m http.server 8000 --directory docs
```

然后访问 `http://localhost:8000`。

不要直接双击 `docs/index.html` 作为主要验证方式，浏览器通常会因为本地 `fetch` 限制读不到 `metrics.json`。


# 5. 每类改动的最低检查清单

## 只改 README / PROJECT_CONTEXT / DEVELOPMENT_GUIDE

- 检查术语是否和当前代码一致
- 不要重新引入 `recommender` 或旧 `group` 业务概念

## 改 CSV 或录入工具

- 用临时 CSV 验证，不要污染真实数据
- 验证 `list`
- 验证 `add` 或 `wizard` 新增
- 验证 `update` 或 `wizard` 修改
- 跑 `py_compile`

示例：

```bash
cp docs/data/recommendations.csv /tmp/stock_wizard_test.csv
python3 scripts/manage_recommendations.py --csv /tmp/stock_wizard_test.csv wizard
```

## 改 update_data.py

- 跑 `py_compile`
- 跑 `python3 scripts/update_data.py`
- 检查 `records / pending_records / failures`
- 抽查一条有 `recommend_time` 的记录
- 抽查一条有 `recommend_price` 的记录
- 抽查一条有 `take_profit_price` 的记录，确认 current_price 和 return_rate 固定为止盈价口径
- 抽查一条港股记录，如果本次改动可能影响代码规范化或抓价

## 改 docs/app.js

- 跑 `node --check docs/app.js`
- 本地启动静态服务
- 检查「全部」标签页
- 检查具体标签页
- 检查 grouped view
- 检查 event view
- 检查 pending / failures 是否仍可渲染
- 如果改散点图，检查 hover tooltip 和隐藏点 overlay label

## 改 styles.css

- 检查表格是否仍紧凑
- 检查红涨绿跌是否正确
- 检查移动端宽度是否没有明显文字重叠
- 检查按钮宽度变化是否导致表格跳动

## 改 workflow

- 检查 schedule 的 UTC 到北京时间映射
- 检查 `REFRESH_TRIGGER`
- 检查自动提交 `metrics.json`
- 检查 Pages artifact 是否仍上传 `docs/`


# 6. 外部接口注意事项

当前主要行情源是腾讯接口：

- A 股日线
- 港股日线
- A 股近期 1 分钟线
- 港股当日分钟线

重要限制：

- 腾讯分钟接口不能稳定回查任意历史日期
- 历史精确时刻价格需要 `recommend_price` 兜底
- 腾讯接口偶发超时，脚本有轻量重试
- 个别抓价失败不应打断整次刷新

如果要新增或替换行情源：

- 不要直接改变 `metrics.json` contract
- 先确认 A 股、港股、日线、分钟线各自支持范围
- 明确是否支持历史分钟回查
- 明确价格复权口径
- 明确返回时间是本地时间还是 UTC
- 保持 failures / pending_records 语义


# 7. 生成产物和脏文件

以下文件可能由命令生成或更新：

- `docs/data/metrics.json`
- `scripts/__pycache__/*.pyc`

注意：

- 当前 `scripts/__pycache__/*.pyc` 是 tracked 文件，运行 `py_compile` 后可能出现在 `git status`
- 不要随意删除或回滚用户已有修改
- 如果只做代码逻辑改动但刷新了数据，要在最终说明中明确 `metrics.json` 也变了


# 8. 给后续 agent 的执行建议

每次接到需求后，先判断改动类型：

- 录入数据：优先用 `scripts/manage_recommendations.py wizard` 或现有 CLI
- 改计算：先读 `scripts/update_data.py` 的数据 contract
- 改展示：先读 `docs/app.js` 对 `metrics.json` 字段的使用
- 改样式：先确认用户偏好是紧凑、低装饰噪音
- 改 workflow：先确认当前只有 `pages.yml`

动手前先查相关字段的全局引用：

```bash
rg -n "字段名或函数名" .
```

改完后运行最小必要验证，不要只靠静态阅读判断完成。
