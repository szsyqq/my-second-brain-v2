# 操作日志

> 记录知识库的所有变更历史（自下而上：个券 → 行业 → 宏观）。

---

## 2026-07-31 / 架构迁移 · v2 对齐 K神 schema

- **操作**：将 v2 从「纯 Markdown + convert.py(GitHub Pages)」改造为「Obsidian 库 + K神 schema」
- **改动**：
  - `vault/` → 重命名为 `wiki/`（wikilink 为文件名匹配，无断链）
  - 导入 `.wiki-schema.md` + `.wiki-schema/modules/` + `_sys/schema/`
  - 复制 v1 的 `.obsidian/`，使 v2 成为真正的 Obsidian 库
  - 新建 `raw/inbox` + `raw/processed`（按来源分桶）+ `raw/assets` 生命周期
  - 移植 `bundle_wiki.py` / `build_knowledge_base.py` / `lint_wiki.py`（修正 lint 硬编码路径）
  - 新建根级 `index.md` / `log.md` / `purpose.md` / `.wiki-cache.json`
  - 重写 `_workflow/sl` / `gx` / `jc` 为自下而上流程
  - 归档旧 GitHub Pages 管线（convert.py / deploy.sh / output / viewer）至 `_legacy/`
- **部署语义**：本地 Obsidian 主，CloudStudio `deploy-wiki/` 备用，GitHub Pages 不主动更新
- **状态**：架构迁移完成，待首次 `/gx` 实跑验证
