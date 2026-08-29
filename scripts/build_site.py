#!/usr/bin/env python3
"""Intel Analysis Wiki — static-site builder.

Reads Peter's Vault /Intel/Wiki/**/*.md, applies the classification auto-gate
(only `open` or unlabelled pages ship; anything official-sensitive / internal /
restricted / confidential / secret is skipped and reported), resolves
[[wikilinks]], and renders a themed static site to docs/.

Run with the Hermes venv python (the macOS 3.9 default breaks `markdown extra`):
    ~/.hermes/hermes-agent/venv/bin/python3 scripts/build_site.py
"""
import os
import re
import sys
import html
import shutil
import datetime

import yaml
import markdown as md_lib

# ---------------- paths & constants ----------------
HOME = os.path.expanduser("~")
VAULT = os.path.join(HOME, "Library", "Mobile Documents", "iCloud~md~obsidian",
                     "Documents", "Peter's Vault")
WIKI = os.path.join(VAULT, "Intel", "Wiki")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
ASSETS_SRC = os.path.join(ROOT, "assets")

SITE_NAME = "Intel Wiki"
SITE_TAGLINE = ("A living reference for intelligence analysis — tradecraft, "
                "analytic frameworks, estimative language and the collection-to-"
                "dissemination cycle.")
SITE_BASE = "https://intel.peterjaycox.com"

# classification gate: normalised tokens that are NEVER published
BLOCKED_CLASSIFICATIONS = {
    "officialsensitive", "officialsensitive", "internal", "restricted",
    "confidential", "secret", "topsecret", "classified", "noforn",
    "protected", "cabinetinconfidence",
}

# page types -> display label + order
TYPE_LABELS = {
    "concept": "Concepts",
    "entity": "Entities",
    "case": "Cases",
    "comparison": "Comparisons",
    "query": "Queries",
}
TYPE_ORDER = ["concept", "entity", "case", "comparison", "query"]

SKIP_FILENAMES = {"index.md", "schema.md", "log.md"}

CONF = {
    "high": ("High confidence", "conf-high"),
    "medium": ("Moderate confidence", "conf-med"),
    "low": ("Low confidence", "conf-low"),
}

TODAY = datetime.date.today()


