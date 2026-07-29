# v2 部署与更新流程

本文件定义 `my-second-brain-v2` 的日常更新标准动作。

**核心原则**：数据库与更新信息全在本地 Obsidian（`vault/`），GitHub 只托管构建产物（`gh-pages`），不是真相源、不存历史。

## 架构回顾

| 组件 | 作用 | 是否进 GitHub 主库 |
|------|------|------|
| `vault/` | 本地 Obsidian 内容库（真相源，本地 git 版本化） | 否（仅本地） |
| `scripts/convert.py` | 中间件：读 vault → 产出 `output/` | 是（main 分支） |
| `viewer/` | `index.html` + `app.js` + `style.css` + `vendor/` | 是（main 分支） |
| `output/` | 构建产物（索引 JSON + 前端三件套） | 否（只推 gh-pages） |
| GitHub Pages | 纯静态托管，独立于本地电脑是否开机 | gh-pages 分支 |

## 日常更新（内容改动）

1. 在 Obsidian 打开 `vault/`，编辑 / 新增 `.md`
2. 提交 vault 版本（历史跟踪依赖 vault 的 git 历史）：
   ```bash
   cd vault && git add -A && git commit -m "描述"
   ```
3. 一键部署：
   ```bash
   cd my-second-brain-v2 && ./deploy.sh "本次更新说明"
   ```
   脚本自动：跑 `convert.py` → 复制 `output/` → 推 `gh-pages`
4. 等约 1-2 分钟 GitHub Pages 构建，浏览器硬刷新（Cmd+Shift+R）查看

> 若未给执行权限，用 `bash deploy.sh "说明"` 运行即可。

## 框架 / 样式改动（`viewer/`）

改 `viewer/index.html`、`app.js`、`style.css` 后：

1. `./deploy.sh "框架调整说明"`（`output/` 会重新生成并包含最新 viewer）
2. 若同时改了 `scripts/convert.py` 本身，也需推 main：
   ```bash
   git add -A && git commit -m "middleware 调整" && git push origin main
   ```

## `deploy.sh` 做了什么

- 定位 python3（managed 3.13 优先，回退系统 python3）
- 运行 `scripts/convert.py` 生成 `output/`
- 复制 `output/` 到临时 git 仓，加 `.nojekyll`
- 设 `GIT_HTTP_VERSION=1`，强制推 `gh-pages`
- 打印线上 URL

## 故障排查

- **Pages 404 / 旧内容**：等 1-2 分钟传播；硬刷新；确认 `gh-pages` 分支根目录有 `index.html`
- **push 失败（HTTP/2）**：脚本已设 `GIT_HTTP_VERSION=1`；仍失败可试 `gh auth setup-git`
- **历史版本为空**：`convert.py` 的版本历史来自 `vault` 的 `git log`，编辑后需先 `git commit vault`
- **缓存**：`BUILD_VERSION` 时间戳自动破击，但保险起见硬刷新

## 与 `/gx` 的关系

`/gx` 是针对旧版（`小红书收藏/wiki/` + CloudStudio 沙箱）的素材消化流程，**不包含 v2**。

v2 是独立仓库、独立内容源（Obsidian 手动编辑），使用本文件的 `deploy.sh` 流程，不接入 `/gx`。两套体系刻意分离，避免误部署。
