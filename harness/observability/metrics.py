class HarnessMetrics:

    def __init__(self , observability) -> None:
        meter = observability.meter
        self.agent_runs = meter.create_counter("harness.agent.run.count")
        self.agent_errors = meter.create_counter("harness.agent.run.errors")
        self.tool_calls = meter.create_counter("harness.tool.calls")
        self.tool_errors = meter.create_counter("harness.tool.errors")
        self.mcp_calls = meter.create_counter("harness.mcp.calls")
        self.mcp_errors = meter.create_counter("harness.mcp.errors")
        self.model_input_tokens = meter.create_counter("harness.model.input_tokens")
        self.model_output_tokens = meter.create_counter("harness.model.output_tokens")
        self.agent_duration = meter.create_histogram("harness.agent.run.duration", unit="s")
        self.model_duration = meter.create_histogram("harness.model.duration", unit="s")
        self.tool_duration = meter.create_histogram("harness.tool.duration", unit="s")
        self.retrieval_duration = meter.create_histogram("harness.retrieval.duration", unit="s")
        self.retrieval_result_count = meter.create_histogram("harness.retrieval.result_count", unit="{result}")
        self.mcp_duration = meter.create_histogram("harness.mcp.duration", unit="s")
