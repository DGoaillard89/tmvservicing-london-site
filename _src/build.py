#!/usr/bin/env python3
"""
TMV Servicing London: tiny static page builder.

Page bodies live in _src/pages/**.html. Each starts with a JSON meta block:
    <!--meta { "title": ..., "description": ..., ... } -->
This script wraps them in the shared head/header/footer and writes the finished
HTML to the same relative path in the site root. GitHub Pages serves the output;
nothing here runs in the browser. (Jekyll skips folders starting with "_".)

Run:  python3 _src/build.py

Placeholders available inside page bodies:
    {{root}}            relative path to site root ("" or "../"), "/" on 404
    {{latest_posts}}    3 newest written posts as cards
    {{blog_list}}       all written posts, newest first
    {{related:tag}}     up to 3 related posts, excluding the current one. On posts: any
                        "post.related" slugs first, then the full set ranked by shared
                        tags (+ bonus for `tag`). Elsewhere: posts tagged `tag`, then newest.
    {{tilemap}}         the 33-tile London coverage grid
    {{regions}}         areas-hub region blocks (all boroughs + postcodes)
    {{boroughs:west}}   borough list for one region
    {{codes:west}}      postcode chips for one region
    {{cta}}             enquiry call-to-action box (for posts)

Posts: put them in _src/pages/blog/<slug>.html with a "post" object in meta
({"date": "YYYY-MM-DD", "tags": [...], "excerpt": ...}). Only posts that exist
here are listed anywhere, so unwritten posts are never linked.
"""
import datetime as dt
import html
import json
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent
ROOT = SRC.parent
PAGES = SRC / "pages"
DOMAIN = "https://tmvservicing.london"
BRAND = "TMV Servicing London"
PHONE = "020 3633 6064"
TEL = "+442036336064"
BUILD_DATE = "2026-10-20"
OG_IMAGE = f"{DOMAIN}/assets/og.png"
LOGO_URL = f"{DOMAIN}/assets/logo.png"

# --------------------------------------------------------------------------
# London: 32 boroughs + the City. Grouped by how we plan our rounds (not an
# official definition). Tile positions are a rough, not-to-scale layout.
# --------------------------------------------------------------------------
REGIONS = {
    "central": {"name": "Central London", "page": "areas/central-london.html", "short": "Central"},
    "west": {"name": "West London", "page": "areas/west-london.html", "short": "West"},
    "north": {"name": "North London", "page": "areas/north-london.html", "short": "North"},
    "east": {"name": "East London", "page": "areas/east-london.html", "short": "East"},
    "south": {"name": "South London", "page": "areas/south-london.html", "short": "South"},
}

