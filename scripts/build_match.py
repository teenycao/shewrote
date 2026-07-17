#!/usr/bin/env python3
"""M1 匹配管线 v2:语料作者 ↔ CBDB(简体归一键 + 精确 + ALTNAME 别名 + 僧名剥前缀 + 朝代消歧 + 性别共识)。

Layer A = chinese-poetry(唐宋五代,底本可考)
Layer B = Werneror/Poetry(先秦至清,聚合库,排除近现代/当代)

输出:
  data/interim/author_match.csv   全部唯一 (作者, 朝代标签, layer) 的匹配结果与分桶
  data/interim/women_resolved.csv 唯一命中的女性作者(才女档案表原料)
  data/interim/review_multi.csv   多重命中,人工复核队列(按作品量降序)
  stdout                          分层统计(X%/Y% 第一版)

分桶:
  resolved         唯一人选(直接唯一 / 朝代过滤后唯一)
  multi_consensus  多候选但性别一致 → 计入性别统计,人物归属待复核
  multi            多候选且性别不一 → 人工复核
  era_conflict     有同名人但朝代全不兼容 → 视为未匹配(防错认)
  monk             釋/释 前缀僧人,剥前缀仍无命中(CBDB 覆盖缺口)
  institutional    机构性署名(郊庙乐章类),非个人
  anonymous        无名氏/佚名类
  shi_pattern      「X氏」型(女性标记名,单独统计=数据即论点)
  unmatched        无任何命中
"""
import csv
import glob
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

from opencc import OpenCC

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
DB = RAW / "cbdb" / "cbdb_20260627.sqlite3"
CURATED = ROOT / "data" / "curated" / "overrides.csv"
ALIASES = ROOT / "data" / "curated" / "aliases.csv"
CURATED_PEOPLE = ROOT / "data" / "curated" / "curated_people.csv"

T2S = OpenCC("t2s")

ANON = {"無名氏", "无名氏", "佚名", "闕名", "阙名", "失名", "不詳", "不详", "無名", "无名"}
SHI_PAT = re.compile(r"^[一-鿿]{1,2}氏(\(.+\))?$")
INST_PAT = re.compile(r"歌辭|歌辞|樂章|乐章|樂府|郊廟|郊庙|朝會|朝会")
MONK_PAT = re.compile(r"^[釋释]")

# 语料朝代标签 → 允许的 CBDB c_dy 集合(0=未詳恒允许;含相邻朝代,跨代人物常被 CBDB 编入后代)
WUDAI = {7, 8, 9, 10, 11, 12, 13, 34, 36, 38}
DY = {
    "先秦": {1}, "秦": {1, 2}, "汉": {1, 2, 3, 25, 29, 46}, "漢": {1, 2, 3, 25, 29, 46},
    "魏晋": {2, 3, 4, 23, 25, 26, 27, 42}, "魏晋末南北朝初": {3, 4, 23, 26, 27, 42},
    "南北朝": {3, 4, 5, 23, 24, 27, 28, 30, 31, 32, 35, 37, 40, 41, 44, 45},
    "隋": {4, 5, 6}, "隋末唐初": {4, 5, 6}, "唐": {5, 6} | WUDAI, "唐末宋初": {6, 15} | WUDAI,
    "五代": {6, 15} | WUDAI, "宋": {15, 16, 17, 18} | WUDAI, "宋末金初": {15, 16, 17},
    "宋末元初": {15, 17, 18}, "金": {15, 16, 17, 18}, "金末元初": {15, 17, 18},
    "辽": {6, 15, 16, 17}, "元": {15, 17, 18, 19}, "元末明初": {17, 18, 19},
    "明": {18, 19, 20}, "明末清初": {19, 20}, "清": {19, 20, 21},
}
WERNEROR_EXCLUDE = {"当代", "近现代", "民国末当代初", "近现代末当代初", "清末近现代初", "清末民国初"}


