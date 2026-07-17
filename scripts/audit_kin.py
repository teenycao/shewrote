#!/usr/bin/env python3
"""Audit kinship directions against the relatives' birth years.

The source triples use ``(a, b, label) = a is b's label`` semantics.  The
generated Markdown report is intentionally exhaustive: every source triple is
listed exactly once, including unconstrained and indeterminate relationships.
"""

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
STAR_DATA = ROOT / "web" / "starmap_data.js"
POETS_DATA = ROOT / "data" / "out" / "site" / "poets.json"
REPORT = ROOT / "data" / "out" / "site" / "kin_audit.md"

OLDER_LABELS = {"母", "姑母", "婆母", "祖母", "從姊", "姊"}
YOUNGER_LABELS = {
    "女",
    "女兒",
    "妹",
    "姪女",
    "兒媳",
    "孫女",
    "從妹",
    "從女;姪女",
    "子婦;兒媳",
}
UNCONSTRAINED_LABELS = {"姊妹", "表姐妹", "夫之姐妹"}


def load_kin():
    raw = STAR_DATA.read_text(encoding="utf-8")
    match = re.search(r"const STAR_DATA = (\{.*)", raw, re.S)
    if not match:
        raise ValueError(f"Cannot find STAR_DATA in {STAR_DATA}")
    data = json.loads(match.group(1).strip().rstrip(";"))
    return data.get("kin", [])


def load_people():
    poets = json.loads(POETS_DATA.read_text(encoding="utf-8"))
    return {str(poet["id"]): poet for poet in poets}


def md(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def birth_text(year):
    return str(year) if year is not None else "—"


def actual_gap(a_year, b_year):
    if a_year == b_year:
        return "同年"
    if a_year < b_year:
        return f"a 年长 {b_year - a_year} 年"
    return f"a 年幼 {a_year - b_year} 年"


def classify(label, a_year, b_year):
    if label in OLDER_LABELS:
        direction = "a 应年长于 b"
        if a_year is None or b_year is None:
            return "unknown", direction
        return ("ok" if a_year < b_year else "warning"), direction
    if label in YOUNGER_LABELS:
        direction = "a 应年幼于 b"
        if a_year is None or b_year is None:
            return "unknown", direction
        return ("ok" if a_year > b_year else "warning"), direction
    if label in UNCONSTRAINED_LABELS:
        return "unconstrained", "不设年龄约束"
    raise ValueError(f"Unrecognised kinship label: {label}")


def row_line(row):
    return (
        f"| {row['index']} | {row['status']} | {md(row['a_name'])} | "
        f"{birth_text(row['a_year'])} | {md(row['label'])} | "
        f"{md(row['direction'])} | {md(row['b_name'])} | "
        f"{birth_text(row['b_year'])} | {md(row['gap'])} |"
    )


def table(lines, rows):
    lines.extend(
        [
            "| # | 判定 | 人物 a | a 生年 | 标签 | 语义方向 | 人物 b | b 生年 | 年龄差 |",
            "|---:|:---:|---|---:|---|---|---|---:|---|",
        ]
    )
    lines.extend(row_line(row) for row in rows)
    lines.append("")


def main():
    kin = load_kin()
    people = load_people()
    rows = []

    for index, triple in enumerate(kin, start=1):
        if len(triple) != 3:
            raise ValueError(f"Invalid kin triple at row {index}: {triple!r}")
        a_id, b_id, label = map(str, triple)
        a = people.get(a_id, {"n": f"未知人物 ({a_id})", "b": None})
        b = people.get(b_id, {"n": f"未知人物 ({b_id})", "b": None})
        a_year, b_year = a.get("b"), b.get("b")
        result, direction = classify(label, a_year, b_year)
        status = {
            "warning": "⚠️",
            "ok": "✅",
            "unconstrained": "✅ 不约束",
            "unknown": "无法判定",
        }[result]
        gap = "无法判定" if a_year is None or b_year is None else actual_gap(a_year, b_year)
        rows.append(
            {
                "index": index,
                "result": result,
                "status": status,
                "a_name": a["n"],
                "a_year": a_year,
                "label": label,
                "direction": direction,
                "b_name": b["n"],
                "b_year": b_year,
                "gap": gap,
            }
        )

    buckets = {
        key: [row for row in rows if row["result"] == key]
        for key in ("warning", "ok", "unconstrained", "unknown")
    }
    lines = [
        "# 亲缘方向年龄审计",
        "",
        f"> 三元组语义：`(a, b, label)` 表示“a 是 b 的 label”。共审计 {len(rows)} 对关系。",
        "",
        "## ⚠️ 疑似方向错误",
        "",
    ]
    table(lines, buckets["warning"])
    lines.extend(["## ✅ 方向符合", ""])
    table(lines, buckets["ok"])
    lines.extend(["## 无需年龄约束", ""])
    table(lines, buckets["unconstrained"])
    lines.extend(["## 无法判定（生年缺失）", ""])
    table(lines, buckets["unknown"])
    lines.extend(
        [
            "## 统计",
            "",
            f"- 总关系：{len(rows)}",
            f"- ⚠️ 疑似方向错误：{len(buckets['warning'])}",
            f"- ✅ 方向符合：{len(buckets['ok'])}",
            f"- ✅ 不设年龄约束：{len(buckets['unconstrained'])}",
            f"- 无法判定：{len(buckets['unknown'])}",
            f"- 判定行自检：{sum(len(items) for items in buckets.values())}",
            "",
        ]
    )

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(
        f"{REPORT}: {len(rows)} rows | warnings={len(buckets['warning'])} | "
        f"ok={len(buckets['ok'])} | unconstrained={len(buckets['unconstrained'])} | "
        f"unknown={len(buckets['unknown'])}"
    )


if __name__ == "__main__":
    main()
