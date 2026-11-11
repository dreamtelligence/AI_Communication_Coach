from __future__ import annotations

import unittest

from coach_app.analysis import build_analysis_prompt
from coach_app.scenarios import (
    PAL_VERSION,
    SCENARIOS,
    build_pal_prompt,
    build_conversation_context,
    get_practice_side,
    get_scenario,
    get_stt_hotwords,
    list_public_scenarios,
    scenario_side_payload,
)


class ScenarioPromptTests(unittest.TestCase):
    def test_business_briefings_follow_the_selected_role_through_public_and_session_payloads(self) -> None:
        public = {scenario["id"]: scenario for scenario in list_public_scenarios()}
        for scenario_id in ("salary", "complaint"):
            scenario = get_scenario(scenario_id)
            self.assertEqual(public[scenario_id]["briefing"], scenario.get("briefing"))
            for side in scenario["practice_sides"]:
                with self.subTest(scenario=scenario_id, side=side["id"]):
                    selected = next(s for s in public[scenario_id]["practice_sides"] if s["id"] == side["id"])
                    self.assertEqual(selected["briefing"], side["briefing"])
                    self.assertEqual(scenario_side_payload(scenario, side["id"])["briefing"], side["briefing"])
                    context = build_conversation_context(scenario, side["id"])
                    self.assertIn(side["briefing"], context)
                    self.assertIn("die Du-Ansprache meint den Menschen, nicht dich als Avatar", context)
            self.assertNotEqual(scenario["practice_sides"][0]["briefing"], scenario["practice_sides"][1]["briefing"])

    def test_complaint_prompt_contains_progress_and_boundary_rules(self) -> None:
        scenario = get_scenario("complaint")
        prompt = build_pal_prompt(scenario, "support")

        self.assertEqual(PAL_VERSION, "v9")
        self.assertIn("Wiederhole dieselbe Forderung nicht mehrfach", prompt)
        self.assertIn("setzt du zuerst eine klare Grenze", prompt)
        self.assertIn("dass Details per E-Mail kommen, akzeptierst du diese Zusage", prompt)
        self.assertIn("Barista Pro X", prompt)
        self.assertIn("end_call", prompt)
        self.assertIn("Spracherkennung macht manchmal Fehler", prompt)
        self.assertIn("Wiederhole keine Versanddaten-Forderung", prompt)

    def test_salary_prompt_does_not_include_complaint_specific_artifacts(self) -> None:
        scenario = get_scenario("salary")
        prompt = build_pal_prompt(scenario, "employee")

        self.assertIn("gewuenschtem Gehaltskorridor", prompt)
        self.assertIn("Budgetgrenzen", prompt)
        self.assertNotIn("Auftragsnummer und Sendungsnummer", prompt)
        self.assertNotIn("Tracking-Link", prompt)

    def test_all_practice_sides_have_interaction_rules(self) -> None:
        for scenario_id in ("salary", "complaint"):
            scenario = get_scenario(scenario_id)
            for side in scenario["practice_sides"]:
                practice_side = get_practice_side(scenario, side["id"])
                self.assertTrue(practice_side["interaction_rules"].strip())

    def test_salary_prompt_has_no_duplicated_role_text(self) -> None:
        scenario = get_scenario("salary")
        side = get_practice_side(scenario, "employee")
        prompt = build_pal_prompt(scenario, "employee")
        self.assertEqual(prompt.count(side["avatar_role"]), 1)
        self.assertNotIn("{", prompt)

    def test_every_avatar_role_has_its_own_face(self) -> None:
        face_ids = [
            side["face_id"]
            for scenario_id in ("salary", "complaint")
            for side in get_scenario(scenario_id)["practice_sides"]
        ]
        self.assertEqual(len(face_ids), 4)
        self.assertEqual(len(set(face_ids)), 4)

    def test_different_characters_have_unique_faces(self) -> None:
        # Dr. Meier also interviews applicants; the same character keeps his original face.
        face_ids = [side["face_id"] for scenario in SCENARIOS if scenario["id"] != "interview" for side in scenario["practice_sides"]]
        self.assertEqual(len(face_ids), len(set(face_ids)))
        self.assertEqual(get_practice_side(get_scenario("interview"))["face_id"], get_practice_side(get_scenario("salary"))["face_id"])


class DatingScenarioTests(unittest.TestCase):
    def test_dating_prompt_uses_own_template_with_guardrails(self) -> None:
        scenario = get_scenario("dating")
        self.assertEqual(scenario["id"], "dating")
        for side in scenario["practice_sides"]:
            prompt = build_pal_prompt(scenario, side["id"])
            self.assertIn("ersten Video-Date", prompt)
            self.assertIn("sexuelle Themen", prompt)
            self.assertIn("baust keine Beziehung auf", prompt)
            self.assertIn("end_call", prompt)
            self.assertNotIn("Eine Einigung ist erreichbar", prompt)
            self.assertNotIn("{", prompt)

    def test_business_prompts_keep_default_template(self) -> None:
        prompt = build_pal_prompt(get_scenario("complaint"), "support")
        self.assertIn("Kommunikationstraining", prompt)
        self.assertNotIn("Video-Date", prompt)

    def test_public_scenarios_expose_rubric_labels(self) -> None:
        labels = {s["id"]: [r["label"] for r in s["rubric"]] for s in list_public_scenarios()}
        self.assertEqual(labels["salary"], ["Empathie", "Klarheit", "Ergebnis"])
        self.assertNotIn("dating", labels)
        self.assertEqual(labels["interview"], ["Stellenbezug", "Klarheit", "Fachliche Substanz"])

    def test_analysis_prompt_uses_scenario_rubric(self) -> None:
        business = build_analysis_prompt("Avatar: Hallo\nNutzer: Hallo", "salary", "employee")
        dating = build_analysis_prompt("Avatar: Hallo\nNutzer: Hallo", "dating", "date_lena")
        self.assertIn("1. Empathie und emotionale Intelligenz", business)
        self.assertIn("1. Echtes Interesse und Zuhören", dating)
        self.assertNotIn("Ergebnisorientierung", dating)
        self.assertIn("Kriterium 1 → empathy_score", dating)
        self.assertIn("mit „du“ an", dating)
        self.assertIn("mit „Sie“ an", business)

    def test_stt_hotwords_per_scenario(self) -> None:
        self.assertIn("Dating-App", get_stt_hotwords(get_scenario("dating")))
        self.assertIn("Gehaltsverhandlung", get_stt_hotwords(get_scenario("salary")))


if __name__ == "__main__":
    unittest.main()
