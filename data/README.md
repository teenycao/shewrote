# data/

原始与中间数据落这里,不进 git 的大文件用 .gitignore 排除。

获取原始数据(复现用,共约 1.5GB):
```bash
# CBDB SQLite(下载地址由 latest.json 提供,解压得 cbdb_YYYYMMDD.sqlite3)
curl -sL -o raw/cbdb/latest.zip "https://huggingface.co/datasets/cbdb/cbdb-sqlite/resolve/main/latest.zip" && unzip -d raw/cbdb raw/cbdb/latest.zip
git clone --depth 1 https://github.com/chinese-poetry/chinese-poetry.git raw/chinese-poetry
git clone --depth 1 https://github.com/Werneror/Poetry.git raw/werneror-poetry
```
注意:脚本内数据库文件名按版本更新(scripts/*.py 顶部 DB 常量)。

建议布局(第一个工作 session 按需调整):
- `raw/chinese-poetry/` — clone 或按需拉取的上游 JSON
- `raw/cbdb/` — CBDB SQLite 离线库(下载方式见下方命令与 docs/methodology.md 数据源表)
- `interim/` — 匹配中间产物(alias 映射表/候选匹配对/人工复核清单)
- `out/` — 最终标注子集(发布物)

## curated 人工表

- `curated/overrides.csv` — CBDB 档案纠错/补注：`gender` 补性别，`identity` 处理同名多候选或重复条目归人。
- `curated/aliases.csv` — 同一人的人工别名补充：`signature` 是语料署名归并，参与匹配并改变统计口径；`search` 是大众检索别称，只进入才女档案别名列表，不参与匹配和统计。

验证锚点(手工确认这批人再跑管线):李清照 · 朱淑真 · 薛涛 · 鱼玄机 · 李冶 · 花蕊夫人 · 班婕妤 · 蔡琰 · 上官婉儿 · 管道升

## 管线运行顺序(2026-07-11 踩坑后固化)

```bash
.venv/bin/python scripts/build_match.py          # 匹配(读 curated/overrides.csv)
.venv/bin/python scripts/build_release.py        # → out/women_poems.csv + stats.json
.venv/bin/python scripts/build_profiles.py       # → out/women_profiles.*(去重计数依赖上一步的 women_poems.csv,顺序错则 n_poems 回退未去重值)
.venv/bin/python scripts/build_starmap_data.py   # → web/starmap_data.js(代表句)
.venv/bin/python scripts/build_site_data.py      # → out/site/(简体导出;末行须见「✅ 全部 N 人诗数与 n_poems 精确一致」)
```
