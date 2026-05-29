#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import datetime as dt
import subprocess
import sys
import termios
import tty
from dataclasses import dataclass
from pathlib import Path

from update_data import normalize_symbol, normalize_tag, parse_recommend_price, parse_recommend_time, sanitize_id, validate_symbol


CSV_FIELDS = ["id", "tag", "symbol", "name", "recommend_date", "recommend_time", "recommend_price", "note"]
DEFAULT_CSV_PATH = Path("docs/data/recommendations.csv")
DEFAULT_METRICS_SCRIPT = Path("scripts/update_data.py")
WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


@dataclass
class RecommendationRow:
    id: str
    tag: str
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
                tag=normalize_tag(row.get("tag") or ""),
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
                    "tag": row.tag,
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
        "tag": max(len("tag"), *(len(row.tag) for row in rows)),
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
                row.tag.ljust(widths["tag"]),
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
    if args.tag:
        tag = normalize_tag(args.tag)
        rows = [row for row in rows if row.tag == tag]
    print(render_table(rows))
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    csv_path = Path(args.csv)
    rows = read_rows(csv_path)

    symbol = parse_symbol(args.code)
    tag = normalize_tag(args.tag)
    recommend_date = parse_date(args.recommend_date)
    recommend_time = normalize_time(args.recommend_time)
    recommend_price = normalize_price(args.recommend_price)
    recommendation_id = generate_id(rows, symbol, recommend_date)

    rows.append(
        RecommendationRow(
            id=recommendation_id,
            tag=tag,
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
    new_tag = normalize_tag(args.tag) if args.tag else target.tag
    new_date = parse_date(args.recommend_date) if args.recommend_date else target.recommend_date
    new_time = "" if args.clear_recommend_time else normalize_time(args.recommend_time) if args.recommend_time else target.recommend_time
    new_price = "" if args.clear_recommend_price else normalize_price(args.recommend_price) if args.recommend_price else target.recommend_price

    target.symbol = new_symbol
    target.tag = new_tag
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


def weekday_label(date_value: dt.date) -> str:
    return WEEKDAY_NAMES[date_value.weekday()]


def format_date_label(date_value: dt.date) -> str:
    return f"{date_value.isoformat()} {weekday_label(date_value)}"


def prompt_text(prompt: str, default: str = "", allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{prompt}{suffix}: ").strip()
        if value:
            return value
        if default:
            return default
        if allow_empty:
            return ""
        print("不能为空，请重新输入。")


def prompt_yes_no(prompt: str, default: bool = True) -> bool:
    marker = "Y/n" if default else "y/N"
    while True:
        value = input(f"{prompt} ({marker}): ").strip().lower()
        if not value:
            return default
        if value in ("y", "yes"):
            return True
        if value in ("n", "no"):
            return False
        print("请输入 y 或 n。")


def prompt_choice(title: str, options: list[tuple[str, object]]) -> object:
    if not options:
        raise ValueError("没有可选项")

    while True:
        print(f"\n{title}")
        for index, (label, _) in enumerate(options, start=1):
            print(f"{index}. {label}")

        value = input("请选择编号: ").strip()
        if value.isdigit():
            index = int(value)
            if 1 <= index <= len(options):
                return options[index - 1][1]
        print("选择无效，请重新输入。")


def read_arrow_key() -> str:
    ch = sys.stdin.read(1)
    if ch in ("\r", "\n"):
        return "enter"
    if ch.lower() == "m":
        return "manual"
    if ch.lower() == "q":
        return "quit"
    if ch == "\x03":
        raise KeyboardInterrupt
    if ch == "\x1b":
        seq = sys.stdin.read(2)
        if seq == "[D":
            return "left"
        if seq == "[C":
            return "right"
    return ""


def prompt_date_with_arrows(prompt: str, default_date: dt.date | None = None) -> str:
    selected = default_date or dt.date.today()
    if not sys.stdin.isatty():
        return parse_date(prompt_text(prompt, selected.isoformat(), allow_empty=False))

    print(f"\n{prompt}")
    print("按 ← 前一天，按 → 后一天，Enter 确认，m 手动输入，q 取消。")
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setraw(sys.stdin.fileno())
        while True:
            sys.stdout.write(f"\r当前选择：{format_date_label(selected)}   ")
            sys.stdout.flush()
            key = read_arrow_key()
            if key == "left":
                selected -= dt.timedelta(days=1)
            elif key == "right":
                selected += dt.timedelta(days=1)
            elif key == "enter":
                sys.stdout.write("\n")
                return selected.isoformat()
            elif key == "manual":
                sys.stdout.write("\n")
                break
            elif key == "quit":
                sys.stdout.write("\n")
                raise ValueError("已取消日期选择")
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

    return parse_date(prompt_text(prompt, selected.isoformat(), allow_empty=False))


def known_tags(rows: list[RecommendationRow]) -> list[str]:
    tags = sorted({row.tag for row in rows if row.tag}, key=lambda item: item)
    return tags or ["默认"]


def prompt_tag(rows: list[RecommendationRow], default: str = "默认") -> str:
    tags = known_tags(rows)
    options: list[tuple[str, object]] = [(tag, tag) for tag in tags]
    options.append(("新建标签", "__new__"))
    selected = prompt_choice("选择标签", options)
    if selected == "__new__":
        return normalize_tag(prompt_text("新标签", default, allow_empty=False))
    return normalize_tag(str(selected))


def prompt_symbol() -> str:
    while True:
        try:
            return parse_symbol(prompt_text("股票代码", allow_empty=False))
        except ValueError as exc:
            print(f"代码无效：{exc}")


def latest_name_for_symbol(rows: list[RecommendationRow], symbol: str) -> str:
    matches = [row for row in rows if row.symbol.upper() == symbol.upper() and row.name]
    if not matches:
        return ""
    matches.sort(key=lambda row: (row.recommend_date, row.id), reverse=True)
    return matches[0].name


def prompt_recommend_time(default: str = "") -> str:
    while True:
        raw_value = prompt_text("推荐时间，直接回车表示不填，输入 - 清空", default)
        if raw_value == "-":
            return ""
        try:
            return normalize_time(raw_value)
        except ValueError as exc:
            print(f"时间无效：{exc}")


def prompt_recommend_price(default: str = "") -> str:
    while True:
        raw_value = prompt_text("推荐价格，直接回车表示不填，输入 - 清空", default)
        if raw_value == "-":
            return ""
        try:
            return normalize_price(raw_value)
        except ValueError as exc:
            print(f"价格无效：{exc}")


def prompt_note(default: str = "") -> str:
    selected = prompt_choice(
        "选择备注",
        [
            ("首次推荐", "首次推荐"),
            ("早盘推荐", "早盘推荐"),
            ("二次推荐", "二次推荐"),
            ("手动输入", "__manual__"),
            ("留空", ""),
        ],
    )
    if selected == "__manual__":
        return prompt_text("备注", default)
    return str(selected)


def render_row_detail(row: RecommendationRow) -> str:
    return (
        f"id={row.id}\n"
        f"标签={row.tag}\n"
        f"代码={row.symbol}\n"
        f"名称={row.name}\n"
        f"推荐日期={row.recommend_date}\n"
        f"推荐时间={row.recommend_time or '-'}\n"
        f"推荐价格={row.recommend_price or '-'}\n"
        f"备注={row.note or '-'}"
    )


def wizard_add(csv_path: Path) -> None:
    rows = read_rows(csv_path)
    tag = prompt_tag(rows)
    symbol = prompt_symbol()
    inferred_name = latest_name_for_symbol(rows, symbol)
    name = prompt_text("股票名称", inferred_name, allow_empty=False)
    recommend_date = prompt_date_with_arrows("选择推荐日期", dt.date.today())
    recommend_time = prompt_recommend_time()
    recommend_price = prompt_recommend_price()
    note = prompt_note("首次推荐")
    recommendation_id = generate_id(rows, symbol, recommend_date)
    new_row = RecommendationRow(
        id=recommendation_id,
        tag=tag,
        symbol=symbol,
        name=name,
        recommend_date=recommend_date,
        recommend_time=recommend_time,
        recommend_price=recommend_price,
        note=note,
    )

    print("\n即将新增：")
    print(render_row_detail(new_row))
    if not prompt_yes_no("确认写入", True):
        print("已取消新增。")
        return

    rows.append(new_row)
    write_rows(csv_path, rows)
    print(f"已新增推荐记录: {new_row.id}")
    if prompt_yes_no("是否立即刷新 metrics.json", True):
        maybe_refresh_metrics(True)


def recent_rows(rows: list[RecommendationRow], limit: int = 20) -> list[RecommendationRow]:
    return sorted(rows, key=lambda row: (row.recommend_date, row.id), reverse=True)[:limit]


def prompt_row(rows: list[RecommendationRow]) -> RecommendationRow | None:
    if not rows:
        print("没有推荐记录。")
        return None

    mode = prompt_choice(
        "查找记录",
        [
            ("按股票代码", "code"),
            ("按标签", "tag"),
            ("最近记录", "recent"),
            ("返回", "back"),
        ],
    )
    if mode == "back":
        return None
    if mode == "code":
        symbol = prompt_symbol()
        candidates = [row for row in rows if row.symbol.upper() == symbol.upper()]
    elif mode == "tag":
        tag = prompt_tag(rows)
        candidates = [row for row in rows if row.tag == tag]
    else:
        candidates = recent_rows(rows)

    candidates = sorted(candidates, key=lambda row: (row.recommend_date, row.id), reverse=True)
    if not candidates:
        print("没有匹配记录。")
        return None

    options = [
        (f"{row.id} {row.tag} {row.symbol} {row.name} {row.recommend_date} {row.recommend_time or '-'}", row)
        for row in candidates[:30]
    ]
    options.append(("返回", None))
    selected = prompt_choice("选择记录", options)
    return selected if isinstance(selected, RecommendationRow) else None


def wizard_update(csv_path: Path) -> None:
    rows = read_rows(csv_path)
    target = prompt_row(rows)
    if target is None:
        return

    print("\n当前记录：")
    print(render_row_detail(target))
    field = prompt_choice(
        "选择修改项",
        [
            ("标签", "tag"),
            ("股票代码", "symbol"),
            ("股票名称", "name"),
            ("推荐日期", "date"),
            ("推荐时间", "time"),
            ("推荐价格", "price"),
            ("备注", "note"),
            ("重新生成 ID", "id"),
            ("返回", "back"),
        ],
    )
    if field == "back":
        return

    if field == "tag":
        target.tag = prompt_tag(rows, target.tag)
    elif field == "symbol":
        target.symbol = prompt_symbol()
    elif field == "name":
        target.name = prompt_text("股票名称", target.name, allow_empty=False)
    elif field == "date":
        target.recommend_date = prompt_date_with_arrows("选择推荐日期", dt.date.fromisoformat(target.recommend_date))
    elif field == "time":
        target.recommend_time = prompt_recommend_time(target.recommend_time)
    elif field == "price":
        target.recommend_price = prompt_recommend_price(target.recommend_price)
    elif field == "note":
        target.note = prompt_note(target.note)
    elif field == "id":
        rows_without_target = [row for row in rows if row.id != target.id]
        target.id = generate_id(rows_without_target, target.symbol, target.recommend_date)

    if sum(1 for row in rows if row.id == target.id) > 1:
        raise ValueError(f"更新后 id 重复: {target.id}")

    print("\n更新后记录：")
    print(render_row_detail(target))
    if not prompt_yes_no("确认写入", True):
        print("已取消修改。")
        return

    write_rows(csv_path, rows)
    print(f"已更新推荐记录: {target.id}")
    if prompt_yes_no("是否立即刷新 metrics.json", True):
        maybe_refresh_metrics(True)


def wizard_view(csv_path: Path) -> None:
    rows = read_rows(csv_path)
    mode = prompt_choice(
        "查看记录",
        [
            ("全部", "all"),
            ("按标签", "tag"),
            ("按股票代码", "code"),
            ("最近 20 条", "recent"),
            ("返回", "back"),
        ],
    )
    if mode == "back":
        return
    if mode == "tag":
        tag = prompt_tag(rows)
        rows = [row for row in rows if row.tag == tag]
    elif mode == "code":
        symbol = prompt_symbol()
        rows = [row for row in rows if row.symbol.upper() == symbol.upper()]
    elif mode == "recent":
        rows = recent_rows(rows)
    print()
    print(render_table(rows))


def cmd_wizard(args: argparse.Namespace) -> int:
    csv_path = Path(args.csv)
    print("推荐记录交互向导")
    while True:
        action = prompt_choice(
            "请选择操作",
            [
                ("新增推荐记录", "add"),
                ("修改已有记录", "update"),
                ("查看记录", "view"),
                ("刷新 metrics.json", "refresh"),
                ("退出", "exit"),
            ],
        )
        if action == "add":
            wizard_add(csv_path)
        elif action == "update":
            wizard_update(csv_path)
        elif action == "view":
            wizard_view(csv_path)
        elif action == "refresh":
            maybe_refresh_metrics(True)
        elif action == "exit":
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
    list_parser.add_argument("--tag", dest="tag", help="Only show one tag")
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
    add_parser.add_argument("--tag", dest="tag", default="默认", help="Tag name")
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
    update_parser.add_argument("--tag", dest="tag", help="New tag name")
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

    wizard_parser = subparsers.add_parser("wizard", help="Open an interactive recommendation manager")
    wizard_parser.set_defaults(func=cmd_wizard)

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
