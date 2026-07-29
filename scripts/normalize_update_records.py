#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
normalize_update_records.py
批量归一化 vault/更新记录/*.md，使其符合 _workflow/更新历史编写规范.md。
只改格式（frontmatter / 标题 / 灰色小字 / 章节完整性 / 必看清单条目），
不改动任何语义内容。覆盖写回原文件（vault 在 git 下，可用 git diff 回滚）。
"""
import re, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
UDIR = ROOT / "vault" / "更新记录"

IMP_MAP = {  # 旧值 -> 1-5 整数串
    "normal": "2", "low": "1", "medium": "3", "high": "4",
    "1": "1", "2": "2", "3": "3", "4": "4", "5": "5",
}
TYPE_MAP = {  # 旧更新类型 -> 四枚举
    "站点优化": "站点优化",
    "批量消化": "内容消化", "补消化": "内容消化", "回溯补更": "内容消化",
    "重大更新": "重大重构", "重大重构": "重大重构",
    "日常更新": "例行维护", "例行维护": "例行维护", "内容消化": "内容消化",
}
LABEL = {"5": "必看", "4": "重要", "3": "有价值", "2": "常规", "1": "次要"}

REQUIRED_SECTIONS = ["## 📌 必看清单", "## 新增页面", "## 更新页面", "## 观点变化"]


def parse_front(content):
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    fm_text, body = parts[1], parts[2]
    fm = {}
    for line in fm_text.splitlines():
        m = re.match(r'^([A-Za-z_\u4e00-\u9fff]+):\s*(.*)$', line)
        if m:
            fm[m.group(1)] = m.group(2).strip()
    return fm, body


def get_h1(body):
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("# ") and not s.startswith("## "):
            return s[2:].strip()
    return ""


def num_date(fname, h1):
    m = re.search(r'第\s*(\d+)\s*次', fname + " " + h1)
    num = m.group(1) if m else "?"
    d = re.search(r'(\d{4}-\d{2}-\d{2})', fname + " " + h1)
    date = d.group(1) if d else ""
    return num, date


def strip_md(s):
    return s.replace("**", "").replace("__", "").replace("`", "").strip()


def one_liner(h1, body):
    # 剥离 "第N次更新" 与日期（容忍「日期 第N次」与「第N次 日期」两种顺序）
    s = h1
    s = re.sub(r'\d{4}-\d{2}-\d{2}\s*第\s*\d+\s*次更新', '', s)
    s = re.sub(r'第\s*\d+\s*次更新\s*\d{4}-\d{2}-\d{2}', '', s)
    s = re.sub(r'第\s*\d+\s*次更新', '', s)
    s = re.sub(r'\d{4}-\d{2}-\d{2}', '', s)
    s = s.replace("|", " ").replace("：", ":").strip()
    s = re.sub(r'\s+', ' ', s).strip(' :：')
    if s and s not in ("无", "无。"):
        # 清理后若仍含 markdown 或数字列表残留，视为脏，回退正文
        if "**" not in s and not s.startswith("1.") and not s.startswith("- "):
            return strip_md(s)[:40]
    # 回退：正文第一个普通段落（跳过标题/引用/表格/列表/数字列表）
    for line in body.splitlines():
        t = line.strip()
        if not t:
            continue
        if t.startswith("#") or t.startswith(">") or t.startswith("---") or t.startswith("|"):
            continue
        if t.startswith("- ") or t.startswith("* ") or re.match(r'^\d+\.\s', t):
            continue
        return strip_md(t)[:40]
    return ""


def normalize_mustread(body):
    # 标准化必看清单条目：- [⭐⭐⭐ 4 · 重要] [[slug]] — desc  ->  - [4 · 重要] [[slug]] — desc
    def repl(m):
        pre, score, slug, sep, desc = m.groups()
        lab = LABEL.get(score, "常规")
        return f"{pre}[{score} · {lab}] {slug}{sep}{desc}".rstrip()
    pat = re.compile(r'^(\s*-\s*)\[[^\]]*?(\d+)[^\]]*\]\s*(\[\[[^\]]+\]\])(\s*[—-]?\s*)(.*)$')
    out = []
    in_must = False
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("## ") and not s.startswith("###"):
            in_must = "必看清单" in s
            out.append(line)
            continue
        if in_must:
            mm = pat.match(line)
            if mm:
                out.append(repl(mm))
                continue
        out.append(line)
    return "\n".join(out)


def ensure_sections(body):
    lines = body.splitlines()
    present = {sec: any(l.strip().startswith(sec) for l in lines) for sec in REQUIRED_SECTIONS}
    if all(present.values()):
        return body
    # 末尾补齐缺失章节
    tail = []
    for sec in REQUIRED_SECTIONS:
        if not present[sec]:
            tail.append(sec)
            tail.append("无")
            tail.append("")
    return body.rstrip() + "\n\n" + "\n".join(tail) + "\n"


def main():
    files = sorted(UDIR.glob("*.md"), key=lambda p: p.name)
    print(f"待处理 {len(files)} 篇")
    for fp in files:
        raw = fp.read_text(encoding="utf-8")
        fm, body = parse_front(raw)
        body = body.lstrip("\n")
        h1 = get_h1(body)
        num, date = num_date(fp.name, h1)
        # 规范化 frontmatter
        new_created = fm.get("created", date) or date
        old_imp = (fm.get("importance") or "2")
        new_imp = IMP_MAP.get(old_imp.strip(), "2")
        old_type = (fm.get("更新类型") or "例行维护").strip()
        new_type = TYPE_MAP.get(old_type, "例行维护")
        # 去 body 首部旧 h1
        body_no_h1 = re.sub(r'^# .*\n?', '', body, count=1)
        # 去掉所有已存在的顶部灰色小字引用（避免重复/残留），后面统一加
        body_no_h1 = re.sub(r'^\s*>\s*重点[：:].*\n', '', body_no_h1, flags=re.M)
        # 彻底清除所有残留的旧更新标题行（防止历史累积污染）
        body_no_h1 = re.sub(r'^\s*#\s*第\d+次更新[^\n]*\n', '', body_no_h1, flags=re.M)
        body_no_h1 = body_no_h1.lstrip("\n")
        # 标准化必看清单 + 补章节
        body2 = normalize_mustread(body_no_h1)
        body2 = ensure_sections(body2)
        # 组装
        oneliner = one_liner(h1, body2)
        title = f"# 第{num}次更新 | {date}" + (f" | {oneliner}" if oneliner else "")
        grey = f"> 重点：{oneliner}" if oneliner else "> 重点：（详见下方受影响页面）"
        new_content = (
            "---\n"
            "tags: [更新记录]\n"
            f"created: {new_created}\n"
            f"importance: {new_imp}\n"
            f"更新类型: {new_type}\n"
            "---\n\n"
            f"{title}\n\n"
            f"{grey}\n\n"
            f"{body2.strip()}\n"
        )
        fp.write_text(new_content, encoding="utf-8")
        print(f"  ✓ {fp.name}  ->  imp={new_imp} type={new_type} title='{title[:50]}'")
    print("完成。")


if __name__ == "__main__":
    main()
