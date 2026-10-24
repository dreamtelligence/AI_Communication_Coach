from __future__ import annotations

import json
import unittest

from coach_app.analysis import build_analysis_prompt, parse_analysis_json


class AnalysisTests(unittest.TestCase):
    def test_prompt_tells_model_not_to_punish_asr_errors(self) -> None:
        prompt = build_analysis_prompt("assistant: Ich bin sauer.\nuser: Ja, das ist sehr leicht.", "complaint", "support")
        self.assertIn("automatischen Spracherkennung", prompt)
        self.assertIn("asr_notes", prompt)
        self.assertIn("better_phrasings", prompt)
        self.assertIn("2-3: ignoriert oder verharmlost Gefühle", prompt)

    def test_parse_keeps_new_fields_and_drops_incomplete_phrasings(self) -> None:
        raw = json.dumps({
            "empathy_score": 12, "empathy_feedback": "e", "clarity_score": "6", "clarity_feedback": "c",
            "result_score": 7, "result_feedback": "r", "summary": "s",
            "better_phrasings": [
                {"original": "Ich schätze mal, drei Werktage.", "better": "Das Gerät ist bis Donnerstag bei Ihnen.", "why": "verbindlich"},
                {"original": "nur original"},
            ],
            "counterpart_journey": "sauer, dann versöhnlich",
            "asr_notes": ["'sehr leicht' vermutlich 'sehr ärgerlich'", " "],
        })
        result = parse_analysis_json(f"```json\n{raw}\n```")
        self.assertEqual(result["empathy_score"], 10)
        self.assertEqual(result["clarity_score"], 6)
        self.assertEqual(len(result["better_phrasings"]), 1)
        self.assertEqual(result["counterpart_journey"], "sauer, dann versöhnlich")
        self.assertEqual(result["asr_notes"], ["'sehr leicht' vermutlich 'sehr ärgerlich'"])

    def test_parse_handles_missing_new_fields(self) -> None:
        result = parse_analysis_json(json.dumps({"empathy_score": 5, "summary": "s"}))
        self.assertEqual(result["better_phrasings"], [])
        self.assertEqual(result["asr_notes"], [])


class AsrGuardTests(unittest.TestCase):
    def test_phrasing_of_misrecognized_sentence_is_dropped(self) -> None:
        raw = json.dumps({
            "asr_notes": ['"Auf den Service." – vermutlich "Auf Wiederhören"'],
            "better_phrasings": [
                {"original": "Auf den Service.", "better": "Auf Wiederhören!", "why": "x"},
                {"original": "Ich schätze mal, drei Werktage.", "better": "Bis Donnerstag.", "why": "y"},
            ],
        })
        result = parse_analysis_json(raw)
        self.assertEqual([p["original"] for p in result["better_phrasings"]], ["Ich schätze mal, drei Werktage."])


if __name__ == "__main__":
    unittest.main()
