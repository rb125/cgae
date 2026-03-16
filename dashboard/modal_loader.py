"""
Data loader for Streamlit dashboard — targets HuggingFace Space backend.
"""

import requests
from typing import Optional

MODAL_ENDPOINT = "https://rb512-cgae-backend.hf.space"
IS_CLOUD = True


def load_json_file(filename: str) -> dict:
    return _get(f"/results/{filename}")


def list_available_files() -> list[str]:
    data = _get("/list")
    return [f["name"] for f in data.get("files", [])]


def get_backend_health() -> dict:
    return _get("/health") or {"status": "unknown"}


def _get(path: str) -> dict:
    try:
        r = requests.get(f"{MODAL_ENDPOINT}{path}", timeout=10)
        return r.json() if r.status_code == 200 else {}
    except Exception as e:
        print(f"Backend request failed ({path}): {e}")
        return {}
