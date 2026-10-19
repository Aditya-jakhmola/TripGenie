import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import psycopg

from src.clients import checkpointer

URL = "postgresql://user:pass@host/db"


class FakeConnection:
    """A stand-in for a psycopg connection that can 'die' while idle."""

    def __init__(self, alive=True, closed=False):
        self.alive = alive
        self.closed = closed
        self.pings = 0
        self.close_calls = 0

    def execute(self, sql):
        self.pings += 1

        if not self.alive:
            raise psycopg.OperationalError("the connection is closed")

    def close(self):
        self.close_calls += 1
        self.closed = True


class StateResettingTestCase(unittest.TestCase):
    def setUp(self):
        checkpointer._connections.clear()
        checkpointer._checkpointers.clear()
        self.addCleanup(checkpointer._connections.clear)
        self.addCleanup(checkpointer._checkpointers.clear)

    def connect_returning(self, *connections):
        patcher = patch.object(
            checkpointer.psycopg, "connect", side_effect=list(connections)
        )
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock


class GetConnectionTests(StateResettingTestCase):
    def test_first_call_opens_a_connection_with_autocommit(self):
        conn = FakeConnection()
        connect = self.connect_returning(conn)

        self.assertIs(checkpointer.get_connection(URL), conn)

        connect.assert_called_once()
        self.assertEqual(connect.call_args.args[0], URL)
        self.assertTrue(connect.call_args.kwargs["autocommit"])

    def test_a_healthy_connection_is_reused(self):
        conn = FakeConnection()
        connect = self.connect_returning(conn)

        first = checkpointer.get_connection(URL)
        second = checkpointer.get_connection(URL)

        self.assertIs(first, second)
        self.assertEqual(connect.call_count, 1)
        self.assertEqual(conn.pings, 1)

    def test_a_connection_the_server_dropped_is_replaced(self):
        # The case that broke the live site: the database closes an idle
        # connection, but conn.closed still says False until it is used.
        old, new = FakeConnection(), FakeConnection()
        connect = self.connect_returning(old, new)

        self.assertIs(checkpointer.get_connection(URL), old)

        old.alive = False

        self.assertIs(checkpointer.get_connection(URL), new)
        self.assertEqual(connect.call_count, 2)
        self.assertEqual(old.close_calls, 1)

    def test_a_connection_known_to_be_closed_is_replaced(self):
        old, new = FakeConnection(), FakeConnection()
        self.connect_returning(old, new)

        checkpointer.get_connection(URL)
        old.closed = True

        self.assertIs(checkpointer.get_connection(URL), new)

    def test_a_failure_while_closing_the_dead_connection_is_ignored(self):
        old, new = FakeConnection(), FakeConnection()
        old.close = MagicMock(side_effect=OSError("already gone"))
        self.connect_returning(old, new)

        checkpointer.get_connection(URL)
        old.alive = False

        self.assertIs(checkpointer.get_connection(URL), new)

    def test_each_database_url_gets_its_own_connection(self):
        a, b = FakeConnection(), FakeConnection()
        self.connect_returning(a, b)

        self.assertIs(checkpointer.get_connection("postgresql://one"), a)
        self.assertIs(checkpointer.get_connection("postgresql://two"), b)
        self.assertIs(checkpointer.get_connection("postgresql://one"), a)


class GetCheckpointerTests(StateResettingTestCase):
    def setUp(self):
        super().setUp()

        patcher = patch.object(
            checkpointer,
            "PostgresSaver",
            side_effect=lambda conn: SimpleNamespace(conn=conn, setup=MagicMock()),
        )
        self.saver_class = patcher.start()
        self.addCleanup(patcher.stop)

    def test_it_is_created_once_and_set_up_once(self):
        self.connect_returning(FakeConnection())

        first = checkpointer.get_checkpointer(URL)
        second = checkpointer.get_checkpointer(URL)

        self.assertIs(first, second)
        self.assertEqual(self.saver_class.call_count, 1)
        first.setup.assert_called_once()

    def test_it_is_rebuilt_when_the_connection_is_replaced(self):
        old, new = FakeConnection(), FakeConnection()
        self.connect_returning(old, new)

        first = checkpointer.get_checkpointer(URL)
        self.assertIs(first.conn, old)

        old.alive = False

        second = checkpointer.get_checkpointer(URL)

        self.assertIsNot(first, second)
        self.assertIs(second.conn, new)
        self.assertEqual(self.saver_class.call_count, 2)

    def test_session_checkpointer_uses_the_resolved_database_url(self):
        sentinel = object()

        with patch.object(checkpointer, "require"), \
             patch.object(checkpointer, "resolve_database_url", return_value=URL), \
             patch.object(checkpointer, "get_checkpointer", return_value=sentinel) as get:
            self.assertIs(checkpointer.get_session_checkpointer(), sentinel)

        get.assert_called_once_with(URL)


if __name__ == "__main__":
    unittest.main()
