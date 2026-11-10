"""Opt-in paid provider regression check; only fictional transcripts, no Tavus call.

Run from the repository root: PYTHONPATH=. .venv/bin/python scripts/evaluate_interview.py
Requires GEMINI_API_KEY. The assertions are review examples, not a validated hiring scale.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from coach_app.analysis import build_analysis_prompt, generate_with_gemini, parse_analysis_json


def evaluate() -> list[dict]:
    cases = json.loads((Path(__file__).resolve().parents[1] / "tests/fixtures/interview_cases.json").read_text())
    results = []
    for case in cases:
        transcript = case["transcript"]
        raw = generate_with_gemini(os.environ["GEMINI_API_KEY"], build_analysis_prompt(transcript, "interview", "applicant"))
        result = parse_analysis_json(raw, interview_transcript=transcript)
        scores = [result[f"{key}_score"] for key in ("empathy", "clarity", "result")]
        print(json.dumps({"case": case["id"], "scores": scores, "evidence": result["evidence"]}, ensure_ascii=False), flush=True)
        expected = case["expect"]
        if expected == "unrated":
            assert scores == [None, None, None], (case["id"], scores)
        elif expected == "unsafe":
            assert scores[2] is not None and scores[2] <= 4, (case["id"], scores)
            assert scores[0] is None, (case["id"], "Motivation not assessed", scores)
            assert scores[1] is not None and scores[1] >= 5, (case["id"], "Do not penalize clarity for technical errors", scores)
        elif expected == "strong":
            assert all(s is not None and s >= 7 for s in scores), (case["id"], scores)
        elif expected == "weak":
            assert all(s is not None and s <= 6 for s in scores), (case["id"], scores)
            assert scores[1] >= 3, (case["id"], "Vague but understandable", scores)
        else:
            raise ValueError(f"Unknown expectation: {expected}")
        results.append({"case": case["id"], "scores": scores})
    assert len(results) == 5
    return results


if __name__ == "__main__":
    evaluate()
    print("PASS: five fictional interview cases. No hiring validity claim.")
