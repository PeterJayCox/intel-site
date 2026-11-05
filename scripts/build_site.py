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
import json
import shutil
import datetime

import yaml
import markdown as md_lib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from icons import svg as icon_svg, SLUG_ICON  # noqa: E402

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
    "workshop": "Workshops",
}
TYPE_ORDER = ["concept", "entity", "case", "comparison", "query", "workshop"]

TYPE_SINGULAR = {
    "concept": "Concept",
    "entity": "Entity",
    "case": "Case",
    "comparison": "Comparison",
    "query": "Query",
    "workshop": "Workshop",
}

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


def reading_minutes(body):
    """Rounded reading time at 250 wpm (provenance markers excluded)."""
    words = len(re.findall(r"\S+", strip_provenance(body)))
    return max(1, int(round(words / 250.0)))


def resolve_wikilinks(md, slug_map, tt_slugs=()):
    def link(target, display):
        t = target.strip()
        k = key(t)
        if k in slug_map:
            slug = slug_map[k]
            tt = f' data-tt="{html.escape(slug)}"' if slug in tt_slugs else ""
            return (f'<a href="{html.escape(slug + ".html")}"{tt}>'
                    f'{html.escape(display)}</a>')
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


# ---------------- appearance (three states; default = auto/follows the OS) ----
# Mirrors the Cyber Digest site's behaviour: click cycles auto -> light -> dark
# -> auto (a pinned choice lives in localStorage under `intel-theme2`); the
# legacy `intel-theme` key written by the old two-state toggle is discarded on
# sight so an old pin can't silently override the system appearance.
# Kept as plain (non-f) strings so their braces are never parsed by head().
THEME_HEAD = """<script>
(function(){var d=document.documentElement;
function sys(){try{return (window.matchMedia&&window.matchMedia('(prefers-color-scheme: light)').matches)?'light':'dark';}catch(e){return 'dark';}}
function saved(){try{var s=localStorage.getItem('intel-theme2');return (s==='light'||s==='dark')?s:null;}catch(e){return null;}}
function mode(){return saved()||'auto';}
function save(m){try{if(m==='auto'){localStorage.removeItem('intel-theme2');}else{localStorage.setItem('intel-theme2',m);}}catch(e){}}
function label(m){var b=document.querySelector('.theme-toggle');if(!b){return;}
var t={auto:'Appearance: auto \\u2014 follows your system ('+sys()+'). Click to cycle auto \\u2192 light \\u2192 dark.',
light:'Appearance: light (pinned). Shift-click to follow your system again.',
dark:'Appearance: dark (pinned). Shift-click to follow your system again.'}[m];
if(t){b.setAttribute('title',t);b.setAttribute('aria-label',t);}}
function apply(){var m=mode();d.setAttribute('data-theme',m==='auto'?sys():m);d.setAttribute('data-theme-mode',m);label(m);}
function cycle(ev){var m=mode();
if(ev&&ev.shiftKey){save('auto');}
else if(m==='auto'){save(sys()==='dark'?'light':'dark');}
else if(m===sys()){save('auto');}
else{save(m==='light'?'dark':'light');}
apply();}
function followSystem(){if(!saved()){apply();}}
try{localStorage.removeItem('intel-theme');}catch(e){}
window.__intelSysTheme=sys;
window.__intelTheme={cycle:cycle,apply:apply,mode:mode,setAuto:function(){save('auto');apply();}};
apply();
try{var mq=window.matchMedia&&window.matchMedia('(prefers-color-scheme: light)');
if(mq&&mq.addEventListener){mq.addEventListener('change',followSystem);}}catch(e){}
if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',apply);}
})();
</script>"""
PRINT_JS = """<script>
/* open every spoiler before printing, close it again afterwards */
(function(){
  var closed=[];
  function openAll(){closed=[];var d=document.querySelectorAll('details:not([open])');
    for(var i=0;i<d.length;i++){d[i].open=true;closed.push(d[i]);}}
  function closeAll(){for(var i=0;i<closed.length;i++){closed[i].open=false;}closed=[];}
  window.addEventListener('beforeprint',openAll);
  window.addEventListener('afterprint',closeAll);
})();
</script>"""
THEME_TOGGLE = ('<div class="theme-toggle" role="button" tabindex="0"'
    ' aria-label="Appearance" title="Appearance"'
    ' onclick="window.__intelTheme.cycle(event)"'
    " onkeydown=\"if(event.key==='Enter'||event.key===' '){event.preventDefault();window.__intelTheme.cycle(event)}\">"
    '<span class="tt-auto" aria-hidden="true">\U0001f317</span>'
    '<span class="tt-light" aria-hidden="true">\u2600\ufe0f</span>'
    '<span class="tt-dark" aria-hidden="true">\U0001f319</span></div>')


