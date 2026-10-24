from __future__ import annotations

import unittest
from unittest import mock

from coach_app import tavus_client
from coach_app.scenarios import PAL_VERSION, get_scenario


def _ok(json_body: dict) -> mock.Mock:
    response = mock.Mock(ok=True, status_code=200)
    response.json.return_value = json_body
    return response


class TavusPayloadTests(unittest.TestCase):
    def test_pal_uses_current_tavus_models_and_german(self) -> None:
        scenario = get_scenario("salary")
        with mock.patch.object(tavus_client.requests, "post", return_value=_ok({"pal_id": "p123"})) as post:
            pal_id = tavus_client._create_pal("key", scenario, "employee")

        self.assertEqual(pal_id, "p123")
        url = post.call_args.args[0]
        payload = post.call_args.kwargs["json"]
        self.assertTrue(url.endswith("/v2/pals"))
        self.assertEqual(payload["languages"], ["de"])
        self.assertEqual(payload["default_face_id"], scenario["practice_sides"][0]["face_id"])
        self.assertEqual(payload["layers"]["llm"]["model"], "tavus-gemma-4")
        self.assertEqual(payload["layers"]["stt"]["stt_engine"], "tavus-auto")
        self.assertEqual(payload["layers"]["conversational_flow"]["turn_detection_model"], "sparrow-2")
        self.assertEqual(payload["layers"]["perception"]["perception_model"], "raven-1")

    def test_conversation_uses_pal_face_and_eu_policy(self) -> None:
        scenario = get_scenario("complaint")
        body = {"conversation_id": "c1", "conversation_url": "https://tavus.daily.co/c1"}
        with mock.patch.object(tavus_client.requests, "post", return_value=_ok(body)) as post:
            tavus_client.create_conversation("key", "p123", scenario, "support", sandbox=True)

        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["pal_id"], "p123")
        self.assertEqual(payload["face_id"], scenario["practice_sides"][0]["face_id"])
        self.assertEqual(payload["policy"], "eu")
        self.assertEqual(payload["properties"]["languages"], ["de"])
        self.assertNotIn("language", payload["properties"])
        self.assertTrue(payload["test_mode"])


class PalLookupTests(unittest.TestCase):
    def test_existing_pal_is_found_even_if_tavus_normalized_the_name(self) -> None:
        scenario = get_scenario("salary")
        listing = _ok({"data": [{"pal_id": "p_old", "pal_name": f"TalkToMe {PAL_VERSION} Gehaltsverhandlung employee"}]})
        with mock.patch.object(tavus_client.requests, "get", return_value=listing), \
             mock.patch.object(tavus_client.requests, "post") as post:
            pal_id = tavus_client.ensure_pal("key", scenario, "employee")

        self.assertEqual(pal_id, "p_old")
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