def load_corpus():
    """yield (layer, dynasty_label, author_raw) per poem"""
    cp = RAW / "chinese-poetry"
    for f in sorted(glob.glob(str(cp / "全唐诗" / "poet.tang.*.json"))):
        for p in json.load(open(f)):
            yield "A", "唐", p.get("author", "")
    for f in sorted(glob.glob(str(cp / "全唐诗" / "poet.song.*.json"))):
        for p in json.load(open(f)):
            yield "A", "宋", p.get("author", "")
    for f in sorted(glob.glob(str(cp / "宋词" / "ci.song.*.json"))):
        for p in json.load(open(f)):
            yield "A", "宋", p.get("author", "")
    for f in glob.glob(str(cp / "五代诗词" / "**" / "*.json"), recursive=True):
        try:
            data = json.load(open(f))
        except Exception:
            continue
        if isinstance(data, list):
            for p in data:
                if isinstance(p, dict) and p.get("author") and (p.get("paragraphs") or p.get("sentences")):
                    yield "A", "五代", p["author"]
    for f in sorted(glob.glob(str(RAW / "werneror-poetry" / "*.csv"))):
        name = Path(f).stem.split("_")[0]
        if name in WERNEROR_EXCLUDE:
            continue
        with open(f, newline="") as fh:
            for row in csv.DictReader(fh):
                dy = (row.get("朝代") or "").strip()
                if dy and dy not in WERNEROR_EXCLUDE:
                    yield "B", dy, (row.get("作者") or "").strip()


def load_cbdb():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    person = {}  # pid -> (name_chn, female, dy)
    by_key = defaultdict(set)   # 简体归一键 -> pids(正名)
    by_alias = defaultdict(set)  # 简体归一键 -> pids(别名)
    for pid, name, female, dy in cur.execute(
        "SELECT c_personid, c_name_chn, c_female, c_dy FROM BIOG_MAIN WHERE c_name_chn IS NOT NULL"
    ):
        person[pid] = (name, 1 if female == 1 else 0 if female == 0 else None, dy if dy is not None else 0)
        by_key[T2S.convert(name)].add(pid)
    for pid, alt in cur.execute("SELECT c_personid, c_alt_name_chn FROM ALTNAME_DATA WHERE c_alt_name_chn IS NOT NULL"):
        by_alias[T2S.convert(alt)].add(pid)
    mqww = {r[0] for r in cur.execute("SELECT DISTINCT c_personid FROM BIOG_SOURCE_DATA WHERE c_textid=9601")}
    con.close()
    return person, by_key, by_alias, mqww


# 避讳/异体字变体对(简体键空间;仅在正常匹配失败后才尝试,降低误匹配面)
# 禛↔祯:雍正帝胤禛讳(王士禛/王士祯);玄↔元:康熙帝玄烨讳(魚玄機/魚元機)
# 丘↔邱:孔子讳(丘逢甲/邱逢甲);弘↔宏:乾隆帝弘历讳
VARIANTS = {"禛": "祯", "祯": "禛", "玄": "元", "元": "玄",
            "丘": "邱", "邱": "丘", "弘": "宏", "宏": "弘"}


def variant_keys(key_s):
    """yield 单字变体替换后的候选键(每次替换一个位置,不做组合爆炸)"""
    for i, ch in enumerate(key_s):
        if ch in VARIANTS:
            yield key_s[:i] + VARIANTS[ch] + key_s[i + 1:]


def load_overrides():
    """人工补充表(data/curated/overrides.csv,逐条注明文献依据):
    gender   = CBDB 性别字段缺失的有据补注(person_id → female)
    identity = 同名多候选/重复条目的有据归人(简体作者键 → person_id)
    原则不变:标记,不猜测——此表只收文献确凿者,来源写在 note 列。"""
    gender, identity = {}, {}
    if CURATED.exists():
        for r in csv.DictReader(open(CURATED)):
            if r["type"] == "gender":
                gender[int(r["person_id"])] = int(r["female"])
            elif r["type"] == "identity":
                identity[r["author_key"]] = int(r["person_id"])
    return gender, identity


def load_aliases():
    """人工别名表(data/curated/aliases.csv):
    signature = 语料署名 → CBDB person_id,参与匹配与统计
    search    = 大众检索别称,不参与匹配与统计(由 build_profiles.py 消费)
    display   = 档案展示名:替换 person 表主名(CBDB 正名系婚属描述符等情形,依文献通名)
    feature   = 档案「字号」头衔前置(由 build_profiles.py 消费,此处仅放行不用)
    """
    signature = {}
    display = {}
    if not ALIASES.exists():
        return signature, display
    for r in csv.DictReader(open(ALIASES)):
        kind = (r.get("kind") or "").strip()
        alias = (r.get("alias") or "").strip()
        pid = int((r.get("person_id") or "0").strip())
        if kind not in {"signature", "search", "display", "feature"}:
            raise ValueError(f"unknown aliases.csv kind: {kind!r}")
        if not alias or not pid:
            raise ValueError(f"invalid aliases.csv row: {r}")
        if kind == "signature":
            key = T2S.convert(alias)
            if key in signature and signature[key] != pid:
                raise ValueError(f"conflicting signature alias {alias!r}: {signature[key]} vs {pid}")
            signature[key] = pid
        elif kind == "display":
            if pid in display and display[pid] != alias:
                raise ValueError(f"conflicting display name for {pid}: {display[pid]} vs {alias}")
            display[pid] = alias
    return signature, display


