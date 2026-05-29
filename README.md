# A 股荐股追踪面板

这是一个不依赖自购服务器的静态小项目：

- 你维护推荐记录
- `scripts/update_data.py` 通过腾讯行情接口抓取 A 股 / 港股日线并计算指标
- GitHub Actions 自动刷新 `docs/data/metrics.json`
- GitHub Pages 直接展示网页

项目的统计单位是“推荐事件”，不是“股票去重结果”。同一只股票可以在不同日期多次推荐，每次都会单独保留、单独计算。

## 你平时怎么用

日常只需要做这几步：

1. 本地新增或修改推荐记录
2. 本地执行一次刷新，确认页面效果
3. 提交并推送到 GitHub
4. 等待 GitHub Actions 自动更新线上页面

最省事的录入方式不是手改 CSV，而是打开交互向导：

```bash
python3 scripts/manage_recommendations.py wizard
```

向导支持新增、修改、查看和刷新数据。新增或修改推荐日期时，交互式终端里可以用方向键选日期：`←` 前一天，`→` 后一天，界面会同时显示星期几；按 `Enter` 确认。

如果需要自动化或一次性命令，也可以继续使用普通子命令：

```bash
python3 scripts/manage_recommendations.py add --tag 标签A --code 600519 --name 贵州茅台 --recommend-date 2026-05-25 --recommend-time 10:23 --note 首次推荐 --refresh
python3 scripts/manage_recommendations.py add --tag 标签A --code 600519 --name 贵州茅台 --recommend-date 2026-05-25 --recommend-time 10:23 --recommend-price 1288.5 --note 历史补录 --refresh
python3 scripts/manage_recommendations.py list
python3 scripts/manage_recommendations.py update --id 20260525-600519-1 --tag 标签B --recommend-time 10:23 --recommend-price 1288.5 --note 二次观察 --refresh
python3 scripts/manage_recommendations.py remove --id 20260525-600519-1 --refresh
```

说明：

- `--code` 是主要参数名，支持 A 股和港股代码
- `--tag` 可选，标签名称；不填时归到 `默认`
- `--recommend-time` 可选，格式是 `HH:MM`，系统会尝试使用 1 分钟行情作为推荐价
- `--recommend-price` 可选，用于历史补录或分钟行情不可回查时手工指定推荐价
- `--refresh` 会顺手执行一次 `scripts/update_data.py`
- 工具会自动生成 `id`，你不需要手工维护
- 向导里修改推荐时间或推荐价格时，输入 `-` 可以清空原值

## 数据文件

推荐记录存放在 `docs/data/recommendations.csv`，字段如下：

```csv
id,tag,symbol,name,recommend_date,recommend_time,recommend_price,note
20260506-301666-1,默认,301666,大普微,2026-05-06,,,empty
20260521-688820-1,标签A,688820,盛合晶微,2026-05-21,10:23,,empty
20260525-603986-1,标签B,603986,兆易创新,2026-05-24,10:23,1288.5,二次推荐
```

字段说明：

- `id`：推荐事件唯一标识
- `tag`：标签；为空时按 `默认` 处理
- `symbol`：股票代码列名目前仍保留为 `symbol`
- `name`：股票名称
- `recommend_date`：你记录的推荐日期，格式必须是 `YYYY-MM-DD`
- `recommend_time`：可选，推荐时刻，格式为 `HH:MM`
- `recommend_price`：可选，推荐时刻股价；填写后优先使用该价格，不再依赖分钟行情回查
- `note`：可选备注

补充规则：

- CSV 行可以乱序，脚本会自动按日期和 `id` 排序写回
- 同一只股票允许多次出现
- 同一天同一只股票出现多次时，会自动生成不同的事件 `id`
- 支持直接填 A 股代码：`600519`、`000001`、`300750`
- 也兼容 A 股后缀：`600519.SH`、`600519.SS`、`000001.SZ`
- 支持直接填港股代码：`0700`、`0005`、`1810`
- 也兼容港股后缀：`0700.HK`、`0005.HK`