# (name, official name, region, tile label, (row, col), postcode districts)
BOROUGHS = [
    ("Barnet", "London Borough of Barnet", "north", "BARN", (0, 3), "N2 N3 N11 N12 N20 NW4 NW7 NW9 NW11 EN4 EN5 HA8"),
    ("Enfield", "London Borough of Enfield", "north", "ENF", (0, 4), "N9 N13 N14 N18 N21 EN1 EN2 EN3"),
    ("Harrow", "London Borough of Harrow", "west", "HRW", (1, 1), "HA1 HA2 HA3 HA5 HA7"),
    ("Brent", "London Borough of Brent", "west", "BRE", (1, 2), "NW2 NW6 NW10 HA0 HA9"),
    ("Camden", "London Borough of Camden", "central", "CAM", (1, 3), "NW1 NW3 NW5 WC1 N6 N19"),
    ("Haringey", "London Borough of Haringey", "north", "HGY", (1, 4), "N4 N8 N10 N15 N17 N22"),
    ("Waltham Forest", "London Borough of Waltham Forest", "north", "WFOR", (1, 5), "E4 E10 E11 E17"),
    ("Redbridge", "London Borough of Redbridge", "east", "REDB", (1, 6), "E18 IG1 IG2 IG4 IG5 IG6 IG8"),
    ("Havering", "London Borough of Havering", "east", "HAV", (1, 7), "RM1 RM2 RM3 RM7 RM11 RM12 RM13 RM14"),
    ("Hillingdon", "London Borough of Hillingdon", "west", "HILL", (2, 0), "UB3 UB4 UB7 UB8 UB9 UB10 HA4 HA6"),
    ("Ealing", "London Borough of Ealing", "west", "EAL", (2, 1), "W3 W5 W7 W13 UB1 UB2 UB5 UB6"),
    ("Kensington and Chelsea", "Royal Borough of Kensington and Chelsea", "central", "K&C", (2, 2), "W8 W10 W11 SW3 SW5 SW7 SW10"),
    ("Westminster", "City of Westminster", "central", "WSTM", (2, 3), "W1 W2 W9 SW1 NW8 WC2"),
    ("Islington", "London Borough of Islington", "central", "ISL", (2, 4), "N1 N5 N7 N19 EC1"),
    ("Hackney", "London Borough of Hackney", "east", "HACK", (2, 5), "E2 E5 E8 E9 N16"),
    ("Newham", "London Borough of Newham", "east", "NEWH", (2, 6), "E6 E7 E12 E13 E15 E16 E20"),
    ("Barking and Dagenham", "London Borough of Barking and Dagenham", "east", "B&D", (2, 7), "IG11 RM6 RM8 RM9 RM10"),
    ("Hounslow", "London Borough of Hounslow", "west", "HNS", (3, 0), "TW3 TW4 TW5 TW7 TW8 TW13 TW14 W4"),
    ("Hammersmith and Fulham", "London Borough of Hammersmith and Fulham", "west", "H&F", (3, 1), "W6 W12 W14 SW6"),
    ("Wandsworth", "London Borough of Wandsworth", "south", "WAND", (3, 2), "SW11 SW12 SW15 SW17 SW18"),
    ("Lambeth", "London Borough of Lambeth", "south", "LAM", (3, 3), "SE11 SE27 SW2 SW4 SW8 SW9 SW16"),
    ("City of London", "City of London", "central", "CITY", (3, 4), "EC2 EC3 EC4"),
    ("Tower Hamlets", "London Borough of Tower Hamlets", "east", "TOWH", (3, 5), "E1 E3 E14"),
    ("Greenwich", "Royal Borough of Greenwich", "south", "GRN", (3, 6), "SE2 SE3 SE7 SE9 SE10 SE18 SE28"),
    ("Bexley", "London Borough of Bexley", "south", "BEX", (3, 7), "DA5 DA6 DA7 DA8 DA14 DA15 DA16"),
    ("Richmond upon Thames", "London Borough of Richmond upon Thames", "west", "RICH", (4, 1), "TW1 TW2 TW9 TW10 TW11 TW12 SW13 SW14"),
    ("Merton", "London Borough of Merton", "south", "MERT", (4, 2), "SW19 SW20 CR4 SM4"),
    ("Southwark", "London Borough of Southwark", "south", "SWRK", (4, 4), "SE1 SE5 SE15 SE16 SE17 SE21 SE22"),
    ("Lewisham", "London Borough of Lewisham", "south", "LEW", (4, 5), "SE4 SE6 SE8 SE12 SE13 SE14 SE23 SE26"),
    ("Kingston upon Thames", "Royal Borough of Kingston upon Thames", "south", "KING", (5, 1), "KT1 KT2 KT3 KT5 KT6 KT9"),
    ("Sutton", "London Borough of Sutton", "south", "SUT", (5, 2), "SM1 SM2 SM3 SM5 SM6"),
    ("Croydon", "London Borough of Croydon", "south", "CROY", (5, 3), "CR0 CR2 CR5 CR7 CR8 SE25"),
    ("Bromley", "London Borough of Bromley", "south", "BROM", (5, 4), "BR1 BR2 BR3 BR4 BR5 BR6 BR7"),
]
assert len(BOROUGHS) == 33

NAV = [
    ("tmv-servicing.html", "servicing", "Servicing"),
    ("tmv-installation.html", "installation", "Installation"),
    ("tmv-compliance.html", "compliance", "Compliance"),
    ("areas/index.html", "areas", "Areas"),
    ("blog/index.html", "blog", "Blog"),
    ("faqs.html", "faqs", "FAQs"),
]

