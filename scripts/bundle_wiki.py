#!/usr/bin/env python3
"""Bundle entire wiki into a single JSON for client-side Obsidian-like reading.

Output: wiki-bundle.json with:
- files: { "slug": {"path":..., "title":..., "content":..., "type":..., "links":[...]} }
- tree: nested folder structure for sidebar
- graph: nodes + edges for knowledge graph
"""
import json
import re
import time
import difflib
import datetime
from pathlib import Path
from collections import defaultdict

WIKI_DIR = Path("wiki")
SNAPSHOT_DIR = Path("_snapshots")
HISTORY_DIR = WIKI_DIR / ".history"
MAX_HISTORY = 3
SNAPSHOT_DIR.mkdir(exist_ok=True)
HISTORY_DIR.mkdir(exist_ok=True)
LINK_RE = re.compile(r'\[\[([^\]|#]+)(?:[|#][^\]]+)?\]\]')

files = {}
link_graph = defaultdict(int)
node_ids = set()

def archive_version(slug, old_content):
    """Archive old content to .history/, keeping max MAX_HISTORY versions (FIFO)."""
    base = HISTORY_DIR / slug.replace("/", "__")
    # Shift: v0→delete, v1→v0, v2→v1, old→v2
    for i in range(MAX_HISTORY - 1, 0, -1):
        src = Path(f"{base}.v{i}")
        dst = Path(f"{base}.v{i-1}")
        if src.exists():
            if dst.exists():
                if i == 1:
                    dst.unlink()  # v0 gets deleted (oldest)
                else:
                    src.rename(dst)
            else:
                src.rename(dst)
    # Write old content as newest history entry
    Path(f"{base}.v{MAX_HISTORY - 1}").write_text(old_content, encoding="utf-8")

def count_history_versions(slug):
    """Count how many history versions exist for a slug (0-MAX_HISTORY)."""
    base = HISTORY_DIR / slug.replace("/", "__")
    count = 0
    for i in range(MAX_HISTORY):
        if Path(f"{base}.v{i}").exists():
            count += 1
    return count

def load_history(slug):
    """Load archived history versions for a slug, each with a precomputed
    line diff (segments) against the CURRENT content. The browser is static,
    so old versions must be embedded in the bundle to be viewable/diffable."""
    base = HISTORY_DIR / slug.replace("/", "__")
    cur = files[slug]["content"] if slug in files else None
    result = []
    for i in range(MAX_HISTORY):
        p = Path(f"{base}.v{i}")
        if not p.exists():
            continue
        old = p.read_text(encoding="utf-8", errors="replace")
        segments = []
        if cur is not None:
            diff_lines = list(difflib.ndiff(old.splitlines(), cur.splitlines()))
            for dl in diff_lines:
                if dl.startswith("+ "):
                    segments.append({"type": "add", "text": dl[2:]})
                elif dl.startswith("- "):
                    segments.append({"type": "del", "text": dl[2:]})
                elif dl.startswith("? "):
                    continue
                else:
                    segments.append({"type": "equal", "text": dl[2:]})
        result.append({"version": i, "content": old, "segments": segments})
    return result

import re
# Custom sort key: zero-pad 第N次 so 第10次 sorts after 第9次
def _natural_sort_key(path):
    name = str(path)
    name = re.sub(r'第(\d+)次', lambda m: f'第{int(m.group(1)):03d}次', name)
    return name

