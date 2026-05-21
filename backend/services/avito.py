"""
Avito Messenger API client.

Listens for new chat messages from clients on our Avito ads and converts them
to AmoCRM leads. Uses OAuth2 client_credentials flow (server-to-server, no
human approval required after app is approved).

API docs: https://developers.avito.ru/api-catalog/messenger/documentation
Environment variables required:
  AVITO_CLIENT_ID
  AVITO_CLIENT_SECRET
  AVITO_USER_ID  (numeric account id, can be fetched via /core/v1/accounts/self)

Public methods:
  get_token() — refresh and cache access token
  list_chats() — return chats with unread messages
  list_messages(chat_id, from_message_id=None) — messages in a chat
  fetch_new_messages() — convenience: enumerate all unread messages since
                         last poll; used by poller.

State (last seen message id per chat) is persisted to disk.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import httpx

logger = logging.getLogger(__name__)

AVITO_TOKEN_URL = "https://api.avito.ru/token"
AVITO_API_BASE = "https://api.avito.ru"
DEFAULT_TIMEOUT = 20.0

STATE_PATH = Path(__file__).parent.parent / "data" / "avito_state.json"


class AvitoService:
    def __init__(self) -> None:
        self.client_id = os.getenv("AVITO_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("AVITO_CLIENT_SECRET", "").strip()
        self.user_id = os.getenv("AVITO_USER_ID", "").strip()
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.user_id)

    async def get_token(self) -> str:
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.post(
                AVITO_TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        self._token = data["access_token"]
        self._token_expires_at = time.time() + int(data.get("expires_in", 3600))
        return self._token

    async def _request(self, method: str, path: str, **kwargs: Any) -> Dict[str, Any]:
        token = await self.get_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.request(method, AVITO_API_BASE + path, headers=headers, **kwargs)
        if resp.status_code == 401:
            # token rotated; force refresh
            self._token = None
            token = await self.get_token()
            headers["Authorization"] = f"Bearer {token}"
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                resp = await client.request(method, AVITO_API_BASE + path, headers=headers, **kwargs)
        resp.raise_for_status()
        return resp.json()

    async def list_chats(self, limit: int = 50, only_unread: bool = True) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"limit": limit, "offset": 0}
        if only_unread:
            params["unread_only"] = "true"
        data = await self._request(
            "GET",
            f"/messenger/v2/accounts/{self.user_id}/chats",
            params=params,
        )
        return data.get("chats", [])

    async def list_messages(self, chat_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        data = await self._request(
            "GET",
            f"/messenger/v3/accounts/{self.user_id}/chats/{chat_id}/messages/",
            params={"limit": limit, "offset": 0},
        )
        return data.get("messages", [])

    async def mark_chat_read(self, chat_id: str) -> None:
        try:
            await self._request(
                "POST",
                f"/messenger/v1/accounts/{self.user_id}/chats/{chat_id}/read",
            )
        except Exception as e:
            logger.warning("avito mark_chat_read failed for %s: %s", chat_id, e)

    # ---- state ----------------------------------------------------------------
    @staticmethod
    def _load_state() -> Dict[str, Any]:
        if not STATE_PATH.exists():
            return {"last_seen": {}}
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {"last_seen": {}}

    @staticmethod
    def _save_state(state: Dict[str, Any]) -> None:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    async def fetch_new_messages(self) -> Iterable[Dict[str, Any]]:
        """Yield messages that are new since the last poll.

        Skips outgoing messages from us. State per chat is updated as we yield.
        """
        if not self.is_configured():
            return
        state = self._load_state()
        last_seen: Dict[str, str] = state.get("last_seen", {})

        try:
            chats = await self.list_chats(only_unread=False, limit=50)
        except httpx.HTTPError as e:
            logger.error("avito list_chats error: %s", e)
            return

        new_messages: List[Dict[str, Any]] = []
        for chat in chats:
            chat_id = chat.get("id")
            if not chat_id:
                continue
            try:
                messages = await self.list_messages(chat_id, limit=20)
            except httpx.HTTPError as e:
                logger.warning("avito list_messages failed for chat %s: %s", chat_id, e)
                continue
            # Messages come newest first; iterate oldest first to update state correctly
            seen_for_chat = last_seen.get(chat_id, "")
            first_time_seeing_chat = chat_id not in last_seen

            for msg in reversed(messages):
                msg_id = msg.get("id", "")
                if not msg_id:
                    continue
                if seen_for_chat and msg_id <= seen_for_chat:
                    continue
                # Always update state cursor so we don't reprocess
                last_seen[chat_id] = msg_id
                # First time seeing this chat: bootstrap — record state but
                # do not create leads from history (avoid flooding AmoCRM)
                if first_time_seeing_chat:
                    continue
                # Skip our own outgoing messages
                author_id = str(msg.get("author_id") or "")
                if author_id == str(self.user_id):
                    continue
                msg["_chat"] = chat
                new_messages.append(msg)

        state["last_seen"] = last_seen
        self._save_state(state)
        return new_messages
