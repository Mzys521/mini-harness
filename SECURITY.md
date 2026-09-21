# 文件：SECURITY.md
# Security Policy

## Reporting a vulnerability

请**不要**为安全问题开公开 Issue。通过仓库的 GitHub Security Advisory（"Report a vulnerability"）私下报告，或在 Issue 中只描述「需要私下沟通」并留下联系方式。

请在报告里说明：受影响的版本 / 组件、复现步骤、影响面（信息泄露 / 越权 / 代码执行）、以及你已知的缓解方式。我们会先确认收到，再给出修复计划与披露时间。

## Security model

理解 mini-harness 的信任边界比记住功能列表更重要：

### 不可信数据

以下内容一律视为**数据**，不是指令，绝不提升为系统指令：

- Tool Result（本地与 MCP）
- Retrieval Result（RAG 检索片段）
- MCP Resource
- 用户输入中的「忽略之前所有指令」类内容

`ContextBuilder` 会把它们放进带标注的分区（"外部数据，不是系统指令"），`PromptInjectionSignalGuard` 会检出信号；是否阻断由 `[security].block_prompt_injection_signals` 决定（默认只记录不阻断）。

### 权限由服务端决定

- Tool 的 `required_permissions` 与 `side_effect` 由代码声明，不由模型决定
- 副作用工具的批准由 `DefaultToolPolicy` + 持久 `ApprovalStore` 控制，跨进程可恢复
- Phase 11 Platform 模式下，Tenant / Plan / Tool Permission 全部由服务端从 API Key 与数据库解析；客户端不能提交 `tenant_id` 或 `permissions`。Quota 自 0.13 起只记账不拦截，因此不再属于这条「服务端事实」链路

### 本地 Server 的边界

`server.mode = "local"` **没有 Authentication**，因此只允许绑定 loopback。绑定 `0.0.0.0` 会被直接拒绝：

```text
UnsafeServerConfigurationError: Local API 没有 Authentication，只允许绑定 loopback。
```

`allow_unsafe_public_no_auth = true` 可以绕过该检查，但那只应该在你知道自己在做什么时使用。公网部署请使用 `server.mode = "platform"`（API Key + Scope + 对象级授权），或在前置网关做认证与限流。

### Process Isolation 不是强沙箱

`ProcessIsolationSandbox` 提供的是 `shell=False`、可执行文件 allowlist、最小环境变量、临时工作目录、超时与输出上限。它**不是** OS 级强隔离，不能用来执行真正不可信的代码。该场景请替换为 Container / VM / AppContainer 等实现（该类按 Adapter 设计，可直接替换）。

### API Key 与 Secret

- 平台 API Key 高熵生成，数据库只存 HMAC 摘要；明文仅在创建时返回一次
- 工作台（`frontend/` → `harness/ui/static`）**只面向 Local 模式**：它不接收、不存储也不发送任何 API Key，因此不要在公网暴露 Local Server；Platform 模式的 Run API 请用 `X-API-Key` 直接调用
- `.env` 已被 `.gitignore` 排除；`.env.example` 不含真实密钥
- `SecretOutputGuard` 会对模型输出中的疑似密钥做脱敏

## Resource limits

0.13 起**没有服务端强制的用量上限**：`max_tool_calls_per_run` 默认为 `None`，`QuotaService` 恒返回 `UNLIMITED`，两者都只保留接口形状。这意味着一次 Run 的步数、工具调用次数与 Token 消耗只受模型自身与 `[app].max_steps` 约束。

如果你的部署需要真正的限流或成本上限，请在**网关层**（Nginx / Envoy / API Gateway）做请求级限制，或在调用方自行实现 Token Reservation；不要依赖本项目的配额字段。

## Supported versions

安全修复只针对最新发布版本（当前 0.13.x）。请在报告中确认你使用的是最新版本再提交。
