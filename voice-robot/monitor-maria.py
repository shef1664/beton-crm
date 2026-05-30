#!/usr/bin/env python3
"""Quick monitor for Maria voice bot calls in AmoCRM."""

import os
from pathlib import Path

import requests


SECRETS = Path.home() / "Documents" / "Бетон-deploy" / "secrets"
AMOCRM_BASE_URL = os.getenv("AMOCRM_BASE_URL", "https://shef1664.amocrm.ru").rstrip("/")
VOICE_TAG = "voice-bot-635588"
TRANSFER_TAG = "требует-менеджера"


def read_secret(name):
    path = SECRETS / name
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def amocrm_token():
    return os.getenv("AMOCRM_ACCESS_TOKEN") or read_secret("amocrm_access_token.txt")


def amo_get(path, params=None):
    token = amocrm_token()
    if not token:
        raise RuntimeError("AMOCRM_ACCESS_TOKEN is missing")
    response = requests.get(
        f"{AMOCRM_BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
        timeout=20,
    )
    if not response.ok:
        raise RuntimeError(f"AmoCRM HTTP {response.status_code}: {response.text[:300]}")
    if response.status_code == 204 or not response.text.strip():
        return {}
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"AmoCRM returned non-JSON response: HTTP {response.status_code}, "
            f"content-type={response.headers.get('content-type')}, body={response.text[:300]}"
        ) from exc


def lead_tags(lead):
    return {
        tag.get("name")
        for tag in lead.get("_embedded", {}).get("tags", [])
        if tag.get("name")
    }


def main():
    data = amo_get("/api/v4/leads", params={"query": VOICE_TAG, "with": "contacts"})
    leads = data.get("_embedded", {}).get("leads", [])
    voice_leads = [lead for lead in leads if VOICE_TAG in lead_tags(lead)]
    transfer_leads = [lead for lead in voice_leads if TRANSFER_TAG in lead_tags(lead)]

    print("Maria voice bot monitor")
    print("========================")
    print(f"Voice leads: {len(voice_leads)}")
    print(f"Transfer-needed leads: {len(transfer_leads)}")
    print()
    for lead in voice_leads[:10]:
        tags = ", ".join(sorted(lead_tags(lead)))
        print(f"- #{lead['id']} {lead.get('name', '')} [{tags}]")
    print()
    print("Render logs: https://dashboard.render.com/")
    print("Expected service: beton42-maria-voice")


if __name__ == "__main__":
    main()
