from typing import Protocol

from harness.security.models import (
    SecurityAuditEvent,
    SecurityDecision,
)

class InputGuard(Protocol):
    @property
    def name(self) -> str: ...
    def input(self, input: str) -> SecurityDecision: ...

class OutputGuard(Protocol):
    @property
    def name(self) -> str: ...
    def output(self, output: str) -> SecurityDecision: ...

class ToolPolice(Protocol):
    def anthorize(self, * , tool , call, context ,) -> SecurityDecision: ...

class AuditSink(Protocol):
    def emit(self, issue: SecurityAuditEvent) ->None: ...
