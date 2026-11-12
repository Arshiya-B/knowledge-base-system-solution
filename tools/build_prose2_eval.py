"""Builds eval/prose2_eval.jsonl: second clean read for the prose engine, written AFTER prose tuning.

Run once, record the first-read score, then do not tune against it.
"""
import json, sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import build_custom_eval as B
B.ITEMS.clear()
item = B.item
S5 = B.S5
D = "https://www.dupaco.com"

item("py-001", "What is the longest term I can get on a Dupaco business equipment loan?", None,
     "Loan terms up to seven years.", ["seven years"], [], "current_value", "medium", 1.5, S5, D + "/business/loans/equipment-vehicle-loans", "loan terms up to seven years", "q-eq")
item("py-002", "How much of a down payment do I need for a business vehicle loan?", None,
     "A minimum 20% down payment.", ["20%"], [], "current_value", "medium", 1.5, S5, D + "/business/loans/equipment-vehicle-loans", "A minimum 20% down payment", "q-eqdown")
item("py-003", "What repayment terms does a Dupaco personal loan offer?", None,
     "Terms from 24 to 60 months.", ["24", "60"], [], "current_value", "medium", 1.5, S5, D + "/personal/loans/personal-loans", "repayment terms from 24 to 60 months", "q-pl")
item("py-004", "Does the Dupaco Rewards Visa charge an annual fee?", None,
     "No annual fee.", ["no annual fee"], [], "entity_attribution", "easy", 1.0, S5, D + "/personal/credit-cards", "No annual fee", "q-visa")
item("py-005", "How many reward points do I earn per dollar with the Rewards Visa?", None,
     "1 point for every $1 spent.", ["1 point"], [], "entity_attribution", "easy", 1.0, S5, D + "/personal/credit-cards", "Earn 1 point for every $1 spent", "q-points")
item("py-006", "What number do I call to talk to someone about insurance?", None,
     "800-373-7600, ext. 210.", ["800-373-7600", "210"], ["218"], "current_value", "medium", 1.5, S5, D + "/personal/insurance", "call at 800-373-7600, ext. 210", "q-ins")
item("py-007", "How are payments figured on a Dupaco business line of credit?", None,
     "Monthly, interest-only payments based on your average balance.", ["interest-only"], [], "current_value", "medium", 1.5, S5, D + "/business/credit-lines",
     "interest-only payments based on your average balance", "q-loc")
item("py-008", "How many years of tax returns do I need to apply for a business line of credit?", None,
     "Three years (personal and business).", ["three years"], [], "current_value", "medium", 1.5, S5, D + "/business/credit-lines", "three years of tax returns", "q-loc2")
item("py-009", "Does Dupaco charge employers for its employee financial wellness program?", None,
     "No, the Financial Wellness program is free.", ["free"], [], "entity_attribution", "medium", 1.5, S5, D + "/business/employee-wellness", "our free Financial Wellness program", "q-well")
item("py-010", "What can my business do to avoid card processing fees?", None,
     "Use chip readers, swipe or tap, settle batches daily, process same-day returns before close.", ["daily"], [], "list_completeness", "hard", 2.0, S5,
     D + "/business/cash-management", "Settling your credit card transaction batches daily", "q-fees")
item("py-011", "What rate does Dupaco charge on an aircraft loan for a private jet?", None,
     "Dupaco lists no aircraft loans; contact Dupaco.", [], ["%"], "should_refuse", "medium", 1.5, None, None, None, "q-ref")
item("py-012", "What are the lobby hours for the Dupaco branch in Fargo, North Dakota?", None,
     "Dupaco has no Fargo branch; contact Dupaco.", [], ["9 a.m.", "8:30"], "should_refuse", "medium", 1.5, None, None, None, "q-ref")

if __name__ == "__main__":
    with open("eval/prose2_eval.jsonl", "w") as f:
        for r in B.ITEMS:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(len(B.ITEMS), "prose2 items")