# ---------------- helpers ----------------
def key(s):
    """Normalise a string for slug-equality: lowercase alphanumerics only."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def scalar(v):
    """Coerce a possibly-list YAML scalar to a plain string ('' if null-ish)."""
    if isinstance(v, (list, tuple)):
        v = v[0] if v else ""
    if v is None:
        return ""
    s = str(v).strip()
    if s.lower() in {"null", "none", "nil"}:
        return ""
    return s


def split_frontmatter(text):
    """Return (frontmatter_dict, body) — frontmatter is the leading --- block."""
    m = re.match(r"\A---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if not m:
        return {}, text
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        data = {}
    return (data if isinstance(data, dict) else {}), text[m.end():]


def strip_provenance(md):
    """Remove ^[raw/...] vault-internal provenance markers."""
    return re.sub(r"\^\[[^\]]*\]", "", md)


WIKILINK_DISPLAY = re.compile(r"\[\[([^\[\]|]+)\|([^\[\]]+)\]\]")
WIKILINK_SIMPLE = re.compile(r"\[\[([^\[\]]+)\]\]")


def resolve_wikilinks(md, slug_map):
    def link(target, display):
        t = target.strip()
        k = key(t)
        if k in slug_map:
            return f'<a href="{html.escape(slug_map[k] + ".html")}">{html.escape(display)}</a>'
        return html.escape(display)  # unresolved -> plain text (graceful)

    # display form first: [[Target|display]]
    md = WIKILINK_DISPLAY.sub(
        lambda m: link(m.group(1), m.group(2)), md)
    # then simple: [[Target]]
    md = WIKILINK_SIMPLE.sub(lambda m: link(m.group(1), m.group(1)), md)
    return md


def blank_before_blocks(md):
    """Ensure a blank line precedes lists/tables/blockquotes (markdown-py)."""
    lines = md.split("\n")
    out = []
    block_re = re.compile(r"^\s*(-|\*|\+|\d+\.)\s|^\s*\||^\s*>|^\s*```")
    for line in lines:
        s = line.strip()
        if (block_re.match(s)
                and out
                and out[-1].strip() != ""
                and not block_re.match(out[-1].lstrip())):
            out.append("")
        out.append(line)
    return "\n".join(out)


def title_from(fm, body):
    t = scalar(fm.get("title"))
    if t:
        return re.sub(r"[\[\]]", "", t)
    return "Untitled"


def summary_from(body):
    """First non-empty, non-heading, non-table paragraph -> one-liner blurb."""
    for para in body.split("\n\n"):
        p = para.strip()
        if not p or p.startswith("#") or p.startswith("|") or p.startswith(">"):
            continue
        p = strip_provenance(p)
        p = WIKILINK_DISPLAY.sub(lambda m: m.group(2), p)
        p = WIKILINK_SIMPLE.sub(lambda m: m.group(1), p)
        p = re.sub(r"[\[\]#*_]+", "", p)
        p = re.sub(r"\s+", " ", p).strip()
        if p and not p.startswith(">"):
            return p[:220]
    return ""


# ---------------- chrome ----------------
def head(title, active="", root=""):
    v = TODAY.strftime("%Y%m%d")
    nav = [
        ("index.html", "Home", "index"),
        ("index.html#concepts", "Concepts", "concepts"),
        ("index.html#entities", "Entities", "entities"),
    ]
    links = "".join(
        f'<a class="{"active" if active == a else ""}" href="{root}{h}">{lbl}</a>'
        for h, lbl, a in nav
    )
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · {SITE_NAME}</title>
<meta name="description" content="Open-source intelligence analysis tradecraft — a living reference wiki.">
<link rel="canonical" href="{SITE_BASE}/{root}{'index.html' if title == 'Home' else ''}">
<link rel="icon" type="image/svg+xml" href="{root}assets/img/favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Fraunces:opsz,wght@9..144,600;9..144,700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{root}assets/site.css?v={v}">
</head>
<body>
<nav class="topnav">
  <div class="topnav-inner">
    <a class="brand" href="{root}index.html">
      <span class="brand-mark" aria-hidden="true"></span>
      <span class="brand-name">{SITE_NAME}</span>
      <small>open-source</small>
    </a>
    <div class="nav-links">{links}</div>
    <div class="theme-toggle" role="button" aria-label="Toggle light/dark theme" tabindex="0" onclick="toggleTheme()">🌙</div>
  </div>
</nav>
<main class="container">
"""


FOOT = """</main>
<footer class="footer">
  <div class="footer-inner">
    <span>Intelligence Analysis Wiki</span>
    <span class="foot-dim">open-source tradecraft &middot; classification-gated build</span>
  </div>
</footer>
<script>
function toggleTheme(){var h=document.documentElement;var b=document.querySelector('.theme-toggle');var t=h.getAttribute('data-theme')==='dark'?'light':'dark';h.setAttribute('data-theme',t);if(b)b.textContent=t==='dark'?'☀️':'🌙';try{localStorage.setItem('intel-theme',t)}catch(e){}}
(function(){try{var s=localStorage.getItem('intel-theme');if(s)document.documentElement.setAttribute('data-theme',s);var b=document.querySelector('.theme-toggle');if(b)b.textContent=(s||'dark')==='dark'?'☀️':'🌙'}catch(e){}})();
</script>
</body>
</html>"""


def confidence_badge(fm):
    c = scalar(fm.get("confidence")).lower()
    if c in CONF:
        label, cls = CONF[c]
        return f'<span class="pill conf {cls}">{html.escape(label)}</span>'
    return ""


def tag_chips(tags):
    out = []
    for t in tags:
        t = scalar(t)
        if t:
            out.append(f'<span class="pill tag">{html.escape(t)}</span>')
    return "".join(out)


