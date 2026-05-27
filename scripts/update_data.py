#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo



TENCENT_A_CHART_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,,,{count},qfq"
TENCENT_HK_CHART_URL = "https://web.ifzq.gtimg.cn/appstock/app/hkfqkline/get?param={symbol},day,,,{count},qfq"
TENCENT_MINUTE_KLINE_URL = "https://ifzq.gtimg.cn/appstock/app/kline/mkline?param={symbol},m1,,{count}"
TENCENT_MINUTE_QUERY_URL = "https://web.ifzq.gtimg.cn/appstock/app/minute/query?code={symbol}"


class PendingTrackingError(RuntimeError):
  """Raised when a recommendation exists but cannot be priced yet."""


@dataclass
class Recommendation:
    id: str
    recommender: str
    symbol: str
    query_symbol: str
    name: str
    recommend_date: dt.date
    recommend_time: dt.time | None
    recommend_price: float | None
    note: str


def normalize_symbol(raw_symbol: str) -> str:
  symbol = raw_symbol.strip().upper()
  if not symbol:
    raise ValueError("Empty symbol")

  if re.fullmatch(r"\d{6}", symbol):
    if symbol.startswith(("5", "6", "9")):
      return f"{symbol}.SS"
    if symbol.startswith(("0", "2", "3")):
      return f"{symbol}.SZ"

  if re.fullmatch(r"\d{1,5}", symbol):
    return f"{symbol.zfill(4) if len(symbol) < 4 else symbol}.HK"

  if symbol.endswith(".SH"):
    return symbol[:-3] + ".SS"

  if symbol.endswith(".HK"):
    code = symbol[:-3]
    if re.fullmatch(r"\d{1,5}", code):
      return f"{code.zfill(4) if len(code) < 4 else code}.HK"

  if re.fullmatch(r"\d{6}\.(SS|SZ)", symbol):
    return symbol

  if re.fullmatch(r"\d{4,5}\.HK", symbol):
    return symbol

  return symbol


def validate_symbol(raw_symbol: str) -> str:
  normalized = normalize_symbol(raw_symbol)
  if re.fullmatch(r"\d{6}\.(SS|SZ)", normalized) or re.fullmatch(r"\d{4,5}\.HK", normalized):
    return normalized
  raise ValueError("Invalid A-share or HK symbol format")


def sanitize_id(raw_id: str) -> str:
  value = raw_id.strip()
  if not value:
    raise ValueError("Empty id")
  if not re.fullmatch(r"[A-Za-z0-9._-]+", value):
    raise ValueError("id 只能包含字母、数字、点、下划线、中划线")
  return value


def generate_recommendation_id(symbol: str, recommend_date: str, row_number: int) -> str:
  compact_symbol = re.sub(r"[^A-Za-z0-9]+", "", symbol.upper()) or "UNKNOWN"
  compact_date = re.sub(r"[^0-9]+", "", recommend_date) or "00000000"
  return f"{compact_date}-{compact_symbol}-{row_number}"


def normalize_recommender(raw_recommender: str) -> str:
  return raw_recommender.strip() or "默认"


def parse_recommend_time(raw_time: str) -> dt.time | None:
  value = raw_time.strip()
  if not value:
    return None

  for fmt in ("%H:%M", "%H:%M:%S"):
    try:
      parsed = dt.datetime.strptime(value, fmt).time()
      return parsed.replace(second=0, microsecond=0)
    except ValueError:
      pass

  raise ValueError("recommend_time 必须是 HH:MM 或 HH:MM:SS")


def parse_recommend_price(raw_price: str) -> float | None:
  value = raw_price.strip()
  if not value:
    return None

  try:
    price = float(value)
  except ValueError as exc:
    raise ValueError("recommend_price 必须是数字") from exc

  if price <= 0:
    raise ValueError("recommend_price 必须大于 0")
  return price


