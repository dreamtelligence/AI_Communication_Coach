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


class RateLimiterTests(unittest.TestCase):
    def _req(self, path: str, ip: str) -> mock.Mock:
        request = _request({"x-forwarded-for": ip})
        request.url = mock.Mock(path=path)
        return request

    def test_global_cap_holds_even_with_spoofed_ips(self) -> None:
        limiter = security.InMemoryRateLimiter(limit=40, window_seconds=60, global_limits={"/api/session/create": 3})
        for i in range(3):
            limiter.check(self._req("/api/session/create", f"198.51.100.{i}"))
        with self.assertRaises(HTTPException) as ctx:
            limiter.check(self._req("/api/session/create", "198.51.100.99"))
        self.assertEqual(ctx.exception.status_code, 429)

    def test_other_paths_are_not_globally_capped(self) -> None:
        limiter = security.InMemoryRateLimiter(limit=40, window_seconds=60, global_limits={"/api/session/create": 1})
        for i in range(5):
            limiter.check(self._req("/api/scenarios", f"198.51.100.{i}"))

    def test_stale_keys_are_evicted(self) -> None:
        limiter = security.InMemoryRateLimiter(limit=40, window_seconds=60, global_limits={})
        limiter._requests = {"old:/api/x": security.deque([0.0])}
        limiter._evict(window_start=10.0)
        self.assertEqual(limiter._requests, {})


if __name__ == "__main__":
    unittest.main()
