#!/usr/bin/env python3
"""发布物打包:诗歌级女性作品子集 + 机器可读统计。

输入:data/interim/author_match.csv(匹配产物)+ 原始语料
输出:
  data/out/women_poems.csv  唯一命中女性作者的全部作品(标注子集本体)
  data/out/stats.json       headline 数字 + 分桶分布(机器可读,含生成时间与输入版本)
"""
import csv
import glob
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from opencc import OpenCC

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
OUT = ROOT / "data" / "out"
T2S = OpenCC("t2s")  # 与 build_match 同口径,供 curated_poems 诗级归属匹配

WERNEROR_EXCLUDE = {"当代", "近现代", "民国末当代初", "近现代末当代初", "清末近现代初", "清末民国初"}


def load_corpus_full():
    """yield (layer, dynasty_label, author_raw, title, text)"""
    cp = RAW / "chinese-poetry"
    for f in sorted(glob.glob(str(cp / "全唐诗" / "poet.tang.*.json"))):
        for p in json.load(open(f)):
            yield "A", "唐", p.get("author", ""), p.get("title", ""), "/".join(p.get("paragraphs", []))
    for f in sorted(glob.glob(str(cp / "全唐诗" / "poet.song.*.json"))):
        for p in json.load(open(f)):
            yield "A", "宋", p.get("author", ""), p.get("title", ""), "/".join(p.get("paragraphs", []))
    for f in sorted(glob.glob(str(cp / "宋词" / "ci.song.*.json"))):
        for p in json.load(open(f)):
            yield "A", "宋", p.get("author", ""), p.get("rhythmic", ""), "/".join(p.get("paragraphs", []))
    for f in glob.glob(str(cp / "五代诗词" / "**" / "*.json"), recursive=True):
        try:
            data = json.load(open(f))
        except Exception:
            continue
        if isinstance(data, list):
            for p in data:
                if isinstance(p, dict) and p.get("author") and (p.get("paragraphs") or p.get("sentences")):
                    yield ("A", "五代", p["author"], p.get("title", p.get("rhythmic", "")),
                           "/".join(p.get("paragraphs") or p.get("sentences") or []))
    for f in sorted(glob.glob(str(RAW / "werneror-poetry" / "*.csv"))):
        if Path(f).stem.split("_")[0] in WERNEROR_EXCLUDE:
            continue
        with open(f, newline="") as fh:
            for row in csv.DictReader(fh):
                dy = (row.get("朝代") or "").strip()
                if dy and dy not in WERNEROR_EXCLUDE:
                    yield "B", dy, (row.get("作者") or "").strip(), (row.get("题目") or "").strip(), (row.get("内容") or "").strip()


def main():
    match = list(csv.DictReader(open(INTERIM / "author_match.csv")))

    # --- stats.json ---
    stats = {"generated": subprocess.run(["date", "+%Y-%m-%d"], capture_output=True, text=True).stdout.strip(),
             "inputs": {"cbdb": "cbdb_20260627.sqlite3",
                        "chinese_poetry": "clone 2026-07-03", "werneror_poetry": "clone 2026-07-03"},
             "layers": {}}
    for layer, label in (("A", "Tang-Song (chinese-poetry)"), ("B", "pre-Qin through Qing (Werneror/Poetry)")):
        lr = [r for r in match if r["layer"] == layer]
        total = sum(int(r["n_poems"]) for r in lr)
        buckets = defaultdict(int)
        for r in lr:
            buckets[r["bucket"]] += int(r["n_poems"])
        fem_s = sum(int(r["n_poems"]) for r in lr if r["bucket"] == "resolved" and r["female"] == "1")
        male_s = sum(int(r["n_poems"]) for r in lr if r["bucket"] == "resolved" and r["female"] == "0")
        fem_i = fem_s + sum(int(r["n_poems"]) for r in lr if r["bucket"] == "multi_consensus" and r["female"] == "1")
        male_i = male_s + sum(int(r["n_poems"]) for r in lr if r["bucket"] == "multi_consensus" and r["female"] == "0")
        fem_au = len({r["person_id"] for r in lr if r["bucket"] == "resolved" and r["female"] == "1"})
        male_au = len({r["person_id"] for r in lr if r["bucket"] == "resolved" and r["female"] == "0"})
        stats["layers"][layer] = {
            "label": label,
            "poems_total": total,
            "buckets": dict(sorted(buckets.items(), key=lambda kv: -kv[1])),
            "female_poems": fem_i,
            "female_poems_share_of_all": round(fem_i / total, 6),
            "female_poems_share_of_gender_known": round(fem_i / (fem_i + male_i), 6),
            "female_authors_resolved": fem_au,
            "authors_resolved": fem_au + male_au,
            "female_author_share": round(fem_au / (fem_au + male_au), 6),
            "poems_per_author_female": round(fem_s / fem_au, 1),
            "poems_per_author_male": round(male_s / male_au, 1),
        }
    json.dump(stats, open(OUT / "stats.json", "w"), ensure_ascii=False, indent=1)

    # --- women_poems.csv ---
    women_keys = {}  # (layer, dynasty, author) -> (person_id, name_chn)
    for r in match:
        if r["bucket"] == "resolved" and r["female"] == "1":
            women_keys[(r["layer"], r["dynasty"], r["author"])] = (r["person_id"], r["name_chn"])

    # 诗级归属(curated_poems.csv):(layer, dynasty, T2S(author), T2S(title)) 精确 → person,优先于作者键级。
    # key 与 build_match 扣减同口径(含 layer/dynasty + T2S 归一),避免 match/release 分裂致静默错账。
    poem_attr = {}
    CURATED_POEMS = ROOT / "data" / "curated" / "curated_poems.csv"
    if CURATED_POEMS.exists():
        for r in csv.DictReader(open(CURATED_POEMS, encoding="utf-8")):
            k = (r["layer"], r["dynasty"], T2S.convert(r["corpus_author"].strip()), T2S.convert(r["corpus_title"].strip()))
            poem_attr[k] = (r["person_id"], r["name"])
    attr_hits = defaultdict(int)

    n = 0
    with open(OUT / "women_poems.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["layer", "dynasty", "person_id", "name", "corpus_author", "title", "text"])
        for layer, dy, author, title, text in load_corpus_full():
            if poem_attr:
                pk = (layer, dy, T2S.convert(author.strip()), T2S.convert(title.strip()))
                pa = poem_attr.get(pk)
                if pa:
                    w.writerow([layer, dy, pa[0], pa[1], author, title, text])
                    n += 1
                    attr_hits[pk] += 1
                    continue
            key = (layer, dy, author.strip())
            if key in women_keys:
                pid, name = women_keys[key]
                w.writerow([layer, dy, pid, name, author, title, text])
                n += 1
    # 诗级归属校验:每条 curated_poems 必须在语料恰好命中 1 次,否则 build_match 已扣减/加档而此处无诗行=静默错账,fail-fast
    bad = {k: attr_hits.get(k, 0) for k in poem_attr if attr_hits.get(k, 0) != 1}
    if bad:
        raise SystemExit(f"❌ curated_poems 诗级归属校验失败:(layer,dynasty,简体author,简体title)→命中数 {bad};"
                         f"应恰好 1,请核对 corpus_author/corpus_title 是否与语料署名逐字一致。")
    print(f"women_poems.csv: {n} poems", file=sys.stderr)
    print(json.dumps(stats["layers"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
