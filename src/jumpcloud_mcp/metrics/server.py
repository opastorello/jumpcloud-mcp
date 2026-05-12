"""Prometheus metrics HTTP server.

Starts a background thread exposing /metrics on METRICS_PORT (default 9090).
Grafana datasource: Prometheus scraping http://<host>:9090/metrics
"""
from __future__ import annotations

import asyncio
import threading

from loguru import logger
from prometheus_client import start_http_server

from jumpcloud_mcp.core.config import settings
from jumpcloud_mcp.metrics.collector import run_collection_loop


def start_metrics_http_server() -> None:
    """Start the Prometheus HTTP server in a background thread."""
    port = settings.METRICS_PORT
    try:
        start_http_server(port)
        logger.info(f"metrics: Prometheus /metrics available on :{port}")
    except OSError as exc:
        logger.error(f"metrics: failed to bind :{port} — {exc}")


def launch_metrics(loop: asyncio.AbstractEventLoop) -> None:
    """Start the metrics HTTP server and schedule the collection loop on the given event loop."""
    if not settings.METRICS_ENABLED:
        logger.info("metrics: disabled (METRICS_ENABLED=false)")
        return

    # HTTP server runs in its own thread (prometheus_client WSGI server)
    t = threading.Thread(target=start_metrics_http_server, daemon=True)
    t.start()

    # Collection loop runs as an asyncio task on the MCP server's loop
    asyncio.ensure_future(
        run_collection_loop(settings.METRICS_COLLECT_INTERVAL),
        loop=loop,
    )
    logger.info(
        f"metrics: collection loop scheduled every {settings.METRICS_COLLECT_INTERVAL}s"
    )