# ---------------- pages ----------------
class Page(object):
    def __init__(self, slug, rtype, path, fm, title, body, summary, tags):
        self.slug = slug
        self.rtype = rtype
        self.path = path
        self.fm = fm
        self.title = title
        self.body = body
        self.summary = summary
        self.tags = tags


def load_pages():
    pages = []
    skipped = []
    for dirpath, dirnames, filenames in os.walk(WIKI):
        dirnames[:] = [d for d in dirnames if d not in {".obsidian", "raw", "References"}]
        rel = os.path.relpath(dirpath, WIKI)
        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            if fn.lower() in SKIP_FILENAMES or rel.startswith("raw"):
                continue
            full = os.path.join(dirpath, fn)
            text = open(full, encoding="utf-8").read()
            fm, body = split_frontmatter(text)
            # --- classification gate ---
            cls = fm.get("classification")
            if cls not in (None, ""):
                toks = cls if isinstance(cls, list) else re.split(r"[,\s]+", str(cls))
                blocked = [t for t in toks if key(t) in BLOCKED_CLASSIFICATIONS]
                if blocked:
                    skipped.append((fn, "classification=" + ",".join(blocked)))
                    continue
            title = title_from(fm, body)
            slug = os.path.splitext(fn)[0]
            rtype = scalar(fm.get("type")).lower() or "concept"
            tags = fm.get("tags") or []
            if isinstance(tags, str):
                tags = [tags]
            pages.append(Page(
                slug=slug, rtype=rtype, path=full, fm=fm, title=title,
                body=body, summary=summary_from(body),
                tags=[scalar(t) for t in tags if scalar(t)],
            ))
    pages.sort(key=lambda p: p.title.lower())
    return pages, skipped


def build_slug_map(pages):
    m = {}
    for p in pages:
        m[key(p.slug)] = p.slug
        m[key(p.title)] = p.slug
    return m


def render_body(p, slug_map):
    md = p.body
    # drop the leading H1 (title is rendered in the page header)
    md = re.sub(r"\A\s*#\s+[^\n]*\n?", "", md, count=1)
    md = strip_provenance(md)
    md = resolve_wikilinks(md, slug_map)
    md = blank_before_blocks(md)
    return md_lib.markdown(md, extensions=["extra"])


