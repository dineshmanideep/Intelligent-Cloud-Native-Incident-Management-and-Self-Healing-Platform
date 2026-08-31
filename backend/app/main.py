import asyncio
import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from .config import settings
from .db import (
    check_database,
    close_pool,
    exhaust_pool,
    get_demo_items,
    open_pool,
    reset_demo_state,
    start_lock_contention,
)
from .telemetry import configure_logging, configure_telemetry


configure_logging()
logger = logging.getLogger(settings.app_name)

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)
DEMO_DEPENDENCY_RETRIES = Counter("demo_dependency_retries_total", "Retries performed by the dependency demo")
DEMO_DEPENDENCY_FAILURE = Gauge("demo_dependency_failure_active", "Whether the dependency failure demo is active")
DEMO_MEMORY_PRESSURE = Gauge("demo_memory_pressure_active", "Whether the bounded memory-pressure demo is active")
DEMO_MEMORY_PRESSURE_BYTES = Gauge("demo_memory_pressure_bytes", "Bytes held by the bounded memory-pressure demo")
DEMO_MEMORY_PRESSURE_LIMIT = Gauge("demo_memory_pressure_limit_bytes", "Safe allocation limit for the memory-pressure demo")
_dependency_failure_active = False
_latency_demo_active = False
_memory_pressure: bytearray | None = None
_MEMORY_PRESSURE_LIMIT = 64 * 1024 * 1024
_demo_stop_requested = threading.Event()
DEMO_MEMORY_PRESSURE_LIMIT.set(_MEMORY_PRESSURE_LIMIT)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("starting service=%s environment=%s", settings.app_name, settings.app_env)
    open_pool()
    yield
    close_pool()
    shutdown_telemetry()
    logger.info("stopping service=%s", settings.app_name)


app = FastAPI(title="Incident Demo API", version="0.1.0", lifespan=lifespan)
shutdown_telemetry = configure_telemetry(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        path = request.url.path
        elapsed = time.perf_counter() - started
        REQUEST_COUNT.labels(request.method, path, str(status_code)).inc()
        REQUEST_LATENCY.labels(request.method, path).observe(elapsed)
        logger.info(
            "request method=%s path=%s status=%s duration_ms=%.2f",
            request.method,
            path,
            status_code,
            elapsed * 1000,
        )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/api/hello")
async def hello() -> dict[str, str]:
    return {"message": "Hello from the incident demo API"}


@app.get("/api/db-check")
async def database_check() -> dict[str, object]:
    healthy = check_database()
    if not healthy:
        raise HTTPException(status_code=503, detail="Database is unavailable")
    return {"database": "ok"}


@app.post("/api/demo/db-pool-exhaust")
async def demo_db_pool_exhaust() -> dict[str, object]:
    try:
        state = await asyncio.to_thread(exhaust_pool)
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"Unable to hold database pool connections: {error}") from error
    logger.warning("demo scenario=database_connection_pool_exhaustion state=%s", state)
    return {"scenario": "database_connection_pool_exhaustion", **state}


@app.post("/api/demo/db-lock/start")
async def demo_db_lock_start() -> dict[str, str]:
    try:
        state = await asyncio.to_thread(start_lock_contention)
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"Unable to start database lock scenario: {error}") from error
    logger.warning("demo scenario=database_lock_contention state=active")
    return state


@app.post("/api/demo/reset")
async def demo_reset() -> dict[str, str]:
    global _dependency_failure_active, _latency_demo_active, _memory_pressure
    _dependency_failure_active = False
    _latency_demo_active = False
    _memory_pressure = None
    _demo_stop_requested.set()
    DEMO_DEPENDENCY_FAILURE.set(0)
    DEMO_MEMORY_PRESSURE.set(0)
    DEMO_MEMORY_PRESSURE_BYTES.set(0)
    await asyncio.to_thread(reset_demo_state)
    logger.info("demo scenarios reset")
    return {"status": "reset"}


