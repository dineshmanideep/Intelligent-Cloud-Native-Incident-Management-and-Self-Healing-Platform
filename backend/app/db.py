import psycopg

from .config import settings


def get_connection() -> psycopg.Connection:
    return psycopg.connect(settings.database_url, connect_timeout=3)


def check_database() -> bool:
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return cursor.fetchone() == (1,)
    except psycopg.Error:
        return False


def get_demo_items() -> list[dict[str, object]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, name FROM demo_items ORDER BY id")
            return [{"id": item_id, "name": name} for item_id, name in cursor.fetchall()]

