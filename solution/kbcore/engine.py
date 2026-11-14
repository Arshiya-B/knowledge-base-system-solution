"""Rate/table question engine: parse the question, match table rows, resolve, compose."""
from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from .tables import RowFact
from .textutil import (SOFT, STOP, METRIC, clean, content_tokens, fmt_pct, pct_values, pretty_date, tokens)

OK_TYPES = {"rates", "product", "landing", "calculator", "home"}

# row tokens that mean "a different product variant"; excluded unless the question mentions them
EXCLUSIVE = {"business", "jumbo", "introductory", "intro", "refinance", "roth", "traditional", "ira"}
LIST_EXCLUSIVE = {"introductory", "intro", "roth", "traditional", "ira", "refinance"}

# conversational words; ignored unless a rate row itself uses them
FILLER = {"hi", "hello", "hey", "thanks", "thank", "quick", "question", "wondering", "curious", "looking",
          "interested", "planning", "run", "small", "think", "thought", "hope", "sure", "really", "actually",
          "little", "bit", "big", "lot", "thing", "stuff", "way", "ways", "idea", "info", "information"}

# a question token may be satisfied by any of these row tokens
EXPAND = {
    "mortgage": {"conventional"},
    "auto": {"auto", "motorcycle"},
    "motorcycle": {"motorcycle"},
    "refinance": {"refinance"},
}

NUMWORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
            "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "seventeen": 17, "eighteen": 18, "twenty": 20,
            "thirty": 30, "forty": 40, "sixty": 60}

ABSTAIN_TEXT = ("I don't know. I couldn't find that on the website, so I don't want to guess. "
                "Please contact Dupaco directly.")

MAX_ROWS = 14


@dataclass
class Query:
    raw: str
    qtok: list = field(default_factory=list)
    metric: Optional[str] = None
    terms: set = field(default_factory=set)
    years: list = field(default_factory=list)
    amounts: list = field(default_factory=list)
    superlative: Optional[str] = None
    verify: Optional[float] = None
    is_rate: bool = False
    mentioned: set = field(default_factory=set)


@dataclass
class Result:
    text: str
    urls: list = field(default_factory=list)       # [(url, snapshot_id, quote)]
    confident: bool = True
    note: Optional[str] = None


