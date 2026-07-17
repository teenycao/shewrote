#!/usr/bin/env python3
"""每朝代「所有诗人(男+女)」名单,生成朝代墙动画数据。

展示口径:
  - 显示的 总数/女性数/占比 = 已发布 frozen 口径(fig2 + 867 集),与线上一字不差:
      女性(867集)  先秦至隋20 唐54 宋42 元17 明93 清625
      占比(fig2)    先秦至隋9.9 唐3.5 宋1.0 元3.3 明7.6 清15.9(%)
      总墙 = round(女性 / 占比) → 202 1543 4200 515 1224 3931(Σ≈11,638 已发布口径)
  - 墙面用「真名」:男性名取 author_match resolved 桶(layer B, female=0),女性名取
    women_profiles(867 集 canonical)。名字数≠headcount——墙是视觉密度,权威数字看标签。
  - 男性按存诗量降序取(名家先入:陆游/苏轼…),每朝代封顶 MEN_CAP 控文件体积/渲染负载。
  - 全部 t2s 简体(面向简体读者)。

输出:构建期使用的朝代墙数据文件。
"""
import csv, json, sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
MATCH = ROOT / "data/interim/author_match.csv"
WOMEN = ROOT / "data/out/women_profiles.json"
OUT = ROOT / "clips" / "dynasty_data.js"

MEN_CAP = 5000   # 每朝代最多男性名;宋/清密档需≈4000 铺满整帧,标签数字才是权威

try:
    from opencc import OpenCC
    _t2s = OpenCC("t2s").convert
except Exception:
    _t2s = lambda s: s     # 没装就原样(venv 里有)

def t2s(s): return _t2s(s or "")

# ---- frozen 口径 v1.1(2026-07-10 勘误:找回顾太清/贺双卿,清 625→627;
#      占比按新分子重除同分母,一位小数均不变;总墙=round(女性/占比)) ----
FROZEN = {   # era: (women_count, share%)
    "先秦至隋": (20, 9.9), "唐": (54, 3.5), "宋": (42, 1.0),
    "元": (17, 3.3), "明": (93, 7.6), "清": (627, 15.9),
}
ERA_ORDER = ["先秦至隋", "唐", "宋", "元", "明", "清"]
ERA_EN = {"先秦至隋": "Pre-Qin – Sui", "唐": "Tang", "宋": "Song",
          "元": "Yuan", "明": "Ming", "清": "Qing"}

# ---- 男性朝代 → 6 大时代归并(与 fig2 一致;边界代按主体归) ----
def era_of_male(dy):
    if dy in ("先秦", "秦", "汉", "漢", "魏晋", "魏晋末南北朝初", "南北朝", "隋"): return "先秦至隋"
    if dy in ("隋末唐初", "唐"): return "唐"
    if dy in ("唐末宋初", "宋", "宋末金初", "宋末元初", "宋(劉)"): return "宋"
    if dy in ("金", "金末元初", "元"): return "元"
    if dy in ("元末明初", "明"): return "明"
    if dy in ("明末清初", "清"): return "清"
    return None

# ---- 女性朝代(women_profiles 原始标签)→ 6 大时代 ----
def era_of_female(dy):
    if dy in ("唐",): return "唐"
    if dy in ("宋",): return "宋"
    if dy in ("元",): return "元"
    if dy in ("明",): return "明"
    if dy in ("清",): return "清"
    # 先秦至隋 = 劉宋/南梁/西漢/東晉/西晉/三國/南齊/陳/東漢/隋 等(唐以前 + 劉宋)
    if dy in ("宋(劉)", "南梁", "西漢", "東晉", "西晉", "三國", "南齊", "陳", "東漢", "隋", "先秦", "秦"): return "先秦至隋"
    return None   # 未詳 / 中華民國 → 不入六代

# ---- 收男性名(resolved 桶,按存诗量降序) ----
male = defaultdict(list)   # era -> [(n_poems, name)]
seen = defaultdict(set)
with open(MATCH) as f:
    for r in csv.DictReader(f):
        if r["layer"] != "B" or r["bucket"] != "resolved" or r["female"] == "1":
            continue
        e = era_of_male(r["dynasty"])
        if not e:
            continue
        name = t2s(r["author"]).strip()
        if not name or len(name) > 5 or name in seen[e]:
            continue
        seen[e].add(name)
        try:
            n = int(r["n_poems"] or 0)
        except ValueError:
            n = 0
        male[e].append((n, name))

# ---- 收女性名(867 集 canonical) ----
female = defaultdict(list)   # era -> [(n_poems, name)]
women = json.load(open(WOMEN))
for p in women:
    e = era_of_female(p.get("dynasty", ""))
    if not e:
        continue
    female[e].append((p.get("n_poems", 0), t2s(p.get("name", "")).strip()))

# ---- 组装 ----
eras = []
for e in ERA_ORDER:
    wc, share = FROZEN[e]
    total = round(wc / (share / 100))
    men_sorted = sorted(male[e], key=lambda x: -x[0])
    men_names = [n for _, n in men_sorted[:MEN_CAP]]
    women_names = [n for _, n in sorted(female[e], key=lambda x: -x[0])]
    eras.append({
        "key": e, "label": e, "en": ERA_EN[e],
        "total": total, "women": wc, "share": share,
        "menAvail": len(male[e]), "menShown": len(men_names),
        "womenNames": women_names, "menNames": men_names,
    })
    print(f"{e:<7} total={total:<6} women={wc:<4}({share}%)  "
          f"men resolved={len(male[e]):<5} shown={len(men_names):<5} womenNames={len(women_names)}")

OUT.parent.mkdir(exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write("/* 自动生成 by scripts/build_dynasty_data.py — 勿手改。口径见脚本头。 */\n")
    f.write("const DYN_DATA=" + json.dumps({"eras": eras}, ensure_ascii=False, separators=(",", ":")) + ";\n")

kb = OUT.stat().st_size / 1024
print(f"\n→ {OUT.relative_to(ROOT)}  ({kb:.0f} KB)")
