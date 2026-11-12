"""Turn markdown tables into RowFacts: one fact per table row, with context and tier attributes."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from .textutil import (MONEY, clean, content_tokens, find_dates, money_to_float, pct_values)

INF = float("inf")


@dataclass
class Tier:
    term: Optional[int] = None                 # months
    years: Optional[tuple[int, int]] = None    # model-year range (inclusive)
    amount: Optional[tuple[float, float]] = None


@dataclass
class RowFact:
    url: str
    ptype: str
    authority: int
    scope: str                  # personal | business
    snap_idx: int
    taken_on: date
    fetched: Optional[date]
    stamp: Optional[date]       # "rates effective as of" date printed next to the table
    ctx: tuple[str, ...]        # nearest headings, closest first
    header: tuple[str, ...]
    label: str                  # human label from the non-metric cells
    cells: tuple[str, ...]
    metrics: dict = field(default_factory=dict)   # name -> list[float]
    tier: Tier = field(default_factory=Tier)
    core: frozenset = frozenset()    # tokens of label + nearest headings
    alltok: frozenset = frozenset()  # core + header + remaining headings
    table_id: int = 0
    key: str = ""

    def freshness(self):
        return self.stamp or date.min


# ----------------------------------------------------------------------------- parsing
_SEP = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_FOOT = re.compile(r"(?<=[A-Za-z%\)])\d$")   # trailing footnote digit like "APR1"


def _split_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _strip_md(s: str) -> str:
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = s.replace("**", "").replace("__", "").replace("`", "")
    s = re.sub(r"^[#>\s*-]+", "", s)
    return clean(s).strip()


def _is_heading_like(line: str) -> bool:
    raw = line.strip()
    if not raw or raw.startswith(("|", "![", "[", "- [", "* [", "<")):
        return False
    s = _strip_md(raw)
    if not (2 <= len(s) <= 70):
        return False
    low = s.lower()
    if low.endswith((".", ":", "?", "!")) or "effective as of" in low or "\\r" in s:
        return False
    if len(s.split()) > 9:
        return False
    return True


def _metric_of(header: str) -> Optional[str]:
    h = clean(header).lower()
    if "annual percentage yield" in h or re.search(r"\bapy\b", h):
        return "apy"
    if "dividend" in h:
        return "dividend"
    if "annual percentage rate" in h or re.search(r"\bapr\b", h):
        return "apr"
    if re.search(r"\brate\b", h):
        return "rate"
    return None


_SKIP_HEADER = re.compile(r"point|payment|min\.|minimum|^col\d+$|fee", re.I)


def parse_tier(text: str) -> Tier:
    t = clean(text)
    low = t.lower()
    tier = Tier()
    m = re.search(r"(?<![\d.])(\d{1,3})\s*-?\s*(?:months?|mos?)\b", low)
    if m:
        tier.term = int(m.group(1))
    else:
        m = re.search(r"(?<![\d.])(\d{1,2})\s*-?\s*(?:years?|yrs?)\b(?!\s*\d)", low)
        if m and "model year" not in low[max(0, m.start() - 12):m.end() + 12]:
            tier.term = int(m.group(1)) * 12
    # model years: "2024-27 Model Year", "Model Year 2026-23", "2016 Model Year (and older)"
    m = re.search(r"(?<![\d,$.])(20\d\d)\s*-\s*(\d{2,4})(?![\d,])", low)
    if m and "year" in low:
        a, b = int(m.group(1)), int(m.group(2))
        b = b + 2000 if b < 100 else b
        tier.years = (min(a, b), max(a, b))
    else:
        m = re.search(r"(?<![\d,$.])(20\d\d)\s+model year(?:.*older)?", low)
        if m:
            y = int(m.group(1))
            tier.years = (0, y) if "older" in low else (y, y)
    # amounts
    amts = [money_to_float(x) for x in MONEY.findall(t)]
    m2 = re.search(r"\$\s*([\d,]+(?:\.\d+)?)\s*-\s*\$?\s*([\d,]+(?:\.\d+)?)", t)
    if m2:
        lo, hi = money_to_float(m2.group(1)), money_to_float(m2.group(2))
        tier.amount = (min(lo, hi), max(lo, hi))
    elif amts:
        a = amts[0]
        if "or less" in low or "up to" in low:
            tier.amount = (0.0, a)
        elif re.search(r"\$\s*[\d,]+(?:\.\d+)?\s*\+", t) or "and up" in low or "or more" in low:
            tier.amount = (a, INF)
    return tier


_STAMP_HINT = re.compile(r"effective|as of|accurate as of|rates? (?:are|were)", re.I)


def _find_stamp(lines: list[str], start: int, end: int) -> Optional[date]:
    best = None
    for l in lines[start:end]:
        if _STAMP_HINT.search(l):
            ds = find_dates(l)
            if ds:
                d = max(ds)
                if best is None or d > best:
                    best = d
    return best


def extract_rows(md: str, *, url: str, ptype: str, authority: int, scope: str, snap_idx: int,
                 taken_on: date, fetched: Optional[date], table_counter: list) -> list[RowFact]:
    lines = md.split("\n")
    n = len(lines)
    rows: list[RowFact] = []
    i = 0
    prev_table_end = -1
    while i < n - 1:
        if not (lines[i].lstrip().startswith("|") and _SEP.match(lines[i + 1].strip() or "x")):
            i += 1
            continue
        header = [_strip_md(c) for c in _split_row(lines[i])]
        j = i + 2
        body = []
        while j < n and lines[j].lstrip().startswith("|"):
            body.append(_split_row(lines[j]))
            j += 1
        tbl_start, tbl_end = i, j
        i = j
        if not header or any(re.match(r"^col\d+$", h.lower()) for h in header) or len(header) > 9:
            prev_table_end = tbl_end
            continue
        # which columns carry metrics / which carry labels
        col_metric = {}
        for ci, h in enumerate(header):
            mname = _metric_of(h)
            if mname and not _SKIP_HEADER.search(h):
                col_metric[ci] = mname
            elif re.search(r"\bapr\b|\bapy\b", h.lower()):
                col_metric[ci] = _metric_of(h) or "rate"
        if not col_metric:
            prev_table_end = tbl_end
            continue
        # context headings (closest first)
        ctx = []
        for k in range(tbl_start - 1, max(prev_table_end, tbl_start - 30) - 1, -1):
            if k < 0:
                break
            if _is_heading_like(lines[k]):
                s = _strip_md(lines[k])
                if not ctx or ctx[-1] != s:
                    ctx.append(s)
            if len(ctx) >= 3:
                break
        # "[Explore](.../personal/savings/certificates/)" links name the product section even when
        # the heading above the table is only "Regular" or "Special"
        for k in range(tbl_start - 1, max(prev_table_end, tbl_start - 30) - 1, -1):
            mm = re.match(r"\s*\[(?:Explore|Learn more|Get started)[^\]]*\]\(https?://[^/]+/([^?#)]*)", lines[k]) if k >= 0 else None
            if mm:
                segs = [x for x in mm.group(1).strip("/").split("/") if x]
                if segs:
                    ctx.append(" ".join(segs[-2:]).replace("-", " "))
                break
        stamp = _find_stamp(lines, tbl_end, min(n, tbl_end + 10)) or _find_stamp(lines, max(0, tbl_start - 4), tbl_start)
        table_counter[0] += 1
        tid = table_counter[0]
        seen = set()
        for cells in body:
            if len(cells) < len(header):
                cells = cells + [""] * (len(header) - len(cells))
            cells = [_strip_md(c) for c in cells[:len(header)]]
            metrics = {}
            for ci, mname in col_metric.items():
                vals = pct_values(cells[ci])
                if vals:
                    # the unit printed in the cell beats a (sometimes wrong) column header
                    unit = re.search(r"%\s*(apr|apy)\b", cells[ci].lower())
                    metrics.setdefault(unit.group(1) if unit else mname, []).extend(vals)
            if not metrics:
                continue
            label_cells = [c for ci, c in enumerate(cells)
                           if ci not in col_metric and c and c not in ("-", "—") and not _SKIP_HEADER.search(header[ci])]
            label = " | ".join(label_cells)
            sig = (label, tuple(sorted((k, tuple(v)) for k, v in metrics.items())))
            if sig in seen:
                continue
            seen.add(sig)
            tier = parse_tier(" ".join(label_cells))
            core_text = " ".join([label] + list(ctx[:2]))
            core = frozenset(content_tokens(core_text))
            alltok = core | frozenset(content_tokens(" ".join(list(header) + list(ctx[2:]))))
            key = re.sub(r"(?<=\d),(?=\d{3})", "", re.sub(r"\s+", " ", clean(label).lower()))
            rows.append(RowFact(url=url, ptype=ptype, authority=authority, scope=scope, snap_idx=snap_idx,
                                taken_on=taken_on, fetched=fetched, stamp=stamp, ctx=tuple(ctx),
                                header=tuple(header), label=label, cells=tuple(cells), metrics=metrics,
                                tier=tier, core=core, alltok=alltok, table_id=tid, key=key))
        prev_table_end = tbl_end
    return rows
