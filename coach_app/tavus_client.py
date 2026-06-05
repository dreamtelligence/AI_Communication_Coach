from __future__ import annotations

from typing import Any

import requests

from coach_app.scenarios import (
    PERSONA_VERSION,
    build_conversation_context,
    build_persona_prompt,
    get_opening,
    get_practice_side,
)


TAVUS_API_BASE = "https://tavusapi.com/v2"
REQUEST_TIMEOUT = 20
CONVERSATION_LANGUAGE = "german"
STT_ENGINE = "tavus-parakeet"


class TavusError(RuntimeError):
    pass


def is_configured(api_key: str | None, replica_id: str | None) -> bool:
    return bool(api_key and replica_id)


def setup_personas(api_key: str, replica_id: str, scenarios: list[dict[str, Any]]) -> dict[str, str]:
    existing = _list_personas(api_key)
    persona_ids: dict[str, str] = {}
    for scenario in scenarios:
        for side in scenario["practice_sides"]:
            cache_key = _cache_key(scenario, side["id"])
            persona_name = _persona_name(scenario, side["id"])
            if persona_name in existing:
                persona_ids[cache_key] = existing[persona_name]
                continue
            persona_ids[cache_key] = _create_persona(api_key, replica_id, scenario, side["id"])
    return persona_ids


def ensure_persona(api_key: str, replica_id: str, scenario: dict[str, Any], practice_side_id: str | None = None) -> str:
    side = get_practice_side(scenario, practice_side_id)
    existing = _list_personas(api_key)
    persona_name = _persona_name(scenario, side["id"])
    if persona_name in existing:
        return existing[persona_name]
    return _create_persona(api_key, replica_id, scenario, side["id"])


def create_conversation(
    api_key: str,
    replica_id: str,
    persona_id: str,
    scenario: dict[str, Any],
    practice_side_id: str | None = None,
    sandbox: bool = False,
) -> dict[str, Any]:
    side = get_practice_side(scenario, practice_side_id)
    payload = {
        "replica_id": replica_id,
        "persona_id": persona_id,
        "conversation_name": f"TalkToMe - {scenario['title']} - {side['label']}",
        "conversational_context": build_conversation_context(scenario, side["id"]),
        "custom_greeting": get_opening(scenario["id"], side["id"]),
        "max_participants": 2,
        "properties": {
            "language": CONVERSATION_LANGUAGE,
            "max_call_duration": 900,
            "participant_left_timeout": 20,
            "participant_absent_timeout": 120,
            "enable_closed_captions": True,
        },
    }
    if sandbox:
        payload["test_mode"] = True
    response = requests.post(
        f"{TAVUS_API_BASE}/conversations",
        headers=_headers(api_key),
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    data = _checked_json(response, "create Tavus conversation")
    conversation_id = data.get("conversation_id")
    conversation_url = data.get("conversation_url")
    if not conversation_id or not conversation_url:
        raise TavusError("Tavus did not return a conversation URL.")
    return data


def end_conversation(api_key: str, conversation_id: str) -> dict[str, Any]:
    response = requests.post(
        f"{TAVUS_API_BASE}/conversations/{conversation_id}/end",
        headers=_headers(api_key),
        timeout=REQUEST_TIMEOUT,
    )
    if response.ok or response.status_code in {404, 409}:
        return {}
    return _checked_json(response, "end Tavus conversation")


def get_conversation(api_key: str, conversation_id: str, verbose: bool = True) -> dict[str, Any]:
    response = requests.get(
        f"{TAVUS_API_BASE}/conversations/{conversation_id}",
        headers=_headers(api_key),
        params={"verbose": "true"} if verbose else None,
        timeout=REQUEST_TIMEOUT,
    )
    return _checked_json(response, "fetch Tavus conversation")


def _list_personas(api_key: str) -> dict[str, str]:
    response = requests.get(f"{TAVUS_API_BASE}/personas", headers=_headers(api_key), timeout=REQUEST_TIMEOUT)
    data = _checked_json(response, "list Tavus personas")
    personas = data.get("data", data if isinstance(data, list) else [])
    if not isinstance(personas, list):
        return {}
    return {
        persona["persona_name"]: persona["persona_id"]
        for persona in personas
        if isinstance(persona, dict) and persona.get("persona_name") and persona.get("persona_id")
    }


def _create_persona(api_key: str, replica_id: str, scenario: dict[str, Any], practice_side_id: str) -> str:
    payload = {
        "persona_name": _persona_name(scenario, practice_side_id),
        "system_prompt": build_persona_prompt(scenario, practice_side_id),
        "pipeline_mode": "full",
        "default_replica_id": replica_id,
        "layers": {
            "stt": {
                "stt_engine": STT_ENGINE,
                "hotwords": (
                    "Deutschsprachiges Business-Rollenspiel. Wichtige Begriffe: "
                    "Gehaltsverhandlung, Kundenbeschwerde, Führungskraft, Mitarbeiter, "
                    "Service, Beschwerde, Vergütung, Budget, Lösung."
                ),
            }
        },
    }
    response = requests.post(
        f"{TAVUS_API_BASE}/personas",
        headers=_headers(api_key),
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    data = _checked_json(response, f"create Tavus persona for {scenario['id']}")
    persona_id = data.get("persona_id")
    if not persona_id:
        raise TavusError(f"Tavus did not return a persona_id for {scenario['id']}.")
    return persona_id


def _headers(api_key: str) -> dict[str, str]:
    return {"x-api-key": api_key, "Content-Type": "application/json", "Accept": "application/json"}


def _checked_json(response: requests.Response, action: str) -> dict[str, Any]:
    if not response.ok:
        raise TavusError(f"Could not {action}.")
    try:
        data = response.json()
    except ValueError as exc:
        raise TavusError(f"Tavus returned invalid JSON while trying to {action}.") from exc
    if not isinstance(data, dict):
        raise TavusError(f"Tavus returned an unexpected response while trying to {action}.")
    return data


def _cache_key(scenario: dict[str, Any], practice_side_id: str) -> str:
    return f"{scenario['id']}:{practice_side_id}"


def _persona_name(scenario: dict[str, Any], practice_side_id: str) -> str:
    return f"TalkToMe {PERSONA_VERSION} - {scenario['title']} - {practice_side_id}"
