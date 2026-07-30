#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""harness_probe — 量化「评分器公平性」的离线探针（实验 A）。

问题：机器评分被默认为客观，但字面匹配的评分器会把**正确但表述不同**的
答案判成错。强模型倾向用更自然、更多变的方式给对答案，因此被系统性扣分。

做法（完全离线，不需 API、不需模型）：
  取一批**已知正确**的 gold 答案 → 程序化生成 N 类语义等价变体 →
  用目标评分器逐一判分 → 统计 false-negative（正确却被判错）率，按变体类型细分。

得到的是一个**与模型无关**的 harness 脆弱性指标：
  harness_fnr = 被判错的等价变体数 / 等价变体总数

用法：
  # 用内置朴素评分器（严格字面匹配）跑内置样例
  python3 scripts/harness_probe.py --demo
  # 对任意 JSONL 基准：抽 gold 字段生成变体
  python3 scripts/harness_probe.py bench.jsonl --gold-field gold [--scorer strict|normalized]
  # 比较两个评分器（strict vs FSP 规范化）
  python3 scripts/harness_probe.py bench.jsonl --gold-field gold --compare
"""
import argparse, json, re, sys
from collections import defaultdict

# ---------- 变体生成器：每类都保持语义等价（正确答案仍然正确） ----------
_D = {"零":0,"一":1,"二":2,"两":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9}
_CN = {v: k for k, v in _D.items() if v > 0}
_SYN = {"这个月":"本月","本月":"这个月","上个月":"上月","上月":"上个月",
        "儿子":"我儿子","女儿":"我女儿","没有":"无"}

def _int2cn(n):
    n = int(n)
    if n < 10: return _CN.get(n, str(n))
    if n < 20: return "十" + (_CN.get(n % 10, "") if n % 10 else "")
    if n < 100:
        t, o = divmod(n, 10)
        return _CN.get(t, "") + "十" + (_CN.get(o, "") if o else "")
    return str(n)

def variants(gold):
    """给一个 gold 答案生成语义等价变体：[(变体类型, 文本), ...]"""
    g = str(gold).strip()
    out = [("identity", g)]
    # 1. 加解释前后缀
    out.append(("explained", f"答案是{g}"))
    out.append(("explained", f"{g}\n\n（依据题意，选{g}）"))
    # 2. 格式包裹
    out.append(("wrapped", f'"{g}"'))
    out.append(("wrapped", f"```\n{g}\n```"))
    out.append(("wrapped", json.dumps({"answer": g}, ensure_ascii=False)))
    # 3. 数字形式（阿拉伯 ↔ 中文）
    if re.fullmatch(r"-?\d+", g):
        out.append(("numeral", _int2cn(g) if abs(int(g)) < 100 else g))
        out.append(("numeral", f"{int(g):,}"))          # 千分位
    m = re.fullmatch(r"([零一二两三四五六七八九十]+)(.*)", g)
    if m:
        t = m.group(1)
        if t == "十": num = "10"
        elif "十" in t:
            a, _, b = t.partition("十")
            num = str((_D.get(a, 1) if a else 1) * 10 + (_D.get(b, 0) if b else 0))
        else:
            num = "".join(str(_D[c]) for c in t if c in _D)
        if num: out.append(("numeral", num + m.group(2)))
    # 4. 单位/量词增减（"3" ↔ "3路"）
    m2 = re.fullmatch(r"(\d+|[零一二两三四五六七八九十]+)(路|号|个|元|次|月)", g)
    if m2: out.append(("unit", m2.group(1)))
    # 5. 同义替换
    for k, v in _SYN.items():
        if k in g: out.append(("synonym", g.replace(k, v)))
    # 6. 空白/全半角/大小写
    out.append(("whitespace", f" {g} "))
    if re.fullmatch(r"[A-Za-z]", g):
        out.append(("case", g.lower() if g.isupper() else g.upper()))
        out.append(("fullwidth", chr(ord(g.upper()) - ord('A') + 0xFF21)))
    return out

# ---------- 两个评分器 ----------
def score_strict(pred, gold):
    """朴素字面匹配（很多基准的默认做法）"""
    return str(pred).strip() == str(gold).strip()

def _fsp_norm(s):
    """FSP 规范化：首行 → 中文数字 → 去标点空白 → 同义归并"""
    s = str(s)
    # 去 markdown code fence
    s = re.sub(r"```[a-zA-Z]*\n?", "", s).replace("```", "")
    first = next((ln.strip() for ln in s.splitlines() if ln.strip()), "")
    # JSON 里取值
    m = re.search(r'"answer"\s*:\s*"([^"]*)"', s)
    if m: first = m.group(1)
    def cn2int(t):
        if t == "十": return "10"
        if "十" in t:
            a, _, b = t.partition("十")
            return str((_D.get(a, 1) if a else 1) * 10 + (_D.get(b, 0) if b else 0))
        return "".join(str(_D[c]) if c in _D else c for c in t)
    first = re.sub(r"[零一二两三四五六七八九十]+", lambda m: cn2int(m.group()), first)
    first = re.sub(r"[\s\W_,]+", "", first)
    # 全角字母 → 半角
    first = "".join(chr(ord(c) - 0xFF21 + ord('A')) if 0xFF21 <= ord(c) <= 0xFF3A else c for c in first)
    for k, v in [("本月", "这个月"), ("上月", "上个月")]:
        first = first.replace(k, v)
    return first.lower()

def _norm_full(s):
    """全文规范化（不取首行）——用作 FSP 的回退，避免长推理输出被首行截断"""
    s = re.sub(r"```[a-zA-Z]*\n?", "", str(s)).replace("```", "")
    def cn2int(t):
        if t == "十": return "10"
        if "十" in t:
            a, _, b = t.partition("十")
            return str((_D.get(a, 1) if a else 1) * 10 + (_D.get(b, 0) if b else 0))
        return "".join(str(_D[c]) if c in _D else c for c in t)
    s = re.sub(r"[零一二两三四五六七八九十]+", lambda m: cn2int(m.group()), s)
    s = re.sub(r"[\s\W_,]+", "", s)
    s = "".join(chr(ord(c) - 0xFF21 + ord('A')) if 0xFF21 <= ord(c) <= 0xFF3A else c for c in s)
    for k, v in [("本月", "这个月"), ("上月", "上个月")]:
        s = s.replace(k, v)
    return s.lower()

def score_fsp(pred, gold):
    """Fair Scoring Protocol：先按首行/JSON 值严判，再回退全文包含。
    回退是必需的——只取首行会让长推理输出中命中的答案被丢掉（实测反例见 PLAN）。"""
    g = _fsp_norm(gold)
    if not g: return False
    gs = re.sub(r"(路|号|个|元|次|月)$", "", g)
    for p in (_fsp_norm(pred), _norm_full(pred)):
        if p == g or g in p: return True
        if gs and (p == gs or gs in p): return True
    return False

SCORERS = {"strict": score_strict, "fsp": score_fsp}

# ---------- 探针主流程 ----------
def probe(golds, scorer):
    by_type = defaultdict(lambda: [0, 0])   # type -> [false_negatives, total]
    examples = []
    for g in golds:
        for vtype, v in variants(g):
            ok = scorer(v, g)
            by_type[vtype][1] += 1
            if not ok:
                by_type[vtype][0] += 1
                if len(examples) < 12:
                    examples.append({"gold": g, "type": vtype, "variant": v[:60]})
    tot_fn = sum(x[0] for x in by_type.values())
    tot = sum(x[1] for x in by_type.values())
    return {"harness_fnr": round(tot_fn / tot, 3) if tot else None,
            "false_negatives": tot_fn, "variants_total": tot,
            "by_variant_type": {k: f"{v[0]}/{v[1]} ({round(v[0]/v[1],3)})"
                                for k, v in sorted(by_type.items())},
            "examples": examples}

DEMO_GOLDS = ["B", "6860", "三路", "这个月", "骨科", "A", "17580", "十六路", "电费", "降压药"]

def load_golds(path, field):
    out = []
    for l in open(path, encoding="utf-8"):
        l = l.strip()
        if not l: continue
        o = json.loads(l)
        g = o.get(field)
        if isinstance(g, dict): g = next(iter(g.values()), None)
        if g is not None and str(g).strip(): out.append(str(g).strip())
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bench", nargs="?")
    ap.add_argument("--gold-field", default="gold")
    ap.add_argument("--scorer", choices=list(SCORERS), default="strict")
    ap.add_argument("--compare", action="store_true", help="strict vs fsp 对比")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--report")
    a = ap.parse_args()
    golds = DEMO_GOLDS if (a.demo or not a.bench) else load_golds(a.bench, a.gold_field)
    src = "demo" if (a.demo or not a.bench) else a.bench
    if a.compare:
        rep = {"source": src, "n_golds": len(golds),
               "strict": probe(golds, score_strict), "fsp": probe(golds, score_fsp)}
        rep["fnr_reduction"] = round(rep["strict"]["harness_fnr"] - rep["fsp"]["harness_fnr"], 3)
    else:
        rep = {"source": src, "n_golds": len(golds), "scorer": a.scorer}
        rep.update(probe(golds, SCORERS[a.scorer]))
    txt = json.dumps(rep, ensure_ascii=False, indent=2)
    if a.report: open(a.report, "w", encoding="utf-8").write(txt)
    print(txt)
    return 0

if __name__ == "__main__":
    sys.exit(main())
