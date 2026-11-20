"""Explainable website audit.

Fetches the homepage once (with up to 2 retries on network errors), then checks a handful of same-site links.
A network failure NEVER means "no website": the business is marked `unreachable_retry`.
Every score point is backed by a finding with a human-readable explanation.
"""
import ipaddress
import re
import socket
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

import httpx

from app.modules.discovery import http
from app.modules.discovery.config import get_discovery_settings

MAX_BYTES = 2_000_000
MAX_LINKS = 5

# (key, max points, label)
CHECKS = (
    ("reachable", 25, "Website responds successfully"),
    ("ssl_valid", 15, "Served over valid HTTPS"),
    ("mobile_viewport", 15, "Mobile viewport meta tag"),
    ("has_title", 10, "Page title present"),
    ("has_meta_description", 10, "Meta description present"),
    ("has_contact_info", 10, "Contact information visible"),
    ("has_cta", 10, "Clear call to action"),
    ("fast_load", 5, "Homepage loads in under 3 seconds"),
)
BROKEN_LINK_PENALTY = 2

_CTA = re.compile(r"\b(contact us|call now|book( now| an appointment| online)?|get (a )?quote|request (a )?quote|"
                  r"schedule|order now|buy now|enquire|enquiry|sign up|get started)\b", re.I)
_EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
_PHONE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")


class BlockedTarget(Exception):
    pass


def guard_target(url: str) -> None:
    """SSRF guard: refuse non-http(s) URLs and hosts resolving to private/loopback/link-local addresses.
    (Limitation: DNS rebinding between this check and the fetch is not prevented.)"""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise BlockedTarget("Only http(s) URLs can be audited")
    try:
        infos = socket.getaddrinfo(parts.hostname, None)
    except socket.gaierror as e:
        raise httpx.ConnectError(f"DNS resolution failed for {parts.hostname}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise BlockedTarget("Target resolves to a non-public address")


def normalize_url(url: str) -> str:
    u = url.strip()
    return u if "://" in u else f"https://{u}"


@dataclass
class AuditResult:
    url: str
    final_url: str | None = None
    reachable: bool = False
    http_status: int | None = None
    ssl_valid: bool | None = None
    mobile_viewport: bool | None = None
    load_ms: int | None = None
    has_contact_info: bool | None = None
    has_cta: bool | None = None
    has_title: bool | None = None
    has_meta_description: bool | None = None
    broken_links_checked: int = 0
    broken_links_found: int = 0
    score: int | None = None
    findings: list = field(default_factory=list)
    error: str | None = None
    attempts: int = 0
    network_failure: bool = False


def _fetch(c: httpx.Client, url: str, retries: int) -> tuple[httpx.Response, int, int]:
    last: Exception | None = None
    for attempt in range(1, retries + 2):
        try:
            guard_target(url)
            t0 = time.perf_counter()
            r = c.get(url)
            return r, int((time.perf_counter() - t0) * 1000), attempt
        except BlockedTarget:
            raise
        except httpx.HTTPError as e:
            last = e
            last_attempt = attempt
    err = httpx.TransportError(f"{type(last).__name__}: {last}")
    err.attempts = last_attempt  # type: ignore[attr-defined]
    raise err


def _links(html: str, base: str) -> list[str]:
    host = urlsplit(base).hostname
    out: list[str] = []
    for href in re.findall(r'<a\s[^>]*href=["\']([^"\'#]+)["\']', html, re.I):
        u = urljoin(base, href)
        if urlsplit(u).scheme in ("http", "https") and urlsplit(u).hostname == host and u not in out and u != base:
            out.append(u)
        if len(out) >= MAX_LINKS:
            break
    return out


def run_audit(url: str) -> AuditResult:
    s = get_discovery_settings()
    url = normalize_url(url)
    res = AuditResult(url=url)
    with http.client(s.http_timeout_s) as c:
        try:
            r, load_ms, attempts = _fetch(c, url, s.audit_max_retries)
        except BlockedTarget as e:
            res.error, res.attempts = str(e), 0
            res.findings = [{"check": "reachable", "passed": False, "points": 0, "max_points": 25,
                             "explanation": f"Audit refused: {e}."}]
            res.score = None
            return res
        except httpx.HTTPError as e:
            if url.startswith("https://"):
                # some small-business sites only serve plain HTTP; try once before giving up
                try:
                    r, load_ms, attempts = _fetch(c, "http://" + url[8:], 0)
                    attempts += s.audit_max_retries + 1
                except (httpx.HTTPError, BlockedTarget):
                    return _unreachable(res, e)
            else:
                return _unreachable(res, e)
        res.attempts, res.load_ms, res.http_status = attempts, load_ms, r.status_code
        res.final_url = str(r.url)
        res.reachable = r.status_code < 400
        res.ssl_valid = res.final_url.startswith("https://")  # httpx verifies certificates by default
        html = r.text[:MAX_BYTES] if "html" in r.headers.get("content-type", "html") else ""
        res.has_title = bool(re.search(r"<title[^>]*>\s*\S[^<]*</title>", html, re.I))
        res.has_meta_description = bool(
            re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']\s*\S', html, re.I)
            or re.search(r'<meta[^>]+content=["\']\s*\S[^>]+name=["\']description["\']', html, re.I))
        res.mobile_viewport = bool(re.search(r'<meta[^>]+name=["\']viewport["\']', html, re.I))
        text = re.sub(r"<[^>]+>", " ", html)
        res.has_contact_info = bool(re.search(r'href=["\'](tel:|mailto:)', html, re.I) or _EMAIL.search(text)
                                    or _PHONE.search(text))
        res.has_cta = bool(_CTA.search(text))
        if res.reachable:
            for link in _links(html, res.final_url):
                res.broken_links_checked += 1
                try:
                    guard_target(link)
                    lr = c.head(link)
                    if lr.status_code == 405:
                        lr = c.get(link)
                    if lr.status_code >= 400:
                        res.broken_links_found += 1
                except (httpx.HTTPError, BlockedTarget):
                    res.broken_links_found += 1
    _score(res)
    return res


