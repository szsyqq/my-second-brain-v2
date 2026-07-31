#!/usr/bin/env python3
"""Build 知识库.html from 知识库_template.html.

- Inlines marked.min.js, vis.min.js, vis.min.css (vendored locally) so it works
  offline (CloudStudio deploy has no external CDN access).
- wiki-bundle.json is NOT inlined; it's served as a separate file and loaded
  via fetch() for async loading (avoids blocking the main thread).
- Copies wiki-bundle.json to deploy-wiki/ alongside 知识库.html.
"""
import os
import re
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "知识库_template.html"
BUNDLE = ROOT / "wiki-bundle.json"
OUT = ROOT / "知识库.html"
DEPLOY = ROOT / "deploy-wiki"
VENDOR = ROOT / "scripts" / "vendor"
VERSION_FILE = ROOT / "VERSION"

# Read version from VERSION file (fallback to "0.0.0" if missing)
VERSION = VERSION_FILE.read_text(encoding="utf-8").strip() if VERSION_FILE.exists() else "0.0.0"
print(f"Building v{VERSION} (from VERSION file)...")

# --- System Monitor version data ---
# Baseline skill versions (override by any `version:` in skill SKILL.md frontmatter).
SKILL_VERSIONS = {"gx": "3.0", "sl": "1.0"}

def _parse_frontmatter_version(path):
    """Extract a `version: X.Y[.Z]` field from a markdown file's YAML frontmatter."""
    try:
        txt = Path(path).read_text(encoding="utf-8")
    except Exception:
        return None
    if not txt.startswith("---"):
        return None
    end = txt.find("\n---", 3)
    if end == -1:
        return None
    fm = txt[3:end]
    m = re.search(r"^version:\s*([0-9]+\.[0-9]+(?:\.[0-9]+)?)\s*$", fm, re.M)
    return m.group(1) if m else None

# Schema module versions: parse "版本 X.Y" from each .wiki-schema/modules/*.md
schema_versions = {}
schema_files = {}  # key -> real filename (handles leading dashes like --template.md)
mod_dir = ROOT / ".wiki-schema" / "modules"
if mod_dir.exists():
    for md in mod_dir.glob("*.md"):
        m = re.search(r"版本\s*([0-9]+\.[0-9]+)", md.read_text(encoding="utf-8"))
        if m:
            key = md.stem.lstrip("-")
            schema_versions[key] = m.group(1)
            schema_files[key] = md.name

# Skill versions: baseline dict, then override with frontmatter `version:` if present
skill_versions = dict(SKILL_VERSIONS)
skills_root = ROOT.parent / ".workbuddy" / "skills"
if skills_root.exists():
    for d in skills_root.iterdir():
        if d.is_dir():
            v = _parse_frontmatter_version(d / "SKILL.md")
            if v:
                skill_versions[d.name] = v

SYS_VERSIONS = {
    "page": VERSION,
    "schema": schema_versions,
    "skills": skill_versions,
}
print(f"  sys-mon: page={VERSION} schema={len(schema_versions)} skills={len(skill_versions)}")

# --- System Monitor workflow links (clickable version rows open the workflow source) ---
from urllib.parse import quote as _quote
_HOME = os.path.expanduser("~")
# Bundle workflow source files into _sys/ so links resolve both locally (file://)
# and online (CloudStudio static server). Relative links keep both working.
_SYS = ROOT / "_sys"
def _bundle_src(rel, src):
    dst = _SYS / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.exists():
        shutil.copy2(src, dst)
        return True
    return False
SYS_WORKFLOW_LINKS = {"page": "", "schema": {}, "skills": {}}
# page -> 应用更新记录.md
if _bundle_src("应用更新记录.md", ROOT / "应用更新记录.md"):
    SYS_WORKFLOW_LINKS["page"] = "./_sys/应用更新记录.md"
# schema modules
for k in schema_versions:
    fname = schema_files.get(k, k + ".md")
    if _bundle_src("schema/" + k + ".md", ROOT / ".wiki-schema" / "modules" / fname):
        SYS_WORKFLOW_LINKS["schema"][k] = "./_sys/schema/" + k + ".md"
# skills (user-level ~/.workbuddy/skills)
_skills_dir = Path(_HOME) / ".workbuddy" / "skills"
for k in skill_versions:
    if _bundle_src("skills/" + k + ".md", _skills_dir / k / "SKILL.md"):
        SYS_WORKFLOW_LINKS["skills"][k] = "./_sys/skills/" + k + ".md"
