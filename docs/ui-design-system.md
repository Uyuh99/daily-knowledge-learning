# UI 设计系统（YZFD-31）

所有界面的视觉规则集中在这里与 `src/daily_knowledge_learning/ui/theme.py`。
页面不写自己的样式表；需要数值时从 `theme.C` / `theme.SPACE` 取，需要强调变化时
用控件的 `variant` 动态属性。原始控件样式冲突一律回到 `theme.stylesheet()` 修。

## 设计方向：纸墨书房

长时间阅读学习内容，界面应当像纸面笔记：暖白纸底、近黑墨字、单一青瓷色强调。
刻意避开 Qt 默认灰底 + 系统蓝，也避免纯白高对比造成的阅读疲劳。

- 背景分三层：纸面 `PAPER` → 卡片 `SURFACE` → 凹陷/轨道 `SURFACE_SUNK`
- 强调只有一种：青瓷 `ACCENT`，用于主按钮、当前导航、链接、进度
- 状态色只服务于学习状态徽标，不做装饰

## 色彩

| 令牌 | 值 | 用途 |
| --- | --- | --- |
| `PAPER` | `#FAF7F2` | 窗口与页面底色 |
| `SURFACE` | `#FFFFFF` | 卡片、编辑区、输入框 |
| `SURFACE_ALT` | `#F5F0E8` | 悬停行、侧栏底色 |
| `SURFACE_SUNK` | `#EDE7DC` | 进度轨道、禁用填充 |
| `BORDER` | `#E6DFD3` | 常规分隔线 |
| `BORDER_STRONG` | `#D3C9B8` | 输入框边界 |
| `INK` | `#232019` | 一级文字 |
| `INK_2` | `#5B544A` | 二级正文 |
| `INK_3` | `#8B8377` | 元信息、占位符 |
| `ACCENT` | `#2C6E63` | 主操作、当前项 |
| `ACCENT_SOFT` | `#E4EFEB` | 选中底色 |

学习状态（`STATUS_TONES`）：已学 `#40795B`、进行中 `#A0721C`、待学习 `#8B8377`、
已搁置 `#9A5B2C`。徽标用 `theme.tint(tone, 0.86)` 做底色。

## 字体层级

字体族由 `fonts.resolve_cjk_family()` 决定（Microsoft YaHei UI → YaHei → SimHei →
SimSun），基准 10.5pt。

| 层级 | 字号 | 字重 | objectName |
| --- | --- | --- | --- |
| 页面标题 | 22px | 600 | `pageHeading` |
| 页面副标题 | 12px | 400 | `pageSubtitle` |
| 区块标题 | 14px | 600 | `sectionTitle` |
| 正文 | 13px | 400 | 默认 |
| 元信息 | 12px | 400 | `metaText` |
| 极小标注 | 11px | 600 | `fieldLabel` / 徽标 |

Markdown 正文通过 `theme.document_stylesheet()` 统一 h1–h3、段落间距和代码底色。

## 间距与尺寸

- 间距阶梯 `SPACE = (4, 8, 12, 16, 24, 32)`，只用这些值
- 页面外边距统一 `24, 20, 24, 20`（`PageHeader` 所在容器）
- 卡片内边距 `18, 16, 18, 16`，卡片间距 12–16
- 圆角：控件 6、卡片行 8、大卡片/面板 12
- 控件高度 30；侧栏宽 212、导航行高 36
- 分隔线 1px `BORDER`；焦点环 2px `ACCENT`

## 组件

`ui/widgets.py` 提供：

| 组件 | 说明 |
| --- | --- |
| `PageHeader` | 标题 + 可选副标题 + 右侧操作区 |
| `SectionTitle` | 区块标题 |
| `Card` | 白底描边容器 |
| `EmptyState` | 虚线空/错误状态，含标题与提示 |
| `StatusPill` | 学习状态徽标 |
| `Hairline` | 1px 分隔线 |
| `primary_button` / `secondary_button` / `ghost_button` | 三种按钮变体 |
| `set_reading_metrics` | 阅读区行宽、边距与文档样式 |

## 交互状态

每个可交互控件都必须具备：正常、悬停、焦点、按下、禁用；列表项额外需要选中态。
输入类在聚焦时边框由 1px 变 2px `ACCENT` 并通过收回内边距保持尺寸不跳动。

## 页面节奏

1. `PageHeader`（标题 + 一句副标题 + 右侧主操作）
2. 筛选/上下文条（可选，12px 元信息文字）
3. 主内容区
4. 空状态或错误状态必须有明确的一句话说明与下一步动作

## 验收

`tools/capture_pages.py` 在 1024×680、1280×800、760×480 三档窗口下截取全部页面，
用于改造前后对比。截图输出到 `test-output/`，不提交。
