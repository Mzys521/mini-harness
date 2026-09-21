# 文件：harness/security/config.py
from dataclasses import dataclass, field

@dataclass(frozen=True)
class SecurityConfig:
    """Phase 9 确定性 Security Policy（安全策略）配置。"""

    max_input_chars: int = 16_000
    max_output_chars: int = 32_000
    max_tool_calls_per_run: int | None = None

    # Prompt Injection Signal 默认只审计，避免关键词误杀正常请求。
    detect_prompt_injection_signals: bool = True
    block_prompt_injection_signals: bool = False

    # 所有 Side-effect Tool（副作用工具）默认需要明确 Approval。
    approval_required_for_side_effects: bool = True

    # 部署时可以彻底禁用某些 Tool。
    disabled_tools: frozenset[str] = field(
        default_factory=frozenset
    )

    # 教学/开发阶段 Audit Sink；生产环境应换集中式审计存储。
    audit_path: str = "data/security_audit.jsonl"