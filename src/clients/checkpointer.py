"""PostgreSQL checkpointer used by LangGraph to persist conversation threads."""

import psycopg
from psycopg.rows import dict_row

from langgraph.checkpoint.postgres import PostgresSaver

from src.config.session import require, resolve_database_url

_connections: dict[str, psycopg.Connection] = {}
_checkpointers: dict[str, PostgresSaver] = {}


def get_connection(database_url: str) -> psycopg.Connection:
    connection = _connections.get(database_url)

    if connection is None or connection.closed:
        connection = psycopg.connect(
            database_url,
            autocommit=True,
            row_factory=dict_row,
        )
        _connections[database_url] = connection

        # Any checkpointer built on the old connection is now stale too.
        _checkpointers.pop(database_url, None)

    return connection


def get_checkpointer(database_url: str) -> PostgresSaver:
    checkpointer = _checkpointers.get(database_url)

    if checkpointer is None:
        connection = get_connection(database_url)
        checkpointer = PostgresSaver(connection)
        checkpointer.setup()
        _checkpointers[database_url] = checkpointer

    return checkpointer


def get_session_checkpointer() -> PostgresSaver:
    """Checkpointer for whichever database URL the current session resolves to."""

    require("DATABASE_URL")

    return get_checkpointer(resolve_database_url())