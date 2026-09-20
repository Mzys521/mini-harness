# 文件：tests/fakes_security.py
from contextlib import (
    contextmanager,
)

class FakeSpan:
    def __init__(self) -> None:
        self.attributes = {}
        self.errors = []

    def set_attribute(
        self,
        key,
        value,
    ) -> None:
        self.attributes[key] = value

    def add_event(
        self,
        name,
        attributes=None,
    ) -> None:
        return None

    def record_exception(
        self,
        exc,
    ) -> None:
        self.errors.append(
            exc
        )

    def set_error(
        self,
        description,
    ) -> None:
        self.errors.append(
            description
        )

class FakeObservability:
    def __init__(self) -> None:
        self.span_names = []

    @contextmanager
    def span(
        self,
        name,
        attributes=None,
    ):
        self.span_names.append(
            name
        )
        yield FakeSpan()

class FakeInstrument:
    def __init__(self) -> None:
        self.values = []

    def add(
        self,
        value,
        attributes=None,
    ) -> None:
        self.values.append(
            (value, attributes)
        )

    def record(
        self,
        value,
        attributes=None,
    ) -> None:
        self.values.append(
            (value, attributes)
        )

class FakeSecurityMetrics:
    def __init__(self) -> None:
        # ToolExecutor 会使用这些 Metric。
        self.tool_calls = FakeInstrument()
        self.tool_errors = FakeInstrument()
        self.tool_duration = FakeInstrument()

        # SecurityService 会使用这些 Metric。
        self.security_decisions = FakeInstrument()
        self.security_blocks = FakeInstrument()
        self.security_redactions = FakeInstrument()

def build_fake_security(
    *,
    config,
):
    from harness.security import (
        DefaultToolPolicy,
        InMemoryApprovalStore,
        InMemoryRunBudgetStore,
        InputLengthGuard,
        NullAuditSink,
        OutputLengthGuard,
        PromptInjectionSignalGuard,
        SecretOutputGuard,
        SecurityService,
    )

    observability = FakeObservability()
    metrics = FakeSecurityMetrics()
    approval_store = (
        InMemoryApprovalStore()
    )
    budget_store = (
        InMemoryRunBudgetStore()
    )

    security = SecurityService(
        input_guards=[
            InputLengthGuard(
                config.max_input_chars
            ),
            PromptInjectionSignalGuard(
                block_on_signal=(
                    config.block_prompt_injection_signals
                )
            ),
        ],
        output_guards=[
            SecretOutputGuard(),
            OutputLengthGuard(
                config.max_output_chars
            ),
        ],
        tool_policy=DefaultToolPolicy(
            config=config,
            approval_store=approval_store,
            budget_store=budget_store,
        ),
        audit_sink=NullAuditSink(),
        observability=observability,
        metrics=metrics,
    )

    return (
        security,
        approval_store,
        observability,
        metrics,
    )