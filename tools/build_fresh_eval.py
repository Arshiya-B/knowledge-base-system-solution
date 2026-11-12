"""Builds eval/fresh_eval.jsonl: a clean read written AFTER step 1 was tuned.

Nobody had seen the engine's output on these items when they were written.
Run once, record the score, then do not tune against it.
"""
import json, sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import build_custom_eval as B
B.ITEMS.clear()
item, RATES, AUTO = B.item, B.RATES, B.AUTO
BUS = "https://www.dupaco.com/business-rates"
S1, S2, S3, S4, S5 = B.S1, B.S2, B.S3, B.S4, B.S5

item("fx-001", "My HSA has $12,000 in it. What APY am I earning?", None,
     "Health Savings Account, $10,000 - $24,999.99 tier: 0.30% APY.", ["0.30%"], ["0.35%", "0.25%"], "tier_disambiguation", "hard", 2.0, S5, RATES,
     "| Health Savings Account | $10,000 – $24,999.99 | 0.30% | 0.30%1 | $25.00 | $10,000.00 |", "f-hsa")
item("fx-002", "Dividend rate on a health savings account with a $1,000 balance?", None,
     "Health Savings Account, $0.01 - $2,499.99 tier: 0.20%.", ["0.20%"], ["0.25%"], "tier_disambiguation", "medium", 1.5, S5, RATES,
     "| Health Savings Account | $0.01 – $2,499.99 | 0.20% | 0.20%1 | $25.00 | $0.01 |", "f-hsa")
item("fx-003", "What APY does High-Yield Savings pay on $300,000?", None,
     "High-Yield Savings, $250,000 - $499,999.99 tier: 2.05% APY.", ["2.05%"], ["1.85%", "2.25%"], "tier_disambiguation", "hard", 2.0, S5, RATES,
     "| High-Yield Savings | $250,000 – $499,999.99 | 2.03% | 2.05%", "f-hy")
item("fx-004", "High-yield savings APY with $120,000 on deposit, as of 2026-05-13?", "2026-05-13",
     "May 12 snapshot: $100,000 - $249,999.99 tier paid 1.85% APY.", ["1.85%"], ["2.05%"], "temporal_as_of", "hard", 2.0, S1, RATES,
     "| $100,000 - $249,999.99 | 1.83% | 1.85% | $50,000 | $100,000 |", "f-hy")
item("fx-005", "What does a business High-Yield Savings account pay with $600,000?", None,
     "High-Yield Savings (Business), $500,000 - $999,999.99 tier: 2.25% APY.", ["2.25%"], ["2.05%", "2.45%"], "entity_attribution", "hard", 2.0, S5, BUS,
     "| High-Yield Savings (Business) | $500,000 – $999,999.99 | 2.23% | 2.25%1 | $50,000.00 | $500,000.00 |", "f-bhy")
item("fx-006", "APY for Business 1st Rate Checking if the balance is $10,000?", None,
     "Business 1st Rate Checking, $5,000 - $24,999.99 tier: 2.50% APY.", ["2.50%"], ["0.10%"], "entity_attribution", "hard", 2.0, S5, BUS,
     "| Business 1st Rate Checking | $5,000 – $24,999.99 | 2.47% | 2.50%1 | — | $5,000.00 |", "f-b1st")
item("fx-007", "What dividend rate does You Name It Savings pay on $20,000?", None,
     "You Name It Savings, $10,000 - $24,999.99 tier: 0.15%.", ["0.15%"], ["0.20%", "0.10%"], "tier_disambiguation", "medium", 1.5, S5, RATES,
     "| You Name It Savings | $10,000 – $24,999.99 | 0.15% | 0.15% | $0.00 | $10,000.00 |", "f-yni")
item("fx-008", "Dupaco 20-year fixed home purchase rate and APR as of 2026-06-12?", "2026-06-12",
     "June 9 snapshot: 20-Year Fixed Conventional 6.125% rate, 6.256% APR.", ["6.125%", "6.256%"], ["7.13%", "6.250%"], "temporal_as_of", "hard", 2.0, S3, RATES,
     "| Purchase: 20-Year Fixed Conventional | 6.125% | 0.00% | 6.256% |", "f-m")
item("fx-009", "What was the 15-year fixed purchase rate on 2026-08-27?", "2026-08-27",
     "Aug 27 snapshot: 15-Year Fixed Conventional 6.000% rate, 6.125% APR.", ["6.000%", "6.125%"], ["6.75%", "5.875%"], "temporal_as_of", "hard", 2.0, S4, RATES,
     "| Purchase: 15-Year Fixed Conventional | 6.000% | 0.00% | 6.125% |", "f-m")
item("fx-010", "As of 2026-05-12, refinance rate for a 30-year fixed with a $200,000 loan?", "2026-05-12",
     "May 12 snapshot: Refinance 30-Year Fixed Conventional $200,000 or less 6.000% rate, 6.091% APR.", ["6.000%", "6.091%"], ["6.079%"], "entity_attribution", "hard", 2.0, S1, RATES,
     "| Refinance: 30-Year Fixed Conventional $200,000 or less | 6.000% | 0.00% | 6.091% |", "f-m")
item("fx-011", "What APR applies to a 48-month auto loan on a 2015 vehicle?", None,
     "2016 Model Year (and older), 48 months: 8.59% APR.", ["8.59%"], ["8.39%"], "tier_disambiguation", "hard", 2.0, S5, AUTO,
     "| 2016 Model Year (and older) | 48 Months | 8.59% APR", "f-auto")
item("fx-012", "60-month auto loan APR for a 2018 car as of 2026-09-01?", "2026-09-01",
     "Aug 27 snapshot: 2017-20 Model Year, 60 months: 6.14% APR.", ["6.14%"], ["6.34%"], "temporal_as_of", "hard", 2.0, S4, AUTO,
     "| 2017-20 Model Year | 60 Months | 6.14% APR", "f-auto")
item("fx-013", "What APY is paid on a 6 month certificate?", None,
     "6 Month certificate: 3.40% APY.", ["3.40%"], ["2.70%", "2.10%"], "current_value", "easy", 1.0, S5, RATES,
     "| 6 Month | 3.37% | 3.40%1 | $1,000.00 |", "f-cert")
item("fx-014", "36 month certificate yield as of 2026-06-20?", "2026-06-20",
     "June 9 snapshot: 36 Month certificate 2.10% APY.", ["2.10%"], ["3.40%"], "temporal_as_of", "medium", 1.5, S3, RATES,
     "| 36 Month | 2.09% | 2.10% | $1,000 |", "f-cert")
item("fx-015", "What was the dividend rate (not the APY) on the 17 month jumbo certificate special as of 2026-08-28?", "2026-08-28",
     "Aug 27 snapshot: 17 Month Fixed Jumbo Certificate Special dividend rate 4.01% (4.05% APY).", ["4.01%"], ["4.15%"], "entity_attribution", "hard", 2.0, S4, RATES,
     "| 17 Month Fixed Jumbo Certificate Special | 4.01% | 4.05%1 | $100,000 |", "f-cj")
item("fx-016", "What APY does the Premier Gold money market account pay?", None,
     "No such account is listed; Dupaco should be contacted.", [], ["0.40%", "0.35%"], "should_refuse", "medium", 1.5, None, None, None, "f-ref")

if __name__ == "__main__":
    with open("eval/fresh_eval.jsonl", "w") as f:
        for r in B.ITEMS:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(len(B.ITEMS), "fresh items")
