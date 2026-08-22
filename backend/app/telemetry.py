import json
import logging
from collections.abc import Callable

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
from opentelemetry.sdk.resources import DEPLOYMENT_ENVIRONMENT, SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from .config import settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        span = trace.get_current_span()
        context = span.get_span_context()
        payload = {
            "timestamp": self.formatTime(record, self.default_time_format),
            "severity": record.levelname,
            "service": settings.otel_service_name,
            "environment": settings.app_env,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": format(context.trace_id, "032x") if context.is_valid else "",
            "span_id": format(context.span_id, "016x") if context.is_valid else "",
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))


def configure_telemetry(app) -> Callable[[], None]:
    if not settings.otel_enabled:
        return lambda: None

    resource = Resource.create(
        {
            SERVICE_NAME: settings.otel_service_name,
            DEPLOYMENT_ENVIRONMENT: settings.app_env,
        }
    )
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    PsycopgInstrumentor().instrument(tracer_provider=provider)

    def shutdown() -> None:
        provider.force_flush()
        FastAPIInstrumentor.uninstrument_app(app)
        PsycopgInstrumentor().uninstrument()

    return shutdown