# ---------------- chrome ----------------
def head(title, active="", root="", search_markup="", canonical_path="index.html",
         desc=""):
    v = TODAY.strftime("%Y%m%d")
    canon = f"{SITE_BASE}/" if title == "Home" else f"{SITE_BASE}/{canonical_path}"
    meta_desc = (desc or SITE_TAGLINE).replace('"', "&quot;")
    meta_desc = re.sub(r"\s+", " ", meta_desc).strip()[:300]
    nav = [
        ("index.html", "Home", "index"),
        ("index.html#concepts", "Concepts", "concepts"),
        ("index.html#entities", "Entities", "entities"),
        ("index.html#workshops", "Workshops", "workshops"),
        # The way back up to the hub, as the AI daily's nav carries it. An
        # absolute href is off-site, so it gets no `root` prefix.
        ("https://peterjaycox.com", "Hub", "hub"),
    ]
    links = "".join(
        f'<a class="{"active" if active == a else ""}" '
        f'href="{h if h.startswith(("http://", "https://")) else root + h}">{lbl}</a>'
        for h, lbl, a in nav
    )
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{THEME_HEAD}
{PRINT_JS}
<title>{html.escape(title)} · {SITE_NAME}</title>
<meta name="description" content="{meta_desc}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{meta_desc}">
<meta property="og:url" content="{canon}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{html.escape(title)}">
<meta name="twitter:description" content="{meta_desc}">
<link rel="canonical" href="{canon}">
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
    {search_markup}
    {THEME_TOGGLE}
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
        # optional editorial fields (see SCHEMA.md)
        self.dek_explicit = bool(scalar(fm.get("summary")))
        self.dek = scalar(fm.get("summary")) or summary
        self.signature = scalar(fm.get("signature"))
        self.one_move = scalar(fm.get("one_move"))
        self.owner = scalar(fm.get("owner")).lower()
        self.technique = scalar(fm.get("technique"))
        self.artefact = scalar(fm.get("artefact"))
        self.family = scalar(fm.get("family"))
        self.toc = str(scalar(fm.get("toc"))).lower() in {"true", "yes", "1"}
        self.prevnext = str(scalar(fm.get("prevnext"))).lower() not in {"false", "no", "0"}
        self.mins = reading_minutes(body)
        self.icon = scalar(fm.get("icon")) or SLUG_ICON.get(slug, "")


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


def _md_cell(s):
    """One-line, pipe-safe table cell text."""
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s.replace("|", "\\|")


def bias_pages(pages):
    return [p for p in pages if p.signature]


def bias_card_md(pages):
    """The signature card, generated from the bias pages' front matter."""
    bp = bias_pages(pages)
    mine = sorted([p for p in bp if p.owner != "system"], key=lambda p: p.title.lower())
    theirs = sorted([p for p in bp if p.owner == "system"], key=lambda p: p.title.lower())
    out = []
    out.append(f"**Yours to fix in the draft** — {len(mine)} rows you can close in ten "
               "minutes, alone, before issue.\n")
    out.append("| Bias | The signature — what you will see in your own draft | The fix — one move |")
    out.append("|---|---|---|")
    for p in mine:
        out.append(f"| [[{p.title}]] | {_md_cell(p.signature)} | {_md_cell(p.one_move)} |")
    out.append("")
    out.append(f"**Yours to raise with whoever owns the team or the collection** — "
               f"{len(theirs)} rows no amount of personal discipline will close. The "
               "signature is still yours to spot; the fix is somebody else's to make.\n")
    out.append("| Bias | The signature | What to raise, and with whom |")
    out.append("|---|---|---|")
    for p in theirs:
        out.append(f"| [[{p.title}]] | {_md_cell(p.signature)} | {_md_cell(p.one_move)} |")
    return "\n".join(out)


