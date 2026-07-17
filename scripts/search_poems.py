#!/usr/bin/env python3
"""女性诗词检索小工具(未来 MCP server 的 search_poems 原型)。

用法:
  .venv/bin/python scripts/search_poems.py 猫                 # 题目+正文全搜
  .venv/bin/python scripts/search_poems.py 琴 --field title   # 只搜题目
  .venv/bin/python scripts/search_poems.py 梅 --dynasty 清 --limit 5
  .venv/bin/python scripts/search_poems.py --poet 柳如是      # 查诗人档案(名/别名)

繁简自动归一;唐宋作品在 A/B 两库重复者自动去重(保留繁体版)。
"""
import argparse
import csv
import json
import re
from pathlib import Path

from opencc import OpenCC

T2S = OpenCC("t2s")
OUT = Path(__file__).resolve().parent.parent / "data" / "out"


def load_poems():
    rows = list(csv.DictReader(open(OUT / "women_poems.csv")))
    seen, uniq = {}, []
    for r in rows:
        key = (r["person_id"], T2S.convert(r["title"].replace(" ", "")).strip(), T2S.convert(r["text"].replace("/", "").replace("，", ",")[:20]))
        if key in seen:
            continue
        seen[key] = True
        r["_title_s"] = T2S.convert(r["title"])
        r["_text_s"] = T2S.convert(r["text"])
        r["_name_s"] = T2S.convert(r["name"])
        uniq.append(r)
    return uniq


def match_line(text, text_s, kw_s):
    """返回原文中包含关键词的那一句"""
    lines = text.split("/")
    lines_s = text_s.split("/")
    for orig, simp in zip(lines, lines_s):
        if kw_s in simp:
            return orig.strip()
    return text[:40]


def search(kw, field="all", dynasty=None, author=None, limit=20):
    kw_s = T2S.convert(kw)
    poems = load_poems()
    hits = []
    for r in poems:
        if dynasty and dynasty not in r["dynasty"]:
            continue
        if author and T2S.convert(author) not in r["_name_s"]:
            continue
        in_title = kw_s in r["_title_s"]
        in_text = kw_s in r["_text_s"]
        if field == "title" and not in_title:
            continue
        if field == "text" and not in_text:
            continue
        if field == "all" and not (in_title or in_text):
            continue
        hits.append((not in_title, r))  # 题目命中排前
    hits.sort(key=lambda h: h[0])
    total = len(hits)
    print(f"「{kw}」共 {total} 首(去重后;题目命中优先)")
    for _, r in hits[:limit]:
        where = "题" if kw_s in r["_title_s"] else "文"
        line = match_line(r["text"], r["_text_s"], kw_s) if where == "文" else r["text"].split("/")[0].strip()
        print(f"◆ [{where}] {r['name']}《{r['title'][:24]}》[{r['dynasty']}]  {line[:44]}")
    if total > limit:
        print(f"… 另有 {total - limit} 首,--limit 调整")


def poet(name):
    profiles = json.load(open(OUT / "women_profiles.json"))
    name_s = T2S.convert(name)
    for p in profiles:
        hay = T2S.convert(p["name"] + "/" + (p.get("aliases") or ""))
        surname = T2S.convert(p["name"])[0]
        # 直接命中,或「姓+字号」组合命中(档案别名不带姓:柳如是 → 姓柳 + 别名「如是」)
        if name_s in hay or (name_s.startswith(surname) and len(name_s) > 1 and name_s[1:] in hay):
            print(f"◆ {p['name']}({p.get('name_pinyin','')})[{p['dynasty']}] CBDB {p['person_id']}")
            print(f"  生卒: {p.get('birth_year','?')}–{p.get('death_year','?')} · 籍贯: {p.get('place') or '未详'}"
                  f" · 存世 {p['n_poems']} 首 · MQWW {'✓' if p.get('in_mqww') else '—'}")
            if p.get("aliases"):
                print(f"  别名({len(p['aliases'].split('/'))}): {p['aliases'][:100]}")
            if p.get("statuses"):
                print(f"  身份: {p['statuses']}")
            print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("keyword", nargs="?", help="检索关键词")
    ap.add_argument("--field", choices=["all", "title", "text"], default="all")
    ap.add_argument("--dynasty", help="朝代过滤,如 清")
    ap.add_argument("--author", help="作者过滤")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--poet", help="查诗人档案(名或别名)")
    args = ap.parse_args()
    if args.poet:
        poet(args.poet)
    elif args.keyword:
        search(args.keyword, args.field, args.dynasty, args.author, args.limit)
    else:
        ap.print_help()
