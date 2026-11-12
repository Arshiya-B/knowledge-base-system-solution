"""
Temporal knowledge system for website snapshots (step 1: rate engine).

Deterministic and dependency-free (standard library only). No network, no model calls.

  ingest(snapshot)  -> normalise pages, extract table rows with their dated context, store history
  answer(q, as_of)  -> parse the question, match rows, rank by authority then effective date, compose
  conflicts()       -> (step 3) disagreements between pages

See NOTES.md for how "current" is decided.
"""
from __future__ import annotations

import sys
from datetime import date
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
from kbcore.prose import ProseEngine, intent_of, page_links, page_passages  # noqa: E402
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
        passages, links = [], []
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
            if ptype not in OK_TYPES:
                continue
            rows.extend(extract_rows(
                pg.markdown, url=url, ptype=ptype, authority=P.AUTH[ptype], scope=P.scope_of(pg.url),
                snap_idx=idx, taken_on=taken_on, fetched=parse_iso(pg.fetched_at),
                table_counter=self._table_counter))
        self.engine.add_snapshot(snapshot.snapshot_id, taken_on, rows, texts)
        self.prose.index.add_snapshot(passages, links)

    # ------------------------------------------------------------------ answer
    def answer(self, question: str, as_of: Optional[str] = None) -> Answer:
        res = self.engine.answer(question, as_of)
        gave_up = res is None or (not res.confident and not res.urls)
        # a duration ("how long can the interest rate stay fixed") is not a request for a rate value
        if gave_up and (not parse_query(question).is_rate or intent_of(question) == "duration"):
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
        out = []
        for c in rate_conflicts(self.engine):
            out.append(Conflict(topic=c["topic"], values=c["values"],
                                sources=[Source(url=u, snapshot_id=s, quote=q) for u, s, q in c["sources"]],
                                resolution=c["resolution"], reason=c["reason"]))
        if self.engine.snap_ids:
            si = len(self.engine.snap_ids) - 1
            bc = branch_count_conflict(self.prose.index.snaps[si]["passages"], self.engine.snap_ids[si])
            if bc:
                out.append(Conflict(topic=bc["topic"], values=bc["values"],
                                    sources=[Source(url=u, snapshot_id=s, quote=q) for u, s, q in bc["sources"]],
                                    resolution=bc["resolution"], reason=bc["reason"]))
        return out


def build() -> KnowledgeBase:
    return KnowledgeBase()
