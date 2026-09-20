import re

from harness.security.models import (
    SecurityAction,
    SecurityDecision,
    SecurityFinding,
    SecuritySeverity,
)

class InputLengthGuard:
    def __init__(self, max_chars: int , ) -> None:
        self.max_chars =  max_chars

    @property
    def name(self) -> str : 
        return "input_length"
    
    def inspect(self , text : str) -> SecurityDecision:
        if len(text) <= self.max_chars:
            return SecurityDecision(
                action=SecurityAction.ALLOW,
                code="SEC_INPUT_LENGTH_OK",
                reason="输入长度在允许范围内"
            )

        return SecurityDecision(
            action=SecurityAction.BLOCK,
            code="SEC_INPUT_TOOL_LARGE",
            reason=(
                f"输入长度 {len(text)} 超过限制 "
                f"{self.max_chars}。"
            ),
            findings=(
                SecurityFinding(
                    code="SEC_INPUT_TOOL_LARGE",
                    severity=SecuritySeverity.MEDIUM,
                    message="输入超过安全资源预算。",

                )
            )
        )
    
class PromptInjectionSignalGuard:
    """启发式 Signal Detector；不能证明某个 Prompt 安全或恶意。"""
    _PATTERNS = (
        re.compile(
            r"\bignore\b.{0,40}\b(previous|prior|above)\b"
            r".{0,20}\b(instruction|instructions)\b",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r"\b(reveal|show|print|leak)\b.{0,40}"
            r"\b(system|developer)\b.{0,20}"
            r"\b(prompt|message|instruction)\b",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r"忽略.{0,20}(之前|以上|前面).{0,20}(指令|要求|规则)",
            re.DOTALL,
        ),
        re.compile(
            r"(泄露|输出|显示|打印).{0,20}(系统提示|开发者消息|系统指令)",
            re.DOTALL,
        ),
    )

    def __init__(self, *, block_on_signal: bool = False,) -> None:
        self.block_on_signal = block_on_signal

    @property
    def name(self) -> str:
        return "prompt_injection_signal"

    def inspect(self,text: str,) -> SecurityDecision:
        matched = any(
            pattern.search(text)
            for pattern in self._PATTERNS
        )

        if not matched:
            return SecurityDecision(
                action=SecurityAction.ALLOW,
                code="SEC_PROMPT_SIGNAL_CLEAR",
                reason="未发现当前启发式规则可识别的提示注入信号。",
            )

        finding = SecurityFinding(
            code="SEC_PROMPT_INJECTION_SIGNAL",
            severity=SecuritySeverity.HIGH,
            message=(
                "输入包含提示注入风险信号；"
                "该信号不能单独证明攻击，也不能单独证明安全。"
            ),
        )

        if self.block_on_signal:
            return SecurityDecision(
                action=SecurityAction.BLOCK,
                code="SEC_PROMPT_INJECTION_BLOCKED",
                reason="配置要求阻止命中的提示注入风险信号。",
                findings=(finding,),
            )

        return SecurityDecision(
            action=SecurityAction.ALLOW,
            code="SEC_PROMPT_INJECTION_SIGNAL",
            reason="发现风险信号，默认审计但不依赖启发式规则单独封禁。",
            findings=(finding,),
        )

class SecretOutputGuard:
    """只处理明显 Credential Pattern；不是完整 DLP 系统。"""

    _RULES = (
        (
            re.compile(
                r"(?i)\bBearer\s+[A-Za-z0-9._~+/\-=]{16,}"
            ),
            "Bearer [REDACTED]",
        ),
        (
            re.compile(
                r"\bsk-[A-Za-z0-9_-]{20,}\b"
            ),
            "[REDACTED_API_KEY]",
        ),
        (
            re.compile(
                r"\bAKIA[A-Z0-9]{16}\b"
            ),
            "[REDACTED_AWS_ACCESS_KEY]",
        ),
    )

    @property
    def name(self) -> str:
        return "secret_output"

    def inspect(self,text: str,) -> SecurityDecision:
        transformed = text
        matched = False

        for pattern, replacement in self._RULES:
            transformed, count = pattern.subn(
                replacement,
                transformed,
            )
            matched = matched or count > 0

        if not matched:
            return SecurityDecision(
                action=SecurityAction.ALLOW,
                code="SEC_OUTPUT_SECRET_CLEAR",
                reason="未发现当前规则可识别的明显 Credential。",
            )

        return SecurityDecision(
            action=SecurityAction.REDACT,
            code="SEC_OUTPUT_SECRET_REDACTED",
            reason="输出中的明显 Credential Pattern 已脱敏。",
            transformed_text=transformed,
            findings=(
                SecurityFinding(
                    code="SEC_OUTPUT_SECRET_REDACTED",
                    severity=SecuritySeverity.HIGH,
                    message="输出中发现疑似密钥并已脱敏。",
                ),
            ),
        )

class OutputLengthGuard:
    def __init__(self,max_chars: int,) -> None:
        self.max_chars = max_chars

    @property
    def name(self) -> str:
        return "output_length"

    def inspect(
        self,
        text: str,
    ) -> SecurityDecision:
        if len(text) <= self.max_chars:
            return SecurityDecision(
                action=SecurityAction.ALLOW,
                code="SEC_OUTPUT_LENGTH_OK",
                reason="输出长度在允许范围内。",
            )

        transformed = (
            text[: self.max_chars]
            + "\n\n[OUTPUT_TRUNCATED_BY_SECURITY_POLICY]"
        )

        return SecurityDecision(
            action=SecurityAction.REDACT,
            code="SEC_OUTPUT_TRUNCATED",
            reason="输出超过限制，已截断。",
            transformed_text=transformed,
            findings=(
                SecurityFinding(
                    code="SEC_OUTPUT_TRUNCATED",
                    severity=SecuritySeverity.MEDIUM,
                    message="输出超过安全资源预算。",
                ),
            ),
        )