def _unreachable(res: AuditResult, e: Exception) -> AuditResult:
    res.network_failure = True
    res.attempts = getattr(e, "attempts", 1)
    res.error = str(e)[:500]
    res.findings = [{"check": "reachable", "passed": False, "points": 0, "max_points": 25,
                     "explanation": "The website could not be reached after retries (network error). This does NOT "
                                    "mean the business has no website; the audit should be retried later."}]
    return res


def _score(res: AuditResult) -> None:
    passed = {
        "reachable": res.reachable,
        "ssl_valid": bool(res.ssl_valid) and res.reachable,
        "mobile_viewport": bool(res.mobile_viewport),
        "has_title": bool(res.has_title),
        "has_meta_description": bool(res.has_meta_description),
        "has_contact_info": bool(res.has_contact_info),
        "has_cta": bool(res.has_cta),
        "fast_load": res.reachable and res.load_ms is not None and res.load_ms < 3000,
    }
    why = {
        "reachable": (f"Homepage returned HTTP {res.http_status}.",
                      f"Homepage returned HTTP {res.http_status}; visitors see an error."),
        "ssl_valid": ("Site is served over HTTPS with a certificate that verified.",
                      "Site is not served over valid HTTPS; browsers may warn visitors."),
        "mobile_viewport": ("A viewport meta tag is set, so the page can adapt to phones.",
                            "No viewport meta tag; the page likely renders poorly on phones."),
        "has_title": ("The page has a <title>.", "The page has no <title>, which hurts search results."),
        "has_meta_description": ("A meta description is present for search snippets.",
                                 "No meta description; search engines will guess the snippet."),
        "has_contact_info": ("A phone number, email or tel:/mailto: link is visible.",
                             "No phone number or email found on the homepage."),
        "has_cta": ("A call to action (e.g. 'Contact us', 'Book now') was found.",
                    "No clear call to action found on the homepage."),
        "fast_load": (f"Homepage loaded in {res.load_ms} ms.",
                      f"Homepage took {res.load_ms} ms to load (target < 3000 ms)."),
    }
    total = 0
    findings = []
    for key, pts, label in CHECKS:
        ok = bool(passed[key])
        total += pts if ok else 0
        findings.append({"check": key, "label": label, "passed": ok, "points": pts if ok else 0, "max_points": pts,
                         "explanation": why[key][0 if ok else 1]})
    if res.broken_links_checked:
        penalty = min(10, res.broken_links_found * BROKEN_LINK_PENALTY)
        total -= penalty
        findings.append({"check": "broken_links", "label": "Internal links work",
                         "passed": res.broken_links_found == 0, "points": -penalty, "max_points": 0,
                         "explanation": f"{res.broken_links_found} of {res.broken_links_checked} checked internal "
                                        f"links were broken (-{BROKEN_LINK_PENALTY} each, max -10)."})
    res.score = max(0, min(100, total))
    res.findings = findings