def parse_query(question: str) -> Query:
    t = clean(question).lower()
    toks = tokens(question)
    q = Query(raw=question)
    q.mentioned = set(toks)

    # terms ("60-month", "5 year", "six month")
    for n, unit in re.findall(r"(?<![\d.$,])(\d{1,3})\s*-?\s*(months?|mos?|years?|yrs?)\b", t):
        n = int(n)
        if unit.startswith(("y",)):
            n *= 12
        q.terms.add(n)
    for w, unit in re.findall(r"\b(" + "|".join(NUMWORDS) + r")[\s-]+(months?|years?)\b", t):
        q.terms.add(NUMWORDS[w] * (12 if unit.startswith("year") else 1))

    # model years: only when the question is about a vehicle-ish thing
    if "model" in q.mentioned or q.mentioned & {"auto", "motorcycle", "boat", "rv", "atv", "snowmobile", "jet"}:
        for m in re.finditer(r"(?<![\d,$.])((?:19|20)\d\d)(?![\d,])", t):
            before = t[max(0, m.start() - 12):m.start()]
            if re.search(r"(as of|in|since|by|during|until)\s+(?:\w+\s+)?$", before):
                continue
            q.years.append(int(m.group(1)))

    # amounts
    for m in re.finditer(r"\$\s*([\d,]+(?:\.\d+)?)\s*(k|m|million|thousand)?\b", t):
        v = float(m.group(1).replace(",", ""))
        mult = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6}.get(m.group(2) or "", 1)
        q.amounts.append(v * mult)
    for m in re.finditer(r"(?<![\d.$,])(\d+(?:\.\d+)?)\s*k\b", t):
        q.amounts.append(float(m.group(1)) * 1e3)
    if not q.amounts:
        for m in re.finditer(r"(?<![\d.$])(\d{1,3}(?:,\d{3})+)(?!\d)", t):
            q.amounts.append(float(m.group(1).replace(",", "")))

    # metric ("dividend rate, not the APY" asks for the dividend rate)
    neg = re.search(r"\b(?:not|rather than|instead of|excluding)\s+(?:the\s+|an?\s+)?(apy|yield|dividend|apr)\b", t)
    if neg and neg.group(1) in ("apy", "yield") and "dividend" in t:
        q.metric = "dividend"
    elif neg and neg.group(1) == "dividend" and re.search(r"\bapy\b|\byield", t.replace(neg.group(0), "")):
        q.metric = "apy"
    elif re.search(r"\bapy\b|\byield", t):
        q.metric = "apy"
    elif "dividend" in t:
        q.metric = "dividend"
    elif re.search(r"\bapr\b|\bapr?s\b|annual percentage rate", t):
        q.metric = None if re.search(r"\b(interest )?rates?\b(?! \(?apr)", re.sub(r"annual percentage rate", "", t)) else "apr"

    if re.search(r"\b(highest|maximum|max|best|top|most)\b", t):
        q.superlative = "max"
    elif re.search(r"\b(lowest|minimum|min|cheapest|least|smallest)\b", t):
        q.superlative = "min"

    pcts = pct_values(question)
    if pcts and re.search(r"\b(any|do|does|which|is there|are there)\b", t):
        q.verify = pcts[0]

    q.is_rate = bool(q.mentioned & {"rate", "apr", "apy", "dividend", "interest", "yield", "aprs", "percentage"}) or bool(pcts)
    has_qual = bool(q.terms or q.amounts or q.years)
    DEPOSIT = {"certificate", "savings", "checking", "ira", "roth", "money", "market", "hsa", "share"}
    LOANISH = {"mortgage", "loan", "auto", "heloc", "visa", "equity", "refinance", "refinancing"}
    NONRATE = {"minimum", "fee", "hour", "branch", "address", "phone", "apply", "open", "requirement",
               "eligible", "eligibility", "login", "payment", "deadline", "close", "closed",
               "point", "points", "worth", "reward", "rewards", "redeem", "redemption", "redemptions"}
    if not q.is_rate and not (q.mentioned & NONRATE):
        if q.mentioned & {"earn", "pay", "return"} and (has_qual or q.mentioned & DEPOSIT):
            q.is_rate = True
        elif has_qual and q.mentioned & (LOANISH | DEPOSIT):
            q.is_rate = True
    # questions that ask for a link/page are not asking for a rate value
    if re.search(r"\b(link|url|website|webpage|web page|where can i (?:see|find|look))\b", t):
        q.is_rate = False

    drop = SOFT - {"special", "jumbo"}
    q.qtok = sorted({w for w in content_tokens(question) if w not in drop and not w.isdigit()
                     and not re.fullmatch(r"\d+[km]", w)})
    if re.search(r"\bhigh[\s-]+yield", t) and "high" not in q.qtok:
        q.qtok = sorted(set(q.qtok) | {"high"})     # "high-yield" is a product name, not an adjective
    return q


