# Dupaco knowledge system

A deterministic Python 3.11 system (standard library only) that reads dated snapshots of the Dupaco credit union website and answers member questions with the current, correctly tiered value, a source, and an honest "I don't know" when the site does not say. It also lists places where the site contradicts itself.

No API keys, no network calls, no LLM. `requirements.txt` is empty on purpose. See `NOTES.md` for the approach, evaluation record and known gaps.

## The three methods

`solution/solution.py` defines `build()`, which returns a `KnowledgeBase` with the three methods the contract (`harness/contract.py`) asks for. Every question and every check goes through them.

### 1. `ingest(snapshot)`: read the snapshots
Called once per snapshot, oldest first. For every page it:
- classifies the page (rates page, product page, landing page, calculator, blog, newsroom, file) and gives it an authority rank;
- parses every markdown rate table into rows: label, heading context, tier (term, model-year range, balance or loan-amount range), metrics (APY, dividend rate, APR, rate) and the page's own "effective as of" stamp;
- splits the text into searchable passages (sentences, FAQ question and answer pairs, short windows) and records every link with its anchor text and the page that carries it.

The rows go to the rate engine, the passages and links go to the prose engine. Duplicate URLs inside a snapshot are collapsed.

### 2. `answer(question, as_of=None)`: answer a question
`as_of` empty means the latest snapshot; a date means the website as it stood on that date (the latest snapshot taken on or before it). The flow:

1. **Rate engine first.** Pulls the product, term, amount and metric out of the question, filters the rate rows by tier (the tightest tier that fits wins; business, jumbo, IRA, introductory and refinance variants are excluded unless the question names them), then picks the current value: best match, then page authority, then the in-page effective stamp, then snapshot date.
2. **Prose engine second.** If the rate engine gives up and the question is not a pure rate question, the prose engine ranks passages with BM25, works out the question type (phone, address, hours, routing number, link, duration, amount, count, status, general), and keeps only passages that fit that type, for example a phone question needs a phone number in the passage. It prefers the most authoritative page.
3. **Links.** "Where can I apply", "link to see rates" and "how do I join" return a real link taken from the snapshot pages, never one built from memory. The cited source is the snapshot page that carries the link.
4. **Abstain.** If coverage of the question's product words is too low, a distinctive word is missing, the question needs live data (weather, a market price), or nothing validates, the answer is "I don't know" with no numbers.

Every answer carries sources (URL, snapshot id and the quote it came from).

### 3. `conflicts()`: list contradictions
Looks at the latest snapshot and reports places where the site disagrees with itself:
- **Rate conflicts:** the same product and tier showing different values on different pages (for example a rates page and a product page). The winner is the newest effective stamp, then the newest snapshot, then page authority, and the reason is stated.
- **Branch count:** pages that say 22, 23 or 24 branch locations.

Rows are grouped by product family, so auto loan APRs, mortgage purchase rates, mortgage refinance rates, Achieve Money Market, the 17-month certificates, 1st Rate Checking, business Share Savings and the branch count each appear once, with every competing value, the winner per tier row and all sources. `GROUP_BY_PRODUCT = True` in `solution/solution.py` switches back to one entry per rate row.

## Layout
- `solution/solution.py`: `build()` returns the object with `ingest`, `answer` and `conflicts`.
- `solution/kbcore/`: `tables.py` and `engine.py` (rate tables and tier selection), `prose.py` (branch, contact, program and link facts), `conflicts.py`, `textutil.py`, `pages.py`.
- `harness/`: the supplied scorer.
- `eval/`: the supplied public set plus our own practice sets, each with a source snapshot, page and quote. `tools/verify_gold.py` re-checks them against the raw pages. The `tools/build_*_eval.py` scripts rebuild them.

## Run
Put the supplied snapshot zips in `snapshots_zip/` (they are not in this repo). The scorer unpacks them into `snapshots/` on first run.

```
python harness/run_eval.py --submission solution --eval eval/public_eval.jsonl
python harness/run_eval.py --submission solution --eval eval/public_eval.jsonl --conflicts-gold eval/conflicts_gold_own.json
```

Ingest takes about 7 seconds; answers take about 0.1 seconds at p95.

## Results and limits
- Public set: accuracy 0.9488, consistency 1.0, speed score 1.0, no errors, no stale-value hits. This set was used for tuning, so it is optimistic.
- Clean first reads on unseen question sets we wrote ranged from about 0.43 to 0.88, so expect roughly 0.6 to 0.8 on unseen prose questions.
- The conflicts score uses our own small gold file, so it is not an independent measure.
