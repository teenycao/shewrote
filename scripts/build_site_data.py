#!/usr/bin/env python3
"""导出卡牌站(shewrote-site)构建数据。

展示层口径:站点全部使用简体,以保证主要读者群的可读性;
数据集本体(women_profiles/poems CSV)保持繁体原貌不动——简化只发生在本导出层。

合成三个源:
- data/out/women_profiles.csv  档案(权威字段)
- data/out/women_poems.csv     全部诗作全文
- web/starmap_data.js          代表句 rt/rl(复用星图管线的甄选)

产出 data/out/site/:
- poets.json     全部女性索引(轻,前端舞台/搜索直接吃):id/slug/名/简体名/拼音/朝代/生卒/籍贯/字号/存诗量/代表句
- poems.json     {person_id: [{t,x}]} 全文(重,仅构建期用)

slug 规则:name_pinyin 小写连字符;撞名追加 -{person_id}(可读优先,id 兜底)。
"""
import csv
import json
import re
from pathlib import Path

from opencc import OpenCC

_T2S = OpenCC("t2s")

# t2s 陷阱与异体字兜底:
# 沈=姓氏,禁转「沉」(OpenCC 在部分语境会转);其余为 OpenCC 不覆盖的异体字
_PROTECT = "沈"
_VARIANTS = {"鵶": "鸦", "僊": "仙", "陜": "陕", "谿": "溪", "栢": "柏"}


def convert(s, _lang=None):
    if not s:
        return s
    guarded = s.replace(_PROTECT, "\x00")
    out = _T2S.convert(guarded).replace("\x00", _PROTECT)
    for a, b in _VARIANTS.items():
        out = out.replace(a, b)
    return out

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "out" / "site"
OUT.mkdir(parents=True, exist_ok=True)


def load_star():
    raw = (ROOT / "web" / "starmap_data.js").read_text()
    m = re.search(r"const STAR_DATA = (\{.*)", raw, re.S)
    d = json.loads(m.group(1).strip().rstrip(";"))
    return {w["id"]: w for w in d["women"]}, d.get("kin", [])


# kin 三元组语义:(a, b, label) = a 是 b 的 label(锚点验证:沈宜修-母->葉小鸞)
# 反向标签:b 在 a 页显示为 INV[label]
KIN_INV = {
    "母": "女", "女兒": "母", "姊": "妹", "姊妹": "姊妹",
    "從妹": "從姊", "從女;姪女": "姑母", "子婦;兒媳": "婆母",
    "夫之姐妹": "兄弟之妻", "孫女": "祖母", "表姐妹": "表姐妹",
    "從姊妹": "從姊妹",
}
KIN_DISP = {"從女;姪女": "姪女", "子婦;兒媳": "兒媳"}

# 注:2026-07-10 曾加过一套「生卒年方向校正」(KIN_AGE_SIGN + 同年降级),本是为遮 build_starmap_data
# 的 sorted() 丢方向 bug。2026-07-13 已在源头保方向(见 build_starmap_data),且经交叉核实发现
# 估算生年会误翻真实 kin code(张学雅一门姐妹估年并列 1649 → 误把长姊学雅翻成妹),故整套年龄启发式移除:
# 方向与长幼一律以 CBDB kin code 为准。生卒年真实性交由 v1.4 MQWW 系统校验单独处理。


def build_kin(kin_pairs):
    """person_id -> [{id, rel}];方向与长幼以 CBDB kin code 为准,正反双向展开。"""
    out = {}
    seen = set()
    for a, b, lab in kin_pairs:
        if (a, b, lab) in seen:
            continue
        seen.add((a, b, lab))
        # 方向与长幼一律以 CBDB kin code 为准(build_starmap_data 已在三元组主宾中保方向)。
        # 既不按生卒年翻转方向,也不对同年姐妹降级:CBDB 生年多为估算上界(如张学雅一门姐妹并列
        # 估作 1649),用不可靠估算年覆盖 kin code 会致错(2026-07-13 交叉核实:张学雅/张学鲁
        # 曾被误翻;故完全以 kin code 为准)。生卒年真实性待 v1.4 MQWW 系统校验时另行核。
        out.setdefault(b, []).append({"id": a, "rel": KIN_DISP.get(lab, lab)})
        inv = KIN_INV.get(lab)
        if inv:
            out.setdefault(a, []).append({"id": b, "rel": inv})
    print(f"kin: 方向与长幼一律以 CBDB kin code 为准({sum(len(v) for v in out.values())} 条展示)")
    return out


def slugify(py, pid, used):
    s = re.sub(r"[^a-z0-9]+", "-", py.lower()).strip("-") or f"p-{pid}"
    if s in used:
        s = f"{s}-{pid}"
    used.add(s)
    return s


