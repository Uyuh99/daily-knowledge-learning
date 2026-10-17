# UI 技术选型结论（PySide6 验证报告）

本报告是 `YZFD-20` 预研任务的产出。验证环境：Windows 10.0.26200 (x64)、Python 3.13.15、PySide6 6.12.0（Qt 6.12.0）、PyInstaller 6.22.3，通过 `uv` 管理依赖。

验证代码：`src/daily_knowledge_learning/ui/`（独立骨架，不依赖 `note_manager` / `file_writer` / `config`）。
运行入口：`python -m daily_knowledge_learning.ui`。

---

## 1. PySide6 的许可证是否适合本项目

**适合。**

| 项目 | 情况 |
| --- | --- |
| PySide6（Qt for Python）许可证 | LGPLv3 / GPLv3 / 商业授权 三选一 |
| 本项目性质 | 个人学习用途、公开练习仓库，不打算闭源分发 |
| 结论 | 采用 **LGPLv3** 即可，免费、可商用 |

关键注意点（LGPL 合规要点，写进约束避免以后踩坑）：

- 动态链接 Qt 库时，LGPL 允许闭源使用；PySide6 默认就是动态链接（打包后 Qt DLL 独立放在 `_internal/` 中，见第 4 节）。
- 若将来要闭源 + 静态链接 + 修改 Qt 源码，则需要商业授权。本项目不涉及。
- 对比 **PyQt6**（Riverbank）：PyQt6 是 GPLv3 或商业授权，闭源分发必须购买商业许可。**PySide6 的许可证比 PyQt6 更宽松，是选它的第一理由。**
- 对比 **Tkinter**：许可证无问题，但控件简陋、Markdown/中文排版和现代化 UI 明显吃亏。
- 对比 **Electron/Tauri**：许可证无问题，但打包体积（100MB+）与内存占用更高，且需要前后端两套技术栈，对个人项目成本过高。

## 2. 中文字体显示是否正常（Windows 下有没有豆腐块）

**正常，无豆腐块，但有一个必须显式处理的坑。**

实测（同一台 Windows 机器）：

| 运行方式 | `QFontDatabase.families()` 数量 | 命中的中文字体 |
| --- | --- | --- |
| 真实窗口平台（windows 插件，正常显示） | **411** | `Microsoft YaHei UI` |
| `QT_QPA_PLATFORM=offscreen`（离屏模式） | **0** | 无 |

字符宽度实测（真实平台）：

```text
Microsoft YaHei UI  学=13  沉=13  A=9
Microsoft YaHei     学=13  沉=13  A=9
SimHei              学=13  沉=13  A=7
```

中文字符宽度非 0，说明字形真实存在、不会回退成方框。字体栈按 `Microsoft YaHei UI → Microsoft YaHei → SimHei → SimSun → Noto Sans CJK SC` 顺序挑选（见 `ui/fonts.py: resolve_cjk_family()`）。

**两个必须记住的结论：**

1. **不要依赖 Qt 的默认字体。** Qt 在 Windows 下的默认族可能落到不含 CJK 字形的字体上，中文就会变豆腐块。必须像 `fonts.py` 那样显式按优先级挑选已安装字体，并通过 `QApplication.setFont()` 全局应用。
2. **`offscreen` 平台下没有任何字体。** 这意味着 CI / 无头环境测中文渲染时，只能断言"逻辑正确"（控件存在、`toPlainText()` 内容正确），**不能**断言"字面宽度正确"——offscreen 下宽度必然为 0。中文显示的验收必须在真实桌面会话里做（见第 4 节截图）。

## 3. Markdown 渲染方案：第一版用 `QTextEdit.setMarkdown()` 够不够

**第一版够用，但不适合最终形态。需要分阶段过渡。**

`QTextEdit.setMarkdown()` 是本骨架采用的方案（`ui/pages.py: MarkdownPreviewPage`），实测能正常渲染：

- 标题（`#` / `##`）→ 字号分级
- 粗体 / 斜体 / 行内 `代码`
- 无序列表
- 围栏代码块 ```` ``` ````（**只做等宽等样式呈现，无语法高亮**）
- 表格（转为普通文本块，**不保留边框和对齐**）

**它的短板（对本项目会真实踩到）：**

| 需求 | `setMarkdown()` |
| --- | --- |
| 语法高亮 | 不支持 |
| 表格边框 / 对齐 | 不支持，退化成纯文本 |
| Obsidian 双链 `[[笔记]]` | 不支持，原样显示 |
| 任务列表 `- [ ]` | 不支持勾选交互 |
| 内嵌 HTML / 数学公式 | 不支持（数学公式需额外方案） |
| 大文档滚动 / 增量渲染 | 全量解析，长文性能一般 |

**推荐方案：**

- **第一版（已落地）**：继续用 `QTextEdit.setMarkdown()`。理由：零依赖、随 PySide6 自带、能把"读一遍知识点"这个核心场景撑起来，避免过早引入复杂度。
- **第二版（建议替换为 `QTextBrowser` + `markdown` 库）**：用 `markdown`（或 `markdown-it-py`）把 Markdown 转成 HTML，再交给 `QTextBrowser.setHtml()`。收益：表格边框、更多语法、可插入自定义 HTML。依赖极小（纯 Python）。
- **需要代码高亮 / 数学公式时**：换 **`QWebEngineView`**（PySide6-WebEngine，本机已随 `pyside6` 装好）。用 `markdown-it-py` + `Pygments` 生成 HTML，公式交给 KaTeX/MathJax。代价是打包体积和内存显著上升（WebEngine 单独就几十 MB）。**不建议第一版就上，性能与体积代价与当前需求不匹配。**

一句话：**第一版 `setMarkdown()`，第二版 `markdown` 库 + `QTextBrowser`，WebEngine 只在明确需要高亮/公式时才上。**

## 4. 打包体积有多大，是否可接受

实测命令：

```powershell
uv run pyinstaller --noconfirm --windowed `
  --name daily-knowledge-learning `
  --paths src tools/ui_entry.py
