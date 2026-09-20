# 文件：harness/durable/config.py
from dataclasses import dataclass

@dataclass(frozen=True)
class DurableConfig:
    worker_count: int = 2
    lease_seconds: float = 120.0
    poll_interval_seconds: float = 0.5
    idle_backoff_seconds: float = 0.5
    transition_retry_delay_seconds: float = 2.0
    max_transitions_per_claim: int = 16
