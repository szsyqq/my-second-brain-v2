# /gx —— 更新流程（v2 · K神 schema 对齐 · 自下而上）

> 配合 `gx` skill（路由壳）使用。消化 `raw/inbox/` 中待处理素材，自下而上（**个券 → 行业 → 宏观**）生成/更新 `wiki/` 页面，构建并发布：推 `gh-pages`（GitHub Pages 线上通道）+ 同步 CloudStudio 备用镜像 `deploy-wiki/`。

## 项目路径

| 变量 | 值 |
|------|-----|
| V2_ROOT | `my-second-brain-v2/` |
| INBOX | `$V2_ROOT/raw/inbox/` |
| PROCESSED | `$V2_ROOT/raw/processed/` |
| WIKI | `$V2_ROOT/wiki/` |
| 构建脚本 | `$V2_ROOT/scripts/bundle_wiki.py` → `build_knowledge_base.py` |
| 质检脚本 | `$V2_ROOT/scripts/lint_wiki.py` |
| 备用镜像 | `$V2_ROOT/deploy-wiki/`（CloudStudio 沙箱） |

## 设计原则：自下而上

知识库从「底」建起，再向上聚合：

1. **底 · 个券 / 素材**：每篇 inbox 素材先生成 `wiki/sources/<slug>.md`（素材摘要页）；投资相关且涉及个股 → 在所属**行业文件夹**下创建/更新**个券页**，并写入 `## 信息流（标准化表）` 一行（日期/信息/定性/催化性质/信号判定/来源）。
2. **中 · 行业**：个券更新后，自动在其父**行业页**追加「关联个券动态 / 联动」与信息流汇总行——行业是「个券的集合视图」。
3. **顶 · 宏观**：当素材属宏观（货币政策、利率、流动性、PMI 等）或行业变化触发宏观再定价时，更新**宏观枢纽页**（`wiki/topics/02_投资/02-10_宏观/`）的信息流与观点变化。

> 一切更新「先底后顶」：永远先落个券/素材，再回写行业，最后才动宏观。宏观页不得凭空改写——必须有底层个券/行业信号支撑。

规则细节见 schema 模块：`.wiki-schema/modules/investment.md`（三层体系与信息流）、`ingest.md`（生命周期）、`workflow.md`（Skills）。

## 流程

### 步骤 1：扫描 inbox
列出 `raw/inbox/` 下所有 `.md`（跳过 `.wiki-cache.json`），按子目录分组统计，向用户展示待处理清单。

### 步骤 2：逐个消化（自下而上）
对每篇 inbox 文件：
1. 读取 frontmatter + 正文，提取 `[[wikilink]]` 目标与 `investment_relevance`。
2. **生成素材摘要页** `wiki/sources/<slug>.md`（精简 frontmatter + 正文要点），`sources:` 指向原始 inbox 文件。
3. **底 · 实体 / 个券**：
   - 若 `[[实体]]` 不存在 → 在 `wiki/entities/` 建骨架（`sources:` + `tags:`）；存在 → 回填 `sources:` 与正文链接。
   - 投资相关个股 → 在所属**行业文件夹**下创建/更新**个券页**，写入信息流一行。
4. **中 · 行业联动**：在父**行业页**追加「关联个券动态」与信息流汇总行（行业 = 个券集合视图）。
5. **顶 · 宏观分流**（仅当适用）：时效性→宏观信号流；框架方法→交易手册；象限改变→观点变化+反向联动，写回**宏观枢纽页**。
6. 移动源文件 `raw/inbox/{type}/<slug>.md` → `raw/processed/{type}/`。

### 步骤 3：指标刷新（定量）

> 与素材消化并行的定量数据更新。**即使 inbox 无新素材，本步骤仍执行**——策略与宏观指标需定期刷新以判断趋势性调整。

