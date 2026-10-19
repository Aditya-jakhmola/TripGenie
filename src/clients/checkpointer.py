"""PostgreSQL checkpointer used by LangGraph to persist conversation threads."""

import logging
import threading

import psycopg
from psycopg.rows import dict_row

from langgraph.checkpoint.postgres import PostgresSaver

from src.config.session import require, resolve_database_url

logger = logging.getLogger(__name__)

_connections: dict[str, psycopg.Connection] = {}
_checkpointers: dict[str, tuple] = {}

# Re-entrant, because get_checkpointer() calls get_connection() while
# holding it.
_lock = threading.RLock()


def _is_alive(connection) -> bool:
    """
    Managed databases (Neon, Render) close idle connections on their side,
    but psycopg only finds out when it next uses the socket, so
    `connection.closed` can say False for a connection that is already
    dead. A cheap query is the reliable test.
    """

    if connection.closed:
        return False

    try:
        connection.execute("SELECT 1")
        return True
    except Exception:
        return False


def get_connection(database_url: str) -> psycopg.Connection:
    """A connection that has just been verified to work."""

    with _lock:
        connection = _connections.get(database_url)

        if connection is not None and _is_alive(connection):
            return connection

        if connection is not None:
            logger.info("Database connection was lost; reconnecting.")

            try:
                connection.close()
            except Exception:
                pass

        connection = psycopg.connect(
            database_url,
            autocommit=True,
            row_factory=dict_row,
        )
        _connections[database_url] = connection

        return connection


def get_checkpointer(database_url: str) -> PostgresSaver:
    with _lock:
        connection = get_connection(database_url)
        cached = _checkpointers.get(database_url)

        # Reuse the checkpointer only while it is still bound to the live
        # connection. After a reconnect it points at a dead one.
        if cached is not None and cached[0] is connection:
            return cached[1]

        checkpointer = PostgresSaver(connection)
        checkpointer.setup()
        _checkpointers[database_url] = (connection, checkpointer)

        return checkpointer


def get_session_checkpointer() -> PostgresSaver:
    """Checkpointer for whichever database URL the current session resolves to."""

    require("DATABASE_URL")

    return get_checkpointer(resolve_database_url())
