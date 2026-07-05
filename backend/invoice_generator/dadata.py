import json
import os
from pathlib import Path
from typing import Optional

import httpx

from invoice_generator.models import Buyer


DADATA_PARTY_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"


def dadata_token() -> str:
    token = os.environ.get("DADATA_TOKEN", "")
    if token:
        return token
    secret_path = Path.home() / ".secrets" / "dadata.json"
    if secret_path.exists():
        data = json.loads(secret_path.read_text(encoding="utf-8"))
        return data.get("token", "")
    return ""


def party_from_dadata_suggestion(suggestion: dict) -> Buyer:
    data = suggestion.get("data") or {}
    address = data.get("address") or {}
    return Buyer(
        name=suggestion.get("value") or data.get("name", {}).get("full_with_opf") or "",
        inn=data.get("inn") or "",
        kpp=data.get("kpp") or None,
        address=address.get("unrestricted_value") or address.get("value") or None,
    )


async def find_party_by_inn(inn: str, token: Optional[str] = None) -> Optional[Buyer]:
    resolved_token = token or dadata_token()
    if not resolved_token:
        return None
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            DADATA_PARTY_URL,
            headers={"Authorization": f"Token {resolved_token}", "Content-Type": "application/json"},
            json={"query": inn},
        )
        response.raise_for_status()
        payload = response.json()
    suggestions = payload.get("suggestions") or []
    if not suggestions:
        return None
    return party_from_dadata_suggestion(suggestions[0])