for md_file in sorted(WIKI_DIR.rglob("*.md"), key=_natural_sort_key):
    slug = str(md_file.relative_to(WIKI_DIR)).replace(".md", "")
    if not slug or slug in node_ids:
        continue
    node_ids.add(slug)

    content = md_file.read_text(encoding="utf-8", errors="replace")

    # Determine type
    if slug.startswith("entities/"): page_type = "entity"
    elif slug.startswith("sources/"): page_type = "source"
    elif slug.startswith("topics/"): page_type = "topic"
    elif slug.startswith("Interesting_findings/"): page_type = "insight"
    elif slug.startswith("comparisons/"): page_type = "comparison"
    elif slug.startswith("synthesis/"): page_type = "synthesis"
    elif slug.endswith("overview"): page_type = "overview"
    else: page_type = "other"

    # Extract title
    title = slug.split("/")[-1]
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("# ") and not line.startswith("## "):
            title = line[2:].strip()
            break

    # Extract [[links]]
    links = []
    for match in LINK_RE.finditer(content):
        target = match.group(1).strip()
        links.append(target)

    # Extract frontmatter dates
    updated_date = None
    m = re.search(r'^updated:\s*(\S+)', content, re.M)
    if m:
        try:
            updated_date = datetime.date.fromisoformat(m.group(1).strip())
        except Exception:
            updated_date = None
    created_date_str = None
    m_c = re.search(r'^created:\s*(\S+)', content, re.M)
    if m_c:
        created_date_str = m_c.group(1).strip()

    # Skip frontmatter for display
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            body = parts[2]

    # --- Diff: compare with snapshot (deferred write) ---
    today_str = datetime.date.today().isoformat()
    cur_body = body.strip()
    snapshot_filename = slug.replace("/", "__") + ".txt"
    snapshot_path = SNAPSHOT_DIR / snapshot_filename
    prev_body = None
    if snapshot_path.exists():
        prev_body = snapshot_path.read_text(encoding="utf-8", errors="replace").strip()

    diff_data = None
    snapshot_to_write = None  # collect for batch write after loop

    if prev_body is not None and prev_body != cur_body:
        # Content changed since last snapshot → real update
        is_updated = True
        diff_lines = list(difflib.ndiff(prev_body.splitlines(), cur_body.splitlines()))
        segments = []
        for dl in diff_lines:
            if dl.startswith("+ "):
                segments.append({"type": "add", "text": dl[2:]})
            elif dl.startswith("- "):
                segments.append({"type": "del", "text": dl[2:]})
            elif dl.startswith("? "):
                continue
            else:
                segments.append({"type": "equal", "text": dl[2:]})
        has_changes = any(s["type"] in ("add", "del") for s in segments)
        if has_changes:
            diff_data = {"type": "updated", "segments": segments}
        else:
            diff_data = {"type": "metadata_only"}
        # Queue snapshot write after loop (new baseline)
        snapshot_to_write = body
        # Archive previous content to .history/ for version history
        archive_version(slug, prev_body)
    elif created_date_str == today_str and prev_body is None:
        # Brand new file created today, no baseline → all content is new
        is_updated = True
        diff_data = {"type": "new", "segments": [
            {"type": "add", "text": line} for line in cur_body.splitlines()
        ]}
        snapshot_to_write = body
    elif prev_body is None:
        # No previous snapshot → first time, create baseline without marking as new
        is_updated = True
        # Do NOT set diff_data — let the user see the page normally on first view
        # Queue snapshot write after loop
        snapshot_to_write = body

    files[slug] = {
        "slug": slug,
        "path": str(md_file.relative_to(WIKI_DIR)),
        "title": title,
        "type": page_type,
        "content": body.strip(),
        "links": links,
        "updated_date": updated_date.isoformat() if updated_date else None,
        "mtime": md_file.stat().st_mtime,
        "diff_data": diff_data,
        "snapshot_to_write": snapshot_to_write,
        "update_severity": None,  # will be classified after all files loaded
        "history_versions": count_history_versions(slug)
    }

