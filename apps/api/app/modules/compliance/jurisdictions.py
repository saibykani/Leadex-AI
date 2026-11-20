"""Conservative default jurisdiction profiles (seeded by migration 0005; also used as an in-code fallback).

These are engineering defaults, NOT legal advice. Every channel requires a recorded consent by default.
`calling_window` is [start_hour, end_hour) in the recipient's local time. `utc_offsets` lists the standard-time
offsets spanned by the jurisdiction; a call is only allowed if it is inside the window in EVERY listed zone
(DST is ignored, which is why windows are narrow enough to tolerate a one-hour shift only partially -- see
known limitations). DNC registries are named for operator awareness only: no registry is queried.
"""

EU_COUNTRIES = frozenset(
    "AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE".split()
)

ALL_CHANNELS = ("voice", "email", "whatsapp", "sms")


def _rules(window, dnc, recording, offsets, ai=True):
    msg = {"requires_consent": True, "ai_disclosure_required": ai}
    return {
        "utc_offsets": offsets,
        "voice": {"requires_consent": True, "calling_window": window, "dnc_registry": dnc,
                  "ai_disclosure_required": ai, "recording_consent": recording},
        "sms": {**msg, "calling_window": window, "dnc_registry": dnc},
        "whatsapp": dict(msg),
        "email": dict(msg),
    }


DEFAULT_PROFILES: dict[str, dict] = {
    "IN": {"name": "India", "rules": _rules([9, 21], "TRAI NCPR (DND)", "one_party_disclosed", [5.5])},
    "US": {"name": "United States", "rules": _rules([8, 21], "National Do Not Call Registry", "all_party",
                                                    [-5, -6, -7, -8, -10])},
    "UK": {"name": "United Kingdom", "rules": _rules([8, 21], "TPS / CTPS", "all_party", [0])},
    "EU": {"name": "European Union", "rules": _rules([9, 20], "National Robinson lists", "all_party", [0, 1, 2])},
    "CA": {"name": "Canada", "rules": _rules([9, 21], "National DNCL", "all_party",
                                             [-3.5, -4, -5, -6, -7, -8])},
    "AU": {"name": "Australia", "rules": _rules([9, 20], "Do Not Call Register", "all_party", [8, 9.5, 10])},
    # Unknown time zone: voice is blocked by the calling-window check (no offsets).
    "DEFAULT": {"name": "Default (most restrictive)", "rules": _rules([10, 17], "unknown", "all_party", [])},
}


def jurisdiction_code(country: str | None) -> str | None:
    if not country:
        return None
    c = country.strip().upper()
    if c in {"GB", "UK"}:
        return "UK"
    if c in EU_COUNTRIES:
        return "EU"
    if c in DEFAULT_PROFILES:
        return c
    return "DEFAULT"
