# 文件：harness/platform/runtime.py
from dataclasses import dataclass
from typing import Any

from harness.platform.auth import ApiKeyManager
from harness.platform.billing import BillingService
from harness.platform.metering import UsageReconciler
from harness.platform.service import CommercialPlatformService
from harness.platform.store import SQLitePlatformStore

@dataclass(frozen=True)
class CommercialRuntime:
    core: Any
    store: SQLitePlatformStore
    api_keys: ApiKeyManager
    service: CommercialPlatformService
    metering: UsageReconciler
    billing: BillingService