```

产物为 `dist/daily-knowledge-learning/`（**onedir 模式**）：

| 指标 | 实测值 |
| --- | --- |
| 文件总数 | 206 个 |
| 目录总大小 | **117.5 MB** |
| 主程序 exe | 1.7 MB |
| `_internal/`（Qt DLL、Python 运行时） | 115.8 MB |

**实际运行验证（未跳过）**：直接双击/启动 `dist/daily-knowledge-learning/daily-knowledge-learning.exe`，进程 12 秒后仍存活，`Responding=True`，窗口标题为 `每日知识点学习`，随后可正常关闭。**不是空白窗口，不是打不开的产物。**

体积构成与优化空间：

- 117 MB 主要来自 PySide6 全量模块（含 WebEngine / PDF / Addons，这些当前骨架用不到）。
- 可用 `--exclude-module` 排除 `PySide6.QtWebEngineCore` / `QtPdf` 等，或用 PyInstaller 的 `--collect-submodules` 白名单裁剪；预估可压到 **60–80 MB**。
- 若用 `--onefile` 可压成单文件，但**启动会明显变慢**（每次解压到临时目录），桌面软件推荐继续用 onedir。
- **结论：117 MB 对桌面软件完全可接受**（对比 Electron 动辄 150–200 MB）。后续做体积优化即可，不构成选型阻碍。

打包注意点：

- `.gitignore` 已含 `dist/`、`build/`，**不要提交打包产物**（本任务已遵守）。
- 打包产物在**干净机器**上需要 VC++ 运行库（Qt 依赖），后续发布时随安装包附带。
- `--windowed` 保证不弹黑色控制台窗口。

## 5. 结论：建议采用 PySide6，还是推荐替代方案

**建议采用 PySide6。理由是逐条验证过的，不是照抄需求文档。**

| 维度 | 结论 |
| --- | --- |
| 许可证 | LGPLv3，个人项目免费，比 PyQt6 的 GPL/商业双授权更宽松 ✅ |
| 中文显示 | 正常，无豆腐块；但必须显式指定 CJK 字体栈（已在 `fonts.py` 落地）✅ |
| Markdown | 第一版 `setMarkdown()` 够用 ✅；第二版可平滑升级到 `markdown` + `QTextBrowser` |
| 打包 | PyInstaller onedir 一次成功，117 MB，产物实测能跑 ✅ |
| 开发效率 | Qt Widgets 是成熟桌面栈，中文文档/社区丰富，适合单人维护 ✅ |

**与替代方案对比（一句话各自否决理由）：**

- **PyQt6**：许可证更严（闭源需付费），功能与 PySide6 高度重叠，无理由切换。
- **Tkinter**：自带但控件能力弱，中文排版与 Markdown 渲染都要自造轮子。
- **Electron / Tauri**：体积、内存、双技术栈成本对个人项目过高。
- **Web 前端 + 本地服务**：引入本地 HTTP 服务与浏览器外壳，复杂度和安全面反而更大。

**风险与遗留事项（交接用）：**

1. 骨架**未接入** `note_manager` / `file_writer` / `config`（本任务刻意解耦）——接入时需重新定义数据流。
2. Markdown 第一版不支持语法高亮、表格边框、Obsidian 双链——按需在第二版解决。
3. 未做体积裁剪（117 MB → 预估 60–80 MB）。
4. 未配置应用图标、未做安装包（后续用 Inno Setup / NSIS 包装 onedir 产物）。
5. 未验证 Windows 高 DPI 缩放与深色模式下的显示效果。

---

## 附：验证证据

- 骨架源码：`src/daily_knowledge_learning/ui/`（`app.py` / `main_window.py` / `sidebar.py` / `pages.py` / `fonts.py`）
- 冒烟测试：`tests/test_ui_skeleton.py`（离屏运行，断言窗口标题、4 个导航入口、切页、Markdown 渲染）
- 打包入口：`tools/ui_entry.py`
- 界面截图：`test-output/ui-1-home.png` … `ui-4-settings.png`（真实窗口截取，含 Markdown 预览页）
