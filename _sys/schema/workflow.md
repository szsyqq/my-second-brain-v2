# 工作流 — Skills 系统与日常操作

> `.wiki-schema/modules/workflow.md` | 版本 3.0

## Skills 体系

| Skill | 用途 | 触发 |
|-------|------|------|
| `llm-wiki-skill` | 知识库构建（init/ingest/query/lint/graph） | "知识库"、"消化"、"查询" |
| `sl` | `/sl` 快捷归档 URL | `/sl <URL>` |
| `gx` | `/gx` 批量消化 inbox | `/gx` |
| `link-inbox` | 链接自动分类保存（全局） | 保存链接 |
| `wecom-unified` | 企业微信集成 | 企业微信操作 |

## 日常操作全流程

```
┌─────────────────────────────────────────────────┐
│                    日常流程                       │
│                                                   │
│  看到好文章                                       │
│     │                                             │
│     ▼                                             │
│  /sl <URL>        ← 收藏归档到 raw/inbox/         │
│     │                                             │
│     ▼                                             │
│  /gx              ← 批量消化 + 移到 processed     │
│     │                                             │
│     ▼                                             │
│  知识库更新 ✓     ← wiki 页面已生成               │
│                                                   │
└─────────────────────────────────────────────────┘
```

| 命令 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `/sl` | **收录** | URL（可多个） | 归档到 `raw/inbox/` |
| `/gx` | **更新** | 无（扫描 inbox） | 消化 → 移到 `processed/` |

### /sl 使用方法

```
/sl https://www.xiaohongshu.com/explore/xxx
/sl https://mp.weixin.qq.com/s/xxx https://www.zhihu.com/question/yyy
```

### /gx 使用方法

```
/gx
```

流程：扫描 inbox → 确认范围 → 逐篇消化 → 移动文件 → 总结报告
