"""Builds eval/prose4_eval.jsonl: fourth unseen prose batch, written AFTER the URL fixes.

Pages not used in earlier batches. Run once, record the first-read score, then do not tune against it.
"""
import json, sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import build_custom_eval as B
B.ITEMS.clear()
item = B.item
S5 = B.S5
D = "https://www.dupaco.com"
SCH = D + "/scholarships"
SW = D + "/switch-and-earn"
LP = D + "/personal/loans/loan-protection"
MP = D + "/online-and-mobile-banking/mobile-payments"
BS = D + "/business/savings-accounts"
OS = D + "/savings-account/online-savings-account"
CL = D + "/business/loans/construction-loans"

item("pw-001", "How many Dupaco scholarships go to high school seniors headed to a community college or trade school?", None,
     "Ten scholarships of $2,000 each.", ["$2,000"], ["$4,000"], "current_value", "medium", 1.5, S5, SCH, "10 scholarships of $2,000 each", "q-sch1")
item("pw-002", "Over how many years is a Dupaco four-year college scholarship paid out?", None,
     "Four years, in annual increments of $1,000.", ["four years"], [], "current_value", "medium", 1.5, S5, SCH, "annual increments of $1,000 over four years", "q-sch2")
item("pw-003", "What is the most cash back I can earn by moving a loan to Dupaco under the switch and earn offer?", None,
     "Up to $300 cash back.", ["$300"], [], "current_value", "easy", 1.0, S5, SW, "earn up to $300* cash back", "q-sw1")
item("pw-004", "What is the smallest loan from another lender that qualifies for the Dupaco switch and earn offer?", None,
     "Loans of $5,000 or more.", ["$5,000"], [], "current_value", "medium", 1.5, S5, SW, "of $5,000 or more", "q-sw2")
item("pw-005", "How long can my first loan payment be delayed if I move a loan to Dupaco?", None,
     "Up to 45 days.", ["45 days"], [], "current_value", "medium", 1.5, S5, SW, "could be delayed up to 45 days", "q-sw3")
item("pw-006", "How much of my remaining balance can Dupaco loan protection cancel after an accidental death?", None,
     "Up to $1,000.", ["$1,000"], [], "current_value", "medium", 1.5, S5, LP, "may cancel up to $1,000 of your remaining balance", "q-lp1")
item("pw-007", "What extension do I dial to reach Dupaco card services about mobile payments?", None,
     "800-373-7600, ext. 201.", ["201"], [], "current_value", "easy", 1.0, S5, MP, "800-373-7600, ext. 201", "q-mp1")
item("pw-008", "What dividend rate does the Dupaco business Investor's Choice money market pay on a $50,000 balance?", None,
     "0.35% for balances of $25,000 to $99,999.99.", ["0.35%"], ["0.40%", "0.30%"], "tier_disambiguation", "hard", 2.0, S5, BS, "Investor's Choice Money Market (Business) | $25,000 - $99,999.99 | 0.35%", "q-bs1")
item("pw-009", "What APY does the Dupaco online savings account earn if I turn on eStatements?", None,
     "A special 2.25% APY.", ["2.25%"], [], "current_value", "medium", 1.5, S5, OS, "unlock a special **2.25% APY**", "q-os1")
item("pw-010", "About how much does Smart Save typically move into savings each week?", None,
     "Often $10 to $50 a week.", ["$10"], [], "current_value", "medium", 1.5, S5, OS, "often $10-$50 a week", "q-os2")
item("pw-011", "What extension do I call to talk about a Dupaco business construction loan?", None,
     "800-373-7600, ext. 234.", ["234"], [], "current_value", "medium", 1.5, S5, CL, "800-373-7600, ext. 234", "q-cl1")
item("pw-012", "What is the minimum balance for the Dupaco Diamond Platinum savings account?", None,
     "Dupaco lists no Diamond Platinum savings account; contact Dupaco.", [], ["$"], "should_refuse", "medium", 1.5, None, None, None, "q-ref3")

if __name__ == "__main__":
    with open("eval/prose4_eval.jsonl", "w") as f:
        for r in B.ITEMS:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(len(B.ITEMS), "prose4 items")
