# /jc —— 检查流程（v2 · K神 schema 对齐）

> 配合 `jc` skill（路由壳）使用。静态检查知识库一致性，不改动内容（除非用户明确要求修复）。

## 项目路径

| 变量 | 值 |
|------|-----|
| V2_ROOT | `my-second-brain-v2/` |
| WIKI | `$V2_ROOT/wiki/` |
| 质检脚本 | `$V2_ROOT/scripts/lint_wiki.py` |

## 检查项

### 1. Wikilink 解析（核心）
- 运行 `python3 scripts/lint_wiki.py`：统计页面总数、解析 `[[wikilink]]`、标记断裂链接与孤儿页。
- 断裂链接 = `[[目标]]` 无对应 `wiki/**/<目标>.md` 文件名。逐条列出，交由用户决定：创建目标页 or 修正拼写。

### 2. 乱码扫描
- `grep -rl $'\uFFFD' wiki/ raw/`：任何 U+FFFD 替换符都需修复（含 `wiki/.history/` 快照）。

### 3. 结构合规
- `wiki/` 下应有 `entities/ topics/ sources/ comparisons/ synthesis/ Interesting_findings/ 更新记录/ queries/`。
- 投资三层：`topics/02_投资/` 下 宏观（02-10）→ 行业（02-2X）→ 个券（挂在行业文件夹下），个券不单独设枢纽。
- 主题页命名：`{编号}_{名}.md` = 枢纽；`{编号}-NN_{名}` = 子页；`{编号}-NN-MM_{名}` = 个券。

### 4. frontmatter 规范
- 实体/主题页含 `tags / created / updated / sources / investment_relevance`（投资相关）。
- 素材页含 `title / url / source / source_type / theme / saved_at / summary / fetched / investment_relevance`。

### 5. 自下而上一致性（投资）
- 抽查 3–5 个行业页：其「关联个券动态」是否能在对应个券页找到来源；宏观页的观点变化是否由行业/个券信号支撑（无凭空改写）。

## 流程
1. 跑 `lint_wiki.py` + 乱码扫描 + 结构合规清单。
2. 汇总问题清单（按严重度：断裂链接 > 乱码 > 命名违规 > frontmatter 缺项）。
3. 报告给用户；**默认不改文件**，仅当明确授权才修复。

## 红线
- 只读检查；修复动作需用户确认。
- 不碰 v1（`../小红书收藏/wiki/` 已冻结）。
