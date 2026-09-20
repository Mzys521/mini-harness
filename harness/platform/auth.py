# 文件：harness/platform/auth.py
import hashlib
import hmac
import secrets

from harness.platform.errors import AuthenticationError
from harness.platform.models import (
    ApiKeyRecord,
    ApiKeyStatus,
    IssuedApiKey,
    Principal,
    utc_now,
)
from harness.state.ids import new_id


class ApiKeyManager:
    """API Key 发行与认证。

    明文 Secret 只在 create_key() 返回一次；数据库只保存 HMAC-SHA256 摘要。
    """

    def __init__(
        self,
        *,
        store,
        pepper: str,
        prefix: str = "mhk",
    ) -> None:
        if len(pepper) < 16:
            raise ValueError("HARNESS_API_KEY_PEPPER 至少需要 16 个字符")
        self.store = store
        self.pepper = pepper.encode("utf-8")
        self.prefix = prefix

    def create_key(
        self,
        *,
        tenant_id: str,
        name: str,
        scopes: frozenset[str],
    ) -> IssuedApiKey:
        api_key_id = new_id("key")
        secret_part = secrets.token_urlsafe(32)
        raw_key = f"{self.prefix}_{api_key_id}.{secret_part}"
        record = ApiKeyRecord(
            id=api_key_id,
            tenant_id=tenant_id,
            name=name,
            key_hash=self._digest(raw_key),
            scopes=scopes,
            status=ApiKeyStatus.ACTIVE,
            created_at=utc_now(),
        )
        self.store.insert_api_key(record)
        return IssuedApiKey(record=record, secret=raw_key)

    def authenticate(self, raw_key: str | None) -> Principal:
        if not raw_key:
            raise AuthenticationError("缺少 API key。")

        api_key_id = self._parse_id(raw_key)
        record = self.store.get_api_key(api_key_id)
        if record is None or record.status != ApiKeyStatus.ACTIVE:
            raise AuthenticationError()

        expected = self._digest(raw_key)
        if not hmac.compare_digest(expected, record.key_hash):
            raise AuthenticationError()

        self.store.touch_api_key(record.id)
        return Principal(
            tenant_id=record.tenant_id,
            api_key_id=record.id,
            scopes=record.scopes,
        )

    def _parse_id(self, raw_key: str) -> str:
        expected_prefix = f"{self.prefix}_"
        if not raw_key.startswith(expected_prefix) or "." not in raw_key:
            raise AuthenticationError()
        left, _ = raw_key.split(".", 1)
        api_key_id = left[len(expected_prefix):]
        if not api_key_id:
            raise AuthenticationError()
        return api_key_id

    def _digest(self, raw_key: str) -> str:
        return hmac.new(
            self.pepper,
            raw_key.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
