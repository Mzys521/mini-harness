# 文件：harness/platform/config.py
from dataclasses import dataclass

@dataclass(frozen=True)
class PlatformConfig:
    api_key_header: str = "X-API-Key"
    api_key_prefix: str = "mhk"
    metering_poll_seconds: float = 1.0
    usage_sync_batch_size: int = 100
    billing_currency: str = "USD"
