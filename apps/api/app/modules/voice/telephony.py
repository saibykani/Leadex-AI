"""Telephony adapters.

`TelephonyAdapter` is the provider-neutral interface used by voice.service. `TwilioAdapter` places outbound calls via
the Twilio REST API (httpx, no SDK) and the conversation runs over TwiML webhooks (<Gather input="speech"> + <Say>),
see voice.webhooks. A LiveKit/SIP adapter can implement the same interface later.

Credentials: per-org integration "twilio" (account_sid, auth_token, from_number[, escalation_number]) via
administration.get_credential, falling back to env TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM_NUMBER.
Webhooks need a public HTTPS base URL (PUBLIC_WEBHOOK_BASE_URL, e.g. a cloudflared/ngrok tunnel to the API).

Status:  not_configured | needs_public_url | configured  (+ mode: live | test_allowlist | simulated)
"""
import base64
import hashlib
import hmac
import re
import uuid
from dataclasses import dataclass
from typing import Protocol

import httpx
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.orm import Session

from app.core.config import get_settings

API_PREFIX = "/api/v1"


class TelephonySettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")

    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None
    twilio_escalation_number: str | None = None
    twilio_api_base: str = "https://api.twilio.com"
    twilio_machine_detection: bool = False
    public_webhook_base_url: str | None = None
    allow_test_calls: bool = False
    test_call_allowlist: str = ""
    telephony_max_turns: int = 12
    telephony_llm_budget_s: float = 8.0

    @field_validator("twilio_account_sid", "twilio_auth_token", "twilio_from_number", "twilio_escalation_number",
                     "public_webhook_base_url", mode="before")
    @classmethod
    def empty_is_none(cls, v):
        return (v or "").strip() or None

    @property
    def allowlist(self) -> set[str]:
        return {n for n in (to_e164(x.strip(), None) for x in self.test_call_allowlist.split(",")) if n}

    @property
    def public_base(self) -> str | None:
        u = (self.public_webhook_base_url or "").rstrip("/")
        return u if u.startswith("https://") and len(u) > len("https://") else None


def telephony_settings() -> TelephonySettings:
    return TelephonySettings()


# Tests inject an httpx.MockTransport here; production leaves it None (real network).
http_transport: httpx.BaseTransport | None = None

# ------------------------------------------------------------------ phone numbers
_CC = {"IN": "91", "US": "1", "CA": "1", "GB": "44", "AE": "971", "AU": "61", "SG": "65", "DE": "49", "FR": "33",
       "NZ": "64", "ZA": "27", "SA": "966", "QA": "974", "MY": "60", "PH": "63", "IE": "353", "NL": "31", "ES": "34",
       "IT": "39", "BR": "55", "MX": "52", "JP": "81", "NP": "977", "LK": "94", "BD": "880", "PK": "92"}
_NATIONAL_LEN = {"IN": 10, "US": 10, "CA": 10, "GB": 10, "AU": 9, "AE": 9, "SG": 8}


def to_e164(raw: str | None, country: str | None) -> str | None:
    """Best-effort E.164 normalisation using the lead country. Returns None if the number cannot be normalised."""
    if not raw or not raw.strip():
        return None
    s = raw.strip()
    plus = s.startswith("+") or s.startswith("00")
    digits = re.sub(r"\D", "", s)
    if s.startswith("00"):
        digits = digits[2:]
    if plus:
        return f"+{digits}" if 8 <= len(digits) <= 15 else None
    cc_country = (country or "").upper()
    cc = _CC.get(cc_country)
    if not cc:
        return None
    national = digits.lstrip("0")
    want = _NATIONAL_LEN.get(cc_country)
    if national.startswith(cc) and (want is None or len(national) == len(cc) + want):
        full = national
    else:
        if want is not None and len(national) != want:
            return None
        full = cc + national
    return f"+{full}" if 8 <= len(full) <= 15 else None


# ------------------------------------------------------------------ adapter interface
@dataclass
class DialResult:
    ok: bool
    provider_call_id: str | None = None
    status: str | None = None
    error: str | None = None  # provider error text, verbatim


@dataclass
class AdapterStatus:
    provider: str
    status: str  # not_configured | needs_public_url | configured
    credential_source: str | None  # org | env | None
    from_number: str | None
    public_base_url: str | None
    detail: str


class TelephonyAdapter(Protocol):
    name: str

    def status(self) -> AdapterStatus: ...

    def place_call(self, *, call_id: uuid.UUID, to: str, record: bool) -> DialResult: ...


@dataclass
class TwilioCreds:
    account_sid: str
    auth_token: str
    from_number: str | None
    escalation_number: str | None
    source: str  # org | env