def read_recommendations(csv_path: Path) -> tuple[list[Recommendation], list[dict]]:
  recommendations: list[Recommendation] = []
  failures: list[dict] = []
  seen_ids: set[str] = set()

  with csv_path.open("r", encoding="utf-8") as fh:
    reader = csv.DictReader(fh)
    for row_number, row in enumerate(reader, start=2):
      raw_id = (row.get("id") or "").strip()
      recommender = normalize_recommender(row.get("recommender") or "")
      symbol = (row.get("symbol") or "").strip()
      name = (row.get("name") or "").strip()
      recommend_date = (row.get("recommend_date") or "").strip()
      raw_recommend_time = (row.get("recommend_time") or "").strip()
      raw_recommend_price = (row.get("recommend_price") or "").strip()
      note = (row.get("note") or "").strip()

      if not any([raw_id, symbol, name, recommend_date, raw_recommend_time, raw_recommend_price, note]):
        continue

      if not symbol:
        failures.append(
          {
            "id": raw_id or generate_recommendation_id(symbol, recommend_date, row_number),
            "recommender": recommender,
            "symbol": "",
            "name": name,
            "recommend_date": recommend_date or "",
            "error": f"CSV 第 {row_number} 行缺少 symbol",
          }
        )
        continue

      if not recommend_date:
        failures.append(
          {
            "id": raw_id or generate_recommendation_id(symbol, recommend_date, row_number),
            "recommender": recommender,
            "symbol": symbol,
            "name": name,
            "recommend_date": "",
            "error": f"CSV 第 {row_number} 行缺少 recommend_date",
          }
        )
        continue

      try:
        parsed_date = dt.date.fromisoformat(recommend_date)
      except ValueError:
        failures.append(
          {
            "id": raw_id or generate_recommendation_id(symbol, recommend_date, row_number),
            "recommender": recommender,
            "symbol": symbol,
            "name": name,
            "recommend_date": recommend_date,
            "error": f"CSV 第 {row_number} 行日期格式错误，要求 YYYY-MM-DD",
          }
        )
        continue

      try:
        parsed_time = parse_recommend_time(raw_recommend_time)
      except ValueError as exc:
        failures.append(
          {
            "id": raw_id or generate_recommendation_id(symbol, recommend_date, row_number),
            "recommender": recommender,
            "symbol": symbol,
            "name": name,
            "recommend_date": recommend_date,
            "recommend_time": raw_recommend_time,
            "error": f"CSV 第 {row_number} 行推荐时间格式错误：{exc}",
          }
        )
        continue

      try:
        parsed_price = parse_recommend_price(raw_recommend_price)
      except ValueError as exc:
        failures.append(
          {
            "id": raw_id or generate_recommendation_id(symbol, recommend_date, row_number),
            "recommender": recommender,
            "symbol": symbol,
            "name": name,
            "recommend_date": recommend_date,
            "recommend_time": raw_recommend_time,
            "error": f"CSV 第 {row_number} 行推荐价格格式错误：{exc}",
          }
        )
        continue

      try:
        query_symbol = validate_symbol(symbol)
      except ValueError as exc:
        failures.append(
          {
            "id": raw_id or generate_recommendation_id(symbol, recommend_date, row_number),
            "recommender": recommender,
            "symbol": symbol,
            "name": name,
            "recommend_date": recommend_date,
            "error": f"CSV 第 {row_number} 行代码格式错误：{exc}",
          }
        )
        continue

      recommendation_id = raw_id or generate_recommendation_id(symbol, recommend_date, row_number)
      try:
        recommendation_id = sanitize_id(recommendation_id)
      except ValueError as exc:
        failures.append(
          {
            "id": raw_id or recommendation_id,
            "recommender": recommender,
            "symbol": symbol,
            "name": name,
            "recommend_date": recommend_date,
            "error": f"CSV 第 {row_number} 行 id 格式错误：{exc}",
          }
        )
        continue

      if recommendation_id in seen_ids:
        failures.append(
          {
            "id": recommendation_id,
            "recommender": recommender,
            "symbol": symbol,
            "name": name,
            "recommend_date": recommend_date,
            "error": f"CSV 第 {row_number} 行 id 重复：{recommendation_id}",
          }
        )
        continue
      seen_ids.add(recommendation_id)

      recommendations.append(
        Recommendation(
          id=recommendation_id,
          recommender=recommender,
          symbol=symbol,
          query_symbol=query_symbol,
          name=name,
          recommend_date=parsed_date,
          recommend_time=parsed_time,
          recommend_price=parsed_price,
          note=note,
        )
      )

  return recommendations, failures


