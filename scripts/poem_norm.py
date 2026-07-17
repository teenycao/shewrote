"""站内收录去重的文本归一(仅用于去重比对,不用于展示)。

背景:人工复核发现七岁女子《送兄》等重复记录。
A/B 两库同诗常以「标题规范不同(六首 一 vs 六首 其一)+ 异体字(鴈/雁)」逃过
旧去重键(person+标题+文本前 20 字)。全库扫描:815 对近重复,622 对零差异,
168 对一字差(几乎全为异体)。

规则:
- 去重键 = (person_id, 全文归一) —— 忽略标题;
- 归一 = OpenCC t2s + 异体折叠表 + 去全部标点/空白;
- 折叠表只收**无歧义异体/通用写法**(逐对人工核过);方/芳、何/如、声/应、
  户/牖、潇/萧 这类真异文**不折叠**——一字之差的两个版本各自保留,标记不猜测。
"""
import re
from collections import defaultdict

try:
    import opencc
    _T2S = opencc.OpenCC("t2s").convert
except ImportError:  # 站点仓 node 侧不会走到这里;数据仓必须有 venv
    raise SystemExit("poem_norm 需要 opencc,请用 .venv/bin/python 运行")

# 异体折叠(全库近重复扫描高频差字对中,人工甄别出的无歧义项;含 OpenCC t2s 漏网字)
VARIANTS = str.maketrans({
    "馀": "余", "簷": "檐", "粧": "妆", "鬬": "斗", "鴈": "雁", "牋": "笺",
    "嬾": "懒", "慙": "惭", "筯": "箸", "徧": "遍", "巵": "卮", "疎": "疏",
    "翦": "剪", "櫂": "棹", "遶": "绕", "覩": "睹", "敧": "欹", "攲": "欹",
    "遯": "遁", "翺": "翱", "懽": "欢", "劒": "剑", "壻": "婿", "櫺": "棂",
    "妬": "妒", "彷": "仿", "秪": "祗", "薰": "熏", "醿": "醾", "阑": "栏",
    "邨": "村", "昇": "升",
})

_STRIP = re.compile(r"[^\w]")


def norm_text(text: str) -> str:
    """去重比对用归一:t2s → 异体折叠 → 去标点空白。空文本返回空串(调用方应保留不归并)。"""
    return _STRIP.sub("", _T2S(text or "").translate(VARIANTS))


