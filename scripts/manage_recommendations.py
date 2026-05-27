#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import datetime as dt
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from update_data import normalize_recommender, normalize_symbol, parse_recommend_price, parse_recommend_time, sanitize_id, validate_symbol


CSV_FIELDS = ["id", "recommender", "symbol", "name", "recommend_date", "recommend_time", "recommend_price", "note"]
DEFAULT_CSV_PATH = Path("docs/data/recommendations.csv")
DEFAULT_METRICS_SCRIPT = Path("scripts/update_data.py")


@dataclass
class RecommendationRow:
    id: str
    recommender: str
    symbol: str
    name: str
    recommend_date: str
    recommend_time: str
    recommend_price: str
    note: str


def read_rows(csv_path: Path) -> list[RecommendationRow]:
    if not csv_path.exists():
        return []

    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return [
            RecommendationRow(
                id=(row.get("id") or "").strip(),
                recommender=normalize_recommender(row.get("recommender") or ""),
                symbol=(row.get("symbol") or "").strip(),
                name=(row.get("name") or "").strip(),
                recommend_date=(row.get("recommend_date") or "").strip(),
                recommend_time=(row.get("recommend_time") or "").strip(),
                recommend_price=(row.get("recommend_price") or "").strip(),
                note=(row.get("note") or "").strip(),
            )
            for row in reader
            if any((row.get(field) or "").strip() for field in CSV_FIELDS)
        ]