# --- Also include root-level special pages ---
# index.md           → 知识库索引（内容导航）
# 应用更新记录.md → 应用（主版本）本身的更新历史（区别于文件内容更新）
# Skills更新记录.md → 技能版本的演进（与 Schema更新记录.md 平级，均为根级特殊页）
# Schema更新记录.md → 结构规范的演进
# 更新汇总.md     → 四层更新记录统一入口（应用 / Skills / Schema / Wiki 内容）
for root_file in ["index.md", "应用更新记录.md", "Skills更新记录.md", "Schema更新记录.md", "更新汇总.md"]:
    root_path = Path(root_file)
    if not root_path.exists():
        continue
    slug = root_file.replace(".md", "")  # "index"
    if slug in node_ids:
        continue
    node_ids.add(slug)

    content = root_path.read_text(encoding="utf-8", errors="replace")
    page_type = "other"

    # Extract title
    title = slug
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("# ") and not line.startswith("## "):
            title = line[2:].strip()
            break

    # Extract [[links]]
    links = []
    for match in LINK_RE.finditer(content):
        target = match.group(1).strip()
        links.append(target)

    # Extract frontmatter dates
    updated_date = None
    m = re.search(r'^updated:\s*(\S+)', content, re.M)
    if m:
        try:
            updated_date = datetime.date.fromisoformat(m.group(1).strip())
        except Exception:
            updated_date = None
    created_date_str = None
    m_c = re.search(r'^created:\s*(\S+)', content, re.M)
    if m_c:
        created_date_str = m_c.group(1).strip()

    # Skip frontmatter for display
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            body = parts[2]

    # --- Diff: compare with snapshot ---
    today_str = datetime.date.today().isoformat()
    cur_body = body.strip()
    snapshot_filename = slug.replace("/", "__") + ".txt"
    snapshot_path = SNAPSHOT_DIR / snapshot_filename
    prev_body = None
    if snapshot_path.exists():
        prev_body = snapshot_path.read_text(encoding="utf-8", errors="replace").strip()

    diff_data = None
    snapshot_to_write = None

    if prev_body is not None and prev_body != cur_body:
        is_updated = True
        diff_lines = list(difflib.ndiff(prev_body.splitlines(), cur_body.splitlines()))
        segments = []
        for dl in diff_lines:
            if dl.startswith("+ "):
                segments.append({"type": "add", "text": dl[2:]})
            elif dl.startswith("- "):
                segments.append({"type": "del", "text": dl[2:]})
            elif dl.startswith("? "):
                continue
            else:
                segments.append({"type": "equal", "text": dl[2:]})
        has_changes = any(s["type"] in ("add", "del") for s in segments)
        if has_changes:
            diff_data = {"type": "updated", "segments": segments}
        else:
            diff_data = {"type": "metadata_only"}
        snapshot_to_write = body
    elif created_date_str == today_str and prev_body is None:
        is_updated = True
        diff_data = {"type": "new", "segments": [
            {"type": "add", "text": line} for line in cur_body.splitlines()
        ]}
        snapshot_to_write = body
    elif prev_body is None:
        is_updated = True
        snapshot_to_write = body

    files[slug] = {
        "slug": slug,
        "path": root_file,
        "title": title,
        "type": page_type,
        "content": body.strip(),
        "links": links,
        "updated_date": updated_date.isoformat() if updated_date else None,
        "mtime": root_path.stat().st_mtime,
        "diff_data": diff_data,
        "snapshot_to_write": snapshot_to_write,
        "update_severity": None
    }

# --- Batch write all snapshots AFTER all diffs computed ---
snaps_written = 0
for slug, info in files.items():
    snap_data = info.pop("snapshot_to_write", None)
    if snap_data is None:
        continue
    snap_path = SNAPSHOT_DIR / (slug.replace("/", "__") + ".txt")
    snap_path.write_text(snap_data, encoding="utf-8")
    snaps_written += 1

# --- Attach version history (with precomputed diff vs current) to each file ---
for slug, info in files.items():
    info["history"] = load_history(slug)

# --- Update Severity Classification ---
VIEWPOINT_CHANGE_PATTERNS = [
    "下调至", "上调至", "转向", "转为", "转谨慎", "转积极",
    "由.*转", "由.*变", "从.*调整为", "从.*变",
    "估值锚点.*移动", "估值锚点.*调整",
    "方向变化", "方向反转", "评级.*调整",
    "证伪", "推翻",
]

