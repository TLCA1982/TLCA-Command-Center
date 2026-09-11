from __future__ import annotations

import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.db import get_conn
from app.main import app
from app.services import microsoft_metadata


class _FakeGraphClient:
    def get_access_token(self) -> str:
        return "fake-token"


def _lists_payload(list_id: str) -> dict:
    return {"value": [{"id": list_id, "displayName": "My List"}]}


def _tasks_payload(tasks: list[dict]) -> dict:
    return {"value": tasks}


class ActionsMetadataBatchingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def setUp(self) -> None:
        self.list_id = f"list-{uuid.uuid4()}"
        self.task_with_meta_id = f"task-{uuid.uuid4()}"
        self.task_without_meta_id = f"task-{uuid.uuid4()}"
        microsoft_metadata.upsert(
            self.task_with_meta_id,
            customer="Acme BV",
            contact="Jane Doe",
            action_type="Bezoek",
        )

    def tearDown(self) -> None:
        with get_conn() as conn:
            conn.execute(
                "DELETE FROM microsoft_metadata WHERE ms_id IN (:a, :b)",
                {"a": self.task_with_meta_id, "b": self.task_without_meta_id},
            )

    def _tasks(self) -> list[dict]:
        return [
            {
                "id": self.task_with_meta_id,
                "title": "Task with metadata",
                "status": "notStarted",
                "importance": "normal",
            },
            {
                "id": self.task_without_meta_id,
                "title": "Task without metadata",
                "status": "notStarted",
                "importance": "normal",
            },
        ]

    def _fake_http_get(self, url: str, headers=None, params=None):
        if url == "https://graph.microsoft.com/v1.0/me/todo/lists":
            payload = _lists_payload(self.list_id)
        elif url == f"https://graph.microsoft.com/v1.0/me/todo/lists/{self.list_id}/tasks":
            payload = _tasks_payload(self._tasks())
        else:
            raise AssertionError(f"Unexpected URL requested in test: {url}")
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json = MagicMock(return_value=payload)
        return response

    def _run_with_mocks(self, path: str):
        with patch("app.routers.actions.MicrosoftGraphClient", return_value=_FakeGraphClient()), \
             patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=self._fake_http_get)), \
             patch(
                 "app.services.microsoft_metadata.get_many",
                 wraps=microsoft_metadata.get_many,
             ) as get_many_spy, \
             patch("app.services.microsoft_metadata.get") as get_spy:
            response = self.client.get(path)
            return response, get_many_spy, get_spy

    def test_microsoft_actions_use_bulk_metadata_lookup(self) -> None:
        response, get_many_spy, get_spy = self._run_with_mocks("/actions/microsoft")

        self.assertEqual(response.status_code, 200, response.text)
        get_spy.assert_not_called()
        get_many_spy.assert_called_once()

        actions_by_id = {item["id"]: item for item in response.json()}
        with_meta = actions_by_id[self.task_with_meta_id]
        self.assertEqual(with_meta["customer"], "Acme BV")
        self.assertEqual(with_meta["contact"], "Jane Doe")
        self.assertEqual(with_meta["actionType"], "Bezoek")

        without_meta = actions_by_id[self.task_without_meta_id]
        self.assertEqual(without_meta["customer"], "")
        self.assertEqual(without_meta["contact"], "")
        self.assertEqual(without_meta["actionType"], "")

    def test_combined_actions_do_not_repeat_metadata_lookup(self) -> None:
        response, get_many_spy, get_spy = self._run_with_mocks("/actions/")

        self.assertEqual(response.status_code, 200, response.text)
        # get_all_actions() must rely solely on the metadata already merged by
        # get_microsoft_actions(); it must not call microsoft_metadata.get()
        # (per-item) or microsoft_metadata.get_many() a second time.
        get_spy.assert_not_called()
        get_many_spy.assert_called_once()

        actions_by_id = {item["id"]: item for item in response.json()}
        with_meta = actions_by_id[self.task_with_meta_id]
        self.assertEqual(with_meta["customer"], "Acme BV")
        self.assertEqual(with_meta["contact"], "Jane Doe")
        self.assertEqual(with_meta["actionType"], "Bezoek")


class MicrosoftMetadataGetManyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.id_a = f"meta-{uuid.uuid4()}"
        self.id_b = f"meta-{uuid.uuid4()}"
        self.missing_id = f"meta-{uuid.uuid4()}"
        microsoft_metadata.upsert(self.id_a, customer="Company A", contact="Alice", action_type="Bezoek")
        microsoft_metadata.upsert(self.id_b, customer="Company B", contact="Bob", action_type="Belactie")

    def tearDown(self) -> None:
        with get_conn() as conn:
            conn.execute(
                "DELETE FROM microsoft_metadata WHERE ms_id IN (:a, :b)",
                {"a": self.id_a, "b": self.id_b},
            )

    def test_get_many_returns_rows_for_known_ids_only(self) -> None:
        result = microsoft_metadata.get_many([self.id_a, self.id_b, self.missing_id])

        self.assertEqual(set(result.keys()), {self.id_a, self.id_b})
        self.assertEqual(result[self.id_a]["customer"], "Company A")
        self.assertEqual(result[self.id_b]["contact"], "Bob")

    def test_get_many_matches_individual_get_results(self) -> None:
        bulk = microsoft_metadata.get_many([self.id_a, self.id_b])
        individual_a = microsoft_metadata.get(self.id_a)
        individual_b = microsoft_metadata.get(self.id_b)

        self.assertEqual(bulk[self.id_a], individual_a)
        self.assertEqual(bulk[self.id_b], individual_b)

    def test_get_many_with_empty_input_returns_empty_dict_without_querying(self) -> None:
        self.assertEqual(microsoft_metadata.get_many([]), {})
        self.assertEqual(microsoft_metadata.get_many([None, ""]), {})


if __name__ == "__main__":
    unittest.main()
