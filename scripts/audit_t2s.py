#!/usr/bin/env python3
"""Audit character-level Traditional-to-Simplified profile changes."""

import csv
import json
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from itertools import zip_longest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PROFILES = ROOT / "data" / "out" / "women_profiles.csv"
POETS = ROOT / "data" / "out" / "site" / "poets.json"
REPORT = ROOT / "data" / "out" / "site" / "t2s_audit.md"

SUSPICIOUS = set("沈于后云发里干斗几征复台钟适万")
FIELDS = (
    ("name", "name", "n"),
    ("aliases", "aliases", "al"),
    ("place", "place", "pl"),
)


def md(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def normalized_source(field, value):
    value = value or ""
    if field == "aliases":
        return value.replace(" / ", "、")
    return value


def changed_pairs(source, target):
    """Yield every changed character pair, retaining inserts/deletes as ∅."""
    matcher = SequenceMatcher(a=source, b=target, autojunk=False)
    for tag, a0, a1, b0, b1 in matcher.get_opcodes():
        if tag == "equal":
            continue
        old, new = source[a0:a1], target[b0:b1]
        if tag == "delete":
            yield from ((char, "∅") for char in old)
        elif tag == "insert":
            yield from (("∅", char) for char in new)
        else:
            yield from zip_longest(old, new, fillvalue="∅")


def pair_label(pair):
    return f"{pair[0]}→{pair[1]}"


def render_table(lines, pairs, counts, examples, fields):
    lines.extend(
        [
            "| 字符对 | 次数 | 字段 | 人物例（最多 5 位） |",
            "|---|---:|---|---|",
        ]
    )
    for pair in pairs:
        names = "、".join(examples[pair])
        field_list = "、".join(sorted(fields[pair]))
        lines.append(
            f"| {md(pair_label(pair))} | {counts[pair]} | "
            f"{md(field_list)} | {md(names)} |"
        )
    lines.append("")


def main():
    with PROFILES.open(encoding="utf-8", newline="") as handle:
        source_rows = {row["person_id"]: row for row in csv.DictReader(handle)}
    output_rows = {
        str(row["id"]): row
        for row in json.loads(POETS.read_text(encoding="utf-8"))
    }

    if source_rows.keys() != output_rows.keys():
        missing_output = sorted(source_rows.keys() - output_rows.keys())
        missing_source = sorted(output_rows.keys() - source_rows.keys())
        raise ValueError(
            f"person_id mismatch: missing output={missing_output[:5]}, "
            f"missing source={missing_source[:5]}"
        )

    counts = Counter()
    examples = defaultdict(list)
    fields = defaultdict(set)
    changed_values = 0

    for person_id, source_row in source_rows.items():
        output_row = output_rows[person_id]
        person_name = source_row["name"]
        for field, source_key, output_key in FIELDS:
            source = normalized_source(field, source_row.get(source_key))
            target = output_row.get(output_key) or ""
            pairs = list(changed_pairs(source, target))
            if pairs:
                changed_values += 1
            for pair in pairs:
                counts[pair] += 1
                fields[pair].add(field)
                if person_name not in examples[pair] and len(examples[pair]) < 5:
                    examples[pair].append(person_name)

    all_pairs = sorted(counts, key=lambda pair: (-counts[pair], pair[0], pair[1]))
    suspicious_pairs = [
        pair for pair in all_pairs if pair[0] in SUSPICIOUS or pair[1] in SUSPICIOUS
    ]
    shen_accident = counts[("沈", "沉")]

    lines = [
        "# 繁简转换全量审计",
        "",
        "## 可疑多映射字（优先复核）",
        "",
        f"- 沈姓保护：`沈→沉` {shen_accident} 次 {'✅' if shen_accident == 0 else '⚠️'}",
        f"- 复核字符：{' / '.join('沈于后云发里干斗几征复台钟适万')}",
        "",
    ]
    if suspicious_pairs:
        render_table(lines, suspicious_pairs, counts, examples, fields)
    else:
        lines.extend(["未发现涉及上述字符的转换。", ""])

    lines.extend(["## 全部字符对", ""])
    render_table(lines, all_pairs, counts, examples, fields)
    lines.extend(
        [
            "## 统计",
            "",
            f"- 对齐人物：{len(source_rows)}",
            f"- 比较字段值：{len(source_rows) * len(FIELDS)}",
            f"- 发生变化的字段值：{changed_values}",
            f"- 不同字符对：{len(all_pairs)}",
            f"- 变化字符总次数：{sum(counts.values())}",
            "",
        ]
    )

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(
        f"{REPORT}: people={len(source_rows)} | pairs={len(all_pairs)} | "
        f"changes={sum(counts.values())} | 沈→沉={shen_accident}"
    )


if __name__ == "__main__":
    main()