def tencent_symbol(symbol: str) -> tuple[str, str]:
  if symbol.endswith(".SS"):
    return "a", f"sh{symbol[:-3]}"
  if symbol.endswith(".SZ"):
    return "a", f"sz{symbol[:-3]}"
  if symbol.endswith(".HK"):
    return "hk", f"hk{symbol[:-3].zfill(5)}"
  raise ValueError(f"Unsupported market symbol: {symbol}")


def parse_minute_rows(raw_rows: list, target_date: dt.date | None) -> list[dict]:
  bars = []
  for raw_bar in raw_rows:
    if isinstance(raw_bar, list):
      if len(raw_bar) < 3:
        continue
      timestamp = str(raw_bar[0])
      if not re.fullmatch(r"\d{12}", timestamp):
        continue
      bar_date = dt.date.fromisoformat(f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}")
      bar_time = dt.time(int(timestamp[8:10]), int(timestamp[10:12]))
      close = raw_bar[2]
    elif isinstance(raw_bar, str):
      parts = raw_bar.split()
      if len(parts) < 2 or target_date is None:
        continue
      time_text = parts[0]
      if not re.fullmatch(r"\d{4}", time_text):
        continue
      bar_date = target_date
      bar_time = dt.time(int(time_text[:2]), int(time_text[2:4]))
      close = parts[1]
    else:
      continue

    if close in (None, ""):
      continue

    bars.append(
      {
        "date": bar_date,
        "time": bar_time,
        "price": float(close),
      }
    )

  return bars


def tencent_minute_history(symbol: str, target_date: dt.date, today: dt.date) -> list[dict]:
  market, provider_symbol = tencent_symbol(symbol)

  if market == "a":
    # This unofficial endpoint returns recent 1-minute bars, but does not reliably
    # honor arbitrary historical date parameters.
    request = urllib.request.Request(
      TENCENT_MINUTE_KLINE_URL.format(symbol=provider_symbol, count=800),
      headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
      },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
      payload = json.loads(response.read().decode("utf-8"))

    if payload.get("code") not in (0, "0"):
      raise RuntimeError(payload.get("msg") or "Tencent minute API error")

    result_item = (payload.get("data") or {}).get(provider_symbol)
    raw_rows = (result_item or {}).get("m1") or []
    return parse_minute_rows(raw_rows, None)

  if target_date != today:
    raise RuntimeError("腾讯港股分钟接口仅稳定返回当日分时，历史港股推荐价请填写 recommend_price")

  request = urllib.request.Request(
    TENCENT_MINUTE_QUERY_URL.format(symbol=provider_symbol),
    headers={
      "User-Agent": "Mozilla/5.0",
      "Accept": "application/json",
    },
  )
  with urllib.request.urlopen(request, timeout=20) as response:
    payload = json.loads(response.read().decode("utf-8"))

  if payload.get("code") not in (0, "0"):
    raise RuntimeError(payload.get("msg") or "Tencent minute API error")

  result_item = (payload.get("data") or {}).get(provider_symbol)
  raw_rows = (((result_item or {}).get("data") or {}).get("data")) or []
  return parse_minute_rows(raw_rows, target_date)


def first_minute_on_or_after(minute_bars: list[dict], target_date: dt.date, target_time: dt.time) -> dict | None:
  same_day_bars = sorted(
    (bar for bar in minute_bars if bar["date"] == target_date),
    key=lambda item: item["time"],
  )
  for bar in same_day_bars:
    if bar["time"] >= target_time:
      return bar
  return None


