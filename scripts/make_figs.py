#!/usr/bin/env python3
"""配图 ×4 ×双语(注:图中数值为 2026-07 冻结口径,数据更新后需人工核对 stats.json/theme_landscape 输出):词云 / 朝代占比 / 籍贯分布 / 题材分布。统一视觉:宣纸底+墨色+印章红。
zh → article/figs/  ·  en → article/figs/en/"""
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch
from opencc import OpenCC

T2S = OpenCC("t2s")
ROOT = Path(__file__).resolve().parent.parent
FIGS = {"zh": ROOT / "article" / "figs", "en": ROOT / "article" / "figs" / "en"}
for d in FIGS.values():
    d.mkdir(parents=True, exist_ok=True)

PAPER = "#F8F5EC"
INK = "#33302A"
INK_MID = "#6E6A5E"
INK_FAINT = "#B7B2A4"
RED = "#A63F3B"
GRID = "#DFD9CA"

# 自托管开源字体替换系统字体(合规:OFL 可商用/嵌入,见 assets/fonts/LICENSES.md)
_FONTS = ROOT / "assets" / "fonts"
for _f in ("NotoSerifSC.ttf", "LXGWWenKai-Regular.ttf"):
    font_manager.fontManager.addfont(str(_FONTS / _f))
SONG = "Noto Serif SC"   # 原 Songti SC 系统字体
KAI = "LXGW WenKai"       # 原 Kaiti SC 系统字体(含词云 font_path)
plt.rcParams["font.family"] = SONG
plt.rcParams["axes.unicode_minus"] = False

NOTE = {"zh": "数据:「中国古代才女」数据集 · github.com/teenycao/shewrote",
        "en": "Data: SheWrote — women poets of premodern China · github.com/teenycao/shewrote"}


def canvas():
    fig, ax = plt.subplots(figsize=(10.8, 8.1), dpi=100)
    fig.patch.set_facecolor(PAPER)
    ax.set_facecolor(PAPER)
    for s in ax.spines.values():
        s.set_visible(False)
    return fig, ax


def chrome(fig, title, subtitle, note):
    fig.text(0.06, 0.935, title, fontsize=26, fontweight="bold", color=INK, family=SONG)
    fig.text(0.06, 0.885, subtitle, fontsize=14, color=INK_MID, family=SONG)
    fig.text(0.06, 0.035, note, fontsize=11, color=INK_FAINT, family=SONG)
    # 朱印:单列竖排长条章(引首章式),中英版共用
    rect = FancyBboxPatch((0.9305, 0.715), 0.038, 0.245, boxstyle="round,pad=0.003,rounding_size=0.006",
                          transform=fig.transFigure, facecolor=RED, edgecolor="none", zorder=10)
    fig.add_artist(rect)
    fig.text(0.9495, 0.9515, "中\n国\n古\n代\n才\n女", fontsize=13, color="#FFFFFF", family=KAI,
             ha="center", va="top", linespacing=1.28, zorder=11)


