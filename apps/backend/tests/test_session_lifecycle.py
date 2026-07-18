from __future__ import annotations

from sqlalchemy import event

from tests.api_command_test_case import ApiCommandTestCase


class SessionLifecycleTest(ApiCommandTestCase):
    def test_request_sessions_return_connections_to_pool(self) -> None:
        for _ in range(5):
            response = self.client.get("/api/skills")
            self.assertEqual(response.status_code, 200)

        checked_out = getattr(self.engine.pool, "checkedout", None)
        self.assertIsNotNone(checked_out)
        self.assertEqual(checked_out(), 0)

    def test_skill_list_query_count_does_not_grow_per_skill(self) -> None:
        self.create_skill("query-count-one")
        single_count = self._request_query_count()
        self.create_skill("query-count-two")
        self.create_skill("query-count-three")
        multiple_count = self._request_query_count()

        self.assertEqual(multiple_count, single_count)

    def _request_query_count(self) -> int:
        statements: list[str] = []

        def record_statement(*args) -> None:
            statements.append(str(args[2]))

        event.listen(self.engine, "before_cursor_execute", record_statement)
        try:
            response = self.client.get("/api/skills")
            self.assertEqual(response.status_code, 200)
        finally:
            event.remove(self.engine, "before_cursor_execute", record_statement)
        return len(statements)
