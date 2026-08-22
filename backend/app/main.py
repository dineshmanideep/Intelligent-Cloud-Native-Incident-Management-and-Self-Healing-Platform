import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from .config import settings
from .db import check_database, get_demo_items


logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
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


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("starting service=%s environment=%s", settings.app_name, settings.app_env)
    yield
    logger.info("stopping service=%s", settings.app_name)


app = FastAPI(title="Incident Demo API", version="0.1.0", lifespan=lifespan)
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
    await asyncio.sleep(seconds)
    return {"message": "Delay completed", "seconds": seconds}


@app.get("/api/cpu")
async def controlled_cpu(seconds: float = Query(default=10, ge=0, le=60)) -> dict[str, object]:
    deadline = time.perf_counter() + seconds
    value = 0.0
    while time.perf_counter() < deadline:
        value = (value * 1.000001 + 1.0) % 1000000
    return {"message": "CPU workload completed", "seconds": seconds, "result": value}


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

