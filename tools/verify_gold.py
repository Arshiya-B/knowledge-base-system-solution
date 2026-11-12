"""Check every custom eval item's gold against the raw snapshot pages.

usage: python tools/verify_gold.py <snapshots_dir> <eval.jsonl> [more.jsonl ...]
Checks per item:
  1. as_of resolves to the declared gold_snapshot (latest snapshot with taken_on <= as_of)
  2. gold_quote text exists on the gold_url page of that snapshot
  3. every must_include value appears inside gold_quote
  4. no must_not_include value appears inside gold_quote
"""
import json, os, re, sys

def norm(s):
    s = s.replace("\\*", "*").replace("–", "-").replace("—", "-").replace("’", "'")
    return re.sub(r"\s+", " ", s).strip().lower()

def canon(u):
    return u.split("#")[0].rstrip("/").replace("http://", "https://").lower()

def main():
    root, files = sys.argv[1], sys.argv[2:]
    snaps = []
    for d in sorted(os.listdir(root)):
        mp = os.path.join(root, d, "manifest.json")
        if os.path.exists(mp):
            m = json.load(open(mp))
            pages = {}
            for p in m["pages"]:
                pages.setdefault(canon(p["url"]), []).append(os.path.join(root, d, p["file"]))
            snaps.append((m["taken_on"], d, pages))
    bad = 0; n = 0
    for fn in files:
        for line in open(fn):
            it = json.loads(line); n += 1
            probs = []
            gs = it.get("gold_snapshot")
            if gs is None:
                if it["must_include"]:
                    probs.append("no gold source but must_include set")
            else:
                if it["as_of"]:
                    ok = [d for t, d, _ in snaps if t <= it["as_of"]]
                    want = ok[-1] if ok else None
                else:
                    want = snaps[-1][1]
                if want != gs:
                    probs.append(f"as_of resolves to {want}, gold says {gs}")
                pages = dict((d, p) for _, d, p in snaps)[gs]
                files_ = pages.get(canon(it["gold_url"]), [])
                quotes = it["gold_quote"] if isinstance(it["gold_quote"], list) else [it["gold_quote"]]
                q = " ".join(norm(x) for x in quotes)
                if not files_:
                    probs.append("gold_url not in snapshot")
                else:
                    for x in quotes:
                        if not any(norm(x) in norm(open(f).read()) for f in files_):
                            probs.append("gold_quote not found on page: " + x[:50])
                for v in it["must_include"]:
                    if v.rstrip("%").lower() not in q:
                        probs.append(f"must_include {v} not in quote")
                for v in it["must_not_include"]:
                    if v.rstrip("%").lower() in q and v in it["expected_answer"] + " ":
                        probs.append(f"must_not_include {v} appears in gold quote")
            if probs:
                bad += 1
                print("FAIL", it["id"], "; ".join(probs))
    print(f"checked {n} items, {bad} failing")
    sys.exit(1 if bad else 0)

main()
