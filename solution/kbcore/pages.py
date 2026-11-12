"""URL canonicalisation and page classification (type, authority, scope)."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

# Authority is how much we trust a page *type* to carry the current official value.
AUTH = {"rates": 5, "product": 5, "landing": 3, "home": 3, "calculator": 2, "resource": 1,
        "news": 1, "blog": 1, "file": 1, "other": 1}


def canon(url: str) -> tuple[str, str]:
    """(host, path) with no scheme/query/fragment/trailing slash; root path is ''."""
    s = urlsplit(url)
    host = s.netloc.lower()
    path = re.sub(r"/+$", "", s.path or "")
    return host, path


def canon_url(url: str) -> str:
    host, path = canon(url)
    return f"https://{host}{path or '/'}"


def classify(url: str) -> str:
    host, p = canon(url)
    p = p.lower()
    if host and not host.endswith("dupaco.com"):
        return "other"
    if p.startswith(("/hubfs", "/hs-fs", "/hs/")) or p.endswith((".pdf", ".xls", ".xlsx", ".doc", ".docx", ".csv")):
        return "file"
    if p.startswith("/learn/blog") or re.match(r"^/\d{4}/\d\d/", p):
        return "blog"
    if p.startswith("/newsroom"):
        return "news"
    if p.startswith("/business/resources") or p.startswith("/learn"):
        return "resource"
    if p.startswith("/calculators") or "calculator" in p:
        return "calculator"
    if p in ("/rates", "/business-rates"):
        return "rates"
    if p == "":
        return "home"
    if p.startswith(("/personal", "/business", "/connect", "/about")):
        return "product"
    if p.count("/") == 1 or p.startswith("/savings-account"):
        return "landing"
    return "other"


def scope_of(url: str) -> str:
    _, p = canon(url)
    return "business" if "business" in p.lower() else "personal"