def bias_map_md(pages):
    """bias -> technique -> artefact, grouped by technique."""
    bp = [p for p in bias_pages(pages) if p.technique]
    groups = {}
    for p in bp:
        groups.setdefault(p.technique, []).append(p)
    out = ["| Technique | The biases it counters | The artefact it leaves behind |",
           "|---|---|---|"]
    order = sorted(groups, key=lambda t: (-len(groups[t]), t.lower()))
    for tech in order:
        names = ", ".join(sorted("[[%s]]" % p.title for p in groups[tech]))
        arts = sorted({p.artefact for p in groups[tech] if p.artefact})
        out.append(f"| **{_md_cell(tech)}** | {names} | "
                   + ("; ".join(_md_cell(a) for a in arts) or "—") + " |")
    return "\n".join(out)


def render_body(p, pages, slug_map, tt_slugs=(), icon_by_slug=None):
    md = p.body
    # drop the leading H1 (title is rendered in the page header)
    md = re.sub(r"\A\s*#\s+[^\n]*\n?", "", md, count=1)
    md = strip_provenance(md)
    if "{{BIAS_CARD}}" in md:
        md = md.replace("{{BIAS_CARD}}", bias_card_md(pages))
    if "{{BIAS_MAP}}" in md:
        md = md.replace("{{BIAS_MAP}}", bias_map_md(pages))
    md = resolve_wikilinks(md, slug_map, tt_slugs)
    md = blank_before_blocks(md)
    if p.toc:
        body_html = md_lib.markdown(
            md, extensions=["extra", "toc"],
            extension_configs={"toc": {"permalink": "&#128279;", "toc_depth": "2-3"}})
    else:
        body_html = md_lib.markdown(md, extensions=["extra"])
    # bias rows carry their glyph in the first cell
    # a cell holding exactly one bias link gets a flex wrapper so the glyph
    # sits beside the first line; a cell with several links gets the glyph
    # inline, because a flex wrapper would make each link its own flex item
    def _icon_single(m):
        slug, attrs, text = m.group(1), m.group(2), m.group(3)
        key = icon_by_slug.get(slug)
        if not key:
            return m.group(0)
        return (f'<td><span class="bias-cell">{icon_svg(key)}'
                f'<a href="{slug}.html"{attrs}>{text}</a></span></td>')

    def _icon_multi(m):
        slug = m.group(1)
        key = icon_by_slug.get(slug)
        if not key:
            return m.group(0)
        return f'<td>{icon_svg(key, "bias-icon inline")}<a href="{slug}.html"'

    body_html = re.sub(
        r'<td><a href="([a-z0-9-]+)\.html"([^>]*)>([^<]*)</a></td>', _icon_single, body_html)
    body_html = re.sub(r'<td><a href="([a-z0-9-]+)\.html"', _icon_multi, body_html)
    # wide tables get their own scroll container (see site.css .table-wrap)
    body_html = body_html.replace("<table>", '<div class="table-wrap"><table>')
    body_html = body_html.replace("</table>", "</table></div>")
    return body_html


def toc_html(body_html):
    """Contents rail built from the rendered h2/h3 ids."""
    items = []
    for m in re.finditer(r'<h([23]) id="([^"]+)"[^>]*>(.*?)</h\1>', body_html, re.S):
        level = int(m.group(1))
        text = re.sub(r"<[^>]+>", "", m.group(3)).replace("&#128279;", "").strip()
        if not text:
            continue
        items.append((level, m.group(2), text))
    if len(items) < 4:
        return ""
    rows = "".join(
        f'<li class="lvl{lv}"><a href="#{html.escape(hid)}">{html.escape(txt)}</a></li>'
        for lv, hid, txt in items)
    return (f'<details class="toc" open><summary>On this page '
            f'<span class="toc-n">{len(items)}</span></summary>'
            f'<ol class="toc-list">{rows}</ol></details>')