def tencent_history(symbol: str, start_date: dt.date, end_date: dt.date) -> list[dict]:
  market, provider_symbol = tencent_symbol(symbol)
  bar_count = min(max((end_date - start_date).days * 2 + 60, 120), 5000)
  url_template = TENCENT_HK_CHART_URL if market == "hk" else TENCENT_A_CHART_URL
  url = url_template.format(symbol=provider_symbol, count=bar_count)
  request = urllib.request.Request(
    url,
    headers={
      "User-Agent": "Mozilla/5.0",
      "Accept": "application/json",
    },
  )

  with urllib.request.urlopen(request, timeout=20) as response:
    payload = json.loads(response.read().decode("utf-8"))

  if payload.get("code") not in (0, "0"):
    raise RuntimeError(payload.get("msg") or "Tencent quote API error")

  result_item = (payload.get("data") or {}).get(provider_symbol)
  if not result_item:
    raise RuntimeError("No quote result returned")

  raw_bars = result_item.get("qfqday") or result_item.get("day") or []
  if not raw_bars:
    raise RuntimeError("No market data returned")

  bars = []
  for raw_bar in raw_bars:
    if len(raw_bar) < 6:
      continue
    bar_date = dt.date.fromisoformat(str(raw_bar[0]))
    if bar_date < start_date or bar_date > end_date:
      continue

    close = raw_bar[2]
    if close is None or close == "":
      continue

    bars.append(
      {
        "date": bar_date,
        "open": float(raw_bar[1]) if raw_bar[1] not in (None, "") else None,
        "high": float(raw_bar[3]) if raw_bar[3] not in (None, "") else float(close),
        "low": float(raw_bar[4]) if raw_bar[4] not in (None, "") else float(close),
        "close": float(close),
        "volume": float(raw_bar[5]) if raw_bar[5] not in (None, "") else None,
      }
    )

  return bars


def first_index_on_or_after(bars: list[dict], target_date: dt.date) -> int | None:
  for idx, bar in enumerate(bars):
    if bar["date"] >= target_date:
      return idx
  return None


def calculate_max_drawdown(closes: list[float]) -> tuple[float | None, float | None]:
  if not closes:
    return None, None

  peak = closes[0]
  max_drawdown = 0.0
  trough_price = closes[0]

  for close in closes:
    peak = max(peak, close)
    drawdown = close / peak - 1
    if drawdown < max_drawdown:
      max_drawdown = drawdown
      trough_price = close

  return max_drawdown, trough_price


def resolve_entry_price(rec: Recommendation, entry_bar: dict, minute_bars: list[dict] | None) -> tuple[float, str | None, str]:
  if rec.recommend_price is not None:
    return rec.recommend_price, rec.recommend_time.strftime("%H:%M") if rec.recommend_time else None, "manual"

  if rec.recommend_time is not None:
    if minute_bars is None:
      raise RuntimeError("缺少分钟行情，无法计算推荐时刻股价")

    minute_bar = first_minute_on_or_after(minute_bars, rec.recommend_date, rec.recommend_time)
    if minute_bar is None:
      raise RuntimeError("推荐时间之后暂无可用 1 分钟行情；历史记录可手工填写 recommend_price 兜底")

    return float(minute_bar["price"]), minute_bar["time"].strftime("%H:%M"), "minute_1m"

  return float(entry_bar["close"]), None, "daily_close"


