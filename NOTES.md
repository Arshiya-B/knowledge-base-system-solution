# Notes: temporal knowledge system for Dupaco website snapshots

Status: rate engine, prose engine (branch/contact/link facts) and `conflicts()` are built.

## Approach
Deterministic Python, standard library only. No LLM or network call at ingest or answer time.

1. **Row-level facts, not page diffs.** About 97% of pages differ between recrawls, mostly noise. Each markdown rate table is parsed into rows: label, heading context, tier (term, model-year range, balance or loan-amount range), metrics (APY, dividend rate, APR, rate), and the page's own "Rates are effective as of" stamp.
2. **Which value is current.** Ranked by match quality, then page authority (rates and product pages above landing pages above calculators above blog or news), then the in-page effective stamp, then snapshot date. The effective stamp is the real freshness signal. Crawl time is not.
3. **`as_of`.** Use only the latest snapshot with `taken_on <= as_of`. No `as_of` means the latest snapshot.
4. **Tier selection.** Term, model year and amount qualifiers filter rows. The tightest tier that fits wins (a $250,000 loan uses the "$300,000 or less" row). Business, jumbo, IRA, introductory and refinance variants are excluded unless the question mentions them.
5. **Abstaining.** If coverage of the question's product words is below 0.72, or a distinctive word is not covered, or the qualifiers eliminate every row, the system answers "I don't know" with no digits.

## Known data quirks handled
- A stale calculator page labels a column "Annual Percentage Yield" over cells that say "APR". The unit printed in the cell wins.
- Section names differ between snapshots ("Regular" versus "Regular Certificates"). The product link above the table supplies the missing context.
- The same loan row appears with and without thousands separators. These are merged.

## Evaluation
- `eval/public_eval.jsonl`: supplied set.
- `eval/custom_eval.jsonl` (30), `eval/custom_blind_eval.jsonl` (15), `eval/fresh_eval.jsonl` (16), `eval/fresh2_eval.jsonl` (16): written from the raw snapshots, each with its source snapshot, page and quote. `python tools/verify_gold.py snapshots eval/<file>.jsonl` re-checks every gold value against the raw pages. `tools/build_*_eval.py` regenerate the files.
- First-read scores (before any tuning on that file): blind 0.80, fresh 0.7353, fresh2 0.8814. Each file was then used for generic fixes, so its later score (1.0) is optimistic. Only the first read is an honest generalization number.

## Fixes the clean reads drove
- Product-name words that are usually filler ("You Name It", "High-Yield") are kept when the question spells out a product name the site uses.
- Words matched in a row's own name beat words that only appear in a distant heading.
- Conversational filler and -ing/-ed verbs that no rate row uses are ignored.
- "dividend rate, not the APY" switches the metric.

## Known gaps
- Prose facts are answered by a BM25 passage search with typed checks (phone, address, hours, amount, date, count, link). About 0.7 to 0.8 expected on unseen prose questions. Weak spot: deciding which of several pages owns a date or amount (hub pages versus the product page).
- Known public misses (after round 4): lobby hours "noon" (only an old press release says it; the current branch pages say 12:30), and the unwinnable dup-005. Fine-grained product splits on one page are still weak (HELOC versus home equity loan limits on the same page).
- `conflicts()` has no measured score: the hidden gold's size and granularity are unknown, and one entry per tier may cost precision.
- API keys: none needed. The solution makes no network or LLM calls.

## Reproduce
`python harness/run_eval.py --submission solution --eval eval/public_eval.jsonl`


## conflicts()
`solution/kbcore/conflicts.py`. A conflict is the same slot (product, tier, term) showing different numbers on different pages of the same snapshot.
- Bare tiers such as "$100,000+" only count as the same slot when the product heading above them matches, otherwise two products look like they disagree.
- Only the latest snapshot in which a slot disagrees is used. A rate that moved between snapshots is history, not a contradiction.
- Winner: newest "effective as of" stamp, then newest snapshot, then page authority (rate sheet over product page). The reason string says which rule decided.
- Prose claim: the branch count is repeated in dated press-release boilerplate (24, 23, 22 ...). The newest dated page wins (22).
- Limitation: our own conflict gold (`eval/conflicts_gold_own.json`) was written from this system's output, so its recall is optimistic and precision cannot be measured. The hidden gold size and granularity are unknown.


## Prose clean read and what it changed
`eval/prose_eval.jsonl` (17 items: grants, program dates, phone numbers, loan limits, 2 refusals; gold verified by `tools/verify_gold.py`) was written after the prose engine existed and run once before any tuning. First-read score: 0.4279 (public was 0.80 after tuning, so that gap was overfit). Generic fixes it drove:
- "how much / maximum / limit" use an amount intent (needs a $ or %), "how long" a duration intent, "who do I contact" a contact intent.
- Dates and "as of" are stripped from the question text before matching, so as-of questions do not fail on the digits.
- A capitalised name only has to appear on the same page for non-card facts; address, phone and hours cards must name the place themselves.
- A fact line with no subject ("Application period: ...") takes its subject from its page; big hub pages are down-weighted against focused pages.
- Small numbers in the question ("Week 4") must appear in the passage, so a missing week is refused instead of answered with weeks 1 to 3.
- "apply / application / applying" are one word; "ext." no longer ends a sentence.
After these fixes prose_eval is 0.6912, but that number is no longer a clean read (tuned on it). Still missed: which of several pages owns a date or amount (First-Time Homebuyer Grant vs a newsroom article, Gift of Innovation dates under a hub page).

