#!/usr/bin/env python3
"""v2 middleware: Obsidian vault (Markdown) -> JSON contract -> static viewer.

Local-first paradigm:
- Source of truth = local Obsidian vault (managed by the user, optionally git-versioned).
- This script is the ONLY converter: it reads the vault and emits a JSON contract
  (slim wiki-bundle.json + wiki-content.json) plus a ready-to-serve static site.
- GitHub (or any host) is just a dumb static CDN; it never holds the editable vault.

History model (the part that was "done poorly" before):
- Per-file version history is derived from LOCAL git (git log/show/diff). The vault
  is a git repo, so history is real, unbounded, and authoritative. Snapshots are
  pre-rendered into the content bundle (with full old text + line diff segments) so
  the deployed site is fully static and needs no git at view time.
- The "updated/新增" badge (diff_data / update_severity) is computed against a local
  _buildstate cache so edits are flagged on rebuild whether or not they are committed.
- The overall update log (更新记录/*.md) is parsed from the vault and stays the
  curated, human-written view; it is NOT disconnected from per-page history.
"""
import json
import re
import time
import difflib
import datetime
import subprocess
import hashlib
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
VAULT = ROOT / "vault"
OUTPUT = ROOT / "output"
BUILDSTATE = ROOT / ".buildstate.json"
MAX_HISTORY = 3  # number of git versions to pre-render per file

LINK_RE = re.compile(r'\[\[([^\]|#]+)(?:[|#][^\]]+)?\]\]')

files = {}
link_graph = defaultdict(int)
node_ids = set()

