
import os
import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes

from recall.observability.metrics import (
    DASH_LEARNINGS_SAVED,
    DASH_LEARNINGS_TOTAL,
    DASH_QUERIES_TOTAL,
    DASH_QUERY_ERRORS,
    DASH_QUERY_LATENCY,
    DASH_VECTOR_SEARCH_LATENCY,
    LLM_TOKEN_USAGE,
    get_metrics,
    get_metrics_content_type,
    metrics_decorator,
    record_learning_saved,
    record_query_error,
    record_query_failure,
    record_query_success,
    record_token_usage,
    refresh_learning_count,
    track_query_latency,
    track_vector_search_latency,
    update_learnings_total,
)

logger = logging.getLogger(__name__)

def init_telemetry(service_name: str = "dash-agent"):
    """Initialize OpenTelemetry tracing."""
    otel_endpoint = os.getenv("ARCHESTRA_OTEL_ENDPOINT")
    
    resource = Resource.create(attributes={
        ResourceAttributes.SERVICE_NAME: service_name,
    })

    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)

    if otel_endpoint:
        logger.info(f"Initializing OTEL exporter to {otel_endpoint}")
        exporter = OTLPSpanExporter(endpoint=otel_endpoint)
        span_processor = BatchSpanProcessor(exporter)
        tracer_provider.add_span_processor(span_processor)
    else:
        logger.info("ARCHESTRA_OTEL_ENDPOINT not set, using ConsoleSpanExporter")
        # Use Console exporter for debugging if no endpoint
        tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

__all__ = [
    "init_telemetry",
    "DASH_LEARNINGS_SAVED",
    "DASH_LEARNINGS_TOTAL",
    "DASH_QUERIES_TOTAL",
    "DASH_QUERY_ERRORS",
    "DASH_QUERY_LATENCY",
    "DASH_VECTOR_SEARCH_LATENCY",
    "LLM_TOKEN_USAGE",
    "get_metrics",
    "get_metrics_content_type",
    "metrics_decorator",
    "record_learning_saved",
    "record_query_error",
    "record_query_failure",
    "record_query_success",
    "record_token_usage",
    "refresh_learning_count",
    "track_query_latency",
    "track_vector_search_latency",
    "update_learnings_total",
]
