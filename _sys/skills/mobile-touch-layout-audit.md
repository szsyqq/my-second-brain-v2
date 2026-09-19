---
name: mobile-touch-layout-audit
description: "诊断并修复触摸屏上的滚动/布局异常——内容滑不到最底部、滑动到末尾回弹卡住、固定侧栏或抽屉的底部被裁掉、横竖屏切换后错位。适用于 app-shell 类布局（body 定高 + 面板内部各自滚动）。含病灶清单、--app-h 动态视口修复模式，以及基于 puppeteer-core + 系统 Chrome 的真实布局 A/B 验证脚手架。触发词：触摸屏滑不到底、滑动回弹卡住、移动端滚动异常、面板底部被裁、固定面板滑不到底、100vh 问题、移动端布局验证、touch scroll、safe-area。"
version: 1.0
agent_created: true
---

# 触摸屏滚动/布局异常：诊断 · 修复 · 验证

## 何时用

- 触摸屏（手机/平板/触屏笔记本）上出现：内容**滑不到最底部**、滑到末尾**回弹卡住**、固定面板（侧栏/抽屉）**底部被裁**、横竖屏切换后布局错位。
- 要改动 app-shell 类布局（外层定高 + 内部面板各自滚动）的高度或滚动样式，需要**改前改后可量化**的验证，而非肉眼判断。

## 核心判断：`100vh` 不是「用户能看见的高度」

移动端 `100vh` 是**大视口**——包含浏览器地址栏/工具栏所占据的区域，比可视区更高。若同时外层 `overflow:hidden`，文档本身永不滚动，内部滚动面板的底部就落在可见区之外，**永远无法滚入视野**。用户感知为「滑到底了却还有内容看不见 / 回弹卡住」。

> 判断口诀：**只要「外层定高 + 外层不滚 + 内层滚动」三个条件同时成立，就必须用真实可视高度而非 `100vh`。**

注意：普通文档流长页面（整页滚动）**没有**这个问题，也不该给它定高——不要套用本模式。

## 病灶清单（逐条核对）

| # | 病灶 | 后果 |
|---|------|------|
| 1 | 外壳用 `height:100vh` 且 `overflow:hidden` | 所有内部滚动面板底部不可达 |
| 2 | `position:fixed` 面板用 `height:100%` | 高度按视口解析，同样中招 |
| 3 | 滚动容器缺 `overscroll-behavior` | 到底后回弹**串链**到外层，加重「卡住」感 |
| 4 | 纵向 flex 的滚动子项缺 `min-height:0` | 收缩失败，被父级 `overflow:hidden` 裁掉 |
| 5 | 底部内容贴边 | iPhone 底部指示条遮挡最后一行 |

补充：`<meta name="viewport">` 未带 `viewport-fit=cover` 时，`env(safe-area-inset-*)` 恒为 0，加 `env()` 也不会生效——不是 bug，别误判。

## 修复模式：动态视口变量

三段式，缺一不可：

1. **CSS 分层回退**：先写 `height:100vh`，再写 `height:var(--app-h,100vh)`。
   - 关键：`var()` 的**回退值必须是恒合法值**（如 `100vh`）。若回退成 `100dvh`，在不支持 `dvh` 的浏览器里该声明会「计算期无效」，`height` 退化为 `auto`，整个外壳塌掉。
2. **无 JS 兜底**：`@supports(height:100dvh){ ... }` 包一条以 `100dvh` 为回退的规则。
3. **JS 测量**：把真实可视高度写入 `--app-h`。要点：
   - 优先 `visualViewport.height`，但**必须判 `scale === 1`**——捏合缩放时它会随缩放变小，不判会让整个外壳跟着缩水。
   - 回退 `window.innerHeight`；取值后 `Math.round` 归一，避免亚像素抖动反复触发。
   - **加变化量 guard**：值没变就不要写 CSS 变量，否则每个 `scroll` 事件都会触发一次样式重算。
   - 监听 `resize` + `orientationchange` + `visualViewport` 的 `resize`/`scroll`；**旋转后 iOS 会连续几帧回报旧尺寸**，需延时（约 120ms / 400ms）复测一次。

同时：给每个滚动容器补 `overscroll-behavior:contain` 与 `min-height:0`；固定定位面板的高度也要跟随该变量。

## 验证：真实布局 + A/B 对照

用 `scripts/verify_touch_scroll.js`。要点：

- 本机可能只有 `puppeteer-core`（无自带浏览器），用**系统 Chrome** 作 `executablePath`；`NODE_PATH` 指向装有 `puppeteer-core` 的 `node_modules`。
- **headless 里 `innerHeight === visualViewport.height`，无法自然复现「工具栏吃掉 100vh」**。做法：把模拟视口当作**大视口**，以 `视口 − toolbar` 当作**用户可见高度**，让三种规则（现状 / 旧规则 `100vh` / 无 JS 兜底）对**同一可见基准**测量，比较「折叠线下被藏高度」。旧规则那一行应当显示 `+N ❌`，这就是 bug 被复现的证据。
- 必须单独确认 `--app-h` 是**页面自身 JS** 写入的，而不是测试脚本手动赋值造成的假象；并断言 `pageerror` 为空。
- **两套基准不可混用**：真实环境读数（`--app-h`、body 高度）对比浏览器自己的 `visualViewport.height`；A/B 场景读数对比模拟基准。混用会产生假阳性。

用法（一行）：

```bash
NODE_PATH=<node_modules> node scripts/verify_touch_scroll.js --file <html_path> --sidebar "#sidebar"
```

脚本输出场景对照表与退出码（0 通过 / 1 未通过），可挂进构建前检查。

## 决策规则

- 纯现代浏览器、且可接受无 JS：`100dvh` 足够。需要兼容旧 iOS Safari 就必须上 JS 测量。
- 抽屉/侧栏等**固定定位**面板要单独确认，它们的高度解析基准与普通块级元素不同。
- 改完必须重跑验证脚本；不接受「看着应该好了」。
- 若验证脚本报 `body 高度超出可视高度`，先检查它用的是哪套基准，别急着改布局。

## 变量

- `<project_root>`：站点项目根目录
- `<html_path>`：待验证的单文件 HTML
- `<node_modules>`：装有 `puppeteer-core` 的目录
- `<chrome_bin>`：系统 Chrome 可执行文件

## 附：沙箱构建踩坑

构建脚本里 `Path.mkdir(exist_ok=True)` 在受限文件代理下，对**已存在目录**抛的是 `PermissionError`（`exist_ok=True` 只能吞 `FileExistsError`），会中断构建。改为先 `exists()` 判断再 `mkdir`——同时是幂等优化。
