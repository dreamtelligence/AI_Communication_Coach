from __future__ import annotations

import json
from typing import Any

import requests

from coach_app.scenarios import get_practice_side, get_rubric, get_scenario
from coach_app.transcript import parse_transcript


DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
# gemini-3.5-flash with low thinking: ~4s and stable. gemini-3.8-flash took 40-120s+ in tests (24.10.2026).
GEMINI_MODEL = "gemini-3.5-flash"
GEMINI_FALLBACK_MODELS = (
    "gemini-2.5-flash",
)
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
REQUEST_TIMEOUT = 45


class AnalysisProviderError(RuntimeError):
    def __init__(self, provider: str, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


def build_analysis_prompt(text: str, scenario_id: str = "salary", practice_side_id: str | None = None) -> str:
    parsed = parse_transcript(text)
    scenario = get_scenario(scenario_id)
    side = get_practice_side(scenario, practice_side_id)
    user_text = parsed["user_only"] or "(Keine Nutzer-Aussagen identifiziert.)"
    avatar_text = parsed["avatar_only"] or "(Keine Avatar-Aussagen identifiziert.)"
    clean_transcript = parsed["full_transcript"] or "(Keine auswertbare Unterhaltung identifiziert.)"
    rubric_text = _rubric_text(scenario)
    return f"""Analysiere ein Live-Rollenspiel aus einem Kommunikationstraining.

SZENARIO: {scenario["title"]}
TRAINIERTE ROLLE DES NUTZERS: {side["user_role"]}
ZIEL DES NUTZERS: {side["user_goal"]}
ROLLE DES KI-AVATARS: {side["avatar_role"]}

DER KI-AVATAR sagte:
{avatar_text}

DER MENSCHLICHE NUTZER, der bewertet wird, sagte:
{user_text}

VOLLSTÄNDIGES TRANSKRIPT:
{clean_transcript[:6000]}

WICHTIG ZUM TRANSKRIPT
- Die Nutzer-Aussagen stammen aus einer automatischen Spracherkennung. Einzelne Wörter können falsch erkannt sein.
- Bestimme ZUERST die vermutlich falsch erkannten Aussagen: Sätze, die unsinnig wirken, nicht in den Zusammenhang passen oder auf die
  das Gegenüber verwirrt reagiert. Nimm sie in "asr_notes" auf und nenne, was vermutlich gemeint war.
- Aussagen aus "asr_notes" fließen in KEINEN Score, kein Feedback und keine Umformulierung ein. Bewerte an ihrer Stelle die vermutlich
  gemeinte Aussage. Reagiert das Gegenüber auf einen Erkennungsfehler, ist das nicht die Schuld des Nutzers.
- Füllwörter und abgebrochene Sätze gehören zu gesprochener Sprache. Bewerte sie nur, wenn sie das Gespräch spürbar schwächen.
- Ein KI-Hinweis des Avatars am Anfang („Ich bin ein KI-Avatar…“) gehört nicht zum Rollenspiel.

BEWERTE AUSSCHLIESSLICH DEN MENSCHLICHEN NUTZER (je 1-10)
{rubric_text}
Feld-Zuordnung im JSON: Kriterium 1 → empathy_score/empathy_feedback, Kriterium 2 → clarity_score/clarity_feedback, Kriterium 3 → result_score/result_feedback.
Belege jeden Score mit mindestens einem wörtlichen Zitat des Nutzers. Sei ehrlich, aber fair, und sprich den Nutzer mit „Sie“ an.

ZUSÄTZLICH
- "better_phrasings": zwei bis drei echte Sätze des Nutzers, die am meisten Wirkung gekostet haben, jeweils mit einer besseren,
  natürlich klingenden Formulierung und einem kurzen Grund. Keine falsch erkannten Sätze verwenden.
- "counterpart_journey": in ein bis zwei Sätzen, wie sich die Stimmung des Gegenübers entwickelt hat und welche Nutzer-Aussage der Wendepunkt war.

Gib nur JSON in dieser Form zurück:
{{"asr_notes":["..."],"empathy_score":7,"empathy_feedback":"...","clarity_score":6,"clarity_feedback":"...","result_score":8,"result_feedback":"...","summary":"...","better_phrasings":[{{"original":"...","better":"...","why":"..."}}],"counterpart_journey":"..."}}"""


def _rubric_text(scenario: dict[str, Any]) -> str:
    """Numbered scoring criteria; order matches the empathy/clarity/result JSON fields."""
    return "\n".join(
        f"{i}. {item['title']}\n   {item['levels']}" for i, item in enumerate(get_rubric(scenario), start=1)
    )


def build_fallback_prompt(scenario_id: str = "salary", practice_side_id: str | None = None) -> str:
    scenario = get_scenario(scenario_id)
    side = get_practice_side(scenario, practice_side_id)
    return f"""Das Transkript eines Tavus Live-Rollenspiels ist technisch noch nicht verfügbar.

SZENARIO: {scenario["title"]}
TRAINIERTE ROLLE DES NUTZERS: {side["user_role"]}
ZIEL DES NUTZERS: {side["user_goal"]}
ROLLE DES AVATARS: {side["avatar_role"]}

Erstelle eine klar als hypothetisch erkennbare Beispiel-Analyse für den menschlichen Nutzer.
Verwende realistische Scores und konkrete Verbesserungsvorschläge für dieses Szenario.
Gib nur JSON in dieser Form zurück:
{{"empathy_score":7,"empathy_feedback":"...","clarity_score":6,"clarity_feedback":"...","result_score":8,"result_feedback":"...","summary":"..."}}"""


def system_prompt() -> str:
    return """Du bist ein erfahrener Kommunikations-Coach mit 20 Jahren Erfahrung.
Du analysierst Rollenspiele, in denen ein menschlicher Nutzer mit einem KI-Avatar spricht.
Bewerte ausschliesslich den menschlichen Nutzer. Avatar-Aussagen dienen nur als Kontext.
Antworte nur mit gültigem JSON, ohne Markdown."""


def parse_analysis_json(raw: str) -> dict[str, Any]:
    clean = raw.strip()
    if "```json" in clean:
        clean = clean.split("```json", 1)[1].split("```", 1)[0].strip()
    elif clean.startswith("```"):
        clean = clean.split("```", 1)[1].split("```", 1)[0].strip()
    parsed = json.loads(clean)
    if not isinstance(parsed, dict):
        raise ValueError("Analysis response was not a JSON object.")
    asr_notes = (
        [str(n) for n in parsed.get("asr_notes", []) if str(n).strip()][:5]
        if isinstance(parsed.get("asr_notes"), list)
        else []
    )
    return {
        "empathy_score": _score(parsed.get("empathy_score")),
        "empathy_feedback": str(parsed.get("empathy_feedback", "")),
        "clarity_score": _score(parsed.get("clarity_score")),
        "clarity_feedback": str(parsed.get("clarity_feedback", "")),
        "result_score": _score(parsed.get("result_score")),
        "result_feedback": str(parsed.get("result_feedback", "")),
        "summary": str(parsed.get("summary", "")),
        "better_phrasings": [
            p for p in _phrasings(parsed.get("better_phrasings")) if not _mentioned_in(p["original"], asr_notes)
        ],
        "counterpart_journey": str(parsed.get("counterpart_journey", "")),
        "asr_notes": asr_notes,
    }


def _mentioned_in(sentence: str, notes: list[str]) -> bool:
    """True if a (probably misrecognized) sentence is quoted in one of the ASR notes."""
    def norm(text: str) -> str:
        return " ".join("".join(ch for ch in text.lower() if ch.isalnum() or ch.isspace()).split())

    needle = norm(sentence)[:40]
    return bool(needle) and any(needle in norm(note) or norm(note).find(needle[:20]) >= 0 for note in notes)


def _phrasings(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    items = []
    for entry in raw[:3]:
        if isinstance(entry, dict) and entry.get("original") and entry.get("better"):
            items.append({
                "original": str(entry["original"]),
                "better": str(entry["better"]),
                "why": str(entry.get("why", "")),
            })
    return items


def _generation_config(model: str) -> dict[str, Any]:
    config: dict[str, Any] = {"temperature": 0.25, "responseMimeType": "application/json"}
    if model.startswith("gemini-3"):
        config["thinkingConfig"] = {"thinkingLevel": "low"}  # Gemini 3.x; 2.5 uses thinkingBudget instead
    return config


def generate_with_gemini(api_key: str, prompt: str, model: str = GEMINI_MODEL) -> str:
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt()}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
    }
    models = _unique_models((model, *GEMINI_FALLBACK_MODELS))
    last_error: AnalysisProviderError | None = None
    for candidate_model in models:
        response = requests.post(
            f"{GEMINI_API_BASE}/models/{candidate_model}:generateContent",
            headers={"x-goog-api-key": api_key},  # header, so the key never appears in URLs or exception texts
            json={**payload, "generationConfig": _generation_config(candidate_model)},
            timeout=REQUEST_TIMEOUT,
        )
        if not response.ok:
            last_error = AnalysisProviderError("Gemini", _provider_error_message("Gemini", response), response.status_code)
            if response.status_code in {404, 429, 503}:
                continue
            raise last_error
        data = response.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict))
        except (KeyError, IndexError, TypeError) as exc:
            raise AnalysisProviderError("Gemini", "Gemini returned no analysis text.") from exc
    if last_error:
        raise last_error
    raise AnalysisProviderError("Gemini", "Gemini is not configured with a usable model.")