def classify_update_severity(slug, page_type, dd):
    """Return severity string: None | new | updated | major | viewpoint"""
    if not dd:
        return None
    diff_type = dd.get("type")
    segments = dd.get("segments", [])

    if diff_type == "new":
        return "new"

    if diff_type == "metadata_only":
        return "updated"

    if diff_type == "updated":
        add_lines = [s["text"] for s in segments if s["type"] == "add"]
        del_lines = [s["text"] for s in segments if s["type"] == "del"]
        add_count = len(add_lines)
        del_count = len(del_lines)
        total_lines = len(segments)
        add_ratio = add_count / max(total_lines, 1)

        combined_text = "\n".join(add_lines)
        # Viewpoint change detection (only for investment pages)
        is_investment = slug.startswith("topics/02_投资/")
        for pat in VIEWPOINT_CHANGE_PATTERNS:
            if re.search(pat, combined_text):
                return "viewpoint"

        # Major vs minor: sources/entities shorter → lower threshold
        threshold = 0.06 if page_type == "topic" else 0.12
        if add_ratio > threshold or add_count > 15:
            return "major"
        return "updated"

    return None

# Classify each file's update severity
for slug, info in files.items():
    info["update_severity"] = classify_update_severity(
        slug, info.get("type", "other"), info.get("diff_data")
    )

# --- Resolve bare-name links to actual slugs ---
slug_index = set(files.keys())

# Pre-build: slug → last segment lookup for bare-name resolution
slug_by_name = defaultdict(list)
for s in slug_index:
    slug_by_name[s.split("/")[-1]].append(s)
# Also index by full slug for names like "entities/XXX"
for s in slug_index:
    slug_by_name[s].append(s)

resolved_links = {}
for slug, info in files.items():
    resolved = []
    for target in info["links"]:
        if target in slug_index:
            resolved.append(target)
            continue
        # Try slug_by_name lookup (match last segment of path)
        name = target.split("/")[-1]
        candidates = slug_by_name.get(name, []) + slug_by_name.get(target, [])
        if candidates:
            # Prefer entities, then topics, then sources
            priority = {"entity": 0, "topic": 1, "insight": 2, "source": 3}
            best = min(candidates, key=lambda c: priority.get(files[c]["type"], 99))
            resolved.append(best)
        elif target not in ("wikilink", ""):
            # Keep as-is for unresolved but not nonsense
            resolved.append(target)
    resolved_links[slug] = resolved

# Update files with resolved links
for slug in files:
    files[slug]["links"] = resolved_links[slug]

# Build graph data
nodes = []
edges = []
for slug, info in files.items():
    nodes.append({
        "id": slug,
        "label": info["title"][:30],
        "type": info["type"],
        "linkCount": 0
    })

# Build graph from resolved links
link_counts = defaultdict(int)
edges = []
for slug in files:
    for target in resolved_links[slug]:
        if target in slug_index:
            link_counts[slug] += 1
            link_counts[target] += 1
            edges.append({"source": slug, "target": target, "weight": 1})

for n in nodes:
    n["linkCount"] = link_counts[n["id"]]

# Build file tree
def build_tree():
    tree = {"name": "wiki", "type": "folder", "children": [], "slug": ""}
    for slug, info in sorted(files.items()):
        parts = slug.split("/")
        current = tree
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                # It's a file
                current["children"].append({
                    "name": part,
                    "type": info["type"],
                    "slug": slug,
                    "title": info["title"],
                    "is_updated": info.get("diff_data") is not None,
                    "update_severity": info.get("update_severity"),
                    "history_versions": info.get("history_versions", 0)
                })
            else:
                # Find or create folder
                found = False
                for child in current["children"]:
                    if child.get("type") == "folder" and child["name"] == part:
                        current = child
                        found = True
                        break
                if not found:
                    new_folder = {
                        "name": part,
                        "type": "folder",
                        "children": [],
                        "slug": slug.rsplit("/", 1)[0] if i == len(parts)-1 else ""
                    }
                    current["children"].append(new_folder)
                    current = new_folder

    # Sort: order = topics, Interesting_findings, sources, entities (entities last as backup layer)
    # Within each: hub pages first (⭐), then other files, then folders
    _folder_order = {"entities": 30, "sources": 99, "Interesting_findings": 20, "topics": 0, "overview": -10}
    _folder_emoji = {"02_投资": "💰", "03_旅游": "✈️", "04_个人": "👤", "01_使用说明": "📖"}

    def mark_hubs(node):
        """Detect hub pages: files whose name matches their parent folder name."""
        if "children" in node:
            folder_name = node.get("name", "")
            for child in node["children"]:
                if child.get("type") != "folder":
                    # Check if this file is the hub page for this folder
                    child_name = child.get("name", "").rstrip(".md")
                    if child_name == folder_name:
                        child["is_hub"] = True
                    # Also match common hub patterns like "02_投资" matching folder "02_投资"
                    if child_name in _folder_emoji:
                        child["emoji"] = _folder_emoji[child_name]
                mark_hubs(child)
            # Set folder emoji
            if folder_name in _folder_emoji:
                node["emoji"] = _folder_emoji[folder_name]

    def sort_tree(node):
        if "children" in node:
            node["children"].sort(key=lambda x: (
                _folder_order.get(x.get("name", ""), 5),
                0 if x.get("is_hub") else (1 if x.get("type") != "folder" else 2),
                _natural_sort_key(x.get("name", ""))
            ))
            for child in node["children"]:
                sort_tree(child)

    mark_hubs(tree)
    sort_tree(tree)
    return tree

