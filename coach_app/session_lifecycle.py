from __future__ import annotations

import re
import time
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from coach_app.security import require_session_token
from coach_app.tavus_client import TavusError, end_conversation


LEASE_SECONDS = 120
CONVERSATION_ID = re.compile(r"[a-z0-9]{8,64}")


class SessionLeases:
    """Persist deadlines outside the web container so crashes cannot retain a call indefinitely."""

    def __init__(self, store: Any, api_key: Callable[[], str | None]):
        self.store = store
        self.api_key = api_key

    def start(self, conversation_id: str) -> None:
        try:
            self.store.put(conversation_id, time.time() + LEASE_SECONDS)
        except Exception:
            # A conversation without a durable deadline must never be handed to the browser.
            end_conversation(self.api_key() or "", conversation_id)
            raise

    def renew(self, conversation_id: str) -> bool:
        now = time.time()
        deadline = self.store.get(conversation_id)
        if deadline is None or deadline <= now:
            return False
        self.store.put(conversation_id, now + LEASE_SECONDS)
        return True

    def end(self, conversation_id: str) -> None:
        end_conversation(self.api_key() or "", conversation_id)
        self.store.pop(conversation_id, None)

    def was_expired(self, conversation_id: str) -> bool:
        return self.store.get(f"expired:{conversation_id}", 0) > time.time()

    def expire(self) -> dict[str, int]:
        ended = failed = 0
        for conversation_id, _ in list(self.store.items()):
            # Re-read: a heartbeat may have renewed the deadline since iteration started.
            deadline = self.store.get(conversation_id)
            if conversation_id.startswith("expired:"):
                if deadline is not None and deadline <= time.time():
                    self.store.pop(conversation_id, None)
                continue
            if deadline is None or deadline > time.time():
                continue
            try:
                # Keep the reason briefly so a returning browser does not grade an abandoned call.
                self.store.put(f"expired:{conversation_id}", time.time() + 3600)
                self.end(conversation_id)
                ended += 1
            except (TavusError, OSError):
                failed += 1  # Keep the deadline for the next watchdog run.
        return {"ended": ended, "failed": failed}


def session_routes(leases: SessionLeases) -> APIRouter:
    router = APIRouter()

    def authorize(conversation_id: str, request: Request) -> None:
        if not CONVERSATION_ID.fullmatch(conversation_id):
            raise HTTPException(status_code=400, detail="Invalid conversation id.")
        require_session_token(request, conversation_id)

    @router.post("/api/session/{conversation_id}/heartbeat")
    def heartbeat(conversation_id: str, request: Request) -> dict:
        authorize(conversation_id, request)
        if not leases.renew(conversation_id):
            raise HTTPException(status_code=410, detail="Die Videoverbindung ist abgelaufen. Bitte neu starten.")
        return {"status": "active"}

    @router.post("/api/session/{conversation_id}/end")
    def end(conversation_id: str, request: Request) -> dict:
        authorize(conversation_id, request)
        try:
            leases.end(conversation_id)
        except (TavusError, OSError) as exc:
            raise HTTPException(status_code=502, detail="Sitzung konnte noch nicht freigegeben werden.") from exc
        return {"status": "ended"}

    return router
