"""Custom-domain helpers: hostname normalisation and DNS TXT lookup (monkeypatchable `lookup_txt`)."""
import ipaddress
import logging
import re

from app.core.errors import AppError

log = logging.getLogger(__name__)
VERIFY_PREFIX = "_leadex-verify"
_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")


def normalize_domain(raw: str) -> str:
    d = (raw or "").strip().lower().rstrip(".")
    if "://" in d or "/" in d or ":" in d or " " in d:
        raise AppError(422, "invalid_domain", "Enter a bare domain such as www.example.com (no scheme, path or port)")
    labels = d.split(".")
    if len(d) > 253 or len(labels) < 2 or not all(_LABEL.match(x) for x in labels) or labels[-1].isdigit():
        raise AppError(422, "invalid_domain", "Enter a valid domain name such as www.example.com")
    try:
        ipaddress.ip_address(d)
    except ValueError:
        return d
    raise AppError(422, "invalid_domain", "IP addresses are not supported; use a domain name")


def record_name(domain: str) -> str:
    return f"{VERIFY_PREFIX}.{domain}"


def lookup_txt(name: str) -> list[str]:
    """Return the TXT strings published at `name` (empty list when absent or on any DNS failure)."""
    import dns.exception
    import dns.resolver

    try:
        answers = dns.resolver.resolve(name, "TXT", lifetime=5.0)
    except (dns.exception.DNSException, OSError) as exc:
        log.info("TXT lookup for %s failed: %s", name, exc.__class__.__name__)
        return []
    return ["".join(part.decode("utf-8", "replace") for part in rdata.strings) for rdata in answers]


def txt_matches(domain: str, token: str) -> bool:
    return any(v.strip().strip('"') == token for v in lookup_txt(record_name(domain)))