def fig_dynasty(lang):
    eras = {"zh": ["先秦至隋", "唐", "宋", "元", "明", "清"],
            "en": ["Pre-Qin–Sui", "Tang", "Song", "Yuan", "Ming", "Qing"]}[lang]
    vals = [9.9, 3.5, 1.0, 3.3, 7.6, 15.9]
    fig, ax = canvas()
    fig.subplots_adjust(top=0.82, bottom=0.13, left=0.08, right=0.94)
    colors = [INK_MID, INK_MID, RED, INK_MID, INK_MID, INK]
    bars = ax.bar(eras, vals, width=0.58, color=colors, zorder=3)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.35, f"{v}%", ha="center",
                fontsize=15, color=INK, fontweight="bold", family=SONG)
    ax.set_ylim(0, 18.5)
    ax.set_yticks([])
    ax.tick_params(axis="x", labelsize=15, colors=INK, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    t = {"zh": ("各朝代的女性诗人占比", "女性占身份可考诗人的比例,按时代"),  # 非「朝代分布」:数值是每代女性占比,不求和为 100%
         "en": ("Women's share of poets, by era", "Women as a share of identifiable poets in the corpus")}[lang]
    chrome(fig, t[0], t[1], NOTE[lang])
    fig.savefig(FIGS[lang] / "fig2_dynasty.png")
    plt.close(fig)


def fig_place(lang):
    data_zh = [("钱塘(今杭州)", 19), ("常熟", 17), ("长洲(今苏州)", 12), ("吴县(今苏州)", 10),
               ("山阴(今绍兴)", 10), ("无锡", 9), ("苏州府", 9), ("歙县(今黄山)", 9),
               ("武进(今常州)", 8), ("吴江(今苏州)", 7), ("桐城", 7), ("阳湖(今常州)", 7)]
    data_en = [("钱塘 Qiantang (Hangzhou)", 19), ("常熟 Changshu", 17), ("长洲 (Suzhou)", 12),
               ("吴县 (Suzhou)", 10), ("山阴 (Shaoxing)", 10), ("无锡 Wuxi", 9), ("苏州府 Suzhou", 9),
               ("歙县 (Huizhou)", 9), ("武进 (Changzhou)", 8), ("吴江 (Suzhou)", 7),
               ("桐城 Tongcheng", 7), ("阳湖 (Changzhou)", 7)]
    data = {"zh": data_zh, "en": data_en}[lang]
    names = [d[0] for d in data][::-1]
    vals = [d[1] for d in data][::-1]
    fig, ax = canvas()
    fig.subplots_adjust(top=0.82, bottom=0.10, left={"zh": 0.21, "en": 0.27}[lang], right=0.90)
    colors = [INK_MID] * len(vals)
    colors[-1] = RED
    ax.barh(names, vals, height=0.62, color=colors, zorder=3)
    for i, v in enumerate(vals):
        ax.text(v + 0.25, i, str(v), va="center", fontsize=13.5, color=INK, family=SONG)
    ax.set_xlim(0, 21.5)
    ax.set_xticks([])
    ax.tick_params(axis="y", labelsize=13.5, colors=INK, length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
    t = {"zh": ("女性诗人籍贯分布 TOP12", "籍贯可考的女性诗人数,全部位于江南与徽州——今江浙沪皖"),
         "en": ("Native places of women poets, top 12", "All twelve lie in Jiangnan & Huizhou — the lower Yangzi region")}[lang]
    note = {"zh": "数据:「中国古代才女」数据集 · 籍贯可考者 339 人 · github.com/teenycao/shewrote",
            "en": "Among 339 women with recorded native place · SheWrote dataset · github.com/teenycao/shewrote"}[lang]
    chrome(fig, t[0], t[1], note)
    fig.savefig(FIGS[lang] / "fig3_place.png")
    plt.close(fig)


def fig_theme(lang):
    cats = [("四季时令", "Seasons & festivals", 20.2), ("花木草虫", "Flora & small creatures", 12.3),
            ("送别寄赠", "Parting & letters", 10.3), ("山水行旅", "Landscape & travel", 9.4),
            ("夜与独处", "Night & solitude", 6.9), ("感怀述志", "Reflections", 3.5),
            ("题画题物", "On paintings & objects", 3.4), ("宗教方外", "Religious life", 3.1),
            ("亲情家人", "Family", 2.3), ("闺怨宫怨", "Boudoir lament", 2.2),
            ("悼亡哭挽", "Mourning", 1.8), ("唱和次韵", "Matching rhymes", 1.6),
            ("读书论诗", "Books & poetics", 1.6), ("梦", "Dreams", 1.0),
            ("病中", "Illness", 0.9), ("自伤绝命", "Last words", 0.1)]
    idx = 0 if lang == "zh" else 1
    names = [c[idx] for c in cats][::-1]
    vals = [c[2] for c in cats][::-1]
    top4 = {c[idx] for c in cats[:4]}
    lament = cats[9][idx]
    fig, ax = canvas()
    fig.subplots_adjust(top=0.82, bottom=0.10, left={"zh": 0.15, "en": 0.24}[lang], right=0.90)
    colors = [INK if n in top4 else RED if n == lament else INK_FAINT for n in names]
    ax.barh(names, vals, height=0.62, color=colors, zorder=3)
    for i, (n, v) in enumerate(zip(names, vals)):
        ax.text(v + 0.25, i, f"{v}%", va="center", fontsize=12.5,
                color=RED if n == lament else INK, family=SONG,
                fontweight="bold" if n == lament else "normal")
    ax.set_xlim(0, 23)
    ax.set_xticks([])
    ax.tick_params(axis="y", labelsize={"zh": 13.5, "en": 12.5}[lang], colors=INK, length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
    t = {"zh": ("女性诗词题材分布", "9,749 首女性诗词的题目题材标记率"),
         "en": ("Themes in women's poems", "Title-keyword tagging rate across 9,749 poems by women")}[lang]
    note = {"zh": "基于诗题关键词分类(已剔除词牌干扰),约四成诗题无标记,占比为标记率 · 「中国古代才女」数据集",
            "en": "Tagged by title keywords, tune names excluded; ~40% of titles carry no tag · SheWrote dataset"}[lang]
    chrome(fig, t[0], t[1], note)
    fig.savefig(FIGS[lang] / "fig4_theme.png")
    plt.close(fig)


def fig_cloud(lang):
    from wordcloud import WordCloud
    from fontTools.ttLib import TTFont
    kai_path = font_manager.findfont(font_manager.FontProperties(family=KAI))
    tt = TTFont(kai_path, fontNumber=0)
    cmap = set(tt.getBestCmap().keys())
    profiles = json.load(open(ROOT / "data" / "out" / "women_profiles.json"))
    freq = {}
    for p in profiles:
        # 密集名字场只用真名(2026-07-09 定):柳是不再映射为柳如是
        name = T2S.convert(re.sub(r"[(（].*?[)）]", "", p["name"]))
        if len(name) < 2:
            continue
        if any(ord(ch) not in cmap for ch in name):
            continue
        freq[name] = freq.get(name, 0) + p["n_poems"]
    freq = {k: v ** 0.5 for k, v in freq.items()}
    top = set(sorted(freq, key=freq.get, reverse=True)[:10])

    def color_func(word, **kw):
        if word in top:
            return RED
        return ["#33302A", "#4A463D", "#6E6A5E", "#8A8579"][hash(word) % 4]

    wc = WordCloud(font_path=kai_path, width=1080, height=690, background_color=PAPER,
                   prefer_horizontal=0.95, max_words=400, margin=6,
                   min_font_size=9, max_font_size=110, random_state=7,
                   color_func=color_func)
    wc.generate_from_frequencies(freq)
    fig = plt.figure(figsize=(10.8, 8.1), dpi=100)
    fig.patch.set_facecolor(PAPER)
    ax = fig.add_axes([0.0, 0.06, 1.0, 0.76])
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    # 长效资产不放会变的数字(2026-07-10 社交卡定此原则,2026-07-11 词云跟进):
    # 收录数随修订持续增长,烙进图=每版都要重出;具体数字由 README 正文承载(发版时批量改)
    t = {"zh": ("中国古代女诗人", "字号大小对应存世作品量"),
         "en": ("Women poets of premodern China", "Font size ∝ number of surviving poems")}[lang]
    chrome(fig, t[0], t[1], NOTE[lang])
    fig.savefig(FIGS[lang] / "fig1_cloud.png")
    plt.close(fig)


if __name__ == "__main__":
    for lang in ("zh", "en"):
        fig_cloud(lang)
        fig_dynasty(lang)
        fig_place(lang)
        fig_theme(lang)
    print("done:", [str(p.relative_to(ROOT)) for d in FIGS.values() for p in sorted(d.glob("*.png"))])
