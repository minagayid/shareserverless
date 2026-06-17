from prometheus_client import Counter, Gauge, Histogram, make_asgi_app
from fastapi import FastAPI, Request


TASKS_TOTAL = Counter(
    "ss_tasks_total",
    "Total number of tasks processed",
    ["status", "app_type"],
)


LATENCY = Histogram(
    "ss_task_latency_seconds",
    "Task execution latency",
    ["app_type", "tier"],
    buckets=[0.1, 0.5, 1, 5, 30, 60, 300, 600],
)


NODE_REGISTERED = Gauge("ss_nodes_registered", "Number of nodes registered per tier", ["tier"])


REPUTATION = Gauge(
    "ss_node_reputation",
    "Reputation score of a node",
    ["node_id", "tier"],
)


def instrument_app(app: FastAPI) -> FastAPI:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)
    return app


async def record_task(
    app_type: str,
    tier: str | None,
    status: str,
    latency_seconds: float | None = None,
) -> None:
    TASKS_TOTAL.labels(app_type=app_type, status=status).inc()
    if latency_seconds is not None and tier:
        LATENCY.labels(app_type=app_type, tier=tier).observe(latency_seconds)
