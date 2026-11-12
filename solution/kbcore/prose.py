"""Passage search for facts that live in prose rather than in rate tables.

Pipeline: page markdown -> sentences with their heading -> inverted index per snapshot ->
BM25-style scoring -> validation by question intent (a "phone" question needs a phone number) ->
conflict rule (when passages disagree, the most recently dated one wins) -> short quoted answer.

Standard library only; no model of any kind.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from .textutil import STOP, clean, parse_iso, tokens

_MONTHS = {m: i + 1 for i, m in enumerate(
    "january february march april may june july august september october november december".split())}
WORD_DATE = re.compile(r"\b(" + "|".join(m.capitalize() for m in _MONTHS) + r")\.? (\d{1,2}), (20\d\d)\b")
ISO_DATE = re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)\b")

ADDR_RE = re.compile(r"\b\d{1,6} [A-Z0-9][\w.\- ]{2,40}?,\s*[A-Z][\w. ]+,\s*[A-Z]{2},?\s*\d{5}\b")
PO_RE = re.compile(r"\bP\.?O\.? Box \d+[^.]{0,60}\d{5}")
PHONE_RE = re.compile(r"\b(?:1[-. ])?\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}\b")
TIME_RE = re.compile(r"\b\d{1,2}(?::\d\d)?\s?(?:a\.m\.|p\.m\.|am|pm|AM|PM|noon)\b|\bnoon\b|\bclosed\b", re.I)
NUM_RE = re.compile(r"\b\d[\d,]*\b")
TIME_DIGITS = re.compile(r"\b\d{1,2}(?::\d\d)?\s?(?:a\.m\.|p\.m\.|am|pm|AM|PM)|\bnoon\b", re.I)
URL_RE = re.compile(r"https?://[^\s)\]>\"']+")

_ABBR = ["ext.", "a.m.", "p.m.", "Mon.", "Tue.", "Wed.", "Thu.", "Fri.", "Sat.", "Sun.", "St.", "Ave.", "Ln.", "Dr.",
         "Rd.", "Blvd.", "Inc.", "No.", "U.S.", "Dec.", "Jan.", "Feb.", "Aug.", "Sept.", "Oct.", "Nov.",
         "Mr.", "Mrs.", "Ms.", "Dr.", "Co.", "Ct.", "Hwy.", "N.", "S.", "E.", "W.", "Ste.", "vs.", "etc."]


# --------------------------------------------------------------------------- cleaning
_IMG = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]*)[^)]*\)")
_TAGS = re.compile(r"<[^>]+>")


def page_date(md: str) -> Optional[date]:
    head = md[:900]
    for m in WORD_DATE.finditer(head):
        try:
            return date(int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2)))
        except ValueError:
            continue
    m = ISO_DATE.search(head)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def page_links(md: str) -> list[tuple[str, str]]:
    out = []
    for m in _LINK.finditer(_IMG.sub("", md)):
        anchor, url = m.group(1).strip(), m.group(2).strip()
        if anchor and url.startswith("http"):
            out.append((clean(anchor), url))
    return out


def _protect(s: str) -> str:
    for i, a in enumerate(_ABBR):
        s = s.replace(a, a.replace(".", "․"))
    return s


def _restore(s: str) -> str:
    return s.replace("․", ".")


def split_sentences(block: str) -> list[str]:
    block = _protect(block)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“(\[$])", block)
    return [_restore(p).strip() for p in parts if len(p.strip()) > 3]


@dataclass
class Passage:
    url: str
    ptype: str
    auth: int
    when: Optional[date]          # publication date of the page, if it has one
    taken_on: date
    heading: str
    text: str
    tf: Counter = field(default_factory=Counter)
    n: int = 0
    ttl: frozenset = frozenset()       # words of the page title and slug: what the page is about


_DRIVE = re.compile(r"drive[\s\-]*(?:up|thru|through)", re.I)


_APPLY = re.compile(r"^appl(?:y|ies|ied|ying|ication|ications|icant|icants)$")
_KEEP = frozenset(("borrow",))          # a stopword for the rate engine, but it names what a limit applies to
_JOIN = re.compile(r"\b(?:become|becoming|becomes)\s+(?:a\s+|an\s+)?(?:new\s+)?(?:dupaco\s+)?member(?:-owner)?s?\b", re.I)
_CHANGE = frozenset(("update", "updates", "updated", "updating", "edit", "edits", "edited", "editing", "modify", "modifies", "modified", "modifying"))


def _tok(text: str) -> list[str]:
    text = _JOIN.sub("join", _DRIVE.sub("driveup", text))
    # long words are cut to 7 letters so "recognition" and "recognized" meet ("eligibility" stays apart)
    out = []
    for t in tokens(text):
        if (t in STOP and t not in _KEEP) or not (len(t) > 1 or t.isdigit()):
            continue
        if _APPLY.match(t) or t in ("applyi", "applic", "applica"):
            t = "apply"
        elif t in _CHANGE:
            t = "change"
        out.append(t[:7] if len(t) >= 9 else t)
    return out


def _clean_line(raw: str) -> str:
    line = _TAGS.sub(" ", _IMG.sub(" ", raw.strip()))
    line = _LINK.sub(r"\1", line)
    line = re.sub(r"[*_`]+|\\+", "", line)
    line = re.sub(r"^\s*[-+\u2022]\s+", "", line)
    if line.startswith("|"):                      # table row on a prose page (e.g. a schedule)
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            return ""
        line = ", ".join(c for c in cells if c)
    return clean(re.sub(r"\s+", " ", line)).strip()


def _mk(url, ptype, auth, when, taken_on, heading, text) -> Passage:
    p = Passage(url, ptype, auth, when, taken_on, heading, text)
    tf = Counter(_tok(text))
    for t in _tok(heading):
        tf[t] += 0.5
    slug = url.split(".com")[-1].split("?")[0].strip("/")
    if slug and not re.match(r"(?:learn|newsroom|business/resources|dupacodaily|\d{4}/)", slug):
        for t in _tok(re.sub(r"[-_/]+", " ", slug)):          # a product page's own slug names its topic
            if t not in tf:
                tf[t] = 0.3
    p.tf, p.n = tf, max(1, sum(tf.values()))
    return p


SHORT = 100
CTA_RE = re.compile(r"(?:for (?:more|additional|complete|further) (?:information|details|info)|to learn more|learn more|visit|click|to apply|to get started|get started|stop by|call us|contact us)\b", re.I)
REALTIME_RE = re.compile(r"\b(?:weather|forecast|temperature|bitcoin|ethereum|crypto(?:currency)? price|stock price|share price|sports? scores?|traffic)\b", re.I)
BANKING_RE = re.compile(r"\b(?:loans?|accounts?|rates?|apr|apy|cards?|branch(?:es)?|members?|membership|savings?|checking|mortgages?|deposits?|credit|debit|dividends?|certificates?|ira|atm|bank|banking|fees?|payments?|insurance|grants?|scholarships?|budget\w*|money|financ\w+|interest|refinanc\w+|fraud|scams?|identity|retire\w*|invest\w*)\b", re.I)
MIN_RE = re.compile(r"\bminimum|\bat least\b|\bstarts? (?:at|from)\b|\bas (?:low|little) as\b|\bno less than\b|\bbegins? at\b", re.I)
LIMIT_RE = re.compile(r"\bup to\b|\bmaximum\b|\bas long as\b|\bno more than\b|\bat most\b|\bless than\b", re.I)


def page_passages(md: str, url: str, ptype: str, auth: int, taken_on: date, title: str = "") -> list[Passage]:
    when = page_date(md)
    out: list[Passage] = []
    heading = clean(title or "")
    run: list[str] = []
    run_heading = heading

    def flush():
        nonlocal run
        if len(run) >= 3:
            step, size = 3, 6
            for i in range(0, len(run), step):
                chunk = run[i:i + size]
                if i and len(chunk) < 3:
                    break
                out.append(_mk(url, ptype, auth, when, taken_on, run_heading, " ".join(chunk)[:600]))
        for ln in run:
            # a run of >=3 short lines is kept together (schedules, address cards); a dated or priced line also stands alone
            if len(run) < 3 or (re.match(r"[A-Z][\w ]{2,30}:\s", ln) and (WORD_DATE.search(ln) or re.search(r"\$\d", ln))):
                out.append(_mk(url, ptype, auth, when, taken_on, run_heading, ln))
        run = []

    pending_q = ""
    for raw in md.split("\n"):
        line = raw.strip()
        if not line or set(line) <= set("*-_| "):
            continue
        if line.startswith("#"):
            if pending_q:
                out.append(_mk(url, ptype, auth, when, taken_on, heading, pending_q))
                pending_q = ""
            flush()
            heading = clean(re.sub(r"^#+\s*", "", _LINK.sub(r"\1", line)))
            continue
        line = _clean_line(line)
        if len(line) < 4:
            continue
        if pending_q:                       # an FAQ question and its answer belong together
            flush()
            out.append(_mk(url, ptype, auth, when, taken_on, heading, (pending_q + " " + line)[:700]))
            pending_q = ""
            continue
        elif line.endswith("?") and len(line) <= 200:
            flush()
            pending_q = line
            continue
        if len(line) <= SHORT:
            if not run:
                run_heading = heading
            run.append(line)
            continue
        flush()
        for sent in split_sentences(line):
            out.append(_mk(url, ptype, auth, when, taken_on, heading, sent[:700]))
    if pending_q:
        out.append(_mk(url, ptype, auth, when, taken_on, heading, pending_q))
    flush()
    slug = url.split(".com")[-1].split("?")[0]
    ttl = frozenset(_tok(clean(title or "")) + _tok(re.sub(r"[-_/]+", " ", slug)))
    for p_ in out:
        p_.ttl = ttl
    # a form's country dropdown ("Uganda +256 Ukraine +380 ...") is page furniture, not content
    out = [q for q in out if not (re.search(r"[\U0001F1E6-\U0001F1FF]{2}", q.text) or len(re.findall(r"\+\d{1,3}\b", q.text)) >= 3)]
    return out


# --------------------------------------------------------------------------- index
class PassageIndex:
    def __init__(self):
        self.snaps: list[dict] = []

    def add_snapshot(self, passages: list[Passage], links: list[tuple[str, str, str, int]]) -> None:
        post: dict[str, list[int]] = defaultdict(list)
        df: Counter = Counter()
        total = 0
        for i, p in enumerate(passages):
            total += p.n
            for t in p.tf:
                post[t].append(i)
                df[t] += 1
        pagetok: dict = defaultdict(set)
        bypage: dict = defaultdict(list)
        for p_ in passages:
            pagetok[p_.url].update(p_.tf)
            bypage[p_.url].append(p_)
        self.snaps.append(dict(pagetok=pagetok, bypage=bypage, passages=passages, post=post, df=df, avg=total / max(1, len(passages)),
                               links=links))

    # BM25 ---------------------------------------------------------------------
    def search(self, si: int, qtoks: list[str], k: int = 12) -> list[tuple[float, Passage]]:
        S = self.snaps[si]
        N = len(S["passages"])
        cand: Counter = Counter()
        for t in set(qtoks):
            df = S["df"].get(t, 0)
            if not df:
                continue
            idf = math.log(1 + (N - df + 0.5) / (df + 0.5))
            for i in S["post"][t]:
                p = S["passages"][i]
                tf = p.tf[t]
                cand[i] += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * p.n / S["avg"]))
        # reward passages that hold the question's words next to each other
        out = []
        for i, sc in cand.most_common(400):
            p = S["passages"][i]
            sc *= 1 + 0.06 * (p.auth - 1)
            out.append((sc, p))
        out.sort(key=lambda x: -x[0])
        return out[:k]

    def idf(self, si: int, t: str) -> float:
        S = self.snaps[si]
        df = S["df"].get(t, 0)
        N = len(S["passages"])
        return math.log(1 + (N - df + 0.5) / (df + 0.5)) if df else math.log(1 + N)


# --------------------------------------------------------------------------- intents
def intent_of(q: str) -> str:
    t = q.lower()
    if re.search(r"\brouting\b|\baba\b", t):
        return "routing"
    if re.search(r"\b(link|url|web ?address|webpage|web page|website for|where (?:can|do) i (?:find|see|go))\b", t) or \
            re.search(r"\b(?:how|where) (?:do|can|would) i (?:join|apply|enroll|sign up|become a member|log ?in)\b", t):
        return "url"
    if re.search(r"\baddress\b|\bwhere is\b|\bwhere'?s\b|\blocated\b|\bstreet\b", t) and \
            not re.search(r"email|e-mail|ip address", t):
        return "address"
    if re.search(r"\bextension\b|\bwhat ext\b|\bdial\b", t):
        return "contact"
    if re.search(r"\bphone\b|\bcall\b|\btelephone\b|\bnumber (?:for|to)\b|\bcontact (?:number|info)", t) and \
            not re.search(r"\b(?:update|change|edit|correct|modify)\b", t):
        return "phone"
    if re.search(r"^\s*when\b|\bwhat (?:date|year)\b", t):
        return "when"
    if re.search(r"\bstill (?:open|operating|available)\b|\b(?:is|are) .{0,40}\b(?:closed|closing)\b", t):
        return "status"
    if re.search(r"\bhours?\b|\bopen (?:at|until|on)\b|\bcloses? at\b|\bclosing time", t):
        return "hours"
    if re.search(r"\bwho (?:do|should|can|would|could) i (?:contact|call|talk to|reach|ask)\b|\bwho to (?:contact|call)\b", t):
        return "contact"
    if re.search(r"\bhow long (?:can|could|is|are|does|do|will|would)\b|\bhow many (?:months|years|days|weeks|hours)\b|"
                 r"\b(?:longest|shortest|maximum|minimum)\s+(?:\w+\s+){0,2}(?:term|length|period)\b", t) and \
            not re.search(r"\bhow long ago\b", t):
        return "duration"
    if re.search(r"\bhow much\b|\bmaximum\b|\bminimum\b|\bmost (?:the|a|an)\b|\blimit\b|\b(?:smallest|lowest|least|fewest|largest|biggest|greatest)\b", t):
        return "amount_pct" if re.search(r"percent|%|\brate\b|\bapr\b|\bapy\b|interest|dividend|yield|how much of|down payment", t) else "amount"
    if re.search(r"\bhow many\b|\bnumber of\b", t):
        return "count"
    if re.search(r"\bwhen\b|\bhow long ago\b", t):
        return "when"
    return "general"


_NUMWORD = "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|sixty|ninety"
_VALID = {
    "address": lambda s: bool(ADDR_RE.search(s) or PO_RE.search(s)),
    "phone": lambda s: bool(PHONE_RE.search(s)),
    "hours": lambda s: bool(TIME_DIGITS.search(s)),
    "count": lambda s: bool(NUM_RE.search(s)),
    "amount": lambda s: bool(re.search(r"\$\s?\d|\b(?:million|billion)\b", s)),
    "amount_pct": lambda s: bool(re.search(r"\$\s?\d|\d\s?%|\b(?:million|billion)\b", s)),
    "duration": lambda s: bool(re.search(r"\b(?:\d+|" + _NUMWORD + r")\s*(?:-\s*)?(?:month|year|day|week|hour|minute)s?\b", s, re.I)),
    "contact": lambda s: bool(PHONE_RE.search(s) or re.search(r"[\w.]+@[\w.]+\.\w+", s)),
    "when": lambda s: bool(WORD_DATE.search(s) or re.search(r"\b(19|20)\d\d\b", s)),
}


def _numbers(s: str) -> frozenset:
    return frozenset(x.replace(",", "") for x in NUM_RE.findall(s))


@dataclass
class ProseResult:
    text: str
    urls: list[tuple[str, str]]       # (url, quote)
    confident: bool = True
    note: Optional[str] = None


QWORDS = {"figured", "figure", "calculated", "calculate", "determined", "maximum", "minimum", "limit", "most", "longest", "largest", "highest", "long", "many", "much", "does", "did", "have", "has", "offer", "offers", "provide", "tell", "know",
          "please", "need", "want", "like", "use", "using", "get", "give", "show", "find", "link", "url",
          "website", "page", "address", "phone", "number", "hours", "open", "close", "closing", "still",
          "today", "now", "current", "currently", "any", "also", "about", "there", "can"}


QWORDS |= {"stay", "stays", "remain", "remains", "make", "take", "smallest", "lowest", "least", "fewest", "shortest", "biggest", "greatest", "same", "all", "every", "each", "different", "keep", "kept", "online", "hour", "hours", "still",
           "actually", "specific", "exactly", "typical", "usual", "general", "generally"}
QWORDS |= {t for w in list(QWORDS) for t in _tok(w)}


def proper_tokens(q: str) -> list[str]:
    """Capitalised words that are not at the start of a sentence: names the answer has to mention."""
    out = []
    for m in re.finditer(r"(?<![.?!]\s)(?<!^)\b[A-Z][\w$\-]*", q.strip()):
        if m.start() == 0:
            continue
        out += _tok(m.group(0))
    return [t for t in out if t not in QWORDS]


_ISO_Q = re.compile(r"\b(?:19|20)\d\d-\d\d-\d\d\b|\bas of\b", re.I)


def query_tokens(q: str) -> list[str]:
    q = _ISO_Q.sub(" ", q)
    toks = [t for t in _tok(q) if t not in QWORDS]
    return toks or _tok(q)


class ProseEngine:
    def __init__(self):
        self.index = PassageIndex()

    # ------------------------------------------------------------ public
    def answer(self, si: int, question: str, as_of_date: Optional[date] = None) -> Optional[ProseResult]:
        intent = intent_of(question)
        if intent == "routing":
            r = self._routing(si)
            if r:
                return r
        if intent == "url":
            r = self._url(si, question)
            if r:
                return r
        qt = query_tokens(question)
        if not qt:
            return None
        if REALTIME_RE.search(question):
            return None                     # a static site snapshot cannot say what the weather or a market price is right now
        hits = self.index.search(si, qt, k=300 if intent in ("count", "contact") else 60)
        if not hits:
            return None
        valid = _VALID.get(intent)
        S = self.index.snaps[si]
        if valid and intent not in ("hours", "address", "phone", "status", "count"):
            # facts that name no subject themselves: take them from the pages that best match the question
            agg: dict = defaultdict(float)
            for sc_, p_ in hits:
                agg[p_.url] += sc_
            # big hub pages (many passages) match everything; favour the focused page that names the subject
            ranked = sorted(agg, key=lambda u: -agg[u] / math.sqrt(len(S["bypage"].get(u, [])) or 1))
            seen_pg, extra = ranked[:3], []
            have_ids = {id(p_) for _, p_ in hits}
            top = hits[0][0]
            for pu in seen_pg:
                for p_ in S["bypage"].get(pu, []):
                    if id(p_) not in have_ids and valid(p_.text):
                        own = sum(self.index.idf(si, t) for t in set(qt) if t in p_.tf)
                        extra.append((0.4 * top + own, p_))
            hits = hits + extra
        # weight of the question's words that a passage actually contains
        wsum = sum(self.index.idf(si, t) for t in set(qt)) or 1.0

        paged = intent not in ("general", "hours", "address", "phone", "status")
        nontopic_ok = True

        def cover(p: Passage) -> float:
            # a fact line ("Application period: ...") sits under the page that names its subject
            have = (p.tf.keys() | S["pagetok"].get(p.url, set())) if paged else p.tf
            return sum(self.index.idf(si, t) for t in set(qt) if t in have) / wsum

        def counted(p: Passage) -> bool:
            # "how many branches": the number has to sit next to the thing being counted
            nouns = [t for t in qt if not t.isdigit()]
            low = p.text.lower()
            return any(re.search(r"(?<![\d,$])\b\d{1,3}(?:,\d{3})?\+?\s+(?:[a-z\-]+\s+){0,3}" + re.escape(n[:5]), low) for n in nouns)

        proper = set(proper_tokens(question))
        names_co = bool(re.search(r"\bdupaco\b", question, re.I))
        elig_q = bool(re.search(r"\beligib|\bqualif|\bwho can (?:join|become|open|apply)\b", question, re.I))
        how_q = bool(re.match(r"\s*how (?:can|do|should|would|could) (?:i|we|you)\b", question, re.I))
        define_q = bool(re.match(r"\s*(?:what|who|which|tell|describe|explain)\b", question, re.I))
        past_q = bool(re.search(r"\b(was|were|did|had|last year|previous|used to)\b", question, re.I))
        min_q = bool(re.search(r"\b(?:minimum|smallest|lowest|least|fewest|at least)\b", question, re.I))
        limit_q = bool(re.search(r"\b(maximum|most|limit|longest|largest|highest|how long can|up to|can be)\b", question, re.I))
        need_nums = re.findall(r"(?<![\w$.,/-])\d{1,2}(?![\w%,.\-/]|\d)", _ISO_Q.sub(" ", question))
        scored = []
        for sc, p in hits:
            if valid and not valid(p.text):
                continue
            if proper:
                # a card (address, phone, hours) must name the place itself; other facts may name it elsewhere on the page
                where = p.tf if (intent in ("address", "phone", "hours") and not re.search(r"\bext(?:ension)?\b", question.lower())) else (p.tf.keys() | S["pagetok"].get(p.url, set()))
                if not all(t in where for t in proper):
                    continue
            if need_nums and not all(n in p.tf for n in need_nums):
                continue
            if paged and nontopic_ok is not None:
                nt = set(qt) - p.ttl
                if nt and not (nt & set(_tok(p.text))):
                    continue        # a date or amount that shares nothing with what was asked beyond the page's own topic
            if intent == "count" and not counted(p):
                continue
            boost = 1.5 if (limit_q and LIMIT_RE.search(p.text)) else 1.0
            if min_q and MIN_RE.search(p.text):
                boost *= 1.5                        # a floor is stated as "minimum", "starts at", "at least"
            if intent == "general":
                if p.n < 5:
                    boost *= 0.5                    # a bare heading or label carries no fact
                if CTA_RE.match(p.text):
                    boost *= 0.5 if define_q else 0.7   # "for more information, visit..." points elsewhere instead of answering
                tm_ = sum(self.index.idf(si, t) for t in set(qt) if t in p.ttl) / wsum
                boost *= 1.0 + 0.8 * tm_            # the page whose title names the subject owns it
                if p.heading:
                    ht = set(_tok(p.heading)) - p.ttl       # the page's own title is true of every passage on it
                    hm = sum(self.index.idf(si, t) for t in set(qt) if t in ht) / wsum
                    if hm >= 0.5:
                        boost *= 1.0 + hm       # the section is titled with most of what was asked ("HELOC", "Home Equity Loan")
                if names_co and p.ptype in ("blog", "news", "resource") and "dupaco" not in p.text.lower():
                    boost *= 0.6                    # generic advice in a post does not state what Dupaco itself does
            if intent in ("amount", "amount_pct", "duration") and not re.search(r"[.!?][\"')\]\u00b9\u00b2\u00b3\d]{0,3}\s*$", p.text):
                boost *= 0.6                            # calculator labels and table scraps are not statements of a limit
            if paged:
                boost *= 1.0 + 0.15 * (p.auth - 1)      # product and landing pages outrank news for a current fact
            if intent == "when" and not past_q:
                yrs = [int(y) for y in re.findall(r"\b(20\d\d)\b", p.text)]
                if yrs and max(yrs) < p.taken_on.year:
                    boost *= 0.5                        # "when can I apply" is not answered by a deadline from years ago
            if paged:
                boost *= min(1.0, (60.0 / max(1, len(S["bypage"].get(p.url, [])))) ** 0.25)
                # the page whose title/slug names the subject owns the fact; news and blog posts only mention it
                tm = sum(self.index.idf(si, t) for t in set(qt) if t in p.ttl) / wsum
                boost *= 1.0 + 1.5 * tm
                if p.ptype in ("news", "blog", "resource"):
                    boost *= 0.8
            scored.append((sc * (0.5 + cover(p)) * boost, cover(p), p))
        if not scored:
            return None
        if intent == "status":
            scored = [(sc * (1.6 if WORD_DATE.search(p.text) else 1.0), cv, p) for sc, cv, p in scored]
        if min_q and intent in ("amount", "amount_pct") and any(MIN_RE.search(x[2].text) for x in scored):
            scored = [x for x in scored if MIN_RE.search(x[2].text)]
        if limit_q and any(LIMIT_RE.search(x[2].text) for x in scored):
            scored = [x for x in scored if LIMIT_RE.search(x[2].text)]      # a maximum is stated as "up to" / "maximum"
        scored.sort(key=lambda x: -x[0])
        if define_q and intent == "general":
            # a definition's figures (an award amount, a limit) are often in a sentence that never repeats the name
            pg = S["bypage"].get(scored[0][2].url, [])
            at = next((i for i, q_ in enumerate(pg) if q_ is scored[0][2]), 0)
            top_sc, top_cv = scored[0][0], scored[0][1]
            known = {id(x[2]): k for k, x in enumerate(scored)}
            for i, p_ in enumerate(pg):
                if p_.n >= 5 and re.search(r"\$\s?\d", p_.text):
                    floor = top_sc * (0.31 + 0.09 / (1 + 0.25 * abs(i - at)))       # nearer the lead = more on topic
                    if id(p_) in known:
                        k = known[id(p_)]
                        scored[k] = (max(scored[k][0], floor), scored[k][1], p_)
                    else:
                        scored.append((floor, top_cv, p_))
            scored.sort(key=lambda x: -x[0])
        self.last_scored = scored[:6]
        best, bcov, bp = scored[0]
        if intent == "general" and not names_co and bp.ptype in ("blog", "news", "resource") and \
                (len(set(qt)) <= 2 or not BANKING_RE.search(question)):
            return None                     # one stray word matching a blog post ("joke") is not an answer about Dupaco
        topic_page = False
        if bcov < 0.6 and intent == "general":
            # a product page titled for the subject answers a loosely worded question even when its sentences share few words with it
            def named(p_: Passage) -> bool:
                hit = set(qt) & p_.ttl
                return len(hit) >= 2 and sum(self.index.idf(si, t) for t in hit) / wsum >= 0.2
            tp = [x for x in scored if x[2].ptype in ("product", "landing") and x[1] >= 0.35 and named(x[2])]
            if tp:
                tp.sort(key=lambda x: -x[0])
                scored = [tp[0]] + [x for x in scored if x is not tp[0]]
                best, bcov, bp = scored[0]
                topic_page = True
        if bcov < 0.6 and not topic_page:
            return None
        # a count is restated on many dated pages (boilerplate): compare them all, newest wins
        frac = 0.5 if intent == "count" else 0.88
        pool = [x for x in scored if x[0] >= best * frac and x[1] >= bcov - 0.15]
        note = None
        if intent == "hours":
            # schedules differ by branch: show the best one and a different one, and say so
            chosen = [bp]
            sig = _numbers(bp.text)
            for sc, cv, p in scored[1:]:
                if p.url != bp.url and _numbers(p.text) != sig and sc >= best * 0.7 and cv >= bcov - 0.2:
                    chosen.append(p)
                    break
            text = " ".join(p.text[:260] for p in chosen) + " Hours vary by branch, so tell me which branch you mean for exact hours."
            return ProseResult(re.sub(r"\s+", " ", text), [(p.url, p.text[:200]) for p in chosen], True,
                               "More than one hours schedule is published." if len(chosen) > 1 else None)
        # conflicting values: the most recently dated source wins
        top_auth = max(x[2].auth for x in pool)
        pool = [x for x in pool if x[2].auth == top_auth]      # a product page beats a news article that repeats the fact
        def _sig(p):
            return _numbers(p.text) or frozenset([p.text[:40]])
        sigs = {_sig(p) for _, _, p in pool}
        by_url: dict = defaultdict(set)
        for _, _, p in pool:
            by_url[p.url].add(_sig(p))
        multi = len({frozenset(v) for v in by_url.values()}) > 1      # pages that state different things
        yr_groups: dict = defaultdict(list)
        for x in pool:
            ys = frozenset(re.findall(r"\b20\d\d\b", x[2].text))
            if ys and x[0] >= best * 0.9:
                yr_groups[ys].append(x)
        periods = (len(sigs) > 1 and len(yr_groups) > 1
                   and all(len({_sig(p) for _, _, p in g}) == 1 for g in yr_groups.values()))
        if periods:
            # "294 in 2023" and "256 in 2024" describe different periods, so they do not contradict each other
            chosen = [max(g, key=lambda x: (x[2].when or x[2].taken_on, x[0]))[2] for g in yr_groups.values()]
            chosen.sort(key=lambda p: min(re.findall(r"\b20\d\d\b", p.text)))
        elif multi:
            pool.sort(key=lambda x: (x[2].when is not None, x[2].when or x[2].taken_on, x[0]), reverse=True)
            top = pool[0][2]
            if any(_numbers(p.text) != _numbers(top.text) for _, _, p in pool):
                note = "Sources disagree; the most recently dated page was used."
            chosen = [top]
        else:
            chosen = [pool[0][2]]
        anchor = chosen[0]
        # other strong sentences from the same page complete a definition or a list
        if intent in ("general", "when", "count") and not multi and len(chosen) == 1:
            mates = [(sc, p) for sc, cv, p in scored[1:] if p.url == chosen[0].url and p.text != chosen[0].text
                     and sc >= best * 0.3 and (not valid or valid(p.text))]
            if define_q:
                mates.sort(key=lambda x: (not re.search(r"\$\s?\d|\d\s?%", x[1].text), -x[0]))
            else:
                mates.sort(key=lambda x: -x[0])
            mates = [m for m in mates if not (CTA_RE.match(m[1].text) or m[1].text.rstrip().endswith(">"))]
            chosen += [p for _, p in mates[:3 if define_q else 2]]
            order = {id(p): i for i, p in enumerate(S["passages"])}
            chosen.sort(key=lambda p: order.get(id(p), 0))
        if how_q and intent == "general" and not multi:
            pg = S["bypage"].get(anchor.url, [])
            at = next((i for i, q_ in enumerate(pg) if q_ is anchor), None)
            if at is not None:
                chosen = [anchor] + [q_ for q_ in pg[at + 1:at + 3] if q_.n >= 5 and not CTA_RE.match(q_.text)]
        if elig_q and intent == "general":
            sec = [p for p in S["bypage"].get(chosen[0].url, []) if re.search(r"eligib|qualif|requirement", p.heading, re.I) and p.n >= 5]
            if sec:
                chosen = sec[:4]
        text = " ".join(p.text for p in chosen)
        if re.search(r"charter area", text, re.I) and not re.search(r"\b(?:Iowa|Illinois|Wisconsin)\b", text):
            area = Counter(p.text for p in S["passages"] if re.search(r"serves (?:residents|members) in \d+ counties throughout", p.text))
            if area:
                best_area = area.most_common(1)[0][0]
                text += " " + best_area
                chosen = chosen + [next(p for p in S["passages"] if p.text == best_area)]
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > 560:
            text = text[:560].rsplit(" ", 1)[0]
        return ProseResult(text, [(p.url, p.text[:200]) for p in chosen], True, note)

    # ------------------------------------------------------------ typed handlers
    def _routing(self, si: int) -> Optional[ProseResult]:
        S = self.index.snaps[si]
        votes: Counter = Counter()
        where: dict = {}
        for p in S["passages"]:
            m = re.search(r"routing\s*(?:number|#|no\.?)?[^0-9]{0,40}(\d{9})", p.text, re.I)
            if m:
                key = m.group(1)
                votes[key] += p.auth
                where.setdefault(key, p)
        if not votes:
            return None
        num, _ = votes.most_common(1)[0]
        p = where[num]
        return ProseResult(f"Dupaco's routing number is {num}.", [(p.url, p.text[:200])])

    def _url(self, si: int, question: str) -> Optional[ProseResult]:
        S = self.index.snaps[si]
        low = question.lower()
        drop = {"link", "url", "website", "web", "address", "page", "webpage", "site", "see", "find",
                "use", "dupaco", "get", "visit", "where", "online", "start"}
        qt = [t for t in query_tokens(question) if t not in drop]
        if re.search(r"\bjoin\b|\bbecome a member\b|\bsign up\b|\benroll", low):
            qt = ["join"]                       # "how do I join online" asks for the join link
        if "cd" in qt or "cds" in qt:
            qt = [t for t in qt if t not in ("cd", "cds")] + _tok("certificates")
        if not qt:
            return None
        wsum = sum(self.index.idf(si, t) for t in set(qt)) or 1.0
        loose: dict[str, float] = {}
        if re.search(r"\brates?\b", low):
            # "link to see X rates": a product page's own rates button, on the page that discusses X
            topic = [t for t in qt if not t.startswith("rate")]
            if topic:
                tw = sum(self.index.idf(si, t) for t in set(topic)) or 1.0
                cands: dict[str, float] = {}
                for anchor, url, page_url, auth in S["links"]:
                    if auth < 3 or "dupaco.com" not in url or not re.search(r"#rates?$", url):
                        continue
                    if url.split("#")[0].rstrip("/") != page_url.split("#")[0].rstrip("/"):
                        continue
                    have = S["pagetok"].get(page_url, set())
                    cov = sum(self.index.idf(si, t) for t in set(topic) if t in have) / tw
                    if cov >= 0.99:
                        pg = S["bypage"].get(page_url, [])
                        ttl = pg[0].ttl if pg else frozenset()
                        named = sum(self.index.idf(si, t) for t in set(topic) if t in ttl) / tw      # the page titled for the subject
                        if named >= 0.5:
                            cands[url] = max(cands.get(url, 0), 10 * named + auth)
                        else:
                            loose[url] = max(loose.get(url, 0), auth)
                if cands:
                    url = max(cands, key=lambda u: (cands[u], -len(u)))
                    return ProseResult(f"You can use this link: {url}", [(url.split("#")[0], url)])
        if re.search(r"\bapply\b|\bapplication\b", low):
            topic = [t for t in qt if t not in ("apply", "application", "applying", "can", "do", "i")]
            if topic:
                tw = sum(self.index.idf(si, t) for t in set(topic)) or 1.0
                cands = {}
                for anchor, url, page_url, auth in S["links"]:
                    if "dupaco.com" not in url or url.endswith((".pdf", ".jpg", ".png")):
                        continue
                    if not re.search(r"apply|application|loanapp", anchor + " " + url, re.I):
                        continue
                    if re.search(r"/(learn/blog|newsroom|blog|news|resources?)/", page_url):
                        continue
                    have = S["pagetok"].get(page_url, set())
                    cov = sum(self.index.idf(si, t) for t in set(topic) if t in have) / tw
                    if cov < 0.99:
                        continue
                    pg = S["bypage"].get(page_url, [])
                    ttl = pg[0].ttl if pg else frozenset()
                    named = sum(self.index.idf(si, t) for t in set(topic) if t in ttl) / tw
                    if named < 0.5:
                        continue
                    cands[(url, page_url)] = 10 * named + auth + (1 if "shine." in url else 0)
                if cands:
                    (url, pu) = max(cands, key=lambda k: (cands[k], -len(k[0])))
                    url = url.rstrip("#")
                    return ProseResult(f"You can use this link: {url}", [(pu, url)])
        best: dict[str, float] = defaultdict(float)
        seen_from: dict[str, str] = {}
        for anchor, url, page_url, auth in S["links"]:
            if "dupaco.com" not in url or url.endswith((".jpg", ".png", ".webp", ".svg", ".pdf")):
                continue
            host, _, path = url.split("://", 1)[-1].partition("/")
            slug = re.sub(r"[/\-_.#?=]+", " ", host.replace("dupaco.com", "") + " " + path)
            toks = set(_tok(anchor)) | set(_tok(slug))
            cov = sum(self.index.idf(si, t) for t in set(qt) if t in toks) / wsum
            if cov < 0.6:
                continue
            weight = 0.3 if re.search(r"/(learn/blog|newsroom|blog|news|resources?)/", url) else 1.0
            if len(anchor) > 40:
                weight *= 0.7
            if re.match(r"https?://(?:join|shine)\.", url) and not re.search(r"\b(?:join|apply|open|enroll|sign)\b", low):
                weight *= 0.4
            best[url] += cov * (1 + 0.1 * auth) * weight
            seen_from.setdefault(url, page_url)
        if not best:
            return None
        firm = {u: v for u, v in best.items() if not re.search(r"/(learn/blog|newsroom|blog|news|resources?)/|/calculators?/", u)}
        if firm and not re.search(r"calculat", low):
            best = firm
        url = max(best, key=lambda u: (best[u], -len(u)))
        url = url.rstrip("#")
        known = url.split("#")[0].rstrip("/")
        if loose and not any(pu.rstrip("/") == known for pu in S["bypage"]):
            lu = max(loose, key=lambda u: (loose[u], -len(u)))
            return ProseResult(f"You can use this link: {lu}", [(lu.split("#")[0], lu)])
        src = next((pu for pu in S["bypage"] if pu.rstrip("/") == known), seen_from.get(url, seen_from.get(url + "#")))
        return ProseResult(f"You can use this link: {url}", [(src, url)])