def _unique_models(models: tuple[str, ...]) -> tuple[str, ...]:
    unique: list[str] = []
    for model in models:
        if model and model not in unique:
            unique.append(model)
    return tuple(unique)


def deepseek_error_message(exc: Exception) -> str:
    status_code = getattr(exc, "status_code", None)
    body = str(getattr(exc, "body", "") or exc)
    if status_code == 402 or "Insufficient Balance" in body:
        return (
            "Analyse nicht verfügbar: Das DeepSeek-Guthaben ist leer. "
            "Modal Secret `my-deepseek-secret` enthält `DEEPSEEK_API_KEY`, aber der Key braucht Guthaben."
        )
    if status_code:
        return f"Analyse nicht verfügbar: DeepSeek antwortet mit HTTP {status_code}."
    return "Analyse nicht verfügbar: DeepSeek konnte nicht erreicht werden."


def _provider_error_message(provider: str, response: requests.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        data = response.text[:200]
    if response.status_code in {400, 401, 403}:
        return f"Analyse nicht verfügbar: {provider}-API-Key ist ungültig oder nicht berechtigt."
    if response.status_code == 429:
        return f"Analyse nicht verfügbar: {provider}-Limit erreicht."
    return f"Analyse nicht verfügbar: {provider} antwortet mit HTTP {response.status_code}. Details: {data}"


def _score(value: Any) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(10, score))
