"""Builds eval/custom_eval.jsonl (tuning set) and eval/custom_blind_eval.jsonl (blind set).

Every item carries gold_snapshot / gold_url / gold_quote so tools/verify_gold.py can
re-check the gold answer against the raw snapshot pages.  Items are written by hand
from the corpus; nothing here is produced by the solution under test.
"""
import json, os, sys

RATES = "https://www.dupaco.com/rates"
AUTO = "https://www.dupaco.com/personal/loans/auto-motorcycle-loans"
S1, S2, S3, S4, S5 = "01_2026-05-12_baseline", "02_2026-05-19_recrawl", "03_2026-06-09_recrawl", "04_2026-08-27_rebaseline", "05_2026-09-28_latest"

ITEMS = []
def item(id, q, as_of, answer, inc, exc, cat, diff, w, snap, url, quote, group=None, blind=False):
    ITEMS.append(dict(id=id, question=q, as_of=as_of, expected_answer=answer, must_include=inc,
        must_not_include=exc, category=cat, difficulty=diff, weight=w,
        expected_sources=[url] if (url and cat != 'should_refuse') else [], group=group or id,
        gold_snapshot=snap, gold_url=url, gold_quote=quote, blind=blind))

# ---------------- certificates (tier + as_of) ----------------
q17 = "| 17 Month Fixed Certificate Special | 4.06% | 4.10%2 | $1,000.00 |"
item("cx-001", "What APY does the 17 month special certificate earn right now?", None,
     "17-Month Fixed Certificate Special: 4.10% APY ($1,000 min). Jumbo version is 4.20%.", ["4.10%"], ["3.85%", "3.95%"], "tier_disambiguation", "medium", 1.5, S5, RATES, q17, "g-cert17")
item("cx-002", "If I put $5,000 in Dupaco's 17-month certificate special today, what yield do I get?", None,
     "17-Month Fixed Certificate Special pays 4.10% APY.", ["4.10%"], ["4.20%"], "tier_disambiguation", "hard", 2.0, S5, RATES, q17, "g-cert17")
item("cx-003", "Dupaco 17 month special certificate APY as of 2026-06-10?", "2026-06-10",
     "As of 2026-06-10 (June 9 snapshot) the 17-Month Fixed Certificate Special paid 3.85% APY.", ["3.85%"], ["4.10%", "3.95%"], "temporal_as_of", "medium", 1.5, S3,
     RATES, "| 17 Month Fixed Certificate Special | 3.81% | 3.85%2 | $1,000 |", "g-cert17-time")
item("cx-004", "What was the 17-month special certificate APY at the end of August 2026 (as of 2026-08-30)?", "2026-08-30",
     "The August 27 snapshot lists 3.95% APY for the 17-Month Fixed Certificate Special.", ["3.95%"], ["3.85%", "4.10%"], "temporal_as_of", "hard", 2.0, S4,
     RATES, "| 17 Month Fixed Certificate Special | 3.91% | 3.95%2 | $1,000 |", "g-cert17-time", blind=True)
item("cx-005", "As of 2026-05-15, what APY did the 25 month special certificate pay?", "2026-05-15",
     "The May 12 snapshot lists the 25-Month Fixed Certificate Special at 3.60% APY.", ["3.60%"], ["4.10%"], "temporal_as_of", "medium", 1.5, S1,
     RATES, "| 25 Month Fixed Certificate Special | 3.57% | 3.60%2 | $1,000 |", "g-cert25")
item("cx-006", "What's the current APY on the 25-month certificate special?", None,
     "The 25-month special is no longer listed on the current rates page; the site does not give a current rate.", [], ["3.60%", "3.70%"], "should_refuse", "hard", 2.0, S5,
     RATES, "| 17 Month Fixed Certificate Special | 4.06% | 4.10%2 | $1,000.00 |", "g-cert25", blind=True)
