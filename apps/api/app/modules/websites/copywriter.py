"""Builds initial site content from supplied business facts only.

Deterministic template copy is the default (generation_mode='template'). If OLLAMA_BASE_URL is set and
reachable, a local model may rewrite the hero/about wording (generation_mode='ai'); it is instructed to use
only the given facts, and its output is length-limited and still HTML-escaped at render time.
Missing facts become clearly marked "[Add your ...]" placeholders; nothing is invented.
"""
import json
import logging
import os

import httpx

log = logging.getLogger(__name__)

INDUSTRY_LABELS = {
    "real_estate": "Real estate", "architecture": "Architecture", "interior_design": "Interior design",
    "construction": "Construction", "restaurant": "Restaurant", "retail": "Retail", "healthcare": "Healthcare",
    "education": "Education", "corporate": "Corporate", "professional_services": "Professional services",
    "general": "",
}


def _p(v, what: str) -> str:
    return v.strip() if isinstance(v, str) and v.strip() else f"[Add your {what}]"


def build_content(facts: dict, template: dict) -> dict:
    name = facts["name"].strip()
    city = (facts.get("city") or "").strip()
    industry_label = facts.get("industry") or INDUSTRY_LABELS.get(template["industry"], "")
    business = {
        "name": name, "industry_label": industry_label, "tagline": facts.get("tagline"),
        "description": facts.get("description"), "city": city or None, "address": facts.get("address"),
        "country": facts.get("country"), "phone": facts.get("phone"), "email": facts.get("email"),
        "hours": facts.get("hours"), "whatsapp_number": facts.get("whatsapp_number"),
        "whatsapp_authorized": bool(facts.get("whatsapp_authorized")) and bool(facts.get("whatsapp_number")),
    }
    services = [s.strip() for s in (facts.get("services") or []) if isinstance(s, str) and s.strip()][:12]
    service_items = [{"title": s, "description": "[Add your description of this service]"} for s in services] or [
        {"title": "[Add your service]", "description": "[Add your description of this service]"}
        for _ in range(3)]
    where = f" in {city}" if city else ""
    hero_sub = facts.get("tagline") or facts.get("description") or "[Add your tagline]"
    about_body = facts.get("description") or "[Add your business description: who you are, how long you have been " \
                                              "operating and what makes your work different]"
    sections = []
    for s in template["sections"]:
        sec = {"type": s["type"], "heading": s["heading"], "enabled": True}
        t = s["type"]
        if t == "hero":
            sec.update(heading=name, body=hero_sub, cta_label=template["theme"].get("hero_cta"))
        elif t == "services":
            sec["items"] = service_items
        elif t == "about":
            sec.update(heading=f"About {name}", body=about_body)
        elif t == "gallery":
            sec["items"] = [{"title": "[Add your photo]"} for _ in range(3)]
        elif t == "contact":
            sec["body"] = f"We'd be glad to hear from you{where}."
        elif t == "cta":
            sec["body"] = f"Get in touch with {name}{where} today."
        sections.append(sec)
    desc_src = facts.get("description") or facts.get("tagline")
    seo_desc = (desc_src[:155] if desc_src else
                f"{name}{(' · ' + industry_label) if industry_label else ''}{where}. Contact us to learn more.")
    return {
        "business": business,
        "seo": {"title": (name + (f" | {industry_label}" if industry_label else "")
                          + (f" in {city}" if city else ""))[:70],
                "description": seo_desc},
        "sections": sections,
    }


def try_ai_polish(content: dict, facts: dict) -> bool:
    """Optionally rewrite hero subheading + about body with a local Ollama model. Returns True on success."""
    base = (os.environ.get("OLLAMA_BASE_URL") or os.environ.get("OLLAMA_URL"))
    if not base or not (facts.get("description") or facts.get("tagline")):
        return False
    model = os.environ.get("OLLAMA_MODEL", "llama3.1")
    known = {k: v for k, v in facts.items() if v and k in
             ("name", "industry", "city", "tagline", "description", "services")}
    prompt = ("Write website copy for a small business using ONLY these facts. Do not invent awards, years, "
              "ratings, clients, testimonials, certifications or numbers. Reply as JSON "
              '{"hero_subheading": "<max 160 chars>", "about": "<max 600 chars>"}.\nFacts: ' + json.dumps(known))
    try:
        r = httpx.post(f"{base.rstrip('/')}/api/chat", timeout=20, json={
            "model": model, "stream": False, "format": "json",
            "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        out = json.loads(r.json()["message"]["content"])
        hero, about = str(out.get("hero_subheading") or "")[:160], str(out.get("about") or "")[:600]
    except Exception as exc:  # unreachable / malformed: fall back to template copy
        log.info("Ollama copy generation unavailable: %s", exc)
        return False
    if not hero or not about:
        return False
    for s in content["sections"]:
        if s["type"] == "hero":
            s["body"] = hero
        elif s["type"] == "about":
            s["body"] = about
    return True
