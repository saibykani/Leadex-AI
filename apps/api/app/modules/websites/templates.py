"""Built-in website templates. Pure data: imported by the service and by migration 0008 for seeding.

Each template is a distinct design (palette, typography, hero layout, services layout, shapes).
No stock photos or third-party images are used: visuals are CSS gradients and inline SVG icons.
"""

SERIF = "Georgia, 'Times New Roman', serif"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
ROUNDED = "ui-rounded, 'SF Pro Rounded', -apple-system, 'Segoe UI', Roboto, sans-serif"
MONO_HEAD = "'Helvetica Neue', Helvetica, Arial, sans-serif"

DEFAULT_ORDER = ["hero", "services", "about", "gallery", "contact", "cta"]


def _t(key, industry, name, theme, order=None, labels=None):
    lab = {"services": "Services", "about": "About us", "gallery": "Our work", "contact": "Get in touch",
           "cta": "Ready to talk?", "hero_cta": "Contact us"}
    lab.update(labels or {})
    return {
        "key": key, "industry": industry, "name": name,
        "sections": [{"type": s, "heading": lab.get(s, s.title())} for s in (order or DEFAULT_ORDER)],
        "theme": {"hero_cta": lab["hero_cta"], **theme},
    }


TEMPLATES: list[dict] = [
    _t("real_estate", "real_estate", "Skyline Estates", {
        "primary": "#0f2a44", "accent": "#c8a24a", "bg": "#ffffff", "surface": "#f5f3ee", "text": "#14202b",
        "muted": "#5b6670", "font": SANS, "heading_font": SERIF, "radius": "4px", "hero": "split",
        "services_layout": "cards", "gradient": "linear-gradient(135deg,#0f2a44 0%,#1f4e79 60%,#c8a24a 140%)",
    }, labels={"services": "Properties & services", "gallery": "Featured listings", "hero_cta": "Book a viewing"}),
    _t("architecture", "architecture", "Monolith Studio", {
        "primary": "#111111", "accent": "#e4572e", "bg": "#fafafa", "surface": "#ffffff", "text": "#111111",
        "muted": "#666666", "font": MONO_HEAD, "heading_font": MONO_HEAD, "radius": "0px", "hero": "minimal",
        "services_layout": "list", "gradient": "linear-gradient(90deg,#111 0%,#333 100%)",
    }, order=["hero", "about", "gallery", "services", "contact", "cta"],
        labels={"services": "Practice", "about": "Studio", "gallery": "Selected projects",
                "hero_cta": "Start a project"}),
    _t("interior_design", "interior_design", "Linen & Oak", {
        "primary": "#6b4f3a", "accent": "#d9a68c", "bg": "#fbf8f4", "surface": "#f1e9df", "text": "#2f2620",
        "muted": "#7d6e62", "font": SANS, "heading_font": SERIF, "radius": "24px", "hero": "centered",
        "services_layout": "cards", "gradient": "linear-gradient(160deg,#f1e9df 0%,#d9a68c 100%)",
    }, order=["hero", "gallery", "services", "about", "contact", "cta"],
        labels={"gallery": "Spaces we've shaped", "hero_cta": "Book a consultation"}),
    _t("construction", "construction", "Ironbuild", {
        "primary": "#1d1d1f", "accent": "#f5b700", "bg": "#ffffff", "surface": "#f2f2f2", "text": "#1d1d1f",
        "muted": "#555555", "font": SANS, "heading_font": MONO_HEAD, "radius": "2px", "hero": "overlay",
        "services_layout": "grid", "gradient": "repeating-linear-gradient(135deg,#1d1d1f 0 22px,#2a2a2c 22px 44px)",
    }, labels={"services": "What we build", "gallery": "Recent projects", "hero_cta": "Request a quote"}),
    _t("restaurant", "restaurant", "Ember Table", {
        "primary": "#7a1f1f", "accent": "#f2a541", "bg": "#fffaf3", "surface": "#fbeedd", "text": "#2b1a12",
        "muted": "#7b6555", "font": SANS, "heading_font": SERIF, "radius": "16px", "hero": "overlay",
        "services_layout": "menu", "gradient": "radial-gradient(circle at 30% 20%,#f2a541 0%,#7a1f1f 55%,#2b1a12 100%)",
    }, labels={"services": "On the menu", "gallery": "From our kitchen", "hero_cta": "Reserve a table"}),
    _t("retail", "retail", "Corner Shop", {
        "primary": "#ff3b6b", "accent": "#5e5ce6", "bg": "#ffffff", "surface": "#fff0f4", "text": "#1c1c1e",
        "muted": "#6e6e73", "font": ROUNDED, "heading_font": ROUNDED, "radius": "20px", "hero": "split",
        "services_layout": "grid", "gradient": "linear-gradient(135deg,#ff3b6b 0%,#5e5ce6 100%)",
    }, labels={"services": "Shop by category", "gallery": "In store", "hero_cta": "Visit us"}),
    _t("clinic", "healthcare", "CarePoint Clinic", {
        "primary": "#0a7ea4", "accent": "#34c759", "bg": "#ffffff", "surface": "#eef7fa", "text": "#10242c",
        "muted": "#58707a", "font": SANS, "heading_font": SANS, "radius": "14px", "hero": "centered",
        "services_layout": "list", "gradient": "linear-gradient(180deg,#eef7fa 0%,#ffffff 100%)",
    }, order=["hero", "services", "about", "contact", "gallery", "cta"],
        labels={"services": "Treatments & care", "gallery": "Our facility", "hero_cta": "Book an appointment"}),
    _t("education", "education", "Brightpath Academy", {
        "primary": "#3a3ab8", "accent": "#ffcc00", "bg": "#ffffff", "surface": "#f3f3ff", "text": "#161640",
        "muted": "#5c5c80", "font": ROUNDED, "heading_font": ROUNDED, "radius": "18px", "hero": "split",
        "services_layout": "cards", "gradient": "linear-gradient(135deg,#3a3ab8 0%,#7b61ff 100%)",
    }, labels={"services": "Programs & courses", "gallery": "Campus life", "hero_cta": "Enquire about admission"}),
    _t("corporate", "corporate", "Meridian Corporate", {
        "primary": "#1b2a4a", "accent": "#0a84ff", "bg": "#ffffff", "surface": "#f5f7fb", "text": "#101828",
        "muted": "#5a6478", "font": SANS, "heading_font": SANS, "radius": "10px", "hero": "centered",
        "services_layout": "grid", "gradient": "linear-gradient(120deg,#1b2a4a 0%,#0a84ff 100%)",
    }, labels={"services": "Capabilities", "gallery": "Case highlights", "hero_cta": "Talk to our team"}),
    _t("professional_services", "professional_services", "Counsel & Co.", {
        "primary": "#24343b", "accent": "#2f8f83", "bg": "#fcfcfa", "surface": "#eef2f0", "text": "#1a2326",
        "muted": "#5d6a6e", "font": SANS, "heading_font": SERIF, "radius": "6px", "hero": "minimal",
        "services_layout": "list", "gradient": "linear-gradient(135deg,#24343b 0%,#2f8f83 100%)",
    }, order=["hero", "services", "about", "contact", "gallery", "cta"],
        labels={"services": "Practice areas", "gallery": "Our office", "hero_cta": "Schedule a consultation"}),
    _t("general_smb", "general", "Everyday Business", {
        "primary": "#0071e3", "accent": "#ff9f0a", "bg": "#ffffff", "surface": "#f5f5f7", "text": "#1d1d1f",
        "muted": "#6e6e73", "font": SANS, "heading_font": SANS, "radius": "18px", "hero": "centered",
        "services_layout": "cards", "gradient": "linear-gradient(135deg,#0071e3 0%,#5e5ce6 100%)",
    }),
]

TEMPLATE_KEYS = [t["key"] for t in TEMPLATES]
BY_KEY = {t["key"]: t for t in TEMPLATES}
