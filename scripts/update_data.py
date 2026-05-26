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
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo



YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


class PendingTrackingError(RuntimeError):
  """Raised when a recommendation exists but cannot be priced yet."""


@dataclass
class Recommendation:
    id: str
    symbol: str
    query_symbol: str
    name: str
    recommend_date: dt.date
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


def read_recommendations(csv_path: Path) -> tuple[list[Recommendation], list[dict]]:
  recommendations: list[Recommendation] = []
  failures: list[dict] = []
  seen_ids: set[str] = set()

  with csv_path.open("r", encoding="utf-8") as fh:
    reader = csv.DictReader(fh)
    for row_number, row in enumerate(reader, start=2):
      raw_id = (row.get("id") or "").strip()
      symbol = (row.get("symbol") or "").strip()
      name = (row.get("name") or "").strip()
      recommend_date = (row.get("recommend_date") or "").strip()
      note = (row.get("note") or "").strip()

      if not any([raw_id, symbol, name, recommend_date, note]):
        continue

      if not symbol:
        failures.append(
          {
            "id": raw_id or generate_recommendation_id(symbol, recommend_date, row_number),
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
            "symbol": symbol,
            "name": name,
            "recommend_date": recommend_date,
            "error": f"CSV 第 {row_number} 行日期格式错误，要求 YYYY-MM-DD",
          }
        )
        continue

      try:
        query_symbol = validate_symbol(symbol)
      except ValueError as exc:
        failures.append(
          {
            "id": raw_id or generate_recommendation_id(symbol, recommend_date, row_number),
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
          symbol=symbol,
          query_symbol=query_symbol,
          name=name,
          recommend_date=parsed_date,
          note=note,
        )
      )

  return recommendations, failures


def yahoo_history(symbol: str, start_date: dt.date, end_date: dt.date) -> list[dict]:
  period1 = int(dt.datetime.combine(start_date, dt.time.min, tzinfo=dt.timezone.utc).timestamp())
  period2 = int(dt.datetime.combine(end_date + dt.timedelta(days=1), dt.time.min, tzinfo=dt.timezone.utc).timestamp())
  query = urllib.parse.urlencode(
    {
      "period1": period1,
      "period2": period2,
      "interval": "1d",
      "includePrePost": "false",
      "events": "div,splits",
    }
  )
  url = YAHOO_CHART_URL.format(symbol=urllib.parse.quote(symbol)) + f"?{query}"
  request = urllib.request.Request(
    url,
    headers={
      "User-Agent": "Mozilla/5.0",
      "Accept": "application/json",
    },
  )

  with urllib.request.urlopen(request, timeout=20) as response:
    payload = json.loads(response.read().decode("utf-8"))

  result = payload.get("chart", {}).get("result")
  error = payload.get("chart", {}).get("error")
  if error:
    raise RuntimeError(error.get("description") or "Yahoo Finance API error")
  if not result:
    raise RuntimeError("No chart result returned")

  result_item = result[0]
  timestamps = result_item.get("timestamp") or []
  quote = (result_item.get("indicators", {}).get("quote") or [{}])[0]

  opens = quote.get("open") or []
  highs = quote.get("high") or []
  lows = quote.get("low") or []
  closes = quote.get("close") or []
  volumes = quote.get("volume") or []

  bars = []
  for idx, stamp in enumerate(timestamps):
    close = closes[idx] if idx < len(closes) else None
    if close is None:
      continue

    bars.append(
      {
        "date": dt.datetime.fromtimestamp(stamp, tz=dt.timezone.utc).date(),
        "open": opens[idx] if idx < len(opens) else None,
        "high": highs[idx] if idx < len(highs) else close,
        "low": lows[idx] if idx < len(lows) else close,
        "close": close,
        "volume": volumes[idx] if idx < len(volumes) else None,
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


def compute_record(rec: Recommendation, bars: list[dict]) -> dict:
  entry_index = first_index_on_or_after(bars, rec.recommend_date)
  if entry_index is None:
    raise PendingTrackingError("推荐日期之后暂无可用交易数据，等待下一个交易日")

  entry_bar = bars[entry_index]
  entry_price = float(entry_bar["close"])
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
    "symbol": rec.symbol,
    "query_symbol": rec.query_symbol,
    "name": rec.name,
    "note": rec.note,
    "recommend_date": rec.recommend_date.isoformat(),
    "entry_date": entry_bar["date"].isoformat(),
    "entry_price": round(entry_price, 4),
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
  grouped: dict[str, list[dict]] = defaultdict(list)
  for record in records:
    grouped[record["symbol"]].append(record)

  for symbol_records in grouped.values():
    symbol_records.sort(key=lambda item: (item["recommend_date"], item["id"]))
    total = len(symbol_records)
    for index, record in enumerate(symbol_records, start=1):
      record["recommendation_sequence"] = index
      record["recommendation_count_for_symbol"] = total

  return records


def build_stock_summaries(records: list[dict]) -> list[dict]:
  grouped: dict[str, list[dict]] = defaultdict(list)
  for record in records:
    grouped[record["symbol"]].append(record)

  summaries = []
  for symbol, symbol_records in grouped.items():
    symbol_records.sort(key=lambda item: (item["recommend_date"], item["id"]))
    profitable = sum(1 for item in symbol_records if item["is_profitable"])

    summaries.append(
      {
        "symbol": symbol,
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
  total = len(records)
  profitable = sum(1 for record in records if record.get("is_profitable"))

  return {
    "total_picks": total,
    "unique_symbols": len({record["symbol"] for record in records}),
    "profitable_picks": profitable,
    "win_rate": round(profitable / total, 6) if total else None,
    "average_return": average([record.get("return_rate") for record in records]),
    "average_return_5d": average([record.get("return_5d") for record in records]),
    "average_return_10d": average([record.get("return_10d") for record in records]),
    "average_return_20d": average([record.get("return_20d") for record in records]),
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

  for rec in recommendations:
    try:
      start_date = rec.recommend_date - dt.timedelta(days=14)
      bars = yahoo_history(rec.query_symbol, start_date=start_date, end_date=today)
      if not bars:
        raise RuntimeError("No market data returned")
      records.append(compute_record(rec, bars))
      time.sleep(0.4)
    except PendingTrackingError as exc:
      pending_records.append(
        {
          "id": rec.id,
          "symbol": rec.symbol,
          "query_symbol": rec.query_symbol,
          "name": rec.name,
          "recommend_date": rec.recommend_date.isoformat(),
          "status": "pending_tracking",
          "message": str(exc),
        }
      )
    except (urllib.error.URLError, RuntimeError, ValueError) as exc:
      failures.append(
        {
          "id": rec.id,
          "symbol": rec.symbol,
          "query_symbol": rec.query_symbol,
          "name": rec.name,
          "recommend_date": rec.recommend_date.isoformat(),
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
