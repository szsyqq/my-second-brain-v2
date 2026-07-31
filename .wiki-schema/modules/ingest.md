# Ingest — 素材消化规则

> `.wiki-schema/modules/ingest.md` | 版本 3.0

## 素材生命周期

```
企业微信转发 / 手动保存
        │
        ▼
  raw/inbox/{类型}/        ← 新素材先存入 inbox
        │
        ▼
   AI 消化处理              ← 提取、分类、生成 wiki 页面
        │
        ▼
  raw/processed/{类型}/     ← 完成后从 inbox 移动到 processed
```

**发现规则**：AI 扫描 `raw/inbox/` 下所有子目录，发现新文件后自动触发 ingest。完成后将源文件移至 `raw/processed/` 对应子目录。

## 来源自动分类

| 识别特征 | 分类 | 目录 |
|----------|------|------|
| URL 含 `xiaohongshu.com` / `xhslink.com` | 小红书 | `raw/inbox/xiaohongshu/` |
| URL 含 `zhihu.com` | 知乎 | `raw/inbox/zhihu/` |
| URL 含 `mp.weixin.qq.com` | 微信公众号 | `raw/inbox/wechat/` |
| URL 含 `x.com` / `twitter.com` | X/Twitter | `raw/inbox/tweets/` |
| 文件为 `.pdf` | PDF | `raw/inbox/pdfs/` |
| 普通网页（以上都不匹配） | 网页文章 | `raw/inbox/articles/` |
| 纯文本（无 URL） | 笔记 | `raw/inbox/notes/` |

## 分级处理

**完整处理**（> 1000 字）：
1. 生成摘要页 `wiki/sources/`
2. 提取 3-5 个关键概念
3. 评估投资相关性，标注 `investment_relevance`
4. 检查 / 创建实体页
5. 检查 / 创建 / 更新主题页
6. 更新 `index.md`、`log.md`
7. 移动源文件到 `raw/processed/`
8. 运行 lint 质量检查

**简化处理**（≤ 1000 字）：
1. 生成摘要页
2. 提取 1-3 个关键概念
3. 评估投资相关性
4. 概念有实体页 → 追加；无 → 摘要页标注
5. 更新 `index.md`、`log.md`
6. 移动源文件
7. 跳过主题页创建 / 更新

## 来源边界

| 分类 | 来源 | 处理原则 |
|------|------|----------|
| 核心主线 | PDF / Markdown / 文本 | 不依赖外挂，直接处理 |
| 企业微信转发 | 网页 / 公众号 / 小红书 / 知乎 | 自动接收并分类 |
| 手动入口 | 本地文件、纯文本 | 直接使用 |

## 素材类型路由

| 来源 | inbox | → processed | 处理 |
|------|-------|-------------|------|
| 网页文章 | `inbox/articles/` | `processed/articles/` | 直接读取 |
| 微信公众号 | `inbox/wechat/` | `processed/wechat/` | 直接读取 |
| 小红书 | `inbox/xiaohongshu/` | `processed/xiaohongshu/` | 直接读取（本地 MD） |
| 知乎 | `inbox/zhihu/` | `processed/zhihu/` | 直接读取 |
| PDF | `inbox/pdfs/` | `processed/pdfs/` | 直接读取 |
| 纯文本 | `inbox/notes/` | `processed/notes/` | 直接读取 |
