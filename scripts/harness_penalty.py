#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""harness_penalty — 实验 B：量化「评分器冤枉了谁」。

对同一批模型的**原始输出**，用两套评分器各算一次分：
  strict  朴素字面匹配（gold 必须逐字出现/相等）
  fsp     Fair Scoring Protocol 规范化后匹配（见 harness_probe.score_fsp）

  harness_penalty = fsp_score − strict_score

假设 H1：**模型越强，harness_penalty 越大**——强模型倾向用更自然多变的
方式给对答案（加解释/JSON/换措辞/换数字形式），被字面匹配系统性扣分；
弱模型答错是真错，两套评分都判错，penalty 小。

用法：
  python3 scripts/harness_penalty.py --task slots \
      --gold <slots.jsonl> --gold-field slot_value \
      --pred model=<pred.jsonl> [--pred model2=...]
"""
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness_probe import score_fsp, _fsp_norm

def score_strict(pred, gold):
    """朴素：gold 原样出现在输出里（很多基准的 contains 版本）"""
    return str(gold).strip() in str(pred)

def load_gold(path, field):
    out = {}
    for l in open(path, encoding="utf-8"):
        l = l.strip()
        if not l: continue
        o = json.loads(l)
        g = o.get(field)
        if isinstance(g, dict): g = next(iter(g.values()), None)
        if g is not None: out[o["id"]] = str(g)
    return out

def load_pred(path):
    out = {}
    for l in open(path, encoding="utf-8"):
        l = l.strip()
        if not l: continue
        o = json.loads(l)
        out[o["id"]] = o.get("answer", "")
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", required=True)
    ap.add_argument("--gold-field", default="gold")
    ap.add_argument("--pred", action="append", required=True,
                    help="name=path.jsonl，可重复")
    ap.add_argument("--task", default="")
    ap.add_argument("--report")
    a = ap.parse_args()
    gold = load_gold(a.gold, a.gold_field)
    rows = []
    for spec in a.pred:
        name, _, path = spec.partition("=")
        preds = load_pred(path)
        s_hit = f_hit = n = 0
        only_fsp = []
        for i, g in gold.items():
            if i not in preds: continue
            n += 1
            p = preds[i]
            s = score_strict(p, g); f = score_fsp(p, g)
            s_hit += s; f_hit += f
            if f and not s and len(only_fsp) < 5:
                only_fsp.append({"id": i, "gold": g, "output": str(p)[:70]})
        strict = round(s_hit / n, 3) if n else None
        fsp = round(f_hit / n, 3) if n else None
        rows.append({"model": name, "n": n,
                     "strict_score": strict, "fsp_score": fsp,
                     "harness_penalty": round(fsp - strict, 3) if n else None,
                     "rescued_examples": only_fsp})
    rows.sort(key=lambda r: -(r["fsp_score"] or 0))
    rep = {"task": a.task or a.gold, "models": rows,
           "note": "harness_penalty = fsp_score - strict_score；越大表示被字面匹配冤枉越多"}
    txt = json.dumps(rep, ensure_ascii=False, indent=2)
    if a.report: open(a.report, "w", encoding="utf-8").write(txt)
    print(txt)
    return 0

if __name__ == "__main__":
    sys.exit(main())