@app.post("/api/demo/stop")
async def demo_stop() -> dict[str, str]:
    """Stop persistent and cancellable demo activity without touching incidents or memory."""
    await demo_reset()
    return {"status": "stopped"}


@app.post("/api/demo/memory/start")
async def demo_memory_start() -> dict[str, object]:
    global _memory_pressure
    _demo_stop_requested.clear()
    _memory_pressure = bytearray(_MEMORY_PRESSURE_LIMIT)
    _memory_pressure[:] = b"\x01" * _MEMORY_PRESSURE_LIMIT
    DEMO_MEMORY_PRESSURE.set(1)
    DEMO_MEMORY_PRESSURE_BYTES.set(_MEMORY_PRESSURE_LIMIT)
    logger.warning("demo scenario=memory_pressure state=active bytes=%s", _MEMORY_PRESSURE_LIMIT)
    return {"scenario": "memory_pressure", "status": "active", "allocated_mb": _MEMORY_PRESSURE_LIMIT // (1024 * 1024)}


@app.post("/api/demo/latency/start")
async def demo_latency_start() -> dict[str, str]:
    global _latency_demo_active
    _demo_stop_requested.clear()
    _latency_demo_active = True
    logger.warning("demo scenario=latency_degradation state=active")
    return {"scenario": "latency_degradation", "status": "active"}


@app.post("/api/demo/dependency-failure")
async def demo_dependency_failure() -> dict[str, str]:
    global _dependency_failure_active
    _dependency_failure_active = True
    DEMO_DEPENDENCY_FAILURE.set(1)
    logger.warning("demo scenario=downstream_dependency_retry_storm state=active")
    return {"scenario": "downstream_dependency_retry_storm", "status": "active"}


@app.get("/api/demo/downstream")
async def demo_downstream() -> dict[str, str]:
    if _dependency_failure_active:
        for attempt in range(3):
            DEMO_DEPENDENCY_RETRIES.inc()
            logger.warning("demo downstream timeout retry=%s", attempt + 1)
            await asyncio.sleep(0.25)
        raise HTTPException(status_code=504, detail="Controlled downstream timeout")
    return {"dependency": "ok"}


@app.get("/api/demo/latency")
async def demo_latency() -> dict[str, object]:
    if _latency_demo_active:
        await asyncio.sleep(2)
        return {"status": "degraded", "duration_seconds": 2}
    return {"status": "normal", "duration_seconds": 0}


@app.get("/api/items")
async def items() -> dict[str, object]:
    try:
        return {"items": get_demo_items()}
    except Exception as error:
        logger.exception("database query failed")
        raise HTTPException(status_code=503, detail="Database query failed") from error


@app.get("/api/error")
async def controlled_error() -> None:
    logger.error("controlled demo error triggered")
    raise HTTPException(status_code=500, detail="Controlled demo error")


@app.get("/api/delay")
async def controlled_delay(seconds: float = Query(default=5, ge=0, le=60)) -> dict[str, object]:
    _demo_stop_requested.clear()
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        if _demo_stop_requested.is_set():
            raise HTTPException(status_code=409, detail="Demo scenario stopped")
        await asyncio.sleep(min(0.1, max(0.0, deadline - time.perf_counter())))
    return {"message": "Delay completed", "seconds": seconds}


@app.get("/api/cpu")
async def controlled_cpu(seconds: float = Query(default=10, ge=0, le=60)) -> dict[str, object]:
    _demo_stop_requested.clear()
    deadline = time.perf_counter() + seconds
    value = 0.0
    while time.perf_counter() < deadline:
        if _demo_stop_requested.is_set():
            raise HTTPException(status_code=409, detail="Demo scenario stopped")
        value = (value * 1.000001 + 1.0) % 1000000
    return {"message": "CPU workload completed", "seconds": seconds, "result": value}


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
