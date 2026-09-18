from dataclasses import dataclass

@dataclass
class ObservabilityConfig:
    service_name: str = "mini-harness"
    service_version: str = "0.8.0"
    exporter: str = "console"
    otlp_endpoint: str = "http://localhost:4318"
    capture_content: bool = False
    log_level: str = "INFO"


