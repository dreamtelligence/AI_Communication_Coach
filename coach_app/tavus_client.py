from __future__ import annotations

import re
from typing import Any

import requests

from coach_app.scenarios import (
    PAL_VERSION,
    build_conversation_context,
    build_pal_prompt,
    get_opening,
    get_practice_side,
    get_stt_hotwords,
)


TAVUS_API_BASE = "https://tavusapi.com/v2"
REQUEST_TIMEOUT = 20
LANGUAGES = ["de"]
# tavus-gemma-4 is Tavus' recommended default (fastest, most natural, best with Phoenix emotion control).
LLM_MODEL = "tavus-gemma-4"
STT_ENGINE = "tavus-auto"
TURN_DETECTION_MODEL = "sparrow-2"
PERCEPTION_MODEL = "raven-1"
# EU AI Act: workplace training -> AI disclosure + no biometric emotion inference (Raven "limited").
CONVERSATION_POLICY = "eu"
VERBAL_DISCLOSURE = "Kurzer Hinweis: Ich bin ein KI-Avatar für dieses Trainingsgespräch, kein Mensch."
VISUAL_DISCLOSURE = "KI-Avatar – Trainingsgespräch"


class TavusError(RuntimeError):
    pass


class TavusCapacityError(TavusError):
    pass


def is_configured(api_key: str | None) -> bool:
    return bool(api_key)


def setup_pals(api_key: str, scenarios: list[dict[str, Any]]) -> dict[str, str]:
    existing = _list_pals(api_key)
    pal_ids: dict[str, str] = {}
    for scenario in scenarios:
        for side in scenario["practice_sides"]:
            cache_key = _cache_key(scenario, side["id"])
            pal_key = _name_key(_pal_name(scenario, side["id"]))
            if pal_key in existing:
                pal_ids[cache_key] = existing[pal_key]
                continue
            pal_ids[cache_key] = _create_pal(api_key, scenario, side["id"])
    return pal_ids


def ensure_pal(api_key: str, scenario: dict[str, Any], practice_side_id: str | None = None) -> str:
    side = get_practice_side(scenario, practice_side_id)
    existing = _list_pals(api_key)
    pal_key = _name_key(_pal_name(scenario, side["id"]))
    if pal_key in existing:
        return existing[pal_key]
    return _create_pal(api_key, scenario, side["id"])


def create_conversation(
    api_key: str,
    pal_id: str,
    scenario: dict[str, Any],
    practice_side_id: str | None = None,
    sandbox: bool = False,
) -> dict[str, Any]:
    side = get_practice_side(scenario, practice_side_id)
    payload = {
        "pal_id": pal_id,
        "face_id": side["face_id"],
        "conversation_name": f"TalkToMe - {scenario['title']} - {side['label']}",
        "conversational_context": build_conversation_context(scenario, side["id"]),
        "custom_greeting": get_opening(scenario["id"], side["id"]),
        "max_participants": 2,
        "policy": CONVERSATION_POLICY,
        "properties": {
            "languages": LANGUAGES,
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
    if response.status_code == 400 and "maximum concurrent conversations" in response.text.lower():
        raise TavusCapacityError(
            "Alle Videoleitungen sind gerade belegt. Bitte beende dein anderes Gespräch "
            "oder versuche es in wenigen Minuten erneut."
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


def _list_pals(api_key: str) -> dict[str, str]:
    """Map normalized PAL name -> pal_id."""
    pals: dict[str, str] = {}
    page = 1
    while True:
        response = requests.get(
            f"{TAVUS_API_BASE}/pals",
            headers=_headers(api_key),
            params={"limit": 100, "page": page},
            timeout=REQUEST_TIMEOUT,
        )
        data = _checked_json(response, "list Tavus PALs")
        items = data.get("data", [])
        if not isinstance(items, list) or not items:
            break
        for pal in items:
            if isinstance(pal, dict) and pal.get("pal_name") and pal.get("pal_id"):
                pals[_name_key(pal["pal_name"])] = pal["pal_id"]
        if len(items) < 100:
            break
        page += 1
    return pals


def _create_pal(api_key: str, scenario: dict[str, Any], practice_side_id: str) -> str:
    side = get_practice_side(scenario, practice_side_id)
    payload = {
        "pal_name": _pal_name(scenario, practice_side_id),
        "system_prompt": build_pal_prompt(scenario, practice_side_id),
        "pipeline_mode": "full",
        "default_face_id": side["face_id"],
        "languages": LANGUAGES,
        "disclosure_type": "auto",
        "verbal_disclosure": VERBAL_DISCLOSURE,
        "visual_disclosure": VISUAL_DISCLOSURE,
        "layers": {
            "llm": {
                "model": LLM_MODEL,
                "extra_body": {"temperature": 0.7},
            },
            "stt": {
                "stt_engine": STT_ENGINE,
                "hotwords": get_stt_hotwords(scenario),
            },
            "conversational_flow": {
                "turn_detection_model": TURN_DETECTION_MODEL,
                # people need time to think in negotiations
                "turn_taking_patience": "high",
                "pal_interruptibility": "medium",
            },
            "perception": {
                "perception_model": PERCEPTION_MODEL,
                "emotion_recognition": "auto",
            },
        },
    }
    response = requests.post(
        f"{TAVUS_API_BASE}/pals",
        headers=_headers(api_key),
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    data = _checked_json(response, f"create Tavus PAL for {scenario['id']}")
    pal_id = data.get("pal_id")
    if not pal_id:
        raise TavusError(f"Tavus did not return a pal_id for {scenario['id']}.")
    return pal_id


def _headers(api_key: str) -> dict[str, str]:
    return {"x-api-key": api_key, "Content-Type": "application/json", "Accept": "application/json"}


def _checked_json(response: requests.Response, action: str) -> dict[str, Any]:
    if not response.ok:
        detail = response.text[:500].strip()
        raise TavusError(f"Could not {action}: HTTP {response.status_code}. {detail}")
    try:
        data = response.json()
    except ValueError as exc:
        raise TavusError(f"Tavus returned invalid JSON while trying to {action}.") from exc
    if not isinstance(data, dict):
        raise TavusError(f"Tavus returned an unexpected response while trying to {action}.")
    return data


def _cache_key(scenario: dict[str, Any], practice_side_id: str) -> str:
    return f"{scenario['id']}:{practice_side_id}"


def _pal_name(scenario: dict[str, Any], practice_side_id: str) -> str:
    return f"TalkToMe {PAL_VERSION} {scenario['title']} {practice_side_id}"


def _name_key(name: str) -> str:
    # Tavus normalizes PAL names (e.g. drops " - "), so compare on letters/digits only.
    return re.sub(r"[^0-9a-zäöüß]+", " ", name.lower()).strip()
