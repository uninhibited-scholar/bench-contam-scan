#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bench-contam-scan: offline contamination / integrity scanner for JSONL benchmarks.

Checks (all zero-dependency, deterministic):
  1. exact-dup      normalized-text exact duplicates inside the benchmark
  2. near-dup       char 5-gram Jaccard >= --near-threshold (default 0.80)
  3. gold-leak      gold answer string literally embedded in the prompt text
  4. cross-overlap  8-gram containment vs another corpus/benchmark (--against)

Usage:
  scan.py bench.jsonl --text-field message [--gold-field gold] [--id-field id]
          [--against other.jsonl --against-text-field text]
          [--near-threshold 0.8] [--report report.json]

Exit code: 0 = no findings, 1 = findings present (CI-friendly).
Findings are signals for human review, NOT proof of training contamination —
true train-set contamination cannot be established offline; use probe_model.py
for a model-side memorization heuristic."""
import argparse, json, re, sys, unicodedata
from collections import defaultdict

def norm(t):
    t = unicodedata.normalize("NFKC", str(t)).lower()
    return re.sub(r"[\s\W_]+", "", t, flags=re.UNICODE)

def ngrams(t, n):
    return {t[i:i+n] for i in range(max(0, len(t)-n+1))}

def jaccard(a, b):
    if not a or not b: return 0.0
    return len(a & b) / len(a | b)

def gold_strings(g):
    if isinstance(g, dict): out = []; [out.extend(gold_strings(v)) for v in g.values()]; return out
    if isinstance(g, list): out = []; [out.extend(gold_strings(v)) for v in g]; return out
    s = str(g).strip()
    return [s] if len(s) >= 2 else []

def load(path, tf, idf):
    rows = []
    for ln, l in enumerate(open(path, encoding="utf-8"), 1):
        l = l.strip()
        if not l: continue
        o = json.loads(l)
        rows.append({"id": str(o.get(idf, f"L{ln}")), "text": str(o.get(tf, "")), "raw": o})
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bench"); ap.add_argument("--text-field", required=True)
    ap.add_argument("--gold-field"); ap.add_argument("--id-field", default="id")
    ap.add_argument("--against"); ap.add_argument("--against-text-field")
    ap.add_argument("--near-threshold", type=float, default=0.80)
    ap.add_argument("--report", default="contam_report.json")
    a = ap.parse_args()

    rows = load(a.bench, a.text_field, a.id_field)
    findings = {"exact_dup": [], "near_dup": [], "gold_leak": [], "cross_overlap": []}

    seen = defaultdict(list)
    for r in rows: seen[norm(r["text"])].append(r["id"])
    for t, ids in seen.items():
        if len(ids) > 1 and t: findings["exact_dup"].append(ids)

    grams = [(r["id"], ngrams(norm(r["text"]), 5)) for r in rows]
    for i in range(len(grams)):
        for j in range(i+1, len(grams)):
            s = jaccard(grams[i][1], grams[j][1])
            if s >= a.near_threshold and grams[i][0] not in [x for g in findings["exact_dup"] for x in g]:
                findings["near_dup"].append({"a": grams[i][0], "b": grams[j][0], "jaccard": round(s, 3)})

    if a.gold_field:
        for r in rows:
            g = r["raw"].get(a.gold_field)
            if g is None: continue
            nt = norm(r["text"])
            for gs in gold_strings(g):
                ng = norm(gs)
                if len(ng) >= 4 and ng in nt:
                    findings["gold_leak"].append({"id": r["id"], "gold": gs})
                    break

    if a.against:
        otf = a.against_text_field or a.text_field
        corpus = set()
        for r in load(a.against, otf, a.id_field):
            corpus |= ngrams(norm(r["text"]), 8)
        for rid, _ in grams: pass
        for r in rows:
            g8 = ngrams(norm(r["text"]), 8)
            if not g8: continue
            cont = len(g8 & corpus) / len(g8)
            if cont >= 0.5:
                findings["cross_overlap"].append({"id": r["id"], "containment": round(cont, 3)})

    n_f = sum(len(v) for v in findings.values())
    rep = {"bench": a.bench, "n_records": len(rows), "near_threshold": a.near_threshold,
           "n_findings": n_f, "findings": findings,
           "note": "findings are review signals, not proof of training contamination"}
    json.dump(rep, open(a.report, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"scanned {len(rows)} records | exact_dup {len(findings['exact_dup'])} | "
          f"near_dup {len(findings['near_dup'])} | gold_leak {len(findings['gold_leak'])} | "
          f"cross_overlap {len(findings['cross_overlap'])} -> {a.report}")
    return 1 if n_f else 0

if __name__ == "__main__":
    sys.exit(main())
