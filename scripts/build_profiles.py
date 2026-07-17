#!/usr/bin/env python3
"""才女档案表生成:women_resolved.csv(匹配产物)× CBDB 档案字段。

输出:
  data/out/women_profiles.csv   档案表(发布物雏形,person 一等公民)
  data/out/women_profiles.json  同内容 JSON(嵌套别名/身份/地理)
  stdout                        身份构成/朝代分布统计
"""
import csv
import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

from opencc import OpenCC

T2S = OpenCC("t2s")

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "raw" / "cbdb" / "cbdb_20260627.sqlite3"
CURATED_PEOPLE = ROOT / "data" / "curated" / "curated_people.csv"
INTERIM = ROOT / "data" / "interim"
OUT = ROOT / "data" / "out"
ALIASES = ROOT / "data" / "curated" / "aliases.csv"

ALT_TYPES = {3: "别名", 4: "字", 5: "号", 6: "谥号", 8: "封爵", 9: "小名", 10: "小字", 11: "赐号"}


def load_search_aliases(pids):
    """kind=search 只补档案别名/站内搜索;kind=display 替换档案展示名(附拼音);
    kind=feature 指定档案「字号」头衔——将该别名提到别名列表首位
    (前端 aliasList 无字/号时兜底取 [0],故 [0] 即头衔展示位)。"""
    out = defaultdict(list)
    display = {}
    feature = {}
    if not ALIASES.exists():
        return out, display, feature
    pid_set = set(pids)
    for r in csv.DictReader(open(ALIASES)):
        kind = (r.get("kind") or "").strip()
        alias = (r.get("alias") or "").strip()
        pid = int((r.get("person_id") or "0").strip())
        if kind not in {"signature", "search", "display", "feature"}:
            raise ValueError(f"unknown aliases.csv kind: {kind!r}")
        if not alias or not pid:
            raise ValueError(f"invalid aliases.csv row: {r}")
        if kind == "search" and pid in pid_set:
            out[pid].append(alias)
        elif kind == "display" and pid in pid_set:
            display[pid] = (alias, (r.get("pinyin") or "").strip())
        elif kind == "feature" and pid in pid_set:
            feature[pid] = alias
    return out, display, feature


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    women = list(csv.DictReader(open(INTERIM / "women_resolved.csv")))
    # 去重后的存世量:唐宋作品在 A/B 两库各存一份。
    # v1.2 起忽略标题、全文归一比对(poem_norm:t2s+异体折叠+去标点)——
    # 旧键(标题+前 20 字)被「六首 一/其一」类标题规范差与鴈/雁类异体打穿(815 对漏网)
    from poem_norm import Deduper
    dedup_np = defaultdict(int)
    dd = Deduper()
    for q in dd.dedupe_records(list(csv.DictReader(open(OUT / "women_poems.csv")))):
        dedup_np[q["person_id"]] += 1
    pids = [int(w["person_id"]) for w in women]
    ph = ",".join("?" * len(pids))

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    main_rows = {r["c_personid"]: r for r in cur.execute(f"""
        SELECT b.c_personid, b.c_name_chn, b.c_name, b.c_birthyear, b.c_deathyear,
               b.c_index_year, b.c_death_age, b.c_index_addr_id, b.c_notes, d.c_dynasty_chn
        FROM BIOG_MAIN b LEFT JOIN DYNASTIES d ON b.c_dy = d.c_dy
        WHERE b.c_personid IN ({ph})""", pids)}

    aliases = defaultdict(list)
    for r in cur.execute(f"""
        SELECT c_personid, c_alt_name_chn, c_alt_name_type_code FROM ALTNAME_DATA
        WHERE c_personid IN ({ph})""", pids):
        t = ALT_TYPES.get(r["c_alt_name_type_code"], "")
        aliases[r["c_personid"]].append(f"{r['c_alt_name_chn']}({t})" if t else r["c_alt_name_chn"])
    curated_search_aliases, display_names, feature_names = load_search_aliases(pids)
    for pid, names in curated_search_aliases.items():
        existing = {T2S.convert(a.split("(", 1)[0]) for a in aliases.get(pid, [])}
        for name in names:
            key = T2S.convert(name)
            if key not in existing:
                aliases[pid].append(name)
                existing.add(key)

    statuses = defaultdict(list)
    for r in cur.execute(f"""
        SELECT s.c_personid, c.c_status_desc_chn FROM STATUS_DATA s
        JOIN STATUS_CODES c USING(c_status_code)
        WHERE s.c_personid IN ({ph}) ORDER BY s.c_sequence""", pids):
        if r["c_status_desc_chn"] and r["c_status_desc_chn"] not in statuses[r["c_personid"]]:
            statuses[r["c_personid"]].append(r["c_status_desc_chn"])

    # 籍贯优先级:index_addr > 籍貫(1) > 本貫(7) > 出生地(8) > 任意
    addr = {}
    for r in cur.execute(f"""
        SELECT a.c_personid, a.c_addr_type, ac.c_name_chn, ac.x_coord, ac.y_coord
        FROM BIOG_ADDR_DATA a JOIN ADDR_CODES ac USING(c_addr_id)
        WHERE a.c_personid IN ({ph})""", pids):
        pid = r["c_personid"]
        rank = {1: 0, 7: 1, 8: 2}.get(r["c_addr_type"], 9)
        if pid not in addr or rank < addr[pid][0]:
            addr[pid] = (rank, r["c_name_chn"], r["x_coord"], r["y_coord"])
    idx_addr = {}
    for r in cur.execute(f"""
        SELECT b.c_personid, ac.c_name_chn, ac.x_coord, ac.y_coord
        FROM BIOG_MAIN b JOIN ADDR_CODES ac ON b.c_index_addr_id = ac.c_addr_id
        WHERE b.c_personid IN ({ph})""", pids):
        idx_addr[r["c_personid"]] = (r["c_name_chn"], r["x_coord"], r["y_coord"])
    con.close()

    # curated_people(诗在语料、CBDB 无档的合成档案):元数据从 curated_people.csv 注入,替代 CBDB 查询
    if CURATED_PEOPLE.exists():
        resolved_pids = {int(w["person_id"]) for w in women}
        for cr in csv.DictReader(open(CURATED_PEOPLE, encoding="utf-8")):
            cpid = int(cr["curated_id"])
            if cpid not in resolved_pids:
                continue  # 该 curated 人本轮诗未匹配,不建档
            main_rows[cpid] = {
                "c_personid": cpid, "c_name_chn": cr["name"], "c_name": cr["name_pinyin"],
                "c_birthyear": cr["birth_year"] or None, "c_deathyear": cr["death_year"] or None,
                "c_index_year": None, "c_notes": cr["source_note"], "c_dynasty_chn": cr["dynasty"],
            }
            if cr["aliases"].strip():
                aliases[cpid] = [a.strip() for a in cr["aliases"].split(";") if a.strip()]
            if cr["statuses"].strip():
                statuses[cpid] = [s.strip() for s in cr["statuses"].split(";") if s.strip()]
            if cr["place"].strip():
                idx_addr[cpid] = (cr["place"].strip(), None, None)

    # curated_poems(诗级归属的合成女性,如许穆夫人《载驰》):元数据从 curated_poems.csv 注入。
    # corpus_names 用真实语料署名(corpus_author,如《载驰》署「诗经」),不用合成占位名。
    CURATED_POEMS = ROOT / "data" / "curated" / "curated_poems.csv"
    cp_signatures = {}  # pid -> set(真实语料署名)
    if CURATED_POEMS.exists():
        resolved_pids = {int(w["person_id"]) for w in women}
        for cr in csv.DictReader(open(CURATED_POEMS, encoding="utf-8")):
            cpid = int(cr["person_id"])
            if cpid not in resolved_pids:
                continue
            cp_signatures.setdefault(cpid, set()).add(cr["corpus_author"].strip())
            if cpid not in main_rows:
                main_rows[cpid] = {
                    "c_personid": cpid, "c_name_chn": cr["name"], "c_name": cr["name_pinyin"],
                    "c_birthyear": None, "c_deathyear": None, "c_index_year": None,
                    "c_notes": cr["source_note"], "c_dynasty_chn": cr["dynasty"],
                }

    profiles = []
    for w in women:
        pid = int(w["person_id"])
        m = main_rows[pid]
        place, x, y = idx_addr.get(pid) or (addr.get(pid) or (9, "", None, None))[1:]
        disp_name, disp_py = display_names.get(pid, (None, None))
        p_name = disp_name or m["c_name_chn"]
        p_aliases = [a for a in aliases.get(pid, []) if a.split("(", 1)[0] != p_name]
        feat = feature_names.get(pid)
        if feat:  # 档案「字号」头衔:把指定别名提到首位(异体/繁简折叠后匹配)
            fkey = T2S.convert(feat)
            fidx = next((i for i, a in enumerate(p_aliases)
                         if T2S.convert(a.split("(", 1)[0]) == fkey), None)
            if fidx is not None:
                p_aliases.insert(0, p_aliases.pop(fidx))
            else:
                p_aliases.insert(0, feat)
                print(f"⚠️ feature 头衔 {feat!r} 不在 pid {pid} 别名表,已作策展别名前置")
        profiles.append({
            "person_id": pid,
            "name": p_name,
            "name_pinyin": (disp_py or m["c_name"] or "").strip(),
            "dynasty": m["c_dynasty_chn"] or "",
            "birth_year": m["c_birthyear"] or "",
            "death_year": m["c_deathyear"] or "",
            "index_year": m["c_index_year"] or "",
            "aliases": " / ".join(p_aliases),
            "statuses": " / ".join(statuses.get(pid, [])),
            "place": place or "",
            "x_coord": x if x else "",
            "y_coord": y if y else "",
            "n_poems": dedup_np.get(w["person_id"]) or int(w["n_poems"]),
            "layers": w["layers"],
            "corpus_names": " / ".join(sorted(cp_signatures[pid])) if pid in cp_signatures else w["corpus_names"],
            "in_mqww": int(w["in_mqww"]),
            "cbdb_notes": re.sub(r"[\x00-\x1f\x7f]+", " ", (m["c_notes"] or "")[:200]),
            "supplement": "",
        })

    # 补源人(supplement_people.csv):语料外补录,元数据本表注入,诗数=其 supplement_poems 中 include_in_site 首数。
    # ⚠️ 铁律:语料 stats.json / women_poems.csv 完全不含补源——补源只在站点组装层(profiles/site_data)汇入,
    # 绝不回流语料层与语料统计(1.50%/female_author_share/MQWW% 保持纯语料口径)。
    SUP_PEOPLE = ROOT / "data" / "curated" / "supplement_people.csv"
    SUP_POEMS_F = ROOT / "data" / "curated" / "supplement_poems.csv"
    if SUP_PEOPLE.exists():
        sup_np = defaultdict(int)
        if SUP_POEMS_F.exists():
            for r in csv.DictReader(open(SUP_POEMS_F, encoding="utf-8")):
                if (r.get("include_in_site") or "1").strip() == "1":
                    sup_np[r["person_id"].strip()] += 1
        n_sup = 0
        for cr in csv.DictReader(open(SUP_PEOPLE, encoding="utf-8")):
            pid = cr["person_id"].strip()
            np = sup_np.get(pid, 0)
            if np == 0:
                continue  # 无上站补源诗,不建档(防死档)
            profiles.append({
                "person_id": pid, "name": cr["name"], "name_pinyin": (cr["name_pinyin"] or "").strip(),
                "dynasty": cr["dynasty"] or "", "birth_year": cr["birth_year"] or "",
                "death_year": cr["death_year"] or "", "index_year": "",
                "aliases": cr.get("aliases") or "", "statuses": cr.get("statuses") or "",
                "place": cr.get("place") or "", "x_coord": "", "y_coord": "",
                "n_poems": np, "layers": "C", "corpus_names": "",
                "in_mqww": int(cr.get("in_mqww") or 0),
                "cbdb_notes": re.sub(r"[\x00-\x1f\x7f]+", " ", (cr.get("source_note") or "")[:200]),
                "supplement": "1",
            })
            n_sup += 1
        if n_sup:
            print(f"补源人: +{n_sup}(语料外补录,不入语料统计)")

    profiles.sort(key=lambda p: -p["n_poems"])
    with open(OUT / "women_profiles.csv", "w", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=list(profiles[0].keys()))
        wtr.writeheader()
        wtr.writerows(profiles)
    json.dump(profiles, open(OUT / "women_profiles.json", "w"), ensure_ascii=False, indent=1)

    print(f"profiles: {len(profiles)}")
    print(f"有生卒年(任一): {sum(1 for p in profiles if p['birth_year'] or p['death_year'])}")
    print(f"有地理坐标: {sum(1 for p in profiles if p['x_coord'])}")
    print(f"有身份标注: {sum(1 for p in profiles if p['statuses'])}")
    print(f"有别名: {sum(1 for p in profiles if p['aliases'])}")
    print("\n朝代分布:", dict(Counter(p["dynasty"] for p in profiles).most_common()))
    sc = Counter()
    for p in profiles:
        for s in p["statuses"].split(" / "):
            if s:
                sc[s] += 1
    print("\n身份 TOP20:", dict(sc.most_common(20)))


if __name__ == "__main__":
    main()
