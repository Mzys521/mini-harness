import logging
from pathlib import Path

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from harness.observability.logging import configure_structured_logging

# exporter="file" 模式下 span / 指标 共用的输出流（进程内只打开一次）
_telemetry_stream = None


def _telemetry_output(path: str):
    """打开（或复用）span / 指标 的落盘文件。

    显式使用 UTF-8：console exporter 默认继承 stdout 编码（中文 Windows 下为 gbk），
    写入文件时固定 UTF-8 才不会出现中文乱码。
    """
    global _telemetry_stream
    if _telemetry_stream is None or _telemetry_stream.closed:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        _telemetry_stream = target.open("a", encoding="utf-8")
    return _telemetry_stream


def _trace_exporter(config):
    if config.exporter == "console":
        return ConsoleSpanExporter()
    if config.exporter == "file":
        return ConsoleSpanExporter(out=_telemetry_output(config.telemetry_path))
    if config.exporter == "otlp":
        return OTLPSpanExporter(endpoint=config.otlp_endpoint.rstrip("/") + "/v1/traces")
    raise ValueError(f"unknown exporter: {config.exporter}")

def _metric_reader(config):
    if config.exporter == "console":
        exporter = ConsoleMetricExporter()
    elif config.exporter == "file":
        exporter = ConsoleMetricExporter(out=_telemetry_output(config.telemetry_path))
    elif config.exporter == "otlp":
        exporter = OTLPMetricExporter(endpoint=config.otlp_endpoint.rstrip("/") + "/v1/metrics")
    else:
        raise ValueError(f"unknown exporter: {config.exporter}")
    return PeriodicExportingMetricReader(exporter, export_interval_millis=10_000)

def configure_observability(config) -> None:
    resource = Resource.create({
        "service.name": config.service_name,
        "service.version": config.service_version,
    })
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(_trace_exporter(config)))
    trace.set_tracer_provider(tracer_provider)
    meter_provider = MeterProvider(resource=resource, metric_readers=[_metric_reader(config)])
    metrics.set_meter_provider(meter_provider)

    # file 模式下结构化日志一并落盘，控制台只保留业务输出（对话 / 工具调用）。
    configure_structured_logging(
        config.log_level,
        path=config.log_path if config.exporter == "file" else None,
    )


def shutdown_observability() -> None:
    """冲刷并关闭遥测。

    BatchSpanProcessor 与 PeriodicExportingMetricReader 均为异步批量导出，
    进程退出前必须 force_flush，否则最后一批 span / 指标会丢失（file 模式下表现为记录不完整）。
    """
    tracer_provider = trace.get_tracer_provider()
    if hasattr(tracer_provider, "force_flush"):
        tracer_provider.force_flush()
    if hasattr(tracer_provider, "shutdown"):
        tracer_provider.shutdown()

    meter_provider = metrics.get_meter_provider()
    if hasattr(meter_provider, "force_flush"):
        meter_provider.force_flush()
    if hasattr(meter_provider, "shutdown"):
        meter_provider.shutdown()

    for handler in logging.getLogger().handlers:
        handler.flush()

    global _telemetry_stream
    if _telemetry_stream is not None and not _telemetry_stream.closed:
        _telemetry_stream.close()