# --- Parse 更新记录 ---
def parse_update_records():
    """Parse 更新记录/*.md files into structured records with affected pages."""
    update_dir = WIKI_DIR / "更新记录"
    if not update_dir.exists():
        return []
    records = []
    for md_file in sorted(update_dir.glob("*.md"), key=_natural_sort_key):
        slug = str(md_file.relative_to(WIKI_DIR)).replace(".md", "")
        content = md_file.read_text(encoding="utf-8", errors="replace")
        body = content
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                body = parts[2]

        # Extract title (from "# " heading or filename)
        title = slug.split("/")[-1]
        for line in body.split("\n"):
            line = line.strip()
            if line.startswith("# ") and not line.startswith("## "):
                title = line[2:].strip()
                break

        # Extract frontmatter
        created = None
        importance = "normal"
        update_type = "日常更新"
        for line in content.split("\n"):
            line = line.strip()
            m = re.match(r'^created:\s*(\S+)', line)
            if m:
                created = m.group(1)
            m = re.match(r'^importance:\s*(\S+)', line)
            if m:
                importance = m.group(1)
            m = re.match(r'^更新类型:\s*(.+)$', line)
            if m:
                update_type = m.group(1).strip()

        # --- Pass 1: parse the "## 📌 必看清单" section for per-page scores (1-5) ---
        # Format:  - [⭐⭐ | 4] [[slug]] — description
        # The number after "|" is the explicit 1-5 importance level.
        mustread = {}
        in_must = False
        for line in body.split("\n"):
            s = line.strip()
            if s.startswith("## ") and not s.startswith("###"):
                in_must = ("必看清单" in s)
                continue
            if not in_must:
                continue
            m = re.match(r'^- \[[⭐\s|]*?(\d+)[^\]]*\]\s*\[\[([^\]]+)\]\]', s)
            if m:
                sc = int(m.group(1))
                pg = m.group(2).strip()
                resolved = pg
                if pg not in files:
                    for fs in files:
                        if fs.split("/")[-1] == pg:
                            resolved = fs
                            break
                mustread[resolved] = sc

        # --- Pass 2: extract affected pages from 新增/更新/观点变化 sections ---
        # Each page gets a 1-5 "level": the 必看清单 score if present, otherwise a
        # category default so every page carries a visible, distinct level.
        #   new → 3 (有价值) · updated → 2 (常规) · viewpoint → 4 (重要)
        CAT_DEFAULT_LEVEL = {"new": 3, "updated": 2, "viewpoint": 4}
        affected_pages = []
        section_cat = None
        seen_slugs = {}
        for line in body.split("\n"):
            s = line.strip()
            # Only a real H2 (exactly "## ") switches the active section; H3/H4
            # sub-headings (e.g. "### 素材摘要") must NOT reset the category.
            if s.startswith("## ") and not s.startswith("###"):
                if s.startswith("## 新增页面"):
                    section_cat = "new"
                elif s.startswith("## 更新页面"):
                    section_cat = "updated"
                elif s.startswith("## 观点变化"):
                    section_cat = "viewpoint"
                else:
                    section_cat = None
                continue
            if section_cat is None:
                continue
            m = re.match(r'^- \[\[([^\]]+)\]\]?\s*—?\s*(.*)', s)
            if m:
                page_slug = m.group(1).strip()
                desc = m.group(2).strip()
                # Resolve bare slug → full path slug (same logic as frontend resolveSlug)
                resolved_slug = page_slug
                if page_slug not in files:
                    for fs in files:
                        if fs.split("/")[-1] == page_slug:
                            resolved_slug = fs
                            break
                # Level: explicit 必看清单 score wins; else category default
                if resolved_slug in mustread:
                    lvl = mustread[resolved_slug]
                else:
                    lvl = CAT_DEFAULT_LEVEL.get(section_cat, 2)
                # Dedupe: a slug may appear in both 新增/更新 sections of one update.
                # Keep the first occurrence's category, but upgrade level if the
                # later occurrence carries a higher explicit 必看 score.
                if resolved_slug in seen_slugs:
                    idx = seen_slugs[resolved_slug]
                    if mustread.get(resolved_slug, 0) > affected_pages[idx].get("level", 0):
                        affected_pages[idx]["level"] = lvl
                    continue
                seen_slugs[resolved_slug] = len(affected_pages)
                affected_pages.append({
                    "slug": resolved_slug,
                    "level": lvl,
                    "importance": "none",
                    "description": desc,
                    "category": section_cat
                })
        records.append({
            "slug": slug,
            "title": title,
            "created": created,
            "importance": importance,
            "update_type": update_type,
            "affected_pages": affected_pages,
            "content": body.strip()
        })
    return records

