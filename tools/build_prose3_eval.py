"""Builds eval/prose3_eval.jsonl: third clean read for the prose engine, written AFTER the round-4 fixes.

Run once, record the first-read score, then do not tune against it.
"""
import json, sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import build_custom_eval as B
B.ITEMS.clear()
item = B.item
S5 = B.S5
D = "https://www.dupaco.com"
RE = D + "/business/loans/real-estate-loans"
HE = D + "/personal/loans/home-equity"
CC = D + "/personal/credit-cards"

item("pz-001", "What is the longest term on a Dupaco business real estate loan?", None,
     "Loan terms up to 20 years.", ["20 years"], [], "current_value", "medium", 1.5, S5, RE, "Loan terms are available for up to 20 years", "q-re1")
item("pz-002", "For how long can the interest rate stay fixed on a Dupaco business real estate loan?", None,
     "Fixed rates for up to five years.", ["five years"], [], "current_value", "medium", 1.5, S5, RE, "fixed interest rates for up to five years", "q-re2")
item("pz-003", "What down payment does Dupaco typically require for a business real estate loan?", None,
     "A minimum of 20%.", ["20%"], [], "current_value", "medium", 1.5, S5, RE, "A minimum down payment of 20% is typically required", "q-re3")
item("pz-004", "How much of my available equity can I borrow with a Dupaco HELOC?", None,
     "Up to 100% of available equity, with a $5,000 minimum.", ["100%"], ["85%"], "tier_disambiguation", "hard", 2.0, S5, HE, "Borrow up to 100% of your available equity", "q-he1")
item("pz-005", "How much of my home's equity can I borrow with the Dupaco home equity loan?", None,
     "Up to 85% of home equity, with a $5,000 minimum.", ["85%"], ["100%"], "tier_disambiguation", "hard", 2.0, S5, HE, "Borrow up to 85% of your home", "q-he2")
item("pz-006", "How much of the closing costs will Dupaco cover on a home equity line of credit?", None,
     "Closing costs up to $350.", ["$350"], [], "current_value", "medium", 1.5, S5, HE, "cover closing costs up to $350", "q-he3")
item("pz-007", "What is the smallest redemption I can make with Dupaco Rewards Visa points?", None,
     "Redemptions start at $25.", ["$25"], [], "current_value", "medium", 1.5, S5, CC, "Redemptions start at $25", "q-cc1")
item("pz-008", "How much cash is 5,000 Dupaco Rewards Visa points worth?", None,
     "About $50.", ["$50"], [], "current_value", "easy", 1.0, S5, CC, "5,000 points is about $50", "q-cc2")
item("pz-009", "What is the longest repayment term on a Dupaco recreational loan?", None,
     "Terms up to 84 months.", ["84"], [], "current_value", "medium", 1.5, S5, D + "/personal/loans/recreational-loans", "terms up to 84 months", "q-rec")
item("pz-010", "How can I avoid the monthly fee on Dupaco personal checking?", None,
     "Keep a monthly balance of $5,000 or more to avoid the $10 fee.", ["$5,000"], [], "current_value", "medium", 1.5, S5, D + "/personal/checking-accounts", "avoid a $10 monthly fee by keeping a monthly balance of $5,000+", "q-chk")
item("pz-011", "What interest rate does Dupaco charge on a cryptocurrency-backed loan?", None,
     "Dupaco lists no cryptocurrency loan; contact Dupaco.", [], ["%"], "should_refuse", "medium", 1.5, None, None, None, "q-ref1")
item("pz-012", "What is the cash back percentage on the Dupaco Platinum Elite Visa?", None,
     "Dupaco lists no Platinum Elite Visa; contact Dupaco.", [], ["%"], "should_refuse", "medium", 1.5, None, None, None, "q-ref2")

if __name__ == "__main__":
    with open("eval/prose3_eval.jsonl", "w") as f:
        for r in B.ITEMS:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(len(B.ITEMS), "prose3 items")
