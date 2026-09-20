# 文件：harness/platform/errors.py
from dataclasses import dataclass

@dataclass
class PlatformError(Exception):
    code: str
    title: str
    detail: str
    status_code: int

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"

class AuthenticationError(PlatformError):
    def __init__(self, detail: str = "API key 无效或已撤销。") -> None:
        super().__init__(
            code="PLATFORM_AUTHENTICATION_FAILED",
            title="Authentication failed",
            detail=detail,
            status_code=401,
        )

class AuthorizationError(PlatformError):
    def __init__(self, detail: str = "当前凭据没有执行该操作的权限。") -> None:
        super().__init__(
            code="PLATFORM_AUTHORIZATION_FAILED",
            title="Authorization failed",
            detail=detail,
            status_code=403,
        )

class TenantSuspendedError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            code="PLATFORM_TENANT_SUSPENDED",
            title="Tenant suspended",
            detail="当前租户已被暂停。",
            status_code=403,
        )

class QuotaExceededError(PlatformError):
    def __init__(self, *, code: str, detail: str) -> None:
        super().__init__(
            code=code,
            title="Quota exceeded",
            detail=detail,
            status_code=429,
        )

class ResourceNotFoundError(PlatformError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            code="PLATFORM_RESOURCE_NOT_FOUND",
            title="Resource not found",
            detail=detail,
            status_code=404,
        )

class ConflictError(PlatformError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            code="PLATFORM_CONFLICT",
            title="Conflict",
            detail=detail,
            status_code=409,
        )
