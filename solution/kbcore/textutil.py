"""Small, dependency-free text helpers: normalisation, tokens, numbers, dates."""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

_TRANS = str.maketrans({
    "–": "-", "—": "-", "−": "-", " ": " ",
    "’": "'", "‘": "'", "“": '"', "”": '"', "•": " ",
})


def clean(s: str) -> str:
    return (s or "").translate(_TRANS)


# ----------------------------------------------------------------------------- tokens
_TOK = re.compile(r"[a-z0-9]+")

# canonical forms (applied after light stemming)
SYN = {
    "cd": "certificate", "cds": "certificate", "cert": "certificate", "certs": "certificate",
    "car": "auto", "vehicle": "auto", "automobile": "auto", "truck": "auto",
    "refi": "refinance", "refinancing": "refinance", "refinanced": "refinance",
    "mortgages": "mortgage", "creditcard": "card",
    "heloc": "heloc", "hsa": "health", "jetski": "jet",
    "yields": "yield", "wallet": "mobile", "wallets": "mobile",
}

STOP = set("""
a an the of for on in at to is are was were be been am do does did can could would should will
what whats which who whom whose how when where why that this these those there here
i me my we us our you your yours they them their it its
and or but if then than so as by with from about into over under up down out off
tell give show provide get need want know like please any some all each every
have has had having may might must just also very much many more most other another
dupaco credit union cu member members account accounts
offer offers offered available avail currently current currently now today right latest
charge charges pay paying cost costs earn earns earned earning
keep put borrow borrowing expect see take got offering financing financed finance
paid not no deposit range ranges ranging carry carries between only just end beginning start middle around approximately roughly
typical typically usually generally going someone anyone people
january february march april june july august september october november december
""".split())

# words describing the *metric* rather than the product
METRIC = {"rate", "apr", "apy", "dividend", "interest", "yield", "percentage", "annual", "percent", "pct", "rates"}

# words that rarely identify a product row but often appear in questions
SOFT = {"standard", "purchase", "typical", "typically", "general", "generally", "option", "options",
        "special", "specials", "low", "lowest", "high", "highest", "best", "top", "maximum", "minimum",
        "max", "min", "tier", "tiers", "level", "levels", "one", "ones", "thing", "things", "type",
        "types", "kind", "kinds", "whats", "balance", "between", "above", "below", "least", "most",
        "per", "year", "month", "model", "term", "length", "number", "range", "ranges", "look", "see",
        "know", "tell", "link", "page", "learn", "find", "list", "name", "names", "know", "good",
        "new", "used", "old", "get", "got", "gets", "using", "use", "uses", "apply", "applying"}


def stem(w: str) -> str:
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and re.search(r"(ch|sh|x|ss|zz)es$", w):      # branches -> branch, taxes -> tax
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
        return w[:-1]
    return w


STOP |= {stem(w) for w in STOP}


def tokens(text: str) -> list[str]:
    """Lower-cased, stemmed, synonym-folded alphanumeric tokens (numbers kept raw)."""
    out = []
    for w in _TOK.findall(clean(text).lower()):
        w = stem(w)
        out.append(SYN.get(w, w))
    return out


def content_tokens(text: str) -> list[str]:
    """Tokens that can identify a product: no stop words, no pure numbers, no metric words."""
    out = []
    for w in tokens(text):
        if w.isdigit() or w in STOP or w in METRIC or len(w) < 2:
            continue
        out.append(w)
    return out


# ----------------------------------------------------------------------------- numbers
PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
MONEY = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)")


def pct_values(cell: str) -> list[float]:
    """All percentages in a cell; a trailing footnote digit ('3.90%1') is ignored."""
    return [float(x) for x in PCT.findall(clean(cell))]


def fmt_pct(x: float) -> str:
    s = f"{x:.3f}".rstrip("0")
    if s.endswith("."):
        s += "0"
    # keep at least two decimals ("5.3" -> "5.30")
    head, _, tail = s.partition(".")
    tail = tail.ljust(2, "0")
    return f"{head}.{tail}%"


def money_to_float(s: str) -> float:
    return float(s.replace(",", ""))


# ----------------------------------------------------------------------------- dates
_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}
_MONTHS.update({k[:3]: v for k, v in list(_MONTHS.items())})
_MONTHS["sept"] = 9

NUM_DATE = re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})(?!\d)")
WORD_DATE = re.compile(
    r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|"
    r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", re.I)


def _mk(y: int, m: int, d: int) -> Optional[date]:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def find_dates(text: str) -> list[date]:
    out = []
    for m in NUM_DATE.finditer(text):
        mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y = 2000 + y if y < 100 else y
        dt = _mk(y, mo, d)
        if dt:
            out.append(dt)
    for m in WORD_DATE.finditer(text):
        mo = _MONTHS.get(m.group(1).lower().rstrip("."))
        if mo:
            dt = _mk(int(m.group(3)), mo, int(m.group(2)))
            if dt:
                out.append(dt)
    return out


def parse_iso(s: str) -> Optional[date]:
    try:
        return date.fromisoformat((s or "")[:10])
    except ValueError:
        return None


def pretty_date(d: date) -> str:
    return d.strftime("%B ") + str(d.day) + d.strftime(", %Y")
