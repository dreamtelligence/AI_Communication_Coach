from __future__ import annotations

import unittest

from coach_app.analysis import build_analysis_prompt
from coach_app.scenarios import (
    PAL_VERSION,
    SCENARIOS,
    build_pal_prompt,
    get_practice_side,
    get_scenario,
    get_stt_hotwords,
    list_public_scenarios,
)


class ScenarioPromptTests(unittest.TestCase):
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

    def test_faces_are_unique_across_all_scenarios(self) -> None:
        face_ids = [side["face_id"] for scenario in SCENARIOS for side in scenario["practice_sides"]]
        self.assertEqual(len(face_ids), len(set(face_ids)))


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
        self.assertEqual(labels["dating"], ["Interesse", "Gesprächsfluss", "Wirkung"])

    def test_analysis_prompt_uses_scenario_rubric(self) -> None:
        business = build_analysis_prompt("Avatar: Hallo\nNutzer: Hallo", "salary", "employee")
        dating = build_analysis_prompt("Avatar: Hallo\nNutzer: Hallo", "dating", "date_lena")
        self.assertIn("1. Empathie und emotionale Intelligenz", business)
        self.assertIn("1. Echtes Interesse und Zuhören", dating)
        self.assertNotIn("Ergebnisorientierung", dating)
        self.assertIn("Kriterium 1 → empathy_score", dating)

    def test_stt_hotwords_per_scenario(self) -> None:
        self.assertIn("Dating-App", get_stt_hotwords(get_scenario("dating")))
        self.assertIn("Gehaltsverhandlung", get_stt_hotwords(get_scenario("salary")))


if __name__ == "__main__":
    unittest.main()
