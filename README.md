# mini-harness

> 一个分阶段演进的迷你 LLM Agent 框架：工具运行时、上下文工程、状态持久化

![Python](https://img.shields.io/badge/Python-3.12%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Phase%205%20%28RAG%29-orange)

## 目录

- [简介](#简介)
- [已实现能力](#已实现能力phase-14)
- [路线图](#路线图)
- [快速开始](#快速开始)
- [运行流程](#运行流程)
- [项目结构](#项目结构)
- [设计要点](#设计要点)
- [开发状态](#开发状态)
- [贡献](#贡献)
- [更新日志](#更新日志)
- [许可证](#许可证)

## 简介

mini-harness 是一个分阶段演进的 LLM Agent 框架（Harness），目标是从内核出发，逐步补全一个生产级 Agent 系统所需的全部基础设施。项目按 11 个阶段推进，**当前处于 Phase 5（RAG）开发阶段**。

已完成的 Phase 1–4 把「模型会调用工具」这件事拆解成三个可独立演进的子系统：

- **工具运行时**：工具注册与 Schema 导出、Pydantic 参数校验、权限检查、超时控制、重试策略与中间件（如日志）
- **上下文工程**：Token 预算管理、基于策略的滑动窗口裁剪、工作状态（WorkingState）注入、超长工具结果截断
- **状态与持久化**：Run / Step / Checkpoint 状态模型、SQLite 仓储（Repository）+ 工作单元（UnitOfWork）事务、检查点快照支持崩溃恢复

模型层通过 Provider 适配，目前支持 DeepSeek（chat 接口）与 OpenAI（responses 接口），可平滑替换。

## 已实现能力（Phase 1–4）

| 模块 | 阶段 | 能力 |
| --- | --- | --- |
| `harness/runner.py` | P1 | `AgentRunner` 主循环：生成 → 工具执行 → 结果回传，直至无调用或达到步数上限 |
| `harness/providers` | P1 | `DeepSeekProvider`（chat 接口，本地历史续接）、`OpenAIProvider`（responses 接口） |
| `harness/tools` | P2 | 注册表、执行器（校验 → 权限 → 中间件 → 超时/重试 → 统一结果）、中间件协议与日志实现 |
| `harness/context` | P3 | TokenBudget 预算、ContextPolicy 策略、ContextBuilder 组装与裁剪、滑动窗口 |
| `harness/state` | P4 | RunState/StepState 状态机、Checkpoint 快照、ID 生成 |
| `harness/persistence` | P4 | SQLite 建表脚本、Repository 仓储、UnitOfWork 事务边界 |
| `app_tools` | P2 | 示例工具：加减乘除、异步 sleep、删除文件（权限/副作用演示） |

## 路线图

| # | 阶段 | 状态 | 核心内容 |
| --- | --- | --- | --- |
| 1 | Harness Kernel | 已完成 | Agent 主循环、消息与结果模型、模型 Provider 抽象 |
| 2 | Production Tool Runtime | 已完成 | 工具注册 / 校验 / 权限 / 超时 / 重试 / 中间件 / 统一结果 |
| 3 | Context Engineering | 已完成 | Token 预算、上下文策略、滑动窗口、WorkingState 注入与裁剪 |
| 4 | State / Session / Persistence | 已完成 | Run / Step / Checkpoint 状态机、SQLite 仓储、UnitOfWork 事务 |
| 5 | **RAG** | **开发中** | 文档加载与切分、向量化与索引、检索结果注入上下文 |
| 6 | MCP | 计划中 | 接入 Model Context Protocol，复用外部工具生态 |
| 7 | Observability | 计划中 | 调用链追踪、指标采集、结构化日志 |
| 8 | Evaluation | 计划中 | 评测数据集、自动化评分、回归基线 |
| 9 | Security | 计划中 | 沙箱执行、权限模型增强、审计与脱敏 |
| 10 | Durable Execution | 计划中 | 崩溃恢复、断点续跑、长任务编排 |
| 11 | Commercial Platform | 计划中 | 多租户、配额与计费、管理后台 |

## 快速开始

### 环境要求

- Python 3.12+
- 运行依赖：`openai`、`pydantic`、`python-dotenv`
- 测试依赖：`pytest`、`pytest-asyncio`

### 安装

```bash
pip install openai pydantic python-dotenv pytest pytest-asyncio
```

### 配置 .env

```env
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_API_KEY=sk-xxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

### 运行示例

```bash
python main.py
```

示例会注册计算器等工具，向模型发起一道多步计算题，由 Agent 自主完成多轮工具调用，并通过日志中间件打印每次调用的耗时与状态。

### 运行测试

```bash
python -m pytest test -q
```

## 运行流程

```
用户输入
   │
   ▼
AgentRunner.run ──► 模型 generate(工具 schema)
   │                        │
   │              无工具调用 ──► 返回最终文本
   │                        │
   │              有工具调用
   │                        ▼
   │              ToolExecutor.execute ──► 查找→校验→权限→中间件→超时/重试
   │                        │
   └──── 工具结果回传 ◄──────┘   (循环直至无调用或达到 max_steps)
```

## 项目结构

以下为 Phase 1–4 已落地的结构，规划中的子模块将随路线图逐步新增至 `harness/` 下：

```
mini-harness/
├── main.py                    # 示例入口：注册工具、组装运行器并跑一轮
├── harness/
│   ├── models.py              # ToolCall / ModelResult
│   ├── runner.py              # AgentRunner 主循环
│   ├── tools/                 # 工具运行时（定义/注册/执行/中间件/结果/错误）
│   ├── context/               # 上下文工程（预算/策略/构建器/来源）
│   ├── state/                 # 状态模型与状态机（Run/Step/Checkpoint）
│   ├── persistence/           # SQLite 仓储与 UnitOfWork
│   ├── providers/             # DeepSeek / OpenAI 适配
│   ├── rag/                   # [规划] Phase 5：文档切分 / 向量化 / 检索
│   ├── mcp/                   # [规划] Phase 6：MCP 协议接入
│   ├── observability/         # [规划] Phase 7：追踪 / 指标 / 结构化日志
│   ├── evaluation/            # [规划] Phase 8：评测数据集与自动评分
│   └── security/              # [规划] Phase 9：沙箱 / 审计 / 脱敏
├── app_tools/                 # 示例工具
├── test/                      # pytest 测试（工具运行时 / 上下文 / 持久化）
└── del/                       # 旧版实现（仅供对照，不入库）
```

> 各子系统通过 `harness` 内部接口解耦，新增模块不影响已有代码；`[规划]` 目录随对应阶段落地。

## 设计要点

- **统一结果对象**：所有工具失败都以 `ToolResult` 状态码返回（不向主循环抛异常），便于回传给模型自行纠错
- **同步/异步 handler 兼容**：协程直接 await，同步函数放入线程池执行，并统一受超时约束
- **上下文可裁剪**：`required` 标记的消息（系统指令、当前输入）永不被裁剪，其余按预算从旧到新丢弃并记录到 `dropped_sections`
- **事务边界清晰**：`UnitOfWork` 上下文管理器统一提交/回滚，异常时自动回滚

## 开发状态

项目处于活跃开发中，接口与目录结构可能随阶段推进调整。各阶段完成后会同步更新本文档的路线图与能力清单（详见 [CHANGELOG.md](CHANGELOG.md)）。

- `.env` 与 `del/` 已加入 `.gitignore`，不会提交到仓库

## 贡献

欢迎参与共建！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解开发环境、提交规范与 PR 流程。

## 更新日志

版本变更记录见 [CHANGELOG.md](CHANGELOG.md)。

## 许可证

本项目基于 [MIT License](LICENSE) 开源。