LOGO_SVG = (
    '<svg viewBox="0 0 48 48" aria-hidden="true"><rect width="48" height="48" rx="10" fill="#0d2438"/>'
    '<path d="M13 10.5h22M24 10.5v12" stroke="#f0b43c" stroke-width="5.5" stroke-linecap="round"/>'
    '<circle cx="24" cy="26" r="5.6" fill="#f0b43c"/>'
    '<path d="M5 37.5c4.5 0 5.5-4 10-4s5 6 10 6 5.5-6 10-6 4.5 3 8 3" fill="none" stroke="#8cc4e0" stroke-width="3.4" stroke-linecap="round"/></svg>'
)

PHONE_ICON = '<svg class="icon" aria-hidden="true"><use href="{root}assets/icons.svg#phone" /></svg>'
ARROW_ICON = '<svg class="icon" aria-hidden="true"><use href="{root}assets/icons.svg#arrow" /></svg>'

BUSINESS_SCHEMA_ID = f"{DOMAIN}/#business"


def area_served(region=None):
    items = [b for b in BOROUGHS if region is None or b[2] == region]
    return [{"@type": "AdministrativeArea", "name": b[1]} for b in items]


def business_ref():
    return {
        "@type": "ProfessionalService",
        "@id": BUSINESS_SCHEMA_ID,
        "name": BRAND,
        "url": f"{DOMAIN}/",
        "telephone": "+44 20 3633 6064",
        "address": {
            "@type": "PostalAddress",
            "streetAddress": "The Lightbox G16, 111 Power Road",
            "addressLocality": "Chiswick, London",
            "postalCode": "W4 5PY",
            "addressCountry": "GB",
        },
    }


