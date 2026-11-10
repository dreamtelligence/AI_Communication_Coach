from __future__ import annotations

import json
import unittest
from unittest import mock

from coach_app.analysis import INTERVIEW_FIELDS, build_analysis_prompt, parse_analysis_json
from coach_app.scenarios import build_pal_prompt, get_scenario, list_public_scenarios, scenario_side_payload
from coach_app.schemas import AnalysisResult
from coach_app.tavus_client import create_conversation


class InterviewScenarioTests(unittest.TestCase):
    def test_job_and_criteria_reach_both_public_payloads_and_prompts(self) -> None:
        scenario = get_scenario("interview")
        public = next(s for s in list_public_scenarios() if s["id"] == "interview")
        session = scenario_side_payload(scenario, "applicant")
        for payload in (public, session):
            self.assertEqual(payload["briefing"], scenario["briefing"])
            self.assertEqual([r["label"] for r in payload["rubric"]], ["Stellenbezug", "Klarheit", "Fachliche Substanz"])
        live = build_pal_prompt(scenario, "applicant")
        analysis = build_analysis_prompt("user: Mein Projekt ist eine Serviceplattform.", "interview", "applicant")
        self.assertIn(scenario["briefing"], live)
        self.assertIn(scenario["briefing"], analysis)
        self.assertNotIn("{", live)
        self.assertIn("end_call", live)
        self.assertIn("Welche Fragen haben Sie an uns?", live)
        self.assertIn("keinen Zugriff auf GitHub", live)
        self.assertIn("Nicht gefragt heißt nicht schlecht beantwortet", analysis)
        self.assertNotIn("verbindliche Vereinbarung", analysis)

    def test_conversation_opens_the_interview_and_keeps_disclosure_policy(self) -> None:
        response = mock.Mock(ok=True)
        response.json.return_value = {"conversation_id": "c123", "conversation_url": "https://tavus.daily.co/test"}
        with mock.patch("coach_app.tavus_client.requests.post", return_value=response) as post:
            create_conversation("test-key", "test-pal", get_scenario("interview"), "applicant", sandbox=True)
        payload = post.call_args.kwargs["json"]
        self.assertIn("Fullstack-Stelle", payload["custom_greeting"])
        self.assertEqual(payload["policy"], "eu")
        self.assertTrue(payload["test_mode"])

    def test_analysis_keeps_the_end_of_a_long_interview(self) -> None:
        transcript = "assistant: Wie sind Sie vorgegangen?\nuser: " + "Ein Projektdetail. " * 500
        transcript += "\nassistant: Ihre Fragen?\nuser: Wie läuft ein Code-Review bei Ihnen ab?"
        self.assertIn("Wie läuft ein Code-Review bei Ihnen ab?", build_analysis_prompt(transcript, "interview"))


class InterviewEvidenceTests(unittest.TestCase):
    def result(self, **overrides):
        quote = "Ich habe den Zugriff vor der Datenbankabfrage geprüft."
        payload = {
            "empathy_score": None, "empathy_feedback": "Nicht gefragt.",
            "clarity_score": 7, "clarity_feedback": f'„{quote}“ beschreibt den Ablauf verständlich.',
            "result_score": 8, "result_feedback": f'„{quote}“ ist ein konkreter Sicherheitsansatz.',
            "evidence": {"clarity": [quote], "result": [quote]},
            "summary": "Konkretes Vorgehen, Motivation wurde noch nicht gefragt.",
        }
        payload.update(overrides)
        for legacy, domain in INTERVIEW_FIELDS.items():
            for suffix in ("score", "feedback"):
                payload[f"{domain}_{suffix}"] = payload.pop(f"{legacy}_{suffix}")
        evidence = payload.get("evidence")
        if isinstance(evidence, dict):
            payload["evidence"] = {INTERVIEW_FIELDS[key]: value for key, value in evidence.items()}
        return parse_analysis_json(json.dumps(payload), interview_transcript=f"assistant: Hallo.\nuser: {quote}")

    def test_verified_scores_survive_and_unassessed_is_null(self) -> None:
        result = self.result()
        self.assertEqual(result["clarity_score"], 7)
        self.assertEqual(result["result_score"], 8)
        self.assertIsNone(result["empathy_score"])
        self.assertEqual(len(result["evidence"]["result"]), 1)
        AnalysisResult(**result)

    def test_missing_invented_or_avatar_only_quotes_cannot_support_scores(self) -> None:
        for evidence in ({}, {"clarity": ["Erfunden."], "result": ["Hallo."]}, {"clarity": "kein Array"}):
            with self.subTest(evidence=evidence):
                result = self.result(evidence=evidence)
                self.assertIsNone(result["clarity_score"])
                self.assertIsNone(result["result_score"])
                self.assertNotIn("Konkretes Vorgehen", result["summary"])

    def test_verified_quote_is_added_to_visible_feedback(self) -> None:
        result = self.result(result_feedback="Ein konkreter Sicherheitsansatz.")
        self.assertEqual(result["result_score"], 8)
        self.assertIn("Beleg: „Ich habe den Zugriff vor der Datenbankabfrage geprüft.“", result["result_feedback"])

    def test_empty_feedback_cannot_support_a_score(self) -> None:
        for feedback in (None, "", "   "):
            with self.subTest(feedback=feedback):
                self.assertIsNone(self.result(result_feedback=feedback)["result_score"])

    def test_asr_suspect_quotes_are_excluded_without_inventing_a_replacement(self) -> None:
        result = self.result(asr_notes=["Ich habe den Zugriff vor der Datenbankabfrage geprüft. – unklar erkannt"])
        self.assertIsNone(result["result_score"])

    def test_invalid_scores_cannot_be_clamped_into_a_valid_interview_rating(self) -> None:
        for score in (0, 11, True, "8", 7.5, None):
            with self.subTest(score=score):
                self.assertIsNone(self.result(result_score=score)["result_score"])

    def test_invented_original_phrasing_is_dropped(self) -> None:
        result = self.result(better_phrasings=[{"original": "Ich habe 20 Jahre Erfahrung.", "better": "Ich habe viel Erfahrung."}])
        self.assertEqual(result["better_phrasings"], [])

    def test_no_user_statements_gives_no_scores(self) -> None:
        result = parse_analysis_json(json.dumps({"technical_depth_score": 9}), interview_transcript="assistant: Hallo.")
        self.assertTrue(all(result[f"{key}_score"] is None for key in ("empathy", "clarity", "result")))


if __name__ == "__main__":
    unittest.main()
