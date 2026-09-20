# 文件：harness/observability/metrics.py
class HarnessMetrics:
    """Phase 9 当前完整 Metric（指标）集合。"""

    def __init__(
        self,
        observability,
    ) -> None:
        meter = observability.meter

        # Agent Run
        self.agent_runs = meter.create_counter(
            "harness.agent.run.count",
            description="Agent Run 总数",
        )
        self.agent_errors = meter.create_counter(
            "harness.agent.run.errors",
            description="Agent Run 错误总数",
        )
        self.agent_duration = meter.create_histogram(
            "harness.agent.run.duration",
            unit="s",
            description="Agent Run 耗时",
        )

        # Model
        self.model_input_tokens = meter.create_counter(
            "harness.model.input_tokens",
            description="Model Input Token 总数",
        )
        self.model_output_tokens = meter.create_counter(
            "harness.model.output_tokens",
            description="Model Output Token 总数",
        )
        self.model_duration = meter.create_histogram(
            "harness.model.duration",
            unit="s",
            description="Model Call 耗时",
        )

        # Tool Runtime
        self.tool_calls = meter.create_counter(
            "harness.tool.calls",
            description="Tool Call 总数",
        )
        self.tool_errors = meter.create_counter(
            "harness.tool.errors",
            description="Tool Error 总数",
        )
        self.tool_duration = meter.create_histogram(
            "harness.tool.duration",
            unit="s",
            description="Tool Call 耗时",
        )

        # Retrieval
        self.retrieval_duration = meter.create_histogram(
            "harness.retrieval.duration",
            unit="s",
            description="Retrieval 耗时",
        )
        self.retrieval_result_count = meter.create_histogram(
            "harness.retrieval.result_count",
            unit="{result}",
            description="Retrieval 返回结果数量",
        )

        # MCP
        self.mcp_duration = meter.create_histogram(
            "harness.mcp.duration",
            unit="s",
            description="MCP Remote Call 耗时",
        )
        self.mcp_calls = meter.create_counter(
            "harness.mcp.calls",
            description="MCP Remote Call 总数",
        )
        self.mcp_errors = meter.create_counter(
            "harness.mcp.errors",
            description="MCP Remote Call 错误总数",
        )

        # Evaluation
        self.eval_cases = meter.create_counter(
            "harness.evaluation.cases",
            description="Evaluation Case 执行总数",
        )
        self.eval_case_duration = meter.create_histogram(
            "harness.evaluation.case.duration",
            unit="s",
            description="单个 Evaluation Case 耗时",
        )

        # Phase 9 Security
        self.security_decisions = meter.create_counter(
            "harness.security.decisions",
            description="Security Decision 总数",
        )
        self.security_blocks = meter.create_counter(
            "harness.security.blocks",
            description="Security Block / Approval Required 总数",
        )
        self.security_redactions = meter.create_counter(
            "harness.security.redactions",
            description="Security Redaction 总数",
        )

        # Phase 11 Commercial Platform
        self.platform_auth_failures = meter.create_counter(
            "harness.platform.auth.failures",
            description="Platform API authentication failure 总数",
        )
        self.platform_quota_denials = meter.create_counter(
            "harness.platform.quota.denials",
            description="Platform quota denial 总数",
        )
        self.platform_usage_events = meter.create_counter(
            "harness.platform.usage.events",
            description="Platform usage event 写入总数",
        )
