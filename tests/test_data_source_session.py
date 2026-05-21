"""Tests for Data Source Pack session resolution."""
from __future__ import annotations

import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from data_sources.session import DataSourceSessionError, get_session_for_data_source, _mysql_url_for_data_source
from text2sql.dynamic.auto_debugger import AutoDebugger


def build_pack(source_type: str = "mysql", connection_ref: str = "config/.env"):
    return SimpleNamespace(
        manifest=SimpleNamespace(
            data_source_id="local_mysql_demo",
            type=source_type,
            connection_ref=connection_ref,
        )
    )


class DataSourceSessionTests(unittest.TestCase):
    def test_get_session_for_data_source_uses_business_mysql_session(self) -> None:
        calls: list[str] = []

        class FakeSession:
            def commit(self):
                calls.append("commit")

            def rollback(self):
                calls.append("rollback")

            def close(self):
                calls.append("close")

        with (
            patch("data_sources.session.get_data_source_pack", return_value=build_pack()),
            patch("data_sources.session._session_factory_for_mysql_data_source", return_value=lambda: FakeSession()),
        ):
            with get_session_for_data_source("local_mysql_demo") as session:
                self.assertIsInstance(session, FakeSession)

        self.assertEqual(calls, ["commit", "close"])

    def test_local_mysql_demo_uses_configured_db_url(self) -> None:
        with patch("data_sources.session.settings") as settings:
            settings.local_mysql_demo_db_url = "mysql+pymysql://root:@localhost:3306/zhicetong_t2s?charset=utf8mb4"
            self.assertIn("/zhicetong_t2s?", _mysql_url_for_data_source("local_mysql_demo"))

    def test_get_session_for_data_source_rejects_unknown_pack(self) -> None:
        with patch("data_sources.session.get_data_source_pack", return_value=None):
            with self.assertRaises(DataSourceSessionError):
                with get_session_for_data_source("missing_source"):
                    pass

    def test_get_session_for_data_source_rejects_non_mysql_pack(self) -> None:
        with patch("data_sources.session.get_data_source_pack", return_value=build_pack(source_type="excel")):
            with self.assertRaises(DataSourceSessionError):
                with get_session_for_data_source("excel_source"):
                    pass


class AutoDebuggerDataSourceTests(unittest.TestCase):
    def test_auto_debugger_executes_with_requested_data_source(self) -> None:
        captured: list[str] = []

        class FakeAgent:
            def generate_sql(self, _plan_item, _person_id, _error_feedback, data_source_id=None):
                return "SELECT 'id_card_replace' AS id_card"

        class FakeResult:
            def keys(self):
                return ["id_card"]

            def fetchall(self):
                return [("42090219760310000D",)]

        class FakeSession:
            def execute(self, _sql):
                return FakeResult()

        @contextmanager
        def fake_get_session_for_data_source(data_source_id):
            captured.append(data_source_id)
            yield FakeSession()

        plan_item = SimpleNamespace(
            rule_id="P001_MUST_001",
            rule_name="生存状态",
            rule_description="基础核验",
            allowed_fields=[],
        )
        debugger = AutoDebugger(agent=FakeAgent(), max_retries=1)

        with patch("text2sql.dynamic.auto_debugger.get_session_for_data_source", fake_get_session_for_data_source):
            sql, rows = debugger.execute_with_auto_fix(
                plan_item,
                "42090219760310000D",
                data_source_id="local_mysql_demo",
            )

        self.assertIn("42090219760310000D", sql)
        self.assertEqual(rows, [{"id_card": "42090219760310000D"}])
        self.assertEqual(captured, ["local_mysql_demo"])


if __name__ == "__main__":
    unittest.main()
