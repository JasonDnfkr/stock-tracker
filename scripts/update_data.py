#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


@dataclass
class Recommendation:
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

  if symbol.endswith(".SH"):
    return symbol[:-3] + ".SS"

  return symbol


def read_recommendations(csv_path: Path) -> list[Recommendation]:
  recommendations: list[Recommendation] = []

  with csv_path.open("r", encoding="utf-8") as fh:
    reader = csv.DictReader(fh)
    for row in reader:
      symbol = (row.get("symbol") or "").strip()
      recommend_date = (row.get("recommend_date") or "").strip()
      if not symbol or not recommend_date:
        continue

      recommendations.append(
        Recommendation(
          symbol=symbol,
          query_symbol=normalize_symbol(symbol),
          name=(row.get("name") or "").strip(),
          recommend_date=dt.date.fromisoformat(recommend_date),
          note=(row.get("note") or "").strip(),
        )
      )

  return recommendations


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


def calculate_max_drawdown(closes: list[float]) -> float | None:
  if not closes:
    return None

  peak = closes[0]
  max_drawdown = 0.0

  for close in closes:
    peak = max(peak, close)
    drawdown = close / peak - 1
    max_drawdown = min(max_drawdown, drawdown)

  return max_drawdown


def compute_record(rec: Recommendation, bars: list[dict]) -> dict:
  entry_index = first_index_on_or_after(bars, rec.recommend_date)
  if entry_index is None:
    raise RuntimeError("No trading day found on or after recommend_date")

  entry_bar = bars[entry_index]
  entry_price = float(entry_bar["close"])
  current_bar = bars[-1]
  current_price = float(current_bar["close"])

  closes_since_entry = [float(bar["close"]) for bar in bars[entry_index:]]
  highs_since_entry = [float(bar["high"]) for bar in bars[entry_index:] if bar["high"] is not None]

  bar_5d = bars[entry_index + 5] if entry_index + 5 < len(bars) else None
  bar_20d = bars[entry_index + 20] if entry_index + 20 < len(bars) else None

  return_rate = current_price / entry_price - 1
  return_5d = (float(bar_5d["close"]) / entry_price - 1) if bar_5d else None
  return_20d = (float(bar_20d["close"]) / entry_price - 1) if bar_20d else None
  max_gain = max(highs_since_entry) / entry_price - 1 if highs_since_entry else None
  max_drawdown = calculate_max_drawdown(closes_since_entry)

  return {
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
    "return_20d": round(return_20d, 6) if return_20d is not None else None,
    "max_gain": round(max_gain, 6) if max_gain is not None else None,
    "max_drawdown": round(max_drawdown, 6) if max_drawdown is not None else None,
    "is_profitable": return_rate > 0,
    "current_date": current_bar["date"].isoformat(),
  }


def average(values: list[float | None]) -> float | None:
  valid = [value for value in values if value is not None and not math.isnan(value)]
  if not valid:
    return None
  return round(statistics.fmean(valid), 6)


def build_summary(records: list[dict]) -> dict:
  total = len(records)
  profitable = sum(1 for record in records if record.get("is_profitable"))

  return {
    "total_picks": total,
    "profitable_picks": profitable,
    "win_rate": round(profitable / total, 6) if total else None,
    "average_return": average([record.get("return_rate") for record in records]),
    "average_return_5d": average([record.get("return_5d") for record in records]),
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
  recommendations = read_recommendations(input_path)
  output_path.parent.mkdir(parents=True, exist_ok=True)

  records = []
  failures = []
  today = dt.date.today()

  for rec in recommendations:
    try:
      start_date = rec.recommend_date - dt.timedelta(days=14)
      bars = yahoo_history(rec.query_symbol, start_date=start_date, end_date=today)
      if not bars:
        raise RuntimeError("No market data returned")
      records.append(compute_record(rec, bars))
      time.sleep(0.4)
    except (urllib.error.URLError, RuntimeError, ValueError) as exc:
      failures.append(
        {
          "symbol": rec.symbol,
          "query_symbol": rec.query_symbol,
          "name": rec.name,
          "recommend_date": rec.recommend_date.isoformat(),
          "error": str(exc),
        }
      )

  records.sort(key=lambda item: item["recommend_date"], reverse=True)
  payload = {
    "generated_at": dt.datetime.now(dt.timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
    "summary": build_summary(records),
    "records": records,
    "failures": failures,
  }

  with output_path.open("w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False, indent=2)
    fh.write("\n")

  return 0


if __name__ == "__main__":
  sys.exit(main())
