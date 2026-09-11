from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from app.routers.actions import (
    _BATCH_MAX_SUBREQUESTS,
    _EMPTY_SENDER,
    _fetch_flagged_email_senders,
    _flagged_message_id,
)


def _fake_http_client(post_side_effect) -> MagicMock:
    client = MagicMock()
    client.post = AsyncMock(side_effect=post_side_effect)
    return client


def _batch_response(responses: list[dict], status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value={"responses": responses})
    return response


def _sub_response(message_id: str, status: int, body: dict | None = None) -> dict:
    return {"id": message_id, "status": status, "body": body or {}}


def _message_body(name: str, address: str) -> dict:
    return {"from": {"emailAddress": {"name": name, "address": address}}}


class FlaggedMessageIdExtractionTests(unittest.TestCase):
    def test_returns_none_when_no_linked_resources(self) -> None:
        self.assertIsNone(_flagged_message_id({"linkedResources": []}))
        self.assertIsNone(_flagged_message_id({}))
        self.assertIsNone(_flagged_message_id({"linkedResources": "not-a-list"}))

    def test_returns_none_when_no_mail_application_name(self) -> None:
        task = {"linkedResources": [{"externalId": "abc", "applicationName": "SomeOtherApp"}]}
        self.assertIsNone(_flagged_message_id(task))

    def test_returns_none_when_missing_external_id(self) -> None:
        task = {"linkedResources": [{"applicationName": "Outlook"}]}
        self.assertIsNone(_flagged_message_id(task))

    def test_returns_external_id_for_outlook_resource(self) -> None:
        task = {"linkedResources": [{"externalId": "msg-1", "applicationName": "Outlook"}]}
        self.assertEqual(_flagged_message_id(task), "msg-1")

    def test_returns_external_id_for_mail_resource(self) -> None:
        task = {"linkedResources": [{"externalId": "msg-2", "applicationName": "Mail"}]}
        self.assertEqual(_flagged_message_id(task), "msg-2")

    def test_no_subrequest_target_when_only_non_mail_resource(self) -> None:
        task = {"linkedResources": [{"externalId": "msg-3", "applicationName": "SomeApp"}, {"applicationName": "Outlook"}]}
        # First matching resource fails the mail/outlook check; second has no externalId.
        self.assertIsNone(_flagged_message_id(task))


class FetchFlaggedEmailSendersTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_batch_for_20_or_fewer_messages(self) -> None:
        message_ids = [f"msg-{i}" for i in range(20)]
        responses = [_sub_response(mid, 200, _message_body(f"Name {i}", f"user{i}@example.com")) for i, mid in enumerate(message_ids)]
        http_client = _fake_http_client([_batch_response(responses)])

        result = await _fetch_flagged_email_senders(http_client, {"Authorization": "Bearer x"}, message_ids)

        self.assertEqual(http_client.post.await_count, 1)
        self.assertEqual(len(result), 20)
        self.assertEqual(result["msg-0"], {"senderName": "Name 0", "senderEmail": "user0@example.com"})
        self.assertEqual(result["msg-19"], {"senderName": "Name 19", "senderEmail": "user19@example.com"})

    async def test_multiple_batches_for_more_than_20_messages(self) -> None:
        message_ids = [f"msg-{i}" for i in range(45)]

        def side_effect(url, headers=None, json=None):
            chunk_ids = [item["id"] for item in json["requests"]]
            responses = [_sub_response(mid, 200, _message_body("N", f"{mid}@example.com")) for mid in chunk_ids]
            return _batch_response(responses)

        http_client = _fake_http_client(side_effect)

        result = await _fetch_flagged_email_senders(http_client, {"Authorization": "Bearer x"}, message_ids)

        # 45 messages / 20 per batch => 3 batches (20 + 20 + 5).
        self.assertEqual(http_client.post.await_count, 3)
        self.assertEqual(len(result), 45)
        self.assertEqual(result["msg-44"]["senderEmail"], "msg-44@example.com")

        for call in http_client.post.await_args_list:
            request_count = len(call.kwargs["json"]["requests"])
            self.assertLessEqual(request_count, _BATCH_MAX_SUBREQUESTS)

    async def test_failed_subresponse_returns_empty_sender_without_failing_others(self) -> None:
        responses = [
            _sub_response("msg-ok", 200, _message_body("Ok Sender", "ok@example.com")),
            _sub_response("msg-404", 404, {"error": {"message": "not found"}}),
        ]
        http_client = _fake_http_client([_batch_response(responses)])

        result = await _fetch_flagged_email_senders(http_client, {}, ["msg-ok", "msg-404"])

        self.assertEqual(result["msg-ok"], {"senderName": "Ok Sender", "senderEmail": "ok@example.com"})
        self.assertEqual(result["msg-404"], _EMPTY_SENDER)

    async def test_message_missing_from_batch_responses_defaults_to_empty_sender(self) -> None:
        # Graph returned a sub-response for only one of the two requested ids.
        responses = [_sub_response("msg-a", 200, _message_body("A", "a@example.com"))]
        http_client = _fake_http_client([_batch_response(responses)])

        result = await _fetch_flagged_email_senders(http_client, {}, ["msg-a", "msg-b"])

        self.assertEqual(result["msg-a"]["senderEmail"], "a@example.com")
        self.assertEqual(result["msg-b"], _EMPTY_SENDER)

    async def test_whole_batch_call_failure_returns_empty_senders_for_chunk(self) -> None:
        import httpx

        async def raise_error(url, headers=None, json=None):
            raise httpx.ConnectError("boom")

        http_client = _fake_http_client(raise_error)

        result = await _fetch_flagged_email_senders(http_client, {}, ["msg-x", "msg-y"])

        self.assertEqual(result["msg-x"], _EMPTY_SENDER)
        self.assertEqual(result["msg-y"], _EMPTY_SENDER)

    async def test_empty_message_id_list_makes_no_http_call(self) -> None:
        http_client = _fake_http_client([])

        result = await _fetch_flagged_email_senders(http_client, {}, [])

        http_client.post.assert_not_awaited()
        self.assertEqual(result, {})

    async def test_duplicate_message_ids_are_deduplicated_into_one_subrequest(self) -> None:
        responses = [_sub_response("msg-dup", 200, _message_body("Dup", "dup@example.com"))]
        http_client = _fake_http_client([_batch_response(responses)])

        await _fetch_flagged_email_senders(http_client, {}, ["msg-dup", "msg-dup", "msg-dup"])

        sent_ids = [item["id"] for item in http_client.post.await_args_list[0].kwargs["json"]["requests"]]
        self.assertEqual(sent_ids, ["msg-dup"])


if __name__ == "__main__":
    unittest.main()
