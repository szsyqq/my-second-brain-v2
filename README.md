# 第二大脑 v2（my-second-brain-v2）

本地优先（local-first）的个人知识库。架构与 v1 的根本区别：**内容/版本/更新信息全部在本地 Obsidian 维护，GitHub 只承载构建产物（纯静态托管）**。

## 三层结构

| 层 | 位置 | 说明 |
|---|---|---|
| 数据库（真相源） | `vault/` | Obsidian 管理的 Markdown，本地 git 版本化。**不进 GitHub 仓库**（被 .gitignore），不在此作为数据库维护 |
| 中间件 | `scripts/convert.py` | 读 `vault/` → 产出 JSON 契约（`output/wiki-bundle.json` 瘦包 + `output/wiki-content.json` 内容包）。复用 frontmatter / `[[wikilink]]` / graph / tree / 更新记录解析 |
| 可视化 | `viewer/` | `index.html` + `app.js` + `style.css` + `vendor/`。只渲染 JSON，不碰内容细节 |

## 历史跟踪模型（v2 改进点）

- **子页面历史**：`vault/` 是本地 git 仓库 → `git log/show/diff` 派生真实版本快照（无上限）。middleware 预渲染最近 3 版的 `{version, sha, date, msg, content, segments}` 进 `wiki-content.json`，部署物为纯静态，查看时无需 git。
- **更新徽标（新增/更新）**：基于本地 `_buildstate.json` 缓存（编辑即标记，无论是否提交），重构建时比对，填入 `diff_data` / `update_severity`。
- **整体更新记录**：`vault/更新记录/*.md` 是人工撰写的 release note，middleware 解析为 `update_records`，与子页面历史同源（都来自本地 vault）。

## 本地工作流

```bash
# 1) 在 vault/ 用 Obsidian 编辑内容（可选：提交到本地 git 以获得历史版本）
cd vault && git add -A && git commit -m "..."

# 2) 转换 + 构建静态站
python3 scripts/convert.py
# 产物在 output/ ：index.html + app.js + style.css + vendor/ + wiki-bundle.json + wiki-content.json

# 3) 本地预览
cd output && python3 -m http.server 8753

# 4) 部署到 GitHub Pages（仅 output/）
# 将 output/ 内容推到 gh-pages 分支即可
```

## 部署说明

- `main` 分支：仅应用代码（`scripts/` + `viewer/`）。
- `gh-pages` 分支：仅构建产物（`output/` 内容）。GitHub Pages 作为静态 CDN，不持有可编辑数据库。
- 框架改动只改 `viewer/`，秒级重建；内容改动只跑 `convert.py`，页面框架纹丝不动 → 显示天然一致，不再整页重建。

## 一键部署（推荐）

日常更新只需两条命令，完整说明见 [DEPLOY.md](DEPLOY.md)：

```bash
cd vault && git add -A && git commit -m "更新说明"   # 1) 提交内容版本（历史跟踪依赖 vault 的 git 历史）
./deploy.sh "更新说明"                                # 2) 构建 output/ 并强制推 gh-pages
```

`deploy.sh` 自动完成：定位 python3 → 运行 `convert.py` → 复制 `output/` 到临时 git 仓（加 `.nojekyll`）→ `GIT_HTTP_VERSION=1` 推 `gh-pages`。若未给执行权限，用 `bash deploy.sh "说明"` 运行。

> v2 与 `/gx` 是两套独立体系：`/gx` 针对旧版（`小红书收藏/wiki/` + CloudStudio 沙箱），**不包含 v2**；v2 用本文件的 `deploy.sh` 流程，刻意分离避免误部署。
