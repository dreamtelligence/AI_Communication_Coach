from __future__ import annotations

import json
from typing import Any

import requests

from coach_app.scenarios import get_scenario, get_practice_side
from coach_app.transcript import parse_transcript


DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_FALLBACK_MODELS = (
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash-lite",
)
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
REQUEST_TIMEOUT = 30


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
    return f"""Analysiere ein Live-Coaching-Rollenspiel.

SZENARIO: {scenario["title"]}
TRAINIERTE ROLLE DES NUTZERS: {side["user_role"]}
ZIEL DES NUTZERS: {side["user_goal"]}
ROLLE DES KI-AVATARS: {side["avatar_role"]}

DER KI-AVATAR sagte:
{avatar_text}

DER MENSCHLICHE NUTZER, der bewertet wird, sagte:
{user_text}

VOLLSTAENDIGES TRANSKRIPT:
{text[:4000]}

Bewerte ausschliesslich den menschlichen Nutzer nach:
1. Empathie und emotionale Intelligenz (1-10)
2. Sprachliche Klarheit und Struktur (1-10)
3. Ergebnisorientierung und Zielführung (1-10)

Jeder Score muss mit mindestens einem wörtlichen Zitat des Nutzers belegt werden.
Gib nur JSON in dieser Form zurück:
{{"empathy_score":7,"empathy_feedback":"...","clarity_score":6,"clarity_feedback":"...","result_score":8,"result_feedback":"...","summary":"..."}}"""


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
    return {
        "empathy_score": _score(parsed.get("empathy_score")),
        "empathy_feedback": str(parsed.get("empathy_feedback", "")),
        "clarity_score": _score(parsed.get("clarity_score")),
        "clarity_feedback": str(parsed.get("clarity_feedback", "")),
        "result_score": _score(parsed.get("result_score")),
        "result_feedback": str(parsed.get("result_feedback", "")),
        "summary": str(parsed.get("summary", "")),
    }


def generate_with_gemini(api_key: str, prompt: str, model: str = GEMINI_MODEL) -> str:
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt()}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.25, "responseMimeType": "application/json"},
    }
    models = _unique_models((model, *GEMINI_FALLBACK_MODELS))
    last_error: AnalysisProviderError | None = None
    for candidate_model in models:
        response = requests.post(
            f"{GEMINI_API_BASE}/models/{candidate_model}:generateContent",
            params={"key": api_key},
            json=payload,
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