print(f"  sys-mon links: page={'set' if SYS_WORKFLOW_LINKS['page'] else 'MISSING'} schema={len(SYS_WORKFLOW_LINKS['schema'])} skills={len(SYS_WORKFLOW_LINKS['skills'])}")

# Embed workflow markdown content so it renders in-page (no download; works offline+online)
def _clean_md(s):
    s = s.strip()
    if s.startswith("---"):
        idx = s.find("\n---", 3)
        if idx != -1:
            s = s[idx+4:].lstrip("\n")
    return s
SYS_WORKFLOW_CONTENT = {"page": "", "schema": {}, "skills": {}}
def _read_src(rel):
    p = _SYS / rel
    return _clean_md(p.read_text(encoding="utf-8")) if p.exists() else ""
SYS_WORKFLOW_CONTENT["page"] = _read_src("应用更新记录.md")
for k in schema_versions:
    SYS_WORKFLOW_CONTENT["schema"][k] = _read_src("schema/" + k + ".md")
for k in skill_versions:
    SYS_WORKFLOW_CONTENT["skills"][k] = _read_src("skills/" + k + ".md")

# Parse "最近更新" footnotes from the update-record overviews
import datetime as _dt
_TODAY = _dt.date.today()
def _rel(date_str):
    m = re.search(r"(\d{4}-\d{2}-\d{2})", date_str or "")
    if not m: return ""
    try: d = _dt.date.fromisoformat(m.group(1))
    except ValueError: return ""
    diff = (_TODAY - d).days
    return "今天" if diff == 0 else ("昨天" if diff == 1 else ("前天" if diff == 2 else ""))
def _clean_date(raw):
    m = re.search(r"(\d{4}-\d{2}-\d{2})", raw or "")
    return m.group(1) if m else (raw or "").strip().lstrip("~").strip()
def _upd_schema():
    out = {}
    p = ROOT / "Schema更新记录.md"
    if not p.exists(): return out
    for mm in re.finditer(r"\|\s*`modules/([\w-]+)\.md`\s*\|\s*[^|]*?\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|", p.read_text(encoding="utf-8")):
        key = mm.group(1).lstrip("-")
        out[key] = {"date": _clean_date(mm.group(2)), "rel": _rel(mm.group(2)), "note": mm.group(3).strip()}
    return out
def _upd_skills():
    out = {}
    p = ROOT / "Skills更新记录.md"
    if not p.exists(): return out
    for mm in re.finditer(r"\|\s*`/?([\w-]+)`（[^|]*）\s*\|\s*[^|]*?\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|", p.read_text(encoding="utf-8")):
        out[mm.group(1)] = {"date": _clean_date(mm.group(2)), "rel": _rel(mm.group(2)), "note": mm.group(3).strip()}
    return out
_page_upd = None
_pp = ROOT / "应用更新记录.md"
if _pp.exists():
    _m = re.search(r"\|\s*(v[\d.]+)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*[^|]*?\s*\|\s*([^|]*?)\s*\|", _pp.read_text(encoding="utf-8"))
    if _m:
        _page_upd = {"date": _m.group(2), "rel": _rel(_m.group(2)), "note": _m.group(3).strip()}
SYS_UPDATES = {"page": _page_upd, "schema": _upd_schema(), "skills": _upd_skills()}
print(f"  sys-mon updates: page={'set' if _page_upd else 'none'} schema={len(SYS_UPDATES['schema'])} skills={len(SYS_UPDATES['skills'])}")

marked_js = (VENDOR / "marked.min.js").read_text(encoding="utf-8")
vis_js = (VENDOR / "vis.min.js").read_text(encoding="utf-8")
vis_css = (VENDOR / "vis.min.css").read_text(encoding="utf-8")
purify_js = (VENDOR / "purify.min.js").read_text(encoding="utf-8")
# WORKAROUND: CloudStudio deploy injector does naive string replacement —
# it matches `<head></head>` in the ENTIRE file (including inside <script> tags).
# Purify's `ln()` (createDOM for XHTML) has this exact literal in a JS string:
#   '<html ...><head></head><body>'+e+"</body></html>"
# The deploy injector corrupts it by injecting beacon code inside the JS string.
# Escaping `<` as `\x3C` keeps the deploy injector from matching while preserving
# the JS runtime behavior (hex escape decodes to `<`).
purify_js = purify_js.replace('<head></head>', '<head>\\x3C/head>')
if '<head></head>' in purify_js:
    raise SystemExit("BUILD ABORTED: purify_js still contains <head></head> after escape — CloudStudio deploy would corrupt it.")

