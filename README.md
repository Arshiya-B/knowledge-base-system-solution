# Knowledge system

A deterministic Python 3.11 system (standard library only) that reads dated snapshots of the credit union website and answers member questions with the current, correctly tiered value, a source, and an honest "I don't know" when the site does not say. It also lists places where the site contradicts itself.

No API keys, no network calls, no LLM. See `NOTES.md` for the approach, evaluation record and known gaps.

## Layout
- `solution/solution.py`: `build()` returns the object with `ingest`, `answer` and `conflicts`.
- `solution/kbcore/`: `tables.py` and `engine.py` (rate tables), `prose.py` (branch, contact, program and link facts), `conflicts.py`, `textutil.py`, `pages.py`.
- `harness/`: the supplied scorer.
- `eval/`: the supplied public set plus our own practice sets, each with a source snapshot, page and quote. `tools/verify_gold.py` re-checks them against the raw pages.

## Run
Put the supplied snapshot zips in `snapshots_zip/` (they are not in this repo). The scorer unpacks them into `snapshots/` on first run.

```
python harness/run_eval.py --submission solution --eval eval/public_eval.jsonl
python harness/run_eval.py --submission solution --eval eval/public_eval.jsonl --conflicts-gold eval/conflicts_gold_own.json
```

Ingest takes about 7 seconds; answers take about 0.1 seconds at p95.