item("cx-007", "APY for the 10-month jumbo certificate special?", None,
     "10 Month Fixed Jumbo Certificate Special: 4.00% APY ($100,000 minimum).", ["4.00%"], ["3.70%"], "tier_disambiguation", "medium", 1.5, S5,
     RATES, "| 10 Month Fixed Jumbo Certificate Special | 3.96% | 4.00%1 | $100,000.00 |", "g-cert10")
item("cx-008", "How much does a $1,000 10-month certificate special pay in APY on 2026-05-15?", "2026-05-15",
     "May 12 snapshot: 10 Month Fixed Certificate Special 3.80% APY.", ["3.80%"], ["3.90%"], "temporal_as_of", "hard", 2.0, S1,
     RATES, "| 10 Month Fixed Certificate Special | 3.76% | 3.80%2 | $1,000 |", "g-cert10")
item("cx-009", "What's the APY on a 12 month certificate?", None,
     "12 Month certificate: 3.40% APY ($1,000 minimum).", ["3.40%"], ["2.90%"], "stale_trap", "medium", 1.5, S5,
     RATES, "| 12 Month | 3.37% | 3.40%1 | $1,000.00 |", "g-cert12")
item("cx-010", "12-month certificate APY as of 2026-05-14?", "2026-05-14",
     "May 12 snapshot lists the 12 Month certificate at 2.90% APY.", ["2.90%"], ["3.40%"], "temporal_as_of", "hard", 2.0, S1,
     RATES, "| 12 Month | 2.88% | 2.90% | $1,000 |", "g-cert12")
item("cx-011", "What does a 60 month certificate earn in APY?", None,
     "60 Month certificate: 1.80% APY (1.79% dividend rate).", ["1.80%"], ["3.40%"], "current_value", "easy", 1.0, S5,
     RATES, "| 60 Month | 1.79% | 1.80%1 | $1,000.00 |", "g-cert60")
item("cx-012", "Which certificate specials does Dupaco have right now and what do they pay?", None,
     "17-month 4.10% APY / jumbo 4.20% APY; 10-month 3.90% APY / jumbo 4.00% APY.", ["4.10%", "4.20%", "3.90%", "4.00%"], ["3.60%", "3.70%"], "list_completeness", "hard", 2.0, S5,
     RATES, [q17, "| 17 Month Fixed Jumbo Certificate Special | 4.15% | 4.20%1 | $100,000.00 |",
             "| 10 Month Fixed Certificate Special | 3.86% | 3.90%2 | $1,000.00 |",
             "| 10 Month Fixed Jumbo Certificate Special | 3.96% | 4.00%1 | $100,000.00 |"], "g-certlist", blind=True)
item("cx-013", "What APY does a Roth IRA 10 month jumbo special get?", None,
     "Roth: 10 Month Fixed Jumbo Special pays 4.00% APY.", ["4.00%"], ["3.90%"], "entity_attribution", "hard", 2.0, S5,
     RATES, "| Roth: 10 Month Fixed Jumbo Special | 3.96% | 4.00%1 | $100,000.00 |", "g-ira10")
item("cx-014", "And for a Traditional IRA 10 month jumbo special, what's the APY?", None,
     "Traditional: 10 Month Fixed Jumbo Special pays 3.90% APY.", ["3.90%"], ["4.00%"], "entity_attribution", "hard", 2.0, S5,
     RATES, "| Traditional: 10 Month Fixed Jumbo Special | 3.86% | 3.90%1 | $100,000.00 |", "g-ira10", blind=True)

# ---------------- deposits (balance tiers) ----------------
item("cx-020", "I have $12,000 in Share Savings. What dividend rate applies?", None,
     "Share Savings, $10,000 - $24,999.99 tier: 0.15% dividend rate.", ["0.15%"], ["0.20%", "0.10%"], "tier_disambiguation", "medium", 1.5, S5,
     RATES, "| Share Savings | $10,000 – $24,999.99 | 0.15% | 0.15%1 | $25.00 | $10,000.00 |", "g-ss")
