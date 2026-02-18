"""
CGAE Filecoin Storage — Python Interface
=========================================
Uploads CGAE audit certificates to Filecoin via the Synapse SDK Node.js
uploader script (storage/upload_to_synapse.mjs).

Usage:
    from storage.filecoin_store import FilecoinStore, StoreResult

    store = FilecoinStore()
    result = store.store_audit_result(model_name, audit_json_path)
    print(result.cid)     # "bafk..." or deterministic fallback CID

Filecoin Integration:
    Real uploads require:
      1. Node.js 18+ with `@filoz/synapse-sdk` installed in storage/
      2. FILECOIN_PRIVATE_KEY env var (hex, no 0x prefix)
      3. Wallet funded with tUSDFC on Calibnet
         Faucet: https://forest-explorer.chainsafe.dev/faucet/calibnet_usdfc

    Without credentials the store falls back to a deterministic content-
    addressed CID (SHA-256 of the JSON) so the rest of the pipeline always
    has a CID to work with.  The 'real' field on StoreResult tells callers
    which mode was used.

On-chain anchoring:
    After a successful upload, pass result.cid to CGAERegistry.certify()
    so the Calibnet registry permanently references the Filecoin proof.

Network:
    Default: Filecoin Calibration Testnet (chain 314159)
    RPC:     https://api.calibration.node.glif.io/rpc/v1
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Load .env automatically so FILECOIN_PRIVATE_KEY is available
# even when the user hasn't manually exported it in the shell.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_STORAGE_DIR = Path(__file__).resolve().parent
_UPLOADER_SCRIPT = _STORAGE_DIR / "upload_to_synapse.mjs"

# Calibnet defaults (overridable via env)
CALIBNET_RPC = "https://api.calibration.node.glif.io/rpc/v1"
CALIBNET_CHAIN_ID = 314159
CALIBNET_EXPLORER = "https://calibration.filscan.io"

TUFIL_FAUCET = "https://faucet.calibnet.chainsafe-fil.io/funds.html"
TUSDFC_FAUCET = "https://forest-explorer.chainsafe.dev/faucet/calibnet_usdfc"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class StoreResult:
    """Result of a Filecoin store operation."""
    cid: str                     # PieceCID (real) or sha256-derived (fallback)
    real: bool                   # True = uploaded to Filecoin; False = fallback
    model_name: str
    file_path: str
    size_bytes: int = 0
    network: str = "calibration"
    tx_hash: Optional[str] = None
    error: Optional[str] = None  # Set when real=False due to an error

    @property
    def explorer_url(self) -> Optional[str]:
        """Calibration explorer link (only meaningful for real CIDs)."""
        if self.real:
            return f"{CALIBNET_EXPLORER}/cid/{self.cid}"
        return None

    def to_dict(self) -> dict:
        return {
            "cid": self.cid,
            "real": self.real,
            "model_name": self.model_name,
            "file_path": self.file_path,
            "size_bytes": self.size_bytes,
            "network": self.network,
            "tx_hash": self.tx_hash,
            "error": self.error,
            "explorer_url": self.explorer_url,
        }


# ---------------------------------------------------------------------------
# FilecoinStore
# ---------------------------------------------------------------------------

class FilecoinStore:
    """
    Uploads audit JSON files to Filecoin via the Synapse SDK.

    Constructor args:
        network:     "calibration" (default) or "mainnet"
        private_key: Wallet private key (hex, no 0x). Falls back to
                     FILECOIN_PRIVATE_KEY env var.
        node_cmd:    Path to the `node` executable. Auto-detected.
        fallback_ok: If True (default), use deterministic CID when upload
                     fails instead of raising. Always True for demo runs.
    """

    def __init__(
        self,
        network: str = "calibration",
        private_key: Optional[str] = None,
        node_cmd: Optional[str] = None,
        fallback_ok: bool = True,
    ):
        self.network = network
        self._private_key = private_key or os.getenv("FILECOIN_PRIVATE_KEY")
        self._node = node_cmd or _find_node()
        self.fallback_ok = fallback_ok

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def store_audit_result(
        self,
        model_name: str,
        json_path: str | Path,
    ) -> StoreResult:
        """
        Upload an audit result JSON to Filecoin.

        Returns a StoreResult.  If upload fails and fallback_ok=True,
        returns a fallback result with real=False and a deterministic CID.
        """
        json_path = Path(json_path)
        if not json_path.exists():
            raise FileNotFoundError(f"Audit file not found: {json_path}")

        # --- Attempt real Synapse upload ---
        if self._can_upload():
            try:
                return self._upload_via_synapse(model_name, json_path)
            except Exception as e:
                msg = str(e)
                logger.warning(
                    f"  [filecoin] Synapse upload failed for {model_name}: {msg}. "
                    f"Using deterministic fallback CID."
                )
                if not self.fallback_ok:
                    raise
                return self._fallback_result(model_name, json_path, error=msg)
        else:
            reason = self._unavailable_reason()
            logger.info(
                f"  [filecoin] Synapse upload unavailable ({reason}). "
                f"Using deterministic CID for {model_name}."
            )
            return self._fallback_result(model_name, json_path, error=reason)

    def store_bytes(
        self,
        model_name: str,
        data: bytes,
        filename: str,
        cache_dir: Optional[Path] = None,
    ) -> StoreResult:
        """
        Store raw bytes.  Writes to a temp file then calls store_audit_result().
        cache_dir defaults to the system temp dir.
        """
        import tempfile
        tmp_dir = cache_dir or Path(tempfile.gettempdir())
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / filename
        tmp_path.write_bytes(data)
        return self.store_audit_result(model_name, tmp_path)

    # ------------------------------------------------------------------
    # Internal: real upload
    # ------------------------------------------------------------------

    def _can_upload(self) -> bool:
        return (
            self._node is not None
            and _UPLOADER_SCRIPT.exists()
            and self._private_key is not None
        )

    def _unavailable_reason(self) -> str:
        if self._node is None:
            return "node.js not found in PATH"
        if not _UPLOADER_SCRIPT.exists():
            return f"uploader script missing: {_UPLOADER_SCRIPT}"
        if self._private_key is None:
            return "FILECOIN_PRIVATE_KEY not set"
        return "unknown"

    def _upload_via_synapse(self, model_name: str, json_path: Path) -> StoreResult:
        """Call upload_to_synapse.mjs via subprocess and parse the result."""
        env = {**os.environ}
        if self._private_key:
            env["FILECOIN_PRIVATE_KEY"] = self._private_key
        env["FILECOIN_NETWORK"] = self.network

        cmd = [self._node, str(_UPLOADER_SCRIPT), str(json_path),
               "--network", self.network]

        logger.info(f"  [filecoin] Uploading {json_path.name} for {model_name}...")
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )

        if proc.returncode == 2:
            # Exit code 2 = SDK not installed (soft fail)
            raise RuntimeError(
                "Synapse SDK not installed. Run: "
                "cd storage && npm install @filoz/synapse-sdk ethers"
            )

        if proc.returncode != 0:
            stderr = proc.stderr.strip()
            try:
                err_data = json.loads(stderr)
                raise RuntimeError(err_data.get("error", stderr))
            except (json.JSONDecodeError, KeyError):
                raise RuntimeError(stderr or f"exit code {proc.returncode}")

        # Parse success JSON from stdout
        stdout = proc.stdout.strip()
        data = json.loads(stdout)
        if not data.get("ok"):
            raise RuntimeError(data.get("error", "Unknown upload error"))

        cid = data["cid"]
        size = data.get("size", json_path.stat().st_size)
        tx = data.get("txHash")

        logger.info(
            f"  [filecoin] Uploaded {json_path.name} → CID {cid} "
            f"({size} bytes, network={self.network})"
        )
        return StoreResult(
            cid=cid,
            real=True,
            model_name=model_name,
            file_path=str(json_path),
            size_bytes=size,
            network=self.network,
            tx_hash=tx,
        )

    # ------------------------------------------------------------------
    # Internal: fallback (deterministic content-addressed CID)
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback_result(
        model_name: str,
        json_path: Path,
        error: Optional[str] = None,
    ) -> StoreResult:
        """
        Generate a deterministic pseudo-CID from file content (SHA-256).
        Format: bafk2bzace<sha256_hex_first_50>
        This is NOT a real IPFS/Filecoin CID but has the same prefix pattern
        and is stable across runs for the same file content.
        """
        content = json_path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        # Mimic CIDv1 base32 prefix used by Filecoin
        pseudo_cid = f"bafk2bzace{digest[:50]}"
        size = len(content)

        return StoreResult(
            cid=pseudo_cid,
            real=False,
            model_name=model_name,
            file_path=str(json_path),
            size_bytes=size,
            network="calibration",
            error=error,
        )


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

_default_store: Optional[FilecoinStore] = None


def get_store(**kwargs) -> FilecoinStore:
    """Return (or create) the default FilecoinStore singleton."""
    global _default_store
    if _default_store is None:
        _default_store = FilecoinStore(**kwargs)
    return _default_store


def store_audit_json(
    model_name: str,
    json_path: str | Path,
    network: str = "calibration",
) -> StoreResult:
    """
    Convenience wrapper: upload an audit JSON and return the StoreResult.
    Used directly in cgae_engine/audit.py after audit_live().
    """
    store = FilecoinStore(network=network)
    return store.store_audit_result(model_name, json_path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_node() -> Optional[str]:
    """Find the node executable in PATH."""
    candidates = ["node", "nodejs"]
    for name in candidates:
        try:
            result = subprocess.run(
                [name, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return name
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


def check_setup() -> dict:
    """
    Return a setup status dict useful for the demo / README quickstart.
    Shows which parts of the Filecoin integration are ready.
    """
    node = _find_node()
    sdk_installed = False
    if node:
        nm = _STORAGE_DIR / "node_modules" / "@filoz" / "synapse-sdk"
        sdk_installed = nm.exists()
    has_key = bool(os.getenv("FILECOIN_PRIVATE_KEY"))
    script_ok = _UPLOADER_SCRIPT.exists()

    ready = node and sdk_installed and has_key and script_ok
    return {
        "ready": ready,
        "node_found": node,
        "sdk_installed": sdk_installed,
        "private_key_set": has_key,
        "uploader_script": script_ok,
        "network": os.getenv("FILECOIN_NETWORK", "calibration"),
        "instructions": (
            None if ready else
            "To enable real Filecoin uploads:\n"
            "  1. cd storage && npm install @filoz/synapse-sdk ethers\n"
            f"  2. Get tFIL: {TUFIL_FAUCET}\n"
            f"  3. Get tUSDFC: {TUSDFC_FAUCET}\n"
            "  4. export FILECOIN_PRIVATE_KEY=<your_hex_private_key>\n"
            "  5. Re-run the simulation"
        ),
    }


if __name__ == "__main__":
    # Quick setup check
    status = check_setup()
    print(json.dumps(status, indent=2))
