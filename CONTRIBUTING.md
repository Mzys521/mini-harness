# 贡献指南

感谢你对 mini-harness 的关注！本文档说明开发环境搭建、提交规范与协作流程，帮助你的贡献顺利合入。

## 开发环境

- Python 3.12+
- 安装依赖：

```bash
pip install openai pydantic python-dotenv pytest pytest-asyncio
```

- 参考 README 的「快速开始」配置 `.env`
- 运行测试，确认环境就绪：

```bash
python -m pytest test -q
```

## 工作流程

1. Fork 本仓库并克隆到本地
2. 从 `master` 拉出功能分支，命名建议：`feat/phase5-rag-loader`、`fix/tool-timeout`、`docs/update-readme` 等
3. 开发完成后，确保测试全部通过
4. 使用 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/) 规范提交：

| 前缀 | 用途 |
| --- | --- |
| `feat:` | 新功能 |
| `fix:` | 修复缺陷 |
| `docs:` | 文档变更 |
| `test:` | 测试相关 |
| `refactor:` | 重构（不改变外部行为） |
| `chore:` | 构建 / 工具链 / 杂项 |

5. 提交 Pull Request，在描述中说明：变更动机、实现方案、测试方式

## 阶段开发约定

项目按 11 个阶段推进（见 README 路线图）。每完成一个阶段，请同步：

1. 新增或更新对应模块的测试，保持 `pytest` 全量通过
2. 更新 README 的「路线图」与「已实现能力」
3. 在 [CHANGELOG.md](CHANGELOG.md) 的 `[Unreleased]` 中记录变更
4. 里程碑达成后打版本标签：`git tag -a v0.x.0 -m "v0.x.0 — Phase x 完成"`

## 代码风格

- 遵循仓库现有风格：类型标注、frozen dataclass、简洁中文注释
- 新工具请放入 `app_tools/` 或对应阶段模块，并补充参数模型（Pydantic）
- 测试放在 `test/` 下，文件命名 `test_*.py`
- 不要提交 `.env`、`del/` 及任何缓存文件（已在 `.gitignore` 中排除）

## 反馈问题

- 通过 GitHub Issues 提交缺陷报告或功能建议
- 缺陷报告建议包含：复现步骤、期望行为、实际行为、运行环境（Python 版本 / 操作系统）