## Second prose clean read
`eval/prose2_eval.jsonl` (12 items on business loans, credit cards, insurance, wellness; gold verified) was written after the prose fixes above and run once: **first-read 0.82**. Its two misses were generic and were then fixed: spelled-out numbers ("three years") now count for duration questions, and phrasing words such as "figured" or "calculated" no longer block a match. After that fix it scores 0.9914 (tuned, so optimistic). Honest estimate for unseen prose questions: about 0.7 to 0.8.

## Page ownership fixes (round 3)
Driven by prose misses where a news article or hub page beat the page that owns the fact:
- For amount, date, duration and contact questions, a page whose title or slug names the subject is boosted, product and landing pages outrank news, and a conflict between a product page and a news post goes to the product page.
- "How much" needs a dollar figure unless the question is about a rate or a share ("how much of a down payment").
- A date from years ago does not answer a present-tense "when" question.
- A "maximum / how long can" question prefers sentences that say "up to" or "maximum".
- Result: prose set 0.69 to 0.90 and public 0.8016 to 0.8171 (both tuned, so optimistic); custom, blind, fresh and prose2 sets unchanged. An unseen prose batch is still needed for a clean read of these fixes.

## Round 4: public misses and the third prose clean read
Public misses were fixed with general rules (each checked against all eval sets for regressions):
- Same-page figures are not conflicts: a page that lists "294 in 2023" and "256 in 2024" is answered with both, and duplicate pages with the same figures no longer count as disagreement.
- Definition questions ("what is X") skip "for more information, visit..." sentences and pull the nearest sentence that carries a figure (Home$tart's $15,000).
- "Update/edit/modify" is treated as "change", "become a member" as "join"; a how-to question about contact details is no longer read as a phone lookup, and a how-to answer keeps the sentences that follow the best one (the phone number comes right after).
- Eligibility questions answer with the section the page titles for it, and spell out the charter area (Iowa, Illinois, Wisconsin) using the site's own "serves residents in N counties" sentence.
- Generic blog advice that never names Dupaco no longer answers a question about what Dupaco does.
- "Link to see X rates" returns the rates button of the product page that discusses X; the abstain gate lets a product page whose title names two of the question's words answer a loosely worded question (student loans).
- Third clean read, `eval/prose3_eval.jsonl` (12 unseen items on business real estate loans, home equity, Rewards Visa, recreational loans, checking, 2 refusals): **first-read 0.5311**. Generic causes found: "borrow" and "stay" were stopwords, "points" and "5,000" made the rate engine think it was a rate question, "how long can the interest rate stay fixed" was blocked as a rate question, "smallest" was not understood as a minimum, calculator labels beat real sentences, and a section heading beat the one sentence that answered. All fixed generically; prose3 is then 0.8392 (tuned, so optimistic).
- After round 4: public 0.9488, prose 0.9127, prose2 1.0, custom/blind/fresh/fresh2 1.0 (all tuned). Honest estimate for unseen prose questions is now about 0.6 to 0.8, since the latest clean read was 0.53 before these fixes.

## Off-topic and real-time questions
None of the first five question sets contained a plain off-topic question; when tried, 4 of 15 leaked an answer (weather, a joke, Bitcoin's price, "who is the president"). Fixes, all general:
- Questions about real-time facts (weather, forecast, temperature, crypto and stock prices, sports scores, traffic) are refused, since a static snapshot cannot know them.
- A thin match (one or two content words, or no banking vocabulary at all) supported only by a blog, news or resource page is refused unless the question names Dupaco.
- Form furniture (the country-code dropdown) is filtered out of the index.
- Also: "longest/shortest term" is a duration question, and call-to-action sentences ("Check out ... >") are not added as supporting sentences. Result: 0 of 15 off-topic questions answered; all eval sets unchanged except prose 0.9127 to 0.901 (tuned).
- The Mullan Avenue case (public dup-102): only blog posts mention a "Mullan Avenue branch in Waterloo". No page gives its hours or address, so the system says it does not know instead of inventing hours.

## Design choice: no LLM, no embeddings
The assignment allows any approach. This solution is deterministic (BM25 plus typed rules): the same question always gives the same answer, it needs no API key, and it answers in about 0.1 seconds. The cost is weaker handling of loosely worded questions. An LLM re-ranker behind a flag with this system as the fallback is the obvious next step, but it was not built or measured here.


## Link and URL questions

Questions such as "link to see CD rates", "where can I apply online for an auto loan" or "how do I join" return a real link taken from the snapshot pages, never one built from memory. Rules: apply questions pick the apply link on the product page named by the topic; rates questions pick a rates link only on a page titled for the topic; otherwise links are scored by anchor and path words, and blog, newsroom and calculator links rank below product hubs. The source credited is the snapshot page that carries the link, or the target page when it is itself a snapshot page.
