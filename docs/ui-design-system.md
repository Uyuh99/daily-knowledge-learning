# UI 设计系统

本次改造依据 awesome-design-md 的 references/design-md/claude/DESIGN.md，配合 frontend-design 做中文桌面适配。Claude 文件只作为书刊式设计参考，没有使用品牌标志或专有素材。保留 PySide6、Vault 文件格式、每日选题、AI 交流、三版笔记和归档流程。

## 视觉方向

暖米白纸面搭配墨色文字和陶土色操作，心理学与经济学用不同的纸张层次呈现真实学习进度。自绘书页、书签和细线图标呼应案头阅读；整套界面不使用绿色。

## 色彩与尺寸

视觉令牌集中在 src/daily_knowledge_learning/ui/theme.py。

| 令牌 | 值 | 用途 |
| --- | --- | --- |
| PAPER | #F8F6F0 | 页面画布 |
| SURFACE | #FFFEFA | 卡片、输入、编辑器 |
| SURFACE_ALT | #F0EEE5 | 轻层次与悬停 |
| SURFACE_SUNK | #E9E1D6 | 进度轨道 |
| INK | #38332D | 主要文字 |
| INK_2 | #645D55 | 次要文字 |
| INK_3 | #7A7067 | 元信息 |
| BORDER | #E3E0D4 | 分隔线 |
| ACCENT | #9D563F | 主操作与焦点 |
| ACCENT_SOFT | #F0E2D8 | 选中底色 |
| NAVY | #48382D | 插图墨色（兼容令牌） |
| MINT | #F2ECE2 | 心理学卡片（兼容令牌，实际为暖纸色） |
| PEACH | #F4E5D9 | 经济学卡片 |

- 间距阶梯：4、8、12、16、24、32px。
- 页面常用外边距24px，卡片间距16px，圆角8–12px。
- 标准控件高度38px，侧栏宽204px，导航行高40px。
- 按钮、输入、列表保留悬停、聚焦、按下、禁用与选中状态。
- 已学、进行中和待学习状态均使用墨色、陶土色和暖灰，不使用绿色。

## 中文排版与组件

正文优先使用本机微软雅黑 UI；页面标题依次尝试 Noto Serif SC Medium、华文中宋或宋体，缺失时回退到可用中文字体。显式将字体族应用至 Qt 样式，避免字号规则使中文回退到不合适的字体。标题28px、正文14px、元信息12px，Markdown 使用统一阅读边距与行高。

复用 PageHeader、Card、EmptyState、StatusPill、按钮变体和阅读区样式。BookIllustration 与 navigation_icon 使用 QPainter 自绘，不依赖网络字体或图片。

首页突出开始学习、两学科真实进度和最近完成记录。今日学习按独立思考、交流求证、整理归档三个步骤组织，并用问题 callout 引导阅读。笔记浏览用主题与日期状态两行列表；阅读正文限制最大宽度，宽屏才并排对照三个版本。首页、今日学习与设置允许纵向滚动。

## 验证与打包

运行 uv run pytest 验证既有业务流程。Windows 下先设置环境变量 QT_QPA_PLATFORM=windows，再运行 tools/capture_pages.py，分别检查1120×720、760×480、1440×900页面截图；输出位于 test-output/redesign，不提交。

运行 pwsh -NoProfile -ExecutionPolicy Bypass -File tools/build_windows.ps1 打包。构建包含 Python 稳定 ABI DLL 和 Qt DLL 搜索路径适配；将 Windows 系统目录放在构建搜索路径首位，避免误收集其他工具的不兼容 ICU。构建后验证主窗口标题及持续运行。