def probe(key_s, by_key, by_alias):
    """返回 (candidates, via);正名优先,别名兜底,变体最后"""
    if key_s in by_key:
        return set(by_key[key_s]), "exact"
    if key_s in by_alias:
        return set(by_alias[key_s]), "alias"
    for vk in variant_keys(key_s):
        if vk in by_key:
            return set(by_key[vk]), "variant+exact"
        if vk in by_alias:
            return set(by_alias[vk]), "variant+alias"
    return set(), ""


# 朝代标签 → c_dy 代表码,仅作 curated 合成 person 的占位(curated 人不走候选池,dy 不参与消歧/统计)
_CUR_DY = {"东汉": 3, "汉": 3, "魏晋": 4, "晋": 4, "唐": 6, "宋": 15, "南宋": 15, "南宋末": 15,
           "辽": 16, "元": 18, "明": 19, "清": 20}


def load_curated_people():
    """curated_people.csv:诗在语料、CBDB 无传记档案者,分配合成 person_id(9000000x)建合成档案。
    返回 corpus_key(简体归一)-> pid,以及 person 补充项 pid -> (name, dy_code);curated 人一律 female=1。"""
    cmap, cpersons = {}, {}
    if not CURATED_PEOPLE.exists():
        return cmap, cpersons
    for r in csv.DictReader(open(CURATED_PEOPLE, encoding="utf-8")):
        pid = int(r["curated_id"])
        key = T2S.convert((r["corpus_key"] or "").strip())
        name = (r["name"] or "").strip()
        if not key or not name:
            raise ValueError(f"invalid curated_people.csv row: {r}")
        if key in cmap and cmap[key] != pid:
            raise ValueError(f"conflicting curated corpus_key {key!r}: {cmap[key]} vs {pid}")
        cmap[key] = pid
        cpersons[pid] = (name, _CUR_DY.get((r["dynasty"] or "").strip(), 0))
    return cmap, cpersons