item("cx-021", "What is the APY for a Share Savings balance of $30,000?", None,
     "Share Savings $25,000+ tier: 0.20% APY.", ["0.20%"], ["0.15%"], "tier_disambiguation", "medium", 1.5, S5,
     RATES, "| Share Savings | $25,000+ | 0.20% | 0.20%1 | $25.00 | $25,000.00 |", "g-ss")
item("cx-022", "Share savings with only $50 in it, what does it earn?", None,
     "Share Savings $0 - $99.99 tier: 0.00%.", ["0.00%"], ["0.10%", "0.15%"], "tier_disambiguation", "medium", 1.5, S5,
     RATES, "| Share Savings | $0 – $99.99 | 0.00% | 0.00%1 | $25.00 | $0.00 |", "g-ss", blind=True)
item("cx-023", "What APY does the Investor's Choice Money Market pay on $60,000?", None,
     "Investor's Choice Money Market $25,000 - $99,999.99 tier: 0.35% APY.", ["0.35%"], ["0.40%", "0.30%"], "tier_disambiguation", "hard", 2.0, S5,
     RATES, "| Investor's Choice Money Market | $25,000 – $99,999.99 | 0.35% | 0.35% | $2,500.00 | $25,000.00 |", "g-mm")
item("cx-024", "Money market rate for a $150,000 balance?", None,
     "Investor's Choice Money Market $100,000+ tier: 0.40%.", ["0.40%"], ["0.35%"], "tier_disambiguation", "medium", 1.5, S5,
     RATES, "| Investor's Choice Money Market | $100,000+ | 0.40% | 0.40% | $2,500.00 | $100,000.00 |", "g-mm", blind=True)
item("cx-025", "What APY does 1st Rate Checking pay if I keep $8,000 in it?", None,
     "1st Rate Checking $5,000 - $24,999.99 tier: 2.50% APY.", ["2.50%"], ["3.00%", "0.10%"], "stale_trap", "hard", 2.0, S5,
     RATES, "| 1st Rate Checking | $5,000 – $24,999.99 | 2.47% | 2.50% | — | $5,000.00 |", "g-1st")
item("cx-026", "As of 2026-05-14, what APY did 1st Rate Checking pay on an $8,000 balance?", "2026-05-14",
     "May 12 snapshot: $5,000 - $24,999.99 tier paid 3.00% APY.", ["3.00%"], ["2.50%"], "temporal_as_of", "hard", 2.0, S1,
     RATES, "| $5,000 - $24,999.99 | 2.96% | 3.00% | None | $5,000 |", "g-1st")
item("cx-027", "1st Rate Checking APY for $8,000 as of 2026-07-01?", "2026-07-01",
     "June 9 snapshot: $5,000 - $24,999.99 tier paid 2.50% APY.", ["2.50%"], ["3.00%"], "temporal_as_of", "hard", 2.0, S3,
     RATES, "| $5,000 - $24,999.99 | 2.47% | 2.50% | None | $5,000 |", "g-1st", blind=True)
item("cx-028", "As of 2026-07-01, what did a Roth IRA earn on a $6,000 balance?", "2026-07-01",
     "June 9 snapshot: Roth $5,000-$14,999.99 tier 0.50% APY.", ["0.50%"], ["0.60%", "0.45%"], "tier_disambiguation", "hard", 2.0, S3,
     RATES, "| Roth: $5,000-$14,999.99 | 0.50% | 0.50% | $5,000 |", "g-ira")

# ---------------- mortgages (loan-amount tiers + time) ----------------
m = lambda lab, r, z, a: f"| {lab} | {r} | {z} | {a} |"
item("cx-030", "What rate and APR is Dupaco offering on a 30-year fixed purchase mortgage up to $100,000?", None,
     "30-Year Fixed Conventional $100,000 or less: 7.13% rate, 7.27% APR.", ["7.13%", "7.27%"], ["6.514%", "6.375%"], "stale_trap", "hard", 2.0, S5,
     RATES, "| Purchase: 30-Year Fixed Conventional $100,000 or less | 7.13% | 0 | 7.27% |", "g-m30")
