"""
Observability Metrics Module
============================

Prometheus metrics for monitoring the Dash learning system.
Exposes metrics for queries, errors, learnings, and LLM token usage.
"""

import logging
import time
from contextlib import contextmanager
from functools import wraps
from typing import Callable, Generator

from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)

DASH_QUERIES_TOTAL = Counter(
    "dash_queries_total",
    "Total number of queries processed by Dash agent",
    ["status"],
)

DASH_QUERY_ERRORS = Counter(
    "dash_query_errors",
    "Total number of query errors",
    ["error_type"],
)

DASH_LEARNINGS_SAVED = Counter(
    "dash_learnings_saved",
    "Total number of learnings saved to the database",
    ["error_type"],
)

DASH_LEARNINGS_TOTAL = Gauge(
    "dash_learnings_total",
    "Current total number of learnings in the database",
)

DASH_QUERY_LATENCY = Histogram(
    "dash_query_latency_seconds",
    "Query processing latency in seconds",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

LLM_TOKEN_USAGE = Histogram(
    "llm_token_usage",
    "LLM token usage per request",
    ["model", "token_type"],
    buckets=[10, 50, 100, 250, 500, 1000, 2500, 5000, 10000],
)

DASH_VECTOR_SEARCH_LATENCY = Histogram(
    "dash_vector_search_latency_seconds",
    "Vector similarity search latency in seconds",
    ["search_type"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)


def record_query_success():
    """Record a successful query."""
    DASH_QUERIES_TOTAL.labels(status="success").inc()


def record_query_failure():
    """Record a failed query."""
    DASH_QUERIES_TOTAL.labels(status="failure").inc()


def record_query_error(error_type: str):
    """Record a query error by type."""
    DASH_QUERY_ERRORS.labels(error_type=error_type).inc()


def record_learning_saved(error_type: str = "unknown"):
    """Record a learning being saved."""
    DASH_LEARNINGS_SAVED.labels(error_type=error_type).inc()


def update_learnings_total(count: int):
    """Update the total learnings gauge."""
    DASH_LEARNINGS_TOTAL.set(count)


def record_token_usage(model: str, prompt_tokens: int, completion_tokens: int):
    """Record LLM token usage."""
    LLM_TOKEN_USAGE.labels(model=model, token_type="prompt").observe(prompt_tokens)
    LLM_TOKEN_USAGE.labels(model=model, token_type="completion").observe(completion_tokens)


@contextmanager
def track_query_latency() -> Generator[None, None, None]:
    """Context manager to track query latency."""
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        DASH_QUERY_LATENCY.observe(duration)


@contextmanager
def track_vector_search_latency(search_type: str = "learning") -> Generator[None, None, None]:
    """Context manager to track vector search latency."""
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        DASH_VECTOR_SEARCH_LATENCY.labels(search_type=search_type).observe(duration)


def metrics_decorator(func: Callable) -> Callable:
    """Decorator to automatically track query metrics."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        with track_query_latency():
            try:
                result = await func(*args, **kwargs)
                record_query_success()
                return result
            except Exception as e:
                record_query_failure()
                error_type = type(e).__name__
                record_query_error(error_type)
                raise
    return wrapper


def get_metrics() -> bytes:
    """Get current metrics in Prometheus format."""
    return generate_latest()


def get_metrics_content_type() -> str:
    """Get the content type for Prometheus metrics."""
    return CONTENT_TYPE_LATEST


async def refresh_learning_count():
    """Refresh the learnings total gauge from the database."""
    try:
        from db import db_url
        from db.learning_store import LearningStore
        
        store = LearningStore(db_url=db_url, embedder=None)
        count = store.get_learning_count()
        update_learnings_total(count)
        logger.debug(f"Refreshed learning count: {count}")
    except Exception as e:
        logger.error(f"Failed to refresh learning count: {e}")