def compute_record(rec: Recommendation, bars: list[dict], minute_bars: list[dict] | None = None) -> dict:
  entry_index = first_index_on_or_after(bars, rec.recommend_date)
  if entry_index is None:
    raise PendingTrackingError("推荐日期之后暂无可用交易数据，等待下一个交易日")

  entry_bar = bars[entry_index]
  entry_price, entry_time, entry_price_source = resolve_entry_price(rec, entry_bar, minute_bars)
  current_bar = bars[-1]
  current_price = float(current_bar["close"])

  closes_since_entry = [float(bar["close"]) for bar in bars[entry_index:]]
  highs_since_entry = [float(bar["high"]) for bar in bars[entry_index:] if bar["high"] is not None]

  bar_5d = bars[entry_index + 5] if entry_index + 5 < len(bars) else None
  bar_10d = bars[entry_index + 10] if entry_index + 10 < len(bars) else None
  bar_20d = bars[entry_index + 20] if entry_index + 20 < len(bars) else None

  return_rate = current_price / entry_price - 1
  return_5d_price = float(bar_5d["close"]) if bar_5d else None
  return_10d_price = float(bar_10d["close"]) if bar_10d else None
  return_20d_price = float(bar_20d["close"]) if bar_20d else None
  return_5d = (return_5d_price / entry_price - 1) if return_5d_price is not None else None
  return_10d = (return_10d_price / entry_price - 1) if return_10d_price is not None else None
  return_20d = (return_20d_price / entry_price - 1) if return_20d_price is not None else None
  max_gain_price = max(highs_since_entry) if highs_since_entry else None
  max_gain = max_gain_price / entry_price - 1 if max_gain_price is not None else None
  max_drawdown, max_drawdown_price = calculate_max_drawdown(closes_since_entry)

  return {
    "id": rec.id,
    "recommender": rec.recommender,
    "symbol": rec.symbol,
    "query_symbol": rec.query_symbol,
    "name": rec.name,
    "note": rec.note,
    "recommend_date": rec.recommend_date.isoformat(),
    "recommend_time": rec.recommend_time.strftime("%H:%M") if rec.recommend_time else None,
    "entry_date": entry_bar["date"].isoformat(),
    "entry_time": entry_time,
    "entry_price": round(entry_price, 4),
    "entry_price_source": entry_price_source,
    "current_price": round(current_price, 4),
    "return_rate": round(return_rate, 6),
    "return_5d": round(return_5d, 6) if return_5d is not None else None,
    "return_5d_price": round(return_5d_price, 4) if return_5d_price is not None else None,
    "return_10d": round(return_10d, 6) if return_10d is not None else None,
    "return_10d_price": round(return_10d_price, 4) if return_10d_price is not None else None,
    "return_20d": round(return_20d, 6) if return_20d is not None else None,
    "return_20d_price": round(return_20d_price, 4) if return_20d_price is not None else None,
    "max_gain": round(max_gain, 6) if max_gain is not None else None,
    "max_gain_price": round(max_gain_price, 4) if max_gain_price is not None else None,
    "max_drawdown": round(max_drawdown, 6) if max_drawdown is not None else None,
    "max_drawdown_price": round(max_drawdown_price, 4) if max_drawdown_price is not None else None,
    "is_profitable": return_rate > 0,
    "current_date": current_bar["date"].isoformat(),
  }


def annotate_recommendation_sequences(records: list[dict]) -> list[dict]:
  grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
  for record in records:
    grouped[(record.get("recommender") or "默认", record["symbol"])].append(record)

  for symbol_records in grouped.values():
    symbol_records.sort(key=lambda item: (item["recommend_date"], item["id"]))
    total = len(symbol_records)
    for index, record in enumerate(symbol_records, start=1):
      record["recommendation_sequence"] = index
      record["recommendation_count_for_symbol"] = total

  return records


def build_stock_summaries(records: list[dict]) -> list[dict]:
  grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
  for record in records:
    grouped[(record.get("recommender") or "默认", record["symbol"])].append(record)

  summaries = []
  for (recommender, symbol), symbol_records in grouped.items():
    symbol_records.sort(key=lambda item: (item["recommend_date"], item["id"]))
    profitable = sum(1 for item in symbol_records if item["is_profitable"])

    summaries.append(
      {
        "symbol": symbol,
        "recommender": recommender,
        "name": symbol_records[-1]["name"],
        "recommendation_count": len(symbol_records),
        "profitable_count": profitable,
        "win_rate": round(profitable / len(symbol_records), 6),
        "average_return": average([item["return_rate"] for item in symbol_records]),
        "latest_return": symbol_records[-1]["return_rate"],
        "first_recommend_date": symbol_records[0]["recommend_date"],
        "latest_recommend_date": symbol_records[-1]["recommend_date"],
      }
    )

  summaries.sort(
    key=lambda item: (item["latest_recommend_date"], item["symbol"]),
    reverse=True,
  )
  return summaries


def average(values: list[float | None]) -> float | None:
  valid = [value for value in values if value is not None and not math.isnan(value)]
  if not valid:
    return None
  return round(statistics.fmean(valid), 6)


def refresh_context(now: dt.datetime) -> dict:
  trigger = (os.environ.get("REFRESH_TRIGGER") or "local").strip().lower()
  trigger_map = {
    "schedule": "定时触发",
    "workflow_dispatch": "手动触发",
    "push": "推送触发",
    "local": "本地刷新",
  }

  return {
    "trigger": trigger,
    "trigger_label": trigger_map.get(trigger, trigger or "未知触发"),
    "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
  }