item("cx-031", "30 year mortgage on a $100k loan, as of 2026-05-13?", "2026-05-13",
     "May 12 snapshot: 5.875% rate / 6.010% APR.", ["5.875%", "6.010%"], ["7.13%"], "temporal_as_of", "hard", 2.0, S1,
     RATES, "| Purchase: 30-Year Fixed Conventional $100,000 or less | 5.875% | 0.00% | 6.010% |", "g-m30")
item("cx-032", "30-year fixed rate on a $100,000 loan as of 2026-06-10", "2026-06-10",
     "June 9 snapshot: 6.125% / 6.256% APR.", ["6.125%", "6.256%"], ["7.13%", "5.875%"], "temporal_as_of", "hard", 2.0, S3,
     RATES, "| Purchase: 30-Year Fixed Conventional $100,000 or less | 6.125% | 0.00% | 6.256% |", "g-m30", blind=True)
item("cx-033", "What was the 30-year purchase rate for loans up to $100,000 as of 2026-09-01?", "2026-09-01",
     "Aug 27 snapshot: 6.375% / 6.514% APR.", ["6.375%", "6.514%"], ["7.13%"], "temporal_as_of", "hard", 2.0, S4,
     RATES, "| Purchase: 30-Year Fixed Conventional $100,000 or less | 6.375% | 0.00% | 6.514% |", "g-m30")
item("cx-034", "What's the interest rate on a 15-year fixed mortgage?", None,
     "Purchase 15-Year Fixed Conventional: 6.75% rate, 6.88% APR.", ["6.75%", "6.88%"], ["6.000%", "5.875%"], "stale_trap", "hard", 2.0, S5,
     RATES, "| Purchase: 15-Year Fixed Conventional | 6.75% | 0 | 6.88% |", "g-m15")
item("cx-035", "15-year fixed purchase rate on 2026-05-20?", "2026-05-20",
     "May 19 snapshot: 6.000% rate, 6.125% APR.", ["6.000%", "6.125%"], ["6.75%"], "temporal_as_of", "hard", 2.0, S2,
     RATES, "| Purchase: 15-Year Fixed Conventional | 6.000% | 0.00% | 6.125% |", "g-m15", blind=True)
item("cx-036", "Rate on a 20-year fixed home loan?", None,
     "Purchase 20-Year Fixed Conventional: 7.13% rate, 7.26% APR.", ["7.13%", "7.26%"], ["6.250%"], "current_value", "medium", 1.5, S5,
     RATES, "| Purchase: 20-Year Fixed Conventional | 7.13% | 0 | 7.26% |", "g-m20")
item("cx-037", "I want to borrow $250,000 on a 30-year fixed home purchase. What's the rate and APR?", None,
     "$300,000-or-less tier: 7.25% rate, 7.32% APR.", ["7.25%", "7.32%"], ["7.34%", "7.29%"], "tier_disambiguation", "hard", 2.0, S5,
     RATES, "| Purchase: 30-Year Fixed Conventional $300,000 or less | 7.25% | 0 | 7.32% |", "g-m30t")
item("cx-038", "What APR would I see on a $150,000 30 year fixed purchase loan?", None,
     "$200,000-or-less tier: 7.25% rate, 7.34% APR.", ["7.34%"], ["7.32%", "7.27%"], "tier_disambiguation", "hard", 2.0, S5,
     RATES, "| Purchase: 30-Year Fixed Conventional $200,000 or less | 7.25% | 0 | 7.34% |", "g-m30t", blind=True)
item("cx-039", "Rate and APR for refinancing into a 30-year fixed with a $100,000 balance?", None,
     "Refinance 30-Year Fixed Conventional $100,000 or less: 7.13% rate, 7.28% APR.", ["7.13%", "7.28%"], ["7.27%"], "entity_attribution", "hard", 2.0, S5,
     RATES, "| Refinance: 30-Year Fixed Conventional $100,000 or less | 7.13% | 0 | 7.28% |", "g-mref")