def main():
    star, kin_pairs = load_star()
    kin_by_person = build_kin(kin_pairs)

    # A/B 层去重,键与 build_profiles.py 完全同构(v1.2 起:忽略标题,poem_norm 全文归一。
    # 旧键无法覆盖标题规范差「六首 一/其一」与异体字「鴈/雁」造成的重复。)
    # 用 .venv/bin/python 运行(opencc 在 venv 里);跑完校验总数=Σn_poems
    # 注:A 行在 csv 前部——同诗两版保留 A(带 / 分行结构,展示需要)
    from poem_norm import Deduper
    poems_by_person = {}
    dd = Deduper()
    with open(ROOT / "data" / "out" / "women_poems.csv") as f:
        for r in dd.dedupe_records(list(csv.DictReader(f))):
            poems_by_person.setdefault(r["person_id"], []).append(
                {"t": convert(r["title"], "zh-cn"), "x": convert(r["text"], "zh-cn")}
            )

    # 补源诗(supplement_poems.csv,include_in_site):语料外补录,汇入展示;带 s=sup 供页面标出处(§6)。
    # 语料 women_poems.csv 保持纯语料不含补源——此为站点组装层合并。
    SUP_POEMS = ROOT / "data" / "curated" / "supplement_poems.csv"
    if SUP_POEMS.exists():
        n_sup = 0
        for r in csv.DictReader(open(SUP_POEMS, encoding="utf-8")):
            if (r.get("include_in_site") or "1").strip() != "1":
                continue
            _poem = {"t": convert(r["title"], "zh-cn"), "x": convert(r["text"], "zh-cn"),
                     "s": "sup", "sr": convert((r.get("source_title") or "").strip(), "zh-cn")}
            # 待核补录:transcription_status 非 verified → 带 pd 标,页面显示「出处待核」而非假出处
            if (r.get("transcription_status") or "").strip() not in ("", "verified"):
                _poem["pd"] = 1
            poems_by_person.setdefault(r["person_id"].strip(), []).append(_poem)
            n_sup += 1
        if n_sup:
            print(f"补源诗: +{n_sup} 首(语料外,带 s=sup)")

    poets, used = [], set()
    with open(ROOT / "data" / "out" / "women_profiles.csv") as f:
        rows = list(csv.DictReader(f))
    # 存诗量降序、同量按名,与星图一致的稳定顺序
    rows.sort(key=lambda r: (-int(r["n_poems"] or 0), r["name"]))

    s = lambda v: convert(v, "zh-cn") if v else v
    for r in rows:
        pid = r["person_id"]
        st = star.get(pid, {})
        rt, rl = s(st.get("rt")), s(st.get("rl"))
        if not rl:  # 补源人等无星图代表句:取首诗兜底(poems_by_person 已简体,不再转)
            fp = (poems_by_person.get(pid) or [{}])[0]
            rt = rt or fp.get("t")
            body = fp.get("x") or ""
            rl = rl or (body.split("。")[0][:24] + ("。" if "。" in body[:25] else ""))
        al = (r["aliases"] or "").replace(" / ", "、")
        kin = kin_by_person.get(pid)
        poets.append({
            "id": pid,
            "slug": slugify(r["name_pinyin"] or "", pid, used),
            "n": s(r["name"]),
            "ns": s(r["name"]),  # 简体展示后与 n 相同,保留字段兼容搜索逻辑
            "py": r["name_pinyin"],
            "dy": s(r["dynasty"]),
            "b": int(r["birth_year"]) if r["birth_year"] else None,
            "d": int(r["death_year"]) if r["death_year"] else None,
            "pl": s(r["place"]) or None,
            "al": s(al) or None,
            "als": s(al) or None,
            "np": int(r["n_poems"] or 0),
            "rt": rt,
            "rl": rl,
            "mqww": r["in_mqww"] == "1",
            "kin": [{"id": k["id"], "rel": s(k["rel"])} for k in kin] if kin else None,
            "sup": r.get("supplement") == "1",
        })

    (OUT / "poets.json").write_text(
        json.dumps(poets, ensure_ascii=False, separators=(",", ":"))
    )
    (OUT / "poems.json").write_text(
        json.dumps(poems_by_person, ensure_ascii=False, separators=(",", ":"))
    )
    n_poems = sum(len(v) for v in poems_by_person.values())
    np_sum = sum(p["np"] for p in poets)
    print(f"poets.json: {len(poets)} 人 | poems.json: {n_poems} 首(去重后) vs Σn_poems={np_sum}")
    mismatch = [(p["n"], p["np"], len(poems_by_person.get(p["id"], [])))
                for p in poets if p["np"] != len(poems_by_person.get(p["id"], []))]
    if mismatch:
        print(f"⚠️ {len(mismatch)} 人条数与 np 不符(转换器差异?),前 5: {mismatch[:5]}")
    else:
        print(f"✅ 全部 {len(poets)} 人诗数与 n_poems 精确一致")
    missing_rep = sum(1 for p in poets if not p["rl"])
    print(f"无代表句: {missing_rep} | slug 撞名兜底: {sum(1 for p in poets if p['slug'].endswith('-'+p['id']))}")


if __name__ == "__main__":
    main()