1. 打开 `_workflow/指标刷新台账.md`，按「策略层 → 宏观层」顺序遍历「状态=可获取/待验证」的指标（「不可得」直接跳过）。
2. 每个指标按「数据源优先级」取数：财汇 MCP → 同花顺 iFind MCP → 网络搜索。财汇先 `caihui_mcp_metadata` 定位子工具再 `execute_tool`；同花顺用 `get_edb_data` 自然语言查询。
3. 取到最新值 → 对比台账「上期值」判趋势（↑/↓/→），写回台账「最新值/数据日期/上期值/趋势」；「待验证」首次取数成功 → 状态改「可获取」。
4. 月度指标（PMI/CPI/PPI/社融/工业企业利润等）：距上次刷新 >30 天或数据刚发布时才刷新，否则沿用现值、跳过。
5. 取数失败 → 依序降级到下一数据源；三级均失败 → 状态标「不可得」，记入台账「已知冻结项」，之后不再主动重试。
6. **趋势性调整判定**：连续两期同向，或突破关键阈值（荣枯线 50 / 利差 0 / PE 历史中枢 ~13 倍等）→ 记入步骤 4 更新记录「观点变化」节，并按台账「刷新结果回写清单」回写对应策略页/仪表盘的「最新值/判定」列。

### 步骤 4：全量收尾
1. 重写 `wiki/index.md`（以实际目录树为准，每条 `[[链接]]` 真实存在）与 `wiki/overview.md`（更新统计数字）。
2. 乱码扫描（构建前必做）：`grep -rl $'\uFFFD' wiki/ raw/`，发现 U+FFFD 立即修复（当前文件手工改，`.history` 快照用 difflib 相似度匹配逐行替换）。
3. 质检：运行 `scripts/lint_wiki.py`，核对页面数、wikilink 解析、孤儿页。
4. 写**更新记录** `wiki/更新记录/{YYYY-MM-DD}_第{N}次更新.md`，N 为 v2 序列下一个整数（当前末次见 `wiki/更新记录/`，注意历史空缺保留不重排）。严格按 `_workflow/更新历史编写规范.md`：frontmatter + `## 📌 必看清单` / `## 新增页面` / `## 更新页面` / `## 观点变化`。必看清单与新增/更新页一律 `- [[slug]] — 说明` 列表，禁表格、禁 🔴🟡🟢 替代 1–5 分。
5. 趣味发现触发检查：距上次 `Interesting_findings` ≥1 天则新增一期（沿用现有 IF 格式，语气略带幽默的研究报告口吻）。

### 步骤 5：构建 + 备用镜像
1. `cd $V2_ROOT && python3 scripts/bundle_wiki.py` → 生成 `wiki-bundle.json`。
2. `python3 scripts/build_knowledge_base.py` → 生成 `知识库.html`（同时写入 `deploy-wiki/`）。
3. 发布线上（GitHub Pages）：`cp 知识库.html deploy-wiki/index.html` 确保 `deploy-wiki/index.html` 为最新；随后将 `deploy-wiki/` 内容强推 `gh-pages`（命令见 DEPLOY.md「手动构建」段；本地无 gh-pages 分支时用 `/tmp/_v2_deploy` 临时仓库强推）。
4. 备用镜像（CloudStudio）：`workbuddy_cloudstudio_deploy deploy-wiki/`（沙箱，只读备份）。
5. 回报：更新记录链接、断链情况、GitHub Pages 线上地址、备用镜像地址。

## 红线
- 不碰 v1（`../小红书收藏/wiki/` 已冻结）。
- 自下而上：宏观页不得无底层信号支撑而改写。
- **GitHub Pages 是线上发布通道**：`/gx` 构建后推 `gh-pages`（见 DEPLOY.md）；`deploy-wiki/` 是**备用**镜像（CloudStudio，按需同步）。旧 `convert.py`/`deploy.sh` 已归档 `_legacy/`，勿调用。
- `workbuddy_cloudstudio_deploy` 推送前确认 `git status` 与构建产物无误。
