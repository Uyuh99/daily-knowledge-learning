# 每日知识点学习

这是一个用于学习 Python、LLM 应用、RAG 和 Agent 工程的公开练习项目。

项目最终目标是构建一个 Windows 桌面学习助手，直接维护 Obsidian Markdown 笔记。当前仓库包含只读 Vault 扫描，以及可独立使用和测试的 Markdown 写入、YAML 更新、三版本笔记管理和配置基础模块。

## 当前阶段

- Python 3.13+
- `uv` 环境管理
- pytest 测试
- `src/` 布局
- 只读扫描经济学和心理学学习记录
- 明确区分已学、进行中和旧版待学习记录
- 原子 Markdown 创建与更新、并发冲突检测和幂等追加
- 保留注释和非目标字段的 YAML frontmatter 更新
- 三版本主题笔记创建、更新和 AI 参考内容追加
- JSON 配置与系统凭据库 API 密钥存储

核心模块接口与错误处理见 [docs/core-modules.md](docs/core-modules.md)。

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

## 学习约定

每周任务、教材、视频和验收要求见 [docs/第1周任务.md](docs/第1周任务.md) 与 [docs/学习资源与周计划.md](docs/学习资源与周计划.md)。

真实 API 密钥、真实 Vault 内容和私人笔记不得提交到 Git。模块测试只使用 `tmp_path` 和仓库内的最小只读扫描夹具。
