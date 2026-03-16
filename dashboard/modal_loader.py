"""
Modal-aware data loader for Streamlit dashboard.

Always reads from Modal web endpoints.
"""

import requests
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

HARDCODED_MODAL_ENDPOINT = "https://rb512-cgae-backend.hf.space"


def _normalize_modal_endpoint(endpoint: str) -> str:
    return endpoint.strip().rstrip("/")


def _derive_function_url(function_suffix: str) -> Optional[str]:
    if not MODAL_ENDPOINT:
        return None
    suffix_map = {"list-results": "list", "health": "health"}
    path = suffix_map.get(function_suffix, function_suffix)
    return f"{MODAL_ENDPOINT}/{path}"


def _append_query_param(url: str, key: str, value: str) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query[key] = value
    return urlunparse(parsed._replace(query=urlencode(query)))


def _derive_function_url(function_suffix: str) -> Optional[str]:
    """Derive sibling function URLs (e.g., list-results, health) from get-results URL."""
    if not MODAL_ENDPOINT:
        return None

    parsed = urlparse(MODAL_ENDPOINT)

    # Host-style endpoint: <workspace>--<app>-get-results.modal.run
    if parsed.netloc.endswith(".modal.run") and "-get-results." in parsed.netloc:
        sibling_host = parsed.netloc.replace("-get-results.", f"-{function_suffix}.", 1)
        return urlunparse(parsed._replace(netloc=sibling_host, path="", query="", params="", fragment=""))

    # Path-style endpoint fallback: .../get_results
    path = parsed.path.rstrip("/")
    if path.endswith("/get_results"):
        sibling_path = f"{path[:-len('/get_results')]}/{function_suffix.replace('-', '_')}"
        return urlunparse(parsed._replace(path=sibling_path, query="", params="", fragment=""))

    return None

def _resolve_modal_endpoint() -> Optional[str]:
    """
    Resolve endpoint using a hardcoded Modal app URL.

    This intentionally bypasses env/secrets so Streamlit always targets the
    production Modal backend requested by the user.
    """
    return _normalize_modal_endpoint(HARDCODED_MODAL_ENDPOINT)


MODAL_ENDPOINT = _resolve_modal_endpoint()
IS_CLOUD = bool(MODAL_ENDPOINT)


def load_json_file(filename: str) -> dict:
    """
    Load a JSON result file from the Modal endpoint.
    """
    if not IS_CLOUD:
        print("Error loading from Modal: MODAL_ENDPOINT is not configured.")
        return {}
    return _load_from_modal(filename)


def _load_from_modal(filename: str) -> dict:
    try:
        response = requests.get(f"{MODAL_ENDPOINT}/results/{filename}", timeout=10)
        if response.status_code == 200:
            return response.json()
        return {}
    except Exception as e:
        print(f"Error loading {filename} from backend: {e}")
        return {}


def list_available_files() -> list[str]:
    """List available result files."""
    if IS_CLOUD:
        try:
            list_url = _derive_function_url("list-results")
            if not list_url:
                return []
            response = requests.get(list_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return [f["name"] for f in data.get("files", [])]
        except Exception as e:
            print(f"Error listing files from Modal: {e}")
        return []
    else:
        # Local filesystem
        return []


def get_backend_health() -> dict:
    """Fetch backend health status from Modal health endpoint."""
    if not IS_CLOUD:
        return {}

    try:
        health_url = _derive_function_url("health")
        if not health_url:
            return {"status": "unknown", "reason": "health_endpoint_unresolved"}

        response = requests.get(health_url, timeout=10)
        if response.status_code == 200:
            return response.json()
        return {"status": "unknown", "reason": f"health_status_{response.status_code}"}
    except Exception as e:
        return {"status": "unknown", "reason": str(e)}
