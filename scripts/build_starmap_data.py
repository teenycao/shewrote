#!/usr/bin/env python3
"""《她们的星空》数据打包:women_profiles + 代表句 + 可搜索题目索引 + 亲缘连线 → web/starmap_data.js"""
import csv
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

from opencc import OpenCC

T2S = OpenCC("t2s")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "out"
WEB = ROOT / "web"
WEB.mkdir(exist_ok=True)
DB = ROOT / "data" / "raw" / "cbdb" / "cbdb_20260627.sqlite3"

# 朝代 → 无年份者的落点(近似中值年)
DY_YEAR = {"汉": 50, "漢": 50, "魏晋": 300, "南北朝": 470, "隋": 595, "唐": 800, "五代": 940,
           "辽": 1030, "宋": 1120, "金": 1160, "元": 1300, "明": 1520, "清": 1750,
           "先秦": -400, "秦": -220, "隋末唐初": 615, "唐末宋初": 950, "宋末元初": 1270,
           "宋末金初": 1140, "金末元初": 1230, "元末明初": 1365, "明末清初": 1640, "魏晋末南北朝初": 420}


def main():
    profiles = json.load(open(OUT / "women_profiles.json"))
    poems = list(csv.DictReader(open(OUT / "women_poems.csv")))

    by_person = defaultdict(list)
    for p in poems:
        by_person[p["person_id"]].append(p)

    women = []
    for pr in profiles:
        pid = str(pr["person_id"])
        own_raw = by_person.get(pid, [])
        # A/B 两层去重(唐宋作品两库各存一份):按简体化题目+文本前缀
        seen, own = set(), []
        for q in own_raw:
            k = (T2S.convert(q["title"].replace(" ", "")).strip(), T2S.convert(q["text"].replace("/", "").replace("，", ",")[:20]))
            if k in seen:
                continue
            seen.add(k)
            own.append(q)
        # 代表句:取第一首的第一句(≤20 字)
        rep_title, rep_line = "", ""
        if own:
            first = own[0]
            rep_title = re.sub(r"\s+", " ", first["title"]).strip()[:20]
            rep_line = first["text"].split("/")[0].strip()[:22]
        # 年份落点
        year = None
        for k in ("index_year", "birth_year"):
            v = pr.get(k)
            if v and str(v).lstrip("-").isdigit():
                year = int(v)
                break
        if year is None:
            year = DY_YEAR.get(pr.get("dynasty", ""), 1500)
        # 可搜索文本:简体(名+别名+全部题目)
        titles = " ".join({T2S.convert(p["title"]) for p in own if p["title"]})
        hay = T2S.convert(pr["name"] + " " + (pr.get("aliases") or "")) + " " + titles
        women.append({
            "id": pid,
            "n": pr["name"],
            "py": pr.get("name_pinyin", ""),
            "dy": pr.get("dynasty", ""),
            "y": year,
            "b": pr.get("birth_year") or "",
            "d": pr.get("death_year") or "",
            "pl": pr.get("place") or "",
            "np": len(own) or int(pr["n_poems"]),
            "rt": rep_title,
            "rl": rep_line,
            "al": len((pr.get("aliases") or "").split("/")) if pr.get("aliases") else 0,
            "s": hay,
            "sn": T2S.convert(pr["name"] + " " + (pr.get("aliases") or "")),
        })

    # 亲缘连线(CBDB KIN_DATA,集内互为亲属)
    con = sqlite3.connect(DB)
    pids = [int(w["id"]) for w in women]
    ph = ",".join("?" * len(pids))
    kin_rows = con.execute(
        f"""SELECT k.c_personid, k.c_kin_id, c.c_kinrel_chn FROM KIN_DATA k
            JOIN KINSHIP_CODES c ON k.c_kin_code=c.c_kincode
            WHERE k.c_personid IN ({ph}) AND k.c_kin_id IN ({ph})""",
        pids + pids).fetchall()
    # CBDB KIN_DATA 每行 (c_personid=a, c_kin_id=b, rel):语义为「b 是 a 的 rel」(如 a=周兰秀,b=沈媛,rel=母 → 沈媛是周兰秀的母)。
    # 下游 build_kin 的三元组约定是「(x, y, label) = x 是 y 的 label」,故 x=c_kin_id(b)、y=c_personid(a),三元组存 (b, a, rel) 保方向。
    # 按无序对去重(每对亲属 CBDB 通常有正反两行,取先遇者;方向已在三元组主宾中保真,不依赖下游生卒年启发式补方向)。
    pairs = {}
    for a, b, rel in kin_rows:
        pairs.setdefault(tuple(sorted((a, b))), (str(b), str(a), rel))
    kin = [list(v) for v in pairs.values()]

    data = {"women": women, "kin": kin,
            "meta": {"total": len(women), "poems": len(poems), "shi_poems": 376, "shi_names": 96}}  # shi_* 来自 author_match 审计,更新时同步
    js = "const STAR_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";"
    (WEB / "starmap_data.js").write_text(js)
    print(f"women={len(women)} kin_pairs={len(kin)} size={(WEB/'starmap_data.js').stat().st_size//1024}KB")


if __name__ == "__main__":
    main()
