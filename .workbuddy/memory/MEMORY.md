# MEMORY.md — 第二大脑 v2 知识库（项目长期约定）

> 项目根：`/Users/panyp/文稿-本地-不参与同步/WorkBuddy-local/my-second-brain-v2/`
> 只记「跨会话仍然成立」的项目事实与约定。个案细节留在当日日志。

## 查看器（知识库.html）唯一真源
- **UI 改动只改 `知识库_template.html`**，再跑 `scripts/build_knowledge_base.py` 生成 `知识库.html` 并同步 `deploy-wiki/`。**禁止直接改构建产物**（8MB+ 带内联 bundle，改了下一次重建即丢）。
- 构建产物可用于反推模板状态（其脚本块无 PLACEHOLDER，`node --check` 可过）。

## 「更新历史」框架（v2.0.8 起，全站统一）
- 抽屉里恒定两个 tag：**本页更新历史 / 全部更新历史**。单一状态源 `updTab`，唯一渲染出口 `renderUpdateRecords()`。**不得再引入第二套状态变量或第二个「页面历史」视图**（历史上有过 global/page 模式 + 策略筛选 + 死掉的 openHistoryPanel 三套并行语义，是逻辑错误的根源）。
- 「本页更新历史」= 「📝 本页历次更新记录」+「📜 本页内容快照」两节**并列**。
  - **禁止把更新记录与内容快照按下标配对**：`bundle_wiki.py` 归档的快照只含 `version` + `content`（无时间戳），配对必然是伪配对。
- 入口固定三处，语义一致：侧栏「更新历史」→ 全部；页面标题旁按钮 → 本页（页面无 H1 时兜底到 `#content-header`，不得因缺 H1 就无入口）；首页「查看完整更新历史」卡片 → 全部。
- 抽屉**只在显式点击时打开**，不随页面打开自动弹出（自动弹出会让入口按钮的 toggle 语义变成"点一下反而关闭"）。
- 页面切换 / 回首页时，若抽屉开着必须刷新内容（`refreshUpdateDrawer()`），不得残留上一页。

## 数据事实（改渲染前先确认）
- 页面 slug = `wiki/` 下的相对路径（无 `.md`）。`update_records[].affected_pages[].slug` 会有指向已不存在页面的项 → 渲染前须用 `files[slug]` 存在性兜底。
- 页面内容**未做 frontmatter 剥离**直接交给 marked，所以 `---` 会被渲染成分隔线、`type:`/`title:` 会变成正文段落。判断"页面有无 H1"必须以**渲染后**的实际标题行为准，不能用文件首行判断。
- 快照最多保留 3 个（`wiki/.history/`）。

## 构建与部署红线（2026-10-16 补）
- **bundle 产物新鲜度必验**：`bundle_wiki.py` 失败时 `build_knowledge_base.py` 仍会用**旧 wiki-bundle.json** 构建成功且无告警。build 后必须 `grep -c "<新增页关键词>" wiki-bundle.json 知识库.html` 确认入包（≥1）再部署。
- **沙箱 EEXIST 坑**：WorkBuddy 沙箱 shim 对 `mkdir(exist_ok=True)` 也抛 PermissionError(EEXIST)。脚本写法一律 `if not DIR.exists(): DIR.mkdir()`。
- **断链审计必须镜像 resolveSlug 语义**（末段 basename 匹配），全串匹配会数倍高估断链数。
- **部署代理端口会漂移**：环境变量 HTTP_PROXY 可能 502，部署前先 `curl -x <proxy> https://github.com` 探测，1087 为历史可用兜底。
- **同名页歧义**：`02-15_S5_A股策略` 在 02-40（行业视角）与 02-20（策略框架）下同名共存，wikilink 解析歧义，2026-10-16 起待用户决定合并或重命名。

## 版本号
- `VERSION` 文件 + `应用更新记录.md` 表格同步维护，`build_knowledge_base.py` 注入到系统监控。
- **内容消化（/gx）不 bump**；**查看器 UI / 功能改动要 bump 次版本**，并在 `应用更新记录.md` 补一行。

## 部署
- gh-pages 强推，**必须走代理** `http://127.0.0.1:1087/`（`-c http.proxy=... -c https.proxy=...`），并加 `http.version=HTTP/1.1` + 大 `postBuffer`（大包直连会被掐断）。
- **校验上线必须用 SHA-256 逐字节比对**（裸 URL 有 CDN 缓存，用 `?v=` 绕过）；`grep` 关键词不可作判据（内容打包在转义后的 bundle 里）。