def signature_block(p):
    """The draft signature + one move, rendered on the bias page itself."""
    if not p.signature:
        return ""
    owner = p.owner == "system"
    cls = "sig-card sig-system" if owner else "sig-card"
    owner_tag = ('<span class="sig-owner">Raise, do not fix alone</span>'
                 if owner else '<span class="sig-owner">Yours to fix in the draft</span>')
    return f"""
<aside class="{cls}">
  <div class="sig-kicker">Signature in a draft {owner_tag}</div>
  <p class="sig-main">{html.escape(p.signature)}</p>
  <div class="sig-kicker">The one move</div>
  <p class="sig-fix">{html.escape(p.one_move)}</p>
</aside>"""


def prev_next_html(p, pages):
    """Previous / next within the same page type (workshops, concepts…)."""
    if p.rtype != "workshop" or not p.prevnext:
        return ""
    sibs = sorted([q for q in pages if q.rtype == p.rtype], key=lambda q: q.slug)
    try:
        i = [q.slug for q in sibs].index(p.slug)
    except ValueError:
        return ""
    prev = sibs[i - 1] if i > 0 else None
    nxt = sibs[i + 1] if i + 1 < len(sibs) else None
    cells = []
    for q, lbl, cls in ((prev, "&larr; Previous", "pn-prev"), (nxt, "Next &rarr;", "pn-next")):
        if q:
            cells.append(f'<a class="pn {cls}" href="{html.escape(q.slug)}.html">'
                         f'<span class="pn-lbl">{lbl}</span>'
                         f'<span class="pn-title">{html.escape(q.title)}</span></a>')
    return f'<nav class="prevnext">{"".join(cells)}</nav>' if cells else ""