# ---------------- auto loans (model-year x term) ----------------
a = lambda yr, t, r: f"| {yr} Model Year | {t} Months | {r}% APR"
item("cx-040", "What's the APR on a 60 month auto loan for a 2025 vehicle?", None,
     "2024-27 Model Year, 60 months: 5.39% APR.", ["5.39%"], ["5.19%"], "stale_trap", "hard", 2.0, S5,
     AUTO, a("2024-27", 60, "5.39"), "g-auto")
item("cx-041", "Auto loan APR, 72 months, 2022 model year?", None,
     "2021-23 Model Year, 72 months: 5.79% APR.", ["5.79%"], ["5.59%"], "tier_disambiguation", "hard", 2.0, S5,
     AUTO, a("2021-23", 72, "5.79"), "g-auto", blind=True)
item("cx-042", "I'm financing a 2019 car over 72 months, what APR should I expect?", None,
     "2017-20 Model Year, 72 months: 6.49% APR.", ["6.49%"], ["6.29%"], "tier_disambiguation", "hard", 2.0, S5,
     AUTO, a("2017-20", 72, "6.49"), "g-auto")
item("cx-043", "60 month auto loan APR for a 2024 model, as of 2026-06-10?", "2026-06-10",
     "June 9 snapshot: 2023-26 Model Year, 60 months: 5.19% APR.", ["5.19%"], ["5.39%"], "temporal_as_of", "hard", 2.0, S3,
     AUTO, a("2023–26", 60, "5.19"), "g-auto")
item("cx-044", "Auto loan APR for an 84-month term on a 2025 model year?", None,
     "2024-27 Model Year, 84 months: 5.59% APR.", ["5.59%"], ["5.39%", "5.54%"], "tier_disambiguation", "medium", 1.5, S5,
     AUTO, a("2024-27", 84, "5.59"), "g-auto", blind=True)

# ---------------- other loans / cards ----------------
item("cx-050", "What's the rate on a standard HELOC?", None,
     "HELOC Standard: 6.25% APR.", ["6.25%"], ["1.99%"], "current_value", "medium", 1.5, S5,
     RATES, "| HELOC – Standard | 6.25%1 |", "g-heloc")
item("cx-051", "What APR range does the Platinum Visa carry?", None,
     "Platinum Visa Rate: 12.50% to 19.50% APR.", ["12.50%", "19.50%"], ["15.50%"], "entity_attribution", "medium", 1.5, S5,
     RATES, "| Platinum Visa Rate | 12.50% – 19.50%2 |", "g-visa", blind=True)

# ---------------- unanswerable decoys ----------------
for i, (q, exc) in enumerate([
    ("What's the APY on a 27-month certificate at Dupaco?", ["3.60%", "4.10%"]),
    ("What rate does Dupaco charge on a 40-year fixed mortgage?", ["7.13%", "7.25%"]),
    ("What APR does Dupaco offer on a cryptocurrency-backed loan?", ["12.50%"]),
    ("What APY does Dupaco's Platinum Diamond Bonus Certificate pay?", ["4.10%", "4.20%"]),
    ("What is Dupaco's rate for a yacht loan with a 30 year term?", ["5.39%"]),
], 1):
    item(f"cx-06{i}", q, None, "The website does not give this; Dupaco should be contacted directly.", [], exc,
         "should_refuse", "medium", 1.5, None, None, None, f"g-ref{i}", blind=(i in (2, 5)))

def dump(path, rows):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "eval"
    tune = [i for i in ITEMS if not i["blind"]]
    blind = [i for i in ITEMS if i["blind"]]
    dump(os.path.join(out, "custom_eval.jsonl"), tune)
    dump(os.path.join(out, "custom_blind_eval.jsonl"), blind)
    print(len(tune), "tuning items,", len(blind), "blind items")