def main():
    INTERIM.mkdir(parents=True, exist_ok=True)
    person, by_key, by_alias, mqww = load_cbdb()
    print(f"CBDB loaded: {len(person)} persons, {len(by_key)} name keys, {len(by_alias)} alias keys", file=sys.stderr)

    g_over, id_over = load_overrides()
    signature_aliases, display_names = load_aliases()
    for pid, fem in g_over.items():
        if pid in person:
            name, _, dy = person[pid]
            person[pid] = (name, fem, dy)
    for pid, disp in display_names.items():
        if pid not in person:
            raise ValueError(f"aliases.csv display person_id not found in CBDB: {pid}")
        _, fem, dy = person[pid]
        person[pid] = (disp, fem, dy)
    if g_over or id_over:
        print(f"curated overrides: {len(g_over)} gender, {len(id_over)} identity", file=sys.stderr)
    if signature_aliases or display_names:
        print(f"curated aliases: {len(signature_aliases)} signature, {len(display_names)} display", file=sys.stderr)

    # curated_people:诗在语料、CBDB 无档者建合成档案(合成 pid 注入 person 表,一律 female=1)
    curated_map, curated_persons = load_curated_people()
    for pid, (name, dy) in curated_persons.items():
        person[pid] = (name, 1, dy)
    if curated_map:
        print(f"curated persons: {len(curated_map)} corpus keys → {len(curated_persons)} synthetic archives", file=sys.stderr)

    counts = defaultdict(int)
    for layer, dy, author in load_corpus():
        counts[(layer, dy, author.strip())] += 1
    print(f"corpus loaded: {sum(counts.values())} poems, {len(counts)} unique (layer,dy,author)", file=sys.stderr)

    rows = []
    for (layer, dylabel, raw), n in counts.items():
        key = T2S.convert(raw)
        base = dict(layer=layer, dynasty=dylabel, author=raw, n_poems=n,
                    via="", person_id="", name_chn="", female="", n_cand=0)

        if not raw or key in ANON or raw in ANON:
            rows.append({**base, "bucket": "anonymous"})
            continue
        if INST_PAT.search(raw):
            rows.append({**base, "bucket": "institutional"})
            continue
        if SHI_PAT.match(key):
            rows.append({**base, "bucket": "shi_pattern"})
            continue

        # 人工署名别名:只按归一后的完整署名字符串命中,不做模糊匹配。
        # 与 overrides.csv 的 identity 不同,这里表示“同一人多署名”,不是 CBDB 档案纠错。
        if key in signature_aliases:
            pid = signature_aliases[key]
            if pid not in person:
                raise ValueError(f"aliases.csv person_id not found in CBDB: {pid}")
            name, female, _ = person[pid]
            rows.append({**base, "bucket": "resolved", "via": "curated_alias",
                         "person_id": pid, "name_chn": name,
                         "female": "" if female is None else female, "n_cand": 1})
            continue

        cands, via = probe(key, by_key, by_alias)
        if not cands and MONK_PAT.match(key):
            bare = key[1:]
            cands, via = probe(bare, by_key, by_alias)
            if not cands:
                cands, via = probe("释" + bare, by_key, by_alias)
            if cands:
                via = "monk+" + via
            else:
                rows.append({**base, "bucket": "monk"})
                continue
        if not cands:
            # curated_people:语料署名无 CBDB 候选,但已在 curated_people.csv 建合成档案 → 归合成 pid
            if key in curated_map:
                pid = curated_map[key]
                name, female, _ = person[pid]
                rows.append({**base, "bucket": "resolved", "via": "curated_person",
                             "person_id": pid, "name_chn": name,
                             "female": female, "n_cand": 0})
                continue
            rows.append({**base, "bucket": "unmatched"})
            continue

        allowed = DY.get(dylabel, set())

        # 人工归人(overrides.csv identity):候选中含指定 person、且其 CBDB 朝代与本行朝代标签相容时直取,via=curated。
        # 朝代相容判定与下方 pool 同口径(在 allowed 集内或 c_dy=0 未详);防同名跨朝代误归——
        # 如作者键「张乔」的候选含唐男与明女(566553),override 只应作用于明代张乔那批,不得把唐男诗强归女性。
        if key in id_over and id_over[key] in cands and (person[id_over[key]][2] in allowed or person[id_over[key]][2] == 0):
            pid = id_over[key]
            name, female, _ = person[pid]
            rows.append({**base, "bucket": "resolved", "via": "curated",
                         "person_id": pid, "name_chn": name,
                         "female": "" if female is None else female, "n_cand": len(cands)})
            continue

        pool = [p for p in cands if person[p][2] in allowed or person[p][2] == 0]
        if len(pool) == 1:
            pid = pool[0]
            name, female, _ = person[pid]
            rows.append({**base, "bucket": "resolved", "via": via + ("+dy" if len(cands) > 1 else ""),
                         "person_id": pid, "name_chn": name,
                         "female": "" if female is None else female, "n_cand": len(cands)})
        elif len(pool) == 0:
            rows.append({**base, "bucket": "era_conflict", "via": via, "n_cand": len(cands)})
        else:
            genders = {person[p][1] for p in pool}
            if len(genders) == 1 and None not in genders:
                rows.append({**base, "bucket": "multi_consensus", "via": via,
                             "female": genders.pop(), "n_cand": len(pool)})
            else:
                rows.append({**base, "bucket": "multi", "via": via, "n_cand": len(pool)})

    # curated_poems(诗级归属):把 (corpus_author, title) 精确指定的诗从原作者聚合中移出、
    # 归到合成女性 person(如《载驰》原署「诗经」,据《毛诗序》《列女传》归许穆夫人,仅此一首)。
    # poems_total 守恒:从原作者行减 N、加一条合成女性 resolved 行(n_poems=N);诗级 emit 在 build_release。
    CURATED_POEMS = ROOT / "data" / "curated" / "curated_poems.csv"
    if CURATED_POEMS.exists():
        dec = defaultdict(int)   # (layer, dynasty, 简体作者键) -> 应从原作者聚合移出的首数
        cp_persons = {}          # person_id -> dict(name, layer, dynasty, n)
        for r in csv.DictReader(open(CURATED_POEMS, encoding="utf-8")):
            dec[(r["layer"], r["dynasty"], T2S.convert((r["corpus_author"] or "").strip()))] += 1
            d = cp_persons.setdefault(int(r["person_id"]),
                                      dict(name=r["name"], layer=r["layer"], dynasty=r["dynasty"], n=0))
            d["n"] += 1
        for row in rows:
            k = (row["layer"], row["dynasty"], T2S.convert((row["author"] or "").strip()))
            if dec.get(k, 0) > 0 and row["n_poems"] > 0:
                take = min(dec[k], row["n_poems"])
                row["n_poems"] -= take
                dec[k] -= take
        for k, rem in dec.items():
            if rem > 0:
                print(f"⚠️ curated_poems 未能从原作者移出 {rem} 首:{k}(核 corpus_author/layer/dynasty)", file=sys.stderr)
        for pid, d in cp_persons.items():
            person[pid] = (d["name"], 1, 0)
            rows.append({"layer": d["layer"], "dynasty": d["dynasty"], "author": d["name"],
                         "n_poems": d["n"], "bucket": "resolved", "via": "curated_poem",
                         "person_id": pid, "name_chn": d["name"], "female": 1, "n_cand": 0})
        if cp_persons:
            print(f"curated poems: {sum(d['n'] for d in cp_persons.values())} 首诗级归属 → {len(cp_persons)} 位合成女性", file=sys.stderr)

    fields = ["layer", "dynasty", "author", "n_poems", "bucket", "via",
              "person_id", "name_chn", "female", "n_cand"]
    with open(INTERIM / "author_match.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: -r["n_poems"]))

    with open(INTERIM / "review_multi.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(sorted((r for r in rows if r["bucket"] in ("multi", "multi_consensus", "era_conflict")),
                           key=lambda r: -r["n_poems"]))

    # 才女档案原料:resolved & female,按 person 聚合
    women = defaultdict(lambda: dict(n_poems=0, layers=set(), dynasties=set(), corpus_names=set()))
    for r in rows:
        if r["bucket"] == "resolved" and r["female"] == 1:
            wrec = women[r["person_id"]]
            wrec["n_poems"] += r["n_poems"]
            wrec["layers"].add(r["layer"])
            wrec["dynasties"].add(r["dynasty"])
            wrec["corpus_names"].add(r["author"])
    with open(INTERIM / "women_resolved.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["person_id", "name_chn", "n_poems", "layers", "dynasties", "corpus_names", "in_mqww"])
        for pid, wrec in sorted(women.items(), key=lambda kv: -kv[1]["n_poems"]):
            w.writerow([pid, person[pid][0], wrec["n_poems"], "/".join(sorted(wrec["layers"])),
                        "/".join(sorted(wrec["dynasties"])), "/".join(sorted(wrec["corpus_names"])),
                        1 if pid in mqww else 0])

    # 分层统计
    for layer in ("A", "B"):
        lr = [r for r in rows if r["layer"] == layer]
        total = sum(r["n_poems"] for r in lr)
        b = defaultdict(int)
        for r in lr:
            b[r["bucket"]] += r["n_poems"]
        fem_s = sum(r["n_poems"] for r in lr if r["bucket"] == "resolved" and r["female"] == 1)
        male_s = sum(r["n_poems"] for r in lr if r["bucket"] == "resolved" and r["female"] == 0)
        fem_i = fem_s + sum(r["n_poems"] for r in lr if r["bucket"] == "multi_consensus" and r["female"] == 1)
        male_i = male_s + sum(r["n_poems"] for r in lr if r["bucket"] == "multi_consensus" and r["female"] == 0)
        fem_au = len({r["person_id"] for r in lr if r["bucket"] == "resolved" and r["female"] == 1})
        male_au = len({r["person_id"] for r in lr if r["bucket"] == "resolved" and r["female"] == 0})
        print(f"\n=== Layer {layer} ===")
        print(f"poems total={total}  unique(author,dy)={len({(r['author'], r['dynasty']) for r in lr})}")
        for k in ("resolved", "multi_consensus", "multi", "era_conflict", "monk",
                  "unmatched", "institutional", "anonymous", "shi_pattern"):
            print(f"  {k:15s} {b[k]:>8d} poems ({b[k]/total*100:.2f}%)")
        gr = fem_i + male_i
        print(f"  [strict]    female poems {fem_s}  ({fem_s/total*100:.2f}% of all; {fem_s/(fem_s+male_s)*100:.2f}% of resolved)")
        print(f"  [inclusive] female poems {fem_i}  ({fem_i/total*100:.2f}% of all; {fem_i/gr*100:.2f}% of gender-known {gr})")
        print(f"  female authors (resolved persons): {fem_au} / {fem_au+male_au} ({fem_au/(fem_au+male_au)*100:.2f}%)")


if __name__ == "__main__":
    main()