## 页面现在展示什么

网页默认按股票分组展示，同时支持切换到按事件平铺。

当前核心指标：

- 推荐日建仓价
- 推荐时刻股价与价格来源
- 当前价与当前收益率
- 5 日收益
- 10 日收益
- 20 日收益
- 最大涨幅
- 最大回撤
- 是否盈利

展示规则：

- 同一只股票多次推荐时，默认折叠为首条记录，可手动展开
- 页面支持按标签筛选；每个标签下的股票分组彼此独立
- 展开后，后续推荐会显示在同组内
- 多次推荐的股票，在展开状态下才会显示“第 N 次推荐”
- 5 日、10 日、20 日、最大涨幅、最大回撤都会额外显示对应价格
- 如果没有填写推荐时间，推荐价沿用推荐日收盘价；如果推荐日不是交易日，会显示成 `MM-DD(顺延)收盘`
- 如果填写了推荐时间，推荐价会优先使用 1 分钟行情，页面只显示时间，例如 `09:32`
- 如果填写了 `recommend_price`，页面会显示 `09:32(手填)`；如果走日线收盘价，页面会显示 `MM-DD收盘`

## 异常和兜底

更新脚本不会因为个别坏数据把整次更新打断。

### 失败记录

以下情况会进入失败列表，而不是导致整次更新失败：

- 空字段
- 日期格式错误
- 非法 A 股代码
- 重复 `id`
- 抓价失败

### 待跟踪记录

如果推荐日期之后暂时还没有可用交易日，这条记录不会进入失败列表，而会进入“待跟踪”：

- 未来日期
- 当天还没出可用日线
- 推荐后暂无后续交易日

## 本地调试

刷新数据：

```bash
python3 scripts/update_data.py
python3 scripts/update_data.py --max-workers 4
```

刷新耗时说明：

- 当前脚本按唯一股票并发请求行情，默认 `--max-workers 8`
- 每只唯一股票至少请求一次日线；填写了 `recommend_time` 且没有 `recommend_price` 的记录会额外请求分钟行情
- 如果腾讯接口偶发超时，脚本会对单次请求做轻量重试；如果你想更保守，可以把 `--max-workers` 调小

启动本地静态服务：

```bash
python3 -m http.server 8000 --directory docs
```

然后访问 `http://localhost:8000`。

如果直接双击打开 `docs/index.html`，浏览器通常会因为本地 `fetch` 限制而读不到 `metrics.json`。

## 部署到 GitHub Pages

当前仓库已经使用 GitHub Pages + GitHub Actions 方案，工作流文件是 `.github/workflows/pages.yml`。

工作流触发方式：

- push 到 `main`
- 手动 `Run workflow`
- 定时任务：北京时间工作日 `09:00 / 09:30 / 10:00 / 10:30 / 11:00 / 11:30 / 13:00 / 13:30 / 14:00 / 14:30 / 15:00`

如果你希望继续免费使用 GitHub Actions + GitHub Pages，最简单的方式是保持仓库为公开仓库。

## 目录结构

```text
.
├── .github/workflows/pages.yml
├── docs/
│   ├── index.html
│   ├── app.js
│   ├── styles.css
│   └── data/
│       ├── recommendations.csv
│       └── metrics.json
├── scripts/
│   ├── manage_recommendations.py
│   └── update_data.py
└── README.md
```

## 指标口径

- 推荐价：优先使用手工 `recommend_price`；否则若有 `recommend_time`，使用推荐时刻之后第一条 1 分钟行情价格；否则使用推荐日当天收盘价，若当天不是交易日则顺延到下一个交易日
- 当前价：最新一个可用交易日收盘价
- 收益率：`当前价 / 建仓价 - 1`
- 5 日 / 10 日 / 20 日收益：推荐后第 5 / 10 / 20 个交易日相对建仓价的收益
- 最大涨幅：推荐后区间最高价相对建仓价的涨幅
- 最大回撤：推荐后按收盘价序列计算的区间最大回撤
- 是否盈利：当前收益率是否大于 0
