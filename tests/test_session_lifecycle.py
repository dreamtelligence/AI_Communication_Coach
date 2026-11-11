import os
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from coach_app.security import issue_session_token
from coach_app.session_lifecycle import SessionLeases, session_routes
from coach_app.tavus_client import TavusError


class Store(dict):
    def put(self, key, value):
        self[key] = value


class SessionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.leases = SessionLeases(self.store, lambda: "test-key")
        self.key = "c123456789"

    def test_disconnected_call_expires_but_live_call_is_retained(self):
        with patch("coach_app.session_lifecycle.time.time", return_value=100):
            self.leases.start(self.key)
            self.leases.start("clive12345")
        with patch("coach_app.session_lifecycle.time.time", return_value=200):
            self.assertTrue(self.leases.renew("clive12345"))
        with patch("coach_app.session_lifecycle.time.time", return_value=221), \
             patch("coach_app.session_lifecycle.end_conversation") as end:
            self.assertEqual(self.leases.expire(), {"ended": 1, "failed": 0})
        end.assert_called_once_with("test-key", self.key)
        self.assertNotIn(self.key, self.store)
        self.assertIn("clive12345", self.store)

    def test_expired_or_missing_lease_cannot_be_resurrected(self):
        self.store[self.key] = 100
        with patch("coach_app.session_lifecycle.time.time", return_value=101):
            self.assertFalse(self.leases.renew(self.key))
            self.assertFalse(self.leases.renew("unknown"))
        self.assertEqual(self.store[self.key], 100)

    def test_failed_provider_end_is_retried_on_next_sweep(self):
        self.store[self.key] = 1
        with patch("coach_app.session_lifecycle.end_conversation", side_effect=TavusError("offline")):
            self.assertEqual(self.leases.expire(), {"ended": 0, "failed": 1})
        self.assertIn(self.key, self.store)
        with patch("coach_app.session_lifecycle.end_conversation"):
            self.assertEqual(self.leases.expire(), {"ended": 1, "failed": 0})

    def test_failed_registration_closes_untracked_provider_call(self):
        with patch.object(self.store, "put", side_effect=OSError("unavailable")), \
             patch("coach_app.session_lifecycle.end_conversation") as end:
            with self.assertRaises(OSError):
                self.leases.start(self.key)
        end.assert_called_once_with("test-key", self.key)

    def test_end_and_heartbeat_require_the_conversations_own_token(self):
        app = FastAPI()
        app.include_router(session_routes(self.leases))
        client = TestClient(app)
        with patch.dict(os.environ, {"SESSION_SECRET": "fixture"}), \
             patch("coach_app.session_lifecycle.end_conversation") as end:
            other = {"X-Session-Token": issue_session_token("cother1234")}
            for action in ["end", "heartbeat"]:
                self.assertEqual(client.post(f"/api/session/{self.key}/{action}").status_code, 403)
                self.assertEqual(client.post(f"/api/session/{self.key}/{action}", headers=other).status_code, 403)
            end.assert_not_called()
            headers = {"X-Session-Token": issue_session_token(self.key)}
            self.assertEqual(client.post(f"/api/session/{self.key}/heartbeat", headers=headers).status_code, 410)
            self.leases.start(self.key)
            self.assertEqual(client.post(f"/api/session/{self.key}/heartbeat", headers=headers).status_code, 200)
            self.assertEqual(client.post(f"/api/session/{self.key}/end", headers=headers).status_code, 200)
            self.assertNotIn(self.key, self.store)


if __name__ == "__main__":
    unittest.main()