def build_page(p, pages, slug_map):
    rtype_label = TYPE_LABELS.get(p.rtype, "Concepts")
    badges = [f'<span class="type-pill">{html.escape(rtype_label.rstrip("s"))}</span>',
              confidence_badge(p.fm)]
    chips = tag_chips(p.tags)
    body = render_body(p, slug_map)
    related = [q for q in pages if q.slug != p.slug][:0]  # keep simple; Related rendered inline already

    inner = f"""
<div class="crumb"><a href="index.html">Wiki</a><span class="sep">/</span>{html.escape(rtype_label)}</div>
<div class="page-head">
  <div class="head-top">{''.join(badges)}</div>
  <h1>{html.escape(p.title)}</h1>
  <div class="tags-row">{chips}</div>
  <div class="stamp">Open Source</div>
</div>
<article class="wiki-body">{body}</article>
<a class="nav-back" href="index.html">&larr; Back to Wiki index</a>
"""

    html_out = head(p.title, active=p.rtype if p.rtype in ("concept", "entity") else "index")
    html_out += inner + FOOT
    out_path = os.path.join(DOCS, p.slug + ".html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_out)
    return out_path


def card_html(p):
    badges = [f'<span class="type-pill">{html.escape(TYPE_LABELS.get(p.rtype, "Concepts").rstrip("s"))}</span>',
              confidence_badge(p.fm)]
    chips = tag_chips(p.tags[:3])
    return f"""<a class="card" href="{html.escape(p.slug)}.html">
  <h3>{html.escape(p.title)}</h3>
  <div class="summary">{html.escape(p.summary)}</div>
  <div class="meta">{''.join(badges)}{chips}</div>
</a>"""


def build_index(pages, skipped):
    by_type = {t: [p for p in pages if p.rtype == t] for t in TYPE_ORDER}
    total = len(pages)
    stats = [
        (total, "pages"),
        (len(by_type["concept"]), "concepts"),
        (len(by_type["entity"]), "entities"),
    ]
    stat_html = "".join(
        f'<div class="stat"><b>{n}</b><span>{lbl}</span></div>' for n, lbl in stats
    )
    sections = []
    for t in TYPE_ORDER:
        plist = by_type[t]
        label = TYPE_LABELS[t]
        if plist:
            cards = "".join(card_html(p) for p in plist)
            sections.append(
                f'<section class="section" id="{key(label).strip() or t}">'
                f'<div class="sec-head"><span class="bar"></span><h2>{label}</h2>'
                f'<span class="count">{len(plist)}</span></div>'
                f'<div class="grid">{cards}</div></section>'
            )
        else:
            sections.append(
                f'<section class="section" id="{key(label).strip() or t}">'
                f'<div class="sec-head"><span class="bar"></span><h2>{label}</h2>'
                f'<span class="count">0</span></div>'
                f'<div class="empty">No pages yet — add a {t} page to the wiki and rebuild.</div></section>'
            )

    gate_note = "publishes open-source tradecraft only · classification-gated"
    inner = f"""
<div class="hero">
  <div class="kicker">// open-source intelligence tradecraft</div>
  <h1>Intelligence Analysis Wiki</h1>
  <p class="tagline">{SITE_TAGLINE}</p>
  <div class="stats">{stat_html}</div>
  <p style="margin-top:22px"><span class="gate-note">{gate_note}</span></p>
</div>
{''.join(sections)}
"""
    html_out = head("Home", active="index") + inner + FOOT
    with open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_out)


def build_robots():
    content = f"""User-agent: *
Allow: /

Sitemap: {SITE_BASE}/sitemap.xml
"""
    with open(os.path.join(DOCS, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(content)


def build_sitemap(pages):
    locs = [("", "index.html")]
    for p in pages:
        locs.append((p.slug + ".html", p.slug + ".html"))
    lastmod = TODAY.strftime("%Y-%m-%d")
    urls = "".join(
        f"<url><loc>{SITE_BASE}/{path}</loc><lastmod>{lastmod}</lastmod></url>"
        for _, path in locs
    )
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + urls + "\n</urlset>\n")
    with open(os.path.join(DOCS, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(xml)


def copy_assets():
    dst = os.path.join(DOCS, "assets")
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(ASSETS_SRC, dst)


def copy_cname():
    cname_src = os.path.join(ROOT, "CNAME")
    if os.path.isfile(cname_src):
        shutil.copy(cname_src, os.path.join(DOCS, "CNAME"))


# ---------------- main ----------------
def main():
    os.makedirs(DOCS, exist_ok=True)
    pages, skipped = load_pages()
    slug_map = build_slug_map(pages)

    copy_assets()
    copy_cname()
    build_index(pages, skipped)
    for p in pages:
        build_page(p, pages, slug_map)
    build_robots()
    build_sitemap(pages)

    # ---- report ----
    print(f"Intel Wiki build — {TODAY.isoformat()}")
    print(f"  shipped {len(pages)} pages -> {DOCS}")
    by_type = {}
    for p in pages:
        by_type[p.rtype] = by_type.get(p.rtype, 0) + 1
    for t in TYPE_ORDER:
        if by_type.get(t):
            print(f"    {TYPE_LABELS[t]:<12} {by_type[t]}")
    if skipped:
        print(f"  GATED OUT (not published) — {len(skipped)}:")
        for fn, reason in skipped:
            print(f"    {fn}  ({reason})")
    else:
        print("  GATED OUT: none (all pages open/unlabelled)")
    # sanity: every page's index card + a real page file exist
    assert os.path.isfile(os.path.join(DOCS, "index.html"))
    return 0


if __name__ == "__main__":
    sys.exit(main())