class Deduper:
    """站内收录去重决策(build_profiles / build_site_data 共用,保证口径一致)。

    判重规则(v1.2.2,2026-07-11 深夜,读者发现苏小小《减字木兰花》「未必/未心」两版并存):
    - 归一全文精确相同 → 重复;
    - 同人、同长度(≥12 字)、仅差 1 字 → 视为同诗异文,重复(展示层合并,保留先见版本
      ——csv 中 A 库在前,A 版带 / 分行结构;数据集本体两版皆存,不受影响)。
    差 2 字及以上保留双版:更大的差异可能是真正的组诗/改写,标记不猜测。
    """

    def __init__(self):
        self._kept = {}
        self.composite_rows = []
        self.variant_rows = []

    def check_and_add(self, person_id: str, text: str) -> bool:
        """True=重复应跳过;False=首见,已登记。空文本永远视为首见且不登记。

        流式接口只能处理精确重复/一字异文。需要识别“合并行”时,调用 dedupe_records。
        """
        nt = norm_text(text)
        if not nt:
            return False
        kept = self._kept.setdefault(person_id, [])
        for k in kept:
            if k == nt:
                return True
            if len(k) == len(nt) and len(nt) >= 12 and sum(1 for a, b in zip(k, nt) if a != b) <= 1:
                return True
        kept.append(nt)
        return False

    def dedupe_records(self, records, person_key="person_id", text_key="text", title_key="title"):
        """按 person 分组去重,返回应保留的 records。

        合并行规则:同一人名下,若某行归一化全文 == 其他 >=2 行归一化全文按出现顺序
        或“其N”标题序号顺序拼接,则剔除该行。文本拼接相等是硬条件。
        """
        self._kept = {}
        self.composite_rows = []
        self.variant_rows = []

        indexed = list(enumerate(records))
        by_person = defaultdict(list)
        for pos, rec in indexed:
            by_person[str(rec.get(person_key, ""))].append((pos, rec, norm_text(rec.get(text_key, ""))))

        composite_idx = set()
        for pid, items in by_person.items():
            composite_idx.update(self._find_composites(pid, items, title_key))

        kept_records = []
        for pos, rec in indexed:
            if pos in composite_idx:
                continue
            pid = str(rec.get(person_key, ""))
            nt = norm_text(rec.get(text_key, ""))
            if not nt:
                kept_records.append(rec)
                continue
            kept = self._kept.setdefault(pid, [])
            duplicate = False
            for k in kept:
                if k == nt:
                    duplicate = True
                    break
                if len(k) == len(nt) and len(nt) >= 12 and sum(1 for a, b in zip(k, nt) if a != b) <= 1:
                    duplicate = True
                    break
            if duplicate:
                self.variant_rows.append(rec)
                continue
            kept.append(nt)
            kept_records.append(rec)
        return kept_records

    def _find_composites(self, person_id, items, title_key):
        out = set()
        valid = [(pos, rec, nt) for pos, rec, nt in items if nt]
        if len(valid) < 3:
            return out
        orders = [valid, sorted(valid, key=lambda item: (*_title_order(item[1].get(title_key, "")), item[0]))]
        seen_orders = set()
        for pos, rec, nt in valid:
            if len(nt) < 12:
                continue
            cand_title = rec.get(title_key, "")
            group_items = [
                item for item in valid
                if item[0] != pos and _same_title_group(cand_title, item[1].get(title_key, ""))
            ]
            if len(group_items) < 2:
                continue
            for order in orders:
                order = [item for item in order if item in group_items]
                sig = tuple(p for p, _, _ in order)
                if sig in seen_orders:
                    continue
                seen_orders.add(sig)
                parts = _compose_parts(nt, pos, order)
                if parts:
                    out.add(pos)
                    self.composite_rows.append({
                        "person_id": person_id,
                        "record": rec,
                        "norm_len": len(nt),
                        "parts": [p_rec for _, p_rec, _ in parts],
                    })
                    break
            seen_orders.clear()
        return out


# 「其N」后允许带空格分隔的子题(如「悲感二女遗物 其一 空闺」)——此形态曾绕过合并行识别
_QI_RE = re.compile(r"(.*?)(?:\s+)?其([一二三四五六七八九十百\d]+)(?:\s+\S.*)?$")
_CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _title_order(title):
    title = (title or "").strip()
    m = _QI_RE.match(title)
    if not m:
        return title, 0
    return m.group(1).strip(), _parse_qi_num(m.group(2))


def _same_title_group(a, b):
    a = (a or "").strip()
    b = (b or "").strip()
    if not a or not b:
        return False
    abase, _ = _title_order(a)
    bbase, _ = _title_order(b)
    if abase == bbase or a == b:
        return True
    # 合并行标题常沿用首篇子题(「悲感二女遗物 空闺」vs 基题「悲感二女遗物」)——
    # 基题呈前缀关系即入组;误杀由 _compose_parts 的全文精确拼接匹配兜底
    return bool(abase and bbase and (abase.startswith(bbase) or bbase.startswith(abase)))


def _parse_qi_num(raw):
    if raw.isdigit():
        return int(raw)
    if raw in _CN_NUM:
        return _CN_NUM[raw]
    if raw.startswith("十") and len(raw) == 2:
        return 10 + _CN_NUM.get(raw[1], 0)
    if raw.endswith("十") and len(raw) == 2:
        return _CN_NUM.get(raw[0], 0) * 10
    if "十" in raw and len(raw) == 3:
        return _CN_NUM.get(raw[0], 0) * 10 + _CN_NUM.get(raw[2], 0)
    return 999


def _compose_parts(target, candidate_pos, ordered_items):
    memo = {}

    def walk(offset, start, picked):
        if offset == len(target):
            return picked if len(picked) >= 2 else None
        key = (offset, start, len(picked))
        if key in memo:
            return None
        for i in range(start, len(ordered_items)):
            pos, rec, nt = ordered_items[i]
            if pos == candidate_pos or not nt or len(nt) > len(target) - offset:
                continue
            if target.startswith(nt, offset):
                got = walk(offset + len(nt), i + 1, picked + [(pos, rec, nt)])
                if got:
                    return got
        memo[key] = None
        return None

    return walk(0, 0, [])