def load_twilio_creds(db: Session, org_id: uuid.UUID) -> TwilioCreds | None:
    from app.modules.administration.router import get_credential

    s = telephony_settings()
    sid, tok = get_credential(db, org_id, "twilio", "account_sid"), get_credential(db, org_id, "twilio", "auth_token")
    if sid and tok:
        return TwilioCreds(sid, tok, get_credential(db, org_id, "twilio", "from_number") or s.twilio_from_number,
                           get_credential(db, org_id, "twilio", "escalation_number") or s.twilio_escalation_number,
                           "org")
    if s.twilio_account_sid and s.twilio_auth_token:
        return TwilioCreds(s.twilio_account_sid, s.twilio_auth_token, s.twilio_from_number,
                           s.twilio_escalation_number, "env")
    return None


def webhook_url(kind: str, call_id: uuid.UUID) -> str:
    """kind: voice | turn | status. Only valid when a public base is configured."""
    base = telephony_settings().public_base or ""
    return f"{base}{API_PREFIX}/telephony/twilio/{kind}/{call_id}"


class TwilioAdapter:
    name = "twilio"

    def __init__(self, creds: TwilioCreds | None):
        self.creds = creds
        self.settings = telephony_settings()

    def status(self) -> AdapterStatus:
        c, base = self.creds, self.settings.public_base
        if c is None or not c.from_number:
            missing = "account_sid/auth_token" if c is None else "from_number"
            return AdapterStatus("twilio", "not_configured", c.source if c else None, None, base,
                                 f"Twilio {missing} missing (org integration 'twilio' or TWILIO_* env).")
        if base is None:
            return AdapterStatus("twilio", "needs_public_url", c.source, c.from_number, None,
                                 "Set PUBLIC_WEBHOOK_BASE_URL to a public https:// URL that reaches this API "
                                 "(e.g. a cloudflared or ngrok tunnel to localhost:8010).")
        return AdapterStatus("twilio", "configured", c.source, c.from_number, base, "Ready")

    def place_call(self, *, call_id: uuid.UUID, to: str, record: bool) -> DialResult:
        st = self.status()
        if st.status != "configured":
            return DialResult(False, error=st.detail)
        c = self.creds
        assert c is not None
        data = {"To": to, "From": c.from_number, "Url": webhook_url("voice", call_id), "Method": "POST",
                "StatusCallback": webhook_url("status", call_id), "StatusCallbackMethod": "POST",
                "StatusCallbackEvent": ["initiated", "ringing", "answered", "completed"]}
        if self.settings.twilio_machine_detection:
            data["MachineDetection"] = "Enable"
        if record:  # only when recording consent was captured (enforced by the caller)
            data["Record"] = "true"
        url = f"{self.settings.twilio_api_base.rstrip('/')}/2010-04-01/Accounts/{c.account_sid}/Calls.json"
        try:
            with httpx.Client(transport=http_transport, timeout=15) as cl:
                r = cl.post(url, data=data, auth=(c.account_sid, c.auth_token))
        except httpx.HTTPError as e:
            return DialResult(False, error=f"Twilio unreachable: {type(e).__name__}")
        try:
            body = r.json()
        except ValueError:
            body = {}
        if r.status_code >= 400:
            msg = body.get("message") or r.text[:500] or f"HTTP {r.status_code}"
            code = body.get("code")
            return DialResult(False, error=f"Twilio error {code}: {msg}" if code else f"Twilio error: {msg}")
        return DialResult(True, provider_call_id=body.get("sid"), status=body.get("status"))


def adapter_for(db: Session, org_id: uuid.UUID) -> TwilioAdapter:
    return TwilioAdapter(load_twilio_creds(db, org_id))


def dial_mode(to: str | None) -> str:
    """live (production) | test_allowlist (non-prod, ALLOW_TEST_CALLS and number allow-listed) | simulated."""
    if get_settings().is_production:
        return "live"
    s = telephony_settings()
    if s.allow_test_calls and to and to in s.allowlist:
        return "test_allowlist"
    return "simulated"


# ------------------------------------------------------------------ signatures / TwiML
def twilio_signature(auth_token: str, url: str, params: list[tuple[str, str]]) -> str:
    """Twilio request signature: base64(HMAC-SHA1(auth_token, url + concat(sorted key+value)))."""
    payload = url + "".join(k + v for k, v in sorted(params, key=lambda kv: (kv[0], kv[1])))
    mac = hmac.new(auth_token.encode(), payload.encode(), hashlib.sha1)
    return base64.b64encode(mac.digest()).decode()


def valid_signature(auth_token: str, url: str, params: list[tuple[str, str]], signature: str | None) -> bool:
    if not signature:
        return False
    return hmac.compare_digest(twilio_signature(auth_token, url, params), signature)


INDIAN_LANGS = {"hi", "te", "ta", "kn", "ml", "mr", "bn", "gu"}


def say_language(agent_language: str, country: str | None) -> str:
    if agent_language in INDIAN_LANGS:
        return f"{agent_language}-IN"
    return "en-IN" if (country or "").upper() == "IN" else "en-US"


