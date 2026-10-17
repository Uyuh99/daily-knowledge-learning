# 每日知识点学习

这是一个用于学习 Python、LLM 应用、RAG 和 Agent 工程的公开练习项目。

项目最终目标是构建一个 Windows 桌面学习助手，直接维护 Obsidian Markdown 笔记。当前仓库只实现第 1 周的只读扫描原型，不会修改真实 Vault。

## 当前阶段

- Python 3.13+
- `uv` 环境管理
- pytest 测试
- `src/` 布局
- 只读扫描经济学和心理学学习记录
- 明确区分已学、进行中和旧版待学习记录

## 运行

```powershell
uv sync
uv run pytest
uv run daily-learning "C:\Users\17719\Documents\Obsidian Vault"
```

首次学习请先使用测试夹具：

```powershell
uv run daily-learning .\tests\fixtures\vault_minimal
```

真实 Vault 只读扫描路径是：

```text
C:\Users\17719\Documents\Obsidian Vault
```

## 桌面 UI 骨架（技术验证）

`src/daily_knowledge_learning/ui/` 是一个独立的 PySide6 骨架，用来验证桌面 UI 与
Windows 打包通路。它与正在整合的核心模块
（`note_manager` / `file_writer` / `config`）解耦，不影响上面的 CLI。

```powershell
uv sync
uv run python -m daily_knowledge_learning.ui
```

打包为 Windows 可执行程序（产物写到 `dist/`，不提交 Git）：

```powershell
uv run pyinstaller --noconfirm --windowed --name daily-knowledge-learning ^
  --paths src tools/ui_entry.py
.\dist\daily-knowledge-learning\daily-knowledge-learning.exe
```

选型结论、字体验证、Markdown 方案与体积数据见
[docs/ui-tech-choice.md](docs/ui-tech-choice.md)。

## 学习约定

每周任务、教材、视频和验收要求见 [docs/第1周任务.md](docs/第1周任务.md) 与 [docs/学习资源与周计划.md](docs/学习资源与周计划.md)。

真实 API 密钥、真实 Vault 内容和私人笔记不得提交到 Git。
