from dataclasses import dataclass

from harness import __version__


@dataclass
class ObservabilityConfig:
    service_name: str = "mini-harness"
    service_version: str = __version__
    exporter: str = "console"
    otlp_endpoint: str = "http://localhost:4318"
    capture_content: bool = False
    log_level: str = "INFO"
    # exporter="file" 时 span / 指标 的落盘路径（控制台只保留对话输出）
    telemetry_path: str = "data/telemetry.log"
    # exporter="file" 时结构化 JSON 日志的落盘路径
    log_path: str = "data/logs.jsonl"


