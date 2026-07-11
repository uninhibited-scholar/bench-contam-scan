#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Produce a benchmark PROFILE: whole-file sha256, per-record sha256 + ID set,
schema, and label distribution. Commit the profile next to the data; any silent
edit (delete sample / flip gold / rewrite text) changes the profile and shows up
in git diff. Same mechanism as fraud-detect-bench-zh's MANIFEST, generalized.

Usage: fingerprint.py bench.jsonl [--id-field id] [--label-field label]
       [--out PROFILE.json] [--verify]   # --verify: exit 1 if profile mismatch"""
import argparse, hashlib, json, sys
from collections import Counter

def build(path, idf, lf):
    recs, labels, schema = {}, Counter(), Counter()
    whole = hashlib.sha256()
    for ln, l in enumerate(open(path, encoding="utf-8"), 1):
        l = l.strip()
        if not l: continue
        whole.update(l.encode())
        o = json.loads(l)
        recs[str(o.get(idf, f"L{ln}"))] = hashlib.sha256(l.encode()).hexdigest()
        if lf and lf in o: labels[str(o[lf])] += 1
        schema[tuple(sorted(o.keys()))] += 1
    return {"file_sha256": whole.hexdigest(), "n_records": len(recs),
            "schemas": {" ,".join(k): v for k, v in schema.items()},
            "label_dist": dict(labels), "records": recs}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bench"); ap.add_argument("--id-field", default="id")
    ap.add_argument("--label-field"); ap.add_argument("--out", default="PROFILE.json")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    prof = build(a.bench, a.id_field, a.label_field)
    if a.verify:
        old = json.load(open(a.out, encoding="utf-8"))
        if old["file_sha256"] == prof["file_sha256"]:
            print(f"VERIFY OK — {prof['n_records']} records, profile matches"); return 0
        gone = set(old["records"]) - set(prof["records"])
        new = set(prof["records"]) - set(old["records"])
        changed = [i for i in set(old["records"]) & set(prof["records"])
                   if old["records"][i] != prof["records"][i]]
        print(f"VERIFY FAIL — deleted {sorted(gone)[:5]} added {sorted(new)[:5]} modified {changed[:5]}")
        return 1
    json.dump(prof, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"wrote {a.out}: {prof['n_records']} records, file {prof['file_sha256'][:16]}…")
    return 0

if __name__ == "__main__":
    sys.exit(main())
