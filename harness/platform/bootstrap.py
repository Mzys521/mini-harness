# 文件：harness/platform/bootstrap.py
from harness.platform.models import MeterRate, Plan, PlanLimits, UsageMetric


def default_plans() -> tuple[Plan, ...]:
    """教学基线套餐；真实商业定价必须配置化并由业务团队版本化。"""
    starter = Plan(
        id="starter_v1",
        name="Starter",
        limits=PlanLimits(
            max_concurrent_runs=2,
            max_runs_per_day=50,
            max_input_tokens_per_month=500_000,
            max_output_tokens_per_month=250_000,
            max_tool_calls_per_month=2_000,
        ),
        tool_permissions=frozenset({
            "knowledge.search",
            "mcp.demo.multiply",
            "mcp.demo.get_order_status",
        }),
        rates=(
            MeterRate(
                metric=UsageMetric.RUN_SUBMITTED,
                unit_size=1,
                price_microusd=0,
                included_units=50,
            ),
            MeterRate(
                metric=UsageMetric.INPUT_TOKENS,
                unit_size=1_000,
                price_microusd=1_000,
                included_units=500_000,
            ),
            MeterRate(
                metric=UsageMetric.OUTPUT_TOKENS,
                unit_size=1_000,
                price_microusd=4_000,
                included_units=250_000,
            ),
            MeterRate(
                metric=UsageMetric.TOOL_CALLS,
                unit_size=1,
                price_microusd=100,
                included_units=2_000,
            ),
        ),
    )

    pro = Plan(
        id="pro_v1",
        name="Pro",
        limits=PlanLimits(
            max_concurrent_runs=8,
            max_runs_per_day=1_000,
            max_input_tokens_per_month=10_000_000,
            max_output_tokens_per_month=5_000_000,
            max_tool_calls_per_month=100_000,
        ),
        tool_permissions=frozenset({
            "knowledge.search",
            "note.create",
            "mcp.demo.multiply",
            "mcp.demo.get_order_status",
        }),
        rates=(
            MeterRate(
                metric=UsageMetric.INPUT_TOKENS,
                unit_size=1_000,
                price_microusd=800,
                included_units=10_000_000,
            ),
            MeterRate(
                metric=UsageMetric.OUTPUT_TOKENS,
                unit_size=1_000,
                price_microusd=3_000,
                included_units=5_000_000,
            ),
            MeterRate(
                metric=UsageMetric.TOOL_CALLS,
                unit_size=1,
                price_microusd=50,
                included_units=100_000,
            ),
        ),
    )

    operator = Plan(
        id="operator_v1",
        name="Platform Operator",
        limits=PlanLimits(
            max_concurrent_runs=1,
            max_runs_per_day=1,
            max_input_tokens_per_month=1,
            max_output_tokens_per_month=1,
            max_tool_calls_per_month=1,
        ),
        tool_permissions=frozenset(),
        rates=(),
    )
    return starter, pro, operator


def seed_default_plans(store) -> None:
    for plan in default_plans():
        store.ensure_plan(plan)
