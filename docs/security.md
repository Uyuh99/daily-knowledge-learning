# 安全与数据完整性

## Vault

Vault 路径由用户在设置中指定。扫描与索引功能只读取 Markdown；笔记创建和更新通过业务模块执行，避免以 UI 代码直接覆盖文件。文件写入采用原子替换或冲突检测，并保留未修改的 YAML frontmatter 内容。归档和写入功能仍应由用户审阅其目标路径和内容。

自动化测试只访问仓库内的 `tests/fixtures/` 或临时目录。构建和启动检查不会把真实 Vault 复制进发布目录。

## 凭据和配置

Vault 路径、Provider 选择和模型等非秘密配置保存在用户配置目录，可通过 `DAILY_KNOWLEDGE_LEARNING_CONFIG` 指定其他位置。OpenAI 与 Anthropic API 密钥通过 `keyring` 交由 Windows Credential Manager 等系统密钥库保存，不写入普通配置 JSON。不要把 API 密钥、配置文件或个人笔记提交到 Git。

## 构建产物

`dist/`、`build/`、虚拟环境、`.env` 和秘密文件均由 `.gitignore` 排除。构建脚本仅删除当前仓库下的 `dist/` 和 `build/`，并输出本地 onedir 目录；EXE 需要与旁边的依赖文件一起分发。1.0.0 构建未配置代码签名或自动更新。