tpl = TEMPLATE.read_text(encoding="utf-8")
tpl = tpl.replace("MARKED_PLACEHOLDER", marked_js)
tpl = tpl.replace("VIS_CSS_PLACEHOLDER", vis_css)
tpl = tpl.replace("VIS_JS_PLACEHOLDER", vis_js)
tpl = tpl.replace("PURIFY_PLACEHOLDER", purify_js)
tpl = tpl.replace("WIKI_BUNDLE_PLACEHOLDER", "")  # loaded via fetch
tpl = tpl.replace("VERSION_PLACEHOLDER", VERSION)
tpl = tpl.replace("SYS_VERSIONS_PLACEHOLDER", json.dumps(SYS_VERSIONS, ensure_ascii=False))
tpl = tpl.replace("SYS_WORKFLOW_LINKS_PLACEHOLDER", json.dumps(SYS_WORKFLOW_LINKS, ensure_ascii=False))
tpl = tpl.replace("SYS_WORKFLOW_CONTENT_PLACEHOLDER", json.dumps(SYS_WORKFLOW_CONTENT, ensure_ascii=False).replace("</", "<\\/"))
tpl = tpl.replace("SYS_UPDATES_PLACEHOLDER", json.dumps(SYS_UPDATES, ensure_ascii=False))

# --- Regression guard: keep the security hardening intact ---
# DOMPurify/marked/vis are inlined as libraries and must stay inside
# <script>/<style>. If a placeholder is left unreplaced or moved into the
# visible body, the minified source would render as visible text. Abort the
# build so this class of bug can never ship silently.
if any(p in tpl for p in ("PURIFY_PLACEHOLDER", "MARKED_PLACEHOLDER", "VIS_JS_PLACEHOLDER", "SYS_VERSIONS_PLACEHOLDER", "SYS_WORKFLOW_LINKS_PLACEHOLDER", "SYS_WORKFLOW_CONTENT_PLACEHOLDER", "SYS_UPDATES_PLACEHOLDER")):
    raise SystemExit("BUILD ABORTED: a vendor placeholder was not replaced in 知识库_template.html.")
_visible = re.sub(r"<script[\s\S]*?</script>", " ", tpl, flags=re.I)
_visible = re.sub(r"<style[\s\S]*?</style>", " ", _visible, flags=re.I)
if "parseFromString" in _visible:
    raise SystemExit("BUILD ABORTED: DOMPurify source leaked into visible area — check PURIFY_PLACEHOLDER placement in 知识库_template.html.")

OUT.write_text(tpl, encoding="utf-8")
print(f"Built {OUT}  ({OUT.stat().st_size/1024/1024:.2f} MB)")
print(f"  marked:{len(marked_js)//1024}KB  vis.js:{len(vis_js)//1024}KB  vis.css:{len(vis_css)//1024}KB")
print(f"  bundle: served separately (wiki-bundle.json, {BUNDLE.stat().st_size/1024/1024:.2f} MB)")

# Copy bundle JSON to deploy directory
DEPLOY.mkdir(exist_ok=True)

# --- Strip content and history for fast initial load ---
# Full bundle (with content/history) goes to deploy as wiki-content.json
# Slim bundle (metadata only) goes as wiki-bundle.json for instant loading
bundle_data = json.loads(BUNDLE.read_text(encoding="utf-8"))
content_data = {}

for slug, info in bundle_data["files"].items():
    # Extract content and history into separate payload
    has_content = info.pop("content", None)
    has_history = info.pop("history", None)
    if has_content or has_history:
        entry = {}
        if has_content:
            entry["content"] = has_content
        if has_history:
            entry["history"] = has_history
        content_data[slug] = entry

# Write slim bundle (metadata only)
slim_json = json.dumps(bundle_data, ensure_ascii=False)
(DEPLOY / "wiki-bundle.json").write_text(slim_json, encoding="utf-8")
print(f"  slim bundle: {len(slim_json)/1024/1024:.2f} MB (metadata only)")

# Write content payload (loaded on demand)
if content_data:
    content_json = json.dumps(content_data, ensure_ascii=False)
    (DEPLOY / "wiki-content.json").write_text(content_json, encoding="utf-8")
    print(f"  content bundle: {len(content_json)/1024/1024:.2f} MB ({len(content_data)} files with content/history)")

shutil.copy2(OUT, DEPLOY / "index.html")
print(f"Copied files to {DEPLOY}/")
# Copy bundled workflow sources so online clicks resolve
if _SYS.exists():
    shutil.copytree(_SYS, DEPLOY / "_sys", dirs_exist_ok=True)
    print(f"Copied _sys/ workflow sources to {DEPLOY}/")
