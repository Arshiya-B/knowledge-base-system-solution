"""
Temporal knowledge system for website snapshots (step 1: rate engine).

Deterministic and dependency-free (standard library only). No network, no model calls.

  ingest(snapshot)  -> normalise pages, extract table rows with their dated context, store history
  answer(q, as_of)  -> parse the question, match rows, rank by authority then effective date, compose
  conflicts()       -> (step 3) disagreements between pages

See NOTES.md for how "current" is decided.
"""
from __future__ import annotations
import re

import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
_h = next((d / "harness" for d in _HERE.parents if (d / "harness" / "contract.py").exists()), None)
if _h is not None:
    sys.path.insert(0, str(_h))
from contract import Answer, Conflict, Snapshot, Source  # noqa: E402

from kbcore import pages as P  # noqa: E402
from kbcore.conflicts import branch_count_conflict, rate_conflicts  # noqa: E402
from kbcore.engine import ABSTAIN_TEXT, OK_TYPES, RateEngine, parse_query  # noqa: E402
from kbcore.prose import ProseEngine, intent_of, page_links, page_passages, page_people  # noqa: E402
from kbcore.tables import extract_rows  # noqa: E402
from kbcore.textutil import parse_iso  # noqa: E402


class KnowledgeBase:
    def __init__(self):
        self.engine = RateEngine()
        self.prose = ProseEngine()
        self._table_counter = [0]

    # ------------------------------------------------------------------ ingest
    def ingest(self, snapshot: Snapshot) -> None:
        idx = len(self.engine.snap_ids)
        taken_on = parse_iso(snapshot.taken_on) or date.min
        rows, texts = [], {}
        passages, links, people = [], [], []
        seen_urls = set()
        for pg in snapshot.pages:
            url = P.canon_url(pg.url)
            if url in seen_urls:
                continue
            seen_urls.add(url)
            ptype = P.classify(pg.url)
            texts[url] = pg.markdown.lower()
            if ptype not in ("file", "calculator"):
                passages.extend(page_passages(pg.markdown, url, ptype, P.AUTH[ptype], taken_on, pg.title))
                links.extend((a, u, url, P.AUTH[ptype]) for a, u in page_links(pg.markdown))
                if ptype in ("landing", "product"):
                    people.extend((n, t, url) for n, t in page_people(pg.markdown))
            if ptype not in OK_TYPES:
                continue
            rows.extend(extract_rows(
                pg.markdown, url=url, ptype=ptype, authority=P.AUTH[ptype], scope=P.scope_of(pg.url),
                snap_idx=idx, taken_on=taken_on, fetched=parse_iso(pg.fetched_at),
                table_counter=self._table_counter))
        self.engine.add_snapshot(snapshot.snapshot_id, taken_on, rows, texts)
        self.prose.index.add_snapshot(passages, links, people)

    # ------------------------------------------------------------------ answer
    def answer(self, question: str, as_of: Optional[str] = None) -> Answer:
        if as_of is None:
            as_of = _date_in_question(question, self.engine.snap_dates[-1].year if self.engine.snap_dates else None)
        res = self.engine.answer(question, as_of)
        gave_up = res is None or (not res.confident and not res.urls)
        # a duration ("how long can the interest rate stay fixed") is not a request for a rate value
        if gave_up and (not parse_query(question).is_rate or intent_of(question) == "duration" or
                     re.search(r"\b(?:if|when|after|once) i (?:turn|switch|enable|sign|set|use|have|open|add)\b", question.lower())):
            si = self.engine.pick_snapshot(as_of)
            if si is not None:
                pr = self.prose.answer(si, question)
                if pr is not None:
                    sid = self.engine.snap_ids[si]
                    return Answer(text=pr.text, sources=[Source(url=u, snapshot_id=sid, quote=q) for u, q in pr.urls],
                                  confident=pr.confident, conflict_note=pr.note)
        if res is None:
            return Answer(text=ABSTAIN_TEXT, confident=False)
        return Answer(
            text=res.text,
            sources=[Source(url=u, snapshot_id=s, quote=qt) for u, s, qt in res.urls],
            confident=res.confident,
            conflict_note=res.note,
        )

    # ------------------------------------------------------------------ conflicts
    def conflicts(self) -> list[Conflict]:
        rows = []
        for c in rate_conflicts(self.engine):
            rows.append((c["topic"], c["values"], c["sources"], c["resolution"], c["reason"]))
        if self.engine.snap_ids:
            si = len(self.engine.snap_ids) - 1
            bc = branch_count_conflict(self.prose.index.snaps[si]["passages"], self.engine.snap_ids[si])
            if bc:
                rows.append((bc["topic"], bc["values"], bc["sources"], bc["resolution"], bc["reason"]))
        if not GROUP_BY_PRODUCT:
            return [Conflict(topic=t, values=v, sources=[Source(url=u, snapshot_id=s, quote=q) for u, s, q in src],
                             resolution=r, reason=why) for t, v, src, r, why in rows]
        groups: dict[str, list] = {}
        for row in rows:
            groups.setdefault(_product_key(row[0]), []).append(row)
        out = []
        for key, rs in groups.items():
            if len(rs) == 1:
                t, v, src, r, why = rs[0]
                out.append(Conflict(topic=t, values=v, sources=[Source(url=u, snapshot_id=s, quote=q) for u, s, q in src],
                                    resolution=r, reason=why))
                continue
            values, seen_v, sources, seen_s = [], set(), [], set()
            for t, v, src, r, why in rs:
                for x in v:
                    if x not in seen_v:
                        seen_v.add(x); values.append(x)
                for u, s, q in src:
                    if (u, q) not in seen_s:
                        seen_s.add((u, q)); sources.append(Source(url=u, snapshot_id=s, quote=q))
            winners = "; ".join(f"{(t.split(key, 1)[-1].strip(' :,') if key in t else t.split(':', 1)[-1].strip())}: {r}" for t, v, src, r, why in rs if r)
            out.append(Conflict(topic=key, values=values, sources=sources, resolution=winners,
                                reason=f"{len(rs)} rows on this product disagree across pages. Winner per row (newest effective stamp, then newest snapshot, then page authority): {winners}"))
        return out