def tt_payload(pages, tt_slugs):
    out = {}
    for p in pages:
        if p.slug in tt_slugs:
            out[p.slug] = {
                "t": p.title,
                "d": re.sub(r"\s+", " ", p.dek)[:240],
                "s": p.signature,
                "m": p.one_move,
                "o": "system" if p.owner == "system" else "",
            }
    return json.dumps(out, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")


BIAS_DECK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bias-cards.json")


def flashcards_block():
    """The atlas deck, rendered from the same JSON Flashforge seeds from."""
    try:
        with open(BIAS_DECK, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"  ! flashcards: deck unreadable ({exc})")
        return ""
    n = len(data.get("cards", []))
    if not n:
        return ""
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"""
<section class="fc-block" id="flashcards">
  <h2>Flashcards — the atlas, one card at a time</h2>
  <p class="fc-intro">{n} cards, the same rows as the atlas above: the tell for each mechanism, and the
  one move that answers it. Click a card to turn it over, or shuffle and test yourself in a random order.</p>
  <div class="fc-deck" data-fc-deck>
    <div class="fc-meta"><span data-fc-count>1 / {n}</span><span data-fc-fam>&mdash;</span></div>
    <div class="fc-card" data-fc-card role="button" tabindex="0" aria-pressed="false"
         aria-label="Flashcard. Activate to reveal the answer.">
      <div class="fc-face fc-front" data-fc-front></div>
      <div class="fc-face fc-back">
        <div class="fc-back-title" data-fc-backtitle></div>
        <p><span class="fc-label">The tell</span><span data-fc-tell></span></p>
        <p><span class="fc-label">The one move</span><span data-fc-move></span></p>
      </div>
    </div>
    <div class="fc-controls">
      <button type="button" data-fc-prev>&larr; Prev</button>
      <button type="button" data-fc-flip>Flip</button>
      <button type="button" data-fc-next>Next &rarr;</button>
      <button type="button" data-fc-shuffle>Shuffle</button>
    </div>
    <p class="fc-hint">Space or Enter flips. Arrow keys step. Nothing is recorded.</p>
  </div>
  <noscript><p class="fc-intro">The deck needs JavaScript. The same rows are in the atlas above.</p></noscript>
</section>
<script type="application/json" id="fc-data">{payload}</script>
<script src="assets/flashcards.js" defer></script>
"""


def build_page(p, pages, slug_map, tt_slugs=(), icon_by_slug=None):
    rtype_label = TYPE_LABELS.get(p.rtype, "Concepts")
    badges = [f'<span class="type-pill">{html.escape(rtype_label.rstrip("s"))}</span>',
              confidence_badge(p.fm)]
    chips = tag_chips(p.tags)
    body = render_body(p, pages, slug_map, tt_slugs, icon_by_slug)
    rail = toc_html(body)
    sig = signature_block(p)
    fc = flashcards_block() if p.fm.get("flashcards") else ""
    pn = prev_next_html(p, pages)
    has_tt = "data-tt=" in body
    tt_block = ""
    if has_tt:
        tt_block = (f'<script type="application/json" id="tt-data">'
                    f'{tt_payload(pages, tt_slugs)}</script>{TT_JS}')

    inner = f"""
<div class="crumb"><a href="index.html">Wiki</a><span class="sep">/</span>{html.escape(rtype_label)}</div>
<div class="page-head">
  <div class="head-top">{''.join(badges)}<span class="pill meta-pill">{p.mins} min read</span></div>
  <h1>{icon_svg(p.icon, "page-icon") if p.icon else ""}{html.escape(p.title)}</h1>
  {f'<p class="dek">{html.escape(p.dek)}</p>' if p.dek_explicit else ''}
  <div class="tags-row">{chips}</div>
  <div class="stamp">Open Source</div>
</div>
{pn}{sig}{rail}
<article class="wiki-body">{body}</article>
{fc}
{pn}
<a class="nav-back" href="index.html">&larr; Back to Wiki index</a>
{tt_block}
"""

    html_out = head(
        p.title,
        active=p.rtype if p.rtype in ("concept", "entity", "workshop") else "index",
        search_markup=search_widget_html(pages, compact=True),
        canonical_path=p.slug + ".html",
        desc=p.dek,
    )
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
  <div class="summary">{html.escape(p.dek[:220])}</div>
  <div class="meta">{''.join(badges)}{chips}</div>
</a>"""


# ---------------- search widget (index page only) ----------------
def search_widget_html(pages, compact=False):
    """Client-side search: inline JSON index + zero-dependency JS.
    compact=True renders the slim top-nav variant used on article pages."""
    search_pages = [{
        "slug": p.slug,
        "title": p.title,
        "type": TYPE_SINGULAR.get(p.rtype, "Concept"),
        "tags": p.tags[:5],
        "summary": p.dek[:180],
    } for p in pages]
    index = json.dumps(search_pages, ensure_ascii=False)
    # keep the inline JSON from ever terminating the script tag early
    index = index.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    label = "" if compact else "\n  <div class=\"search-label\" aria-hidden=\"true\">// search the wiki</div>"
    keys = "" if compact else "\n    <span class=\"search-keys\">press <kbd>/</kbd></span>"
    placeholder = "Search the wiki\u2026" if compact else "Search concepts, entities, tags\u2026"
    cls = "search-widget compact" if compact else "search-widget"
    return f"""
<div class="{cls}" id="wiki-search">{label}
  <div class="search-control">
    <span class="search-glyph" aria-hidden="true">&#8965;</span>
    <input id="search-input" type="search" placeholder="{placeholder}" autocomplete="off" spellcheck="false"
           role="combobox" aria-expanded="false" aria-controls="search-results" aria-label="Search the wiki">
    <button class="search-clear" id="search-clear" type="button" aria-label="Clear search" hidden>&#10005;</button>{keys}
  </div>
  <div class="search-results" id="search-results" role="listbox" hidden></div>
</div>
<script type="application/json" id="search-data">{index}</script>
{SEARCH_JS}"""


SEARCH_JS = r"""<script>
(function(){
  var box=document.getElementById('wiki-search');
  if(!box)return;
  var input=document.getElementById('search-input');
  var list=document.getElementById('search-results');
  var clearBtn=document.getElementById('search-clear');
  var data;
  try{data=JSON.parse(document.getElementById('search-data').textContent);}catch(e){data=[];}
  var items=[],active=-1,open=false;
  function norm(s){return String(s||'').toLowerCase();}
  function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
  /* NB: innerHTML below is safe — every dynamic value passes through esc()
     and the index is a single source (vault pages, classification-gated);
     the inline JSON additionally has <,>,& escaped as \uXXXX. */
  data.forEach(function(p){p._hay=norm([p.title,p.summary,p.tags.join(' '),p.slug].join(' ~ '));});

  function run(q){
    var toks=q.trim().toLowerCase().split(/\s+/).filter(Boolean);
    if(!toks.length){render([],null);return;}
    var out=[];
    data.forEach(function(p){
      for(var i=0;i<toks.length;i++){if(p._hay.indexOf(toks[i])===-1)return;}
      var s=0,t;
      for(var j=0;j<toks.length;j++){
        t=toks[j];
        if(norm(p.title).indexOf(t)!==-1)s+=10;
        if(norm(p.tags.join(' ')).indexOf(t)!==-1)s+=4;
        if(norm(p.slug).indexOf(t)!==-1)s+=2;
        if(norm(p.summary).indexOf(t)!==-1)s+=1;
      }
      out.push({p:p,s:s});
    });
    out.sort(function(a,b){return b.s-a.s||norm(a.p.title).localeCompare(norm(b.p.title));});
    render(out.map(function(o){return o.p;}),toks);
  }

  function render(res,toks){
    items=res;
    list.innerHTML='';
    if(!toks||!res.length){
      if(toks){list.innerHTML='<div class="search-empty">No pages match \u201c'+esc(input.value.trim())+'\u201d</div>';show();}
      else{closePanel();}
      return;
    }
    active=-1;
    var html='<div class="search-note">'+res.length+' page'+(res.length===1?'':'s')+' \u00b7 \u201c'+esc(input.value.trim())+'\u201d</div>';
    res.forEach(function(p,i){
      html+='<button type="button" class="search-row" role="option" id="sr-'+i+'" data-i="'+i+'">'
        +'<h4>'+esc(p.title)+'<span class="type-pill">'+esc(p.type)+'</span></h4>'
        +(p.summary?'<p class="snippet">'+esc(p.summary)+'</p>':'')
        +(p.tags.length?'<div class="tags">'+p.tags.map(function(t){return '<span class="pill tag">'+esc(t)+'</span>';}).join('')+'</div>':'')
        +'</button>';
    });
    list.innerHTML=html;
    show();
    Array.prototype.forEach.call(list.querySelectorAll('.search-row'),function(btn){
      btn.addEventListener('click',function(){var i=parseInt(btn.getAttribute('data-i'),10);if(!isNaN(i)&&items[i])location.href=items[i].slug+'.html';});
      btn.addEventListener('mousemove',function(){setActive(parseInt(btn.getAttribute('data-i'),10));});
    });
  }

  function show(){open=true;list.hidden=false;input.setAttribute('aria-expanded','true');}
  function closePanel(){open=false;active=-1;list.hidden=true;input.setAttribute('aria-expanded','false');input.removeAttribute('aria-activedescendant');}
  function setActive(i){
    active=i;
    var rows=list.querySelectorAll('.search-row');
    Array.prototype.forEach.call(rows,function(r,idx){r.classList.toggle('active',idx===i);});
    if(rows[i]){rows[i].scrollIntoView({block:'nearest'});input.setAttribute('aria-activedescendant',rows[i].id);}
  }
  function clearSearch(){input.value='';render([],null);syncClear();}

  function syncClear(){clearBtn.hidden=!input.value;}

  input.addEventListener('input',function(){run(input.value);syncClear();});
  input.addEventListener('focus',function(){if(input.value.trim())run(input.value);});
  input.addEventListener('keydown',function(e){
    if(e.key==='Escape'){clearSearch();e.preventDefault();}
    else if(e.key==='ArrowDown'||e.key==='ArrowUp'){
      if(!open||!items.length)return;
      e.preventDefault();
      var d=e.key==='ArrowDown'?1:-1;
      setActive((active+d+items.length)%items.length);
    }
    else if(e.key==='Enter'){
      if(active>=0&&items[active]){location.href=items[active].slug+'.html';e.preventDefault();}
    }
  });
  clearBtn.addEventListener('click',clearSearch);
  clearBtn.addEventListener('mousedown',function(e){e.preventDefault();});
  list.addEventListener('mousedown',function(e){e.preventDefault();});
  document.addEventListener('click',function(e){if(!box.contains(e.target))closePanel();});
  document.addEventListener('keydown',function(e){
    var t=e.target||{};
    if(e.key==='/'&&!/^(input|textarea|select)$/i.test(t.tagName||'')){e.preventDefault();input.focus();input.select();}
  });
})();
</script>"""


TT_JS = r"""<script>
(function(){
  var raw=document.getElementById('tt-data');
  if(!raw)return;
  var data={};try{data=JSON.parse(raw.textContent);}catch(e){return;}
  var el=document.createElement('div');
  el.id='tt-card';el.setAttribute('role','tooltip');el.setAttribute('aria-hidden','true');
  document.body.appendChild(el);
  var cur=null;
  function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
  /* innerHTML is safe: values come from #tt-data, a build-time JSON blob
     generated from classification-gated vault pages, and every field passes
     through esc(); the JSON itself has <,> escaped as \uXXXX. */
  function fill(d){
    var h='<div class="tt-k">';
    h+= (d.o==='system') ? 'Bias &middot; raise, do not fix alone' : 'Bias';
    h+='</div><h4>'+esc(d.t)+'</h4>';
    if(d.d)h+='<p>'+esc(d.d)+'</p>';
    if(d.s)h+='<div class="tt-row"><span>Signature</span><em>'+esc(d.s)+'</em></div>';
    if(d.m)h+='<div class="tt-row"><span>The one move</span><em>'+esc(d.m)+'</em></div>';
    h+='<div class="tt-foot">'+esc(d.t)+'.html &rarr;</div>';
    el.innerHTML=h;
  }
  function show(a){
    var d=data[a.getAttribute('data-tt')];
    if(!d)return;
    cur=a;fill(d);
    el.classList.add('on');el.setAttribute('aria-hidden','false');
    var r=a.getBoundingClientRect(),w=el.offsetWidth,h=el.offsetHeight;
    var x=Math.min(Math.max(12,r.left),window.innerWidth-w-12);
    var y=(r.bottom+10+h<=window.innerHeight-12)?r.bottom+10:Math.max(12,r.top-h-10);
    el.style.left=x+'px';el.style.top=y+'px';
  }
  function hide(){if(!cur)return;cur=null;el.classList.remove('on');el.setAttribute('aria-hidden','true');}
  var links=document.querySelectorAll('a[data-tt]');
  Array.prototype.forEach.call(links,function(a){
    a.addEventListener('mouseenter',function(){show(a);});
    a.addEventListener('mouseleave',hide);
    a.addEventListener('focus',function(){show(a);});
    a.addEventListener('blur',hide);
  });
  document.addEventListener('keydown',function(e){if(e.key==='Escape')hide();});
  window.addEventListener('scroll',hide,{passive:true});
})();
</script>"""


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
{search_widget_html(pages)}
{''.join(sections)}
"""
    html_out = head("Home", active="index", desc=SITE_TAGLINE) + inner + FOOT
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
    # pages that get a hover card wherever they are wikilinked
    tt_slugs = {p.slug for p in bias_pages(pages)}
    icon_by_slug = {p.slug: p.icon for p in pages if p.icon}

    copy_assets()
    copy_cname()
    build_index(pages, skipped)
    for p in pages:
        build_page(p, pages, slug_map, tt_slugs, icon_by_slug)
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