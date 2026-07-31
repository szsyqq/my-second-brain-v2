# v2 部署与更新流程（K神 schema 对齐版）

本文件定义 `my-second-brain-v2` 的部署语义与更新标准动作。

## 部署语义（重要）

| 通道 | 状态 | 说明 |
|------|------|------|
| **本地 Obsidian** | 主库 | 直接用 Obsidian 打开本目录即可浏览/编辑，无需部署。 |
| **GitHub Pages** | **实际发布通道** | `/gx` 构建后推 `gh-pages` 分支，线上地址 `https://szsyqq.github.io/my-second-brain-v2/`（构建链路见「日常更新」）。 |
| **CloudStudio `deploy-wiki/`** | 备用镜像 | `/gx` 构建产物本地副本，可按需 `workbuddy_cloudstudio_deploy` 推送只读在线备份。 |

> 设计意图：本地 Obsidian 为真相源与日常使用面；GitHub Pages 为线上发布通道；`deploy-wiki/` 保留构建产物作备用。

## 架构回顾

| 组件 | 作用 | 进 GitHub 主库？ |
|------|------|------|
| `wiki/` | 本地 Obsidian 内容库（真相源） | 否（`.gitignore` 忽略，本地优先） |
| `raw/inbox` · `raw/processed` | 素材生命周期 | 否 |
| `scripts/bundle_wiki.py` · `build_knowledge_base.py` · `lint_wiki.py` | 构建 / 质检 | 是（main 分支） |
| `.wiki-schema*` · `_sys/schema/` · `_workflow/` | schema 与流程 | 是 |
| `deploy-wiki/` | 构建产物（备用镜像） | 否 |

## 日常更新（标准动作）

```bash
# 1) 收录素材（落 raw/inbox/）
/sl <链接或本地路径>

# 2) 消化 + 构建 + 发布（自下而上：个券→行业→宏观）
/gx
#   /gx 内部：生成 wiki 页面 → bundle_wiki.py → build_knowledge_base.py
#   → 知识库.html + deploy-wiki/ 产物 → 推 gh-pages（线上发布）
```

无需手动跑构建脚本；`/gx` 已串联完整链路。仅在调试构建时才单独执行 `scripts/` 下的脚本。

## 手动构建（调试用）

```bash
cd my-second-brain-v2
python3 scripts/bundle_wiki.py          # 生成 wiki-bundle.json
python3 scripts/build_knowledge_base.py  # 生成 知识库.html + 写入 deploy-wiki/
python3 scripts/lint_wiki.py            # 质检：页面数 / 断链 / 孤儿
# 推送线上（本地仓库无 gh-pages 分支，用临时仓库强推）：
cd /tmp && rm -rf _v2_deploy && mkdir _v2_deploy
cp -r my-second-brain-v2/deploy-wiki/* _v2_deploy/ && touch _v2_deploy/.nojekyll
cd _v2_deploy && git init -q && git checkout -q -b gh-pages && git add -A
git -c user.email=panyp@local -c user.name=panyp commit -q -m "更新说明"
GIT_HTTP_VERSION=1 git push -f https://github.com/szsyqq/my-second-brain-v2.git gh-pages
```

## 故障排查

- **断链/孤儿**：跑 `lint_wiki.py` 看明细；`/jc` 可交互检查。
- **乱码（U+FFFD）**：`grep -rl $'\uFFFD' wiki/` 定位，手工修复（含 `.history` 快照）。
- **备用镜像未更新**：确认 `workbuddy_cloudstudio_deploy` 执行成功、沙箱在线。
- **构建产物异常**：检查 `wiki/` 目录树与 frontmatter 是否合规（见 `.wiki-schema/modules/base.md`）。

## 与 `/sl` `/gx` `/jc` 的关系

- `/sl`：收录 → `raw/inbox/{type}/`（只收不消化）。
- `/gx`：自下而上消化 inbox → 生成/更新 `wiki/` → 构建 → 推 gh-pages（线上发布，`deploy-wiki/` 产物保留作备用）。
- `/jc`：只读检查一致性（断链/乱码/结构合规）。

更新记录严格遵循 `_workflow/更新历史编写规范.md`。

> 旧版 `../小红书收藏/wiki/`（CloudStudio 沙箱）自 2026-07-31 起冻结，不再更新。v2 为唯一前向目标。
