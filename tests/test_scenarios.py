from __future__ import annotations

import unittest

from coach_app.scenarios import PERSONA_VERSION, build_persona_prompt, get_practice_side, get_scenario


class ScenarioPromptTests(unittest.TestCase):
    def test_complaint_prompt_contains_progress_and_boundary_rules(self) -> None:
        scenario = get_scenario("complaint")
        prompt = build_persona_prompt(scenario, "support")

        self.assertEqual(PERSONA_VERSION, "v6")
        self.assertIn("Wiederhole dieselbe Forderung nicht mehrfach", prompt)
        self.assertIn("setzt du zuerst eine klare Grenze", prompt)
        self.assertIn("Wenn der Nutzer sagt, dass er Details per E-Mail sendet, akzeptierst du diese Zusage", prompt)
        self.assertIn("Wiederhole keine Versanddaten-Forderung", prompt)

    def test_salary_prompt_does_not_include_complaint_specific_artifacts(self) -> None:
        scenario = get_scenario("salary")
        prompt = build_persona_prompt(scenario, "employee")

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


if __name__ == "__main__":
    unittest.main()