class RateEngine:
    def __init__(self):
        self.rows: list[list[RowFact]] = []     # per snapshot index
        self.snap_ids: list[str] = []
        self.snap_dates: list[date] = []
        self.idf: dict[str, float] = {}
        self.max_idf = 1.0
        self._dirty = True
        self._pop_cache: dict = {}
        self.page_text: list[dict] = []         # snapshot -> {url: lower text} (for popularity prior)

    # ------------------------------------------------------------------ build
    def add_snapshot(self, snap_id: str, taken_on: date, rows: list[RowFact], texts: dict):
        self.snap_ids.append(snap_id)
        self.snap_dates.append(taken_on)
        self.rows.append(rows)
        self.page_text.append(texts)
        self._dirty = True

    def _build_idf(self):
        df = defaultdict(int)
        n = 0
        for rows in self.rows:
            for r in rows:
                n += 1
                for t in r.alltok:
                    df[t] += 1
        self.idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}
        self.max_idf = math.log(n + 1) + 1.0
        self._dirty = False

    def pick_snapshot(self, as_of: Optional[str]) -> Optional[int]:
        if not self.rows:
            return None
        if not as_of:
            return len(self.rows) - 1
        try:
            d = date.fromisoformat(as_of[:10])
        except ValueError:
            return len(self.rows) - 1
        idx = None
        for i, sd in enumerate(self.snap_dates):
            if sd <= d:
                idx = i
        return idx

    # ------------------------------------------------------------------ matching helpers
    def _w(self, tok: str) -> float:
        return self.idf.get(tok, self.max_idf)

    def _core_coverage(self, qtok: list, row: RowFact) -> float:
        """Like _coverage but only counts the row's own label and nearest headings."""
        tot = sum(self._w(t) for t in qtok)
        if tot <= 0:
            return 0.0
        got = sum(self._w(t) for t in qtok if (EXPAND.get(t, {t}) | {t}) & row.core)
        return got / tot

    def _coverage(self, qtok: list, row: RowFact) -> float:
        tot = sum(self._w(t) for t in qtok)
        if tot <= 0:
            return 0.0
        got = 0.0
        for t in qtok:
            alts = EXPAND.get(t, {t}) | {t}
            if alts & row.alltok:
                got += self._w(t)
        return got / tot

    # ------------------------------------------------------------------ product names
    def _product_names(self) -> set:
        """Names the site gives its products (first label cell of rate rows), as stemmed token tuples."""
        got = self.__dict__.get("_pnames")
        if got is None or self.__dict__.get("_pnames_n") != sum(len(x) for x in self.rows):
            got = set()
            for snap in self.rows:
                for r in snap:
                    first = re.sub(r"\(.*?\)", " ", r.label.split(" | ")[0])
                    if "$" in first or ":" in first:
                        continue
                    t = tuple(tokens(first))
                    if len(t) >= 2 and not any(w.isdigit() for w in t):
                        got.add(t)
            self._pnames, self._pnames_n = got, sum(len(x) for x in self.rows)
        return got

    def _protect_product_names(self, q: Query) -> None:
        """A product name the question spells out in full keeps all of its words, even ones that are
        usually filler ("You Name It Savings", "High-Yield Savings")."""
        qt = tokens(q.raw)
        add = set()
        for n in self._product_names():
            if any(tuple(qt[i:i + len(n)]) == n for i in range(len(qt) - len(n) + 1)):
                add |= {w for w in n if w not in STOP and w not in METRIC and len(w) > 1}
        if add:
            q.qtok = sorted(set(q.qtok) | add)

    # ------------------------------------------------------------------ main entry
    def answer(self, question: str, as_of: Optional[str]) -> Optional[Result]:
        q = parse_query(question)
        if not q.is_rate:
            return None
        if self._dirty:
            self._build_idf()
        self._protect_product_names(q)
        # conversational filler and -ing/-ed verbs ("thinking", "depositing") that no rate row uses
        q.qtok = [w for w in q.qtok if w in self.idf or not (w in FILLER or (len(w) > 5 and w.endswith(("ing", "ed"))))]
        si = self.pick_snapshot(as_of)
        if si is None:
            return Result(ABSTAIN_TEXT, confident=False)
        if not q.qtok:
            return Result(ABSTAIN_TEXT, confident=False)

        rows = [r for r in self.rows[si] if r.ptype in OK_TYPES]
        scored = [(self._coverage(q.qtok, r), r) for r in rows]
        if not scored:
            return Result(ABSTAIN_TEXT, confident=False)
        best = max(c for c, _ in scored)
        if best < 0.72:
            return Result(ABSTAIN_TEXT, confident=False)
        cov = {id(r): c for c, r in scored}
        elig = [r for c, r in scored if c >= 0.72]

        # variant exclusions (business, jumbo, intro, IRA ...) unless the question mentions them
        excl = set(EXCLUSIVE)
        if not q.terms:
            excl.discard("jumbo")       # "certificate rates" lists jumbo terms too; "17-month" does not
        flagged = lambda r, ex: bool((r.core & ex) - q.mentioned)
        clean_rows = [r for r in elig if not flagged(r, excl)]
        if clean_rows:
            elig = clean_rows
        else:
            elig = [r for r in elig if not flagged(r, LIST_EXCLUSIVE)] or elig

        # hard qualifier filters (term, model year, balance/loan tier) on the whole candidate pool,
        # then keep the best-matching product names among the survivors
        elig = self._filter_qualifiers(q, elig)
        if not elig:
            return Result(ABSTAIN_TEXT, confident=False)
        b2 = max(cov[id(r)] for r in elig)
        elig = [r for r in elig if cov[id(r)] >= b2 - 0.08]
        # words matched in the row's own name beat words that only appear in a distant heading
        # ("You Name It Savings" must not be answered with Share Savings rows)
        if len(q.qtok) >= 2:                   # one-word questions ("credit cards") are category questions
            core = {id(r): self._core_coverage(q.qtok, r) for r in elig}
            cb = max(core.values())
            elig = [r for r in elig if core[id(r)] >= cb - 0.2]

        # keep only the most authoritative page class that carries a match
        top_auth = max(r.authority for r in elig)
        elig = [r for r in elig if r.authority == top_auth]

        # superlative / verification narrow to one product
        if q.superlative or q.verify is not None:
            elig = self._single_product(q, elig, si)

        slots = self._pick_slots(elig)
        if not slots:
            return Result(ABSTAIN_TEXT, confident=False)

        # list-mode: personal slots are few and no scope word given -> also show business variants
        has_qualifier = bool(q.terms or q.years or q.amounts)
        n_products = len({self._product_name(r) for r in slots})
        if (not q.superlative and q.verify is None and not has_qualifier and "business" not in q.mentioned
                and n_products >= 2 and len(slots) <= 4):
            extra = self._business_extras(q, scored, best, si, slots, excl)
            slots = slots + extra

        return self._compose(q, slots, as_of, si)

    # ------------------------------------------------------------------ filters
    def _filter_qualifiers(self, q: Query, rows: list[RowFact]) -> list[RowFact]:
        if q.terms:
            have = [r for r in rows if r.tier.term is not None]
            if have:
                rows = [r for r in have if r.tier.term in q.terms]
        if q.years:
            have = [r for r in rows if r.tier.years]
            if have:
                rows = [r for r in have if all(r.tier.years[0] <= y <= r.tier.years[1] for y in q.years)]
        if q.amounts:
            have = [r for r in rows if r.tier.amount]
            if have:
                lo, hi = min(q.amounts), max(q.amounts)
                keep = [r for r in have if r.tier.amount[0] <= lo and hi <= r.tier.amount[1]]
                rows = keep
                # tightest tier wins inside the same table and term
                groups = defaultdict(list)
                for r in rows:
                    groups[(r.url, r.table_id, r.tier.term)].append(r)
                out = []
                for g in groups.values():
                    span = min(r.tier.amount[1] - r.tier.amount[0] for r in g)
                    out.extend(r for r in g if r.tier.amount[1] - r.tier.amount[0] == span)
                rows = out
        return rows

    def _product_name(self, r: RowFact) -> str:
        return r.ctx[0] if r.ctx else r.label.split(" | ")[0]

    def _popularity(self, name: str, si: int) -> int:
        key = (si, name.lower())
        if key not in self._pop_cache:
            needle = name.lower()
            self._pop_cache[key] = sum(1 for t in self.page_text[si].values() if needle in t)
        return self._pop_cache[key]

    def _single_product(self, q: Query, rows: list[RowFact], si: int) -> list[RowFact]:
        names = {}
        for r in rows:
            names.setdefault(self._product_name(r), []).append(r)
        if len(names) <= 1:
            return rows
        # prefer the product whose name the question spells out, else the most referenced one
        def spelled(n):
            nt = set(content_tokens(n))
            return len(nt & set(q.qtok)) / (len(nt) or 1)
        ranked = sorted(names, key=lambda n: (-spelled(n), -self._popularity(n, si), n))
        return names[ranked[0]]

    def _pick_slots(self, rows: list[RowFact]) -> list[RowFact]:
        """One winning row per (scope, label): newest effective stamp, then newest snapshot."""
        by = defaultdict(list)
        for r in rows:
            by[(r.scope, r.key)].append(r)
        slots = []
        for g in by.values():
            g.sort(key=lambda r: (r.freshness(), r.taken_on, r.fetched or date.min, r.url), reverse=True)
            slots.append(g[0])
        order = {id(r): i for i, r in enumerate(rows)}
        slots.sort(key=lambda r: order[id(r)])
        # a single question normally has one answer: if slots disagree on tier labels but come from
        # different pages of equal authority, prefer the freshest stamp
        return slots

    def _business_extras(self, q, scored, best, si, slots, excl):
        cand = [r for c, r in scored if c >= best - 0.08
                and (r.scope == "business" or "business" in (r.core - q.mentioned))]
        ex = set(excl) - {"business"}
        cand = [r for r in cand if not ((r.core & ex) - q.mentioned)]
        cand = self._filter_qualifiers(q, cand)
        if not cand:
            return []
        top = max(r.authority for r in cand)
        cand = [r for r in cand if r.authority == top]
        return self._pick_slots(cand)

    # ------------------------------------------------------------------ composing
    def _row_name(self, r: RowFact) -> str:
        label = clean(r.label).replace(" | ", ", ")
        name = label
        if r.ctx:
            ctoks = set(content_tokens(r.ctx[0]))
            ltoks = set(content_tokens(label))
            if ctoks and not (ctoks & ltoks):
                name = f"{clean(r.ctx[0])}: {label}"
        if r.scope == "business" and "business" not in name.lower():
            name += " (business)"
        return name

    def _row_value(self, q: Query, r: RowFact) -> str:
        m = r.metrics
        parts = []

        def one(name):
            v = m.get(name)
            if not v:
                return None
            return fmt_pct(v[0]) if len(v) == 1 else f"{fmt_pct(min(v))} to {fmt_pct(max(v))}"

        apy, div, apr, rate = one("apy"), one("dividend"), one("apr"), one("rate")
        if apy or div:
            if q.metric == "apy" and apy:
                return f"{apy} APY"
            if q.metric == "dividend" and div:
                return f"{div} dividend rate"
            if apy and div:
                return f"{apy} APY ({div} dividend rate)" if apy != div else f"{apy} dividend rate and APY"
            return f"{apy} APY" if apy else f"{div} dividend rate"
        if apr and rate:
            if q.metric == "apr":
                return f"{apr} APR"
            return f"{rate} rate, {apr} APR"
        if apr:
            return f"{apr} APR"
        if rate:
            return f"{rate} rate"
        return ""

    def _metric_sort(self, r: RowFact, q: Query) -> float:
        for name in ([q.metric] if q.metric else []) + ["apy", "apr", "rate", "dividend"]:
            v = r.metrics.get(name)
            if v:
                return max(v)
        return 0.0

    def _compose(self, q: Query, slots: list[RowFact], as_of: Optional[str], si: int) -> Result:
        prefix = f"As of the {pretty_date(self.snap_dates[si])} website snapshot, " if as_of else ""
        note = None

        if q.verify is not None:
            hit = [r for r in slots if any(abs(v - q.verify) < 1e-9 for vs in r.metrics.values() for v in vs)]
            top = max(slots, key=lambda r: self._metric_sort(r, q))
            name = clean(self._product_name(top))
            if hit:
                body = "Yes. " + "; ".join(f"{self._row_name(r)}: {self._row_value(q, r)}" for r in hit[:MAX_ROWS]) + "."
            else:
                body = (f"No. The {name} tiers do not pay that. The highest is "
                        f"{self._row_value(q, top)} ({clean(top.label).replace(' | ', ', ')}).")
            text = (prefix + body) if not prefix else prefix + body[0].lower() + body[1:]
            return Result(text, self._sources(slots), True, note)

        if q.superlative:
            pick = max(slots, key=lambda r: self._metric_sort(r, q)) if q.superlative == "max" \
                else min(slots, key=lambda r: self._metric_sort(r, q))
            word = "highest" if q.superlative == "max" else "lowest"
            body = f"The {word} is {self._row_value(q, pick)} ({self._row_name(pick)})."
            return Result(prefix + body if not prefix else prefix + body[0].lower() + body[1:],
                          self._sources([pick] + slots), True, note)

        shown = slots[:MAX_ROWS]
        lines, where = [], {}
        for r in shown:
            line = f"{self._row_name(r)}: {self._row_value(q, r)}"
            key = line.replace(" (business)", "").lower()
            if key in where:                      # the same product and value on two pages: say it once, prefer the plain label
                if "(business)" in lines[where[key]] and "(business)" not in line:
                    lines[where[key]] = line
                continue
            where[key] = len(lines)
            lines.append(line)
        stamps = sorted({r.stamp for r in shown if r.stamp})
        tail = ""
        if len(stamps) == 1:
            tail = f" (rates effective {pretty_date(stamps[0])})"
        elif len(stamps) > 1:
            tail = f" (rates effective {pretty_date(stamps[0])} to {pretty_date(stamps[-1])})"
        if len(slots) > MAX_ROWS:
            tail += f" Plus {len(slots) - MAX_ROWS} more tiers on the rates page."
        body = "; ".join(lines) + "." + tail
        if prefix:
            body = prefix + body[0].lower() + body[1:]
        return Result(body, self._sources(shown), True, note)

    def _sources(self, rows: list[RowFact]) -> list:
        out, seen = [], set()
        for r in rows:
            if r.url not in seen:
                seen.add(r.url)
                out.append((r.url, self.snap_ids[r.snap_idx], f"{r.label}: {' / '.join(r.cells[-3:])}"[:160]))
        # also cite other pages that carry the same labelled row with the same values
        first = rows[0] if rows else None
        if first is not None:
            for other in self.rows[first.snap_idx]:
                if len(out) >= 3:
                    break
                if other.url in seen or other.authority < 3 or other.key != first.key:
                    continue
                if other.metrics == first.metrics:
                    seen.add(other.url)
                    out.append((other.url, self.snap_ids[other.snap_idx], f"{other.label}"[:160]))
        return out[:3]