# ----------------------------------------------------------------------------
# git helpers (all local; degrade gracefully if vault is not a git repo)
# ----------------------------------------------------------------------------
def _git(repo, args, timeout=30):
    try:
        r = subprocess.run(["git", "-C", str(repo)] + args,
                           capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""

def git_history(repo, relpath):
    """Return list of (sha, date, msg) newest-first for a file (follows renames)."""
    if not (repo / ".git").exists():
        return []
    out = _git(repo, ["log", "--follow", "--format=%H%x1f%ci%x1f%s", "--", relpath])
    rows = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\x1f")
        if len(parts) < 3:
            continue
        rows.append((parts[0], parts[1][:19].replace("T", " "), parts[2]))
    return rows

def git_show(repo, relpath, sha):
    return _git(repo, ["show", f"{sha}:{relpath}"])

def git_diff_segments(repo, relpath, a_sha, b_sha):
    """Line-level diff segments between two commits (or empty tree if a_sha None)."""
    if a_sha is None:
        new = git_show(repo, relpath, b_sha)
        old_lines, new_lines = [], new.splitlines()
    else:
        cmd = ["diff", "--no-color", "-U0", a_sha, b_sha, "--", relpath]
        out = _git(repo, cmd)
        old_lines, new_lines = [], []
        for ln in out.splitlines():
            if ln.startswith("+++") or ln.startswith("---") or ln.startswith("@@"):
                continue
            if ln.startswith("+"):
                new_lines.append(ln[1:])
            elif ln.startswith("-"):
                old_lines.append(ln[1:])
            else:
                old_lines.append(ln[1:]); new_lines.append(ln[1:])
    return _segments(old_lines, new_lines)

def _segments(old_lines, new_lines):
    segs = []
    for dl in difflib.ndiff(old_lines, new_lines):
        if dl.startswith("+ "):
            segs.append({"type": "add", "text": dl[2:]})
        elif dl.startswith("- "):
            segs.append({"type": "del", "text": dl[2:]})
        elif dl.startswith("? "):
            continue
        else:
            segs.append({"type": "equal", "text": dl[2:]})
    return segs

# ----------------------------------------------------------------------------
# parsing (reused from bundle_wiki.py)
# ----------------------------------------------------------------------------
def _natural_sort_key(path):
    name = str(path)
    name = re.sub(r'第(\d+)次', lambda m: f'第{int(m.group(1)):03d}次', name)
    return name

def parse_file(md_file, base_dir):
    slug = str(md_file.relative_to(base_dir)).replace(".md", "")
    if not slug or slug in node_ids:
        return None
    node_ids.add(slug)
    content = md_file.read_text(encoding="utf-8", errors="replace")

    if slug.startswith("entities/"): page_type = "entity"
    elif slug.startswith("sources/"): page_type = "source"
    elif slug.startswith("topics/"): page_type = "topic"
    elif slug.startswith("Interesting_findings/"): page_type = "insight"
    elif slug.startswith("comparisons/"): page_type = "comparison"
    elif slug.startswith("synthesis/"): page_type = "synthesis"
    elif slug.endswith("overview"): page_type = "overview"
    else: page_type = "other"

    title = slug.split("/")[-1]
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("# ") and not line.startswith("## "):
            title = line[2:].strip(); break

    links = [m.group(1).strip() for m in LINK_RE.finditer(content)]

    updated_date = None
    m = re.search(r'^updated:\s*(\S+)', content, re.M)
    if m:
        try: updated_date = datetime.date.fromisoformat(m.group(1).strip())
        except Exception: updated_date = None

    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            body = parts[2]
    body = body.strip()
    return {
        "slug": slug, "path": str(md_file.relative_to(base_dir)),
        "title": title, "type": page_type, "body": body,
        "links": links, "updated_date": updated_date.isoformat() if updated_date else None,
        "mtime": md_file.stat().st_mtime,
    }

# ----------------------------------------------------------------------------
# buildstate (local cache for "updated/新增" badge across rebuilds)
# ----------------------------------------------------------------------------
def load_buildstate():
    if BUILDSTATE.exists():
        try: return json.loads(BUILDSTATE.read_text(encoding="utf-8"))
        except Exception: return {"files": {}}
    return {"files": {}}

def save_buildstate(bs):
    BUILDSTATE.write_text(json.dumps(bs, ensure_ascii=False), encoding="utf-8")

# ----------------------------------------------------------------------------
# update severity classification (reused)
# ----------------------------------------------------------------------------
VIEWPOINT_CHANGE_PATTERNS = [
    "下调至", "上调至", "转向", "转为", "转谨慎", "转积极",
    "由.*转", "由.*变", "从.*调整为", "从.*变",
    "估值锚点.*移动", "估值锚点.*调整",
    "方向变化", "方向反转", "评级.*调整", "证伪", "推翻",
]
def classify_update_severity(slug, page_type, dd):
    if not dd: return None
    dt = dd.get("type"); segs = dd.get("segments", [])
    if dt == "new": return "new"
    if dt == "metadata_only": return "updated"
    if dt == "updated":
        add = [s["text"] for s in segs if s["type"] == "add"]
        add_count = len(add); total = len(segs)
        add_ratio = add_count / max(total, 1)
        combined = "\n".join(add)
        if slug.startswith("topics/02_投资/"):
            for pat in VIEWPOINT_CHANGE_PATTERNS:
                if re.search(pat, combined): return "viewpoint"
        threshold = 0.06 if page_type == "topic" else 0.12
        if add_ratio > threshold or add_count > 15: return "major"
        return "updated"
    return None

# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def main():
    t0 = time.time()
    bs = load_buildstate()
    bs_files = bs.get("files", {})
    first_build = len(bs_files) == 0
    OUTPUT.mkdir(exist_ok=True)

    # 1) parse all markdown in vault
    for md_file in sorted(VAULT.rglob("*.md"), key=_natural_sort_key):
        rel = str(md_file.relative_to(VAULT))
        if rel.startswith(".") or "/.git/" in rel or rel.startswith(".history"):
            continue
        info = parse_file(md_file, VAULT)
        if not info: continue
        slug = info["slug"]; body = info["body"]
        cur_hash = hashlib.md5(body.encode("utf-8")).hexdigest()

        # --- badge (diff_data) from buildstate cache ---
        prev = bs_files.get(slug)
        diff_data = None
        if prev is None:
            if not first_build:
                # genuinely new file added after initial build
                diff_data = {"type": "new", "segments": [
                    {"type": "add", "text": l} for l in body.splitlines()]}
        else:
            if prev.get("hash") != cur_hash:
                old = prev.get("body", "")
                segs = _segments(old.splitlines(), body.splitlines())
                has = any(s["type"] in ("add", "del") for s in segs)
                diff_data = {"type": "updated", "segments": segs} if has else {"type": "metadata_only"}

        # history_versions filled in step 7 (single git pass)
        files[slug] = {
            "slug": slug, "path": info["path"], "title": info["title"],
            "type": info["type"], "links": info["links"], "body": body,
            "updated_date": info["updated_date"], "mtime": info["mtime"],
            "diff_data": diff_data,
            "update_severity": classify_update_severity(slug, info["type"], diff_data),
            "history_versions": 0,
        }
        # update buildstate
        bs_files[slug] = {"hash": cur_hash, "body": body}

    # 2) resolve bare links -> slugs
    slug_index = set(files.keys())
    slug_by_name = defaultdict(list)
    for s in slug_index:
        slug_by_name[s.split("/")[-1]].append(s)
    for s in slug_index:
        slug_by_name[s].append(s)
    resolved = {}
    for slug, info in files.items():
        rs = []
        for t in info["links"]:
            if t in slug_index:
                rs.append(t); continue
            name = t.split("/")[-1]
            cands = slug_by_name.get(name, []) + slug_by_name.get(t, [])
            if cands:
                best = min(cands, key=lambda c: {"entity":0,"topic":1,"insight":2,"source":3}.get(files[c].get("type"),99))
                rs.append(best)
            elif t not in ("wikilink", ""):
                rs.append(t)
        resolved[slug] = rs
    for slug in files:
        files[slug]["links"] = resolved[slug]

    # 3) graph
    nodes = [{"id": s, "label": files[s]["title"][:30], "type": files[s]["type"], "linkCount": 0} for s in files]
    link_counts = defaultdict(int); edges = []
    for slug in files:
        for t in resolved[slug]:
            if t in slug_index:
                link_counts[slug] += 1; link_counts[t] += 1
                edges.append({"source": slug, "target": t, "weight": 1})
    for n in nodes: n["linkCount"] = link_counts[n["id"]]

    # 4) tree
    tree = build_tree(files)
    # 5) update records + inbox
    update_records = parse_update_records(VAULT, files)
    inbox_data = {"items": [], "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "total": 0, "groups": {}}

    # 6) write slim bundle (NO content, NO history)
    slim = {
        "files": {s: {k: v for k, v in files[s].items() if k not in ("body",)} for s in files},
        "tree": tree, "graph": {"nodes": nodes, "edges": edges},
        "update_records": update_records, "inbox": inbox_data,
        "stats": {"totalFiles": len(files), "totalEdges": len(edges),
                  "orphans": len([n for n in nodes if n["linkCount"] == 0])},
    }
    # strip body key already excluded; ensure no 'content'/'history' leak
    (OUTPUT / "wiki-bundle.json").write_text(json.dumps(slim, ensure_ascii=False), encoding="utf-8")

    # 7) content bundle (content + history) — single git pass per file
    content_bundle = {}
    for s, info in files.items():
        rel = info["path"]
        body = info["body"]
        log = git_history(VAULT, rel)
        hist = []
        for i, (sha, date, msg) in enumerate(log[:MAX_HISTORY]):
            old = git_show(VAULT, rel, sha)
            segs = _segments(old.splitlines(), body.splitlines())
            # newest version (i==0) equals current content -> omit to avoid duplication;
            # viewer falls back to live content when history[].content is empty.
            content_val = "" if i == 0 else old
            hist.append({"version": len(log)-i, "sha": sha, "date": date, "msg": msg,
                         "content": content_val, "segments": segs})
        files[s]["history_versions"] = len(log)
        content_bundle[s] = {"content": body, "history": hist}
    (OUTPUT / "wiki-content.json").write_text(json.dumps(content_bundle, ensure_ascii=False), encoding="utf-8")

    # 8) assemble static site (copy viewer + inject BUILD_VERSION)
    build_version = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    import shutil
    for item in ["app.js", "style.css"]:
        shutil.copy2(ROOT / "viewer" / item, OUTPUT / item)
    vdir = OUTPUT / "vendor"; vdir.mkdir(exist_ok=True)
    for vf in (ROOT / "viewer" / "vendor").glob("*"):
        shutil.copy2(vf, vdir / vf.name)
    idx = (ROOT / "viewer" / "index.html").read_text(encoding="utf-8")
    idx = idx.replace("__BUILD_VERSION__", build_version)
    (OUTPUT / "index.html").write_text(idx, encoding="utf-8")

    # 9) persist buildstate
    save_buildstate({"files": bs_files})

    print(f"Bundled {len(files)} files, {len(edges)} edges, {slim['stats']['orphans']} orphans")
    print(f"git history: {sum(1 for s in files if files[s]['history_versions']>0)} files versioned")
    print(f"badges: new={sum(1 for s in files if files[s]['diff_data'] and files[s]['diff_data']['type']=='new')} "
          f"updated={sum(1 for s in files if files[s]['diff_data'] and files[s]['diff_data']['type']=='updated')}")
    print(f"wiki-bundle.json: {(OUTPUT/'wiki-bundle.json').stat().st_size//1024} KB")
    print(f"wiki-content.json: {(OUTPUT/'wiki-content.json').stat().st_size//1024} KB")
    print(f"done in {time.time()-t0:.1f}s")

# ----------------------------------------------------------------------------
# tree + update records (reused)
# ----------------------------------------------------------------------------
def build_tree(files):
    tree = {"name": "wiki", "type": "folder", "children": [], "slug": ""}
    for slug, info in sorted(files.items()):
        parts = slug.split("/")
        current = tree
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                current["children"].append({
                    "name": part, "type": info["type"], "slug": slug,
                    "title": info["title"],
                    "is_updated": info.get("diff_data") is not None,
                    "update_severity": info.get("update_severity"),
                    "history_versions": info.get("history_versions", 0),
                })
            else:
                found = False
                for child in current["children"]:
                    if child.get("type") == "folder" and child["name"] == part:
                        current = child; found = True; break
                if not found:
                    nf = {"name": part, "type": "folder", "children": [], "slug": ""}
                    current["children"].append(nf); current = nf
    _folder_order = {"entities":30,"sources":99,"Interesting_findings":20,"topics":0,"overview":-10}
    _folder_emoji = {"02_投资":"💰","03_旅游":"✈️","04_个人":"👤","01_使用说明":"📖"}
    def mark_hubs(node):
        if "children" in node:
            fn = node.get("name","")
            for child in node["children"]:
                if child.get("type") != "folder":
                    cn = child.get("name","").rstrip(".md")
                    if cn == fn: child["is_hub"] = True
                    if cn in _folder_emoji: child["emoji"] = _folder_emoji[cn]
                mark_hubs(child)
            if fn in _folder_emoji: node["emoji"] = _folder_emoji[fn]
    def sort_tree(node):
        if "children" in node:
            node["children"].sort(key=lambda x: (
                _folder_order.get(x.get("name",""),5),
                0 if x.get("is_hub") else (1 if x.get("type")!="folder" else 2),
                _natural_sort_key(x.get("name",""))))
            for child in node["children"]: sort_tree(child)
    mark_hubs(tree); sort_tree(tree)
    return tree

def parse_update_records(vault, files):
    udir = vault / "更新记录"
    if not udir.exists(): return []
    records = []
    for md_file in sorted(udir.glob("*.md"), key=_natural_sort_key):
        slug = str(md_file.relative_to(vault)).replace(".md", "")
        content = md_file.read_text(encoding="utf-8", errors="replace")
        body = content
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3: body = parts[2]
        title = slug.split("/")[-1]
        for line in body.split("\n"):
            line = line.strip()
            if line.startswith("# ") and not line.startswith("## "):
                title = line[2:].strip(); break
        created = None; importance = "normal"; update_type = "日常更新"
        for line in content.split("\n"):
            line = line.strip()
            m = re.match(r'^created:\s*(\S+)', line)
            if m: created = m.group(1)
            m = re.match(r'^importance:\s*(\S+)', line)
            if m: importance = m.group(1)
            m = re.match(r'^更新类型:\s*(.+)$', line)
            if m: update_type = m.group(1).strip()
        mustread = {}
        in_must = False
        for line in body.split("\n"):
            s = line.strip()
            if s.startswith("## ") and not s.startswith("###"):
                in_must = "必看清单" in s; continue
            if not in_must: continue
            m = re.match(r'^- \[[⭐\s|]*?(\d+)[^\]]*\]\s*\[\[([^\]]+)\]\]', s)
            if m:
                sc = int(m.group(1)); pg = m.group(2).strip()
                resolved = pg
                if pg not in files:
                    for fs in files:
                        if fs.split("/")[-1] == pg: resolved = fs; break
                mustread[resolved] = sc
        CAT_DEFAULT = {"new":3,"updated":2,"viewpoint":4}
        affected = []; section_cat = None; seen = {}
        for line in body.split("\n"):
            s = line.strip()
            if s.startswith("## ") and not s.startswith("###"):
                if s.startswith("## 新增页面"): section_cat = "new"
                elif s.startswith("## 更新页面"): section_cat = "updated"
                elif s.startswith("## 观点变化"): section_cat = "viewpoint"
                else: section_cat = None
                continue
            if section_cat is None: continue
            m = re.match(r'^- \[\[([^\]]+)\]\]?\s*—?\s*(.*)', s)
            if m:
                page_slug = m.group(1).strip(); desc = m.group(2).strip()
                resolved = page_slug
                if page_slug not in files:
                    for fs in files:
                        if fs.split("/")[-1] == page_slug: resolved = fs; break
                lvl = mustread.get(resolved, CAT_DEFAULT.get(section_cat, 2))
                if resolved in seen:
                    idx = seen[resolved]
                    if mustread.get(resolved, 0) > affected[idx].get("level", 0):
                        affected[idx]["level"] = lvl
                    continue
                seen[resolved] = len(affected)
                affected.append({"slug": resolved, "level": lvl, "importance": "none",
                                 "description": desc, "category": section_cat})
        records.append({"slug": slug, "title": title, "created": created,
                        "importance": importance, "update_type": update_type,
                        "affected_pages": affected, "content": body.strip()})
    return records

if __name__ == "__main__":
    main()