def write_rows(csv_path: Path, rows: list[RecommendationRow]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    sorted_rows = sorted(rows, key=lambda row: (row.recommend_date, row.id))

    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in sorted_rows:
            writer.writerow(
                {
                    "id": row.id,
                    "recommender": row.recommender,
                    "symbol": row.symbol,
                    "name": row.name,
                    "recommend_date": row.recommend_date,
                    "recommend_time": row.recommend_time,
                    "recommend_price": row.recommend_price,
                    "note": row.note,
                }
            )


def parse_date(date_text: str) -> str:
    try:
        return dt.date.fromisoformat(date_text).isoformat()
    except ValueError as exc:
        raise ValueError("recommend_date 必须是 YYYY-MM-DD") from exc


def normalize_time(time_text: str | None) -> str:
    if not time_text:
        return ""
    parsed = parse_recommend_time(time_text)
    return parsed.strftime("%H:%M") if parsed else ""


def normalize_price(price_text: str | None) -> str:
    if not price_text:
        return ""
    parsed = parse_recommend_price(price_text)
    return f"{parsed:g}" if parsed is not None else ""


def parse_symbol(symbol_text: str) -> str:
    symbol = symbol_text.strip().upper()
    validate_symbol(symbol)
    normalized = normalize_symbol(symbol)
    if normalized.endswith(".SS"):
        return normalized[:-3]
    if normalized.endswith(".SZ"):
        return normalized[:-3]
    if normalized.endswith(".HK"):
        return normalized[:-3]
    return normalized


def generate_id(existing_rows: list[RecommendationRow], symbol: str, recommend_date: str) -> str:
    compact_date = recommend_date.replace("-", "")
    compact_symbol = symbol.upper()
    prefix = f"{compact_date}-{compact_symbol}-"
    max_sequence = 0

    for row in existing_rows:
        if row.id.startswith(prefix):
            suffix = row.id[len(prefix):]
            if suffix.isdigit():
                max_sequence = max(max_sequence, int(suffix))

    return sanitize_id(f"{prefix}{max_sequence + 1}")


def find_row(rows: list[RecommendationRow], recommendation_id: str) -> RecommendationRow:
    for row in rows:
        if row.id == recommendation_id:
            return row
    raise ValueError(f"未找到 id={recommendation_id} 的推荐记录")


def render_table(rows: list[RecommendationRow]) -> str:
    if not rows:
        return "没有推荐记录。"

    widths = {
        "id": max(len("id"), *(len(row.id) for row in rows)),
        "recommender": max(len("recommender"), *(len(row.recommender) for row in rows)),
        "symbol": max(len("symbol"), *(len(row.symbol) for row in rows)),
        "name": max(len("name"), *(len(row.name) for row in rows)),
        "recommend_date": len("recommend_date"),
        "recommend_time": len("recommend_time"),
        "recommend_price": len("recommend_price"),
        "note": max(len("note"), *(len(row.note) for row in rows)),
    }

    header = "  ".join(field.ljust(widths[field]) for field in CSV_FIELDS)
    divider = "  ".join("-" * widths[field] for field in CSV_FIELDS)
    body = [
        "  ".join(
            [
                row.id.ljust(widths["id"]),
                row.recommender.ljust(widths["recommender"]),
                row.symbol.ljust(widths["symbol"]),
                row.name.ljust(widths["name"]),
                row.recommend_date.ljust(widths["recommend_date"]),
                row.recommend_time.ljust(widths["recommend_time"]),
                row.recommend_price.ljust(widths["recommend_price"]),
                row.note.ljust(widths["note"]),
            ]
        )
        for row in rows
    ]
    return "\n".join([header, divider, *body])


def maybe_refresh_metrics(should_refresh: bool) -> None:
    if not should_refresh:
        return

    subprocess.run([sys.executable, str(DEFAULT_METRICS_SCRIPT)], check=True)


def cmd_list(args: argparse.Namespace) -> int:
    rows = read_rows(Path(args.csv))
    if args.code:
        keyword = parse_symbol(args.code)
        rows = [row for row in rows if row.symbol.upper() == keyword.upper()]
    if args.recommender:
        recommender = normalize_recommender(args.recommender)
        rows = [row for row in rows if row.recommender == recommender]
    print(render_table(rows))
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    csv_path = Path(args.csv)
    rows = read_rows(csv_path)

    symbol = parse_symbol(args.code)
    recommender = normalize_recommender(args.recommender)
    recommend_date = parse_date(args.recommend_date)
    recommend_time = normalize_time(args.recommend_time)
    recommend_price = normalize_price(args.recommend_price)
    recommendation_id = generate_id(rows, symbol, recommend_date)

    rows.append(
        RecommendationRow(
            id=recommendation_id,
            recommender=recommender,
            symbol=symbol,
            name=args.name.strip(),
            recommend_date=recommend_date,
            recommend_time=recommend_time,
            recommend_price=recommend_price,
            note=(args.note or "").strip(),
        )
    )
    write_rows(csv_path, rows)
    maybe_refresh_metrics(args.refresh)

    print(f"已新增推荐记录: {recommendation_id}")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    csv_path = Path(args.csv)
    rows = read_rows(csv_path)
    target = find_row(rows, args.id.strip())
    updated_rows = [row for row in rows if row.id != target.id]
    write_rows(csv_path, updated_rows)
    maybe_refresh_metrics(args.refresh)

    print(f"已删除推荐记录: {target.id}")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    csv_path = Path(args.csv)
    rows = read_rows(csv_path)
    target = find_row(rows, args.id.strip())

    if args.clear_recommend_time and args.recommend_time:
        raise ValueError("--recommend-time 和 --clear-recommend-time 不能同时使用")
    if args.clear_recommend_price and args.recommend_price:
        raise ValueError("--recommend-price 和 --clear-recommend-price 不能同时使用")

    new_symbol = parse_symbol(args.code) if args.code else target.symbol
    new_recommender = normalize_recommender(args.recommender) if args.recommender else target.recommender
    new_date = parse_date(args.recommend_date) if args.recommend_date else target.recommend_date
    new_time = "" if args.clear_recommend_time else normalize_time(args.recommend_time) if args.recommend_time else target.recommend_time
    new_price = "" if args.clear_recommend_price else normalize_price(args.recommend_price) if args.recommend_price else target.recommend_price

    target.symbol = new_symbol
    target.recommender = new_recommender
    target.name = args.name.strip() if args.name is not None else target.name
    target.recommend_date = new_date
    target.recommend_time = new_time
    target.recommend_price = new_price
    target.note = args.note.strip() if args.note is not None else target.note

    if args.regenerate_id:
        rows_without_target = [row for row in rows if row.id != target.id]
        target.id = generate_id(rows_without_target, new_symbol, new_date)
    elif args.new_id:
        target.id = sanitize_id(args.new_id.strip())

    if sum(1 for row in rows if row.id == target.id) > 1:
        raise ValueError(f"更新后 id 重复: {target.id}")

    write_rows(csv_path, rows)
    maybe_refresh_metrics(args.refresh)

    print(f"已更新推荐记录: {target.id}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage recommendations.csv without editing ids by hand.")
    parser.add_argument(
        "--csv",
        default=str(DEFAULT_CSV_PATH),
        help="Path to recommendations.csv",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List recommendation records")
    list_parser.add_argument("--code", "--symbol", dest="code", help="Only show one stock code")
    list_parser.add_argument("--recommender", help="Only show one recommender")
    list_parser.set_defaults(func=cmd_list)

    add_parser = subparsers.add_parser("add", help="Add one recommendation record")
    add_parser.add_argument(
        "--code",
        "--symbol",
        dest="code",
        required=True,
        help="A-share or HK code, e.g. 600519, 000001, 0700, 0005, 0700.HK",
    )
    add_parser.add_argument("--name", required=True, help="Stock name")
    add_parser.add_argument("--recommender", default="默认", help="Recommender name")
    add_parser.add_argument("--recommend-date", required=True, help="Recommend date in YYYY-MM-DD")
    add_parser.add_argument("--recommend-time", help="Recommend time in HH:MM; script will try 1-minute quote price")
    add_parser.add_argument("--recommend-price", help="Manual recommend price; useful for historical minute quote fallback")
    add_parser.add_argument("--note", default="", help="Optional note")
    add_parser.add_argument("--refresh", action="store_true", help="Run scripts/update_data.py after writing CSV")
    add_parser.set_defaults(func=cmd_add)

    remove_parser = subparsers.add_parser("remove", help="Remove one recommendation record by id")
    remove_parser.add_argument("--id", required=True, help="Recommendation id")
    remove_parser.add_argument("--refresh", action="store_true", help="Run scripts/update_data.py after writing CSV")
    remove_parser.set_defaults(func=cmd_remove)

    update_parser = subparsers.add_parser("update", help="Update one recommendation record by id")
    update_parser.add_argument("--id", required=True, help="Recommendation id")
    update_parser.add_argument("--code", "--symbol", dest="code", help="New A-share or HK stock code")
    update_parser.add_argument("--recommender", help="New recommender name")
    update_parser.add_argument("--name", help="New stock name")
    update_parser.add_argument("--recommend-date", help="New date in YYYY-MM-DD")
    update_parser.add_argument("--recommend-time", help="New time in HH:MM")
    update_parser.add_argument("--recommend-price", help="New manual recommend price")
    update_parser.add_argument("--clear-recommend-time", action="store_true", help="Clear recommend_time")
    update_parser.add_argument("--clear-recommend-price", action="store_true", help="Clear recommend_price")
    update_parser.add_argument("--note", help="New note")
    update_parser.add_argument("--new-id", help="Set a custom id explicitly")
    update_parser.add_argument(
        "--regenerate-id",
        action="store_true",
        help="Generate a new id from symbol + recommend_date after update",
    )
    update_parser.add_argument("--refresh", action="store_true", help="Run scripts/update_data.py after writing CSV")
    update_parser.set_defaults(func=cmd_update)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        return args.func(args)
    except ValueError as exc:
        parser.exit(1, f"错误: {exc}\n")
    except subprocess.CalledProcessError as exc:
        parser.exit(exc.returncode, f"错误: 更新 metrics.json 失败，退出码 {exc.returncode}\n")


if __name__ == "__main__":
    raise SystemExit(main())
