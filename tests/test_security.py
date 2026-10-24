from __future__ import annotations

import os
import unittest
from unittest import mock

from fastapi import HTTPException

from coach_app import security


def _request(headers: dict[str, str], host: str = "10.0.0.1") -> mock.Mock:
    request = mock.Mock()
    request.headers = headers
    request.client = mock.Mock(host=host)
    return request


class SessionTokenTests(unittest.TestCase):
    def setUp(self) -> None:
        patcher = mock.patch.dict(os.environ, {"TAURUS_API_KEY": "test-key"}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_valid_token_is_accepted(self) -> None:
        token = security.issue_session_token("c1811e26be5a5439")
        security.require_session_token(_request({"X-Session-Token": token}), "c1811e26be5a5439")

    def test_token_of_other_conversation_is_rejected(self) -> None:
        token = security.issue_session_token("c1811e26be5a5439")
        with self.assertRaises(HTTPException) as ctx:
            security.require_session_token(_request({"X-Session-Token": token}), "ce10fe9d1fc114b9")
        self.assertEqual(ctx.exception.status_code, 403)

    def test_missing_token_is_rejected(self) -> None:
        with self.assertRaises(HTTPException):
            security.require_session_token(_request({}), "c1811e26be5a5439")


class ClientIpTests(unittest.TestCase):
    def test_uses_first_forwarded_ip(self) -> None:
        self.assertEqual(security.client_ip(_request({"x-forwarded-for": "203.0.113.5, 76.76.21.21"})), "203.0.113.5")

    def test_falls_back_to_socket_peer(self) -> None:
        self.assertEqual(security.client_ip(_request({})), "10.0.0.1")


if __name__ == "__main__":
    unittest.main()
