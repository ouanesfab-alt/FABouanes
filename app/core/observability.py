from __future__ import annotations

import os
import sys
import logging
from typing import Any

import structlog
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource


# Eventual OTLP exporter support
try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
except ImportError:
    OTLPSpanExporter = None

_TRACER_INITIALIZED = False


def inject_otel_context(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Structlog processor to inject the active OpenTelemetry Trace ID and Span ID."""
    current_span = trace.get_current_span()
    if current_span and current_span.get_span_context().is_valid:
        span_context = current_span.get_span_context()
        event_dict["trace_id"] = format(span_context.trace_id, "032x")
        event_dict["span_id"] = format(span_context.span_id, "016x")
    return event_dict


def setup_observability(service_name: str = "fabouanes") -> None:
    """Initialize OpenTelemetry tracer provider and configure structured logging."""
    global _TRACER_INITIALIZED
    if _TRACER_INITIALIZED:
        return

    # 1. Setup Resource
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    # 2. Add Exporter
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if otlp_endpoint and OTLPSpanExporter:  # pragma: no cover
        try:
            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        except Exception:
            logging.getLogger("observability").warning("Failed to initialize OTLP Span Exporter.")
    elif os.environ.get("OTEL_EXPORT_CONSOLE", "").strip().lower() in ("true", "1") and "pytest" not in sys.modules:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _TRACER_INITIALIZED = True

    # 3. Setup Structlog configuration
    processors: list[Any] = [
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        inject_otel_context,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    is_production = os.environ.get("FASTAPI_ENV", "development").lower() == "production"

    if is_production:  # pragma: no cover
        # JSON formatting for production log processors
        processors.append(structlog.processors.JSONRenderer())
    else:
        # User-friendly console logs for development
        from structlog.dev import ConsoleRenderer
        processors.append(ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def instrument_app(app: Any) -> None:
    """Instrument the FastAPI application with OpenTelemetry."""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except Exception as exc:
        logging.getLogger("observability").warning("Failed to instrument FastAPI application: %s", exc)


def instrument_sqlalchemy(engine: Any) -> None:
    """Instrument SQLAlchemy engine to record all SQL queries in spans."""
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        SQLAlchemyInstrumentor().instrument(engine=engine)
    except Exception as exc:
        logging.getLogger("observability").warning("Failed to instrument SQLAlchemy engine: %s", exc)