GROUP_BY_PRODUCT = True

_MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"])}
_MON_RE = "|".join(_MONTHS)
_ASOF_RE = re.compile(
    r"\b(?:as of|in|during|back in|on|for|around|by)\s+"
    r"(?P<mon>" + _MON_RE + r")\b(?:\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?\b)?(?:,?\s+(?P<yr>20\d\d)\b)?",
    re.I)


def _date_in_question(question: str, default_year: Optional[int] = None) -> Optional[str]:
    """A person who writes "as of May 2026" or "for July 4" means the site on that date, even if the caller passed
    no as_of. Month only: the last day of that month. Month and day: that day. No year: the year of the snapshots."""
    for m in _ASOF_RE.finditer(question):
        word = m.group("mon")
        has_day, has_yr = bool(m.group("day")), bool(m.group("yr"))
        if word.lower() == "may" and not has_yr and not has_day and not word[0].isupper():
            continue                           # "may" as a verb ("what rate may I get in ...")
        if not has_yr and not has_day and not word[0].isupper():
            continue
        if not has_yr and default_year is None:
            continue
        mon = _MONTHS[word.lower()]
        yr = int(m.group("yr")) if has_yr else default_year
        if has_day:
            day = int(m.group("day"))
        else:
            nxt = date(yr + (mon == 12), mon % 12 + 1, 1)
            day = (nxt - timedelta(days=1)).day
        try:
            return date(yr, mon, day).isoformat()
        except ValueError:
            continue
    return None


def build() -> KnowledgeBase:
    return KnowledgeBase()
