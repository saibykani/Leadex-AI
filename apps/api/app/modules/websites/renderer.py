"""Server-side renderer: content JSON + template theme -> one self-contained, mobile-first HTML document.

Every user-supplied value goes through `_e` (HTML escaping) or a strict sanitiser (phone digits, colours).
No external assets are referenced: CSS is inline and visuals are gradients / inline SVG.
"""
import html
import json
import re

_COLOR = re.compile(r"^#[0-9a-fA-F]{3,8}$")
PLACEHOLDER = re.compile(r"^\[Add your .*\]$", re.S)

ICONS = {
    "phone": '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 '
             '2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 '
             '0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z"/>',
    "chat": '<path d="M21 11.5a8.4 8.4 0 0 1-12.4 7.4L3 21l2.1-5.6A8.4 8.4 0 1 1 21 11.5z"/>',
    "star": '<path d="M12 2l3 7h7l-5.5 4.5L18.5 21 12 16.8 5.5 21l2-7.5L2 9h7z"/>',
    "pin": '<path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
}


def _e(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def _icon(name: str, size: int = 20) -> str:
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>')


def tel_digits(v) -> str:
    if not v:
        return ""
    s = re.sub(r"[^\d+]", "", str(v))
    s = s[:1] + s[1:].replace("+", "")
    return s if len(re.sub(r"\D", "", s)) >= 6 else ""


def is_real(v) -> bool:
    return bool(v) and not PLACEHOLDER.match(str(v).strip())


def _color(v, default: str) -> str:
    return v if isinstance(v, str) and _COLOR.match(v) else default


def _css(t: dict) -> str:
    c = {k: _color(t.get(k), d) for k, d in (("primary", "#0071e3"), ("accent", "#ff9f0a"), ("bg", "#ffffff"),
                                            ("surface", "#f5f5f7"), ("text", "#1d1d1f"), ("muted", "#6e6e73"))}
    font = re.sub(r"[^\w\s,'\-]", "", t.get("font", "sans-serif"))
    hfont = re.sub(r"[^\w\s,'\-]", "", t.get("heading_font", font))
    radius = t.get("radius") if re.match(r"^\d{1,2}px$", str(t.get("radius", ""))) else "12px"
    grad = t.get("gradient", "")
    if not re.match(r"^[a-z\-]+-gradient\([#\w\s,%.()\-]+\)$", grad):
        grad = f"linear-gradient(135deg,{c['primary']},{c['accent']})"
    mix = "color-mix(in srgb,var(--t) {}%,transparent)"
    return f""":root{{--p:{c['primary']};--a:{c['accent']};--bg:{c['bg']};--s:{c['surface']};--t:{c['text']};
--m:{c['muted']};--r:{radius};--g:{grad};--hf:{hfont};--f:{font}}}
*{{box-sizing:border-box;margin:0;padding:0}}html{{scroll-behavior:smooth}}
body{{font-family:var(--f);background:var(--bg);color:var(--t);line-height:1.6;-webkit-font-smoothing:antialiased}}
h1,h2,h3{{font-family:var(--hf);line-height:1.15;letter-spacing:-.01em}}
a{{color:inherit}}.wrap{{max-width:1120px;margin:0 auto;padding:0 20px}}
section{{padding:64px 0}}section h2{{font-size:clamp(1.6rem,4vw,2.4rem);margin-bottom:24px}}
.nav{{position:sticky;top:0;z-index:10;background:var(--bg);border-bottom:1px solid {mix.format(8)}}}
.nav .wrap{{display:flex;align-items:center;justify-content:space-between;height:60px;gap:12px}}
.brand{{font-family:var(--hf);font-weight:700;font-size:1.1rem;text-decoration:none}}
.nav-links{{display:none;gap:24px;font-size:.92rem;color:var(--m)}}.nav-links a{{text-decoration:none}}
.btn{{display:inline-flex;align-items:center;gap:8px;padding:12px 22px;border-radius:var(--r);background:var(--p);
color:#fff;text-decoration:none;font-weight:600;border:0;cursor:pointer;font-size:1rem}}
.btn.alt{{background:transparent;color:inherit;border:1.5px solid currentColor}}
.btn.sm{{padding:8px 16px;font-size:.9rem}}
.hero{{padding:72px 0}}.hero h1{{font-size:clamp(2.1rem,6vw,3.8rem);margin-bottom:16px}}
.hero p.lead{{font-size:1.15rem;color:var(--m);max-width:620px;margin-bottom:28px}}
.hero .actions{{display:flex;flex-wrap:wrap;gap:12px}}
.hero-photo img,.tile.photo img{{width:100%;height:100%;object-fit:cover;display:block}}
.hero-photo{{border-radius:var(--r);overflow:hidden;min-height:260px;max-height:420px}}.tile.photo{{padding:0;overflow:hidden}}
.hero-art{{border-radius:var(--r);background:var(--g);min-height:260px;box-shadow:0 30px 60px -30px rgba(0,0,0,.35)}}
.hero.split .wrap{{display:grid;gap:40px;align-items:center}}
.hero.centered{{text-align:center;background:linear-gradient(180deg,var(--s),var(--bg))}}
.hero.centered p.lead{{margin-left:auto;margin-right:auto}}.hero.centered .actions{{justify-content:center}}
.hero.overlay{{background:var(--g);color:#fff;padding:110px 0}}.hero.overlay p.lead{{color:rgba(255,255,255,.85)}}
.hero.overlay .btn{{background:var(--a);color:#111}}.hero.overlay .btn.alt{{background:transparent;color:#fff}}
.hero.minimal{{border-bottom:1px solid {mix.format(12)}}}
.hero.minimal h1{{font-size:clamp(2.4rem,8vw,5rem);max-width:900px}}
.hero.minimal .bar{{width:64px;height:6px;background:var(--a);margin-bottom:28px}}
.eyebrow{{text-transform:uppercase;letter-spacing:.14em;font-size:.78rem;font-weight:700;color:var(--a);margin-bottom:12px}}
.grid{{display:grid;gap:18px}}.card{{background:var(--s);border-radius:var(--r);padding:24px}}
.card h3{{font-size:1.15rem;margin-bottom:6px}}.card p{{color:var(--m)}}
.cards .card{{background:var(--bg);border:1px solid {mix.format(10)};box-shadow:0 10px 30px -18px rgba(0,0,0,.25)}}
.ico{{display:inline-grid;place-items:center;width:42px;height:42px;border-radius:12px;
background:color-mix(in srgb,var(--p) 12%,transparent);color:var(--p);margin-bottom:12px}}
.list .row{{display:grid;gap:4px;padding:20px 0;border-top:1px solid {mix.format(12)}}}
.list .row h3{{font-size:1.2rem}}.list .row p{{color:var(--m)}}
.menu .row{{display:flex;justify-content:space-between;gap:16px;padding:16px 0;
border-bottom:1px dashed {mix.format(25)}}}
.menu .row p{{color:var(--m);font-size:.95rem;text-align:right}}
.alt-bg{{background:var(--s)}}.about p{{font-size:1.08rem;max-width:760px;color:var(--m);margin-bottom:12px}}
.gallery .tile{{aspect-ratio:4/3;border-radius:var(--r);background:var(--g);display:flex;align-items:flex-end;
padding:14px;color:#fff;font-size:.85rem;font-weight:600}}.gallery .tile:nth-child(2n){{filter:hue-rotate(18deg)}}
.gallery .tile:nth-child(3n){{filter:saturate(.6) brightness(1.1)}}
.contact .wrap{{display:grid;gap:32px}}
.info li{{list-style:none;display:flex;gap:12px;align-items:flex-start;margin-bottom:14px}}
.info svg{{color:var(--p);flex:none;margin-top:3px}}
form{{display:grid;gap:12px}}label{{font-size:.85rem;font-weight:600}}
input,textarea{{width:100%;padding:12px 14px;border-radius:10px;border:1px solid {mix.format(18)};
font:inherit;background:var(--bg);color:var(--t)}}textarea{{min-height:120px}}
.note{{font-size:.85rem;color:var(--m)}}.cta{{background:var(--g);color:#fff;text-align:center}}
.cta p{{opacity:.9;margin-bottom:24px}}.cta .btn{{background:#fff;color:var(--p)}}
footer{{padding:28px 0;font-size:.85rem;color:var(--m)}}
.fab{{position:fixed;right:16px;bottom:16px;display:flex;flex-direction:column;gap:10px;z-index:20}}
.fab a{{width:54px;height:54px;border-radius:50%;display:grid;place-items:center;color:#fff;background:var(--p);
box-shadow:0 10px 24px -8px rgba(0,0,0,.45)}}.fab a.wa{{background:#25d366}}
.ph{{background:repeating-linear-gradient(45deg,#fff3cd 0 6px,#ffe9a8 6px 12px);
color:#6b5200;padding:0 4px;border-radius:4px}}
.preview-banner{{background:#1d1d1f;color:#fff;text-align:center;font-size:.8rem;padding:6px}}
@media(min-width:768px){{.nav-links{{display:flex}}.hero.split .wrap{{grid-template-columns:1.1fr .9fr}}
.grid.c3{{grid-template-columns:repeat(3,1fr)}}.contact .wrap{{grid-template-columns:1fr 1fr}}
.list .row{{grid-template-columns:1fr 2fr;gap:24px}}section{{padding:88px 0}}}}
@media(min-width:540px) and (max-width:767px){{.grid.c3{{grid-template-columns:repeat(2,1fr)}}}}"""


def _txt(v) -> str:
    """Escape; visually mark '[Add your ...]' placeholders so they are never mistaken for real copy."""
    s = _e(v)
    if v and PLACEHOLDER.match(str(v).strip()):
        return f'<span class="ph">{s}</span>'
    return s


def _img(i: dict, cls: str = "") -> str:
    """Only http(s) URLs produced by the pipeline image resolver (approved business images) are rendered."""
    url = str(i.get("url") or "")
    if not url.startswith(("http://", "https://")):
        return ""
    return f'<img class="{cls}" src="{_e(url)}" alt="{_e(i.get("alt") or "")}" loading="lazy">'


def _hero(sec, b, theme, imgs=None) -> str:
    variant = theme.get("hero", "centered")
    phone = tel_digits(b.get("phone"))
    cta = f'<a class="btn" href="#contact">{_e(sec.get("cta_label") or theme.get("hero_cta") or "Contact us")}</a>'
    call = f'<a class="btn alt" href="tel:{_e(phone)}">{_icon("phone", 18)} Call now</a>' if phone else ""
    eyebrow = " · ".join(_e(x) for x in (b.get("industry_label"), b.get("city")) if is_real(x))
    body = (f'<div>{f"<p class=eyebrow>{eyebrow}</p>" if eyebrow else ""}'
            f'{"<div class=bar></div>" if variant == "minimal" else ""}'
            f'<h1>{_txt(sec.get("heading") or b.get("name"))}</h1>'
            f'<p class="lead">{_txt(sec.get("body"))}</p><div class="actions">{cta}{call}</div></div>')
    art = '<div class="hero-art" role="presentation"></div>' if variant == "split" else ""
    if imgs:  # approved business photo replaces the decorative gradient
        art = f'<div class="hero-photo">{_img(imgs[0], "cover")}</div>'
        variant = "split" if variant != "overlay" else variant
    return f'<section class="hero {_e(variant)}" id="top"><div class="wrap">{body}{art}</div></section>'


def _items(sec) -> list[dict]:
    return [i for i in (sec.get("items") or []) if isinstance(i, dict) and (i.get("title") or i.get("description"))]


def _services(sec, theme) -> str:
    items = _items(sec)
    layout = theme.get("services_layout", "grid")
    if layout in ("list", "menu"):
        rows = "".join(f'<div class="row"><h3>{_txt(i.get("title"))}</h3><p>{_txt(i.get("description"))}</p></div>'
                       for i in items)
        inner = f'<div class="{layout}">{rows}</div>'
    else:
        cards = "".join(f'<div class="card"><span class="ico">{_icon("star")}</span><h3>{_txt(i.get("title"))}</h3>'
                        f'<p>{_txt(i.get("description"))}</p></div>' for i in items)
        inner = f'<div class="grid c3 {"cards" if layout == "cards" else ""}">{cards}</div>'
    intro = f'<p class="note" style="margin:-12px 0 24px">{_txt(sec.get("body"))}</p>' if sec.get("body") else ""
    return f'<section id="services"><div class="wrap"><h2>{_txt(sec.get("heading"))}</h2>{intro}{inner}</div></section>'


def _about(sec) -> str:
    paras = "".join(f"<p>{_txt(p.strip())}</p>" for p in str(sec.get("body") or "").split("\n\n") if p.strip())
    return (f'<section id="about" class="about alt-bg"><div class="wrap"><h2>{_txt(sec.get("heading"))}</h2>'
            f'{paras}</div></section>')


def _gallery(sec, imgs=None) -> str:
    if imgs:
        tiles = "".join(f'<div class="tile photo">{_img(i, "cover")}</div>' for i in imgs[:9])
        return (f'<section id="gallery" class="gallery"><div class="wrap"><h2>{_txt(sec.get("heading"))}</h2>'
                f'<div class="grid c3">{tiles}</div></div></section>')
    caps = _items(sec)[:9] or [{"title": "[Add your photo]"}] * 3
    tiles = "".join(f'<div class="tile">{_txt(c.get("title"))}</div>' for c in caps)
    return (f'<section id="gallery" class="gallery"><div class="wrap"><h2>{_txt(sec.get("heading"))}</h2>'
            f'<div class="grid c3">{tiles}</div></div></section>')


def _contact(sec, b) -> str:
    info = []
    if is_real(b.get("address")) or is_real(b.get("city")):
        info.append(("pin", ", ".join(_e(x) for x in (b.get("address"), b.get("city")) if is_real(x))))
    phone = tel_digits(b.get("phone"))
    if phone:
        info.append(("phone", f'<a href="tel:{_e(phone)}">{_e(b.get("phone"))}</a>'))
    email = b.get("email") if is_real(b.get("email")) and "@" in str(b.get("email")) else None
    if email:
        info.append(("mail", f'<a href="mailto:{_e(email)}">{_e(email)}</a>'))
    if is_real(b.get("hours")):
        info.append(("clock", _e(b.get("hours"))))
    lis = "".join(f"<li>{_icon(i)}<span>{v}</span></li>" for i, v in info) or \
        '<li><span class="ph">[Add your contact details]</span></li>'
    if email:
        form = (f'<form action="mailto:{_e(email)}" method="post" enctype="text/plain">'
                '<label for="n">Name</label><input id="n" name="name" required autocomplete="name">'
                '<label for="c">Email or phone</label><input id="c" name="contact" required>'
                '<label for="m">Message</label><textarea id="m" name="message" required></textarea>'
                '<button class="btn" type="submit">Send message</button>'
                '<p class="note">Opens your email app. Nothing is stored by this page.</p></form>')
    else:
        form = '<p class="note"><span class="ph">[Add your email address to enable the contact form]</span></p>'
    return (f'<section id="contact" class="contact alt-bg"><div class="wrap"><div><h2>{_txt(sec.get("heading"))}</h2>'
            f'<p class="note" style="margin-bottom:20px">{_txt(sec.get("body"))}</p><ul class="info">{lis}</ul></div>'
            f'{form}</div></section>')


def _cta(sec, b) -> str:
    phone = tel_digits(b.get("phone"))
    href = f"tel:{_e(phone)}" if phone else "#contact"
    label = sec.get("cta_label") or ("Call us" if phone else "Contact us")
    return (f'<section class="cta"><div class="wrap"><h2>{_txt(sec.get("heading"))}</h2><p>{_txt(sec.get("body"))}</p>'
            f'<a class="btn" href="{href}">{_e(label)}</a></div></section>')


def _jsonld(b: dict, url: str | None) -> str:
    """LocalBusiness structured data using only real (non-placeholder) supplied fields."""
    data: dict = {"@context": "https://schema.org", "@type": "LocalBusiness", "name": b.get("name")}
    if is_real(b.get("description")):
        data["description"] = b["description"]
    if tel_digits(b.get("phone")):
        data["telephone"] = b["phone"]
    if is_real(b.get("email")):
        data["email"] = b["email"]
    if is_real(b.get("address")) or is_real(b.get("city")):
        addr = {"@type": "PostalAddress"}
        for src, dst in (("address", "streetAddress"), ("city", "addressLocality"), ("country", "addressCountry")):
            if is_real(b.get(src)):
                addr[dst] = b[src]
        data["address"] = addr
    if is_real(b.get("hours")):
        data["openingHours"] = b["hours"]
    if url:
        data["url"] = url
    raw = json.dumps(data, ensure_ascii=False)
    # Prevent </script> breakout inside the JSON block.
    raw = raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return f'<script type="application/ld+json">{raw}</script>'


def render(content: dict, theme: dict, *, preview: bool = False, url: str | None = None) -> str:
    b = content.get("business") or {}
    seo = content.get("seo") or {}
    name = b.get("name") or "Business"
    title = seo.get("title") or name
    desc = seo.get("description") or ""
    imgs = [i for i in (content.get("images") or []) if isinstance(i, dict)]
    renderers = {"hero": lambda s: _hero(s, b, theme, imgs), "services": lambda s: _services(s, theme),
                 "about": _about, "gallery": lambda s: _gallery(s, imgs[1:] or imgs),
                 "contact": lambda s: _contact(s, b), "cta": lambda s: _cta(s, b)}
    sections = [s for s in (content.get("sections") or []) if isinstance(s, dict) and s.get("enabled", True)]
    body = "".join(renderers[s["type"]](s) for s in sections if s.get("type") in renderers)
    links = "".join(f'<a href="#{s["type"]}">{_e(s.get("heading"))}</a>' for s in sections
                    if s.get("type") in ("services", "about", "gallery", "contact"))
    phone = tel_digits(b.get("phone"))
    wa = re.sub(r"\D", "", str(b.get("whatsapp_number") or "")) if b.get("whatsapp_authorized") is True else ""
    fab = ""
    if phone or len(wa) >= 8:
        fab = '<div class="fab">'
        if len(wa) >= 8:
            fab += (f'<a class="wa" href="https://wa.me/{wa}" aria-label="Chat on WhatsApp" rel="noopener">'
                    f'{_icon("chat", 24)}</a>')
        if phone:
            fab += f'<a href="tel:{_e(phone)}" aria-label="Call {_e(name)}">{_icon("phone", 24)}</a>'
        fab += "</div>"
    robots = '<meta name="robots" content="noindex,nofollow">' if preview else ""
    banner = '<div class="preview-banner">Preview: not yet published</div>' if preview else ""
    og_url = f'<meta property="og:url" content="{_e(url)}">' if url else ""
    nav_cta = (f'<a class="btn sm" href="tel:{_e(phone)}">Call</a>' if phone
               else '<a class="btn sm" href="#contact">Contact</a>')
    city = f" · {_e(b.get('city'))}" if is_real(b.get("city")) else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(title)}</title><meta name="description" content="{_e(desc)}">{robots}
<meta property="og:type" content="website"><meta property="og:title" content="{_e(title)}">
<meta property="og:description" content="{_e(desc)}">{og_url}
<meta name="theme-color" content="{_color(theme.get('primary'), '#0071e3')}">
{_jsonld(b, url)}<style>{_css(theme)}</style></head>
<body>{banner}<header class="nav"><div class="wrap"><a class="brand" href="#top">{_e(name)}</a>
<nav class="nav-links">{links}</nav>{nav_cta}</div></header><main>{body}</main>
<footer><div class="wrap">&copy; {_e(name)}{city}</div></footer>{fab}
</body></html>"""
