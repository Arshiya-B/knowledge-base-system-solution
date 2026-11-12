"""Builds eval/prose_eval.jsonl: clean read for the prose engine (grants, contacts, programs).

Written AFTER the prose engine existed, before any prose tuning against these items.
Run once, record the first-read score, then do not tune against it.
"""
import json, sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import build_custom_eval as B
B.ITEMS.clear()
item = B.item
S1, S2, S3, S4, S5 = B.S1, B.S2, B.S3, B.S4, B.S5
D = "https://www.dupaco.com"

item("px-001", "What is the most the Dupaco Foundation hardship grant will pay?", None,
     "Up to $3,500 per one-time gift.", ["3,500"], ["$2,000"], "current_value", "medium", 1.5, S5, D + "/hardship-grant", "up to $3,500", "p-hard")
item("px-002", "As of 2026-05-25, what was the maximum Dupaco hardship grant?", "2026-05-25",
     "May 19 snapshot: up to $2,000.", ["2,000"], ["3,500"], "temporal_as_of", "hard", 2.0, S2, D + "/hardship-grant", "up to $2,000", "p-hard-time")
item("px-003", "Who administers the Dupaco Foundation hardship fund?", None,
     "Emergency Assistance Foundation.", ["Emergency Assistance Foundation"], [], "entity_attribution", "medium", 1.5, S5, D + "/hardship-grant",
     "administered by Emergency Assistance Foundation", "p-eaf")
item("px-004", "How much is the First-Time Homebuyer Grant?", None,
     "A one-time $1,000 contribution toward the down payment.", ["1,000"], [], "current_value", "easy", 1.0, S5, D + "/first-time-homebuyer-grant",
     "one-time financial contribution of $1,000", "p-fthb")
item("px-005", "What is the maximum amount of the Dupaco Foundation nonprofit grant?", None,
     "Up to $20,000, one time.", ["20,000"], [], "current_value", "easy", 1.0, S5, D + "/non-profit-grant", "up to $20,000", "p-np")
item("px-006", "When is the application period for the Gift of Innovation grant?", None,
     "Oct. 1 to Nov. 12, 2026.", ["Nov. 12"], ["Nov. 14"], "stale_trap", "hard", 2.0, S5, D + "/gift-of-innovation-grant",
     "Application period: Oct. 1–Nov. 12, 2026", "p-goi")
item("px-007", "As of 2026-06-01, what was the Gift of Innovation application window?", "2026-06-01",
     "May 19 snapshot: Oct. 1 to Nov. 14, 2025.", ["Nov. 14"], ["Nov. 12"], "temporal_as_of", "hard", 2.0, S2, D + "/gift-of-innovation-grant",
     "Application period: Oct. 1–Nov. 14, 2025", "p-goi-time")
item("px-008", "When can I apply for the Key City Creative Center maker mentorship program?", None,
     "Oct. 14 to Nov. 11, 2026.", ["Nov. 11"], [], "current_value", "medium", 1.5, S5, D + "/kccc-membership-grant",
     "Application period: Oct. 14–Nov. 11, 2026", "p-kccc")
item("px-009", "Who do I contact with questions about applying for a Dupaco student loan?", None,
     "CU Student Choice at 844-830-3258.", ["CU Student Choice", "844-830-3258"], [], "entity_attribution", "medium", 1.5, S5, D + "/personal/loans/student-loans",
     "you can contact CU Student Choice directly at 844-830-3258", "p-stu")
item("px-010", "What phone number do I call about opening an IRA?", None,
     "800-373-7600, ext. 218.", ["800-373-7600", "218"], [], "current_value", "medium", 1.5, S5, D + "/personal/retirement",
     "call at 800-373-7600, ext. 218", "p-ira")
item("px-011", "What is the borrowing limit on a Dupaco small business loan?", None,
     "Less than $50,000.", ["50,000"], [], "current_value", "medium", 1.5, S5, D + "/business/loans/small-business-loans",
     "borrow less than $50,000", "p-sbl")
item("px-012", "How long can a Dupaco recreational loan term be?", None,
     "Flexible terms up to 84 months.", ["84 months"], [], "current_value", "easy", 1.0, S5, D + "/personal/loans/recreational-loans",
     "flexible terms up to 84 months", "p-rec")
item("px-013", "Who won the grand prize in the Sprint to Savings Challenge?", None,
     "Lisa Klees.", ["Lisa Klees"], [], "entity_attribution", "easy", 1.0, S5, D + "/21-day-sprint-to-savings-challenge",
     "Grand Prize Winner: Lisa Klees", "p-sprint")
item("px-014", "How many promotions did Dupaco celebrate in 2025?", None,
     "86 promotions.", ["86"], [], "current_value", "medium", 1.5, S5, D + "/careers", "86 promotions", "p-careers")
item("px-015", "How can I get my two-step verification codes by text instead of email?", None,
     "Add your mobile number in Shine Mobile or Shine Online to get codes via text.", ["mobile number", "text"], [], "entity_attribution", "medium", 1.5, S5,
     D + "/manage-account-alerts", "add your mobile number to receive codes via text instead", "p-2fa")
item("px-016", "Who won the Week 4 drawing in the Sprint to Savings Challenge?", None,
     "The challenge had three weekly drawings; no Week 4 is listed.", [], ["Lisa Klees", "Mika McCool"], "should_refuse", "hard", 2.0, None, None, None, "p-ref")
item("px-017", "What are the lobby hours at the Dupaco branch in Phoenix, Arizona?", None,
     "Dupaco has no Phoenix branch; contact Dupaco.", [], ["9 a.m.", "8:30"], "should_refuse", "medium", 1.5, None, None, None, "p-ref")

if __name__ == "__main__":
    with open("eval/prose_eval.jsonl", "w") as f:
        for r in B.ITEMS:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(len(B.ITEMS), "prose items")
