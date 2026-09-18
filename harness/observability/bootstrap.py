from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from harness.observability.logging import configure_structured_logging


def _trace_exporter(config):
    if config.exporter == "console":
        return ConsoleSpanExporter()
    if config.exporter == "otlp":
        return OTLPSpanExporter(endpoint=config.otlp_endpoint.rstrip("/") + "/v1/traces")
    raise ValueError(f"unknown exporter: {config.exporter}")

def _metric_reader(config):
    if config.exporter == "console":
        exporter = ConsoleMetricExporter()
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
    configure_structured_logging(config.log_level)








