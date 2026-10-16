#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量消化 raw/inbox/xiaoetong/*.md → wiki/sources/ 结构化 source 页。

设计：
- 解析 frontmatter（title/source/author/role/date/source_url/feed_id/tags）
- 生成 type:source 页：要点预览 + 全文保留 + 自动 topics 标签
  + 自动关联已知实体/策略页 wikilink + 指向本地存档
- 处理完后把源文件移入 raw/processed/xiaoetong/

用法：
  python3 scripts/ingest_xiaoetong_batch.py [--dry] [--limit N]
  --dry   只统计不写文件
  --limit 仅处理前 N 篇（调试）
"""
import os
import re
import shutil
import sys
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INBOX = os.path.join(ROOT, "raw", "inbox", "xiaoetong")
PROCESSED = os.path.join(ROOT, "raw", "processed", "xiaoetong")
SOURCES = os.path.join(ROOT, "wiki", "sources")
ENTITIES = os.path.join(ROOT, "wiki", "entities")
TOPICS_DIR = os.path.join(ROOT, "wiki", "topics")

os.makedirs(PROCESSED, exist_ok=True)
os.makedirs(SOURCES, exist_ok=True)

# ---------- 可用实体/页面 slug 集合 ----------
existing_entity_slugs = set()
if os.path.isdir(ENTITIES):
    for fn in os.listdir(ENTITIES):
        if fn.endswith(".md"):
            existing_entity_slugs.add(fn[:-3])

def topic_page_exists(rel):
    p = os.path.join(ROOT, "wiki", rel)
    return os.path.exists(p)

# ---------- topics 关键词词典 ----------
TOPIC_KEYWORDS = {
    "A股": ["A股", "沪深", "上证", "创业板", "科创", "中证", "北证"],
    "港股": ["港股", "恒生", "H股"],
    "美股": ["美股", "纳斯达克", "标普", "道指", "美国股市"],
    "红利": ["红利", "股息", "高股息"],
    "AI/科技": ["AI", "人工智能", "算力", "芯片", "半导体", "英伟达", "NVIDIA", "华为", "大模型", "机器人"],
    "黄金": ["黄金"],
    "原油": ["原油", "石油", "油价"],
    "债券/利率": ["债券", "国债", "利率", "收益率", "久期", "信用债", "转债"],
    "楼市": ["楼市", "房地产", "房价", "公积金", "房贷", "土拍", "商品房"],
    "基金": ["公募", "私募", "基金", "ETF", "FOF", "指增"],
    "量化": ["量化", "超额", "指增"],
    "理财/资产配置": ["理财", "资产配置", "财富", "保险", "养老", "储蓄"],
    "宏观/汇率": ["汇率", "人民币", "美元", "美债", "通胀", "CPI", "PPI", "PMI", "社融", "流动性", "货币政策"],
    "消费": ["消费", "白酒", "零售", "免税"],
    "新能源": ["新能源", "光伏", "锂电", "电动车", "储能"],
    "医药": ["医药", "创新药", "医保", "CXO"],
    "金融": ["银行", "券商", "保险股", "非银"],
    "周期": ["周期", "有色", "煤炭", "钢铁", "化工"],
    "海外": ["日本", "欧洲", "印度", "越南", "东南亚", "美联储", "非农"],
}

# ---------- 可关联概念 → 实体/页面 slug ----------
# 仅当目标 slug 真实存在时才链接
LINKABLE = [
    ("黄金", "黄金"),
    ("红利", "红利"),
    ("中证红利", "中证红利"),
    ("A股", "A股"),
    ("美股", "美股"),
    ("港股", "港股"),
    ("债券", "债券"),
    ("国债", "国债"),
    ("量化", "量化"),
    ("半导体", "半导体"),
    ("华为", "华为"),
    ("DeepSeek", "DeepSeek"),
    ("英伟达", "NVIDIA"),
    ("NVIDIA", "NVIDIA"),
    ("楼市", "楼市"),
    ("房地产", "房地产"),
    ("理财", "理财"),
    ("美元", "美元"),
    ("人民币", "人民币"),
    ("美债", "美债"),
    ("通胀", "通胀"),
    ("CPI", "CPI消费者价格指数"),
    ("PMI", "PMI"),
    ("股息率", "股息率"),
    ("融资盘", "融资盘"),
    ("ETF", "ETF"),
    ("公募基金", "公募基金"),
    ("私募", "私募"),
    ("社保", "社保基金"),
    ("保险", "保险"),
    ("银行", "银行"),
    ("券商", "券商"),
    ("新能源", "新能源"),
    ("医药", "医药"),
]
# 仅保留真实存在的目标
LINKABLE = [(kw, slug) for kw, slug in LINKABLE if slug in existing_entity_slugs]

# 策略/宏观枢纽页（相对 wiki/ 的路径，去 .md）
STRATEGY_LINKS = [
    ("红利", "topics/02_投资/02-11_S1_哑铃策略"),
    ("哑铃", "topics/02_投资/02-11_S1_哑铃策略"),
    ("事件驱动", "topics/02_投资/02-12_S2_事件驱动"),
    ("全球宏观", "topics/02_投资/02-13_S3_全球宏观配置"),
    ("美债", "topics/02_投资/02-13_S3_全球宏观配置"),
    ("行业轮动", "topics/02_投资/02-14_S4_行业轮动"),
    ("A股", "topics/02_投资/02-15_S5_A股策略"),
    ("策略", "topics/02_投资/02-20_策略专题"),
    ("宏观", "topics/02_投资/02-10_宏观/02-10_宏观"),
]
STRATEGY_LINKS = [(kw, rel) for kw, rel in STRATEGY_LINKS if topic_page_exists(rel + ".md")]

HIGH_RELEVANCE = ["A股", "红利", "AI", "人工智能", "黄金", "原油", "债券", "楼市", "基金",
                  "量化", "理财", "美股", "港股", "策略", "资产配置", "利率", "汇率",
                  "半导体", "新能源", "医药", "消费"]

def parse_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_text = text[3:end].strip()
    body = text[end+4:].lstrip("\n")
    fm = {}
    for line in fm_text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm, body

def slugify_title(title, maxlen=36):
    t = title.strip()
    t = re.sub(r'[\\/:*?"<>|#]', "_", t)
    t = re.sub(r"\s+", "_", t)
    return t[:maxlen]

def extract_date(fm, filename):
    m = re.match(r"(\d{4}-\d{2}-\d{2})", filename)
    if m:
        return m.group(1)
    d = fm.get("date", "")
    m2 = re.match(r"(\d{4}-\d{2}-\d{2})", d)
    if m2:
        return m2.group(1)
    return datetime.date.today().isoformat()

def detect_topics(title, body):
    text = title + "\n" + body
    found = []
    for topic, kws in TOPIC_KEYWORDS.items():
        if any(kw in text for kw in kws):
            found.append(topic)
    # 必有「投资」
    if "投资" not in found:
        found.insert(0, "投资")
    return found

def relevance_level(title, body, topics):
    text = title + "\n" + body
    if any(kw in text for kw in HIGH_RELEVANCE):
        return "high"
    return "medium"

def clean_body(body):
    lines = body.splitlines()
    out = []
    i = 0
    n = len(lines)
    # 1) 跳过开头空行
    while i < n and lines[i].strip() == "":
        i += 1
    # 2) 去掉开头的 # 标题行
    if i < n and lines[i].lstrip().startswith("# "):
        i += 1
        # 3) 紧跟的 --- 分隔线
        while i < n and lines[i].strip() == "":
            i += 1
        if i < n and lines[i].strip() == "---":
            i += 1
    # 4) 去掉作者 blockquote 块（含 **作者**）及其后的 --- 分隔线
    skip = False
    while i < n:
        line = lines[i]
        if not skip and line.strip().startswith(">") and "**作者**" in line:
            skip = True
            i += 1
            continue
        if skip:
            if line.strip() == "---":
                skip = False
                i += 1
                continue
            # 跳过 blockquote 行与块内空行，直到遇到 --- 或正文
            if line.strip().startswith(">") or line.strip() == "":
                i += 1
                continue
            skip = False
        out.append(line)
        i += 1
    cleaned = "\n".join(out).strip()
    # 清理转换残留：行尾空白、空 bold 行 ** \n **
    cleaned = "\n".join(ln.rstrip() for ln in cleaned.splitlines())
    cleaned = re.sub(r"\*\*\s*\n\s*\*\*", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned

def preview(body, n_paras=3, maxlen=220):
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    pick = []
    for p in paras:
        if p.startswith("!["):  # 跳过图片行
            continue
        p = re.sub(r"^>\s?", "", p)
        if len(p) > maxlen:
            p = p[:maxlen] + "…"
        pick.append(p)
        if len(pick) >= n_paras:
            break
    return "\n\n".join(pick) if pick else "(暂无文字预览，详见原文)"

def auto_link(body):
    # 关联已知实体
    used = 0
    for kw, slug in LINKABLE:
        if used >= 18:
            break
        if kw in body:
            # 替换首个未链接的命中（避免破坏 URL / 已有 [[ ）
            pattern = re.compile(r"(?<!\[\[)(?<![\w/])(%s)(?!\]\])" % re.escape(kw))
            new_body, cnt = pattern.subn("[[%s|%s]]" % (slug, kw), body, count=1)
            if cnt:
                body = new_body
                used += 1
    # 关联策略/宏观页
    for kw, rel in STRATEGY_LINKS:
        if kw in body:
            slug = os.path.splitext(os.path.basename(rel))[0]
            pattern = re.compile(r"(?<!\[\[)(?<![\w/])(%s)(?!\]\])" % re.escape(kw))
            body, cnt = pattern.subn("[[%s|%s]]" % (slug, kw), body, count=1)
            if cnt:
                break
    return body

def build_source_page(fm, body, filename, topics, relevance, date_str, orig_rel):
    title = fm.get("title", filename)
    author = fm.get("author", "未知")
    role = fm.get("role", "")
    feed_id = fm.get("feed_id", "")
    # slug
    base = "xet-%s-%s" % (date_str, slugify_title(title))
    slug = base
    i = 1
    while os.path.exists(os.path.join(SOURCES, slug + ".md")):
        slug = "%s_%d" % (base, i)
        i += 1
    # 清理 + 预览 + 链接
    cleaned = clean_body(body)
    prev = preview(cleaned)
    linked = auto_link(cleaned)
    # 作者署名
    author_label = author + ("（%s）" % role if role else "")
    fm_out = [
        "---",
        "type: source",
        'title: "%s"' % title.replace('"', "'"),
        'source: "小鹅通·十六号内参（%s）"' % author,
        "date: %s" % date_str,
        'url: "%s"' % orig_rel,
        'author: "%s"' % author,
        'role: "%s"' % role,
        "topics: [%s]" % ", ".join(topics),
        "investment_relevance: %s" % relevance,
    ]
    if feed_id:
        fm_out.append('feed_id: "%s"' % feed_id)
    fm_out.append("---")
    lines = fm_out + [
        "",
        "# %s（%s）" % (title, author_label),
        "",
        "> 十六号内参 / %s / [本地存档](%s)" % (date_str, orig_rel),
        "",
        "## 要点预览",
        "",
        prev,
        "",
        "## 原文",
        "",
        linked,
        "",
        "sources: [%s](%s)" % (orig_rel, orig_rel),
        "",
    ]
    return slug, "\n".join(lines)

def main():
    dry = "--dry" in sys.argv
    limit = None
    for a in sys.argv[1:]:
        if a.startswith("--limit"):
            limit = int(a.split("=")[1]) if "=" in a else 0
    files = sorted([f for f in os.listdir(INBOX) if f.endswith(".md") and f != "README.md"])
    if limit:
        files = files[:limit]
    print("待处理: %d 篇" % len(files))
    done = 0
    skipped = 0
    errs = []
    for fn in files:
        path = os.path.join(INBOX, fn)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except Exception as e:
            errs.append((fn, str(e)))
            continue
        fm, body = parse_frontmatter(text)
        if not fm:
            skipped += 1
            continue
        date_str = extract_date(fm, fn)
        topics = detect_topics(fm.get("title", ""), body)
        relevance = relevance_level(fm.get("title", ""), body, topics)
        orig_rel = "raw/inbox/xiaoetong/%s" % fn
        slug, content = build_source_page(fm, body, fn, topics, relevance, date_str, orig_rel)
        if dry:
            done += 1
            continue
        out_path = os.path.join(SOURCES, slug + ".md")
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(content)
        # 移动源文件
        shutil.move(path, os.path.join(PROCESSED, fn))
        done += 1
    print("完成: %d  跳过(无frontmatter): %d  错误: %d" % (done, skipped, len(errs)))
    if errs:
        for e in errs[:10]:
            print("  ERR", e)

if __name__ == "__main__":
    main()
