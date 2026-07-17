#!/usr/bin/env python3
"""题材统计(题目关键词分类,女性 vs 男性对照)。

方法:古典诗题高度程式化(哭/悼/送/寄/和/次韵/题…图/咏),按简体化题目做多标签
正则分类;先剔除含干扰字的常见词牌名(如梦令≠梦题材)。只统计唯一命中(resolved)
作者的作品。题目级分类≠内容级分类,无命中约 2/3,结果解读为「题材标记率」而非全量。
"""
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_release import load_corpus_full, INTERIM
from opencc import OpenCC

T2S = OpenCC("t2s")

# 含题材干扰字的词牌名,分类前剔除
TUNE = re.compile(r"如梦令|梦令|梦江南|梦横塘|梦芙蓉|梦还京|梦扬州|梦仙郎|梦相亲|梦游仙"
                  r"|昭君怨|长相思|相思引|诉衷情|忆秦娥|忆江南|忆王孙|忆少年|忆帝京")

CATS = {
    "送别寄赠": r"送|别|寄|赠|留别",
    "咏物赋得": r"咏|赋得",
    "感怀述志": r"感怀|感事|书怀|述怀|遣怀|自遣|偶成|漫兴|即事|杂感",
    "题画题物": r"题.{0,8}(图|画|卷|册|轴|扇)|自题|题壁|题照",
    "节令": r"元夕|上元|中秋|七夕|清明|除夕|重阳|端午|立春|寒食|元旦",
    "闺怨宫怨": r"怨|闺情|宫词|春闺|秋闺",
    "悼亡哭挽": r"悼|哭|挽|殇|吊",
    "唱和次韵": r"次韵|和韵|奉和|步韵|和答|^和|叠韵|依韵",
    "梦": r"梦",
    "病中": r"病",
    "课女教子": r"课子|课女|示儿|示女|训|勉",
}
CATS = {k: re.compile(v) for k, v in CATS.items()}


def main():
    match = list(csv.DictReader(open(INTERIM / "author_match.csv")))
    keys = {(r["layer"], r["dynasty"], r["author"]): r["female"]
            for r in match if r["bucket"] == "resolved" and r["female"] in ("0", "1")}

    stat = {"0": defaultdict(int), "1": defaultdict(int)}
    tot = {"0": 0, "1": 0}
    nohit = {"0": 0, "1": 0}
    for layer, dy, author, title, text in load_corpus_full():
        g = keys.get((layer, dy, author.strip()))
        if g is None:
            continue
        tot[g] += 1
        t = TUNE.sub("", T2S.convert(title or ""))
        hit = False
        for k, pat in CATS.items():
            if pat.search(t):
                stat[g][k] += 1
                hit = True
        if not hit:
            nohit[g] += 1

    print(f"样本: 女 {tot['1']} / 男 {tot['0']} 首(resolved 作者,题目多标签,词牌已剔除)")
    print(f"{'题材':8s} {'女':>6s} {'女占比':>8s} {'男占比':>8s} {'女/男':>6s}")
    rows = [(k, stat["1"][k], stat["1"][k] / tot["1"] * 100, stat["0"][k] / tot["0"] * 100) for k in CATS]
    for k, n, f, m in sorted(rows, key=lambda x: -x[2]):
        print(f"{k:8s} {n:6d} {f:7.2f}% {m:7.2f}% {f/m if m else 0:5.2f}x")
    print(f"{'无命中':8s} {'':6s} {nohit['1']/tot['1']*100:7.2f}% {nohit['0']/tot['0']*100:7.2f}%")


if __name__ == "__main__":
    main()
