from __future__ import annotations

import unittest

from coach_app.scenarios import PAL_VERSION, build_pal_prompt, get_practice_side, get_scenario


class ScenarioPromptTests(unittest.TestCase):
    def test_complaint_prompt_contains_progress_and_boundary_rules(self) -> None:
        scenario = get_scenario("complaint")
        prompt = build_pal_prompt(scenario, "support")

        self.assertEqual(PAL_VERSION, "v8")
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


if __name__ == "__main__":
    unittest.main()
