# /sl —— 收录流程（v2 · K神 schema 对齐）

> 配合 `sl` skill（路由壳）使用。将新素材（URL / 本地 PDF / 微信图片 / 纯文本）归档进 **v2 知识库**的 `raw/inbox/`。本流程只「收」，不「消化」——消化由 `/gx` 完成。

## 项目路径

| 变量 | 值 |
|------|-----|
| V2_ROOT | `my-second-brain-v2/`（`#LittleRedBook/` 空间下） |
| INBOX | `$V2_ROOT/raw/inbox/` |
| 源页产出 | 由 `/gx` 生成到 `$V2_ROOT/wiki/sources/` |
| OCR 脚本 | `~/.workbuddy/skills/sl/scripts/pdf_ocr_extract.py`（含 CMap 乱码修复 Case D） |

## 与 v1 的关系

- v1（`../小红书收藏/wiki/`）已于 2026-07-31 冻结，不再更新。
- v2 是 K神 schema 对齐版：**本地 Obsidian 为主**，`deploy-wiki/`（CloudStudio）为只读备用镜像，GitHub Pages 不再主动更新。

## 来源分类 → 落桶

| 识别特征 | 子目录 |
|----------|--------|
| xiaohongshu.com / xhslink.com | `raw/inbox/xiaohongshu/` |
| zhihu.com | `raw/inbox/zhihu/` |
| mp.weixin.qq.com / weixin.qq.com | `raw/inbox/wechat/` |
| x.com / twitter.com | `raw/inbox/tweets/` |
| quanzi.xiaoe-tech.com | `raw/inbox/xiaoetong/` |
| .pdf / .PDF 本地路径 | `raw/inbox/pdfs/` |
| .docx / .doc 本地路径 | `raw/inbox/docs/` |
| 其他网页 | `raw/inbox/articles/` |
| 纯文本 / 无 URL | `raw/inbox/notes/` |

## 流程

### 1. 解析来源 → 确定子目录（上表）

### 2. 抓取 + 提取（best-effort）
- 网页：`WebFetch` 抓正文；JS 渲染站抓不到 → `fetched: false`，不报错。
- PDF / docx：复制原文件到 `raw/inbox/pdfs/`（重命名为有意义名字），用 `pdf_ocr_extract.py` 提取文本（PyMuPDF → OCR fallback）；失败标记 `fetched: false`。
- 微信图片：OCR 后得到文本。

### 3. 生成 inbox 文件
文件名：`{YYYY-MM-DD}-{标题关键词}.md`（同名冲突追加序号）。
frontmatter：
```
---
title: "..."
url: "..."
source: "来源名"
source_type: "wechat|pdf|xiaoetong|zhihu|xiaohongshu|tweets|article|notes|docs"
theme: [投资, ...]          # 1–4 个中文标签
saved_at: YYYY-MM-DD
summary: "一句话核心"
fetched: true|false
investment_relevance: high|medium|low|none
---
```
正文：`# 标题` → `> 作者 / 日期 / 原文链接` → `## 核心观点`（编号要点）→ `## 关键概念`（含 `[[实体/主题 wikilink]]`）→ `## 原文摘录`。

### 4. 暂存（不提交，留在 inbox）
- 新文件留在 `raw/inbox/` 未提交状态，作为 v2 的「待消化」队列。`/gx` 统一消化、生成 `wiki/sources/`、移动至 `raw/processed/`、构建并同步 `deploy-wiki/`。
- 回报：归档篇数、子目录、图片/OCR 情况、抓取失败、重复跳过。

## 红线
- 绝不写 `../小红书收藏/wiki/`（v1 已冻结）。
- 本流程**不创建** `wiki/sources/` 页面（那是 `/gx` 的职责）；只引用 `[[wikilink]]`，目标由 `/gx` 创建。
- 不在 `raw/processed/` 或 `wiki/更新记录/` 放任何文件。