# Twilio <Say> voice catalogue (Amazon Polly + Google voices that Twilio supports). gender/tier are for the UI.
# tier "standard" = Twilio's basic TTS price; "neural"/"wavenet" sound more natural but Twilio may bill extra.
VOICES: list[dict] = [
    {"id": "Polly.Aditi", "label": "Aditi (Indian English + Hindi)", "gender": "female", "tier": "standard",
     "languages": ["en-IN", "hi-IN"]},
    {"id": "Polly.Raveena", "label": "Raveena (Indian English)", "gender": "female", "tier": "standard",
     "languages": ["en-IN"]},
    {"id": "Polly.Kajal-Neural", "label": "Kajal (natural, Indian English + Hindi)", "gender": "female",
     "tier": "neural", "languages": ["en-IN", "hi-IN"]},
    {"id": "Google.en-IN-Standard-A", "label": "Google Indian English A", "gender": "female", "tier": "standard",
     "languages": ["en-IN"]},
    {"id": "Google.en-IN-Standard-D", "label": "Google Indian English D", "gender": "female", "tier": "standard",
     "languages": ["en-IN"]},
    {"id": "Google.en-IN-Standard-B", "label": "Google Indian English B", "gender": "male", "tier": "standard",
     "languages": ["en-IN"]},
    {"id": "Google.en-IN-Standard-C", "label": "Google Indian English C", "gender": "male", "tier": "standard",
     "languages": ["en-IN"]},
    {"id": "Google.en-IN-Wavenet-A", "label": "Google Indian English A (natural)", "gender": "female",
     "tier": "wavenet", "languages": ["en-IN"]},
    {"id": "Google.hi-IN-Standard-A", "label": "Google Hindi A", "gender": "female", "tier": "standard",
     "languages": ["hi-IN"]},
    {"id": "Google.hi-IN-Standard-D", "label": "Google Hindi D", "gender": "female", "tier": "standard",
     "languages": ["hi-IN"]},
    {"id": "Google.hi-IN-Standard-B", "label": "Google Hindi B", "gender": "male", "tier": "standard",
     "languages": ["hi-IN"]},
    {"id": "Google.hi-IN-Wavenet-A", "label": "Google Hindi A (natural)", "gender": "female", "tier": "wavenet",
     "languages": ["hi-IN"]},
    {"id": "Google.ta-IN-Standard-A", "label": "Google Tamil A", "gender": "female", "tier": "standard",
     "languages": ["ta-IN"]},
    {"id": "Google.ta-IN-Standard-B", "label": "Google Tamil B", "gender": "male", "tier": "standard",
     "languages": ["ta-IN"]},
    {"id": "Google.te-IN-Standard-A", "label": "Google Telugu A", "gender": "female", "tier": "standard",
     "languages": ["te-IN"]},
    {"id": "Google.te-IN-Standard-B", "label": "Google Telugu B", "gender": "male", "tier": "standard",
     "languages": ["te-IN"]},
    {"id": "Google.kn-IN-Standard-A", "label": "Google Kannada A", "gender": "female", "tier": "standard",
     "languages": ["kn-IN"]},
    {"id": "Google.ml-IN-Standard-A", "label": "Google Malayalam A", "gender": "female", "tier": "standard",
     "languages": ["ml-IN"]},
    {"id": "Google.mr-IN-Standard-A", "label": "Google Marathi A", "gender": "female", "tier": "standard",
     "languages": ["mr-IN"]},
    {"id": "Google.bn-IN-Standard-A", "label": "Google Bengali A", "gender": "female", "tier": "standard",
     "languages": ["bn-IN"]},
    {"id": "Google.gu-IN-Standard-A", "label": "Google Gujarati A", "gender": "female", "tier": "standard",
     "languages": ["gu-IN"]},
    {"id": "Polly.Joanna", "label": "Joanna (US English)", "gender": "female", "tier": "standard",
     "languages": ["en-US"]},
    {"id": "Polly.Matthew", "label": "Matthew (US English)", "gender": "male", "tier": "standard",
     "languages": ["en-US"]},
]
_BY_ID = {v["id"]: v for v in VOICES}
# Female by default. Override per deployment with TWILIO_VOICE_<LANG> (e.g. TWILIO_VOICE_EN_IN=Polly.Kajal-Neural).
_DEFAULT_VOICES = {"en-IN": "Polly.Aditi", "hi-IN": "Polly.Aditi", "en-US": "Polly.Joanna",
                   "ta-IN": "Google.ta-IN-Standard-A", "te-IN": "Google.te-IN-Standard-A",
                   "kn-IN": "Google.kn-IN-Standard-A", "ml-IN": "Google.ml-IN-Standard-A",
                   "mr-IN": "Google.mr-IN-Standard-A", "bn-IN": "Google.bn-IN-Standard-A",
                   "gu-IN": "Google.gu-IN-Standard-A"}


def say_voice(lang: str, preferred: str | None = None) -> str | None:
    """The agent's chosen voice when it can speak `lang`, else the deployment/default female voice for `lang`."""
    import os

    if preferred and lang in (_BY_ID.get(preferred) or {}).get("languages", []):
        return preferred
    key = "TWILIO_VOICE_" + lang.replace("-", "_").upper()
    return os.getenv(key) or _DEFAULT_VOICES.get(lang) or os.getenv("TWILIO_VOICE_DEFAULT") or None