# --- Collect raw/inbox pending articles (待处理素材清单) ---
INBOX_ROOT = Path("raw/inbox")
INBOX_SOURCE_LABELS = {
    "wechat": "微信", "pdf": "PDF", "article": "文章", "xiaoetong": "小鹅通",
    "xiaohongshu": "小红书", "zhihu": "知乎", "tweets": "推文", "docs": "文档",
    "notes": "笔记", "images": "图片",
}

def _parse_inbox_frontmatter(text):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).split("\n"):
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip(); v = v.strip()
        if not k:
            continue
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            items = [x.strip().strip('"').strip("'") for x in inner.split(",") if x.strip()]
            fm[k] = items
        else:
            fm[k] = v.strip().strip('"').strip("'")
    return fm

def collect_inbox():
    """Scan raw/inbox/* for pending articles; return {items, generated_at, total, groups}."""
    items = []
    if INBOX_ROOT.exists():
        for sub in sorted(INBOX_ROOT.iterdir()):
            if not sub.is_dir():
                continue
            stype = sub.name
            for md in sorted(sub.glob("*.md")):
                if md.name.startswith("."):
                    continue
                text = md.read_text(encoding="utf-8", errors="replace")
                fm = _parse_inbox_frontmatter(text)
                s_type = fm.get("source_type") or stype
                items.append({
                    "title": fm.get("title") or md.stem,
                    "url": fm.get("url", "") or "",
                    "source_type": s_type,
                    "source_label": INBOX_SOURCE_LABELS.get(s_type, s_type),
                    "saved_at": fm.get("saved_at", "") or "",
                    "summary": fm.get("summary", "") or "",
                    "theme": fm.get("theme", []) or [],
                    "file": str(md),
                })
    groups = {}
    for it in items:
        groups[it["source_type"]] = groups.get(it["source_type"], 0) + 1
    return {
        "items": items,
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": len(items),
        "groups": groups,
    }

# Build output
update_records = parse_update_records()
inbox_data = collect_inbox()

output = {
    "files": files,
    "tree": build_tree(),
    "graph": {"nodes": nodes, "edges": edges},
    "update_records": update_records,
    "inbox": inbox_data,
    "stats": {
        "totalFiles": len(files),
        "totalEdges": len(edges),
        "orphans": len([n for n in nodes if n["linkCount"] == 0])
    }
}

with open("wiki-bundle.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False)

print(f"Bundled: {len(files)} files, {len(edges)} edges, {output['stats']['orphans']} orphans")
print(f"JSON size: {Path('wiki-bundle.json').stat().st_size} bytes")
