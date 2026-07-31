# 第二大脑 v2（my-second-brain-v2）· K神 schema 对齐版

本地优先（local-first）的 **Obsidian 知识库**，结构遵循 K神 `.wiki-schema` 规范。

## 定位

- **主库**：本地 Obsidian 库（本目录）。用 Obsidian 打开即可浏览、编辑、看图谱。
- **规范**：`.wiki-schema.md` + `.wiki-schema/modules/`（base / ingest / workflow / investment / travel / aliases / query / lint / relationships / template）。schema 是「活的」——发现更好的结构就回写模块文件。
- **备用镜像**：`deploy-wiki/`（CloudStudio 沙箱），由 `/gx` 构建并同步，只读备份。
- **GitHub Pages**：**不再主动更新**。旧管线（`convert.py` / `deploy.sh` / `output/` / `viewer/`）已归档至 `_legacy/`，请勿调用。

## 三层结构

| 层 | 位置 | 说明 |
|---|---|---|
| 真相源（Obsidian 库） | `wiki/` | 实体 / 主题 / 素材 / 对比 / 综合 / 趣味发现 / 更新记录。Obsidian 直接编辑。 |
| 原始素材 | `raw/inbox/` → `raw/processed/` | `/sl` 收录进 inbox；`/gx` 消化后移至 processed。 |
| 构建 | `scripts/bundle_wiki.py` → `build_knowledge_base.py` | 读 `wiki/` → 产出 `知识库.html` + `wiki-bundle.json`，并写入 `deploy-wiki/`。 |
| 质检 | `scripts/lint_wiki.py` | 页面计数、wikilink 解析、孤儿页检测。 |

## 自下而上的建库原则

知识从「底」建起，再向上聚合：

```
个券 / 素材  ──→  行业  ──→  宏观
（wiki/sources, entities）   （行业页聚合）   （宏观枢纽页）
```

- `/sl`：只收录，落 `raw/inbox/`，不消化。
- `/gx`：自下而上消化 inbox —— 先生成素材摘要页与个券页，再回写父行业页（关联动态 + 信息流），最后才更新宏观枢纽页。宏观页不得无底层信号支撑而改写。

## 本地工作流

```bash
# 收录（URL / PDF / 图片 / 文本）
/sl <链接或路径>

# 更新（消化 inbox，生成/更新 wiki 页面，构建并同步备用镜像）
/gx

# 检查（断链 / 乱码 / 结构合规，只读）
/jc
```

详细流程见 `_workflow/`：
- `sl-收录流程.md`
- `gx-更新流程.md`（含自下而上聚合规则）
- `jc-检查流程.md`
- `更新历史编写规范.md`（更新记录格式）

## 部署说明

- 本地 Obsidian 为主，无需部署即可用。
- 如需在线只读备份：`/gx` 末尾会自动构建并 `workbuddy_cloudstudio_deploy deploy-wiki/`（CloudStudio 沙箱）。
- GitHub Pages 已停用；旧 `gh-pages` 站点不再更新。

## 版本管理

- `.gitignore` 忽略 `wiki/`、`raw/`、`deploy-wiki/`（本地内容不进 GitHub 仓库）。
- 仓库仅跟踪「系统」：`scripts/`、`_workflow/`、`_sys/schema/`、`.wiki-schema*`、`README.md`、`DEPLOY.md`、`index.md`、`purpose.md`、`log.md`。
- 内容备份 = CloudStudio `deploy-wiki/`（构建产物），非 git。

> v2 为主知识库：`/sl`、`/gx`、`/jc` 均指向本仓库。旧版 `../小红书收藏/wiki/`（CloudStudio 沙箱）自 2026-07-31 起冻结，不再更新。
