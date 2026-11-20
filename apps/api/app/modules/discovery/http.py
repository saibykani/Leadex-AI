"""Single construction point for outbound HTTP clients so tests can inject httpx.MockTransport."""
import httpx

# Tests set this to an httpx.MockTransport. None = real network.
transport: httpx.BaseTransport | None = None

USER_AGENT = "LeadexAI-WebsiteAudit/1.0"


def client(timeout: float, follow_redirects: bool = True) -> httpx.Client:
    return httpx.Client(timeout=timeout, transport=transport, follow_redirects=follow_redirects,
                        headers={"User-Agent": USER_AGENT})