def build_summary(records: list[dict]) -> dict:
  first_records_by_symbol: dict[str, dict] = {}
  for record in sorted(records, key=lambda item: (item["recommend_date"], item["id"])):
    summary_key = f"{record.get('recommender') or '默认'}|{record['symbol']}"
    first_records_by_symbol.setdefault(summary_key, record)

  summary_records = list(first_records_by_symbol.values())
  total = len(records)
  profitable = sum(1 for record in summary_records if record.get("is_profitable"))

  return {
    "total_picks": total,
    "unique_symbols": len({record["symbol"] for record in records}),
    "summary_basis": "first_recommendation_by_recommender_symbol",
    "summary_basis_count": len(summary_records),
    "profitable_picks": profitable,
    "win_rate": round(profitable / len(summary_records), 6) if summary_records else None,
    "average_return": average([record.get("return_rate") for record in summary_records]),
    "average_return_5d": average([record.get("return_5d") for record in summary_records]),
    "average_return_10d": average([record.get("return_10d") for record in summary_records]),
    "average_return_20d": average([record.get("return_20d") for record in summary_records]),
  }


def main() -> int:
  parser = argparse.ArgumentParser(description="Update stock tracking metrics.")
  parser.add_argument(
    "--input",
    default="docs/data/recommendations.csv",
    help="Path to the recommendation CSV file.",
  )
  parser.add_argument(
    "--output",
    default="docs/data/metrics.json",
    help="Path to the generated metrics JSON file.",
  )
  args = parser.parse_args()

  input_path = Path(args.input)
  output_path = Path(args.output)
  recommendations, failures = read_recommendations(input_path)
  output_path.parent.mkdir(parents=True, exist_ok=True)

  records = []
  today = dt.date.today()
  pending_records = []
  bars_cache: dict[str, list[dict]] = {}
  minute_bars_cache: dict[tuple[str, dt.date], list[dict]] = {}

  for rec in recommendations:
    try:
      start_date = rec.recommend_date - dt.timedelta(days=14)
      bars = bars_cache.get(rec.query_symbol)
      if bars is None:
        bars = tencent_history(rec.query_symbol, start_date=start_date, end_date=today)
        bars_cache[rec.query_symbol] = bars
        time.sleep(0.2)
      if not bars:
        raise RuntimeError("No market data returned")

      minute_bars = None
      if rec.recommend_time is not None and rec.recommend_price is None:
        minute_cache_key = (rec.query_symbol, rec.recommend_date)
        minute_bars = minute_bars_cache.get(minute_cache_key)
        if minute_bars is None:
          minute_bars = tencent_minute_history(rec.query_symbol, rec.recommend_date, today)
          minute_bars_cache[minute_cache_key] = minute_bars
          time.sleep(0.2)

      records.append(compute_record(rec, bars, minute_bars))
    except PendingTrackingError as exc:
      pending_records.append(
        {
          "id": rec.id,
          "recommender": rec.recommender,
          "symbol": rec.symbol,
          "query_symbol": rec.query_symbol,
          "name": rec.name,
          "recommend_date": rec.recommend_date.isoformat(),
          "recommend_time": rec.recommend_time.strftime("%H:%M") if rec.recommend_time else None,
          "status": "pending_tracking",
          "message": str(exc),
        }
      )
    except (urllib.error.URLError, RuntimeError, ValueError) as exc:
      failures.append(
        {
          "id": rec.id,
          "recommender": rec.recommender,
          "symbol": rec.symbol,
          "query_symbol": rec.query_symbol,
          "name": rec.name,
          "recommend_date": rec.recommend_date.isoformat(),
          "recommend_time": rec.recommend_time.strftime("%H:%M") if rec.recommend_time else None,
          "error": str(exc),
        }
      )

  annotate_recommendation_sequences(records)
  records.sort(key=lambda item: item["recommend_date"], reverse=True)
  stock_summaries = build_stock_summaries(records)
  now = dt.datetime.now(ZoneInfo("Asia/Shanghai"))
  context = refresh_context(now)
  payload = {
    "generated_at": context["generated_at"],
    "refresh_context": context,
    "summary": build_summary(records),
    "records": records,
    "stock_summaries": stock_summaries,
    "pending_records": pending_records,
    "failures": failures,
  }

  with output_path.open("w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False, indent=2)
    fh.write("\n")

  return 0


if __name__ == "__main__":
  sys.exit(main())
