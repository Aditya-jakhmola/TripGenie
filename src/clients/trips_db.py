"""
Lightweight trip history, stored in the same Postgres database already
used for LangGraph checkpoints.

Trips are scoped by an "owner key" string - either "device:<uuid>" for
anonymous browser sessions, or "user:<id>" once someone is logged in.
This reuses the existing device_id column rather than adding a new one,
so no migration is needed on top of what's already deployed.
"""

import logging

from src.clients.checkpointer import get_connection
from src.config.session import resolve_database_url

logger = logging.getLogger(__name__)

_ensured: set = set()


def _ensure_table(database_url: str) -> None:
    if database_url in _ensured:
        return

    connection = get_connection(database_url)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS trips (
                id SERIAL PRIMARY KEY,
                device_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                query TEXT NOT NULL,
                answer TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_trips_device_id
            ON trips (device_id, created_at DESC)
            """
        )

    _ensured.add(database_url)


def save_trip(owner_key: str, thread_id: str, query: str, answer: str) -> None:
    database_url = resolve_database_url()
    _ensure_table(database_url)

    connection = get_connection(database_url)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO trips (device_id, thread_id, query, answer)
            VALUES (%s, %s, %s, %s)
            """,
            (owner_key, thread_id, query, answer),
        )


def list_trips(owner_key: str, limit: int = 20) -> list:
    database_url = resolve_database_url()
    _ensure_table(database_url)

    connection = get_connection(database_url)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, thread_id, query, created_at
            FROM trips
            WHERE device_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (owner_key, limit),
        )
        rows = cursor.fetchall()

    return [
        {
            "id": row["id"],
            "thread_id": row["thread_id"],
            "query": row["query"],
            "created_at": row["created_at"].isoformat(),
        }
        for row in rows
    ]


def get_trip(owner_key: str, trip_id: int):
    database_url = resolve_database_url()
    _ensure_table(database_url)

    connection = get_connection(database_url)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, thread_id, query, answer, created_at
            FROM trips
            WHERE device_id = %s AND id = %s
            """,
            (owner_key, trip_id),
        )
        row = cursor.fetchone()

    if not row:
        return None

    return {
        "id": row["id"],
        "thread_id": row["thread_id"],
        "query": row["query"],
        "answer": row["answer"],
        "created_at": row["created_at"].isoformat(),
    }


def delete_trip(owner_key: str, trip_id: int) -> bool:
    database_url = resolve_database_url()
    _ensure_table(database_url)

    connection = get_connection(database_url)

    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM trips WHERE device_id = %s AND id = %s",
            (owner_key, trip_id),
        )
        return cursor.rowcount > 0