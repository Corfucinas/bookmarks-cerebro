"""FastAPI app factory, middleware, metrics, and ``run_dashboard`` entrypoint.

The routes themselves live in :mod:`cerebro.dashboard_routes`; this module
owns app creation, the Prometheus middleware, and the uvicorn launcher.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import Response
from prometheus_client import REGISTRY, Histogram
from prometheus_client import Counter as PrometheusCounter

from src.cerebro.dashboard_routes import register_routes
from src.cerebro.security import add_security_middleware

app = FastAPI(title="Bookmarks Cerebro Dashboard", version="1.0.0")
add_security_middleware(app)
register_routes(app)


def _get_or_create_metric(metric_cls: type[Any], name: str, *args: Any, **kwargs: Any) -> Any:
    """Return an existing Prometheus collector or create a new one.

    Re-importing the module during tests would otherwise raise a duplicate
    registration error.
    """
    try:
        return metric_cls(name, *args, **kwargs)
    except ValueError:
        return REGISTRY._names_to_collectors[name]


REQUEST_COUNT = _get_or_create_metric(
    PrometheusCounter,
    "cerebro_http_requests_total",
    "Total HTTP requests",
    ["method", "path"],
)
REQUEST_LATENCY = _get_or_create_metric(
    Histogram,
    "cerebro_http_request_duration_seconds",
    "HTTP request latency",
)


@app.middleware("http")
async def metrics_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Record request counts and latencies for Prometheus."""
    path = request.url.path
    method = request.method
    start = time.time()
    response = await call_next(request)
    REQUEST_LATENCY.observe(time.time() - start)
    REQUEST_COUNT.labels(method=method, path=path).inc()
    return response


def run_dashboard(host: str = "127.0.0.1", port: int = 8080) -> None:
    """Run the FastAPI dashboard server using uvicorn."""
    import uvicorn

    uvicorn.run(app, host=host, port=port)
