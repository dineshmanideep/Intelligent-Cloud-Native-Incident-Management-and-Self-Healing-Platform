import threading
from contextlib import contextmanager
from typing import Iterator

import psycopg
from prometheus_client import Gauge
from psycopg_pool import ConnectionPool, PoolTimeout

from .config import settings


DB_POOL_HELD = Gauge("demo_db_held_connections", "Connections deliberately held by a demo scenario")
DB_POOL_CAPACITY = Gauge("demo_db_pool_capacity", "Configured API database pool capacity")
DB_LOCK_ACTIVE = Gauge("demo_db_lock_contention_active", "Whether the database contention demo is active")

_pool = ConnectionPool(settings.database_url, min_size=settings.database_pool_min_size,
                       max_size=settings.database_pool_max_size, timeout=settings.database_pool_timeout, open=False)
_held_connections: list[psycopg.Connection] = []
_lock = threading.Lock()
_lock_connection: psycopg.Connection | None = None


def open_pool() -> None:
    _pool.open()
    _pool.wait()
    DB_POOL_CAPACITY.set(settings.database_pool_max_size)


def close_pool() -> None:
    reset_demo_state()
    _pool.close()


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    with _pool.connection() as connection:
        yield connection


def check_database() -> bool:
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return cursor.fetchone() == (1,)
    except (psycopg.Error, PoolTimeout):
        return False


def get_demo_items() -> list[dict[str, object]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(424242)")
            cursor.execute("SELECT id, name FROM demo_items ORDER BY id")
            return [{"id": item_id, "name": name} for item_id, name in cursor.fetchall()]


def exhaust_pool() -> dict[str, int]:
    with _lock:
        # Hold one database-wide advisory lock first so requests routed to the
        # other API replica also experience the controlled database wait.
        global _lock_connection
        if _lock_connection is None:
            _lock_connection = _pool.getconn(timeout=settings.database_pool_timeout)
            _lock_connection.autocommit = True
            with _lock_connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_lock(424242)")
            DB_LOCK_ACTIVE.set(1)
        target = max(settings.database_pool_max_size - 1, 1)
        while len(_held_connections) < target:
            _held_connections.append(_pool.getconn(timeout=settings.database_pool_timeout))
        DB_POOL_HELD.set(len(_held_connections) + 1)
        return {"held_connections": len(_held_connections) + 1, "pool_capacity": settings.database_pool_max_size}


def start_lock_contention() -> dict[str, str]:
    global _lock_connection
    with _lock:
        if _lock_connection is None:
            _lock_connection = _pool.getconn(timeout=settings.database_pool_timeout)
            _lock_connection.autocommit = True
            with _lock_connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_lock(424242)")
            DB_LOCK_ACTIVE.set(1)
    return {"status": "active", "lock": "demo_items advisory lock"}


def reset_demo_state() -> None:
    global _lock_connection
    with _lock:
        if _lock_connection is not None:
            try:
                with _lock_connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_unlock(424242)")
            finally:
                _pool.putconn(_lock_connection)
                _lock_connection = None
        for connection in _held_connections:
            _pool.putconn(connection)
        _held_connections.clear()
        DB_POOL_HELD.set(0)
        DB_LOCK_ACTIVE.set(0)
