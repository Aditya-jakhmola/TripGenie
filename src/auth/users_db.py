"""User accounts, stored in the same Postgres database as everything else."""

import logging

from src.auth.passwords import hash_password, verify_password
from src.clients.checkpointer import get_connection
from src.config.session import resolve_database_url

logger = logging.getLogger(__name__)

_ensured: set = set()


class EmailAlreadyExists(Exception):
    pass


def _ensure_table(database_url: str) -> None:
    if database_url in _ensured:
        return

    connection = get_connection(database_url)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )

    _ensured.add(database_url)


def create_user(email: str, password: str, display_name: str) -> dict:
    database_url = resolve_database_url()
    _ensure_table(database_url)

    email = email.strip().lower()
    connection = get_connection(database_url)

    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))

        if cursor.fetchone():
            raise EmailAlreadyExists(email)

        cursor.execute(
            """
            INSERT INTO users (email, password_hash, display_name)
            VALUES (%s, %s, %s)
            RETURNING id, email, display_name
            """,
            (
                email,
                hash_password(password),
                display_name.strip() or email.split("@")[0],
            ),
        )
        row = cursor.fetchone()

    return {"id": row["id"], "email": row["email"], "display_name": row["display_name"]}


def verify_login(email: str, password: str):
    database_url = resolve_database_url()
    _ensure_table(database_url)

    email = email.strip().lower()
    connection = get_connection(database_url)

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, email, password_hash, display_name FROM users WHERE email = %s",
            (email,),
        )
        row = cursor.fetchone()

    if not row or not verify_password(password, row["password_hash"]):
        return None

    return {"id": row["id"], "email": row["email"], "display_name": row["display_name"]}


def get_user_by_id(user_id: int):
    database_url = resolve_database_url()
    _ensure_table(database_url)

    connection = get_connection(database_url)

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, email, display_name FROM users WHERE id = %s",
            (user_id,),
        )
        row = cursor.fetchone()

    if not row:
        return None

    return {"id": row["id"], "email": row["email"], "display_name": row["display_name"]}


def update_display_name(user_id: int, display_name: str):
    database_url = resolve_database_url()
    _ensure_table(database_url)

    display_name = display_name.strip()
    connection = get_connection(database_url)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE users SET display_name = %s
            WHERE id = %s
            RETURNING id, email, display_name
            """,
            (display_name, user_id),
        )
        row = cursor.fetchone()

    if not row:
        return None

    return {"id": row["id"], "email": row["email"], "display_name": row["display_name"]}