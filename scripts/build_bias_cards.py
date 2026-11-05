#!/usr/bin/env python3
"""Build the bias deck once, from the wiki source of truth.

Writes scripts/bias-cards.json, consumed by:
  - the Intel site build (the in-page deck at the bottom of the workshop)
  - the Flashforge seed bundle in the cyber site
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

VAULT = os.path.expanduser("~/Library/Mobile Documents/iCloud~md~obsidian/Documents/"
                           "Peter's Vault/Intel/Wiki/concepts")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bias-cards.json")

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required")


def scalar(v):
    if v is None:
        return ""
    if isinstance(v, list):
        return "; ".join(str(x).strip() for x in v)
    return str(v).strip()


cards = []
for name in sorted(os.listdir(VAULT)):
    if not name.endswith(".md"):
        continue
    raw = open(os.path.join(VAULT, name), encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---", raw, re.S)
    if not m:
        continue
    fm = yaml.safe_load(m.group(1)) or {}
    if not fm.get("icon"):
        continue
    title = scalar(fm.get("title")) or name[:-3].replace("-", " ").title()
    sig = scalar(fm.get("signature"))
    move = scalar(fm.get("one_move"))
    if not (sig and move):
        print(f"  skip {name}: missing signature or one_move")
        continue
    family = scalar(fm.get("family")) or "cognitive"
    owner = scalar(fm.get("owner")) or "analyst"
    kind = "structural" if family == "structural" else "cognitive"
    cards.append({
        "slug": name[:-3],
        "title": title,
        "front": f"{title} — what is the tell, and what is the one move?",
        "signature": sig,
        "move": move,
        "family": family,
        "owner": owner,
        "tags": list(dict.fromkeys([kind, family, owner])),
    })

# cognitive first, structural after, each alphabetical
cards.sort(key=lambda c: (c["family"] == "structural", c["title"].lower()))

payload = {
    "title": "The bias atlas",
    "deck": "Intel · Bias Atlas",
    "cards": cards,
}
json.dump(payload, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"wrote {len(cards)} cards -> {OUT}")
print("  cognitive:", sum(1 for c in cards if c["family"] != "structural"),
      "| structural:", sum(1 for c in cards if c["family"] == "structural"))
