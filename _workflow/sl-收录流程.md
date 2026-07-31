# /sl —— 收录流程（v2 版 · my-second-brain-v2）

> 配合 `sl` skill（路由壳）使用。将新素材（URL / 本地 PDF / 微信图片 / 纯文本）归档进 **v2 知识库**（`my-second-brain-v2/vault/`）。

## 项目路径

| 变量 | 值 |
|------|-----|
| V2_ROOT | `my-second-brain-v2/`（相对 `#LittleRedBook/` 空间根） |
| VAULT | `$V2_ROOT/vault/` |
| 源目录 | `$VAULT/sources/` |
| OCR 脚本 | `~/.workbuddy/skills/sl/scripts/pdf_ocr_extract.py`（用户级，含 CMap 乱码修复 Case D） |

## 与 v1 的区别（重要）
- v1 落在 `../小红书收藏/wiki/`，用 CloudStudio 构建；**v1 已于 2026-07-31 冻结，不再更新**。
- v2 落在 `my-second-brain-v2/vault/`，本地 git 版本化，经 `convert.py` → GitHub Pages 部署（`szsyqq.github.io/my-second-brain-v2`）。
- v2 源页 frontmatter 字段：`title / url / source / source_type / theme / saved_at / summary / fetched / investment_relevance`。**不再使用** v1 的 `original_path` / `extraction_method`。

## 流程

### 1. 解析来源 → slug
- 由 URL 域名或本地扩展名判断来源类型（同 v1 映射：小红书 / 知乎 / 微信 / 推特 / xiaoetong / pdf / docx / 网页 / 笔记）。
- 生成 slug：`YYYY-MM-DD-<标题关键词>`，目标文件 `$VAULT/sources/<slug>.md`。
- 查重：若 `$VAULT/sources/<slug>.md` 已存在则跳过或合并，不重复归档。

### 2. 抓取 + 提取
- 网页：WebFetch 抓正文（JS 渲染站抓不到则 `fetched: false`，不报错）。
- PDF / docx：调用 `pdf_ocr_extract.py`（含乱码自动转 OCR）。
- 微信图片：OCR 后落文本。

### 3. 写源页（v2 frontmatter）
```
---
title: "..."
url: "..."
source: "来源名"
source_type: "wechat|pdf|xiaoetong|zhihu|xiaohongshu|article|notes"
theme: [投资, ...]
saved_at: YYYY-MM-DD
summary: "一句话核心"
fetched: true|false
investment_relevance: high|medium|low|none
---
```
正文结构：`# 标题` → `> 作者 / 日期 / 原文链接` → `## 核心观点`（编号要点）→ `## 关键概念`（含 `[[实体/主题 wikilink]]`）→ `## 原文摘录`。

### 4. 暂存（不提交）
- 新源页留在 git **未提交**状态，作为 v2 的「inbox」。`/gx` 统一消化、提交、部署。
- 向用户回报：归档了哪几篇、slug、是否建议跑 `/gx`。

## 红线
- 绝不写 `../小红书收藏/wiki/`（v1 已冻结）。
- `[[wikilink]]` 目标若不存在，由 `/gx` 创建；本流程只引用不强制建。
- 不在 `vault/更新记录/` 放任何文件。
