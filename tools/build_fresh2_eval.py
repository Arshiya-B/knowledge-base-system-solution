"""Builds eval/fresh2_eval.jsonl: second clean read, written AFTER the product-name fixes.

Run once, record the score, then do not tune against it.
"""
import json, sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import build_custom_eval as B
B.ITEMS.clear()
item, RATES, AUTO = B.item, B.RATES, B.AUTO
BUS = "https://www.dupaco.com/business-rates"
S1, S2, S3, S4, S5 = B.S1, B.S2, B.S3, B.S4, B.S5

item("gx-001", "What APY does a business Investor's Choice Money Market pay on $40,000?", None,
     "Investor's Choice Money Market (Business), $25,000 - $99,999.99 tier: 0.35% APY.", ["0.35%"], ["0.40%", "0.30%"], "entity_attribution", "hard", 2.0, S5, BUS,
     "| Investor's Choice Money Market (Business) | $25,000 – $99,999.99 | 0.35% | 0.35%1 | $2,500.00 | $25,000.00 |", "g2-bmm")
item("gx-002", "I run a small business. What APY would $50,000 earn in High-Yield Savings?", None,
     "High-Yield Savings (Business), $0.01 - $99,999.99 tier: 1.50% APY.", ["1.50%"], ["1.85%", "2.05%"], "tier_disambiguation", "hard", 2.0, S5, BUS,
     "| High-Yield Savings (Business) | $0.01 – $99,999.99 | 1.49% | 1.50%1 | $50,000.00 | $0.01 |", "g2-bhy")
item("gx-003", "What does Bright Savings pay in APY?", None,
     "Bright Savings, $0.01 - $1,000,000: 2.25% APY.", ["2.25%"], ["0.20%"], "current_value", "medium", 1.5, S5, RATES,
     "| Bright Savings | $0.01 – $1,000,000 | 2.23% | 2.25% | $0.00 | $0.01 |", "g2-bright")
item("gx-004", "Holiday Club Savings dividend rate as of 2026-06-15?", "2026-06-15",
     "June 9 snapshot: Holiday Club Savings 0.20% dividend rate.", ["0.20%"], ["2.25%"], "temporal_as_of", "medium", 1.5, S3, RATES,
     "| Holiday Club Savings | $0.01+ | 0.20% | 0.20% | $0.00 | $0.01 |", "g2-holiday")
item("gx-005", "What APY does a Traditional IRA earn on a $20,000 balance?", None,
     "Traditional IRA, $15,000+ tier: 0.60% APY.", ["0.60%"], ["0.50%", "0.45%"], "tier_disambiguation", "hard", 2.0, S5, RATES,
     "| Traditional: $15,000+ | 0.60% | 0.60%1 | $15,000.00 |", "g2-ira")
item("gx-006", "As of 2026-05-25, what APY did 1st Rate Checking pay on a $30,000 balance?", "2026-05-25",
     "May 19 snapshot: $25,000 - $99,999.99 tier paid 0.10% APY.", ["0.10%"], ["3.00%", "2.50%"], "temporal_as_of", "hard", 2.0, S2, RATES,
     "| $25,000 - $99,999.99 | 0.10% | 0.10% | None | $25,000 |", "g2-1st")
item("gx-007", "30-year fixed purchase mortgage with a $300,000 loan as of 2026-06-20: rate and APR?", "2026-06-20",
     "June 9 snapshot: $300,000 or less tier 6.375% rate, 6.449% APR.", ["6.375%", "6.449%"], ["7.25%", "7.32%"], "temporal_as_of", "hard", 2.0, S3, RATES,
     "| Purchase: 30-Year Fixed Conventional $300,000 or less | 6.375% | 0.00% | 6.449% |", "g2-m")
item("gx-008", "What was the APR on a 30 year fixed purchase loan of $200,000 as of 2026-09-15?", "2026-09-15",
     "Aug 27 snapshot: $200,000 or less tier 6.375% rate, 6.456% APR.", ["6.456%"], ["7.34%"], "temporal_as_of", "hard", 2.0, S4, RATES,
     "| Purchase: 30-Year Fixed Conventional $200,000 or less | 6.375% | 0.00% | 6.456% |", "g2-m")
item("gx-009", "Rate and APR for a 30-year fixed home purchase loan of $600,000?", None,
     "$832,750 or less tier: 7.25% rate, 7.29% APR.", ["7.25%", "7.29%"], ["7.32%", "7.34%"], "tier_disambiguation", "hard", 2.0, S5, RATES,
     "| Purchase: 30-Year Fixed Conventional $832,750 or less | 7.25% | 0 | 7.29% |", "g2-m")
item("gx-010", "What APR would I get on an 84 month auto loan for a 2022 car as of 2026-09-10?", "2026-09-10",
     "Aug 27 snapshot: 2021-22 Model Year, 84 months: 5.84% APR.", ["5.84%"], ["6.04%"], "temporal_as_of", "hard", 2.0, S4, AUTO,
     "| 2021-22 Model Year | 84 Months | 5.84% APR", "g2-auto")
item("gx-011", "Auto loan APR for a 2014 vehicle over 48 months as of 2026-05-20?", "2026-05-20",
     "May 19 snapshot: 2016 Model Year (and older), 48 months: 8.39% APR.", ["8.39%"], ["8.59%"], "temporal_as_of", "hard", 2.0, S2, AUTO,
     "| 2016 Model Year (and older) | 48 Months | 8.39% APR", "g2-auto")
item("gx-012", "What's the dividend rate on the 10 month special certificate?", None,
     "10 Month Fixed Certificate Special dividend rate: 3.86% (3.90% APY).", ["3.86%"], ["4.00%", "3.80%"], "tier_disambiguation", "medium", 1.5, S5, RATES,
     "| 10 Month Fixed Certificate Special | 3.86% | 3.90%2 | $1,000.00 |", "g2-cert")
item("gx-013", "Interest rate and APR on a 20-year refinance?", None,
     "Refinance 20-Year Fixed Conventional: 7.13% rate, 7.28% APR.", ["7.13%", "7.28%"], ["7.26%"], "entity_attribution", "hard", 2.0, S5, RATES,
     "| Refinance: 20-Year Fixed Conventional | 7.13% | 0 | 7.28% |", "g2-m")
item("gx-014", "Hi! I'm thinking about opening a Share Savings account and depositing $3,000. What dividend rate would I get?", None,
     "Share Savings, $2,500 - $9,999.99 tier: 0.10% dividend rate.", ["0.10%"], ["0.15%", "0.20%"], "tier_disambiguation", "medium", 1.5, S5, RATES,
     "| Share Savings | $2,500 – $9,999.99 | 0.10% | 0.10%1 | $25.00 | $2,500.00 |", "g2-ss")
item("gx-015", "What dividend rate does the Smart Saver Plus account pay?", None,
     "No such account is listed; Dupaco should be contacted.", [], ["0.20%", "0.15%"], "should_refuse", "medium", 1.5, None, None, None, "g2-ref")
item("gx-016", "What APY does a 5-year Roth IRA bonus certificate earn?", None,
     "No such product is listed; Dupaco should be contacted.", [], ["1.80%"], "should_refuse", "hard", 2.0, None, None, None, "g2-ref")

if __name__ == "__main__":
    with open("eval/fresh2_eval.jsonl", "w") as f:
        for r in B.ITEMS:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(len(B.ITEMS), "fresh2 items")
