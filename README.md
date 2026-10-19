# 每日知识点学习

Windows 桌面学习助手，用于学习心理学与经济学知识点，并维护 Obsidian Vault 中的 Markdown 笔记。应用提供每日学习、笔记浏览、学习地图和设置页面；核心模块包含 AI Provider、三版本笔记管理、学习地图解析、轻量本地检索与归档流程。

当前版本：**1.0.0**。项目使用 Python 3.13+、PySide6 与 `uv` 管理依赖。

## Windows 桌面版

在 Windows 10/11、已安装 Python 3.13+ 和 `uv` 的开发机上，从仓库根目录运行：

```powershell
uv sync
./tools/build_windows.ps1
```

脚本会清除仓库内旧的 `build/` 与 `dist/`，创建 PyInstaller onedir 包，并启动 EXE 做存活检查。成功时输出 EXE 的完整路径和文件大小。双击以下文件启动应用：

```text
dist/daily-knowledge-learning/daily-knowledge-learning.exe
```

发布或拷贝时必须保留整个 `dist/daily-knowledge-learning/` 文件夹，不能只复制 EXE。构建输出不提交到 Git。Windows 构建基线和运行限制见 [发布说明](docs/releases/1.0.0.md)。

## 开发与测试

```powershell
uv sync
uv run pytest
uv run python -m daily_knowledge_learning.ui
```

CLI 可对 Vault 执行只读扫描：

```powershell
uv run daily-learning .\tests\fixtures\vault_minimal
```

## 项目资料

- [项目清单](docs/项目清单.md)：范围、已具备能力和待办事项
- [架构说明](docs/architecture.md)：应用分层、数据流和构建入口
- [安全说明](docs/security.md)：Vault、凭据和本地构建产物的边界
- [核心模块说明](docs/core-modules.md)：模块接口和错误处理
- [更新日志](CHANGELOG.md)
- [1.0.0 发布说明](docs/releases/1.0.0.md)
- [UI 技术选择](docs/ui-tech-choice.md)

自动化测试只使用 `tmp_path` 和仓库内的最小 fixture。真实 API 密钥、个人笔记和真实 Vault 内容不得提交到 Git。
