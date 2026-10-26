# 架构说明

## 运行结构

- `src/daily_knowledge_learning/ui/` 使用 PySide6 构建桌面界面，`tools/ui_entry.py` 是 PyInstaller 的顶层入口。
- UI 调用业务模块，不承担 Markdown 或 YAML 的底层写入实现。
- `note_manager.py` 和 `file_writer.py` 管理主题文件与三版本笔记；`yaml_utils.py` 保留未涉及的 frontmatter 字段及注释。
- `map_parser.py`、`topic_selector.py` 和 `retrieval.py` 负责学习地图解析、主题选择和本地检索。
- `stats_service.py` 只读扫描主题记录与复习计划，计算完成率、连续学习天数、近 7 天活动和分学问进度；统计页不维护第二份状态。
- `vault_qa.py` 用本地 Markdown 检索结果构造带来源的问答上下文；界面在后台线程调用已配置的 Provider，并提供来源回链。
- `ai_provider.py` 封装 mock、Anthropic 与 OpenAI 兼容 Provider；OpenAI、DeepSeek、硅基流动、OpenRouter 和自定义网关共用 Chat Completions 适配器。`config.py` 保存供应商、模型和 API 基础地址，密钥按供应商写入系统密钥库。
- `study_service.py` 在学习工作流中实际组装分角色提示词、学科安全约束和检索笔记上下文，并检查参考版章节。`prompt_builder.py` 另含更严格的提示词和反馈结构校验工具，目前尚未接入该工作流。
- `archive.py` 与 `study_service.py` 提供学习归档及其业务流程。

## 启动和打包

开发模式通过 `uv run python -m daily_knowledge_learning.ui` 启动。Windows 发布包使用 `tools/build_windows.ps1` 调用 PyInstaller 的 onedir 模式。输出位于 `dist/daily-knowledge-learning/`，运行时需保留整个目录；打包脚本会启动 EXE 并验证进程能存活指定时间。

应用版本从 `daily_knowledge_learning.__version__` 读取，包元数据版本在 `pyproject.toml` 中维护，两者需要保持一致。构建包不包含真实 Vault、用户配置或 API 密钥。

## 验证边界

单元测试使用临时目录和仓库 fixture，不读写个人 Vault。EXE 存活检查验证冻结后的程序能启动并保持运行，不替代完整的人工 UI、网络 Provider 或真实 Vault 验收。
