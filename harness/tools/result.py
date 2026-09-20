# 文件：harness/tools/result.py
import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

class ToolStatus(StrEnum):
    SUCCESS = "success"
    INVALID_ARGUMENTS = "invalid_arguments"
    NOT_FOUND = "not_found"
    PERMISSION_DENIED = "permission_denied"
    SECURITY_DENIED = "security_denied"
    APPROVAL_REQUIRED = "approval_required"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    TIMEOUT = "timeout"
    ERROR = "error"

@dataclass
class ToolResult:
    call_id: str
    tool_name: str
    status: ToolStatus
    data: Any = None
    error_code: str | None = None
    error_message: str | None = None
    attempts: int = 1
    security_code: str | None = None
    security_codes: list[str] = field(
        default_factory=list
    )
    model_output_override: str | None = None

    @property
    def ok(self) -> bool:
        return (
            self.status
            == ToolStatus.SUCCESS
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop(
            "model_output_override",
            None,
        )
        payload["status"] = self.status.value
        return payload

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> "ToolResult":
        data = dict(payload)
        data["status"] = ToolStatus(
            data["status"]
        )
        return cls(**data)

    def to_model_output(self) -> str:
        # 对模型暴露的是安全投影，不一定等于应用内部原始 data。
        if self.model_output_override is not None:
            return self.model_output_override

        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            default=str,
        )
