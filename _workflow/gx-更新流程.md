# /gx —— 更新流程（v2 版 · my-second-brain-v2）

> 配合 `gx` skill（路由壳）使用。消化 `vault/` 中未提交的新源页，补全实体/主题页，写更新记录，经 `convert.py` + `deploy.sh` 部署到 GitHub Pages。

## 项目路径

| 变量 | 值 |
|------|-----|
| V2_ROOT | `my-second-brain-v2/` |
| VAULT | `$V2_ROOT/vault/` |
| 部署脚本 | `$V2_ROOT/deploy.sh` |
| 归一脚本 | `$V2_ROOT/scripts/normalize_update_records.py` |
| 线上地址 | `https://szsyqq.github.io/my-second-brain-v2/` |

## 与 v1 的区别（重要）
- v1 走 `bundle_wiki.py` → `build_knowledge_base.py` → CloudStudio；**v1 已冻结**。
- v2 走 `convert.py`（产出 `output/`）→ `deploy.sh`（推 `gh-pages`）。
- v2 更新记录严格遵循 `_workflow/更新历史编写规范.md`（frontmatter + `## 📌 必看清单` 等锚点章节）。

## 流程

### 步骤 1：扫描 inbox（未提交变更）
- 在 `$VAULT` 跑 `git status`，列出未提交的 `sources/` 新页与改动页，向用户展示待消化清单。

### 步骤 2：逐个消化
对每篇新源：
1. 读取 frontmatter + 正文，提取 `[[wikilink]]` 目标。
2. **实体页**：若 `[[实体]]` 不存在，在 `entities/` 建骨架（`sources:` 列表 + `tags:`）；若存在，回填 `sources:` 与正文链接。
3. **主题页**：投资相关素材按 `topics/02_投资/...` 归层；新行业在对应目录建骨架页。
4. **宏观分流**：时效性→更新记录信号流；框架方法→交易手册；象限改变→观点变化。
5. 源页已在收录阶段落位 `sources/`，此处只补链接与联动。

### 步骤 3：全量收尾
1. 更新 `vault/overview.md` 统计（素材 / 实体 / 主题 / 趣味发现 / 更新记录计数）。
2. 乱码扫描：`grep -rl $'\uFFFD' vault/`，发现即修复（含 `.history` 快照）。
3. **写更新记录**：`vault/更新记录/YYYY-MM-DD_第N次更新.md`，N 为 v2 序列下一个整数（当前末次 `2026-07-28_第19次更新` → 下次 **第20次**；注意 v2 第15次原始缺失，保留空缺不重排）。严格按 `_workflow/更新历史编写规范.md`：frontmatter（`tags: [更新记录]` / `created` / `importance 1-5` / `更新类型`）＋ 标题行 `第N次更新 | 日期 | 概述` ＋ `## 📌 必看清单` / `## 新增页面` / `## 更新页面` / `## 观点变化` 锚点章节。
4. 趣味发现触发检查：距上次 `Interesting_findings` ≥1 天则新增一期（沿用 v2 现有 IF 格式）。
5. 运行 `normalize_update_records.py` 归一本次记录格式。

### 步骤 4：提交 + 部署
1. 提交内容版本（v2 页面历史依赖 vault git 历史）：
   `cd vault && git add -A && git commit -m "第N次更新：一句话"`
2. 一键部署：`bash deploy.sh "第N次更新：一句话"`
   脚本自动跑 `convert.py` → 复制 `output/` → 推 `gh-pages`。
3. 等 1–2 分钟 Pages 构建，回报线上地址与本次更新记录链接。

## 红线
- 不碰 v1（`../小红书收藏/wiki/`）。
- `vault/更新记录/` 只放更新记录 `.md`，且遵守 `_workflow/更新历史编写规范.md`。
- `deploy.sh` 会**强制推 `gh-pages`**；提交前确认 `git status` 无误。
