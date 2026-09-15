# 更新日志

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 计划中

- Phase 6（MCP）：接入 Model Context Protocol，复用外部工具生态

## [0.5.0] - 2026-09-15

### 新增

- **P5 RAG 检索模块（`harness/retrieval`）**：文档加载（`loaders`）、字符切分含重叠与稳定 ID（`chunkers`）、嵌入提供方（`QwenEmbeddingProvider` / `OpenAIEmbeddingProvider`）、向量存储（`ChromaVectorStore` 持久化 + `InMemoryVectorStore`，均实现 `VectorStore` 协议）、摄取服务（`IngestionService`）、稠密检索（`DenseRetriever`）、检索流水线（候选召回 → 重排 → 最终结果）、证据投影（`RetrievalContextProjector`）、相似度与指标（`cosine_similarity` / `recall_at_k`）
- **知识检索工具**：`app_tools/knowledge.py` 提供 `search_knowledge_base`（支持多租户 where 过滤，返回带来源/章节/分数的证据文本）
- **上下文注入**：`ContextBuilder.build` 新增 `retrieved_context` 参数，向系统消息注入 `[RETRIEVED CONTEXT]` 段（优先级 75）
- **脚本**：`scripts/ingest_knowledge.py`（加载与切分演示）、`scripts/search_knowledge.py`（端到端检索演示）

### 变更

- 测试目录 `test/` 重命名为 `tests/`，新增 `test_chunking` / `test_retrieval` / `test_fakes`，共 18 个用例全部通过
- `.gitignore` 新增排除向量库数据目录 `data/`
- `main.py` 注册知识检索工具

## [0.4.0] - 2026-09-14

### 新增

- **P1 Harness Kernel**：`AgentRunner` 主循环、`ToolCall`/`ModelResult` 数据模型、`DeepSeekProvider`（chat 接口）与 `OpenAIProvider`（responses 接口）
- **P2 Production Tool Runtime**：工具注册表、执行器（参数校验 → 权限检查 → 中间件 → 超时/重试 → 统一结果）、中间件协议与日志实现、示例工具（计算器 / sleep / delete_file）
- **P3 Context Engineering**：TokenBudget 预算、ContextPolicy 策略、ContextBuilder 组装与裁剪、滑动窗口、WorkingState 注入、超长工具结果截断
- **P4 State / Session / Persistence**：Run / Step / Checkpoint 状态模型与状态机、SQLite schema、Repository 仓储、UnitOfWork 事务边界
- 测试：13 个 pytest 用例（工具运行时 / 上下文 / 持久化）
- 工程：`.gitignore`（排除 `.env`、`del/` 与缓存目录）

### 文档

- 标准化 README：徽章、目录导航、11 阶段路线图、贡献 / 更新日志 / 许可证章节
- 新增 MIT [LICENSE](LICENSE)、[CONTRIBUTING.md](CONTRIBUTING.md)、本更新日志
