"""
Observability Module
====================

Provides metrics, tracing, and monitoring for the Dash system.
"""

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

__all__ = [
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
