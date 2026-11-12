"""conflicts(): places where the website contradicts itself, with the value we believe and why.

Rate facts: rows that describe the same thing (same product, tier, term) but carry different
numbers on different pages. The winner is the row with the newest "effective as of" stamp (then the
newest snapshot, then the more authoritative page type). A bare tier such as "$100,000+" only counts
as the same slot when the product heading above it is the same, otherwise two products would look
like they disagree.
"""
from __future__ import annotations

import re
from collections import defaultdict

from .textutil import clean, fmt_pct

PRIMARY = ("rate", "dividend", "apy", "apr")
_NAME = {"rate": "rate", "dividend": "dividend rate", "apy": "APY", "apr": "APR"}


def _is_bare(label: str) -> bool:
    return not re.search(r"[a-z]{3,}", re.sub(r"(?i)\b(month|months|year|years|day|days|and|or|up|to)\b", "", label))


def _slot_key(r):
    if _is_bare(r.label):
        if not r.ctx:
            return None
        return (r.scope, r.key, clean(r.ctx[0]).lower())
    return (r.scope, r.key)


def _sig(r, metrics):
    return tuple((m, tuple(r.metrics[m])) for m in metrics)


def _fmt(sig) -> str:
    parts = []
    for m, vals in sig:
        parts.append(" / ".join(fmt_pct(v) for v in vals) + f" {_NAME.get(m, m)}")
    return ", ".join(parts)


def _rank(r):
    return (r.freshness(), r.snap_idx, r.authority, r.ptype == "rates", r.fetched is not None)


def rate_conflicts(engine) -> list:
    """Returns dicts: topic, values, sources(list of (url, snapshot_id, quote)), resolution, reason."""
    out: dict = {}
    latest = len(engine.rows) - 1
    # newest-snapshot winner per slot, used to settle conflicts that were fixed later
    latest_win = {}
    for r in engine.rows[latest]:
        k = _slot_key(r)
        if k is not None and (k not in latest_win or _rank(r) > _rank(latest_win[k])):
            latest_win[k] = r
    for si, rows in enumerate(engine.rows):
        groups = defaultdict(list)
        for r in rows:
            k = _slot_key(r)
            if k is not None:
                groups[k].append(r)
        for k, rs in groups.items():
            if len({r.url for r in rs}) < 2:
                continue
            common = [m for m in PRIMARY if all(m in r.metrics and r.metrics[m] for r in rs)]
            if not common:
                continue
            sigs = {_sig(r, common) for r in rs}
            if len(sigs) < 2:
                continue
            win = max(rs, key=_rank)
            # keep only the most recent snapshot in which this slot disagrees: older snapshots
            # hold earlier rates, and a rate that simply moved over time is not a contradiction
            out[k] = {"rows": {(r.url, _sig(r, common), si): (si, r) for r in rs}, "win": win, "si": si,
                      "common": set(common), "name": engine._row_name(win)}
    for k, e in out.items():
        f = latest_win.get(k)
        e["final"] = f if (f is not None and e["si"] != latest and f.freshness() >= e["win"].freshness()) else e["win"]
    res = []
    for k, e in out.items():
        common = [m for m in PRIMARY if m in e["common"]]
        final = e["final"]
        sig_final = tuple((m, tuple(final.metrics[m])) for m in common if m in final.metrics)
        if not sig_final:
            continue
        seen, values, sources = set(), [], []
        for (url, sig, _s), (si, r) in sorted(e["rows"].items(), key=lambda kv: (kv[1][0], kv[0][0])):
            sig = tuple(x for x in sig if x[0] in common)
            text = _fmt(sig)
            if text not in seen:
                seen.add(text)
                values.append(text)
            quote = clean(" | ".join(r.cells))[:160]
            sources.append((url, engine.snap_ids[si], quote))
        if len(values) < 2:
            continue
        fin_text = _fmt(sig_final)
        stale = [r for (u, sg, _s), (si, r) in e["rows"].items() if _sig(r, common) != tuple(x for x in sig_final if x[0] in common)]
        stale_txt = ", ".join(sorted({f"{r.url.split('.com')[-1] or '/'}" + (f" (as of {r.stamp})" if r.stamp else "") for r in stale})[:3])
        fu = final.url.split(".com")[-1] or "/"
        if any(r.freshness() != final.freshness() for r in stale):
            reason = (f"Newest effective date wins: {fu}" + (f" is dated {final.stamp}" if final.stamp else " is the latest copy")
                      + f", while {stale_txt} still show an older figure.")
        else:
            reason = (f"{fu} and {stale_txt} carry the same effective date; the official rate sheet / product page "
                      f"({fu}) is treated as authoritative over the other copy.")
        if fin_text not in seen:
            values.append(fin_text)
        res.append({"topic": f"{e['name']} ({', '.join(_NAME[m] for m in common)})", "values": values,
                    "sources": sources[:6], "resolution": fin_text, "reason": reason})
    return res


# ------------------------------------------------------------------------------ prose claims
_BRANCH = re.compile(r"\b(\d{2})\s+(?:branch office locations|branch locations|branches)\b", re.I)


def branch_count_conflict(passages, snap_id: str):
    """The branch count is repeated in press-release boilerplate that was written on different
    dates, so one site states several different counts. The newest *dated* page wins."""
    seen = {}
    for p in passages:
        m = _BRANCH.search(p.text)
        if not m or p.ptype == "rates":
            continue
        seen.setdefault((int(m.group(1)), p.url), p)
    if len({n for n, _ in seen}) < 2:
        return None
    dated = [(p.when, n, p) for (n, _), p in seen.items() if p.when]
    if not dated:
        return None
    dated.sort(key=lambda x: (x[0], x[1]), reverse=True)
    when, win, wp = dated[0]
    counts = sorted({n for n, _ in seen}, reverse=True)
    values = [f"{n} branch office locations" for n in counts]
    srcs, used = [], set()
    for (n, url), p in sorted(seen.items(), key=lambda kv: (-kv[0][0], kv[0][1])):
        if n in used:
            continue
        used.add(n)
        srcs.append((url, snap_id, p.text[:200]))
    return {"topic": "Number of Dupaco branch office locations", "values": values, "sources": srcs[:6],
            "resolution": f"{win} branch office locations",
            "reason": f"Press releases written at different times quote different branch counts; the newest dated page "
                      f"({wp.url.split('.com')[-1]}, {when}) says {win}, so older figures are out of date."}
