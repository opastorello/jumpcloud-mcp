"""FastAPI app — REST API + Prometheus /metrics for JumpCloud MCP.

Runs separately from mcp_server.py (two processes, one codebase).
  Dockerfile     → this file  (port 8000)
  Dockerfile.mcp → mcp_server (port 8002)
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from loguru import logger
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from jumpcloud_mcp.api.v1.router import api_v1_router
from jumpcloud_mcp.core.config import settings
from jumpcloud_mcp.core.logging import setup_logging
from jumpcloud_mcp.metrics.collector import run_collection_loop

import asyncio


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.LOG_LEVEL)
    logger.info("jumpcloud-api starting")

    task = None
    if settings.METRICS_ENABLED:
        task = asyncio.ensure_future(
            run_collection_loop(settings.METRICS_COLLECT_INTERVAL)
        )
        logger.info(
            f"metrics: collection loop started (interval={settings.METRICS_COLLECT_INTERVAL}s)"
        )

    yield

    if task:
        task.cancel()
    logger.info("jumpcloud-api stopped")


app = FastAPI(
    title="JumpCloud MCP API",
    version="0.1.0",
    docs_url="/docs" if settings.LOG_LEVEL == "DEBUG" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_PUBLIC_PATHS = {"/health", "/health/detailed", "/"}


@app.middleware("http")
async def bearer_auth(request: Request, call_next):
    if request.url.path in _PUBLIC_PATHS or request.url.path.startswith("/docs"):
        return await call_next(request)
    if settings.MCP_SECRET_TOKEN:
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {settings.MCP_SECRET_TOKEN}":
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized"},
                headers={"WWW-Authenticate": "Bearer"},
            )
    return await call_next(request)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def root():
    return {"service": "jumpcloud-api", "status": "ok"}


@app.get("/metrics", include_in_schema=False)
async def prometheus_metrics():
    data = generate_latest()
    return PlainTextResponse(data, media_type=CONTENT_TYPE_LATEST)


app.include_router(api_v1_router)
