#!/usr/bin/env python3
"""Clause-aware status check for the Intel workshop pages.

A status must agree with ITS OWN clause, not with the whole row: a compound row may
legitimately carry several statuses for different subjects (reported for a name,
inferred for a camera operator, unknown for identity). Run after any edit, before a build.
"""
import io, os, re, sys

VAULT = os.path.expanduser(
    "~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Peter's Vault")
W = os.path.join(VAULT, "Intel", "Wiki", "workshops")

FILES = {
    "participant": os.path.join(W, "critical-thinking-workshop-01-train-preacher.md"),
    "facilitator": os.path.join(W, "critical-thinking-workshop-01-train-preacher-facilitator.md"),
    "transfer": os.path.join(VAULT, "Intel", "DRAFT-Workshop-01b-transfer-case.md"),
}

CONTRA_OBSERVED = [r"never shown", r"never appears", r"unseen", r"cannot be seen",
                   r"attributes no line", r"not identifiable", r"\binferred\b"]
# positive forms only: "never appears on screen" is the opposite of "is on screen"
CONTRA_INFERRED = [r"\bis on screen\b", r"\bare on screen\b", r"visible in the clip"]

fail = 0
for name, path in FILES.items():
    if not os.path.isfile(path):
        print("=== %s: MISSING (%s)" % (name, path)); fail += 1; continue
    src = io.open(path, encoding="utf-8").read()
    body = src.split("---", 2)[-1]
    print("=== %s" % name)
    n = 0
    for line in body.split("\n"):
        if not line.startswith("|"):
            continue
        for cell in [c.strip() for c in line.strip("|").split("|")]:
            for clause in re.split(r"(?<=[.;:])\s+|\s+·\s+", cell):
                m = re.search(r"\*\*(observed|reported|inferred|unknown)\*\*", clause, re.I)
                if not m:
                    continue
                n += 1
                tag, c = m.group(1).lower(), clause.lower()
                if tag == "observed":
                    for p in CONTRA_OBSERVED:
                        if re.search(p, c):
                            print("  FLAG observed vs %s: %s" % (p, clause[:110])); fail += 1
                if tag == "inferred":
                    for p in CONTRA_INFERRED:
                        if re.search(p, c):
                            print("  FLAG inferred vs %s: %s" % (p, clause[:110])); fail += 1
    print("  status clauses checked: %d" % n)

print()
print("RESULT:", "clean" if fail == 0 else "%d flags" % fail)
sys.exit(1 if fail else 0)
