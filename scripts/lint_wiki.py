#!/usr/bin/env python3
"""Manual wiki lint: counts + wikilink resolution + orphan detection."""
import os, re, glob
from pathlib import Path

WIKI = str(Path(__file__).resolve().parent.parent / "wiki")

# gather all md files
pages = []
for root, _, files in os.walk(WIKI):
    for f in files:
        if f.endswith(".md"):
            pages.append(os.path.join(root, f))

basenames = {}
for p in pages:
    bn = os.path.splitext(os.path.basename(p))[0]
    basenames.setdefault(bn, []).append(p)

print(f"TOTAL wiki .md pages: {len(pages)}")

# count by dir
from collections import Counter
dirs = Counter()
for p in pages:
    rel = os.path.relpath(os.path.dirname(p), WIKI)
    top = rel.split("/")[0] if rel != "." else "(root)"
    dirs[top] += 1
print("By top dir:", dict(dirs))

# collect wikilinks
link_re = re.compile(r"\[\[([^\]\|#]+)")
all_links = {}  # target -> set of source pages
for p in pages:
    with open(p, encoding="utf-8", errors="ignore") as fh:
        txt = fh.read()
    for m in link_re.finditer(txt):
        tgt = m.group(1).strip()
        # normalize: strip path-like prefix (raw/processed/...) -> take basename
        if "/" in tgt:
            tgt = tgt.split("/")[-1]
            tgt = os.path.splitext(tgt)[0]
        all_links.setdefault(tgt, set()).add(os.path.basename(p))

broken = {}
for tgt, sources in all_links.items():
    # a link resolves if a page basename equals tgt, OR it's an external-style raw/ link (ignore those)
    if tgt in basenames:
        continue
    # ignore links that look like file paths outside wiki (raw/...)
    broken.setdefault(tgt, set()).update(sources)

print(f"\nDistinct link targets: {len(all_links)}")
print(f"Potentially BROKEN link targets (no matching page): {len(broken)}")
for tgt, srcs in sorted(broken.items()):
    print(f"  [[{tgt}]]  <- referenced by {len(srcs)} page(s): {list(srcs)[:3]}")

# orphan pages: pages never linked from any other page
linked_targets = set(all_links.keys())
# also account for self-normalization: build set of all known basenames
known = set(basenames.keys())
orphans = []
for bn in known:
    if bn in linked_targets:
        continue
    # skip index/purpose/overview/hub usage pages? just report
    orphans.append(bn)
print(f"\nPages never linked from any other page (orphans, {len(orphans)}):")
for o in sorted(orphans):
    print(f"  {o}")
