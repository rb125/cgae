"""
Modal-aware data loader for Streamlit dashboard.

When deployed to Streamlit Cloud, reads from Modal web endpoints.
When running locally, reads from local filesystem.
"""

import os
import json
import requests
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def _normalize_modal_endpoint(endpoint: str) -> str:
    """
    Normalize endpoint input to a get-results URL.

    Supports either:
    - Direct endpoint: https://<workspace>--<app>-get-results.modal.run
    - Modal app page: https://modal.com/apps/<workspace>/<env>/deployed/<app>
    """
    normalized = endpoint.strip().rstrip("/")
    parsed = urlparse(normalized)
    parts = [p for p in parsed.path.split("/") if p]

    if parsed.netloc == "modal.com" and len(parts) >= 5 and parts[0] == "apps" and parts[3] == "deployed":
        workspace = parts[1]
        app_name = parts[4]
        return f"https://{workspace}--{app_name}-get-results.modal.run"

    return normalized


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
    """Resolve endpoint from env first, then Streamlit secrets."""
    endpoint = os.getenv("MODAL_ENDPOINT")
    if endpoint:
        return _normalize_modal_endpoint(endpoint)

    try:
        import streamlit as st

        secret_value = st.secrets.get("MODAL_ENDPOINT")
        if secret_value:
            return _normalize_modal_endpoint(str(secret_value))
    except Exception:
        pass

    return None


MODAL_ENDPOINT = _resolve_modal_endpoint()
IS_CLOUD = bool(MODAL_ENDPOINT)


def load_json_file(filename: str, results_dir: Optional[Path] = None) -> dict:
    """
    Load a JSON result file.
    
    - On Streamlit Cloud: Fetch from Modal web endpoint
    - Locally: Read from filesystem
    """
    if IS_CLOUD:
        return _load_from_modal(filename)
    else:
        return _load_from_filesystem(filename, results_dir)


def _load_from_modal(filename: str) -> dict:
    """Load from Modal web endpoint."""
    try:
        url = _append_query_param(MODAL_ENDPOINT, "path", filename)
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return {}
        else:
            print(f"Error loading {filename} from Modal: {response.status_code}")
            return {}
    except Exception as e:
        print(f"Error loading {filename} from Modal: {e}")
        return {}


def _load_from_filesystem(filename: str, results_dir: Optional[Path]) -> dict:
    """Load from local filesystem."""
    if results_dir is None:
        return {}
    
    file_path = results_dir / filename
    
    if not file_path.exists():
        return {}
    
    try:
        with open(file_path) as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filename} from filesystem: {e}")
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
