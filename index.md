# 知识库索引

> 第二大脑 · v2（K神 schema 对齐版）｜ 最后更新：2026-07-31

本库为**本地优先的 Obsidian 知识库**，结构遵循 K神 `.wiki-schema` 规范（详见 [.wiki-schema.md](.wiki-schema.md) 与 [.wiki-schema/modules/](.wiki-schema/modules/)）。

## 结构总览

```
my-second-brain-v2/
├── wiki/            # 知识库主体（实体/主题/素材/对比/综合/趣味发现/更新记录）
├── raw/             # 原始素材：inbox（待处理）/ processed（已处理）/ assets（附件）
├── _workflow/       # /sl 收录 · /gx 更新 · /jc 检查 流程
├── scripts/         # bundle_wiki.py · build_knowledge_base.py · lint_wiki.py
├── .wiki-schema.md  # schema 入口
└── deploy-wiki/     # CloudStudio 备用镜像（构建产物）
```

## 内容导航

- 内容入口：`wiki/index.md`（枢纽页与全库导航）
- 投资主线：`wiki/topics/02_投资/`（宏观→行业→个券，自下而上聚合）
- 旅游：`wiki/topics/03_旅游/`
- 个人：`wiki/topics/04_个人/`
- 更新记录：`wiki/更新记录/`
- 趣味发现：`wiki/Interesting_findings/`

## 运行方式

- `/sl <链接>` → 收录到 `raw/inbox/`
- `/gx` → 自下而上消化 inbox（个券→行业→宏观），生成 wiki 页面，构建并同步 `deploy-wiki/`
- `/jc` → 检查断链与一致性

> 本地 Obsidian 为主，CloudStudio `deploy-wiki/` 为只读备用镜像；GitHub Pages 不再主动更新。
