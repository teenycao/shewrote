# Methodology: Gender-Annotating Classical Chinese Poetry

*SheWrote · 她写过 — draft v1, 2026-07-03. Numbers in this document are reproducible from the scripts in `scripts/`; see [Reproducibility](#reproducibility).*

## The question

Of the classical Chinese poems that survive in open digital corpora, what share was written by women?

This number has never been computed. [chinese-poetry](https://github.com/chinese-poetry/chinese-poetry) (52k+ GitHub stars, the default data source for virtually every Chinese poetry project) stores authors as bare name strings with no gender field. Harvard's [China Biographical Database (CBDB)](https://cbdb.hsites.harvard.edu/) has a gender field for ~660k historical persons but no link to the poetry corpora. We built that link.

## Headline results

| | Layer A: Tang–Song<br>(chinese-poetry) | Layer B: pre-Qin through Qing<br>(Werneror/Poetry) |
|---|---|---|
| Poems | 333,451 | 763,542 |
| Poems by identified women | **936 (0.28%)** | **10,073 (1.32%)** |
| … as share of gender-resolved poems | 0.31% | 1.49% |
| Identified women authors | 97 of 5,893 resolved (1.6%) | 865 of 11,645 resolved (7.4%) |
| Surviving poems per author (resolved only) | women ≈ 10, men ≈ 37 (**3.9×**) | women ≈ 11, men ≈ 39 (**3.6×**) |

**Both percentages are lower bounds** — see [Why these are lower bounds](#why-these-are-lower-bounds).

The two layers are computed independently and must not be summed (their Song-era contents overlap).

A second finding is embedded in the per-author row: women who made it into the record at all were preserved at roughly **a quarter of the per-capita volume of men**. The erasure operated twice — once on who was recorded, once on how much of her work was kept.

## Data sources

| Source | Role | Version used | License |
|---|---|---|---|
| [chinese-poetry](https://github.com/chinese-poetry/chinese-poetry) | Layer A corpus: 全唐诗 (Quan Tangshi), 全宋诗, 全宋词, 五代诗词 | shallow clone 2026-07-03 | MIT |
| [Werneror/Poetry](https://github.com/Werneror/Poetry) | Layer B corpus: 853k poems, pre-Qin → modern, by-era CSV | clone 2026-07-03 | MIT |
| [CBDB](https://github.com/cbdb-project/cbdb_sqlite) | Gender (`c_female`), alias table (`ALTNAME_DATA`, 207,576 rows), dynasty, biographical fields | SQLite release 2026-06-27 (659,593 persons; 57,729 female = 8.75%; 24,273 gender-unknown) | CC BY-NC-SA 4.0 |
| [MQWW 明清妇女著作](https://digital.library.mcgill.ca/mingqing/) | Independent validation: Ming–Qing women writers | via CBDB source link (textid 9601: 9,599 persons, 4,649 women) | (accessed through CBDB) |

Layer B excludes Werneror's post-Qing era files (近现代 / 当代 / 民国 boundary eras), keeping the claim scoped to pre-Qin through Qing.

**Corpus quality differs by design.** Layer A descends from canonical compilations (《全唐诗》《全宋诗》《全宋词》) with traceable provenance. Layer B is an aggregated corpus without per-poem source attribution. We therefore report the layers separately and treat Layer A as the primary citation-grade number.

## Matching pipeline

Implemented in [`scripts/build_match.py`](../scripts/build_match.py). For each unique (corpus author string, era label) pair:

1. **Script normalization.** chinese-poetry is internally inconsistent (Tang files are traditional script, Song ci files are simplified); Werneror is simplified; CBDB is traditional. Both sides are normalized to simplified via OpenCC (`t2s`) and matched on the normalized key. We normalize toward simplified because t2s is many-to-one — collapsing variants is desirable for matching (the reverse direction, s2t, guesses wrongly on cases like 里/裏).
2. **Exact match** against CBDB `BIOG_MAIN.c_name_chn`.
3. **Alias match** against `ALTNAME_DATA` (studio names 号, courtesy names 字, titles, taboo-avoidance variants). This resolves cases where the corpus signature shares zero characters with the canonical name — e.g. 上官昭容 (palace title, her signature in 全唐诗) → 上官婉兒 (CBDB 91931); 花蕊夫人; taboo variant 魚元機 → 魚玄機.
4. **Buddhist-clergy retry.** Corpus names prefixed 釋/释 ("Shi", monastic surname) are retried without the prefix and with the prefix re-attached, since CBDB stores clergy under either form.
5. **Era disambiguation.** Each corpus era label maps to a set of admissible CBDB dynasty codes (including adjacent dynasties — a 宋末元初 person may be coded 元 in CBDB — and code 0 "unknown"). Candidates outside the set are eliminated.
6. **Bucketing.**

| Bucket | Meaning | Counts toward gender stats? |
|---|---|---|
| `resolved` | exactly one candidate survives | yes, with person identity |
| `multi_consensus` | multiple candidates, **all the same gender** | yes, gender only (identity queued for review) |
| `multi` | multiple candidates, mixed gender | no — human review queue |
| `era_conflict` | candidates exist but none era-compatible | no (treated as unmatched to avoid misattribution) |
| `monk` | 釋-prefixed, no match after retry | no (CBDB coverage gap, overwhelmingly male in practice — not assumed) |
| `institutional` | ritual/institutional signatures (郊廟朝會歌辭 etc.) | no (not a person) |
| `anonymous` | 無名氏 / 佚名 / 闕名 … | no |
| `shi_pattern` | "X氏" pattern — see below | no (flagged, not guessed) |
| `unmatched` | no candidate at any stage | no |

### Bucket distribution (share of poems)

| Bucket | Layer A | Layer B |
|---|---|---|
| resolved | 65.25% | 56.11% |
| multi_consensus | 25.17% | 32.71% |
| multi | 2.14% | 1.96% |
| era_conflict | 1.74% | 1.12% |
| monk | 1.30% | 1.36% |
| unmatched | 2.80% | 5.80% |
| institutional | 0.49% | 0.23% |
| anonymous | 1.08% | 0.67% |
| shi_pattern | 0.04% | 0.03% |
| **gender-resolvable (resolved + consensus)** | **90.2%** | **88.6%** |

The `multi_consensus` rule deserves a note: when several same-named, era-compatible CBDB persons all share one gender, the *gender* statistic is safe even though the *person* attribution is not. Same-name candidate pools are overwhelmingly male (the rule added 83,926 Layer-A poems to the denominator and exactly 1 to the female numerator), so removing this rule barely moves the female share: strict-resolved-only gives 0.40% (A) / 2.08% (B) of a smaller denominator.

## Validation

**Anchor set.** Ten canonical women poets were traced by hand through both sources before the pipeline was built: 李清照, 朱淑真, 薛涛, 鱼玄机, 李冶, 花蕊夫人, 班婕妤, 蔡琰, 上官婉儿, 管道昇. Findings: 9/10 exist in CBDB (班婕妤, Western Han, is absent — CBDB's early-era coverage is thin); 7/10 have poems in the corpora; all 7 resolve to the correct CBDB person, including the hard cases:

- 上官婉儿 signs as **上官昭容** (palace title) in 全唐诗 — merged via alias layer; her two corpus signatures land on one person ID;
- 薛涛 has a same-name male in CBDB (18759) — eliminated by era+gender filtering;
- 柳如是 appears in Werneror under her formal name **柳是** — resolved to CBDB 56573 (a person carrying 29 recorded aliases);
- 花蕊夫人 is one alias shared by **three** CBDB persons (two Former-Shu consorts + one Later-Shu consort) — correctly NOT auto-resolved; queued for review.

**Independent cross-check.** Of the 874 women in the dataset, **722 (83%)** independently appear in MQWW (McGill's Ming–Qing Women's Writings database, compiled by domain scholars from 胡文楷《历代妇女著作考》). The remainder are mostly pre-Ming women (MQWW's scope starts at Ming) — e.g. 李清照 is not in MQWW and shouldn't be.

**Eyeball audit.** The top-40 women by poem count read as a recognizable who's-who of 明清才女 (朱淑真, 柳如是, 沈宜修, 顾贞立, 叶小鸾, …) with no evident misattribution.

## Why these are lower bounds

1. **CBDB skews elite and later-era.** Courtesans, nuns, and non-elite women are underrepresented; Western-Han 班婕妤 is simply absent. A corpus author we cannot match cannot be counted as a woman.
2. **The "X氏" problem.** 376 poems across both layers are signed with patterns like 徐氏 / 王孙氏 — a surname plus the marker 氏, i.e. *"the woman of family X."* These are almost certainly women **recorded without a personal name**. We flag them (`shi_pattern`) rather than count them: including them would raise the female share, but we refuse to launder an act of erasure into a data point. Their existence — women whose poems survived while their names did not — is itself one of the findings of this project.
3. **Anonymous poems** (0.7–1.1%) cannot be gendered; history suggests women are overrepresented among the anonymized.
4. **Unmatched authors** (2.8% / 5.8% of poems) resolve to no CBDB person; women are plausibly overrepresented here too, for the same reasons they are underrepresented in CBDB.
5. **Corpus survivorship.** The corpora only contain what was compiled, printed, and preserved — processes controlled almost exclusively by men. 沈宜修's 200 surviving poems exist because her husband published her posthumously; most women had no such editor.

## The Qing sample: what it can and cannot support

Layer B's Qing numbers (women = 15.9% of resolved authors, 13.1% of poems) looked suspiciously high, so we audited the sample (2026-07-03).

**The "women's-anthology contamination" hypothesis is rejected.** Sampling depth is symmetric by gender: Qing women median 3 poems / mean 10.8; Qing men median 3 / mean 13.5. Women's collections were not dumped in wholesale.

**But the Qing corpus truncates canonical male poets.** 袁枚 appears with 80 poems (~4,400 extant), 趙翼 65 (~4,800), 王士禛 313 (~4,000; also unmatched due to a taboo-character variant 禛/禎 — known issue), while 錢謙益 and 吳偉業 are absent entirely. A complete-corpus computation would add millions of male-authored Qing poems to the denominator. **Therefore the Qing *poem share* (13.1%) is a property of this sample, not of surviving Qing poetry, and we do not headline it.** The same truncation artificially deflates Qing male per-capita volume (13.5 vs Ming's 81.9), so per-capita "convergence" in Qing should not be read as a historical finding.

**The Qing *author share* (15.9%), however, is externally consistent.** Two independent bibliographic baselines: 胡文楷《历代妇女著作考》records **3,600+ Qing women writers**; 柯愈春《清人诗文集总目提要》catalogues **~20,000 Qing authors** with ~40,000 extant collections. Women ≈ 3,600 / ~20,000–23,600 ≈ **15–18%** — bracketing our 15.9%. Scholarship also gives ~4,200 Qing women poets with ~70% from the lower Yangzi (Susan Mann's analysis of Hu Wenkai), independently matching our geographic result (all top-12 native places are Jiangnan/Huizhou). The rise in women's *authorship share* from Song (1.0%) to Qing (15.9%) is robust; the poem-level and per-capita Qing figures are not.

## Known limitations & open work

- `multi` and `era_conflict` buckets (~4% of poems) await human review (`data/interim/review_multi.csv`, regenerated by the pipeline); 花蕊夫人's 158-poem 宫词 corpus sits here pending an attribution decision (its authorship is genuinely contested in the scholarship).
- A single corpus author string maps to at most one CBDB person per era; two same-named poets *within* one era cannot be split at poem level.
- `multi_consensus` trusts CBDB's gender coding for every pool member.
- Werneror's Song overlap with chinese-poetry is not deduplicated (layers are reported separately for exactly this reason).
- CBDB's social-status field is sparse for women (16% of our 874), so the 闺秀/歌妓/女冠/宫人 breakdown needs MQWW work-level metadata or notes parsing — planned.
- Wikidata QIDs per woman (visibility layer) — planned; Wikidata itself is unusable as a statistical source here (its Chinese-poet gender ratio is inverted by curation bias: 2,954 women vs 872 men tagged, an artifact of women's entries being more thoroughly attributed).

## Licensing

Code: MIT. Derived annotation data (identities, gender attributions, profile fields) inherits **CC BY-NC-SA 4.0** from CBDB (NonCommercial, ShareAlike). `women_poems.csv` is a mixed file: its poem texts (`title`, `text` columns) come from the MIT-licensed upstream corpora (chinese-poetry, Werneror/Poetry) and remain MIT; the attribution columns (`person_id`, `name`) are CBDB-derived and carry CC BY-NC-SA 4.0. The full source corpora are not redistributed here — only the women-attributed subset.

## Reproducibility

```bash
# data (not in git): see data/README.md for layout
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/build_match.py         # → data/interim/{author_match,women_resolved,review_multi}.csv + stats
.venv/bin/python scripts/build_release.py       # → data/out/women_poems.csv, stats.json
.venv/bin/python scripts/build_profiles.py      # → data/out/women_profiles.{csv,json} (reads women_poems for dedup counts)
.venv/bin/python scripts/build_starmap_data.py  # → web/starmap_data.js
```

Pinned inputs: CBDB SQLite `cbdb_20260627.sqlite3` (sha256 in `data/raw/cbdb/cbdb_20260627.json`), chinese-poetry & Werneror/Poetry clones of 2026-07-03.

## Curated overrides (data v1.1, 2026-07-10)

The pipeline's rule — trust CBDB's gender coding, mark rather than guess — has one failure mode: CBDB itself can be silent. A pre-launch audit of famous "expected" women found two recoverable cases, now handled by a documented supplement table (`data/curated/overrides.csv`, merged by `build_match.py`; every row carries its documentary source):

- **顾太清 (Gu Taiqing, person 521382)** — 379 poems matched in the corpus, CBDB person matched, but CBDB's `c_female` field is *blank*. Identified as female per 《天游阁集》/《东海渔歌》 and 况周颐《蕙风词话》 ("男中成容若,女中太清春"). Type: `gender` override.
- **贺双卿 (He Shuangqing → person 56149)** — 16 poems; CBDB holds two duplicate records for the same woman (56149 with index year 1715, and 567224), so the name fell into `multi_consensus`. Resolved to the dated record. Type: `identity` override.

Two famous names remain deliberately out of the person-level set, per *mark, don't guess*: **班婕妤** (no CBDB entry; the attribution of 《怨歌行》 to her has been disputed since the Six Dynasties) and **花蕊夫人** (three CBDB candidates — two Former-Shu consorts and one Later-Shu consort — and the authorship question is itself a classic scholarly dispute; her 1 corpus poem is counted in the gender statistics via `multi_consensus`, unattributed to a person).

v1.1 effect: women 867 → **869**; women's poems 9,665 → **10,044** (1.27% → **1.32%**); resolved women authors 858 → 860 (still 7.4%). Published figures dated before 2026-07-10 (the launch article and its charts) reflect v1.0 and are kept as method-dated snapshots.