def resolve(obj):
    """Swap placeholders in page schema: "__AREA_SERVED__", "__AREA_SERVED:west__", "__BUSINESS__"."""
    if isinstance(obj, dict):
        return {k: resolve(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [resolve(v) for v in obj]
    if obj == "__AREA_SERVED__":
        return area_served()
    if isinstance(obj, str) and obj.startswith("__AREA_SERVED:"):
        return area_served(obj[14:-2])
    if obj == "__BUSINESS__":
        return business_ref()
    return obj


# --------------------------------------------------------------------------
def read_page(path):
    raw = path.read_text()
    m = re.match(r"\s*<!--meta\s*(\{.*?\})\s*-->\s*", raw, re.S)
    if not m:
        raise SystemExit(f"No meta block in {path}")
    meta = json.loads(m.group(1))
    meta["body"] = raw[m.end():]
    rel = path.relative_to(PAGES).as_posix()
    meta["path"] = rel
    meta["depth"] = rel.count("/")
    return meta


def url_for(path):
    if path == "index.html":
        return f"{DOMAIN}/"
    if path.endswith("/index.html"):
        return f"{DOMAIN}/{path[:-10]}"
    return f"{DOMAIN}/{path}"


def nice_date(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B %Y')}"


def esc(s):
    return html.escape(s, quote=True)


def post_card(p, root):
    d = dt.date.fromisoformat(p["post"]["date"])
    return f"""<a class="post-card" href="{root}{p['path']}">
          <span class="post-card__band"><span>{d.strftime('%b %Y').upper()}</span><b>{esc(p['post'].get('area', 'LONDON'))}</b></span>
          <span class="post-card__body">
            <h3>{esc(p['post']['headline'])}</h3>
            <p>{esc(p['post']['excerpt'])}</p>
            <span class="link-arrow">Read the post {ARROW_ICON.format(root=root)}</span>
          </span>
        </a>"""


def tilemap(root):
    cells = []
    for name, official, region, label, (r, c), codes in BOROUGHS:
        cells.append(
            f'<a class="tile tile--{region}" href="{root}{REGIONS[region]["page"]}" '
            f'style="grid-row:{r + 1};grid-column:{c + 1}" title="{esc(name)}" aria-label="{esc(name)}, {REGIONS[region]["name"]}">{esc(label)}</a>'
        )
    legend = "".join(
        f'<li><i class="tile--{k}"></i><a href="{root}{v["page"]}">{v["name"]}</a></li>' for k, v in REGIONS.items()
    )
    return f"""<div class="tilemap" role="list" aria-label="London boroughs we cover">
            {''.join('<span role="listitem" style="display:contents">' + c + '</span>' for c in cells)}
          </div>
          <ul class="legend">{legend}</ul>
          <p class="tilemap-note">All 32 boroughs plus the City. Not to scale. Squint and it's London.</p>"""


def borough_list(region):
    items = []
    for name, official, reg, label, pos, codes in sorted([b for b in BOROUGHS if b[2] == region], key=lambda b: b[0]):
        chips = "".join(f'<span class="pc">{c}</span>' for c in codes.split())
        items.append(f'<li><strong>{esc(name)}</strong><span class="codes">{chips}</span></li>')
    return f'<ul class="borough-list">{"".join(items)}</ul>'


def region_codes(region):
    seen = []
    for b in BOROUGHS:
        if b[2] == region:
            for c in b[5].split():
                if c not in seen:
                    seen.append(c)
    return "".join(f'<span class="pc">{c}</span>' for c in seen)


REGION_BLURBS = {
    "central": "The City, Westminster, Camden, Islington and Kensington &amp; Chelsea. Mansion blocks, offices, hotels, clinics and some very tight loading bays.",
    "west": "Our home patch, from Chiswick out to Hillingdon and up to Harrow. Victorian conversions, HMOs, schools, care homes and the odd mansion flat.",
    "north": "Barnet, Enfield, Haringey and Waltham Forest. Inter-war semis, big care homes, academy schools and plenty of housing association stock.",
    "east": "Hackney, Tower Hamlets, Newham, Redbridge, Barking &amp; Dagenham and Havering. New-build towers, council estates, student blocks and serviced apartments.",
    "south": "Eleven boroughs from Lambeth and Southwark down to Croydon, Bromley and Kingston. Estates, schools, leisure centres and lots of purpose-built flats.",
}


def regions_block(root):
    out = []
    for key in ["central", "west", "north", "east", "south"]:
        r = REGIONS[key]
        count = sum(1 for b in BOROUGHS if b[2] == key)
        noun = "borough" if count == 1 else "boroughs"
        if key == "central":
            label = f"The City + {count - 1} boroughs"
        else:
            label = f"{count} {noun}"
        out.append(f"""<article class="region region--{key}" id="{key}">
            <div>
              <span class="eyebrow">{label}</span>
              <h3 style="margin-top:10px"><a href="{root}{r['page']}">{r['name']}</a></h3>
              <p>{REGION_BLURBS[key]}</p>
              <p style="margin-top:16px"><a class="link-arrow" href="{root}{r['page']}">TMV servicing in {r['name']} {ARROW_ICON.format(root=root)}</a></p>
            </div>
            {borough_list(key)}
          </article>""")
    return "\n".join(out)


def cta_box(root):
    return f"""<div class="post-cta">
          <h2>Got TMVs in London that need a look?</h2>
          <p>Tell us roughly what you've got and where. We'll give you a fixed quote and a date that works around your building.</p>
          <button class="btn btn--brick" type="button" data-open-enquiry>Get a free quote</button>
        </div>"""


# --------------------------------------------------------------------------
def head(meta, root):
    url = url_for(meta["path"])
    title = meta["title"]
    desc = meta["description"]
    og_type = "article" if meta.get("post") else "website"
    schemas = [resolve(s) for s in meta.get("schema", [])]
    if meta.get("crumbs"):
        items = [{"@type": "ListItem", "position": 1, "name": "Home", "item": f"{DOMAIN}/"}]
        for i, (name, path) in enumerate(meta["crumbs"], start=2):
            items.append({"@type": "ListItem", "position": i, "name": name, "item": url_for(path) if path else url})
        schemas.append({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items})
    if meta.get("faq_schema"):
        qa = re.findall(r'<details class="faq">\s*<summary>(.*?)</summary>\s*<div class="faq__a">(.*?)</div>\s*</details>', meta["body"], re.S)
        if qa:
            def clean(s):
                s = re.sub(r"<[^>]+>", "", s)
                s = s.replace("{{root}}", "")
                return re.sub(r"\s+", " ", html.unescape(s)).strip()
            schemas.append({
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": [
                    {"@type": "Question", "name": clean(q), "acceptedAnswer": {"@type": "Answer", "text": clean(a)}} for q, a in qa
                ],
            })
    if meta.get("post"):
        p = meta["post"]
        schemas.append({
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": p["headline"],
            "description": desc,
            "datePublished": p["date"],
            "dateModified": p.get("modified", p["date"]),
            "author": {"@type": "Organization", "name": BRAND, "url": f"{DOMAIN}/"},
            "publisher": {"@type": "Organization", "name": BRAND, "logo": {"@type": "ImageObject", "url": LOGO_URL}},
            "image": OG_IMAGE,
            "mainEntityOfPage": {"@type": "WebPage", "@id": url},
            "inLanguage": "en-GB",
        })
    ld = "\n".join(
        f'  <script type="application/ld+json">\n{json.dumps(s, indent=2, ensure_ascii=False)}\n  </script>' for s in schemas
    )
    robots = '\n  <meta name="robots" content="noindex" />' if meta.get("noindex") else ""
    canonical = "" if meta.get("noindex") else f'\n  <link rel="canonical" href="{url}" />'
    return f"""<!doctype html>
<html lang="en-GB">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(desc)}" />{canonical}{robots}
  <meta property="og:site_name" content="{BRAND}" />
  <meta property="og:locale" content="en_GB" />
  <meta property="og:type" content="{og_type}" />
  <meta property="og:title" content="{esc(meta.get('og_title', title))}" />
  <meta property="og:description" content="{esc(desc)}" />
  <meta property="og:url" content="{url}" />
  <meta property="og:image" content="{OG_IMAGE}" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta property="og:image:alt" content="TMV Servicing London: thermostatic mixing valve servicing across all 32 boroughs and the City" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{esc(meta.get('og_title', title))}" />
  <meta name="twitter:description" content="{esc(desc)}" />
  <meta name="twitter:image" content="{OG_IMAGE}" />
  <meta name="theme-color" content="#0d2438" />
  <link rel="icon" href="{root}assets/favicon.svg" type="image/svg+xml" />
  <link rel="apple-touch-icon" href="{root}assets/apple-touch-icon.png" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@500&family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,700&family=Fraunces:opsz,wght@9..144,700;9..144,800&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="{root}styles.css" />
{ld}
</head>"""


def header(meta, root):
    links = []
    for path, key, label in NAV:
        cur = ' aria-current="page"' if meta.get("nav") == key else ""
        links.append(f'<a href="{root}{path}"{cur}>{label}</a>')
    nav = "\n        ".join(links)
    return f"""  <a class="skip" href="#main">Skip to content</a>

  <div class="strip">
    <div class="wrap">
      <span class="strip__codes"><b>E</b> · <b>EC</b> · <b>N</b> · <b>NW</b> · <b>SE</b> · <b>SW</b> · <b>W</b> · <b>WC</b> · BR · CR · DA · EN · HA · IG · KT · RM · SM · TW · UB</span>
      <span>London engineers, London only · <a href="tel:{TEL}">{PHONE}</a></span>
    </div>
  </div>

  <header class="site-header">
    <div class="wrap">
      <a class="logo" href="{root}index.html" aria-label="{BRAND} home">
        <span class="logo__mark">{LOGO_SVG}</span>
        <span class="logo__text"><span class="logo__name">TMV Servicing</span><span class="logo__sub">London</span></span>
      </a>

      <button class="nav-toggle" type="button" aria-label="Menu" aria-expanded="false" aria-controls="site-nav">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" /></svg>
      </button>

      <nav class="nav" id="site-nav" aria-label="Main">
        {nav}
      </nav>

      <div class="header-cta">
        <a class="header-phone" href="tel:{TEL}" aria-label="Call {PHONE}">
          {PHONE_ICON.format(root=root)}
          <span>{PHONE}</span>
        </a>
        <button class="btn btn--brick btn--small" type="button" data-open-enquiry>Get a quote</button>
      </div>
    </div>
  </header>"""


def page_hero(meta, root):
    h = meta.get("hero")
    if not h:
        return ""
    crumbs = ""
    if meta.get("crumbs"):
        parts = [f'<li><a href="{root}index.html">Home</a></li>']
        for name, path in meta["crumbs"]:
            if path:
                parts.append(f'<li><a href="{root}{path}">{esc(name)}</a></li>')
            else:
                parts.append(f'<li aria-current="page">{esc(name)}</li>')
        crumbs = f'<nav class="crumbs" aria-label="Breadcrumb"><ol>{"".join(parts)}</ol></nav>'
    eyebrow = f'<span class="eyebrow" style="margin-top:22px">{h["eyebrow"]}</span>' if h.get("eyebrow") else ""
    lede = f'<p class="page-hero__lede">{h["lede"]}</p>' if h.get("lede") else ""
    meta_line = ""
    if meta.get("post"):
        p = meta["post"]
        meta_line = (
            f'<p class="post-meta"><time datetime="{p["date"]}">{nice_date(p["date"])}</time>'
            f'<span>By {BRAND}</span><span>{p.get("read", "6 min read")}</span></p>'
        )
    actions = ""
    if h.get("actions", True) and not meta.get("post"):
        topic = esc(h.get("topic", ""))
        actions = f"""<div class="hero__actions">
          <button class="btn btn--brick" type="button" data-open-enquiry="{topic}">Get a free quote</button>
          <a class="btn btn--line" href="tel:{TEL}">{PHONE_ICON.format(root=root)} Call {PHONE}</a>
        </div>"""
    return f"""    <section class="page-hero">
      <div class="wrap">
        {crumbs}
        {eyebrow}
        <h1>{h['h1']}</h1>
        {lede}
        {meta_line}
        {actions}
      </div>
    </section>
"""


def cta_band(root):
    return f"""    <section class="cta-band">
      <div class="wrap">
        <div>
          <h2>Let's get your TMVs tested, tuned and on record.</h2>
          <p>Tell us where you are in London and roughly how many valves you've got. We'll come back with a fixed quote and a visit plan that suits your building.</p>
        </div>
        <div class="cta-band__actions">
          <button class="btn btn--navy" type="button" data-open-enquiry>Get a free quote</button>
          <a class="btn btn--line" href="tel:{TEL}">Call {PHONE}</a>
        </div>
      </div>
    </section>
"""


def footer(root):
    a = ARROW_ICON.format(root=root)
    area_links = "".join(f'<li><a href="{root}{r["page"]}">{r["name"]}</a></li>' for r in REGIONS.values())
    return f"""  <footer class="site-footer after-band">
    <div class="wrap">
      <div class="footer-grid">
        <div>
          <a class="logo" href="{root}index.html" aria-label="{BRAND} home">
            <span class="logo__mark">{LOGO_SVG}</span>
            <span class="logo__text"><span class="logo__name">TMV Servicing</span><span class="logo__sub">London</span></span>
          </a>
          <p class="footer-blurb">Thermostatic mixing valve servicing, testing and installation for London buildings. Engineers based in Chiswick, working across all 32 boroughs and the City, and nowhere else.</p>
          <address class="footer-contact">
            <a href="tel:{TEL}">{PHONE}</a>
            <span>The Lightbox G16, 111 Power Road<br />Chiswick, London W4 5PY</span>
          </address>
        </div>
        <div>
          <h2>Services</h2>
          <ul>
            <li><a href="{root}tmv-servicing.html">TMV servicing &amp; testing</a></li>
            <li><a href="{root}tmv-installation.html">Installation &amp; replacement</a></li>
            <li><a href="{root}tmv-compliance.html">TMV compliance guide</a></li>
            <li><a href="{root}tmv-asset-registers.html">Asset registers &amp; scheduling</a></li>
            <li><a href="{root}how-we-work.html">How we work in London</a></li>
          </ul>
        </div>
        <div>
          <h2>Areas</h2>
          <ul>
            <li><a href="{root}areas/index.html">All areas we cover</a></li>
            {area_links}
          </ul>
        </div>
        <div>
          <h2>Useful</h2>
          <ul>
            <li><a href="{root}blog/index.html">Blog</a></li>
            <li><a href="{root}faqs.html">FAQs</a></li>
            <li><a href="{root}privacy.html">Privacy notice</a></li>
            <li><button class="link-arrow" type="button" data-open-enquiry style="color:#fff">Get a quote {a}</button></li>
          </ul>
        </div>
      </div>
      <div class="footer-bottom">
        <span>&copy; <span data-year>2026</span> {BRAND}. All rights reserved.</span>
        <span>Inside the M25, and specifically inside the 32 boroughs. We're fussy like that.</span>
      </div>
    </div>
  </footer>"""


def render(meta, posts):
    root = "/" if meta.get("absolute") else "../" * meta["depth"]
    body = meta["body"]
    this_path = meta["path"]
    others = [p for p in posts if p["path"] != this_path]

    def related(m):
        tag = m.group(1)
        mine = set(meta["post"].get("tags", [])) if meta.get("post") else set()

        def score(p):
            # On posts: rank the whole set by shared tags (topic tags count double,
            # region tags single), with a bonus for the block's own tag. Newest wins ties.
            theirs = set(p["post"].get("tags", []))
            s = 3 if tag in theirs else 0
            s += sum(1 if t in REGIONS else 2 for t in mine & theirs)
            return s

        pinned = []
        if meta.get("post"):
            wanted = meta["post"].get("related", [])
            pinned = [p for slug in wanted for p in others if p["path"] == f"blog/{slug}.html"]
        if mine:
            ranked = sorted(others, key=score, reverse=True)  # stable: keeps newest-first within a score
        else:
            ranked = [p for p in others if tag in p["post"].get("tags", [])] + [p for p in others if tag not in p["post"].get("tags", [])]
        chosen = (pinned + [p for p in ranked if p not in pinned])[:3]
        if not chosen:
            return ""
        cards = "\n        ".join(post_card(p, root) for p in chosen)
        return f'<div class="post-cards">\n        {cards}\n      </div>'

    def blog_list(_):
        if not posts:
            return '<p class="empty-note">First posts coming soon.</p>'
        cards = "\n        ".join(post_card(p, root) for p in posts)
        return f'<div class="post-list">\n        {cards}\n      </div>'

    body = re.sub(r"\{\{related:([a-z-]+)\}\}", related, body)
    body = body.replace("{{latest_posts}}", f'<div class="post-cards">{"".join(post_card(p, root) for p in posts[:3])}</div>')
    body = re.sub(r"\{\{blog_list\}\}", blog_list, body)
    body = body.replace("{{tilemap}}", tilemap(root))
    body = body.replace("{{regions}}", regions_block(root))
    body = re.sub(r"\{\{boroughs:([a-z]+)\}\}", lambda m: borough_list(m.group(1)), body)
    body = re.sub(r"\{\{codes:([a-z]+)\}\}", lambda m: region_codes(m.group(1)), body)
    body = body.replace("{{cta}}", cta_box(root))
    body = body.replace("{{arrow}}", ARROW_ICON.format(root=root))
    body = body.replace("{{phone_icon}}", PHONE_ICON.format(root=root))
    body = body.replace("{{root}}", root)

    band = "" if meta.get("no_band") else cta_band(root)
    foot = footer(root)
    if meta.get("no_band"):
        foot = foot.replace('class="site-footer after-band"', 'class="site-footer"')
    return f"""{head(meta, root)}
<body data-root="{root if root != '/' else '/'}">
{header(meta, root)}

  <main id="main">
{page_hero(meta, root)}{body.rstrip()}
{band}  </main>

{foot}

  <script src="{root}script.js" defer></script>
  <script src="{root}enquiry.js" defer></script>
</body>
</html>
"""


def main():
    pages = [read_page(p) for p in sorted(PAGES.rglob("*.html"))]
    posts = sorted([p for p in pages if p.get("post")], key=lambda p: p["post"]["date"], reverse=True)
    for meta in pages:
        if len(meta["title"]) > 60:
            print(f"WARN title {len(meta['title'])} chars: {meta['path']}")
        if len(meta["description"]) > 155:
            print(f"WARN description {len(meta['description'])} chars: {meta['path']}")
        if meta.get("post"):
            meta["schema"] = meta.get("schema", [])
        out = ROOT / meta["path"]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render(meta, posts))
    # sitemap
    urls = []
    for meta in pages:
        if meta.get("noindex"):
            continue
        lastmod = meta["post"].get("modified", meta["post"]["date"]) if meta.get("post") else BUILD_DATE
        urls.append(f"  <url><loc>{url_for(meta['path'])}</loc><lastmod>{lastmod}</lastmod></url>")
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls) + "\n</urlset>\n"
    )
    (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {DOMAIN}/sitemap.xml\n")
    print(f"Built {len(pages)} pages ({len(posts)} posts).")


if __name__ == "__main__":
    main()
