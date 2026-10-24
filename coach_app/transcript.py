from __future__ import annotations

from typing import Any


USER_SPEAKERS = {"user", "human", "nutzer", "you", "participant", "ich", "guest"}
AVATAR_SPEAKERS = {"assistant", "avatar", "replica", "pal", "ai", "bot"}
SYSTEM_SPEAKERS = {"system", "developer", "tool"}


def parse_transcript(full_transcript: str) -> dict[str, str]:
    user_lines: list[str] = []
    avatar_lines: list[str] = []
    all_lines: list[str] = []

    for raw_line in full_transcript.strip().splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ":" not in line:
            user_lines.append(line)
            all_lines.append(f"user: {line}")
            continue
        speaker, text = line.split(":", 1)
        speaker_name = speaker.strip()
        speaker_lower = speaker_name.lower()
        if speaker_lower in SYSTEM_SPEAKERS:
            continue
        clean_text = text.strip()
        if not clean_text:
            continue
        all_lines.append(f"{_display_speaker(speaker_lower, speaker_name)}: {clean_text}")
        if speaker_lower in USER_SPEAKERS:
            user_lines.append(clean_text)
        elif speaker_lower in AVATAR_SPEAKERS:
            avatar_lines.append(f"[{_display_speaker(speaker_lower, speaker_name)}]: {clean_text}")

    return {
        "user_only": "\n".join(user_lines),
        "avatar_only": "\n".join(avatar_lines),
        "full_transcript": "\n".join(all_lines),
    }


def transcript_from_tavus_conversation(conversation: dict[str, Any]) -> str | None:
    direct = conversation.get("transcript")
    direct_text = _transcript_payload_to_text(direct)
    if direct_text:
        return direct_text

    events = conversation.get("events")
    if not isinstance(events, list):
        return None

    for event in events:
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("event_type") or event.get("type") or "")
        payload = event.get("payload") or event.get("properties") or event.get("data") or event
        if "transcript" in event_type or "transcription" in event_type:
            text = _transcript_payload_to_text(payload)
            if text:
                return text
        if isinstance(payload, dict):
            text = _transcript_payload_to_text(payload.get("transcript"))
            if text:
                return text
    return None


def _transcript_payload_to_text(payload: Any) -> str | None:
    if not payload:
        return None
    if isinstance(payload, str):
        return payload.strip() or None
    if isinstance(payload, list):
        lines = [_entry_to_line(entry) for entry in payload]
        clean_lines = [line for line in lines if line]
        return "\n".join(clean_lines) if clean_lines else None
    if isinstance(payload, dict):
        for key in ("messages", "results", "transcript", "utterances"):
            text = _transcript_payload_to_text(payload.get(key))
            if text:
                return text
        return _entry_to_line(payload)
    return None


def _entry_to_line(entry: Any) -> str | None:
    if isinstance(entry, str):
        return entry.strip() or None
    if not isinstance(entry, dict):
        return None
    speaker = entry.get("speaker") or entry.get("role") or entry.get("participant") or "Unknown"
    text = entry.get("text") or entry.get("content") or entry.get("message")
    if not text:
        return None
    speaker_name = str(speaker).strip()
    speaker_lower = speaker_name.lower()
    if speaker_lower in SYSTEM_SPEAKERS:
        return None
    if speaker_lower not in USER_SPEAKERS and speaker_lower not in AVATAR_SPEAKERS:
        return None
    return f"{_display_speaker(speaker_lower, speaker_name)}: {str(text).strip()}"


def _display_speaker(speaker_lower: str, fallback: str) -> str:
    if speaker_lower in USER_SPEAKERS:
        return "user"
    if speaker_lower in AVATAR_SPEAKERS:
        return "assistant"
    return fallback
