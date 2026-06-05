import unittest

from coach_app.scenarios import get_practice_side, get_scenario, list_public_scenarios
from coach_app.analysis import build_analysis_prompt
from coach_app.transcript import parse_transcript, transcript_from_tavus_conversation


class TranscriptTests(unittest.TestCase):
    def test_parse_transcript_splits_user_and_avatar_lines(self) -> None:
        parsed = parse_transcript("Avatar: Ich bin frustriert.\nUser: Ich verstehe Ihren Ärger.")

        self.assertEqual(parsed["user_only"], "Ich verstehe Ihren Ärger.")
        self.assertEqual(parsed["avatar_only"], "[assistant]: Ich bin frustriert.")

    def test_tavus_transcript_from_verbose_events(self) -> None:
        conversation = {
            "events": [
                {
                    "event_type": "application.transcription_ready",
                    "properties": {
                        "transcript": [
                            {"role": "replica", "content": "Was schlagen Sie vor?"},
                            {"role": "user", "content": "Ich möchte eine faire Lösung finden."},
                        ]
                    },
                }
            ]
        }

        transcript = transcript_from_tavus_conversation(conversation)

        self.assertEqual(
            transcript,
            "assistant: Was schlagen Sie vor?\nuser: Ich möchte eine faire Lösung finden.",
        )

    def test_parse_transcript_filters_system_messages(self) -> None:
        parsed = parse_transcript(
            "system: Du bist in einem realistischen Kommunikationstraining.\n"
            "assistant: Ich bin wirklich sauer.\n"
            "user: Ich verstehe Ihren Ärger.\n"
            "system: The user's timezone is unknown."
        )

        self.assertEqual(
            parsed["full_transcript"],
            "assistant: Ich bin wirklich sauer.\nuser: Ich verstehe Ihren Ärger.",
        )
        self.assertNotIn("system:", parsed["full_transcript"])
        self.assertNotIn("realistischen Kommunikationstraining", parsed["full_transcript"])

    def test_analysis_prompt_uses_clean_transcript(self) -> None:
        prompt = build_analysis_prompt(
            "system: Geheimprompt\nassistant: Hallo\nuser: Guten Tag",
            "complaint",
            "support",
        )

        self.assertIn("assistant: Hallo", prompt)
        self.assertIn("user: Guten Tag", prompt)
        self.assertNotIn("system: Geheimprompt", prompt)

    def test_unknown_scenario_falls_back_to_default_demo_case(self) -> None:
        self.assertEqual(get_scenario("missing")["id"], "salary")

    def test_public_scenarios_are_reduced_to_two_demo_cases(self) -> None:
        scenario_ids = [scenario["id"] for scenario in list_public_scenarios()]

        self.assertEqual(scenario_ids, ["salary", "complaint"])

    def test_salary_scenario_has_manager_training_side(self) -> None:
        side = get_practice_side(get_scenario("salary"), "manager")

        self.assertIn("Führungskraft", side["label"])


if __name__ == "__main__":
    unittest.main()
