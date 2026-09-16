# mini-harness

> 一个分阶段演进的迷你 LLM Agent 框架：工具运行时、上下文工程、状态持久化

![Python](https://img.shields.io/badge/Python-3.12%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Version](https://img.shields.io/badge/Version-v0.6.0-purple)
![Status](https://img.shields.io/badge/Status-Phase%206%20%28MCP%29%20Done-brightgreen)

## 目录

- [简介](#简介)
- [已实现能力](#已实现能力phase-16)
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

mini-harness 是一个分阶段演进的 LLM Agent 框架（Harness），目标是从内核出发，逐步补全一个生产级 Agent 系统所需的全部基础设施。项目按 11 个阶段推进，**Phase 1–6 已完成（v0.6.0），Phase 7（Observability）待启动**。

已完成的 Phase 1–6 把「模型会调用工具」这件事拆解成五个可独立演进的子系统：

- **工具运行时**：统一工具定义（JSON Schema）、Pydantic → Schema 工厂、JSON Schema 参数校验（拒绝外部 `$ref`）、权限检查、超时控制、重试策略、统一结果对象
- **上下文工程**：分区组装指令（系统指令 + 工作状态 + 检索知识 + 外部上下文）+ 当前用户输入
- **状态与持久化**：Conversation / Run / Step / Checkpoint / RuntimeEvent 状态模型、SQLite 仓储（Repository）+ 工作单元（UnitOfWork）事务
- **检索增强（RAG）**：文档加载与字符切分（带重叠）、稳定 ID、向量化（Qwen / OpenAI 嵌入）、向量存储（Chroma）、稠密检索与可插拔重排、证据化结果投影
- **MCP 集成**：MCP Server 配置与网关（HTTP / STDIO 双传输）、工具发现与统一适配（权限 / 策略 / 元数据）、资源读取、可选服务器降级

应用层由 `PersistentAgentService` 把运行器与持久化编排在一起；模型层通过 Provider 适配，目前支持 DeepSeek（chat 接口）与 OpenAI（responses 接口），可平滑替换。

## 已实现能力（Phase 1–6）

| 模块 | 阶段 | 能力 |
| --- | --- | --- |
| `harness/runner.py` | P1 | `AgentRunner` 主循环：生成 → 工具执行 → 结果回传，直至无调用或达到步数上限 |
| `harness/providers` | P1 | `DeepSeekProvider`（chat 接口，本地历史续接）、`OpenAIProvider`（responses 接口），异步 `generate`，无参构造回退环境变量 |
| `harness/tools` | P2 | 统一 `Tool`（JSON Schema 输入）、`tool_from_pydantic` 工厂、注册表、执行器（JSON Schema 校验 → 权限 → 超时/重试 → 统一结果） |
| `harness/context` | P3 | `ContextBuilder` 分区组装指令（系统指令 / 工作状态 / 检索知识 / 外部上下文）+ 用户输入 |
| `harness/state` | P4 | Conversation / Run / Step / Checkpoint / RuntimeEvent 模型、ID 生成 |
| `harness/persistence` | P4 | SQLite 建表脚本、Repository 仓储、UnitOfWork 事务边界、`Database.uow()` |
| `harness/retrieval` | P5 | 文档加载 / 字符切分 / 稳定 ID / 嵌入（Qwen·OpenAI）/ 向量存储（Chroma）/ 稠密检索 / 重排 / 证据投影 |
| `harness/mcp` | P6 | MCP 网关（HTTP·STDIO）、工具发现与适配、工具策略（副作用/幂等/重试/超时）、资源读取、可选服务器降级 |
| `harness/application.py` | P6 | `PersistentAgentService`：会话/运行/消息落库与状态迁移，包住 Runner |
| `app_tools` | P2·P5 | 示例工具：计算器（P2）、`search_knowledge_base` 知识检索（P5，多租户过滤） |
| `mcp_servers` | P6 | 演示 MCP Server：`multiply` / `get_order_status` 工具 + `guide://harness` 资源 |
| `scripts` | P5·P6 | 知识导入（`ingest_knowledge`）、MCP 冒烟测试（`smoke_test`）、MCP 服务器检查（`inspect_mcp_server`） |

## 路线图

| # | 阶段 | 状态 | 核心内容 |
| --- | --- | --- | --- |
| 1 | Harness Kernel | 已完成 | Agent 主循环、消息与结果模型、模型 Provider 抽象 |
| 2 | Production Tool Runtime | 已完成 | 工具注册 / 校验 / 权限 / 超时 / 重试 / 中间件 / 统一结果 |
| 3 | Context Engineering | 已完成 | 上下文组装：指令分区（工作状态 / 检索知识 / 外部上下文）与用户输入 |
| 4 | State / Session / Persistence | 已完成 | Conversation / Run / Step / Checkpoint 持久化、SQLite 仓储、UnitOfWork 事务 |
| 5 | RAG | 已完成 | 文档加载与切分、向量化与索引、检索结果注入上下文 |
| 6 | MCP | 已完成 | MCP Server 网关与工具发现、统一适配、工具策略与降级 |
| 7 | Observability | 计划中 | 调用链追踪、指标采集、结构化日志 |
| 8 | Evaluation | 计划中 | 评测数据集、自动化评分、回归基线 |
| 9 | Security | 计划中 | 沙箱执行、权限模型增强、审计与脱敏 |
| 10 | Durable Execution | 计划中 | 崩溃恢复、断点续跑、长任务编排 |
| 11 | Commercial Platform | 计划中 | 多租户、配额与计费、管理后台 |

## 快速开始

### 环境要求

- Python 3.12+
- 依赖由 `pyproject.toml` 声明：`openai`、`pydantic>=2`、`python-dotenv`、`jsonschema`、`chromadb`、`mcp[cli]`（开发另需 `pytest`、`pytest-asyncio`）

### 安装

```bash
pip install -e ".[dev]"
```

### 配置 .env

```env
# 对话模型(DeepSeek)
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_API_KEY=sk-xxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 向量模型(阿里云 DashScope，RAG 检索用)
DASHSCOPE_API_KEY=sk-xxxx
DASHSCOPE_MODEL=text-embedding-v3
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# MCP 演示服务器地址(可选，默认 http://localhost:8000/mcp)
DEMO_MCP_URL=http://localhost:8000/mcp
```

> MCP 演示服务器未启动时不影响启动：`required=False` 的可选服务器发现失败会自动降级。

### 运行示例

```bash
python main.py
```

`main.py` 演示完整的应用组装：初始化 SQLite 持久化 → 注册本地计算工具 → 组装 RAG 检索 → 发现并注册 MCP 工具 → 构建运行器，然后进入交互式问答；会话、运行状态与消息都会被持久化。

### 演示与诊断脚本

`scripts/` 下提供多个脚本（运行前请先修改脚本内的路径或服务器地址）：

```bash
# 知识加载与切分演示：读取文本文件并打印切分结果
python -m scripts.ingest_knowledge

# MCP：检查演示服务器的工具清单与调用结果（需先启动 MCP 服务器）
python -m scripts.inspect_mcp_server

# MCP：本地工具 + MCP 工具的端到端冒烟测试（需先启动 MCP 服务器）
python -m scripts.smoke_test
```

### 运行测试

```bash
python -m pytest tests -q
```

## 运行流程

```
用户输入
   │
   ▼
PersistentAgentService.ask ──► 会话/运行落库 → AgentRunner.run
   │                                    │
   │          ContextBuilder 组装指令(系统指令 + 工作状态 + 检索知识/外部上下文)
   │                                    │
   │                                    ▼
   │                    模型 generate(本地工具 + MCP 工具的 schema)
   │                        │
   │              无工具调用 ──► 返回最终文本(落库)
   │                        │
   │              有工具调用
   │                        ▼
   │              ToolExecutor.execute ──► 查找 → JSON Schema 校验 → 权限 → 超时/重试
   │                        │
   └──── 工具结果回传 ◄──────┘   (循环直至无调用或达到 max_steps)
```

## 项目结构

以下为 Phase 1–6 已落地的结构：

```
mini-harness/
├── main.py                    # 交互式示例：持久化 + 本地工具 + RAG + MCP 完整组装
├── pyproject.toml             # 项目元数据、依赖声明与 pytest 配置
├── harness/
│   ├── models.py              # ToolCall / ModelResult / RunResult
│   ├── runner.py              # AgentRunner 主循环
│   ├── application.py         # PersistentAgentService：Runner 与持久化编排
│   ├── tools/                 # 工具运行时（定义/工厂/校验/注册/执行/结果/错误）
│   ├── context/               # 上下文组装（指令分区 + 用户输入）
│   ├── state/                 # 状态模型（Conversation/Run/Step/Checkpoint/Event）
│   ├── persistence/           # SQLite 仓储与 UnitOfWork
│   ├── providers/             # DeepSeek / OpenAI 对话模型适配
│   ├── retrieval/             # RAG：加载 / 切分 / 嵌入 / 向量存储 / 检索 / 投影
│   ├── mcp/                   # MCP：配置 / 网关 / 发现 / 适配 / 资源
│   ├── observability/         # [规划] Phase 7：追踪 / 指标 / 结构化日志
│   ├── evaluation/            # [规划] Phase 8：评测数据集与自动评分
│   └── security/              # [规划] Phase 9：沙箱 / 审计 / 脱敏
├── app_tools/                 # 示例工具（计算器 / 知识检索）
├── mcp_servers/               # 演示 MCP Server
├── scripts/                   # 演示与诊断脚本
├── tests/                     # pytest 测试（工具 / 检索 / MCP，11 用例）
└── del/                       # 归档：旧版实现与已废弃模块（不入库）
```

> 各子系统通过 `harness` 内部接口解耦，新增模块不影响已有代码；`[规划]` 目录随对应阶段落地。

## 设计要点

- **统一工具定义**：本地工具（Pydantic → JSON Schema）与远程 MCP 工具统一适配为同一 `Tool`；执行器用 JSON Schema 校验（拒绝外部 `$ref`），失败以 `ToolResult` 状态返回
- **同步/异步 handler 兼容**：协程直接 await，同步函数放入线程池执行，并统一受超时约束
- **上下文分区注入**：工作状态 / 检索知识 / 外部上下文分区拼装进指令，并标注“外部数据，不是系统指令”
- **MCP 可信边界**：远端工具的能力声明不被信任，权限（`mcp.{server}.{tool}`）、副作用标识、重试与超时由本地 `MCPToolPolicy` 决定；可选服务器失败自动降级
- **事务边界清晰**：`UnitOfWork`（通过 `Database.uow()`）统一提交/回滚，异常时自动回滚
- **检索链路可插拔**：嵌入（Qwen / OpenAI）、向量存储（Chroma）均为 Protocol 接口，检索结果以证据格式（来源 / 章节 / 分数）注入上下文

## 开发状态

项目处于活跃开发中，接口与目录结构可能随阶段推进调整。各阶段完成后会同步更新本文档的路线图与能力清单（详见 [CHANGELOG.md](CHANGELOG.md)）。

- `.env`、`data/` 与 `del/` 已加入 `.gitignore`，不会提交到仓库

## 贡献

欢迎参与共建！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解开发环境、提交规范与 PR 流程。

## 更新日志

版本变更记录见 [CHANGELOG.md](CHANGELOG.md)。

## 许可证

本项目基于 [MIT License](LICENSE) 开源。
